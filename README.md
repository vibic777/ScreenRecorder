# ScreenRec

ScreenRec is a Windows desktop screen recorder built with Python, Qt and FFmpeg. It ships as two builds: Modern (Python 3.13, PySide6/Qt 6) for Windows 10/11 x64 and Legacy (Python 3.8, PySide2/Qt 5) for Windows 8/8.1 x64.

## Features

- Monitor, region, window and browser-tab capture.
- MP4, MKV and WebM with configurable FPS, quality and audio.
- Microphone, system audio, both, or silent recording.
- System tray workflow and built-in recordings catalogue/player.
- Image and text overlays with reusable templates.
- Seven themes (green, blue, orange, pink, purple, gray, black; gray by default), configurable filenames and runtime logging.
- Single-instance protection enabled by default. Enable Allow multiple instances to run more than one copy.
- Local Chrome/Edge tab capture through a manually installed Manifest V3 extension over loopback.

## Windows support

The Modern build targets 64-bit Windows 10 1809 or newer and Windows 11 (Python 3.13/PySide6). The separate Legacy build targets Windows 8/8.1 x64 (Python 3.8/PySide2). Build them with `scripts/build_modern.bat` and `scripts/build_legacy.bat`; outputs are `dist/modern/ScreenRec.exe` and `dist/legacy/ScreenRec.exe`. Linux support is deferred until a separate compatibility check.

## Development

Each build has its own virtual environment. Modern: Python 3.13 x64 in `.venv` (`scripts/setup_venv_windows.bat`, then `scripts/run_windows.bat`). Legacy: Python 3.8 x64 in `.venv-legacy` (`scripts/setup_venv_legacy.bat`). Both setup scripts locate the interpreter through the `py` launcher (`py -3.13`, `py -3.8`). Install test dependencies with `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` and run `.venv\Scripts\python.exe -m pytest -q`. The pytest suite runs on Modern only; for Legacy, run an import smoke test with `SCREENREC_QT=PySide2` and test the built EXE on Windows 8/8.1.

## Privacy

ScreenRec records locally and does not upload recordings, logs, tab contents, overlay text, or diagnostics. Startup logging is enabled with all levels and writes `screenrec.log` beside the executable (or source package). Do not commit credentials, private keys, local configuration, virtual environments, build artifacts, or test recordings.

## Release status

Version 0.9.3 provides separate Modern (Windows 10/11) and Legacy (Windows 8/8.1) executables. Verify downloaded release assets against the attached SHA-256 checksums.

User-verified: Modern on Windows 10/11; Legacy on Windows 8.1.

## Builds, profiles and cleanup

The Modern track uses Python 3.13 x64 and PySide6/Qt 6 for Windows 10/11. The Legacy track uses Python 3.8 x64 and PySide2/Qt 5 for Windows 8/8.1.

Prepare the environment with:

    scripts\setup_venv_windows.bat

Build the modern EXE with:

    scripts\build_modern.bat

The output is dist\modern\ScreenRec.exe. The generic profile dispatcher is:

    scripts\build_profile.bat modern

Build the Legacy EXE with `scripts\build_legacy.bat` (or `scripts\build_profile.bat legacy`). The output is dist\legacy\ScreenRec.exe.

The two builds differ in these ways:

| | Modern | Legacy |
|---|---|---|
| Windows | 10 1809+ / 11 x64 | 8 / 8.1 x64 |
| Environment | `.venv`, Python 3.13, PySide6, PyInstaller 6 | `.venv-legacy`, Python 3.8, PySide2 5.15, PyInstaller 5.13 |
| Window capture | Windows Graphics Capture by HWND | Screen region under the window rectangle (Pillow ImageGrab); overlapping windows are captured too |
| MP4 | Fragmented MP4 | Regular MP4 (Qt 5/WMF player compatibility) |
| Entry point | scripts\launcher.py | scripts\launcher_legacy.py (sets `SCREENREC_QT=PySide2`) |

The Qt binding is selected by the `screenrec.qt` shim; application code imports Qt only through it. `scripts\build_windows.bat` is the older single-profile command that builds the Modern profile into dist\ScreenRec.exe. `scripts\release_windows.bat` also builds the Modern profile only; build the Legacy EXE separately for a release.

Builds must run inside the profile's virtual environment. scripts\build.py keeps output inside the project, uses --onefile --windowed --noupx, bundles application resources, FFmpeg and the Windows audio/capture modules, and writes the PyInstaller work files under build.

Clean only generated artifacts with:

    powershell -ExecutionPolicy Bypass -File .\scripts\clean_artifacts.ps1 -WhatIf
    powershell -ExecutionPolicy Bypass -File .\scripts\clean_artifacts.ps1

The cleanup script removes build, dist\modern, dist\legacy and dist-build. It never removes source files, .venv or user settings.

## Qt DLL diagnostics

If the EXE reports that Qt or PySide6 cannot load, first run the source version inside .venv:

    .\.venv\Scripts\python.exe -c "from PySide6.QtWidgets import QApplication; print('Qt OK')"

For Legacy, run the same check in `.venv-legacy`: `.\.venv-legacy\Scripts\python.exe -c "from PySide2.QtWidgets import QApplication; print('Qt OK')"`.

Then rebuild with scripts\build_modern.bat (or scripts\build_legacy.bat) and inspect build\ScreenRec\warn-ScreenRec.txt. The build script places the Qt-shipped Microsoft runtime DLLs in the one-file bundle and restricts the build PATH to the Windows system directories and the active venv, preventing incompatible Qt/ICU DLLs from another installation from being selected.

On a clean Windows machine, install the Microsoft Visual C++ x64 runtime if the bundled Qt process still cannot start. Run the EXE from a writable folder and check Windows Event Viewer only after confirming that the file is not blocked by antivirus. Do not copy random DLLs beside the EXE and do not install Python or a separate FFmpeg just to run the packaged application.
