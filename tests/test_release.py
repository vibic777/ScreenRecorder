import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


class ReleaseTests(unittest.TestCase):
    def test_extension_archive_contains_manifest_locales(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("release_script", root / "scripts/release.py")
        release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(release)
        self.assertTrue(release.region_capture_unavailable(
            {"error": "RuntimeError: Windows graphics function failed: BitBlt: Access is denied"}))
        self.assertTrue(release.region_capture_unavailable(
            {"error": "RuntimeError: Windows graphics function failed: BitBlt: Отказано в доступе"}))
        self.assertFalse(release.region_capture_unavailable(
            {"error": "RuntimeError: encoder could not start"}))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "extension.zip"
            with zipfile.ZipFile(path, "w") as archive:
                release.add_extension(archive, root / "src/screenrec/browser_extension")
            with zipfile.ZipFile(path) as archive:
                for name in ("manifest.json", "_locales/en/messages.json", "_locales/ru/messages.json"):
                    self.assertGreater(len(archive.read(name)), 0)
