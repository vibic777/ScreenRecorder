# ScreenRec

ScreenRec is a Windows desktop screen recorder built with Python, PySide6/Qt 6 and FFmpeg. The modern track targets Windows 10 and Windows 11 x64.

## Features

- Monitor, region, window and browser-tab capture.
- MP4, MKV and WebM with configurable FPS, quality and audio.
- Microphone, system audio, both, or silent recording.
- System tray workflow and built-in recordings catalogue/player.
- Image and text overlays with reusable templates.
- Four themes, configurable filenames and runtime logging.
- Single-instance protection enabled by default. Enable Allow multiple instances to run more than one copy.
- Local Chrome/Edge tab capture through a manually installed Manifest V3 extension over loopback.

## Windows support

The Modern build targets 64-bit Windows 10 1809 or newer and Windows 11 (Python 3.13/PySide6). The separate Legacy build targets Windows 8/8.1 x64 (Python 3.8/PySide2). Build them with `scripts/build_modern.bat` and `scripts/build_legacy.bat`; outputs are `dist/modern/ScreenRec.exe` and `dist/legacy/ScreenRec.exe`. Linux support is deferred until a separate compatibility check.

## Development

Use the project virtual environment. On Windows run scripts/setup_venv_windows.bat and scripts/run_windows.bat. Build with scripts/build_modern.bat. Test with .venv/Scripts/python.exe -m pytest -q.

## Privacy

ScreenRec records locally and does not upload recordings, logs, tab contents, overlay text, or diagnostics. Startup logging is enabled with all levels and writes `screenrec.log` beside the executable (or source package). Do not commit credentials, private keys, local configuration, virtual environments, build artifacts, or test recordings.

## Release status

Version 0.9.3 provides separate Modern (Windows 10/11) and Legacy (Windows 8/8.1) executables. Verify downloaded release assets against the attached SHA-256 checksums.

User-verified: Modern on Windows 10/11; Legacy on Windows 8.1.

## Modern build, profiles and cleanup

The Modern track uses Python 3.13 x64 and PySide6/Qt 6 for Windows 10/11. The Legacy track uses Python 3.8 x64 and PySide2/Qt 5 for Windows 8/8.1.

Prepare the environment with:

    scripts\setup_venv_windows.bat

Build the modern EXE with:

    scripts\build_modern.bat

The output is dist\modern\ScreenRec.exe. The generic profile dispatcher is:

    scripts\build_profile.bat modern

The legacy profile is intentionally paused. Builds must run inside .venv. scripts\build.py keeps output inside the project, uses --onefile --windowed --noupx, bundles application resources, FFmpeg and the Windows audio/capture modules, and writes the PyInstaller work files under build.

Clean only generated artifacts with:

    powershell -ExecutionPolicy Bypass -File .\scripts\clean_artifacts.ps1 -WhatIf
    powershell -ExecutionPolicy Bypass -File .\scripts\clean_artifacts.ps1

The cleanup script removes build, dist\modern, dist\legacy and dist-build. It never removes source files, .venv or user settings.

## Qt DLL diagnostics

If the EXE reports that Qt or PySide6 cannot load, first run the source version inside .venv:

    .\.venv\Scripts\python.exe -c "from PySide6.QtWidgets import QApplication; print('Qt OK')"

Then rebuild with scripts\build_modern.bat and inspect build\ScreenRec\warn-ScreenRec.txt. The build script places the Qt-shipped Microsoft runtime DLLs in the one-file bundle and restricts the build PATH to the Windows system directories and the active venv, preventing incompatible Qt/ICU DLLs from another installation from being selected.

On a clean Windows machine, install the Microsoft Visual C++ x64 runtime if the bundled Qt process still cannot start. Run the EXE from a writable folder and check Windows Event Viewer only after confirming that the file is not blocked by antivirus. Do not copy random DLLs beside the EXE and do not install Python or a separate FFmpeg just to run the packaged application.
