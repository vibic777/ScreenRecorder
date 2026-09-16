"""Portable, versioned settings profile format."""
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .settings import Settings
from .recording import FORMATS, QUALITIES, AUDIO_MODES

PROFILE_SCHEMA_VERSION = 1
PROFILE_KIND = "screenrec-settings-profile"


def export_data(settings: Settings) -> dict:
    """Return the stable on-disk representation of a settings profile."""
    return {
        "kind": PROFILE_KIND,
        "schema_version": PROFILE_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "settings": asdict(settings),
    }


def save_profile(path: Path, settings: Settings) -> None:
    path = Path(path)
    path.write_text(json.dumps(export_data(settings), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_profile(path: Path) -> Settings:
    """Load a profile defensively; malformed or unsafe values use defaults."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("kind") != PROFILE_KIND:
            raise ValueError("invalid profile kind")
        if document.get("schema_version") != PROFILE_SCHEMA_VERSION:
            raise ValueError("unsupported profile schema")
        data = document.get("settings")
        if not isinstance(data, dict):
            raise ValueError("invalid profile settings")
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return Settings()

    defaults = Settings()
    values = asdict(defaults)
    for key, default in values.items():
        value = data.get(key, default)
        if type(value) is type(default):
            values[key] = value
    settings = Settings(**values)
    if settings.fps not in (15, 24, 30, 60): settings.fps = defaults.fps
    if settings.file_format not in FORMATS: settings.file_format = defaults.file_format
    if settings.quality not in QUALITIES: settings.quality = defaults.quality
    if settings.audio_mode not in AUDIO_MODES: settings.audio_mode = defaults.audio_mode
    if settings.audio_bitrate not in (96, 128, 192, 256, 320): settings.audio_bitrate = defaults.audio_bitrate
    if settings.language not in ("en", "ru"): settings.language = defaults.language
    if settings.theme not in ("green", "blue", "orange", "pink", "purple", "gray", "black"): settings.theme = defaults.theme
    if settings.source_mode not in ("monitor", "region", "window", "tab"): settings.source_mode = defaults.source_mode
    return settings