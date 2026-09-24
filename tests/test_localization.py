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


def re_cyrillic(text):
    return any("Ѐ" <= char <= "ӿ" for char in text)


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

    def test_locales_have_same_keys_and_real_line_breaks(self):
        english = Translator("en")._messages
        russian = Translator("ru")._messages
        self.assertEqual(set(english), set(russian))
        for messages in (english, russian):
            for key, text in messages.items():
                self.assertTrue(text.strip(), key)
                self.assertNotIn("\\n", text, key)

    def test_every_literal_key_in_code_exists(self):
        import re
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "src" / "screenrec"
        messages = Translator("en")._messages
        pattern = re.compile(r"""\b(?:t|tr)\(\s*["']([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)["']""")
        missing = {(path.name, key) for path in root.rglob("*.py")
                   for key in pattern.findall(path.read_text(encoding="utf-8")) if key not in messages}
        self.assertEqual(missing, set())

    def test_backend_messages_have_no_hardcoded_russian(self):
        import ast
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "src" / "screenrec"
        found = []
        for folder in ("recorder", "config", "logger"):
            for path in (root / folder).rglob("*.py"):
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                    if isinstance(node, ast.Call) and getattr(node.func, "id", "").endswith(("Error", "Exception")):
                        for arg in node.args:
                            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and re_cyrillic(arg.value):
                                found.append(f"{path.name}:{node.lineno}")
        self.assertEqual(found, [])

    def test_process_language_translates_backend_messages(self):
        from screenrec.localization import set_language, tr, LANGUAGE_ENV
        previous = os.environ.get(LANGUAGE_ENV)
        self.addCleanup(set_language, previous or "en")
        set_language("ru")
        self.assertEqual(os.environ[LANGUAGE_ENV], "ru")
        self.assertEqual(tr("error.window_closed"), Translator("ru").tr("error.window_closed"))
        set_language("en")
        self.assertEqual(tr("settings.audio_mode.system"), "System audio")

    def test_filename_format_labels_follow_language(self):
        from screenrec.ui.filename_dialog import FilenameDialog
        for language, label in (("en", "Year-month-day (2026-09-13)"), ("ru", "Год-месяц-день (2026-09-13)")):
            settings = Settings()
            settings.language = language
            dialog = FilenameDialog(settings)
            self.addCleanup(dialog.close)
            self.assertEqual(dialog.date_format.itemText(dialog.date_format.findData("ymd")), label)

    def test_translation_falls_back_for_unknown_language_and_key(self):
        translator = Translator("de")
        self.assertEqual(translator.language, "en")
        self.assertEqual(translator.tr("missing.key"), "missing.key")
        self.assertEqual(translator.tr("missing.key", fallback="Fallback"), "Fallback")


if __name__ == "__main__":
    unittest.main()
