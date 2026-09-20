import subprocess
import tempfile
import threading
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe
from screenrec.config.recording import video_options
from screenrec.logger.logger import get_logger
log = get_logger(__name__)


class Encoder:
    """Write BGRA frames, finalize on EOF, keep diagnostics out of pipe buffers."""

    def __init__(self, path: Path, width: int, height: int, fps: int, file_format="mp4", quality="balanced", overlay=None, overlay_path=None):
        if path.exists():
            raise FileExistsError(f"Файл уже существует: {path}")
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
        inputs, options = ffmpeg_options(video_options(file_format, quality, fps), overlay_path)
        self.errors = tempfile.TemporaryFile()
        self.process = None
        self.timed_out = False
        try:
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
            self.errors.close()
            if self.overlay_directory:
                self.overlay_directory.cleanup()
            raise

    def write(self, frame):
        if self.process.poll() is not None:
            raise RuntimeError("Кодировщик завершился до записи первого кадра.")
        self.process.stdin.write(frame)

    def abort(self):
        if self.process.poll() is None:
            log.critical("Encoder timeout: terminating process")
            self.timed_out = True
            self.process.kill()

    def finish(self):
        watchdog = threading.Timer(15, self.abort)
        watchdog.daemon = True
        watchdog.start()
        try:
            try:
                self.process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
            code = self.process.wait(timeout=20)
            self.errors.seek(0)
            diagnostic = self.errors.read().decode("utf-8", errors="replace").strip()
            log.debug("Encoder exit: code=%s timed_out=%s",code,self.timed_out)
            if code or self.timed_out:
                log.error("Encoder finalization failed")
                raise RuntimeError(diagnostic or "Кодировщик не завершил запись вовремя.")
        finally:
            watchdog.cancel()
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            self.errors.close()
            if self.overlay_directory:
                self.overlay_directory.cleanup()
