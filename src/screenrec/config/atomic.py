"""Replace JSON documents without exposing partial or shared temporary files."""
import json
import os
import tempfile
import threading
import time
from pathlib import Path

_replace_lock = threading.Lock()


def write_json(path, value):
    path = Path(path)
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=str(path.parent),
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        with _replace_lock:
            for attempt in range(5):
                try:
                    temporary.replace(path)
                    break
                except PermissionError as exc:
                    # Windows can briefly deny replacement while another
                    # process is reading/replacing the destination.
                    if os.name != "nt" or getattr(exc, "winerror", None) not in (5, 32, 33) or attempt == 4:
                        raise
                    time.sleep(0.05)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
