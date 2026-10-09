"""Persistent full-screen terminal UI for the ALPHAS command center.

The screen is split into three structural regions rendered by a single
prompt_toolkit ``Application``:

  ┌ header ────── lavender ALPHAS ASCII-art branding (fixed, top)
  ├ workspace ─── dynamic content: command output, help, menus, progress,
  │               errors, results - independently scrollable
  └ input bar ─── bordered command prompt + context/shortcut status line
                  (fixed, bottom)

This module is presentation only.  Every keystroke is routed through the
existing deterministic dispatcher (``agent_cli.CommandTerminal``), so the 13
global slash commands, context-aware ``?`` help, nested options and their real
handlers are exactly the ones the legacy prompt loop used.  No LLM, timers or
fabricated output are involved: handler stdout/stderr and Rich console output
are captured and streamed into the workspace as the handlers actually run.
"""
from __future__ import annotations

import asyncio
import builtins
import contextlib
import io
import os
import queue
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.data_structures import Point
from prompt_toolkit.filters import has_focus
from prompt_toolkit.formatted_text import ANSI, to_formatted_text
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl, UIContent, UIControl
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea
from rich.console import Console

# ---------------------------------------------------------------- constants

HEADER_HEIGHT = 7          # 6 rows of ASCII art + 1 tagline row
RULE_FILL = "─" * 512      # clipped by the window to the real width
MAX_WORKSPACE_LINES = 4000 # scrollback cap; older lines are dropped

IDLE = "idle"
RUNNING = "running"
CONFIRM = "confirm"
EXITING = "exiting"

# Sentinels handed to a handler blocked in input().
_EOF = object()
_INTERRUPT = object()

_TITLES = {
    IDLE: "> Type a command...",
    RUNNING: "command running - input paused (Ctrl+C requests cancel)",
    CONFIRM: "confirmation - type your answer, Enter to send",
    EXITING: "shutting down...",
}


def _letter_rows(*rows: str) -> tuple[str, ...]:
    return rows


# Block letters for "ALPHAS".  Each letter is padded to its own width when the
# rows are joined, so the columns always line up.
_ART_LETTERS = (
    _letter_rows(  # A
        " █████╗",
        "██╔══██╗",
        "███████║",
        "██╔══██║",
        "██║  ██║",
        "╚═╝  ╚═╝",
    ),
    _letter_rows(  # L
        "██╗",
        "██║",
        "██║",
        "██║",
        "███████╗",
        "╚══════╝",
    ),
    _letter_rows(  # P
        "██████╗",
        "██╔══██╗",
        "██████╔╝",
        "██╔═══╝",
        "██║",
        "╚═╝",
    ),
    _letter_rows(  # H
        "██╗   ██╗",
        "██║   ██║",
        "██║   ██║",
        "█████████",
        "██║   ██║",
        "╚═╝   ╚═╝",
    ),
    _letter_rows(  # A
        " █████╗",
        "██╔══██╗",
        "███████║",
        "██╔══██║",
        "██║  ██║",
        "╚═╝  ╚═╝",
    ),
    _letter_rows(  # S
        " ███████╗",
        "██╔═════╝",
        "╚██████╗",
        " ╚════██╗",
        "███████║",
        "╚══════╝",
    ),
)


def _build_art() -> list[str]:
    widths = [max(len(row) for row in letter) for letter in _ART_LETTERS]
    return [
        " ".join(row.ljust(width) for row, width in zip(letter, widths))
        for letter in zip(*_ART_LETTERS)
    ]


HEADER_ART = _build_art()          # 6 rows, 55 columns wide
ART_MIN_WIDTH = len(HEADER_ART[0]) + 1
TAGLINE = "ALPHAS · WorldQuant BRAIN · persistent command center"

_STYLE = Style.from_dict(
    {
        "header": "bold #b9a7e3",
        "header.tag": "#9d8fc4",
        "rule": "#5b5180",
        "status": "#a99ccf",
        "frame": "",
        "frame.border": "#6c5f96",
        "frame.label": "bold #b9a7e3",
        "text-area": "",
        "text-area.prompt": "bold #c4b5fd",
        "scrollbar": "bg:#4a4166",
    }
)


def strip_ansi(text: str) -> str:
    """Plain text of an ANSI-coloured string (used by tests and diagnostics)."""
    return "".join(fragment[1] for fragment in to_formatted_text(ANSI(text)))


