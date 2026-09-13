import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_config_path, user_videos_path
from .recording import FORMATS, QUALITIES, AUDIO_MODES
from .templates import default_template


@dataclass
class Settings:
    output_dir: str = str(user_videos_path() / "ScreenRec")
    fps: int = 30
    close_to_tray: bool = True
    notifications: bool = True
    file_format: str = "mp4"
    quality: str = "balanced"
    audio_mode: str = "none"
    microphone_id: str = ""
    system_device_id: str = ""
    audio_bitrate: int = 192
    filename_prefix: str = "ScreenRec"
    filename_date: bool = True
    filename_time: bool = True
    filename_uuid: bool = True
    filename_date_format: str = "ymd"
    filename_time_format: str = "24h"
    overlay_enabled: bool = False
    overlay_name: str = ""
    overlay: dict = field(default_factory=default_template)
    theme: str = "blue"
    source_mode: str = "monitor"
    region: dict = field(default_factory=dict)

    @staticmethod
    def path() -> Path:
        return user_config_path("ScreenRec", appauthor=False) / "settings.json"

    @classmethod
    def load(cls):
        try:
            data = json.loads(cls.path().read_text(encoding="utf-8"))
            settings = cls()
            for key, default in asdict(settings).items():
                value = data.get(key, default)
                if type(value) is type(default):
                    setattr(settings, key, value)
            if settings.fps not in (15, 24, 30, 60):
                settings.fps = 30
            for key, choices, default in (("file_format", FORMATS, "mp4"),
                                          ("quality", QUALITIES, "balanced"),
                                          ("audio_mode", AUDIO_MODES, "none")):
                if getattr(settings, key) not in choices:
                    setattr(settings, key, default)
            if settings.theme not in ("green", "blue", "gray", "black"):
                settings.theme = "blue"
            if settings.source_mode not in ("monitor", "region", "window", "tab"):
                settings.source_mode = "monitor"
            if settings.audio_bitrate not in (96, 128, 192, 256, 320):
                settings.audio_bitrate = 192
            from .filenames import DATE_FORMATS, TIME_FORMATS, clean_prefix
            settings.filename_prefix = clean_prefix(settings.filename_prefix)
            if settings.filename_date_format not in DATE_FORMATS:
                settings.filename_date_format = "ymd"
            if settings.filename_time_format not in TIME_FORMATS:
                settings.filename_time_format = "24h"
            from .templates import validate
            settings.overlay = validate(settings.overlay)
            return settings
        except (OSError, ValueError, AttributeError):
            return cls()

    def save(self):
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
