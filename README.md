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

The modern build targets 64-bit Windows 10 1809 or newer and Windows 11. Windows 10 compatibility is pending VM verification. Linux support is deferred until a separate compatibility check; no Linux artifact is part of the current modern track.

## Development

Use the project virtual environment. On Windows run scripts/setup_venv_windows.bat and scripts/run_windows.bat. Build with scripts/build_modern.bat. Test with .venv/Scripts/python.exe -m pytest -q.

## Privacy

ScreenRec records locally and does not upload recordings, logs, tab contents, overlay text, or diagnostics. Logs are disabled by default. Do not commit credentials, private keys, local configuration, virtual environments, build artifacts, or test recordings.

## Release status

Version 0.9.0 is under development and is not a public release.

## Modern build, profiles and cleanup

The modern track is the supported Windows 10/11 x64 build. It uses Python 3.13 x64, PySide6/Qt 6, PyInstaller 6 and the project virtual environment.

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
