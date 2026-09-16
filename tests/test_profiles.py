import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from screenrec.config.profiles import (
    PROFILE_KIND, PROFILE_SCHEMA_VERSION, default_profile_path,
    export_data, load_default_profile, load_profile, save_profile,
)
from screenrec.config.settings import Settings
from screenrec.main import profile_path_from_args


class ProfileTests(unittest.TestCase):
    def test_export_import_round_trip(self):
        settings = Settings(theme="purple", fps=60, filename_prefix="Lesson")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            save_profile(path, settings)
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["kind"], PROFILE_KIND)
            self.assertEqual(document["schema_version"], PROFILE_SCHEMA_VERSION)
            loaded = load_profile(path, fallback=False)
            self.assertEqual(loaded.theme, "purple")
            self.assertEqual(loaded.fps, 60)
            self.assertEqual(loaded.filename_prefix, "Lesson")

    def test_invalid_profile_falls_back_without_crashing(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(load_profile(path).theme, "gray")
            with self.assertRaises(ValueError):
                load_profile(path, fallback=False)

    def test_default_profile_is_discovered_next_to_launcher(self):
        with TemporaryDirectory() as directory:
            default = Path(directory) / "default.json"
            save_profile(default, Settings(theme="orange"))
            with patch("screenrec.config.profiles.default_profile_path", return_value=default):
                self.assertEqual(load_default_profile().theme, "orange")

    def test_command_line_profile_has_explicit_path(self):
        path = Path("profiles") / "portable.json"
        self.assertEqual(profile_path_from_args(["screenrec", "--profile", str(path)]), path)
        with self.assertRaises(SystemExit):
            profile_path_from_args(["screenrec", "--profile"])

    def test_missing_fields_are_backward_compatible(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "old.json"
            path.write_text(json.dumps({"kind": PROFILE_KIND, "schema_version": PROFILE_SCHEMA_VERSION,
                                        "settings": {"theme": "pink"}}), encoding="utf-8")
            loaded = load_profile(path, fallback=False)
            self.assertEqual(loaded.theme, "pink")
            self.assertEqual(loaded.fps, Settings().fps)


if __name__ == "__main__":
    unittest.main()