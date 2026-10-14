from screenrec.localization import tr
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
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
user32.PrintWindow.restype = wt.BOOL


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
            raise RuntimeError(tr("error.window_closed"))

    def __enter__(self):
        if os.environ.get("SCREENREC_QT") == "PySide2":
            # Windows Graphics Capture is Windows 10+ only; use PrintWindow
            # for the Legacy profile on Windows 8/8.1.
            self.validate()
            if user32.IsIconic(self.target["hwnd"]):
                raise RuntimeError(tr("error.window_minimized"))
            rect = wt.RECT()
            if not user32.GetWindowRect(self.target["hwnd"], ctypes.byref(rect)) or rect.right <= rect.left or rect.bottom <= rect.top:
                raise RuntimeError(tr("error.window_size"))
            self.legacy_rect = (rect.left, rect.top, rect.right, rect.bottom)
            self.width = rect.right - rect.left
            self.height = rect.bottom - rect.top
            self._open_printwindow()
            self.printwindow_capture = True
            return self
        try:
            from windows_capture import WindowsCapture
            from .windows_capture_compat import cursor_capture_option
            cursor_capture = cursor_capture_option(False)
            self.capture = WindowsCapture(window_hwnd=self.target["hwnd"], cursor_capture=cursor_capture)
            @self.capture.event
            def on_frame_arrived(frame, capture_control):
                # Retain only the newest frame and copy it before the callback
                # releases the native capture buffer.
                with self.lock:
                    import numpy as np
                    self.frame = np.array(frame.frame_buffer, copy=True, order="C")
                    self.last_frame = time.monotonic()
                    self.ready.set()
            @self.capture.event
            def on_closed():
                self.closed = True
                self.ready.set()
            self.control = self.capture.start_free_threaded()
            if not self.ready.wait(8) or self.frame is None:
                self.__exit__()
                raise RuntimeError(tr("error.window_no_frame"))
            self.height, self.width = self.frame.shape[:2]
            return self
        except Exception:
            # WGC can reject otherwise valid HWNDs on some supported Windows
            # builds. Preserve window mode with a desktop rectangle grab.
            if self.control:
                self.__exit__()
            self.capture = None
            rect = wt.RECT()
            if not user32.GetWindowRect(self.target["hwnd"], ctypes.byref(rect)) or rect.right <= rect.left or rect.bottom <= rect.top:
                raise RuntimeError(tr("error.window_size"))
            self.legacy_rect = (rect.left, rect.top, rect.right, rect.bottom)
            self.width, self.height = rect.right - rect.left, rect.bottom - rect.top
            self._open_printwindow()
            self.fallback_capture = True
            return self
    def _open_printwindow(self):
        class BitmapInfoHeader(ctypes.Structure):
            _fields_ = [("size", wt.DWORD), ("width", wt.LONG), ("height", wt.LONG),
                        ("planes", wt.WORD), ("bit_count", wt.WORD), ("compression", wt.DWORD),
                        ("image_size", wt.DWORD), ("xppm", wt.LONG), ("yppm", wt.LONG),
                        ("used", wt.DWORD), ("important", wt.DWORD)]
        class BitmapInfo(ctypes.Structure):
            _fields_ = [("header", BitmapInfoHeader), ("colors", wt.DWORD * 3)]
        gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        gdi.CreateCompatibleDC.argtypes = [wt.HDC]
        gdi.CreateCompatibleDC.restype = wt.HDC
        gdi.CreateDIBSection.argtypes = [wt.HDC, ctypes.POINTER(BitmapInfo), wt.UINT,
                                         ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
        gdi.CreateDIBSection.restype = wt.HANDLE
        gdi.SelectObject.argtypes = [wt.HDC, wt.HANDLE]
        gdi.SelectObject.restype = wt.HANDLE
        gdi.DeleteObject.argtypes = [wt.HANDLE]
        gdi.DeleteObject.restype = wt.BOOL
        gdi.DeleteDC.argtypes = [wt.HDC]
        gdi.DeleteDC.restype = wt.BOOL
        self._gdi = gdi
        self._memory_dc = gdi.CreateCompatibleDC(None)
        info = BitmapInfo()
        info.header = BitmapInfoHeader(ctypes.sizeof(BitmapInfoHeader), self.width, -self.height,
                                       1, 32, 0, self.width * self.height * 4, 0, 0, 0, 0)
        pixels = ctypes.c_void_p()
        self._bitmap = gdi.CreateDIBSection(self._memory_dc, ctypes.byref(info), 0,
                                            ctypes.byref(pixels), None, 0)
        if not self._memory_dc or not self._bitmap or not pixels.value:
            self._close_printwindow()
            raise ctypes.WinError(ctypes.get_last_error())
        self._gdi = gdi
        self._old_bitmap = gdi.SelectObject(self._memory_dc, self._bitmap)
        self._pixels = pixels.value

    def _close_printwindow(self):
        gdi = getattr(self, "_gdi", None)
        if gdi:
            if getattr(self, "_old_bitmap", None):
                gdi.SelectObject(self._memory_dc, self._old_bitmap)
            if getattr(self, "_bitmap", None):
                gdi.DeleteObject(self._bitmap)
            if getattr(self, "_memory_dc", None):
                gdi.DeleteDC(self._memory_dc)
        self._gdi = self._bitmap = self._memory_dc = self._old_bitmap = None
        self._pixels = None
    def grab(self):
        if getattr(self, "fallback_capture", False) or getattr(self, "printwindow_capture", False):
            self.validate()
            if user32.IsIconic(self.target["hwnd"]):
                raise RuntimeError(tr("error.window_minimized"))
            rect = wt.RECT()
            if not user32.GetWindowRect(self.target["hwnd"], ctypes.byref(rect)):
                raise RuntimeError(tr("error.window_closed"))
            if ((rect.left, rect.top, rect.right, rect.bottom) != self.legacy_rect
                    and getattr(self, "printwindow_capture", False)):
                raise RuntimeError(tr("error.window_size"))
            if (rect.right - rect.left, rect.bottom - rect.top) != (self.width, self.height):
                raise RuntimeError(tr("error.window_size"))
            if not user32.PrintWindow(self.target["hwnd"], self._memory_dc, 2):
                raise RuntimeError(tr("error.window_no_frame"))
            return ctypes.string_at(self._pixels, self.width * self.height * 4)
        import cv2
        import numpy as np
        self.validate()
        if self.closed:
            raise RuntimeError(tr("error.window_source_closed"))
        if user32.IsIconic(self.target["hwnd"]) and time.monotonic() - self.last_frame > 2:
            raise RuntimeError(tr("error.window_paused"))
        with self.lock:
            image = self.frame
        if image is None:
            raise RuntimeError(tr("error.window_no_frame"))
        height, width = image.shape[:2]
        if (width, height) != (self.width, self.height):
            ratio = min(self.width / width, self.height / height)
            scaled = cv2.resize(image, (max(1, round(width * ratio)), max(1, round(height * ratio))))
            image = np.zeros((self.height, self.width, 4), dtype=np.uint8)
            y, x = (self.height-scaled.shape[0])//2, (self.width-scaled.shape[1])//2
            image[y:y+scaled.shape[0], x:x+scaled.shape[1]] = scaled
        return memoryview(image).cast("B")

    def __exit__(self, *_):
        if getattr(self, "fallback_capture", False) or getattr(self, "printwindow_capture", False):
            self._close_printwindow()
        if self.control:
            self.control.stop()
            self.control = None
