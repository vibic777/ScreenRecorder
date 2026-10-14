# Reliability review 0.9.7 — 2026-09-30

## Findings fixed

- **Critical startup regression:** `container_options()` read `os.environ` without importing `os`. Selecting MP4 raised `NameError`, preventing recordings in both Modern and Legacy. The import is restored and a test covers both profile settings.
- **Encoder cleanup:** an operating-system error while waiting for FFmpeg could escape finalization before the pipe and diagnostic file were closed. Wait failures now become a normal encoder-timeout error; cleanup bounds reaping and closes resources in `finally`.
- **Windows window capture:** Windows Graphics Capture can reject valid HWNDs with `Failed to convert item to GraphicsCaptureItem`; Legacy desktop BitBlt can also be denied. Both profiles now use Win32 `PrintWindow` with a reusable top-down BGRA DIB when needed. It preserves window bounds, rejects minimized/resized/closed windows, and releases GDI resources; native-window recording under occlusion passed. Protected or GPU-only windows can still reject `PrintWindow`.
- **Delayed capture stop:** after a long source stall, catch-up could enqueue an arbitrarily large number of duplicate frames. Catch-up is capped at one second of frames, limiting resource spikes and stop delay.

## Verification

- Modern: 73 unit tests, Python compileall, pip check, JavaScript syntax checks, and browser extension recovery test.
- Legacy: Python 3.8 compileall, pip check, and application/recorder/profile imports.
- Both standalone Windows executables are built and run through synthetic-source and native-window self-tests by the release script; results are stored in `releases/0.9.7/manifest.json`.

Windows 8/8.1 and Linux target-OS validation is not available on the build host. The mss provider emits a deprecation warning for `mss.mss`; functionality passes, and migration is a compatibility follow-up rather than a current failure.
