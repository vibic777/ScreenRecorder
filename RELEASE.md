# ScreenRec 0.9.11 — reliability review

Local review artifacts in `releases/0.9.11`:

- `ScreenRec-0.9.11-Windows10-11-x64.exe` — Modern, Python 3.13/PySide6 (Windows 10 1809+ and Windows 11).
- `ScreenRec-0.9.11-Windows8-8.1-x64.exe` — Legacy, Python 3.8/PySide2.
- ZIP packages for each profile, source ZIP, browser extension ZIP including `_locales`, dependency snapshots, `manifest.json` and `SHA256SUMS.txt`.

Modern captures a selected region directly through MSS; whole-monitor capture uses Windows Graphics Capture with MSS fallback. Region startup no longer calls the native WGC monitor capture path. If MSS rejects the region, ScreenRec reports the failure without terminating the process. See [the itemized audit](AUDIT_0.9.11.ru.md) and [changelog](CHANGELOG.md).

## Build and verification

Run `scripts/release_windows.bat` from a clean commit with both `.venv` and `.venv-legacy` prepared. It checks dependencies and Modern tests, checks Legacy syntax/imports, builds both EXEs sequentially, and runs each EXE without Python or external FFmpeg in PATH. Both synthetic and native-window self-tests must pass, including decoding, overlays, logging and playback. Results and the exact source commit are recorded in the manifest before the pending directory becomes the final release.

Build outputs remain in `dist/modern` and `dist/legacy`. A failed release leaves `<version>.pending` for diagnosis and never silently reuses it. Move that directory aside before retrying. EXEs and generated artifacts are not committed.

Manual Windows 8/8.1 verification remains required; building Legacy and running it on the development Windows host does not verify that OS. Linux is unverified. Test your normal capture source, microphone/system audio, overlay, stop/restart, playback, profile import and logging after restart. Long-duration recording and every device/driver combination are outside automated coverage.

## Publication

The release is prepared locally for user verification. Push, public release upload and publication require a separate explicit request. The extension retains its independent version. Recording remains local; logging follows saved settings (all levels enabled on a fresh profile).
