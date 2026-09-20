"""Qt binding selector used by the modern and legacy profiles.

The legacy profile sets SCREENREC_QT=PySide2 before importing the application.
Modern remains the default and uses PySide6.
"""
import os

BACKEND = os.environ.get("SCREENREC_QT", "PySide6")
if BACKEND not in ("PySide2", "PySide6"):
    raise RuntimeError("SCREENREC_QT must be PySide2 or PySide6")
