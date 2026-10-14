# ScreenRec reliability review 0.9.8 — 2026-09-30

## Screen capture

- Modern now uses Windows Graphics Capture for monitor and region sources. Region coordinates are mapped to a physical monitor and cropped before the frame is copied, so recordings do not copy the full monitor for a small selected region.
- If WGC cannot start, Modern falls back to MSS. Legacy retains its Windows 8/8.1 compatible MSS backend.
- Added localized errors for a WGC session that closes or does not provide its first frame. Shutdown also tolerates an already-closed capture session.
- The earlier `BitBlt: Access denied` and DXGI `0x80070005` came from the isolated agent desktop: all desktop-image APIs denied access there. Outside that sandbox, WGC and DXGI both returned a 2560×1080 frame. Modern's native smoke test then recorded a window under occlusion and a selected screen region successfully.

## Verification

- Modern: 75 unit tests, compileall, pip check, JavaScript checks and extension recovery test.
- Legacy: Python 3.8 compileall, pip check, and application/recorder/profile imports.
- `scripts/smoke_sources.py` passed outside the sandbox, including native window capture under occlusion and region capture.
- Release artifacts are built and standalone synthetic/window self-tests run by the release pipeline; results are in `releases/0.9.8/manifest.json`.

Windows 8/8.1 and Linux target-OS testing still requires those systems. Restricted or secure desktops can deny screen capture by design; protected window content may also reject `PrintWindow`.
