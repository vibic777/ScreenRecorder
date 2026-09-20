import importlib
from . import BACKEND
_qt = importlib.import_module(f"{BACKEND}.QtMultimedia")
globals().update({name: getattr(_qt, name) for name in dir(_qt) if not name.startswith("_")})
if BACKEND == "PySide2" and "QMediaMetaData" not in globals():
    class QMediaMetaData:
        class Key:
            Resolution = "Resolution"
