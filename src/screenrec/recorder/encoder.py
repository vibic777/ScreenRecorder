from screenrec.localization import tr
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe
from screenrec.config.recording import video_options
from screenrec.logger.logger import get_logger
log = get_logger(__name__)


class Encoder:
    """Write BGRA frames, finalize on EOF, keep diagnostics out of pipe buffers."""
    WRITE_TIMEOUT = 15

    def __init__(self, path: Path, width: int, height: int, fps: int, file_format="mp4", quality="balanced", overlay=None, overlay_path=None):
        if width <= 0 or height <= 0 or fps <= 0:
            raise ValueError("Frame dimensions and FPS must be positive")
        self.frame_bytes = width * height * 4
        if path.exists():
            raise FileExistsError(tr("error.file_exists", path=path))
        self.overlay_directory = None
        from .overlay import enabled, prepare, ffmpeg_options
        if overlay_path is None and enabled(overlay):
            self.overlay_directory = tempfile.TemporaryDirectory(prefix="screenrec-overlay-")
            try:
                overlay_path = prepare(overlay, width, height, Path(self.overlay_directory.name) / "overlay.png")
            except BaseException:
                self.overlay_directory.cleanup()
                raise
        log.debug("Encoder setup: width=%s height=%s fps=%s format=%s overlays=%s",width,height,fps,file_format,overlay_path is not None)
        self.errors = None
        self.process = None
        self.timed_out = False
        try:
            inputs, options = ffmpeg_options(video_options(file_format, quality, fps), overlay_path)
            self.errors = tempfile.TemporaryFile()
            log.debug("Starting FFmpeg: input=%sx%s overlay=%s output=%s", width, height, overlay_path is not None, path)
            self.process = subprocess.Popen(
                [get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-n",
                 "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
                 "-framerate", str(fps), "-i", "pipe:0"]
                + inputs + ["-an"] + options + [str(path)],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self.errors,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            log.debug("FFmpeg process started: pid=%s", self.process.pid)
        except BaseException:
            if self.errors is not None:
                self.errors.close()
            if self.overlay_directory:
                self.overlay_directory.cleanup()
            raise

        self._write_deadline = None
        self._watchdog_stop = threading.Event()
        self._watchdog = threading.Thread(target=self._watch_writes, daemon=True)
        self._watchdog.start()

    def _watch_writes(self):
        while not self._watchdog_stop.wait(0.5):
            deadline = self._write_deadline
            if deadline is not None and time.monotonic() >= deadline:
                self.abort()
                return

    def write(self, frame):
        frame = memoryview(frame).cast("B")
        if frame.nbytes != self.frame_bytes:
            raise ValueError("Unexpected BGRA frame size")
        if self.process.poll() is not None:
            raise RuntimeError(tr("error.encoder_exited"))
        self._write_deadline = time.monotonic() + self.WRITE_TIMEOUT
        try:
            while frame:
                written = self.process.stdin.write(frame)
                if not written:
                    raise BrokenPipeError(tr("error.encoder_exited"))
                frame = frame[written:]
        finally:
            self._write_deadline = None

    def abort(self):
        if self.process.poll() is None:
            log.critical("Encoder timeout: terminating process")
            self.timed_out = True
            try:
                self.process.kill()
            except ProcessLookupError:
                pass

    def finish(self):
        watchdog = threading.Timer(15, self.abort)
        watchdog.daemon = True
        watchdog.start()
        try:
            # Closing a large buffered pipe may itself block while FFmpeg
            # drains input. Do it outside this thread so the watchdog can
            # still kill FFmpeg and unblock the writer on Windows.
            def close_stdin():
                try:
                    self.process.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
            closer = threading.Thread(target=close_stdin, daemon=True)
            closer.start()
            closer.join(16)
            if closer.is_alive():
                self.abort()
                closer.join(2)
                raise RuntimeError(tr("error.encoder_timeout"))
            try:
                code = self.process.wait(timeout=20)
            except (OSError, subprocess.TimeoutExpired):
                self.abort()
                raise RuntimeError(tr("error.encoder_timeout"))
            self.errors.seek(0)
            diagnostic = self.errors.read().decode("utf-8", errors="replace").strip()
            log.debug("Encoder exit: code=%s timed_out=%s",code,self.timed_out)
            if code or self.timed_out:
                log.error("Encoder finalization failed")
                raise RuntimeError(diagnostic or tr("error.encoder_timeout"))
        finally:
            watchdog.cancel()
            self._watchdog_stop.set()
            self._watchdog.join(2)
            # A child that outlives the bounded graceful wait must never turn
            # cleanup into an unbounded GUI shutdown. Escalate once and bound
            # reaping as well; close the pipe and diagnostics on every path.
            try:
                if self.process.poll() is None:
                    try:
                        self.process.kill()
                    except ProcessLookupError:
                        pass
                    except OSError:
                        log.exception("Could not terminate encoder process")
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        log.critical("Encoder process did not exit after kill")
                    except OSError:
                        log.exception("Could not reap encoder process")
                    except Exception:
                        log.exception("Unexpected error while reaping encoder process")
            finally:
                try:
                    if self.process.stdin and not self.process.stdin.closed:
                        self.process.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
                self.errors.close()
                if self.overlay_directory:
                    self.overlay_directory.cleanup()
