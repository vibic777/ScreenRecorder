import threading
import time
from pathlib import Path
from screenrec.config.filenames import reserve

from PySide6.QtCore import QThread, Signal

from .encoder import Encoder
from .screen import ScreenSource
from .audio import AudioSession
from .muxer import mux_audio
from screenrec.config.settings import Settings


class RecordingWorker(QThread):
    recording_started = Signal(str)
    recording_saved = Signal(str)
    failed = Signal(str)
    finalizing = Signal()

    def __init__(self, monitor, directory, fps, parent=None, settings=None):
        super().__init__(parent)
        self.monitor = monitor
        self.directory = Path(directory)
        self.fps = fps
        self.stop_event = threading.Event()
        self.encoder = None
        self.settings = settings or Settings(fps=fps)

    def stop(self):
        self.stop_event.set()

    def run(self):
        path = None
        reservation = None
        error = None
        frames = 0
        audio = None
        parts = None
        tracks = []
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            path, reservation = reserve(self.directory, self.settings)
            video = path
            if self.settings.audio_mode != "none":
                parts = self.directory / f".{path.stem}.parts"
                parts.mkdir()
                video = parts / f"video.{self.settings.file_format}"
                audio = AudioSession(self.settings, parts)
                audio.prepare()
            if self.monitor.get('kind') == 'window':
                from .window import source as window_source
                capture_source = window_source(self.monitor)
            else:
                capture_source = ScreenSource(self.monitor)
            with capture_source as source:
                frame = source.grab()
                self.encoder = Encoder(video, getattr(source, "width", self.monitor["width"]), getattr(source, "height", self.monitor["height"]), self.fps,
                                       self.settings.file_format, self.settings.quality,
                                       overlay=self.settings.overlay if self.settings.overlay_enabled else None)
                start = time.monotonic()
                if audio:
                    audio.start(start)
                self.encoder.write(frame)
                frames = 1
                self.recording_started.emit(str(path))
                while not self.stop_event.is_set():
                    if audio:
                        audio.check()
                    if self.stop_event.wait(max(0, start + frames / self.fps - time.monotonic())):
                        break
                    frame = source.grab()
                    # Duplicate the last captured frame when capture is late, preserving duration.
                    target = max(frames + 1, int((time.monotonic() - start) * self.fps) + 1)
                    while frames < target and not self.stop_event.is_set():
                        self.encoder.write(frame)
                        frames += 1
        except Exception as exc:
            error = str(exc)
        finally:
            self.stop_event.set()
            self.finalizing.emit()
            if audio:
                try:
                    tracks = audio.finish(check=audio.origin is not None)
                except Exception as exc:
                    error = f"{error}\n{exc}" if error else str(exc)
            if self.encoder:
                try:
                    self.encoder.finish()
                except Exception as exc:
                    error = f"{error}\n{exc}" if error else str(exc)
                self.encoder = None
        if not error and audio and frames:
            try:
                mux_audio(video, tracks, path, self.settings, frames / self.fps)
                for file in [video, *(track[0] for track in tracks)]:
                    file.unlink()
                parts.rmdir()
            except Exception as exc:
                error = str(exc)
        if reservation:
            try:
                reservation.rmdir()
            except OSError:
                pass
        if error:
            suffix = f"\nФайл может быть неполным: {path}" if path and path.exists() else ""
            if parts:
                suffix += f"\nПромежуточные видео и звук сохранены: {parts}"
            self.failed.emit(error + suffix)
        elif frames:
            self.recording_saved.emit(str(path))
