import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtWidgets import QApplication
from screenrec.logger.logger import configure,shutdown,hub,get_logger,LEVELS,get_default_log_path
from screenrec.config.settings import Settings
from screenrec.ui.logging_dialog import LoggingDialog

class LoggingTests(TestCase):
    def tearDown(self):
        configure(False)
    def test_all_levels_can_be_enabled_at_startup(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "startup.log"
            configure(True, str(path), list(LEVELS))
            log = get_logger("startup")
            for name, number in LEVELS.items():
                log.logger.log(number, "startup-" + name)
            text = path.read_text(encoding="utf-8")
            for name in LEVELS:
                self.assertIn("startup-" + name, text)
            shutdown()

    def test_disabled_and_exact_level_filter(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"test.log"
            log=get_logger("test")
            configure(False,str(path),list(LEVELS))
            log.fatal_error("not-written")
            self.assertFalse(path.exists())
            configure(True,str(path),["DEBUG","ERROR"])
            for name,number in LEVELS.items():
                log.logger.log(number,"event-"+name)
            text=path.read_text(encoding="utf-8")
            self.assertIn("event-DEBUG",text)
            self.assertIn("event-ERROR",text)
            for name in ("TRACE","INFO","WARNING","CRITICAL","FATAL"):
                self.assertNotIn("event-"+name,text)
            configure(True,str(path),["TRACE","FATAL"])
            log.trace("trace-on")
            log.fatal_error("fatal-on")
            configure(False)
            previous=path.read_bytes()
            log.error("disabled")
            self.assertEqual(path.read_bytes(),previous)
            self.assertIn(b"fatal-on",previous)
            self.assertIn(b"trace-on",previous)
    def test_shutdown_flushes_final_event(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "final.log"
            configure(True, str(path), ["INFO"])
            get_logger("shutdown").info("final shutdown event")
            shutdown()
            self.assertIsNone(hub.file)
            self.assertIn("final shutdown event", path.read_text(encoding="utf-8"))

    def test_rotation_threads_and_runtime_write_failure(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/"test.log"
            configure(True,str(path),["INFO"])
            hub.file.maxBytes=512
            log=get_logger("test")
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda n:log.info("event %s %s",n,"x"*60),range(100)))
            self.assertTrue(Path(str(path)+".1").exists())
            self.assertFalse(Path(str(path)+".4").exists())
            with patch.object(hub.file,"emit",side_effect=OSError("disk full")):
                log.info("failure")
            self.assertIsNone(hub.file)
            self.assertIn("отключена",hub.take_problem())
            self.assertIsNone(hub.take_problem())
    def test_fallback_default_location_and_dialog(self):
        with TemporaryDirectory() as directory:
            default=Path(directory)/"fallback.log"
            with patch("screenrec.logger.logger.get_default_log_path",return_value=default):
                actual,warning=configure(True,str(Path(directory)/"missing"/"test.log"),["WARNING"])
                self.assertEqual(actual,default)
                self.assertIsNotNone(warning)
                shutdown()
                with patch("screenrec.logger.logger.get_default_log_path",return_value=Path(directory)):
                    actual,warning=configure(True,str(Path(directory)/"missing"/"test.log"))
                    self.assertIsNone(actual)
                    self.assertIsNotNone(warning)
            with patch("sys.frozen",True,create=True),patch("sys.executable",str(Path(directory)/"ScreenRec.exe")):
                self.assertEqual(get_default_log_path(),Path(directory)/"screenrec.log")
        app=QApplication.instance() or QApplication([])
        settings=Settings()
        dialog=LoggingDialog(settings)
        self.assertFalse(dialog.enabled.isChecked())
        dialog.enabled.setChecked(True)
        for key,box in dialog.levels.items():
            box.setChecked(key=="TRACE")
        self.assertEqual(dialog.result_settings().log_levels,["TRACE"])
        dialog.reject()
        self.assertFalse(settings.logging_enabled)
        dialog.deleteLater()
