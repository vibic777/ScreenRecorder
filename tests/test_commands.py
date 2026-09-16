import unittest
from screenrec.config.commands import COMMANDS


class CommandRegistryTests(unittest.TestCase):
    def test_shortcuts_are_unique(self):
        shortcuts = [command.shortcut for command in COMMANDS.values() if command.shortcut]
        self.assertEqual(len(shortcuts), len(set(shortcuts)))

    def test_application_menu_commands_have_shortcuts(self):
        for key in ("start_recording", "stop_recording", "show_window", "exit"):
            self.assertTrue(COMMANDS[key].shortcut)
            self.assertEqual(COMMANDS[key].scope, "global")


if __name__ == "__main__":
    unittest.main()