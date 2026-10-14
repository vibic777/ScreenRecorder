import importlib
from . import BACKEND
_qt = importlib.import_module(f"{BACKEND}.QtGui")
globals().update({name: getattr(_qt, name) for name in dir(_qt) if not name.startswith("_")})
# Qt5 exposes these classes from QtWidgets; Qt6 moved them to QtGui.
if BACKEND == "PySide2":
    _widgets = importlib.import_module("PySide2.QtWidgets")
    for _name in ("QAction", "QActionGroup", "QShortcut"):
        if _name not in globals() and hasattr(_widgets, _name):
            globals()[_name] = getattr(_widgets, _name)
