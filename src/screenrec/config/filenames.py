"""Shared filename generation and exclusive per-recording name reservation."""
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import unicodedata

from screenrec.localization import tr

# Display labels live in the locales: filename.date.<key>, filename.time.<key>.
DATE_FORMATS = {
    "ymd": "%Y-%m-%d",
    "dmy": "%d-%m-%Y",
    "mdy": "%m-%d-%Y",
    "dmy_dot": "%d.%m.%Y",
    "ymd_compact": "%Y%m%d",
    "mdy_dot": "%m.%d.%Y",
}
TIME_FORMATS = ("24h", "12h", "24h_compact")
def clean_prefix(value):
    value = "".join("_" if c in '<>:"/\\|?*' or unicodedata.category(c).startswith("C") else c for c in value)
    value = value.strip(" .")[:80].rstrip(" .")
    while len(value.encode("utf-8")) > 128:
        value = value[:-1]
    value = value.rstrip(" .")
    # Windows device names are reserved even when followed by an extension.
    base = value.split(".")[0].upper()
    reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    reserved.update(f"{prefix}{n}" for prefix in ("COM","LPT") for n in "123456789¹²³")
    if base in reserved:
        value = "_" + value
    return value

def filename(settings, moment=None, identifier=None):
    moment = moment or datetime.now()
    parts = [clean_prefix(settings.filename_prefix)]
    if settings.filename_date:
        pattern = DATE_FORMATS.get(settings.filename_date_format,DATE_FORMATS["ymd"])
        parts.append(moment.strftime(pattern))
    if settings.filename_time:
        mode = settings.filename_time_format
        if mode == "12h":
            parts.append(f"{moment.hour % 12 or 12:02}-{moment.minute:02}-{moment.second:02}_" + ("AM" if moment.hour < 12 else "PM"))
        else:
            parts.append(moment.strftime("%H%M%S" if mode == "24h_compact" else "%H-%M-%S"))
    if settings.filename_uuid:
        parts.append(str(identifier or uuid4()))
    stem = "_".join(part for part in parts if part) or "ScreenRec"
    if settings.file_format not in ("mp4","mkv","webm"):
        raise ValueError(tr("error.filename_unknown_format"))
    return stem + "." + settings.file_format

def reserve(directory, settings):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    base = Path(filename(settings))
    for number in range(1,100001):
        path = directory / (base.name if number == 1 else f"{base.stem}_{number}{base.suffix}")
        lock = directory / f".{path.name}.recording"
        parts = directory / f".{path.stem}.parts"
        if path.exists() or parts.exists():
            continue
        try:
            lock.mkdir()
        except FileExistsError:
            continue
        if path.exists() or parts.exists():
            lock.rmdir()
            continue
        return path, lock
    raise RuntimeError(tr("error.filename_no_free_name"))