def _terminal_columns() -> int:
    try:
        size = get_app().output.get_size()
        if size and size.columns:
            return int(size.columns)
    except Exception:
        pass
    try:
        return shutil.get_terminal_size().columns or 80
    except Exception:
        return 80


# ---------------------------------------------------------------- workspace


class WorkspaceBuffer:
    """Scrollback text for the middle region.

    ``anchor`` is the buffer line the Window keeps visible (it is exposed as
    the UI content cursor, so prompt_toolkit's own scroll math positions the
    viewport around it); ``following`` pins the view to the newest output
    until the user scrolls away.
    """

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.anchor = 0
        self.following = True

    def append(self, line: str) -> None:
        self.lines.append(line)
        if len(self.lines) > MAX_WORKSPACE_LINES:
            dropped = len(self.lines) - MAX_WORKSPACE_LINES
            del self.lines[:dropped]
            self.anchor = max(0, self.anchor - dropped)
        if self.following:
            self.anchor = len(self.lines) - 1

    @property
    def last_index(self) -> int:
        return max(0, len(self.lines) - 1)

    def plain_text(self) -> str:
        return "\n".join(strip_ansi(line) for line in self.lines)


class WorkspaceControl(UIControl):
    """Renders the workspace buffer and owns its scroll position."""

    def __init__(self, buffer: WorkspaceBuffer, on_width=None) -> None:
        self.buffer = buffer
        self.on_width = on_width

    def is_focusable(self) -> bool:
        return False

    def create_content(self, width: int, height: int) -> UIContent:
        if self.on_width is not None and width > 0:
            with contextlib.suppress(Exception):
                self.on_width(width)
        lines = self.buffer.lines or [""]
        anchor = max(0, min(self.buffer.anchor, len(lines) - 1))

        def get_line(index: int):
            try:
                return to_formatted_text(ANSI(lines[index]))
            except IndexError:
                return []

        return UIContent(
            get_line=get_line,
            line_count=len(lines),
            cursor_position=Point(x=0, y=anchor),
            show_cursor=False,
        )

    def mouse_handler(self, mouse_event: MouseEvent):
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self._scroll(-3)
            return None
        if mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self._scroll(3)
            return None
        return NotImplemented

    def _scroll(self, direction: int) -> None:
        # Mouse handlers run on the event loop thread, so this is direct.
        buffer = self.buffer
        if direction < 0:
            buffer.anchor = max(0, buffer.anchor + direction * 3)
            if buffer.anchor < buffer.last_index:
                buffer.following = False
        else:
            buffer.anchor = min(buffer.last_index, buffer.anchor + direction * 3)
            if buffer.anchor >= buffer.last_index:
                buffer.following = True
        get_app().invalidate()


class WorkspaceStream:
    """File-like sink that forwards complete lines into the workspace.

    Handles ``\\n`` line breaks, ``\\r\\n`` pairs and carriage-return
    redraws (progress bars).  ``isatty()`` reports True so styling helpers
    keep emitting colour. ``fileno()`` exposes the real terminal only for
    read-only uses such as ``os.get_terminal_size`` - every actual write goes
    through ``write()``, so nothing can paint over the UI.
    """

    encoding = "utf-8"
    line_buffering = True

    def __init__(self, ui: "AlphasUI", fileno: int | None = None) -> None:
        self._ui = ui
        self._fileno = fileno
        self._pending = ""
        self._lock = threading.Lock()

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False

    def isatty(self) -> bool:
        return True

    def fileno(self) -> int:
        if self._fileno is None:
            raise io.UnsupportedOperation("workspace stream has no file descriptor")
        return self._fileno

    def write(self, data) -> int:
        if not data:
            return 0
        if not isinstance(data, str):
            data = str(data)
        with self._lock:
            buffer = (self._pending + data).replace("\r\n", "\n")
            parts = buffer.split("\n")
            complete = [part.rsplit("\r", 1)[-1] for part in parts[:-1]]
            self._pending = parts[-1].rsplit("\r", 1)[-1]
        for line in complete:
            self._ui._post(line)
        return len(data)

    def flush(self) -> None:
        with self._lock:
            pending, self._pending = self._pending, ""
        if pending:
            self._ui._post(pending.rsplit("\r", 1)[-1])


# ---------------------------------------------------------------- the app


