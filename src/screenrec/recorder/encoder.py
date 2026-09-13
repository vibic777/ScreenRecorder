import subprocess
import tempfile
import threading
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe
from screenrec.config.recording import video_options


class Encoder:
    """Write BGRA frames, finalize on EOF, keep diagnostics out of pipe buffers."""

    def __init__(self, path: Path, width: int, height: int, fps: int, file_format="mp4", quality="balanced"):
        if path.exists():
            raise FileExistsError(f"Файл уже существует: {path}")
        self.errors = tempfile.TemporaryFile()
        self.process = None
        self.timed_out = False
        try:
            self.process = subprocess.Popen(
                [get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-n",
                 "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
                 "-framerate", str(fps), "-i", "pipe:0", "-an"]
                + video_options(file_format, quality, fps) + [str(path)],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self.errors,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except BaseException:
            self.errors.close()
            raise

    def write(self, frame):
        self.process.stdin.write(frame)

    def abort(self):
        if self.process.poll() is None:
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
            if code or self.timed_out:
                raise RuntimeError(diagnostic or "Кодировщик не завершил запись вовремя.")
        finally:
            watchdog.cancel()
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            self.errors.close()
