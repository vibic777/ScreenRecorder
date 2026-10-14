"""Extensible application translations loaded from JSON locale files."""
import json
import os
from pathlib import Path

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en": "English", "ru": "Русский"}
# Spawned audio processes inherit the environment, so the language travels with it.
LANGUAGE_ENV = "SCREENREC_LANGUAGE"
_active = None


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


def set_language(language):
    """Select the process-wide language used by non-UI modules (errors, statuses)."""
    global _active
    _active = Translator(language)
    os.environ[LANGUAGE_ENV] = _active.language


def tr(key, fallback=None, **values):
    global _active
    if _active is None:
        _active = Translator(os.environ.get(LANGUAGE_ENV, DEFAULT_LANGUAGE))
    return _active.tr(key, fallback, **values)
