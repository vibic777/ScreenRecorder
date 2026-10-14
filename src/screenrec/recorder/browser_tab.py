"""Authenticated, loopback-only bridge for the bundled tabCapture extension."""
from screenrec.localization import tr
import hmac
import json
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from screenrec.config.filenames import reserve
from urllib.parse import urlsplit, parse_qs

from screenrec.qt.QtCore import QThread, Signal
from imageio_ffmpeg import get_ffmpeg_exe
from screenrec.config.recording import video_options
from .audio import AudioSession
from .muxer import mux_audio
from screenrec.logger.logger import get_logger
log = get_logger(__name__)


class TabSession:
    def __init__(self, path, settings):
        self.path = Path(path)
        self.settings = settings
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.started = threading.Event()
        self.ended = threading.Event()
        self.stop_requested = False
        self.ready = False
        self.error = None
        self.title = ""
        self.origin = None
        self.last_contact = time.monotonic()
        self.sequence = 0
        self.partial_sequence = None
        self.partial_offset = 0
        self.partial_total = None
        self.stream = self.path.open("wb")
        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler())
            self.server.daemon_threads = True
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
        except BaseException:
            if hasattr(self, "server"):
                self.server.server_close()
            self.stream.close()
            raise

    @property
    def pairing_code(self):
        return f"{self.server.server_port}:{self.token}"

    def handler(self):
        session = self
        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(10)

            def log_message(self, *_):
                pass

            def reply(self, code, value):
                data = json.dumps(value).encode()
                self.send_response(code)
                origin = self.headers.get("Origin", "")
                if origin.startswith("chrome-extension://"):
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "Content-Type,X-ScreenRec-Token,X-Chunk-Size")
                self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
                self.send_header("Access-Control-Allow-Private-Network", "true")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def allowed(self):
                origin = self.headers.get("Origin", "")
                return (self.headers.get("Host") == f"127.0.0.1:{session.server.server_port}"
                        and (not origin or origin.startswith("chrome-extension://"))
                        and hmac.compare_digest(self.headers.get("X-ScreenRec-Token", ""), session.token))

            def do_OPTIONS(self):
                if self.headers.get("Origin", "").startswith("chrome-extension://"):
                    self.reply(200, {})
                else:
                    self.reply(403, {"error": "Extension origin required"})

            def do_GET(self):
                if not self.allowed():
                    self.reply(403, {"error": "Invalid session"})
                    return
                if self.path != "/config":
                    self.reply(404, {})
                    return
                session.last_contact = time.monotonic()
                self.reply(200, {"ready": session.ready, "stop": session.stop_requested,
                                 "fps": session.settings.fps, "quality": session.settings.quality})

            def do_POST(self):
                if not self.allowed():
                    self.reply(403, {"error": "Invalid session"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "-1"))
                    parsed = urlsplit(self.path)
                    max_length = 8 * 1024 * 1024 if parsed.path == "/chunk" else 32 * 1024 * 1024
                    if not 0 <= length <= max_length:
                        self.reply(413, {"error": "Chunk too large"})
                        return
                    if parsed.path == "/chunk":
                        with session.write_lock:
                            body = self.rfile.read(length)
                            if len(body) != length:
                                raise ValueError("Incomplete upload")
                            try:
                                session.accept_chunk(parsed, body, self.headers)
                            except (ValueError, OSError) as exc:
                                self.reply(409, {"error": str(exc)})
                                return
                            session.last_contact = time.monotonic()
                        self.reply(200, {"ok": True})
                        return
                    with session.write_lock:
                        body = self.rfile.read(length)
                        if len(body) != length:
                            raise ValueError("Incomplete upload")
                    with session.lock:
                        if parsed.path == "/begin":
                            if not session.ready or session.started.is_set() or session.stop_requested or session.ended.is_set():
                                self.reply(409, {"error": "Session not ready or already recording"})
                                return
                            value = json.loads(body)
                            if not isinstance(value, dict):
                                raise ValueError("Expected a JSON object")
                            session.title = str(value.get("title", tr("error.tab_default_title")))[:250]
                            session.origin = time.monotonic()
                            session.started.set()
                        elif parsed.path == "/end":
                            if not session.started.is_set():
                                self.reply(409, {"error": "Not recording"})
                                return
                            if session.partial_sequence is not None:
                                self.reply(409, {"error": "Incomplete chunk"})
                                return
                            session.ended.set()
                        elif parsed.path == "/abort":
                            value = json.loads(body)
                            if not isinstance(value, dict):
                                raise ValueError("Expected a JSON object")
                            session.error = str(value.get("error", tr("error.tab_capture_stopped")))[:1000]
                            session.ended.set()
                        else:
                            self.reply(404, {})
                            return
                        session.last_contact = time.monotonic()
                    self.reply(200, {"ok": True})
                except (ValueError, OSError, TypeError) as exc:
                    self.reply(400, {"error": str(exc)})
        return Handler

    def accept_chunk(self, parsed, body, headers):
        with self.lock:
            if not self.started.is_set() or self.ended.is_set():
                raise ValueError("Not recording")
            sequence = int(parse_qs(parsed.query).get("seq", ["-1"])[0])
            if sequence < 0:
                raise ValueError("Invalid sequence")
            offset = int(parse_qs(parsed.query).get("part", ["0"])[0])
            if offset < 0:
                raise ValueError("Invalid chunk offset")
            if sequence == self.sequence:
                if self.partial_sequence not in (None, sequence) or offset != self.partial_offset:
                    raise ValueError("Out-of-order chunk part")
                total = int(headers.get("X-Chunk-Size", "-1"))
                if total <= 0 or not body or offset + len(body) > total:
                    raise ValueError("Invalid chunk size")
                if self.partial_total is not None and total != self.partial_total:
                    raise ValueError("Chunk size changed during upload")
                self.stream.write(body)
                self.partial_total = total
                self.partial_sequence = sequence
                self.partial_offset += len(body)
                if offset + len(body) == total:
                    self.sequence += 1
                    self.partial_sequence = None
                    self.partial_offset = 0
                    self.partial_total = None
            elif sequence != self.sequence - 1:
                raise ValueError("Out-of-order chunk")
            self.last_contact = time.monotonic()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        with self.lock:
            self.ended.set()
            self.stream.close()


