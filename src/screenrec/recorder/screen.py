import os
import platform

import mss


def check_platform():
    system = platform.system()
    if system not in ("Windows", "Linux"):
        raise RuntimeError("Первый этап поддерживает Windows и Linux (X11).")
    if system == "Linux" and (os.environ.get("XDG_SESSION_TYPE") == "wayland" or os.environ.get("WAYLAND_DISPLAY")):
        raise RuntimeError("Захват Wayland пока не реализован. Войдите в сеанс X11 для записи экрана.")


def monitors():
    check_platform()
    with mss.mss() as capture:
        return [dict(monitor) for monitor in capture.monitors[1:]]


class ScreenSource:
    def __init__(self, monitor):
        self.monitor = monitor
        self.capture = None

    def __enter__(self):
        check_platform()
        self.capture = mss.mss()
        return self

    def grab(self):
        region = {key: self.monitor[key] for key in ("left", "top", "width", "height")}
        return self.capture.grab(region).bgra

    def __exit__(self, *_):
        self.capture.close()
