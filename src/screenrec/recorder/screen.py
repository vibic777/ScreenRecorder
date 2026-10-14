from screenrec.localization import tr
import os
import platform
import threading
import time

import mss
from screenrec.logger.logger import get_logger
log = get_logger(__name__)


def check_platform():
    system = platform.system()
    if system not in ("Windows", "Linux"):
        raise RuntimeError(tr("error.screen_platform"))
    if system == "Linux" and (os.environ.get("XDG_SESSION_TYPE") == "wayland" or os.environ.get("WAYLAND_DISPLAY")):
        raise RuntimeError(tr("error.wayland"))


def monitors():
    check_platform()
    with mss.mss() as capture:
        return [dict(monitor) for monitor in capture.monitors[1:]]


class ScreenSource:
    def __init__(self, monitor):
        self.monitor = monitor
        self.region = {key: monitor[key] for key in ("left", "top", "width", "height")}
        self.capture = None
        self.capture_control = None
        self.frame_lock = threading.Lock()
        self.frame_ready = threading.Event()
        self.frame = None
        self.capture_closed = False
        self.capture_error = None
        self.last_frame_time = 0.0
        self.first_frame = None

    def __enter__(self):
        check_platform()
        if platform.system() == "Windows" and os.environ.get("SCREENREC_QT", "PySide6") == "PySide6":
            if self.monitor.get("kind") == "region":
                try:
                    # A region is cheaper to capture directly than to capture
                    # a whole display with WGC and crop every callback frame.
                    self.capture = mss.MSS()
                    self.first_frame = self.capture.grab(self.region).raw
                    log.info("Using MSS for selected region: %s", self.region)
                    return self
                except Exception as exc:
                    log.exception("MSS region capture unavailable")
                    if self.capture:
                        try:
                            self.capture.close()
                        except Exception:
                            log.debug("Failed MSS region probe was already closed", exc_info=True)
                    self.capture = None
                    self.first_frame = None
                    raise RuntimeError(tr("error.screen_region_capture_failed", error=exc)) from exc
            try:
                self._open_windows_capture()
                return self
            except Exception:
                log.warning("Windows Graphics Capture unavailable; falling back to mss", exc_info=True)
                if self.capture_control:
                    try:
                        self.capture_control.stop()
                    except Exception:
                        log.debug("Failed WGC session was already closed", exc_info=True)
                    finally:
                        self.capture_control = None
                self.capture = None
        log.debug("Opening mss screen capture: monitor=%s", self.monitor)
        self.capture = mss.mss()
        log.debug("mss screen capture opened")
        return self

    def _open_windows_capture(self):
        from windows_capture import WindowsCapture
        from .windows_capture_compat import cursor_capture_option

        # windows-capture uses the same one-based display order as MSS. Find
        # the physical display containing this full-monitor or region source.
        with mss.mss() as displays:
            monitor_index = next((index for index, display in enumerate(displays.monitors[1:], 1)
                                  if display["left"] <= self.region["left"]
                                  and display["top"] <= self.region["top"]
                                  and display["left"] + display["width"] >= self.region["left"] + self.region["width"]
                                  and display["top"] + display["height"] >= self.region["top"] + self.region["height"]), None)
            if monitor_index is None:
                raise RuntimeError("Capture region does not fit on a physical monitor")
            display = displays.monitors[monitor_index]
        self._display = display
        self._crop = (self.region["left"] - display["left"],
                      self.region["top"] - display["top"],
                      self.region["width"], self.region["height"])
        cursor_capture = cursor_capture_option(True)
        log.debug("Starting WGC monitor capture: monitor=%s region=%s cursor_capture=%s",
                  monitor_index, self.region, cursor_capture)
        self.capture = WindowsCapture(monitor_index=monitor_index, cursor_capture=cursor_capture)

        @self.capture.event
        def on_frame_arrived(frame, capture_control):
            try:
                import numpy as np
                image = frame.frame_buffer
                x, y, width, height = self._crop
                if image.ndim != 3 or image.shape[2] != 4 or image.shape[:2] != (frame.height, frame.width):
                    raise RuntimeError("Windows Graphics Capture returned an invalid frame")
                if x < 0 or y < 0 or x + width > frame.width or y + height > frame.height:
                    raise RuntimeError("Windows Graphics Capture frame does not contain the selected region")
                if x or y or width != frame.width or height != frame.height:
                    image = image[y:y + height, x:x + width]
                owned = np.array(image, copy=True, order="C")
                if owned.shape != (height, width, 4):
                    raise RuntimeError("Windows Graphics Capture returned an incomplete frame")
                with self.frame_lock:
                    self.frame = owned
                    self.last_frame_time = time.monotonic()
                    self.frame_ready.set()
            except Exception as exc:
                with self.frame_lock:
                    self.capture_error = exc
                    self.frame_ready.set()

        @self.capture.event
        def on_closed():
            with self.frame_lock:
                self.capture_closed = True
                self.frame_ready.set()

        self.capture_control = self.capture.start_free_threaded()
        log.debug("WGC monitor capture thread started")
        if not self.frame_ready.wait(8):
            raise RuntimeError(tr("error.screen_no_frame"))
        with self.frame_lock:
            if self.capture_error:
                raise RuntimeError(tr("error.screen_capture_invalid")) from self.capture_error
            if self.capture_closed or self.frame is None:
                raise RuntimeError(tr("error.screen_capture_closed" if self.capture_closed else "error.screen_no_frame"))
        log.debug("Windows Graphics Capture opened: display=%s crop=%s", monitor_index, self._crop)

    def grab(self):
        if self.first_frame is not None:
            frame, self.first_frame = self.first_frame, None
            return frame
        if self.capture_control:
            with self.frame_lock:
                frame = self.frame
                capture_closed = self.capture_closed
                capture_error = self.capture_error
                last_frame_time = self.last_frame_time
            reason = None
            if capture_error:
                reason = tr("error.screen_capture_invalid")
            elif capture_closed:
                reason = tr("error.screen_capture_closed")
            elif frame is None:
                reason = tr("error.screen_no_frame")
            elif time.monotonic() - last_frame_time > 2.0:
                reason = tr("error.screen_capture_stalled")
            if reason is None:
                return memoryview(frame).cast("B")
            log.warning("Windows Graphics Capture stopped; switching to mss: %s", reason,
                        exc_info=(type(capture_error), capture_error, capture_error.__traceback__) if capture_error else None)
            control, self.capture_control = self.capture_control, None
            try:
                control.stop()
            except Exception:
                log.debug("Stopped WGC session during fallback", exc_info=True)
            self.capture = mss.mss()
            log.info("mss screen capture fallback opened")
        # raw is already an owned BGRA bytearray; .bgra copies the whole frame.
        return self.capture.grab(self.region).raw

    def __exit__(self, *_):
        if self.capture_control:
            try:
                self.capture_control.stop()
            except Exception:
                log.debug("Windows Graphics Capture session already stopped", exc_info=True)
            finally:
                self.capture_control = None
        if self.capture:
            if hasattr(self.capture, "close"):
                self.capture.close()
            self.capture = None
