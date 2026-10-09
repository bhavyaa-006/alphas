"""Prompt-toolkit application shell for AlphaPilot's async agent."""
from __future__ import annotations

import asyncio
import os
import shlex
import signal
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from rich.console import Console

from . import config as CFG
from . import util


SLASH_COMMANDS = {
    "/setup": ("Initialize, authenticate, and run diagnostics.", "/setup", "setup"),
    "/run": ("Run or resume simulations and the configured submission workflow.", "/run [--resume] [--simulate|--submit|--dry-run] [options]", "run"),
    "/candidates": ("Review eligible alphas by field; optionally check or submit.", "/candidates [--eligible] [--field FIELD] [--check] [--submit]", "candidates"),
    "/status": ("Show current pool counts, top alphas, and common errors.", "/status", "status"),
    "/fields": ("Show progress by field, optionally filtered to one field.", "/fields [--field FIELD]", "fields"),
    "/errors": ("Show recent error records and grouped diagnostics.", "/errors [--limit N]", "errors"),
    "/retry": ("Reset failed simulations to pending using existing retry rules.", "/retry [--filter TEXT] [--reset-attempts] [--dry-run]", "retry"),
    "/history": ("Show actual alpha submission history.", "/history", "history"),
    "/jump": ("Skip earlier pending expressions or restore skipped expressions.", "/jump N  (N=0 restores skipped work)", "jump"),
    "/settings": ("Manage pack, simulation, submission, and AI provider settings.", "/settings [key.path=value]", "settings"),
    "/doctor": ("Check authentication, pack fields, operators, and one smoke simulation.", "/doctor [--check-model]", "doctor"),
    "/reset": ("Clear local simulation progress while retaining submitted records and history.", "/reset [--yes]", "reset"),
    "/exit": ("Exit the interactive CLI cleanly.", "/exit", "exit"),
}
COMMANDS = {name: details[0] for name, details in SLASH_COMMANDS.items()}

