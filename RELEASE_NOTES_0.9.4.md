# ScreenRec 0.9.4

Two Windows x64 builds are included:

- **Modern** — Windows 10 1809 or later / Windows 11, PySide6 and Python 3.13.
- **Legacy** — Windows 8 / 8.1, PySide2 and Python 3.8.

Changes in this release:

- **Legacy player on Windows 8.1:** selecting a recording no longer hangs the player. `QVideoProbe` and the play/pause priming for the first frame, which wedged WMF, are removed; the preview frame and frame snapshots are now decoded by FFmpeg on a background thread, and the paused state shows the `QVideoWidget` itself. Reloading the same file after a recording is saved is skipped. The Legacy volume slider now controls the player (previously it had no effect).
- **Localization:** about 60 error messages for recording, audio, windows, browser tab, overlays, file names, logging, and startup were hard-coded in Russian and appeared in Russian in the English interface; they now follow the interface language. The quality/audio summary in the main window and the date/time formats in the file name builder are translated. Missing `language.changed_title` and `language.restart_required` keys were added, so the language change dialog no longer shows raw key names. Literal `\n` in the profile import, recording deletion, and extension save dialogs was fixed, and duplicate locale keys were removed.
- **Recordings folder:** changing the recordings folder no longer fails with `NameError`.
- **Tooltips** are connected for search, sorting, the recordings list, timeline, player volume and speed, and the multiple instances checkbox.
- **Documentation** now describes both Modern/Legacy builds, their environments and differences, the seven themes (gray by default), and the Legacy window capture limitations; `scripts/setup_venv_windows.bat` creates `.venv` explicitly with Python 3.13.

SHA-256 checksums for both executables are attached as `SHA256SUMS.txt`. The user verified 0.9.3 (Modern on Windows 10/11, Legacy on Windows 8.1); 0.9.4 has been checked on the build host only. Check the required capture sources and audio modes in your own environment before production use.

Validation: 54 tests and 9 subtests pass on the Windows 11 build host; the Legacy sources compile and import under Python 3.8/PySide2; both standalone EXEs pass synthetic recording, overlay, logging, and player self-tests.