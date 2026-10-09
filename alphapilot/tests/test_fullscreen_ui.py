"""Tests for the persistent full-screen ALPHAS UI.

Covers the three-region layout, dispatch integration through the real
deterministic dispatcher, context-aware help, confirmation prompts routed
through the input bar, input preservation while a command runs, workspace
scrolling that leaves the header/input in place, terminal resize, and stream
restoration on /exit, Ctrl+C and internal errors.
"""
import asyncio
import builtins
import contextlib
import io
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.layout import HSplit
from prompt_toolkit.layout.dimension import to_dimension
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from alphapilot import config as CFG
from alphapilot.agent_cli import CommandTerminal
from alphapilot.fullscreen import (
    CONFIRM,
    HEADER_HEIGHT,
    IDLE,
    RUNNING,
    TAGLINE,
    AlphasUI,
)

REQUIRED = {
    "/setup", "/run", "/candidates", "/status", "/fields", "/errors", "/retry",
    "/history", "/jump", "/settings", "/doctor", "/reset", "/exit",
}


class _SizedOutput(DummyOutput):
    """Dummy output with a mutable terminal size (used by the resize test)."""

    def __init__(self, rows=24, cols=80):
        self.size = Size(rows, cols)

    def get_size(self):
        return self.size


async def _wait_for(predicate, description, timeout=20.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {description}")
        await asyncio.sleep(0.01)


def _send_enter(pipe):
    pipe.send_bytes(b"\r")


def _send(pipe, text):
    pipe.send_text(text)
    _send_enter(pipe)


class FullscreenUiTests(unittest.IsolatedAsyncioTestCase):
    def _make_terminal(self, home):
        terminal = CommandTerminal(Path(home))
        terminal.console = Console(file=io.StringIO(), force_terminal=False)
        return terminal

    async def _start(self, terminal, pipe, output=None):
        ui = AlphasUI(terminal, input=pipe, output=output or _SizedOutput())
        task = asyncio.create_task(ui.run())
        self._task = task
        await _wait_for(lambda: ui._app_running, "the UI to start")
        return ui, task

    async def _command(self, pipe, ui, text, marker=None, timeout=20.0):
        """Send a command only when idle and wait for it to finish.

        Commands run on a worker thread, so tests must never race one command
        against the next: the UI would (correctly) hold the later input.
        """
        await _wait_for(lambda: ui.state == IDLE, "the UI to be idle", timeout=timeout)
        finished_before = ui.commands_finished
        lines_before = len(ui.buffer.lines)
        _send(pipe, text)
        if marker is not None:
            await _wait_for(lambda: marker in ui.buffer.plain_text(),
                            f"the output of {text!r}", timeout=timeout)
        await _wait_for(
            lambda: ui.commands_finished > finished_before and ui.state == IDLE,
            f"{text!r} to finish",
            timeout=timeout,
        )
        return len(ui.buffer.lines) - lines_before

    async def _stop(self, task, pipe):
        """Best-effort clean shutdown so a failing test never leaks a running
        UI (which would keep sys.stdout redirected for later tests)."""
        for _ in range(2):
            if task.done():
                break
            with contextlib.suppress(Exception):
                pipe.send_bytes(b"\x03")  # Ctrl+C exits when idle
            for _ in range(40):
                if task.done():
                    break
                await asyncio.sleep(0.05)
        if not task.done():
            with contextlib.suppress(Exception):
                _send(pipe, "/exit")
            for _ in range(60):
                if task.done():
                    break
                await asyncio.sleep(0.05)
        if not task.done():
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await asyncio.wait_for(task, 5)

    async def asyncTearDown(self):
        task = getattr(self, "_task", None)
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    # ------------------------------------------------------------ layout

    async def test_layout_has_three_persistent_regions(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            terminal = self._make_terminal(directory)
            ui = AlphasUI(terminal, input=pipe, output=_SizedOutput())

            self.assertIsInstance(ui.root, HSplit)
            children = ui.root.children
            self.assertEqual(len(children), 5)

            # Top region: fixed-height ALPHAS header.
            self.assertIs(children[0], ui.header_window)
            header_dim = to_dimension(ui.header_window.height)
            self.assertEqual(header_dim.min, HEADER_HEIGHT)
            self.assertEqual(header_dim.max, HEADER_HEIGHT)

            # Divider rule between header and workspace.
            self.assertIs(children[1], ui.rule_top)
            self.assertEqual(to_dimension(ui.rule_top.height).max, 1)

            # Middle region: the workspace absorbs all remaining space.
            self.assertIs(children[2], ui.workspace_window)
            self.assertIs(ui.workspace_window.content, ui.workspace_control)
            self.assertIsNone(ui.workspace_window.height)  # no fixed height

            # Bottom region: bordered input + one-line status.
            self.assertIs(children[3], ui.input_frame.container)
            self.assertIs(ui.input_frame.body, ui.textarea)
            self.assertEqual(ui.input_frame.title, "> Type a command...")
            self.assertEqual(to_dimension(children[4].height).max, 1)

            # The input bar is the focused region by default.
            self.assertIs(ui.app.layout.current_window, ui.textarea.window)

            # Header carries the ALPHAS branding with lavender styling.
            fragments = ui._header_text()
            header_text = "".join(text for _style, text in fragments)
            self.assertIn(TAGLINE, header_text)
            self.assertIn("ALPHAS", header_text)
            self.assertTrue(any(style.startswith("class:header")
                                for style, _text in fragments))

            # Status line shows context and shortcuts.
            status = ui._status_text()
            self.assertIn("main", status)
            self.assertIn("Enter: run", status)
            self.assertIn("?: help", status)
            self.assertIn("PgUp/PgDn", status)

    # ------------------------------------------------------------ help

    async def test_question_mark_help_lists_thirteen_commands_without_dispatch(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            terminal = self._make_terminal(directory)
            ui, task = await self._start(terminal, pipe)
            try:
                with patch("alphapilot.cli.main",
                           side_effect=AssertionError("help must not dispatch")):
                    added = await self._command(pipe, ui, "?", marker="Usage: /run")
                    plain = ui.buffer.plain_text()
                for command in REQUIRED:
                    self.assertIn(command, plain)
                self.assertNotIn("Command failed", plain)
                self.assertGreater(added, 5)
                # The workspace grew while every region stayed in place.
                self.assertIs(ui.root.children[0], ui.header_window)
                self.assertEqual(to_dimension(ui.header_window.height).max, HEADER_HEIGHT)
                self.assertEqual(to_dimension(ui.root.children[4].height).max, 1)
            finally:
                await self._stop(task, pipe)

    # ------------------------------------------------------------ dispatch

    async def test_command_dispatches_through_registry_and_streams_output(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            terminal = self._make_terminal(directory)
            original_console = terminal.console
            ui, task = await self._start(terminal, pipe)
            try:
                def handler(argv, **kwargs):
                    # Runs on the worker thread with stdout captured by the UI.
                    print("streamed-from-handler")
                    return 0

                with patch("alphapilot.cli.main", side_effect=handler) as mocked:
                    await self._command(pipe, ui, "/status",
                                        marker="streamed-from-handler")
                    self.assertEqual(mocked.call_count, 1)
                    argv = mocked.call_args.args[0]
                    self.assertEqual(argv[:2], ["--home", str(Path(directory))])
                    self.assertEqual(argv[2], "status")

                plain = ui.buffer.plain_text()
                self.assertIn("/status", plain)                  # echoed command
                self.assertIn("streamed-from-handler", plain)    # captured stdout
                # Header/input/status untouched while the workspace grew.
                self.assertIs(ui.root.children[0], ui.header_window)
                self.assertIsNot(terminal.console, original_console)  # output goes to the workspace
                self.assertEqual(ui.textarea.text, "")
                self.assertEqual(ui.input_frame.title, "> Type a command...")
            finally:
                await self._stop(task, pipe)

    async def test_nested_context_help_and_option_use_real_handlers(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            terminal = self._make_terminal(directory)
            ui, task = await self._start(terminal, pipe)
            try:
                await self._command(pipe, ui, "/settings", marker="/submit-mode")
                self.assertEqual(terminal.context, "settings")

                before = len(ui.buffer.lines)
                with patch("alphapilot.cli.main",
                           side_effect=AssertionError("context help must not dispatch")):
                    await self._command(pipe, ui, "?", marker="/metadata-mode")
                    plain = ui.buffer.plain_text()
                self.assertIn("/metadata-mode", plain)   # nested options listed
                self.assertNotIn("Command failed", plain)
                self.assertGreater(len(ui.buffer.lines), before + 5)  # help really re-printed

                # A nested option invokes its real (config) handler.
                await self._command(pipe, ui, "/submit-mode off", marker="Settings saved")
                cfg = CFG.load_config(Path(directory))
                self.assertEqual(cfg.submit.mode, "off")
                self.assertEqual(terminal.context, "settings")
            finally:
                await self._stop(task, pipe)

    # ------------------------------------------------------------ confirmations

    async def test_confirmation_prompt_is_answered_through_the_input_bar(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            terminal = self._make_terminal(directory)
            ui, task = await self._start(terminal, pipe)
            answers = []
            try:
                def handler(argv, **kwargs):
                    answers.append(input("Q? "))  # builtins.input is routed to the UI
                    return 0

                with patch("alphapilot.cli.main", side_effect=handler) as mocked:
                    await _wait_for(lambda: ui.state == IDLE, "the UI to be idle")
                    _send(pipe, "/doctor")
                    await _wait_for(lambda: ui.state == CONFIRM, "the confirmation prompt")
                    self.assertIn("confirmation", ui.input_frame.title)
                    self.assertIn("Q?", ui.buffer.plain_text())

                    _send(pipe, "y")
                    await _wait_for(lambda: ui.state == IDLE and answers,
                                    "the answer to be delivered")
                    self.assertEqual(mocked.call_count, 1)

                self.assertEqual(answers, ["y"])
                self.assertIn("y", ui.buffer.plain_text())  # the answer is echoed
                self.assertEqual(ui.input_frame.title, "> Type a command...")
            finally:
                await self._stop(task, pipe)

    # ------------------------------------------------------------ busy input

    async def test_input_is_preserved_and_not_executed_while_running(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            terminal = self._make_terminal(directory)
            ui, task = await self._start(terminal, pipe)
            started = threading.Event()
            release = threading.Event()
            calls = []

            def slow_handler(argv, **kwargs):
                calls.append(argv)
                started.set()
                release.wait(5)
                return 0

            try:
                with patch("alphapilot.cli.main", side_effect=slow_handler):
                    await _wait_for(lambda: ui.state == IDLE, "the UI to be idle")
                    _send(pipe, "/fields")
                    await _wait_for(started.is_set, "the command to start")
                    self.assertEqual(ui.state, RUNNING)
                    self.assertIn("input paused", ui.input_frame.title)

                    # Typing + Enter while running must neither re-dispatch
                    # nor lose the text being typed.
                    pipe.send_text("draft command")
                    await _wait_for(lambda: ui.textarea.text == "draft command",
                                    "the typed text")
                    _send_enter(pipe)
                    await asyncio.sleep(0.3)
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(ui.textarea.text, "draft command")
                    self.assertEqual(ui.state, RUNNING)

                    release.set()
                    await _wait_for(lambda: ui.state == IDLE, "the command to finish")

                # The preserved text executes exactly once now that we are idle.
                _send_enter(pipe)
                await _wait_for(lambda: "Commands must start with" in ui.buffer.plain_text(),
                                "the input validation message")
                self.assertEqual(len(calls), 1)
                self.assertEqual(ui.textarea.text, "")
            finally:
                release.set()
                await self._stop(task, pipe)

    # ------------------------------------------------------------ scrolling

    async def test_workspace_scrolls_without_moving_header_or_input(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            terminal = self._make_terminal(directory)
            ui = AlphasUI(terminal, input=pipe, output=_SizedOutput())
            for index in range(400):
                ui.buffer.append(f"line-{index:04d}")
            task = asyncio.create_task(ui.run())
            self._task = task
            try:
                await _wait_for(lambda: ui._app_running, "the UI to start")
                await _wait_for(lambda: ui.workspace_window.render_info is not None,
                                "the first render")
                # The welcome block is appended when the UI starts, so the
                # newest line is a few entries past our seeded 400.
                last = ui.buffer.last_index
                self.assertGreaterEqual(last, 399)
                self.assertTrue(ui.buffer.following)
                self.assertEqual(ui.buffer.anchor, last)

                pipe.send_bytes(b"\x1b[5~")  # PageUp
                await _wait_for(lambda: not ui.buffer.following, "scrolling up")
                self.assertLess(ui.buffer.anchor, last)

                # Regions are structurally fixed while the viewport moves.
                self.assertIs(ui.root.children[0], ui.header_window)
                self.assertEqual(to_dimension(ui.header_window.height).max, HEADER_HEIGHT)
                self.assertEqual(to_dimension(ui.root.children[4].height).max, 1)
                self.assertIs(ui.app.layout.current_window, ui.textarea.window)

                pipe.send_bytes(b"\x1b[6~")  # PageDown
                await _wait_for(
                    lambda: ui.buffer.following and ui.buffer.anchor == ui.buffer.last_index,
                    "scrolling back to the newest output",
                )
            finally:
                await self._stop(task, pipe)

    # ------------------------------------------------------------ resize

    async def test_terminal_resize_reflows_workspace_and_keeps_regions(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            terminal = self._make_terminal(directory)
            output = _SizedOutput(rows=24, cols=80)
            ui, task = await self._start(terminal, pipe, output=output)
            try:
                await _wait_for(lambda: ui.workspace_window.render_info is not None,
                                "the first render")
                await _wait_for(lambda: ui._ws_width > 0, "workspace width tracking")
                wide = ui._ws_width

                output.size = Size(24, 50)
                ui.app._on_resize()
                await _wait_for(lambda: ui._ws_width != wide, "the resized workspace width")

                self.assertLess(ui._ws_width, wide)
                self.assertEqual(ui._rich_console.width, ui._ws_width)
                # Fixed regions survive the resize.
                self.assertEqual(to_dimension(ui.header_window.height).max, HEADER_HEIGHT)
                self.assertEqual(to_dimension(ui.root.children[4].height).max, 1)
            finally:
                await self._stop(task, pipe)

    # ------------------------------------------------------------ lifecycle

    async def test_slash_exit_restores_terminal_streams(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            terminal = self._make_terminal(directory)
            original_out, original_err = sys.stdout, sys.stderr
            original_input = builtins.input
            original_console = terminal.console

            ui, task = await self._start(terminal, pipe)
            try:
                self.assertIsNot(sys.stdout, original_out)   # captured while running
                self.assertIsNot(terminal.console, original_console)

                await _wait_for(lambda: ui.state == IDLE, "the UI to be idle")
                _send(pipe, "/exit")
                return_code = await asyncio.wait_for(task, 8)
                self.assertEqual(return_code, 0)
            finally:
                await self._stop(task, pipe)

            self.assertIs(sys.stdout, original_out)
            self.assertIs(sys.stderr, original_err)
            self.assertIs(builtins.input, original_input)
            self.assertIs(terminal.console, original_console)

    async def test_ctrl_c_exits_and_restores_terminal_streams(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            terminal = self._make_terminal(directory)
            original_out, original_err = sys.stdout, sys.stderr
            original_input = builtins.input
            original_console = terminal.console

            ui, task = await self._start(terminal, pipe)
            try:
                pipe.send_bytes(b"\x03")
                return_code = await asyncio.wait_for(task, 8)
                self.assertEqual(return_code, 0)
            finally:
                await self._stop(task, pipe)

            self.assertIs(sys.stdout, original_out)
            self.assertIs(sys.stderr, original_err)
            self.assertIs(builtins.input, original_input)
            self.assertIs(terminal.console, original_console)

    async def test_internal_error_still_restores_terminal_streams(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            terminal = self._make_terminal(directory)
            original_out, original_err = sys.stdout, sys.stderr
            original_input = builtins.input
            original_console = terminal.console

            ui = AlphasUI(terminal, input=pipe, output=_SizedOutput())

            async def boom(*_args, **_kwargs):
                raise RuntimeError("renderer exploded")

            ui.app.run_async = boom
            with self.assertRaises(RuntimeError):
                await ui.run()

            self.assertIs(sys.stdout, original_out)
            self.assertIs(sys.stderr, original_err)
            self.assertIs(terminal.console, original_console)
            self.assertIs(builtins.input, original_input)

    # ------------------------------------------------------------ editing keys

    async def test_ctrl_j_inserts_newline_and_exit_ignores_leftover_text(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe:
            terminal = self._make_terminal(directory)
            ui, task = await self._start(terminal, pipe)
            try:
                pipe.send_text("ab")
                pipe.send_bytes(b"\n")  # Ctrl+J
                pipe.send_text("cd")
                await _wait_for(lambda: ui.textarea.text == "ab\ncd",
                                "the multiline draft")

                ui.textarea.text = ""  # clear the draft before exiting
                await _wait_for(lambda: ui.state == IDLE, "the UI to be idle")
                _send(pipe, "/exit")
                return_code = await asyncio.wait_for(task, 8)
                self.assertEqual(return_code, 0)
            finally:
                await self._stop(task, pipe)


if __name__ == "__main__":
    unittest.main()
