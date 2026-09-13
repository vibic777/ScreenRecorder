import os
import sys
import platform
from pathlib import Path

if sys.prefix == sys.base_prefix:
    raise SystemExit("Build must run inside .venv")

if platform.system() == "Windows":
    # Prevent unrelated applications on PATH from supplying incompatible Qt dependencies (ICU).
    system_root = Path(os.environ["SystemRoot"])
    os.environ["PATH"] = os.pathsep.join([str(system_root / "System32"), str(system_root),
                                        str(Path(sys.executable).parent)])
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
import PyInstaller.__main__
import PySide6

root = Path(__file__).resolve().parents[1]
os.chdir(root)
app = QApplication([])
icon_path = root / "build" / "screenrec.ico"
icon_path.parent.mkdir(exist_ok=True)
icon = QIcon(str(root / "src/screenrec/assets/icons/icon_blue.svg"))
if not icon.pixmap(256, 256).save(str(icon_path), "ICO"):
    raise SystemExit("Could not generate application icon")
audio_package = "pyaudiowpatch" if platform.system() == "Windows" else "soundcard"
excludes = ["--exclude-module", "soundcard"] if platform.system() == "Windows" else ["--exclude-module", "pyaudiowpatch"]
runtime_options = []
if platform.system() == "Windows":
    # Load the Qt-shipped runtime at process startup, before an older system copy.
    qt_directory = Path(PySide6.__file__).parent
    for name in ("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "msvcp140_codecvt_ids.dll",
                 "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll"):
        runtime_options += ["--add-binary", f"{qt_directory / name}{os.pathsep}."]
PyInstaller.__main__.run([
    "--noconfirm", "--clean", "--onefile", "--windowed", "--name", "ScreenRec", "--noupx",
    "--icon", str(icon_path), "--paths", str(root / "src"),
    "--specpath", str(root / "build"), "--collect-data", "screenrec",
    "--collect-all", "imageio_ffmpeg", "--collect-all", audio_package,
    *(["--collect-all", "windows_capture"] if platform.system() == "Windows" else []),
    *runtime_options, *excludes, str(root / "scripts/launcher.py"),
])
