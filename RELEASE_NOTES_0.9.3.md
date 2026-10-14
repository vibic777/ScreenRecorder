# ScreenRec 0.9.3

Two Windows x64 builds are included:

- **Modern** — Windows 10 1809 or later / Windows 11, PySide6 and Python 3.13.
- **Legacy** — Windows 8 / 8.1, PySide2 and Python 3.8.

This release adds the Legacy port, fixes Qt5 playback compatibility and Windows multimedia plugin packaging, improves overlay preparation and text preview, and adds diagnostics around capture, encoding, and playback.

SHA-256 checksums for both executables are attached as `SHA256SUMS.txt`. User verification: Modern was tested on Windows 10/11 and Legacy on Windows 8.1. Check the required capture sources and audio modes in your own environment before production use.

Validation: 48 tests and 9 subtests pass on the Windows 11 build host; both standalone EXEs pass synthetic recording, overlay, logging, and player self-tests. In addition, the user verified Modern on Windows 10/11 and Legacy on Windows 8.1.
