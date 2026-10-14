"""Platform-isolated window capture; never falls back to a desktop crop."""
import platform


def windows():
    if platform.system() == "Windows":
        from .window_windows import windows as enumerate_windows
    else:
        from .window_x11 import windows as enumerate_windows
    return enumerate_windows()


def source(target):
    if platform.system() == "Windows":
        from .window_windows import WindowSource
    else:
        from .window_x11 import WindowSource
    return WindowSource(target)
