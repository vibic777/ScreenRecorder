import importlib
from . import BACKEND
_qt = importlib.import_module(f"{BACKEND}.QtWidgets")
globals().update({name: getattr(_qt, name) for name in dir(_qt) if not name.startswith("_")})
