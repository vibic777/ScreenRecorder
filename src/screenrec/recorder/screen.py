from screenrec.localization import tr
import os
import platform

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
        self.capture = None

    def __enter__(self):
        check_platform()
        log.debug("Opening mss screen capture: monitor=%s", self.monitor)
        self.capture = mss.mss()
        log.debug("mss screen capture opened")
        return self

    def grab(self):
        region = {key: self.monitor[key] for key in ("left", "top", "width", "height")}
        log.trace("Grabbing screen region: %s", region)
        return self.capture.grab(region).bgra

    def __exit__(self, *_):
        self.capture.close()
