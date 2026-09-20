"""Central registry of application commands and their default shortcuts."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    key: str
    shortcut: str | None
    label_key: str
    scope: str


COMMANDS = {
    "start_recording": Command("start_recording", "Ctrl+Shift+R", "command.start_recording", "global"),
    "stop_recording": Command("stop_recording", "Ctrl+Shift+S", "command.stop_recording", "global"),
    "show_window": Command("show_window", "Ctrl+Shift+O", "command.show_window", "global"),
    "exit": Command("exit", "Ctrl+Shift+Q", "command.exit", "global"),
    "play_pause": Command("play_pause", "Space", "command.play_pause", "player"),
    "stop_playback": Command("stop_playback", "Home", "command.stop_playback", "player"),
    "previous_recording": Command("previous_recording", "Ctrl+Left", "command.previous_recording", "player"),
    "next_recording": Command("next_recording", "Ctrl+Right", "command.next_recording", "player"),
    "snapshot": Command("snapshot", "Ctrl+Shift+P", "command.snapshot", "player"),
    "seek_backward": Command("seek_backward", "Left", "command.seek_backward", "player"),
    "seek_forward": Command("seek_forward", "Right", "command.seek_forward", "player"),
    "fullscreen": Command("fullscreen", "F11", "command.fullscreen", "player"),
    "cancel_or_leave_fullscreen": Command("cancel_or_leave_fullscreen", "Escape", "command.cancel_or_leave_fullscreen", "player"),
    "confirm_region": Command("confirm_region", "Enter", "command.confirm_region", "region"),
}


def commands_for(scope=None):
    return tuple(command for command in COMMANDS.values() if scope is None or command.scope == scope)
