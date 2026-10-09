import asyncio
import io
import tempfile
import threading
import unittest
from pathlib import Path

from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from alphapilot.agent_cli import AgentTerminal, prompt_key_bindings


class AgentTerminalTests(unittest.IsolatedAsyncioTestCase):
    async def test_multiline_input_and_history_navigation(self):
        with create_pipe_input() as pipe:
            history = InMemoryHistory()
            session = PromptSession(multiline=True, history=history,
                                    key_bindings=prompt_key_bindings(), input=pipe,
                                    output=DummyOutput())
            first = asyncio.create_task(session.prompt_async())
            await asyncio.sleep(0.02)
            pipe.send_text("compare these")
            pipe.send_bytes(b"\n")  # Ctrl+J is newline in the prompt editor.
            pipe.send_text("rank(ts_rank(close,20))")
            pipe.send_bytes(b"\r")  # Enter sends.
            self.assertEqual(await asyncio.wait_for(first, 1), "compare these\nrank(ts_rank(close,20))")

            second = asyncio.create_task(session.prompt_async())
            await asyncio.sleep(0.02)
            pipe.send_bytes(b"\x1b[A")  # Up recalls the multiline submission.
            pipe.send_bytes(b"\r")
            self.assertEqual(await asyncio.wait_for(second, 1), "compare these\nrank(ts_rank(close,20))")

    async def test_interrupt_cleans_up_turn_and_returns_control(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal = object.__new__(AgentTerminal)
            terminal.home = Path(directory)
            terminal.active_task = None
            terminal.cancel_requested = False
            terminal._status = None
            terminal._stream_open = False
            output = io.StringIO()
            terminal.console = Console(file=output, force_terminal=False)

            class SlowAgent:
                cancel_event = threading.Event()

                async def run_turn(self, _prompt, _sink):
                    await asyncio.Event().wait()

            terminal.agent = SlowAgent()
            task = asyncio.create_task(terminal._turn("slow work"))
            await asyncio.sleep(0.02)
            terminal._interrupt()
            await asyncio.wait_for(task, 1)
            self.assertIsNone(terminal.active_task)
            self.assertIsNone(terminal._status)
            self.assertIn("Cancelled.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
