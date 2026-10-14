"""Compatibility options for Windows Graphics Capture API versions."""
import sys


def cursor_capture_option(enabled):
    """Only set IsCursorCaptureEnabled on Windows 10 2004 (build 19041)+.

    The Windows Graphics Capture API itself is available from Windows 10 1803,
    but the cursor toggle was added in 2004. Passing None leaves the OS default
    untouched and avoids calling that newer property on older supported builds.
    """
    try:
        if sys.getwindowsversion().build >= 19041:
            return enabled
    except (AttributeError, OSError):
        pass
    return None
