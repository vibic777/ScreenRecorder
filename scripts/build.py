import os
import sys
import platform
import importlib
from pathlib import Path

if sys.prefix == sys.base_prefix:
    raise SystemExit("Build must run inside .venv")

if platform.system() == "Windows":
    # Prevent unrelated applications on PATH from supplying incompatible Qt dependencies (ICU).
    system_root = Path(os.environ["SystemRoot"])
    os.environ["PATH"] = os.pathsep.join([str(system_root / "System32"), str(system_root),
                                        str(Path(sys.executable).parent)])
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
qt_backend = os.environ.get("SCREENREC_QT", "PySide6")
qt_widgets = importlib.import_module(f"{qt_backend}.QtWidgets")
qt_gui = importlib.import_module(f"{qt_backend}.QtGui")
qt_package = importlib.import_module(qt_backend)
QApplication = qt_widgets.QApplication
QIcon = qt_gui.QIcon
import PyInstaller.__main__

root = Path(__file__).resolve().parents[1]
os.chdir(root)
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", default="dist")
args = parser.parse_args()
output_dir = (root / args.output_dir).resolve()
try:
    output_dir.relative_to(root)
except ValueError:
    raise SystemExit("Build output must be inside the project")
app = QApplication([])
icon_path = root / "build" / "screenrec.ico"
icon_path.parent.mkdir(exist_ok=True)
icon = QIcon(str(root / "src/screenrec/assets/icons/icon_blue.svg"))
if not icon.pixmap(256, 256).save(str(icon_path), "ICO"):
    raise SystemExit("Could not generate application icon")
audio_package = "pyaudiowpatch" if platform.system() == "Windows" else "soundcard"
excludes = ["--exclude-module", "soundcard"] if platform.system() == "Windows" else ["--exclude-module", "pyaudiowpatch"]
data_options = []
for relative in ("src/screenrec/ui/themes", "src/screenrec/assets", "src/screenrec/locales", "src/screenrec/browser_extension"):
    data_options += ["--add-data", f"{root / relative}{os.pathsep}screenrec/{relative.split('/', 2)[-1]}"]
runtime_options = []
if platform.system() == "Windows":
    # Load the Qt-shipped runtime at process startup, before an older system copy.
    qt_directory = Path(qt_package.__file__).parent
    for name in ("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "msvcp140_codecvt_ids.dll",
                 "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll"):
        runtime_options += ["--add-binary", f"{qt_directory / name}{os.pathsep}."]
    if qt_backend == "PySide2":
        # PyInstaller's Qt5 hook does not reliably collect Multimedia
        # backends. Without wmfengine QMediaPlayer reports InvalidMedia with
        # an empty error string on Windows.
        for plugin in ("wmfengine.dll", "dsengine.dll", "qtmedia_audioengine.dll"):
            runtime_options += ["--add-binary", f"{qt_directory / 'plugins' / 'mediaservice' / plugin}{os.pathsep}PySide2/plugins/mediaservice"]
PyInstaller.__main__.run([
    "--noconfirm", "--clean", "--onefile", "--windowed", "--name", "ScreenRec", "--noupx",
    "--distpath", str(output_dir), "--icon", str(icon_path), "--paths", str(root / "src"),
    "--specpath", str(root / "build"), "--collect-data", "screenrec",
    *data_options,
    "--collect-all", "imageio_ffmpeg", "--collect-all", audio_package,
    "--hidden-import", f"{qt_backend}.QtCore", "--hidden-import", f"{qt_backend}.QtGui",
    "--hidden-import", f"{qt_backend}.QtWidgets", "--hidden-import", f"{qt_backend}.QtMultimedia",
    "--hidden-import", f"{qt_backend}.QtMultimediaWidgets",
    *(["--collect-all", "windows_capture"] if platform.system() == "Windows" and qt_backend == "PySide6" else []),
    *runtime_options, *excludes, str(root / ("scripts/launcher_legacy.py" if qt_backend == "PySide2" else "scripts/launcher.py")),
])
