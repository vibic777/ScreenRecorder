import ctypes
from ctypes import wintypes as wt
import os
import threading
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsWindow.argtypes = [wt.HWND]
user32.IsIconic.argtypes = [wt.HWND]
CALLBACK = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [CALLBACK, wt.LPARAM]


def windows():
    result = []
    @CALLBACK
    def visit(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd)
        if not length or not user32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        rect = wt.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)) and rect.right > rect.left and rect.bottom > rect.top:
            result.append({"kind": "window", "hwnd": int(hwnd), "pid": pid.value,
                           "title": title.value, "width": rect.right-rect.left, "height": rect.bottom-rect.top})
        return True
    if not user32.EnumWindows(visit, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return sorted(result, key=lambda item: item["title"].casefold())


class WindowSource:
    def __init__(self, target):
        self.target = target
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.closed = False
        self.frame = None
        self.control = None
        self.last_frame = 0
        self.width = self.height = 0

    def validate(self):
        pid = wt.DWORD()
        hwnd = self.target["hwnd"]
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not user32.IsWindow(hwnd) or pid.value != self.target["pid"]:
            raise RuntimeError("Выбранное окно закрыто. Выберите окно заново.")

    def __enter__(self):
        if os.environ.get("SCREENREC_QT") == "PySide2":
            # Windows Graphics Capture is Windows 10+ only.  The legacy
            # profile uses the Win8-compatible desktop grabber instead.
            from PIL import ImageGrab
            self.validate()
            rect = wt.RECT()
            user32.GetWindowRect(self.target["hwnd"], ctypes.byref(rect))
            if rect.right <= rect.left or rect.bottom <= rect.top:
                raise RuntimeError("У выбранного окна недоступный размер.")
            self.legacy_grab = ImageGrab
            self.legacy_rect = (rect.left, rect.top, rect.right, rect.bottom)
            self.width = rect.right - rect.left
            self.height = rect.bottom - rect.top
            return self
        from windows_capture import WindowsCapture
        self.validate()
        if user32.IsIconic(self.target["hwnd"]):
            raise RuntimeError("Разверните выбранное окно перед началом записи.")
        self.capture = WindowsCapture(window_hwnd=self.target["hwnd"], cursor_capture=False)
        @self.capture.event
        def on_frame_arrived(frame, capture_control):
            with self.lock:
                self.frame = frame.frame_buffer.copy()
                self.last_frame = time.monotonic()
                self.ready.set()
        @self.capture.event
        def on_closed():
            self.closed = True
            self.ready.set()
        self.control = self.capture.start_free_threaded()
        if not self.ready.wait(8) or self.frame is None:
            self.__exit__()
            raise RuntimeError("Windows не предоставила кадр выбранного окна. Оно может быть защищено или недоступно.")
        self.height, self.width = self.frame.shape[:2]
        return self

    def grab(self):
        if hasattr(self, "legacy_grab"):
            import numpy as np
            self.validate()
            rect = wt.RECT()
            user32.GetWindowRect(self.target["hwnd"], ctypes.byref(rect))
            box = (rect.left, rect.top, rect.right, rect.bottom)
            image = np.asarray(self.legacy_grab.grab(bbox=box).convert("RGBA"))
            image = image[:, :, [2, 1, 0, 3]]
            return image.tobytes()
        import cv2
        import numpy as np
        self.validate()
        if self.closed:
            raise RuntimeError("Источник окна закрылся.")
        if user32.IsIconic(self.target["hwnd"]) and time.monotonic() - self.last_frame > 2:
            raise RuntimeError("Windows приостановила кадры свёрнутого окна. Запись остановлена; разверните окно и начните снова.")
        with self.lock:
            image = self.frame
        height, width = image.shape[:2]
        if (width, height) != (self.width, self.height):
            ratio = min(self.width / width, self.height / height)
            scaled = cv2.resize(image, (max(1, round(width * ratio)), max(1, round(height * ratio))))
            image = np.zeros((self.height, self.width, 4), dtype=np.uint8)
            y, x = (self.height-scaled.shape[0])//2, (self.width-scaled.shape[1])//2
            image[y:y+scaled.shape[0], x:x+scaled.shape[1]] = scaled
        return image.tobytes()

    def __exit__(self, *_):
        if self.control:
            self.control.stop()
            self.control = None
