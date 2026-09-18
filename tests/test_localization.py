import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from screenrec.config.settings import Settings
from screenrec.localization import Translator
from screenrec.config.commands import COMMANDS, commands_for
from screenrec.ui.main_window import MainWindow
from screenrec.version import __version__


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
        self.assertEqual(window.windowTitle(), f"ScreenRec — Screen Recorder v{__version__}")
        self.assertEqual(window.tabs.tabText(0), "Recording")
        self.assertEqual(window.tabs.tabText(1), "Recordings")
        self.assertEqual(window.start.text(), "Start recording")
        self.assertEqual(window.source_mode.itemText(0), "Monitor")

    def test_russian_startup(self):
        window = self.make_window("ru")
        self.assertEqual(window.windowTitle(), f"ScreenRec — Запись экрана v{__version__}")
        self.assertEqual(window.tabs.tabText(0), "Запись")
        self.assertEqual(window.tabs.tabText(1), "Записи")
        self.assertEqual(window.start.text(), "Начать запись")
        self.assertEqual(window.source_mode.itemText(0), "Монитор")

    def test_recording_settings_note_has_real_line_break(self):
        from screenrec.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(Settings())
        self.addCleanup(dialog.close)
        note = dialog.layout().itemAt(dialog.layout().count() - 2).widget()
        self.assertIn("\n", note.text())
        self.assertNotIn("\\n", note.text())

    def test_help_text_has_normalizable_line_breaks(self):
        for language in ("en", "ru"):
            text = Translator(language).tr("help.description")
            normalized = text.replace("/n", "\n").replace("\\n", "\n")
            self.assertGreater(normalized.count("\n"), 10)
            self.assertNotIn("/n", normalized)

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
    def test_menu_translations_are_complete(self):
        russian = Translator("ru")
        self.assertEqual(russian.tr("menu.file"), "Файл")
        self.assertEqual(russian.tr("menu.settings"), "Настройки")
        self.assertEqual(russian.tr("menu.help"), "Справка")
        self.assertEqual(russian.tr("menu.language"), "Язык")
        self.assertEqual(russian.tr("language.en"), "Английский")
        self.assertEqual(russian.tr("language.ru"), "Русский")
        english = Translator("en")
        self.assertEqual(english.tr("menu.file"), "File")
        self.assertEqual(english.tr("menu.settings"), "Settings")
        self.assertEqual(english.tr("menu.help"), "Help")
        self.assertEqual(english.tr("menu.language"), "Language")

    def test_translation_falls_back_for_unknown_language_and_key(self):
        translator = Translator("de")
        self.assertEqual(translator.language, "en")
        self.assertEqual(translator.tr("missing.key"), "missing.key")
        self.assertEqual(translator.tr("missing.key", fallback="Fallback"), "Fallback")


if __name__ == "__main__":
    unittest.main()
