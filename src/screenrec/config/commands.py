"""Central registry of application commands and their default shortcuts."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    key: str
    shortcut: str | None
    label_key: str
    scope: str


COMMANDS = {
    "play_pause": Command("play_pause", "Space", "command.play_pause", "player"),
    "seek_backward": Command("seek_backward", "Left", "command.seek_backward", "player"),
    "seek_forward": Command("seek_forward", "Right", "command.seek_forward", "player"),
    "fullscreen": Command("fullscreen", "F11", "command.fullscreen", "player"),
    "cancel_or_leave_fullscreen": Command("cancel_or_leave_fullscreen", "Escape", "command.cancel_or_leave_fullscreen", "global"),
    "confirm_region": Command("confirm_region", "Enter", "command.confirm_region", "region"),
}


def commands_for(scope=None):
    return tuple(command for command in COMMANDS.values() if scope is None or command.scope in (scope, "global"))