import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from screenrec.config.settings import Settings
from screenrec.localization import Translator
from screenrec.config.commands import COMMANDS, commands_for
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

    def test_help_contains_localized_sections(self):
        english = Translator("en").tr("help.description")
        russian = Translator("ru").tr("help.description")
        for section in ("RECORDING", "SOURCES", "AUDIO", "FORMATS", "OVERLAYS", "CATALOGUE", "TROUBLESHOOTING"):
            self.assertIn(section, english)
        for section in ("ЗАПИСЬ", "ИСТОЧНИКИ", "ЗВУК", "ФОРМАТЫ", "НАЛОЖЕНИЯ", "КАТАЛОГ", "УСТРАНЕНИЕ ПРОБЛЕМ"):
            self.assertIn(section, russian)

    def test_all_command_labels_are_localized(self):
        for language in ("en", "ru"):
            translator = Translator(language)
            for command in COMMANDS.values():
                self.assertNotEqual(translator.tr(command.label_key), command.label_key)
    def test_translation_falls_back_for_unknown_language_and_key(self):
        translator = Translator("de")
        self.assertEqual(translator.language, "en")
        self.assertEqual(translator.tr("missing.key"), "missing.key")
        self.assertEqual(translator.tr("missing.key", fallback="Fallback"), "Fallback")


if __name__ == "__main__":
    unittest.main()