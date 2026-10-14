# ScreenRec 0.9.2 — security check

## Scope

This report covers the Windows x64 executable shipped in the `v0.9.2` release.

## Artifact

- File: `ScreenRec.exe`
- SHA-256: `147b184c309be2d02bab007232dcd500d2f78b9ef1cb49520e38b2cd437b72f1`
- Target: Windows 10/11 x64
- Build source: commit `8350d60`

## Checks performed

- Source test suite: **47/47 passed**.
- Standalone EXE self-test: **passed**.
- Synthetic recording: **31 frames, 2.06 seconds**.
- Self-test covered recording, logging, overlays and player checks.
- The release includes `SHA256SUMS.txt` for local hash verification.

## Antivirus reports

The following heuristic detections were reported by the user:

- `W32.Malware.7E9A7643`
- `McAfee ScannerTi!147B184C309B`

These detections are not treated as proof that the application is malicious, but they are also not dismissed as proof of safety. The executable is a PyInstaller one-file Windows build and bundles Python, Qt and FFmpeg; that packaging can trigger generic heuristic detections. The signatures must be independently reviewed with the exact SHA-256 above by the relevant vendors.

Do not run the file if it came from an untrusted mirror. Verify the hash, inspect the source and build locally, and use a clean Windows test environment. This project does not claim that an antivirus result is a false positive without vendor confirmation.

## Known limitation

The isolated build environment could not complete the separate Windows Graphics Capture window-fixture check (`GraphicsCaptureItem` conversion failure). The standalone self-test and all source tests listed above passed.
