# ScreenRec 0.9.4 release

This release publishes two Windows x64 executables:

- `ScreenRec-0.9.4-Windows10-11-x64.exe` — Modern, Python 3.13/PySide6, Windows 10 1809+ and Windows 11.
- `ScreenRec-0.9.4-Windows8-8.1-x64.exe` — Legacy, Python 3.8/PySide2, Windows 8/8.1.

Local build outputs are `dist/modern/ScreenRec.exe` and `dist/legacy/ScreenRec.exe`. Python and a separate FFmpeg installation are not needed to run either executable. User verification for 0.9.3: Modern on Windows 10/11 and Legacy on Windows 8.1; 0.9.4 is validated by the test suite and EXE self-tests on the build host. Check the required capture sources and audio modes in your own environment before production use.

## Validation

- Modern: `scripts/build_modern.bat` and `scripts/setup_venv_windows.bat`.
- Legacy: install Python 3.8 x64, run `scripts/setup_venv_legacy.bat`, then `scripts/build_legacy.bat`.
- Run the modern pytest suite and `pip check`; compile/import-smoke the Legacy sources in `.venv-legacy`.
- Test overlay preview, text/image recording, recording playback, and the selected audio mode on each supported Windows target.
- Attach `SHA256SUMS.txt` with both EXEs to the GitHub Release. Do not commit executables or other generated build artifacts into Git history.

## Publish

Commit the source and documentation, create the annotated `v0.9.4` tag, push the branch and tag, then create GitHub Release `v0.9.4` with both named EXEs, this release note, and SHA-256 sums. The browser extension retains its independent version.

## Product notes

Recording is local. The app does not upload recordings, logs, browser tab contents, overlay text, or diagnostics. Startup logging is enabled at all levels and writes `screenrec.log` beside the EXE; users can change or disable it. Default audio mode is silent. The browser extension is installed manually. Linux has no release artifact and remains unverified.
