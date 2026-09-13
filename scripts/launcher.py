"""Absolute import entry point for PyInstaller and multiprocessing children."""
from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    from screenrec.main import main
    raise SystemExit(main())