class BrowserWorker(QThread):
    recording_started = Signal(str)
    recording_saved = Signal(str)
    failed = Signal(str)
    finalizing = Signal()
    pairing_ready = Signal(str)
    tab_selected = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.stop_event = threading.Event()
        self.encoder = None
        self.session = None

    def stop(self):
        self.stop_event.set()
        if self.session:
            self.session.stop_requested = True

    def run(self):
        log.info("Browser capture session starting")
        session, audio, parts = None, None, None
        raw = None
        parts_created = False
        error = None
        reservation = None
        tracks = []
        try:
            directory = Path(self.settings.output_dir)
            directory.mkdir(parents=True, exist_ok=True)
            output, reservation = reserve(directory, self.settings)
            stem = output.stem
            parts = directory / f".{stem}.parts"
            parts.mkdir()
            parts_created = True
            raw = parts / "tab.webm"
            from .overlay import load_image
            from screenrec.config.templates import validate
            overlay_template = validate(self.settings.overlay) if self.settings.overlay_enabled else {}
            overlay_image = None
            if overlay_template and overlay_template["image"]["enabled"]:
                overlay_image = load_image(overlay_template["image"]["path"])
            if self.settings.audio_mode != "none":
                audio = AudioSession(self.settings, parts)
                audio.prepare()
            session = self.session = TabSession(raw, self.settings)
            session.ready = True
            log.debug("Loopback bridge ready; awaiting browser")
            self.pairing_ready.emit(session.pairing_code)
            deadline = time.monotonic() + 300
            while not session.started.wait(0.05):
                if self.stop_event.is_set():
                    return
                if session.error:
                    raise RuntimeError(session.error)
                if time.monotonic() > deadline:
                    raise RuntimeError(tr("error.tab_connect_timeout"))
            if audio:
                audio.start(session.origin)
            log.info("Browser connected; tab capture active")
            self.tab_selected.emit(session.title)
            self.recording_started.emit(str(output))
            stop_deadline = None
            while not session.ended.wait(0.05):
                if audio:
                    audio.check()
                if self.stop_event.is_set():
                    session.stop_requested = True
                    stop_deadline = stop_deadline or time.monotonic() + 15
                    if time.monotonic() > stop_deadline:
                        raise RuntimeError(tr("error.tab_incomplete"))
                if time.monotonic() - session.last_contact > 20:
                    raise RuntimeError(tr("error.tab_disconnected"))
            duration = time.monotonic() - session.origin
            if session.error:
                raise RuntimeError(session.error)
            self.stop_event.set()
            self.finalizing.emit()
            if audio:
                tracks = audio.finish()
                audio = None
            session.close()
            session = self.session = None
            if raw.stat().st_size == 0:
                raise RuntimeError(tr("error.tab_no_video"))
            log.debug("Browser transfer complete; encoding received video")
            video = parts / f"video.{self.settings.file_format}" if tracks else output
            from .overlay import prepare, ffmpeg_options
            overlay_path = None
            if self.settings.overlay_enabled:
                from imageio_ffmpeg import read_frames
                reader = read_frames(str(raw))
                try:
                    size = next(reader)["size"]
                finally:
                    reader.close()
                overlay_path = prepare(overlay_template, *size, parts / "overlay.png", overlay_image)
            inputs, options = ffmpeg_options(video_options(self.settings.file_format, self.settings.quality, self.settings.fps), overlay_path)
            command = [get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-n", "-i", str(raw),
                       ] + inputs + ["-an", "-r", str(self.settings.fps)]
            command += options + [str(video)]
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                    timeout=max(120, duration * 10), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors="replace"))
            if tracks:
                # Let video EOF define the final duration, with audio aligned to the browser handshake.
                from imageio_ffmpeg import count_frames_and_secs
                _, video_duration = count_frames_and_secs(str(video))
                mux_audio(video, tracks, output, self.settings, video_duration)
            try:
                for path in [raw, *(track[0] for track in tracks), *([video] if tracks else [])]:
                    path.unlink()
                if overlay_path:
                    overlay_path.unlink()
                parts.rmdir()
            except OSError:
                log.exception("Browser recording saved, but temporary parts could not be removed: %s", parts)
            self.recording_saved.emit(str(output))
        except Exception as exc:
            log.exception("Browser capture failed")
            error = str(exc)
        finally:
            self.stop_event.set()
            if session:
                try:
                    session.close()
                except Exception as exc:
                    log.exception("Could not close browser capture session")
                    error = f"{error}\n{exc}" if error else str(exc)
                self.session = None
            if audio:
                try:
                    audio.finish(check=False)
                except Exception:
                    pass
            # A cancelled pairing has no recording to recover. Keep any
            # nonempty browser stream after errors for manual recovery.
            try:
                if parts_created and parts.exists() and (raw is None or not raw.exists() or raw.stat().st_size == 0):
                    for item in parts.iterdir():
                        if item.is_file():
                            item.unlink()
                    parts.rmdir()
            except OSError:
                log.exception("Could not clean cancelled browser session: %s", parts)
            if reservation:
                try:
                    reservation.rmdir()
                except OSError:
                    pass
            if error:
                self.failed.emit(error + "\n" + tr("error.parts_kept", path=parts) if parts and parts.exists() else error)
