import ctypes
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from screenrec.qt.QtWidgets import QApplication, QMessageBox
from screenrec.app import ScreenRecApp
from screenrec.config.settings import Settings
from screenrec.config.profiles import save_profile, load_profile
from screenrec.main import acquire_instance_lock
from screenrec.recorder.encoder import Encoder
from screenrec.recorder.worker import RecordingWorker
from screenrec.ui.recordings_view import FrameGrabber


class ReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def test_windows_capture_cursor_option_is_gated_by_api_version(self):
        from types import SimpleNamespace
        from screenrec.recorder.windows_capture_compat import cursor_capture_option
        from screenrec.recorder import windows_capture_compat
        with patch.object(windows_capture_compat.sys, "getwindowsversion",
                          create=True, return_value=SimpleNamespace(build=18363)):
            self.assertIsNone(cursor_capture_option(True))
            self.assertIsNone(cursor_capture_option(False))
        with patch.object(windows_capture_compat.sys, "getwindowsversion",
                          create=True, return_value=SimpleNamespace(build=19041)):
            self.assertIs(cursor_capture_option(True), True)
            self.assertIs(cursor_capture_option(False), False)
        with patch.object(windows_capture_compat.sys, "getwindowsversion",
                          create=True, side_effect=OSError("version unavailable")):
            self.assertIsNone(cursor_capture_option(True))

    def test_mux_failure_keeps_recoverable_video_and_audio(self):
        class Source:
            def __init__(self, _): pass
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def grab(self): return bytes([20, 80, 140, 255]) * 64 * 48

        class Audio:
            origin = None
            def __init__(self, settings, directory):
                self.path = directory / "microphone.wav"
            def prepare(self): self.path.write_bytes(b"recoverable audio")
            def start(self, origin): self.origin = origin
            def finish(self, check=True): return [(self.path, 0)]

        with tempfile.TemporaryDirectory() as folder, \
             patch("screenrec.recorder.worker.ScreenSource", Source), \
             patch("screenrec.recorder.worker.AudioSession", Audio), \
             patch("screenrec.recorder.worker.mux_audio", side_effect=OSError("disk full")):
            worker = RecordingWorker({"width": 64, "height": 48}, folder, 15,
                                     settings=Settings(audio_mode="microphone"))
            errors, saved = [], []
            worker.recording_started.connect(lambda _: worker.stop())
            worker.failed.connect(errors.append)
            worker.recording_saved.connect(saved.append)
            worker.run()
            self.assertIn("disk full", errors[0])
            self.assertEqual(saved, [])
            parts = next(Path(folder).glob(".*.parts"))
            self.assertEqual((parts / "microphone.wav").read_bytes(), b"recoverable audio")
            from imageio_ffmpeg import count_frames_and_secs
            self.assertEqual(count_frames_and_secs(str(parts / "video.mp4"))[0], 1)
            self.assertFalse(list(Path(folder).glob("*.recording")))

    def test_stalled_encoder_is_killed_and_writer_unblocked(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                 stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        with tempfile.TemporaryDirectory() as folder:
            try:
                with patch("screenrec.recorder.encoder.subprocess.Popen", return_value=child), \
                     patch.object(Encoder, "WRITE_TIMEOUT", 0.1):
                    encoder = Encoder(Path(folder) / "video.mp4", 1024, 1024, 30)
                    failures = []
                    def write():
                        try:
                            encoder.write(bytes(1024 * 1024 * 4))
                        except OSError as exc:
                            failures.append(exc)
                    writer = threading.Thread(target=write, daemon=True)
                    writer.start()
                    writer.join(4)
                    self.assertFalse(writer.is_alive())
                    self.assertTrue(failures)
                    with self.assertRaises(RuntimeError):
                        encoder.finish()
                    self.assertFalse(encoder._watchdog.is_alive())
                    self.assertIsNotNone(child.poll())
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=5)
                child.stdin.close()

    def test_encoder_cleanup_still_closes_resources_if_wait_raises(self):
        class StuckProcess:
            def __init__(self):
                self.pid = 12345
                self.stdin = type("Pipe", (), {"closed": False, "close": lambda pipe: setattr(pipe, "closed", True)})()
                self.killed = False
            def poll(self): return None if not self.killed else -9
            def kill(self): self.killed = True
            def wait(self, timeout=None):
                if timeout is None:
                    raise AssertionError("Unbounded process wait")
                raise OSError("wait unavailable")

        with tempfile.TemporaryDirectory() as folder, \
             patch("screenrec.recorder.encoder.subprocess.Popen", return_value=StuckProcess()), patch("screenrec.recorder.encoder.get_ffmpeg_exe", return_value="ffmpeg"):
            encoder = Encoder(Path(folder) / "video.mp4", 64, 48, 15)
            diagnostics = encoder.errors
            with self.assertRaises(RuntimeError):
                encoder.finish()
            self.assertTrue(encoder.process.stdin.closed)
            self.assertTrue(diagnostics.closed)
            self.assertFalse(encoder._watchdog.is_alive())
    def test_encoder_rejects_bad_frame_without_corrupting_stream(self):
        with tempfile.TemporaryDirectory() as folder:
            encoder = Encoder(Path(folder) / "video.mp4", 64, 48, 15)
            try:
                with self.assertRaises(ValueError):
                    encoder.write(b"short frame")
                encoder.write(bytes(64 * 48 * 4))
            finally:
                encoder.finish()

    def test_profile_uses_same_validation_as_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profile.json"
            settings = Settings(log_levels=[{}, "ERROR", "ERROR", "invalid"],
                                filename_prefix="CON", filename_date_format="invalid",
                                overlay={"text": {"size": 10 ** 400, "enabled": "wrong"}})
            save_profile(path, settings)
            loaded = load_profile(path, fallback=False)
            self.assertEqual(loaded.log_levels, ["ERROR"])
            self.assertEqual(loaded.filename_prefix, "_CON")
            self.assertEqual(loaded.filename_date_format, "ymd")
            self.assertFalse(loaded.overlay["text"]["enabled"])
            self.assertEqual(loaded.overlay["text"]["size"], 1)

    def test_concurrent_settings_saves_use_independent_temporary_files(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(Settings, "path", return_value=Path(folder) / "settings.json"):
            def save(number):
                Settings(filename_prefix=str(number)).save()
            with ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(save, range(20)))
            document = json.loads(Settings.path().read_text(encoding="utf-8"))
            self.assertIn(document["filename_prefix"], [str(n) for n in range(20)])
            self.assertEqual(list(Path(folder).glob("*.tmp")), [])

    def test_non_windows_instance_lock_on_first_launch(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch("screenrec.main.platform.system", return_value="Linux"), \
             patch.object(Settings, "path", return_value=Path(folder) / "new" / "settings.json"):
            lock = acquire_instance_lock()
            self.assertTrue(lock)
            try:
                self.assertFalse(acquire_instance_lock())
            finally:
                lock.unlock()

    def test_failed_settings_replace_preserves_previous_document(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(Settings, "path", return_value=Path(folder) / "settings.json"):
            Settings(filename_prefix="original").save()
            with patch("screenrec.config.atomic.os.replace", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    Settings(filename_prefix="replacement").save()
            self.assertEqual(Settings.load().filename_prefix, "original")
            self.assertEqual(list(Path(folder).glob("*.tmp")), [])

    def test_screen_capture_passes_owned_buffer_without_copy(self):
        from screenrec.recorder.screen import ScreenSource
        class Shot:
            raw = bytearray(64 * 48 * 4)
            @property
            def bgra(self):
                raise AssertionError("Full-frame copying property was used")
        source = ScreenSource({"left": 0, "top": 0, "width": 64, "height": 48})
        with patch("screenrec.recorder.screen.mss.mss") as capture:
            capture.return_value.grab.return_value = Shot()
            with source:
                self.assertIs(source.grab(), Shot.raw)

    def test_stalled_windows_capture_recovers_through_mss(self):
        from screenrec.recorder.screen import ScreenSource
        class Shot:
            raw = bytearray(4 * 3 * 4)
        class Control:
            stopped = False
            def stop(self): self.stopped = True
        source = ScreenSource({"left": 0, "top": 0, "width": 4, "height": 3})
        control = Control()
        source.capture_control = control
        source.frame = bytearray(4 * 3 * 4)
        source.last_frame_time = time.monotonic() - 3
        source.region = {"left": 0, "top": 0, "width": 4, "height": 3}
        with patch("screenrec.recorder.screen.mss.mss") as capture:
            capture.return_value.grab.return_value = Shot()
            self.assertIs(source.grab(), Shot.raw)
        self.assertTrue(control.stopped)
        self.assertIsNone(source.capture_control)

    @unittest.skipUnless(sys.platform == "win32", "Windows capture backend")
    def test_modern_region_uses_mss_directly_without_starting_wgc(self):
        from screenrec.recorder.screen import ScreenSource
        class Shot:
            raw = bytearray(4 * 3 * 4)
        class Capture:
            def __init__(self): self.calls = []
            def grab(self, region):
                self.calls.append(region)
                return Shot()
            def close(self): self.closed = True
        capture = Capture()
        with patch.dict(os.environ, {"SCREENREC_QT": "PySide6"}), \
             patch("screenrec.recorder.screen.platform.system", return_value="Windows"), \
             patch("screenrec.recorder.screen.mss.MSS", return_value=capture), \
             patch("windows_capture.WindowsCapture") as wgc:
            source = ScreenSource({"kind": "region", "left": 10, "top": 20, "width": 4, "height": 3})
            source.__enter__()
            self.assertIs(source.grab(), Shot.raw)
            self.assertEqual(capture.calls, [source.region])
            wgc.assert_not_called()
            source.__exit__()

    @unittest.skipUnless(sys.platform == "win32", "Windows capture backend")
    def test_modern_region_failure_is_reported_without_starting_wgc(self):
        from screenrec.recorder.screen import ScreenSource
        with patch.dict(os.environ, {"SCREENREC_QT": "PySide6"}), \
             patch("screenrec.recorder.screen.platform.system", return_value="Windows"), \
             patch("screenrec.recorder.screen.mss.MSS", side_effect=OSError("access denied")), \
             patch("windows_capture.WindowsCapture") as wgc:
            with self.assertRaisesRegex(RuntimeError, "access denied"):
                ScreenSource({"kind": "region", "left": 0, "top": 0, "width": 4, "height": 3}).__enter__()
            wgc.assert_not_called()

    def test_windows_capture_rejects_bad_frame_and_enters_fallback(self):
        import numpy as np
        from screenrec.recorder.screen import ScreenSource
        display = {"left": 0, "top": 0, "width": 4, "height": 3}
        class DisplayList:
            monitors = [display, display]
            def __enter__(self): return self
            def __exit__(self, *_): pass
        class Frame:
            frame_buffer = np.zeros((2, 2, 3), dtype=np.uint8)
            width, height = 2, 2
        class Control:
            def stop(self): pass
        class Capture:
            def event(self, handler):
                setattr(self, handler.__name__, handler)
                return handler
            def start_free_threaded(self):
                self.on_frame_arrived(Frame(), None)
                return Control()
        class Shot:
            raw = bytearray(4 * 3 * 4)
        with patch.dict(os.environ, {"SCREENREC_QT": "PySide6"}), \
             patch("screenrec.recorder.screen.platform.system", return_value="Windows"), \
             patch("screenrec.recorder.screen.mss.mss", side_effect=[DisplayList(), type("MSS", (), {"grab": lambda _, region: Shot(), "close": lambda _: None})()]), \
             patch("windows_capture.WindowsCapture", return_value=Capture()):
            source = ScreenSource(display)
            source.__enter__()
            self.assertIs(source.grab(), Shot.raw)
            source.__exit__()

    @unittest.skipUnless(sys.platform == "win32", "Windows capture backend")
    def test_modern_screen_capture_uses_wgc_and_crops_selected_region(self):
        import numpy as np
        from screenrec.recorder.screen import ScreenSource
        pixels = np.arange(4 * 6 * 4, dtype=np.uint8).reshape(4, 6, 4)
        display = {"left": 100, "top": 200, "width": 6, "height": 4}
        virtual = {"left": 0, "top": 0, "width": 106, "height": 204}
        class DisplayList:
            monitors = [virtual, display]
            def __enter__(self): return self
            def __exit__(self, *_): pass
        class Frame:
            frame_buffer = pixels
            width, height = 6, 4
        class Control:
            stopped = False
            def stop(self): self.stopped = True
        class Capture:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
            def event(self, handler):
                setattr(self, handler.__name__, handler)
                return handler
            def start_free_threaded(self):
                self.on_frame_arrived(Frame(), None)
                return control
        control = Control()
        with patch.dict(os.environ, {"SCREENREC_QT": "PySide6"}), \
             patch("screenrec.recorder.screen.platform.system", return_value="Windows"), \
             patch("screenrec.recorder.screen.mss.mss", return_value=DisplayList()), \
             patch("windows_capture.WindowsCapture", side_effect=lambda **kwargs: capture_factory(kwargs)):
            created = []
            def capture_factory(kwargs):
                capture = Capture(**kwargs)
                created.append(capture)
                return capture
            source = ScreenSource({"kind": "monitor", "left": 102, "top": 201, "width": 2, "height": 2})
            source.__enter__()
            from screenrec.recorder.windows_capture_compat import cursor_capture_option
            self.assertEqual(created[0].kwargs,
                             {"monitor_index": 1, "cursor_capture": cursor_capture_option(True)})
            self.assertEqual(source.grab(), pixels[1:3, 2:4].copy().tobytes())
            source.__exit__()
            self.assertTrue(control.stopped)

    @unittest.skipUnless(sys.platform == "win32", "Windows capture backend")
    def test_modern_screen_capture_falls_back_to_mss_when_wgc_fails(self):
        from screenrec.recorder.screen import ScreenSource
        class Shot:
            raw = bytearray(4 * 3 * 4)
        class Capture:
            monitors = [{"left": 0, "top": 0, "width": 4, "height": 3},
                        {"left": 0, "top": 0, "width": 4, "height": 3}]
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def grab(self, region):
                self.region = region
                return Shot()
        capture = Capture()
        with patch.dict(os.environ, {"SCREENREC_QT": "PySide6"}), \
             patch("screenrec.recorder.screen.platform.system", return_value="Windows"), \
             patch("screenrec.recorder.screen.mss.mss", return_value=capture), \
             patch("windows_capture.WindowsCapture", side_effect=RuntimeError("WGC unavailable")):
            source = ScreenSource({"kind": "monitor", "left": 0, "top": 0, "width": 4, "height": 3})
            source.__enter__()
            self.assertIs(source.grab(), Shot.raw)
            self.assertEqual(capture.region, source.region)
            source.__exit__()

    @unittest.skipUnless(sys.platform == "win32", "Windows capture backend")
    def test_modern_window_capture_falls_back_when_wgc_rejects_hwnd(self):
        from ctypes import wintypes as wt
        from screenrec.recorder.window_windows import WindowSource, user32
        rectangle = {"left": 100, "top": 120, "right": 164, "bottom": 168}
        class Shot:
            raw = bytearray(64 * 48 * 4)
        def get_rect(hwnd, pointer):
            rect = ctypes.cast(pointer, ctypes.POINTER(wt.RECT)).contents
            rect.left, rect.top = rectangle["left"], rectangle["top"]
            rect.right, rect.bottom = rectangle["right"], rectangle["bottom"]
            return True
        def get_pid(hwnd, pointer):
            ctypes.cast(pointer, ctypes.POINTER(wt.DWORD)).contents.value = os.getpid()
            return 1
        with patch.dict(os.environ, {"SCREENREC_QT": "PySide6"}), \
             patch("windows_capture.WindowsCapture", side_effect=RuntimeError("GraphicsCaptureItem conversion failed")), \
             patch("screenrec.recorder.window_windows.user32.IsWindow", return_value=True), \
             patch("screenrec.recorder.window_windows.user32.IsIconic", return_value=False), \
             patch("screenrec.recorder.window_windows.user32.GetWindowThreadProcessId", side_effect=get_pid), \
             patch("screenrec.recorder.window_windows.user32.GetWindowRect", side_effect=get_rect), \
             patch.object(WindowSource, "_open_printwindow", side_effect=lambda: None), \
             patch("screenrec.recorder.window_windows.user32.PrintWindow", return_value=True), \
             patch("screenrec.recorder.window_windows.ctypes.string_at", return_value=Shot.raw):
            source = WindowSource({"hwnd": 123, "pid": os.getpid()})
            source._memory_dc = 1
            source._pixels = 1
            source.__enter__()
            self.assertTrue(source.fallback_capture)
            self.assertEqual((source.width, source.height), (64, 48))
            self.assertIs(source.grab(), Shot.raw)
            rectangle["right"] = 165
            with self.assertRaises(RuntimeError):
                source.grab()
            source.__exit__()
    @unittest.skipUnless(sys.platform == "win32", "Windows capture backend")
    def test_legacy_minimized_window_fails_before_desktop_grab(self):
        from screenrec.recorder.window_windows import WindowSource
        source = WindowSource({"hwnd": 1, "pid": 1})
        with patch.dict(os.environ, {"SCREENREC_QT": "PySide2"}), \
             patch.object(source, "validate"), \
             patch("screenrec.recorder.window_windows.user32.IsIconic", return_value=True):
            with self.assertRaises(RuntimeError):
                source.__enter__()
            self.assertFalse(hasattr(source, "legacy_grab"))

    @unittest.skipUnless(sys.platform == "win32", "Windows capture backend")
    def test_legacy_window_uses_printwindow_without_desktop_grab(self):
        from ctypes import wintypes as wt
        from screenrec.recorder.window_windows import WindowSource
        rectangle = {"left": 100, "top": 120, "right": 164, "bottom": 168}
        frame = bytes(64 * 48 * 4)
        def get_rect(hwnd, pointer):
            rect = ctypes.cast(pointer, ctypes.POINTER(wt.RECT)).contents
            rect.left, rect.top = rectangle["left"], rectangle["top"]
            rect.right, rect.bottom = rectangle["right"], rectangle["bottom"]
            return True
        def get_pid(hwnd, pointer):
            ctypes.cast(pointer, ctypes.POINTER(wt.DWORD)).contents.value = os.getpid()
            return 1
        with patch.dict(os.environ, {"SCREENREC_QT": "PySide2"}), \
             patch("screenrec.recorder.window_windows.user32.IsWindow", return_value=True), \
             patch("screenrec.recorder.window_windows.user32.IsIconic", return_value=False), \
             patch("screenrec.recorder.window_windows.user32.GetWindowThreadProcessId", side_effect=get_pid), \
             patch("screenrec.recorder.window_windows.user32.GetWindowRect", side_effect=get_rect), \
             patch.object(WindowSource, "_open_printwindow"), \
             patch("screenrec.recorder.window_windows.user32.PrintWindow", return_value=True), \
             patch("screenrec.recorder.window_windows.ctypes.string_at", return_value=frame):
            source = WindowSource({"hwnd": 123, "pid": os.getpid()})
            source._memory_dc = 1
            source._pixels = 1
            source.__enter__()
            self.assertTrue(source.printwindow_capture)
            self.assertEqual(source.grab(), frame)
            source.__exit__()

    def test_import_updates_directory_source_and_respects_logging_choice(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch("screenrec.app.load_default_profile", return_value=None), \
             patch("screenrec.app.Settings.load", return_value=Settings(output_dir=folder, logging_enabled=False)), \
             patch.object(Settings, "path", return_value=Path(folder) / "settings.json"), \
             patch("screenrec.app.monitors", return_value=[{"left": 0, "top": 0, "width": 64, "height": 48}]):
            controller = ScreenRecApp(self.qt)
            try:
                from screenrec.logger.logger import hub
                self.assertIsNone(hub.file)
                path = Path(folder) / "profile.json"
                target = Path(folder) / "recordings"
                save_profile(path, Settings(output_dir=str(target), source_mode="region",
                                           region={"left": 1, "top": 2, "width": 32, "height": 24},
                                           logging_enabled=False))
                with patch("screenrec.app.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
                     patch("screenrec.app.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), \
                     patch("screenrec.app.QMessageBox.information"):
                    controller.import_profile()
                self.assertEqual(controller.window.folder.text(), str(target))
                self.assertEqual(controller.window.recordings.directory, target)
                self.assertEqual(controller.current_source()["kind"], "region")
                self.assertEqual(controller.current_source()["width"], 32)
                controller.set_busy(True)
                self.assertFalse(controller.import_profile_action.isEnabled())
            finally:
                controller.cleanup()
                controller.timer.stop()
                controller.window.deleteLater()
                controller.deleteLater()
                self.qt.processEvents()

    def test_preview_skips_obsolete_queued_requests(self):
        gate, entered = threading.Event(), threading.Event()
        calls = []
        def grab(path):
            calls.append(path)
            entered.set()
            gate.wait(3)
            return None
        grabber = FrameGrabber()
        with patch("screenrec.ui.recordings_view.grab_frame", side_effect=grab):
            try:
                grabber.request("first")
                self.assertTrue(entered.wait(1))
                for i in range(20):
                    grabber.request(str(i))
                gate.set()
                grabber._future.result(timeout=3)
                self.assertEqual(calls, ["first", "19"])
            finally:
                gate.set()
                grabber.shutdown()
                grabber._executor.shutdown(wait=True)
