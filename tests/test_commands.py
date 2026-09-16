import unittest
from screenrec.config.commands import COMMANDS, commands_for


class CommandRegistryTests(unittest.TestCase):
    def test_shortcuts_are_unique(self):
        shortcuts = [command.shortcut for command in COMMANDS.values() if command.shortcut]
        self.assertEqual(len(shortcuts), len(set(shortcuts)))

    def test_scoped_commands_are_isolated(self):
        self.assertTrue(all(command.scope == "player" for command in commands_for("player")))
        self.assertTrue(all(command.scope == "region" for command in commands_for("region")))
        self.assertNotIn(COMMANDS["start_recording"], commands_for("player"))
    def test_application_menu_commands_have_shortcuts(self):
        for key in ("start_recording", "stop_recording", "show_window", "exit"):
            self.assertTrue(COMMANDS[key].shortcut)
            self.assertEqual(COMMANDS[key].scope, "global")


if __name__ == "__main__":
    unittest.main()