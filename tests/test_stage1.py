import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from imageio_ffmpeg import count_frames_and_secs, get_ffmpeg_exe
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QLockFile

from screenrec.app import ScreenRecApp
from screenrec.config.settings import Settings
from screenrec.recorder.encoder import Encoder
from screenrec.recorder.worker import RecordingWorker


MONITOR = {"left": 0, "top": 0, "width": 65, "height": 49}


class SyntheticSource:
    def __init__(self, monitor):
        self.frame = bytes([32, 96, 160, 255]) * monitor["width"] * monitor["height"]

    def __enter__(self):
        return self

    def grab(self):
        return self.frame

    def __exit__(self, *_):
        pass


class StageOneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def pump_until(self, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.qt.processEvents()
            time.sleep(0.01)
        self.qt.processEvents()
        self.assertTrue(predicate(), "Timed out waiting for recording lifecycle")

    def assert_video(self, path):
        count, seconds = count_frames_and_secs(str(path))
        self.assertGreater(count, 0)
        self.assertGreater(seconds, 0)
        result = subprocess.run([get_ffmpeg_exe(), "-v", "error", "-i", str(path),
                                 "-f", "null", "-"], capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stderr, b"")

    def test_encoder_odd_dimensions_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "video.mp4"
            encoder = Encoder(path, 65, 49, 15)
            for _ in range(15):
                encoder.write(bytes([10, 50, 90, 255]) * 65 * 49)
            encoder.finish()
            self.assert_video(path)
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                Encoder(path, 65, 49, 15)
            self.assertEqual(original, path.read_bytes())

    def test_worker_capture_error_releases_encoder(self):
        class FailingSource(SyntheticSource):
            calls = 0

            def grab(self):
                self.calls += 1
                if self.calls > 1:
                    raise RuntimeError("Monitor disconnected")
                return super().grab()

        with tempfile.TemporaryDirectory() as folder, patch("screenrec.recorder.worker.ScreenSource", FailingSource):
            worker = RecordingWorker(MONITOR, folder, 15)
            errors = []
            worker.failed.connect(errors.append)
            worker.start()
            self.pump_until(lambda: not worker.isRunning())
            self.assertIn("Monitor disconnected", errors[0])
            self.assertIsNone(worker.encoder)
            self.assert_video(next(Path(folder).glob("*.mp4")))

    def test_tray_stop_restart_and_exit(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch("screenrec.app.Settings.load", return_value=Settings(output_dir=folder, notifications=False, close_to_tray=True)), \
             patch("screenrec.app.monitors", return_value=[MONITOR]), \
             patch("screenrec.recorder.worker.ScreenSource", SyntheticSource), \
             patch("screenrec.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=True):
            controller = ScreenRecApp(self.qt)
            try:
                controller.window.show()
                controller.start_action.trigger()
                self.pump_until(lambda: controller.started_at is not None)
                controller.window.close()
                self.assertFalse(controller.window.isVisible())
                self.assertTrue(controller.worker.isRunning())
                controller.show_action.trigger()
                self.assertTrue(controller.window.isVisible())
                controller.stop_action.trigger()
                self.pump_until(lambda: controller.worker is None)
                self.assertTrue(controller.start_action.isEnabled())
                controller.start_action.trigger()
                self.pump_until(lambda: controller.started_at is not None)
                with patch("screenrec.app.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
                    controller.request_exit()
                self.assertFalse(controller.exiting)
                self.assertTrue(controller.worker.isRunning())
                with patch("screenrec.app.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
                    controller.request_exit()
                self.pump_until(lambda: controller.worker is None)
                self.assertTrue(controller.exiting)
                videos = list(Path(folder).glob("*.mp4"))
                self.assertEqual(len(videos), 2)
                for video in videos:
                    self.assert_video(video)
            finally:
                controller.cleanup()
                controller.timer.stop()
                controller.window.hide()
                controller.window.deleteLater()
                controller.deleteLater()
                self.qt.processEvents()

    def test_exit_paths_dispatch_application_exit(self):
        with patch("screenrec.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False), patch("screenrec.app.Settings.load", return_value=Settings()):
            controller = ScreenRecApp(self.qt)
            try:
                with patch.object(controller.application, "exit") as exit_mock:
                    controller.close_window()
                    exit_mock.assert_called_once_with(0)
                    controller.exiting = False
                    exit_mock.reset_mock()
                    controller.exit_action.trigger()
                    exit_mock.assert_called_once_with(0)
            finally:
                controller.cleanup()
                controller.timer.stop()
                controller.window.deleteLater()
                controller.deleteLater()
                self.qt.processEvents()

    def test_missing_tray_exits_instead_of_hiding(self):
        with patch("screenrec.app.monitors", return_value=[MONITOR]), \
             patch("screenrec.app.Settings.load", return_value=Settings()), \
             patch("screenrec.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            controller = ScreenRecApp(self.qt)
            controller.close_window()
            self.assertTrue(controller.exiting)
            controller.cleanup()
            controller.timer.stop()
            controller.window.deleteLater()
            controller.deleteLater()
            self.qt.processEvents()

    def test_single_instance_lock_allows_only_one_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "instance.lock")
            first = QLockFile(path)
            second = QLockFile(path)
            self.assertTrue(first.tryLock(100))
            try:
                self.assertFalse(second.tryLock(100))
            finally:
                first.unlock()
                second.unlock()

    def test_settings_roundtrip_and_malformed_file(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(Settings, "path", return_value=Path(folder) / "settings.json"):
            settings = Settings(output_dir=folder, fps=60, close_to_tray=False)
            settings.save()
            self.assertEqual(Settings.load(), settings)
            Settings.path().write_text("[]", encoding="utf-8")
            self.assertEqual(Settings.load(), Settings())


if __name__ == "__main__":
    unittest.main()
