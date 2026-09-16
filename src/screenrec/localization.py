"""Extensible application translations loaded from JSON locale files."""
import json
from pathlib import Path

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en": "English", "ru": "Русский"}


class Translator:
    def __init__(self, language=DEFAULT_LANGUAGE):
        self.language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        self._messages = self._load(self.language)

    @staticmethod
    def _load(language):
        path = Path(__file__).with_name("locales") / f"{language}.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def set_language(self, language):
        self.language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        self._messages = self._load(self.language)

    def tr(self, key, fallback=None, **values):
        text = self._messages.get(key, fallback if fallback is not None else key)
        return text.format(**values) if values else text