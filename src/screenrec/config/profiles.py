"""Portable, versioned settings profile format."""
from __future__ import annotations
from screenrec.localization import tr
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import sys

from .settings import Settings

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
    from .atomic import write_json
    write_json(path, export_data(settings))


def load_profile(path: Path, *, fallback=True) -> Settings:
    """Load a profile defensively; malformed or unsafe values use defaults."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("kind") != PROFILE_KIND:
            raise ValueError(tr("error.profile_kind"))
        if document.get("schema_version") != PROFILE_SCHEMA_VERSION:
            raise ValueError(tr("error.profile_schema"))
        data = document.get("settings")
        if not isinstance(data, dict):
            raise ValueError(tr("error.profile_settings"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        if not fallback:
            raise
        return Settings()

    return Settings.from_data(data)

def default_profile_path() -> Path:
    """Return the directory where a default profile is discovered."""
    executable = Path(sys.executable if getattr(sys, "frozen", False) else sys.argv[0]).resolve()
    return executable.parent / "default.json"


def load_default_profile() -> Settings | None:
    path = default_profile_path()
    if not path.is_file():
        return None
    return load_profile(path)
