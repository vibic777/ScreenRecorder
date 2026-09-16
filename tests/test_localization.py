import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from screenrec.config.settings import Settings
from screenrec.localization import Translator
from screenrec.ui.main_window import MainWindow


class LocalizationStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self, language):
        settings = Settings()
        settings.language = language
        window = MainWindow(settings, QIcon())
        self.addCleanup(window.close)
        return window

    def test_english_startup(self):
        window = self.make_window("en")
        self.assertEqual(window.windowTitle(), "ScreenRec — Screen Recorder")
        self.assertEqual(window.tabs.tabText(0), "Recording")
        self.assertEqual(window.tabs.tabText(1), "Recordings")
        self.assertEqual(window.start.text(), "Start recording")
        self.assertEqual(window.source_mode.itemText(0), "Monitor")

    def test_russian_startup(self):
        window = self.make_window("ru")
        self.assertEqual(window.windowTitle(), "ScreenRec — Запись экрана")
        self.assertEqual(window.tabs.tabText(0), "Запись")
        self.assertEqual(window.tabs.tabText(1), "Записи")
        self.assertEqual(window.start.text(), "Начать запись")
        self.assertEqual(window.source_mode.itemText(0), "Монитор")

    def test_translation_falls_back_for_unknown_language_and_key(self):
        translator = Translator("de")
        self.assertEqual(translator.language, "en")
        self.assertEqual(translator.tr("missing.key"), "missing.key")
        self.assertEqual(translator.tr("missing.key", fallback="Fallback"), "Fallback")


if __name__ == "__main__":
    unittest.main()