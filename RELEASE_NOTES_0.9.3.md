# ScreenRec 0.9.3

Two Windows x64 builds are included:

- **Modern** — Windows 10 1809 or later / Windows 11, PySide6 and Python 3.13.
- **Legacy** — Windows 8 / 8.1, PySide2 and Python 3.8.

This release adds the Legacy port, fixes Qt5 playback compatibility and Windows multimedia plugin packaging, improves overlay preparation and text preview, and adds diagnostics around capture, encoding, and playback.

SHA-256 checksums for both executables are attached as `SHA256SUMS.txt`. The Legacy executable is provided for compatibility testing on Windows 8/8.1; test all capture sources and audio modes on the target system before production use.

Validation on the Windows 11 build host: 48 tests and 9 subtests pass; both standalone EXEs pass synthetic recording, overlay, logging, and player self-tests. A native Windows 8/8.1 VM was not available, so Legacy still needs target-OS verification.