# Context options are deliberately separate from the top-level registry.  They
# are only accepted while their parent context is active and therefore never
# become additional global slash commands.
CONTEXT_OPTIONS = {
    "main": (),
    "setup": (
        ("/execute", "Run initialization, login, and diagnostics.", "/setup", "setup"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "run": (
        ("/simulate", "Run simulation only.", "/run --simulate", "run"),
        ("/submit", "Run with the configured submission safeguards.", "/run --submit", "run"),
        ("/resume", "Resume from the existing checkpoint.", "/run --resume", "run"),
        ("/dry-run", "Simulate and preview submissions without sending them.", "/run --dry-run", "run"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "candidates": (
        ("/review", "Review candidates using the normal eligibility rules.", "/candidates", "candidates"),
        ("/eligible", "List eligible candidates.", "/candidates --eligible", "candidates"),
        ("/submit", "Submit eligible candidates after the existing checks.", "/candidates --eligible --submit", "candidates"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "status": (("/back", "Return to the main command context.", "/back", "back"),),
    "fields": (("/back", "Return to the main command context.", "/back", "back"),),
    "errors": (("/back", "Return to the main command context.", "/back", "back"),),
    "retry": (
        ("/retry", "Retry all failed simulations using existing retry rules.", "/retry", "retry"),
        ("/dry-run", "Preview how many failures would be retried.", "/retry --dry-run", "retry"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "history": (("/back", "Return to the main command context.", "/back", "back"),),
    "jump": (
        ("/restore", "Restore skipped work to pending.", "/jump 0", "jump"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "settings": (
        ("/show", "Display current settings without revealing secrets.", "/settings", "settings"),
        ("/set", "Change a validated setting using key.path=value.", "/settings key.path=value", "settings"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "doctor": (("/back", "Return to the main command context.", "/back", "back"),),
    "reset": (
        ("/preview", "Show reset scope without changing progress.", "/reset --preview", "reset"),
        ("/confirm", "Clear local progress after confirmation.", "/reset", "reset"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "exit": (),
}


def context_reference(context: str = "main") -> str:
    """Render the active context from the same definitions used for dispatch."""
    if context == "main":
        return command_reference()
    title = context.replace("-", " ").title()
    lines = [title, "─" * max(12, len(title)), "", "Available options", ""]
    for name, description, usage, _route in CONTEXT_OPTIONS.get(context, ()):
        lines.extend((f"  {name:<12} {description}", f"               Usage: {usage}"))
    lines.extend(("", "Type ? to show these options. Type /back to return to the main context."))
    return "\n".join(lines)


def command_reference() -> str:
    lines = ["AlphaPilot commands", ""]
    for number, (name, (description, usage, _route)) in enumerate(SLASH_COMMANDS.items(), 1):
        lines.extend((f"{number:>2}. {name}", f"    {description}", f"    Usage: {usage}"))
    lines.extend(("", "Type ? or / to show this list. Arguments follow the command on the same line."))
    return "\n".join(lines)


def prompt_key_bindings():
    bindings = KeyBindings()

    @bindings.add("enter")
    def _(event):
        event.current_buffer.append_to_history()
        event.app.exit(result=event.current_buffer.text)

    @bindings.add("c-j")
    def _(event):
        event.current_buffer.insert_text("\n")

    @bindings.add("escape", "enter")
    def _(event):
        event.current_buffer.append_to_history()
        event.app.exit(result=event.current_buffer.text)

    @bindings.add("c-c")
    def _(event):
        raise KeyboardInterrupt

    return bindings


class AgentTerminal:
    def __init__(self, home: Path):
        self.home = Path(home)
        self.console = Console()
        self.history_file = self.home / "history"
        self.history = FileHistory(str(self.history_file))
        try:
            os.chmod(self.history_file, 0o600)
        except OSError:
            pass
        self.last_prompt = ""
        self.agent = None
        self.command_terminal = None
        self.active_task = None
        self.prompt_task = None
        self.cancel_requested = False
        self._status = None
        self._stream_open = False
        self.session = PromptSession(
            multiline=True, history=self.history, key_bindings=prompt_key_bindings(),
            completer=WordCompleter(list(COMMANDS), sentence=True), complete_while_typing=True,
            style=Style.from_dict({"prompt": "bold #7ab8ff", "bottom-toolbar": "#888888"}),
            bottom_toolbar=self._toolbar,
            enable_suspend=True,
        )

    def _toolbar(self):
        return "Enter: send  |  Ctrl+J: newline  |  ?: command reference  |  Ctrl+C: cancel/exit"

    async def start(self):
        CFG.resolve_home(self.home)
        self.home.mkdir(parents=True, exist_ok=True)
        util.load_dotenv(self.home / ".env")
        try:
            from .agent import AgentError, AlphaAgent
        except ImportError as exc:
            cfg = CFG.load_config(self.home)
            model = f"{cfg.llm.provider} (not ready)"
            self._agent_error = f"Optional chat dependencies are missing. Install with `pip install 'alphapilot[ai]'`. {exc}"
        else:
            try:
                cfg = CFG.load_config(self.home)
                self.agent = AlphaAgent(self.home, cfg)
                model = f"{cfg.llm.provider}/{self.agent.client.provider.get('model', '')}"
            except AgentError as exc:
                cfg = CFG.load_config(self.home)
                model = f"{cfg.llm.provider} (not ready)"
                self._agent_error = str(exc)
        self.console.print("[bold]ALPHAPILOT[/bold]  [dim]WorldQuant BRAIN research agent[/dim]")
        self.console.print(f"[dim]Pack: {cfg.pack}  |  Model: {model}[/dim]")
        if getattr(self, "_agent_error", None):
            self.console.print(f"[yellow]Agent setup: {self._agent_error}[/yellow]")
        self.console.print("[dim]Ask about your alpha pack or request a bounded simulation. Type ? for the 13 CLI commands.[/dim]\n")

        loop = asyncio.get_running_loop()
        old_handler = None
        loop_signal_handler = False
        if hasattr(loop, "add_signal_handler") and sys.platform != "win32":
            try:
                old_handler = signal.getsignal(signal.SIGINT)
                loop.add_signal_handler(signal.SIGINT, self._interrupt)
                loop_signal_handler = True
            except (NotImplementedError, RuntimeError, ValueError):
                try:
                    signal.signal(signal.SIGINT, lambda *_: loop.call_soon_threadsafe(self._interrupt))
                except (ValueError, OSError):
                    old_handler = None
        elif sys.platform == "win32":
            try:
                old_handler = signal.getsignal(signal.SIGINT)
                signal.signal(signal.SIGINT, lambda *_: loop.call_soon_threadsafe(self._interrupt))
            except (ValueError, OSError):
                old_handler = None
        try:
            while True:
                try:
                    self.prompt_task = asyncio.create_task(self.session.prompt_async([("class:prompt", "› ")]))
                    prompt = await self.prompt_task
                    self.prompt_task = None
                    try:
                        os.chmod(self.history_file, 0o600)
                    except OSError:
                        pass
                except KeyboardInterrupt:
                    self.console.print("\n[dim]Bye.[/dim]")
                    return 0
                except asyncio.CancelledError:
                    self.console.print("\n[dim]Bye.[/dim]")
                    return 0
                except EOFError:
                    self.console.print("\n[dim]Bye.[/dim]")
                    return 0
                prompt = prompt.strip()
                if not prompt:
                    continue
                if prompt.startswith("/") or prompt == "?":
                    command_task = asyncio.create_task(self._command(prompt))
                    self.active_task = command_task
                    try:
                        if await command_task:
                            return 0
                    except asyncio.CancelledError:
                        self.console.print("\n[dim]Cancelled.[/dim]")
                    except Exception as exc:
                        self.console.print(f"[red]✕ Command failed[/red]  {type(exc).__name__}: {exc}")
                    finally:
                        if self.active_task is command_task:
                            self.active_task = None
                    continue
                self.last_prompt = prompt
                if self.agent is None:
                    self.console.print(f"[red]✕ {self._agent_error}[/red]\n")
                    continue
                turn = asyncio.create_task(self._turn(prompt))
                self.active_task = turn
                try:
                    await turn
                finally:
                    if self.active_task is turn:
                        self.active_task = None
        finally:
            if old_handler is not None:
                try:
                    if loop_signal_handler:
                        loop.remove_signal_handler(signal.SIGINT)
                except (NotImplementedError, RuntimeError, ValueError, OSError):
                    pass
                try:
                    signal.signal(signal.SIGINT, old_handler)
                except (ValueError, OSError):
                    pass
            self.prompt_task = None
            self._finish_stream()

    def _interrupt(self):
        self.cancel_requested = True
        if self.agent is not None:
            self.agent.cancel_event.set()
        if self.active_task is not None and not self.active_task.done():
            self.console.print("[yellow]Cancelling active operation…[/yellow]")
            self.active_task.cancel()
        elif self.prompt_task is not None and not self.prompt_task.done():
            self.prompt_task.cancel()

    async def _turn(self, prompt: str):
        from .agent import AgentError
        self.cancel_requested = False
        if self.active_task is None:
            self.active_task = asyncio.current_task()
        self._status = self.console.status("[cyan]Thinking[/cyan]", spinner="dots")
        self._status.start()
        try:
            await self.agent.run_turn(prompt, self._event)
        except asyncio.CancelledError:
            self.agent.cancel_event.set()
            self.console.print("\n[dim]Cancelled.[/dim]")
        except AgentError as exc:
            self.console.print(f"\n[red]✕ Agent request failed[/red]\n  {exc}\n")
        except Exception as exc:
            self.console.print(f"\n[red]✕ Operation failed[/red]\n  {type(exc).__name__}: {exc}\n")
        finally:
            self._finish_stream()
            if self.active_task is asyncio.current_task():
                self.active_task = None
            self.console.print()

    async def _event(self, event: AgentEvent):
        if event.kind == "state":
            state = event.data.get("state")
            if state in ("thinking", "retrying"):
                if self._status is None:
                    self._status = self.console.status(f"[cyan]{event.text}[/cyan]", spinner="dots")
                    self._status.start()
            elif state in ("completed", "failed", "cancelled"):
                self._stop_status()
            return
        if event.kind == "text":
            self._stop_status()
            self.console.print(event.text, end="", soft_wrap=True, highlight=False, markup=False)
            self._stream_open = True
            return
        if event.kind == "tool_start":
            self._finish_stream()
            self.console.print(f"[cyan]→[/cyan] {event.text}")
            self._status = self.console.status(f"[cyan]{event.text}[/cyan]", spinner="dots")
            self._status.start()
            return
        if event.kind == "tool_progress":
            self.console.print(f"[dim]{event.text}[/dim]", soft_wrap=True)
            return
        if event.kind == "tool_end":
            self._stop_status()
            marker = "✓" if event.data.get("ok") else "✕"
            style = "green" if event.data.get("ok") else "red"
            self.console.print(f"[{style}]{marker}[/{style}] {event.text}")

    def _stop_status(self):
        if self._status is not None:
            self._status.stop()
            self._status = None

    def _finish_stream(self):
        self._stop_status()
        if self._stream_open:
            self.console.print()
            self._stream_open = False

    async def _command(self, raw: str) -> bool:
        if self.command_terminal is None:
            self.command_terminal = CommandTerminal(self.home)
            self.command_terminal.console = self.console
        return await self.command_terminal.execute(raw)


def main(home_arg=None):
    """Start the model-free interactive command shell."""
    home = CFG.resolve_home(home_arg)
    try:
        return asyncio.run(CommandTerminal(home).start())
    except KeyboardInterrupt:
        print("\nBye.")
        return 0


def chat_main(home_arg=None):
    """Start the optional natural-language chat interface."""
    home = CFG.resolve_home(home_arg)
    try:
        return asyncio.run(AgentTerminal(home).start())
    except KeyboardInterrupt:
        print("\nBye.")
        return 0


class CommandTerminal:
    """Modern prompt-toolkit UI with a fixed slash registry and deterministic handlers."""

    SLASH = SLASH_COMMANDS

    def __init__(self, home: Path):
        self.home = Path(home)
        self.console = Console()
        self.context = "main"
        self.context_stack = []
        self.history_file = self.home / "history"
        self.home.mkdir(parents=True, exist_ok=True)
        self.session = PromptSession(
            multiline=True, history=FileHistory(str(self.history_file)),
            key_bindings=prompt_key_bindings(),
            completer=WordCompleter([*self.SLASH, "?"], sentence=True), complete_while_typing=True,
            style=Style.from_dict({"prompt": "bold #7ab8ff", "bottom-toolbar": "#888888"}),
            bottom_toolbar=lambda: "Enter: run command  |  Ctrl+J: newline  |  ?: command reference  |  Ctrl+C: exit",
        )

    async def start(self):
        from .cli import build_parser
        cfg = CFG.load_config(self.home)
        self.console.print("[bold]ALPHAPILOT[/bold]  [dim]WorldQuant BRAIN command center[/dim]")
        self.console.print(f"[dim]Pack: {cfg.pack}  |  Deterministic command routing[/dim]")
        self.console.print("[dim]Use one of the 13 slash commands. Type ? or / for the command reference.[/dim]\n")
        while True:
            try:
                raw = (await self.session.prompt_async([("class:prompt", "› ")])).strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[dim]Bye.[/dim]")
                return 0
            if not raw:
                continue
            if await self.handle_input(raw):
                return 0

    async def handle_input(self, raw: str) -> bool:
        if raw == "?" or raw == "/" or raw.startswith("/"):
            return await self.execute(raw)
        self.console.print("[yellow]Commands must start with /. Type ? to see available commands.[/yellow]")
        return False

    async def execute(self, raw: str) -> bool:
        if raw == "/":
            self.console.print(command_reference(), markup=False)
            return False
        if raw == "?":
            self.console.print(context_reference(self.context), markup=False)
            return False
        try:
            argv = shlex.split(raw)
        except ValueError as exc:
            self.console.print(f"[red]Invalid command quoting:[/red] {exc}. Type ? for examples.")
            return False
        command = argv[0].lower() if argv else ""
        if len(argv) == 2 and argv[1] == "?" and command in self.SLASH:
            self.console.print(context_reference(self.SLASH[command][2]), markup=False)
            return False
        if self.context != "main" and command == "/back":
            self.context = self.context_stack.pop() if self.context_stack else "main"
            self.console.print(context_reference(self.context), markup=False)
            return False
        if self.context != "main" and command in {name for name, *_ in CONTEXT_OPTIONS.get(self.context, ())}:
            option = next(item for item in CONTEXT_OPTIONS[self.context] if item[0] == command)
            _name, _description, usage, route = option
            if route == "back":
                self.context = self.context_stack.pop() if self.context_stack else "main"
                self.console.print(context_reference(self.context), markup=False)
                return False
            nested_args = shlex.split(usage)[1:]
            if route == "setup":
                return await self.execute("/setup")
            return await self.execute("/" + route + (" " + " ".join(nested_args) if nested_args else ""))
        if command not in self.SLASH:
            self.console.print(f"[yellow]Unknown command {command!r}. Type ? for the 13 supported commands.[/yellow]")
            return False
        route = self.SLASH[command][2]
        arguments = argv[1:]
        if route == "exit":
            if arguments:
                self.console.print("/exit takes no arguments.")
                return False
            self.console.print("Bye.")
            return True
        # Keep the most recently executed command as the active context.  This
        # makes a subsequent bare `?` contextual while preserving direct CLI
        # invocation semantics for the command itself.
        self.context_stack = ["main"]
        self.context = route
        self.console.print(f"[cyan]›[/cyan] {raw}")
        try:
            if route == "setup":
                if arguments:
                    self.console.print("Usage: /setup")
                    return False
                from . import menu
                menu._quick_setup(self.home)
                return False
            if route == "settings":
                return self._settings(arguments)
            if route == "jump":
                return self._jump(arguments)
            target = {"history": "submissions", "retry": "retry-errors"}.get(route, route)
            if route == "run":
                return self._run(arguments)
            return self._cli(target, arguments)
        except Exception as exc:
            self.console.print(f"[red]✕ Command failed[/red] {type(exc).__name__}: {exc}")
            return False

    def _cli(self, command: str, arguments: list[str]) -> bool:
        from . import cli
        try:
            code = cli.main(["--home", str(self.home), command, *arguments])
        except SystemExit as exc:
            code = int(exc.code or 0)
        if code:
            self.console.print(f"[red]Command exited with status {code}.[/red]")
        return False

    def _run(self, arguments: list[str]) -> bool:
        return self._cli("run", arguments)

    def _settings(self, arguments: list[str]) -> bool:
        from . import config as C
        if not arguments:
            from . import menu
            menu._settings_screen(self.home)
            return False
        cfg = dict(C.load_config(self.home))
        try:
            override = C.parse_overrides(arguments)
        except C.ConfigError as exc:
            self.console.print(str(exc))
            return False
        updated = C.deep_merge(cfg, override)
        problems = C.validate(updated)
        if problems:
            self.console.print("Invalid settings:\n" + "\n".join(f"  - {p}" for p in problems))
            return False
        C.save_file_config(self.home, updated)
        self.console.print("Settings saved. Secrets are read from the environment or .env and are not displayed.")
        return False

    def _jump(self, arguments: list[str]) -> bool:
        import argparse
        from . import cli, config as C, state as ST
        parser = argparse.ArgumentParser(prog="/jump", add_help=False)
        parser.add_argument("n", type=int)
        parser.add_argument("--yes", action="store_true")
        parser.add_argument("--set", action="append", default=[])
        try:
            parsed = parser.parse_args(arguments)
        except SystemExit:
            return False
        if parsed.n < 0:
            self.console.print("Position must be 0 or greater.")
            return False
        cfg = C.load_config(self.home, parsed.set)
        db = cli._state_db_for(self.home, cfg)
        store = ST.Store(db)
        try:
            pack, _pool, _info = cli._ensure_pool(self.home, cfg, store)
            total = store.pool_size()
            if parsed.n > total:
                self.console.print(f"Pool has {total} positions; requested position {parsed.n} is out of range.")
                return False
            if parsed.n == 0:
                affected = store.conn.execute("SELECT COUNT(*) FROM alphas WHERE status='skipped'").fetchone()[0]
                action = f"restore {affected} skipped expression(s) to pending"
            else:
                affected = store.conn.execute(
                    "SELECT COUNT(*) FROM alphas WHERE idx < ? AND status='pending'", (parsed.n - 1,)
                ).fetchone()[0]
                action = f"skip {affected} still-pending expression(s) before position {parsed.n}"
        finally:
            store.close()
        self.console.print(f"Pack {pack.name!r}: {action}. Simulated, errored, and submitted rows remain untouched.")
        if not parsed.yes:
            while True:
                answer = input("Proceed? [y/N] ").strip().lower()
                if answer == "?":
                    self.console.print(context_reference("jump"), markup=False)
                    continue
                if answer != "y":
                    self.console.print("Cancelled; progress was not changed.")
                    return False
                break
        args = [str(parsed.n)] + [part for value in parsed.set for part in ("--set", value)]
        self._cli("jump", args)
        return False