class AlphasUI:
    """The persistent three-region screen and its command execution bridge."""

    def __init__(self, terminal, *, input=None, output=None) -> None:
        self.terminal = terminal
        self.home = Path(terminal.home)

        self.state = IDLE
        self.current_command = ""
        # Monotonic count of completed commands (tests/diagnostics rely on it
        # to know a submitted command has fully finished).
        self.commands_finished = 0
        self._note = ""
        self._loop: asyncio.AbstractEventLoop | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._task: asyncio.Task | None = None
        self._answer_q: queue.Queue | None = None
        self._app_running = False
        self._closing = False
        self._bridge: WorkspaceStream | None = None
        self._rich_console: Console | None = None
        self._ws_width = 0
        self._cancel_event = threading.Event()
        self.terminal.cancel_event = self._cancel_event

        self.buffer = WorkspaceBuffer()

        # ------------------------------------------------ layout components
        self.header_window = Window(
            content=FormattedTextControl(self._header_text),
            height=HEADER_HEIGHT,
            wrap_lines=False,
            dont_extend_height=True,
        )
        self.rule_top = Window(
            content=FormattedTextControl(lambda: [("class:rule", RULE_FILL)]),
            height=1,
            wrap_lines=False,
            dont_extend_height=True,
        )
        self.workspace_control = WorkspaceControl(self.buffer, on_width=self._on_width)
        self.workspace_window = Window(
            content=self.workspace_control,
            wrap_lines=True,
            always_hide_cursor=True,
            right_margins=[ScrollbarMargin(display_arrows=False)],
        )

        history_file = self.home / "history"
        self.textarea = TextArea(
            multiline=False,
            prompt="> ",
            completer=WordCompleter([*terminal.SLASH, "?"], sentence=True),
            complete_while_typing=False,
            history=FileHistory(str(history_file)),
            accept_handler=self._on_accept,
            wrap_lines=True,
        )
        self.input_frame = Frame(self.textarea, title=_TITLES[IDLE])

        self.status_window = Window(
            content=FormattedTextControl(self._status_text),
            height=1,
            wrap_lines=False,
            dont_extend_height=True,
        )

        self.root = HSplit(
            [
                self.header_window,
                self.rule_top,
                self.workspace_window,
                self.input_frame,
                self.status_window,
            ]
        )

        # ------------------------------------------------ key bindings
        kb = KeyBindings()

        @kb.add("c-c")
        def _ctrl_c(event):
            self._on_sigint()

        @kb.add("c-j", filter=has_focus(self.textarea.buffer))
        def _ctrl_j(event):
            # Same as the legacy prompt: Ctrl+J inserts a newline.
            event.current_buffer.insert_text("\n")

        @kb.add("pageup")
        def _page_up(event):
            self._scroll_view(-1)

        @kb.add("pagedown")
        def _page_down(event):
            self._scroll_view(1)

        self.key_bindings = kb

        # ------------------------------------------------ application
        if output is None:
            try:
                from prompt_toolkit.output import create_output
                from prompt_toolkit.output import DummyOutput

                output = (
                    create_output(sys.stdout)
                    if sys.stdout.isatty()
                    else DummyOutput()
                )
            except Exception:
                from prompt_toolkit.output import DummyOutput

                output = DummyOutput()
        if input is None:
            from prompt_toolkit.input import create_input

            input = create_input()

        self.app: Application = Application(
            layout=Layout(self.root, focused_element=self.textarea.window),
            style=_STYLE,
            key_bindings=kb,
            full_screen=True,
            mouse_support=True,
            input=input,
            output=output,
        )

    # ------------------------------------------------------------ rendering

    def _header_text(self):
        fragments = []
        if _terminal_columns() >= ART_MIN_WIDTH:
            rows = [*HEADER_ART, TAGLINE]
        else:
            rows = ["ALPHAS", TAGLINE]
        for index, row in enumerate(rows):
            if index:
                fragments.append(("", "\n"))
            style = "class:header.tag" if index == len(rows) - 1 else "class:header"
            fragments.append((style, row))
        return fragments

    def _status_text(self) -> str:
        context = getattr(self.terminal, "context", None) or "main"
        context = "main" if context == "main" else f"/{context}"
        if self.state == RUNNING:
            activity = f"running {self.current_command}".strip()
        elif self.state == CONFIRM:
            activity = "waiting for your answer"
        elif self.state == EXITING:
            activity = "exiting"
        else:
            activity = "idle"
        if self._note:
            activity = f"{activity} · {self._note}"
        shortcuts = "Enter: run · ?: help · PgUp/PgDn: scroll · Ctrl+C: cancel/exit"
        return f" {context} │ {activity} │ {shortcuts}"

    def _on_width(self, width: int) -> None:
        """Keep captured Rich output wrapped to the real workspace width."""
        if width > 0 and width != self._ws_width:
            self._ws_width = width
            if self._rich_console is not None:
                with contextlib.suppress(Exception):
                    self._rich_console.width = width

    def _scroll_view(self, direction: int) -> None:
        step = self._viewport_height() - 1 or 1
        if direction < 0:
            self.buffer.anchor = max(0, self.buffer.anchor - step)
            if self.buffer.anchor < self.buffer.last_index:
                self.buffer.following = False
        else:
            self.buffer.anchor = min(self.buffer.last_index, self.buffer.anchor + step)
            if self.buffer.anchor >= self.buffer.last_index:
                self.buffer.following = True
        self.app.invalidate()

    def _viewport_height(self) -> int:
        info = self.workspace_window.render_info
        if info is not None and info.window_height > 0:
            return info.window_height
        return 20

    # ------------------------------------------------------------ state

    def _set_state(self, state: str) -> None:
        self.state = state
        self.input_frame.title = _TITLES[state]
        self._notify()

    def _invalidate(self) -> None:
        if self._app_running:
            self.app.invalidate()

    def _notify(self) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            if self._app_running:
                self.app.invalidate()
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(self._invalidate)

    def _push_line(self, line: str) -> None:
        """Loop-thread append of one output line into the workspace."""
        if self._closing:
            return
        self.buffer.append(line)
        self._invalidate()

    def _post(self, line: str) -> None:
        """Thread-safe append (worker threads, capture streams)."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(self._push_line, line)

    # ------------------------------------------------------------ input bar

    def _on_accept(self, buffer) -> bool:
        """Enter in the input bar: run a command, answer a confirmation, or
        do nothing while a command is still running (typed text is kept)."""
        text = buffer.text
        if self.state == CONFIRM:
            answer_queue = self._answer_q
            if answer_queue is not None:
                with contextlib.suppress(queue.Full):
                    answer_queue.put_nowait(text)
            return False
        if self.state != IDLE:
            return True  # keep the user's text; execution continues.
        raw = text.strip()
        if not raw:
            return False
        self._start_command(raw)
        return False

    def _start_command(self, raw: str) -> None:
        self.current_command = raw
        self._note = ""
        self._cancel_event.clear()
        self._set_state(RUNNING)
        self._task = asyncio.create_task(self._run_command(raw))

    def _on_sigint(self) -> None:
        if self.state == RUNNING:
            self._cancel_event.set()
            self._note = "cancel requested - waiting for the command to respond"
            self._notify()
        elif self.state == CONFIRM:
            answer_queue = self._answer_q
            if answer_queue is not None:
                with contextlib.suppress(queue.Full):
                    answer_queue.put_nowait(_INTERRUPT)
        elif self.state != EXITING:
            self._set_state(EXITING)
            self.app.exit(result=0)

    # ------------------------------------------------------------ execution

    async def _run_command(self, raw: str) -> None:
        loop = asyncio.get_running_loop()
        should_exit = False
        try:
            assert self._executor is not None
            should_exit = await loop.run_in_executor(self._executor, self._worker, raw)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            self._push_line(f"\x1b[91m✕ UI error\x1b[0m  {type(exc).__name__}: {exc}")
        self.commands_finished += 1
        if self._closing:
            return
        self.current_command = ""
        if should_exit:
            self._set_state(EXITING)
            self.app.exit(result=0)
        else:
            self._note = ""
            self._set_state(IDLE)

    def _worker(self, raw: str) -> bool:
        """Run one command on the worker thread.

        Handlers are synchronous, so they execute sequentially on a single
        worker thread - exactly the legacy execution order.  stdout/stderr are
        already redirected to the workspace for the whole UI lifetime; the
        builtins ``input`` is swapped only for the duration of the command so
        confirmation prompts flow through the input bar.
        """
        original_input = builtins.input
        builtins.input = self._fake_input
        try:
            return bool(asyncio.run(self.terminal.handle_input(raw)))
        except KeyboardInterrupt:
            self._post("\x1b[93m! Operation cancelled\x1b[0m")
            return False
        except BaseException as exc:
            self._post(f"\x1b[91m✕ Command failed\x1b[0m  {type(exc).__name__}: {exc}")
            return False
        finally:
            builtins.input = original_input
            answer_queue = self._answer_q
            if answer_queue is not None:
                self._answer_q = None
            if self.state == CONFIRM:
                self._set_state(RUNNING)

    def _fake_input(self, prompt=""):
        """Replacement for ``builtins.input`` while a handler runs.

        The prompt is shown in the workspace and the answer is taken from the
        persistent input bar, so confirmation flows (y/N prompts, setup,
        reset, submissions) work without leaving the screen.
        """
        if self._closing:
            raise EOFError("input stream closed")
        if prompt:
            self._post(str(prompt))
        answer_queue: queue.Queue = queue.Queue(maxsize=1)
        self._answer_q = answer_queue
        self._set_state(CONFIRM)
        # Block only the worker thread until the user answers (or the UI
        # shuts down); the timeout closes the race with _shutdown.
        while True:
            if self._closing:
                self._answer_q = None
                raise EOFError("input stream closed")
            try:
                token = answer_queue.get(timeout=0.2)
                break
            except queue.Empty:
                continue
        self._answer_q = None
        self._set_state(RUNNING)
        if token is _EOF:
            raise EOFError("input stream closed")
        if token is _INTERRUPT:
            raise KeyboardInterrupt
        self._post(str(token))
        return str(token)

    # ------------------------------------------------------------ lifecycle

    def _welcome(self) -> None:
        try:
            from . import config as CFG

            pack = CFG.load_config(self.home).pack
        except Exception:
            pack = "(not configured)"
        self._push_line("ALPHAS command center")
        self._push_line(
            f"pack {pack} · deterministic routing · type ? for the 13 slash commands · /exit quits"
        )
        self._push_line("")

    async def run(self) -> int:
        """Run the screen until /exit, Ctrl+C or EOF; always restores state."""
        self._loop = asyncio.get_running_loop()
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="alphapilot-command"
        )
        real_stdout, real_stderr = sys.stdout, sys.stderr
        original_console = self.terminal.console
        return_code = 1
        try:
            try:
                real_fileno = real_stdout.fileno()
            except (AttributeError, OSError, ValueError):
                real_fileno = None
            self._bridge = WorkspaceStream(self, fileno=real_fileno)
            sys.stdout = sys.stderr = self._bridge
            width = max(40, shutil.get_terminal_size().columns - 1)
            self._ws_width = width
            self._rich_console = Console(
                file=self._bridge,
                force_terminal=True,
                width=width,
                markup=True,
                highlighter=None,
                emoji=False,
            )
            self.terminal.console = self._rich_console
            self._welcome()
            self._app_running = True
            try:
                result = await self.app.run_async()
                return_code = 0 if result is None else int(result)
            finally:
                self._app_running = False
        except KeyboardInterrupt:
            return_code = 130
        except EOFError:
            return_code = 0
        finally:
            try:
                await self._shutdown()
            finally:
                # Streams and the console come back no matter how the UI
                # ended: /exit, Ctrl+C, error, or task cancellation.
                sys.stdout, sys.stderr = real_stdout, real_stderr
                self.terminal.console = original_console
                with contextlib.suppress(OSError):
                    os.chmod(self.home / "history", 0o600)
        return return_code

    async def _shutdown(self) -> None:
        # Keep capturing output while an active command unwinds so its final
        # messages (progress saved, cancelled, ...) still reach the workspace.
        if self.state == RUNNING:
            self._cancel_event.set()
        answer_queue = self._answer_q
        if answer_queue is not None:
            with contextlib.suppress(queue.Full):
                answer_queue.put_nowait(_EOF)
        task = self._task
        if task is not None and not task.done():
            with contextlib.suppress(Exception):
                await task
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None
        self._closing = True


def run(terminal, *, input=None, output=None) -> int:
    """Run the persistent full-screen UI for a CommandTerminal (blocking)."""
    return asyncio.run(_run(terminal, input=input, output=output))


async def _run(terminal, *, input=None, output=None) -> int:
    ui = AlphasUI(terminal, input=input, output=output)
    return await ui.run()
