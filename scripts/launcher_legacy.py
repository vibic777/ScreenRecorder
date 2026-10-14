"""PyInstaller entry point for the Windows 8/8.1 PySide2 profile."""
import os
os.environ["SCREENREC_QT"] = "PySide2"
from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    from screenrec.main import main
    raise SystemExit(main())
