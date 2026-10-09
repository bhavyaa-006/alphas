"""Small standard-library terminal helpers for the interactive front end."""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import readline  # GNU readline on Unix, libedit on macOS
except ImportError:  # pragma: no cover - Windows
    readline = None


from .agent_cli import SLASH_COMMANDS

COMMANDS = SLASH_COMMANDS
_loaded_history: set[str] = set()


def prompt(text: str, *, history_file: Path | None = None, record: bool = False) -> str:
    """Read an editable line; persist only explicitly selected command prompts."""
    if readline is None or not sys.stdin.isatty():
        return input(text)
    history_key = str(history_file) if history_file else ""
    if history_file and history_key not in _loaded_history:
        try:
            readline.read_history_file(str(history_file))
        except (OSError, ValueError):
            pass
        _loaded_history.add(history_key)
    if record:
        readline.set_completer(lambda value, state: _complete(value, state))
        readline.parse_and_bind("tab: complete")
        readline.set_completer_delims(" \t\n")
    value = input(text)
    if record and value.strip():
        readline.add_history(value.strip())
    if history_file:
        try:
            history_file.parent.mkdir(parents=True, exist_ok=True)
            readline.write_history_file(str(history_file))
            os.chmod(history_file, 0o600)
        except OSError:
            pass
    return value


def _complete(value: str, state: int):
    matches = [c for c in COMMANDS if c.startswith(value)]
    return matches[state] if state < len(matches) else None


def history(limit: int = 12) -> list[str]:
    if readline is None:
        return []
    size = readline.get_current_history_length()
    return [readline.get_history_item(i) or "" for i in range(max(1, size - limit + 1), size + 1)]


def clear() -> None:
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.flush()
