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
    "/candidates": ("Review eligible alphas by field; optionally check or submit.", "/candidates [--eligible] [--field FIELD] [--limit N] [--check|--submit] [thresholds]", "candidates"),
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
        ("/init", "Create or repair the local configuration.", "/setup /init", "setup"),
        ("/login", "Store BRAIN credentials using the existing secure prompt.", "/setup /login", "setup"),
        ("/doctor", "Run setup diagnostics.", "/setup /doctor", "setup"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "run": (
        ("/execute", "Run using the configured mode from the current checkpoint.", "/run --resume", "run"),
        ("/simulate", "Run simulation only.", "/run --simulate", "run"),
        ("/submit", "Run with the configured submission safeguards.", "/run --submit", "run"),
        ("/resume", "Resume from the existing checkpoint.", "/run --resume", "run"),
        ("/dry-run", "Simulate and preview submissions without sending them.", "/run --dry-run", "run"),
        ("/mode", "Choose configured, simulate, submit, or dry-run execution mode.", "/run /mode MODE", "run"),
        ("/focus", "Set a field/combo focus for this run.", "/run /focus FIELD[,FIELD...]", "run"),
        ("/stop-after", "Set the per-run submission limit.", "/run /stop-after N", "run"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "candidates": (
        ("/review", "Review eligible candidates using the normal checks.", "/candidates --eligible", "candidates"),
        ("/eligible", "List eligible candidates.", "/candidates --eligible", "candidates"),
        ("/submit", "Submit eligible candidates after the existing checks.", "/candidates --eligible --submit", "candidates"),
        ("/check", "Re-check candidate platform status and correlation.", "/candidates --check", "candidates"),
        ("/field", "Filter candidates to one field or combo.", "/candidates /field FIELD", "candidates"),
        ("/limit", "Set the maximum number of candidates displayed.", "/candidates /limit N", "candidates"),
        ("/min-sharpe", "Override the minimum Sharpe cutoff.", "/candidates /min-sharpe VALUE", "candidates"),
        ("/min-fitness", "Override the minimum Fitness cutoff.", "/candidates /min-fitness VALUE", "candidates"),
        ("/inspect", "Inspect a candidate by its displayed position.", "/candidates /inspect N", "candidates"),
        ("/fail", "Mark a candidate as a check failure.", "/candidates /fail N [REASON]", "candidates"),
        ("/manual-active", "Mark a candidate as submitted outside AlphaPilot.", "/candidates /manual-active N", "candidates"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "status": (("/back", "Return to the main command context.", "/back", "back"),),
    "fields": (
        ("/field", "Filter progress to one field or combo.", "/fields /field FIELD", "fields"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "errors": (
        ("/limit", "Limit the number of recent error rows displayed.", "/errors /limit N", "errors"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "retry": (
        ("/retry", "Retry all failed simulations using existing retry rules.", "/retry", "retry"),
        ("/dry-run", "Preview how many failures would be retried.", "/retry --dry-run", "retry"),
        ("/filter", "Retry only errors matching a case-insensitive substring.", "/retry /filter TEXT", "retry"),
        ("/reset-attempts", "Reset retry counters while retrying failures.", "/retry --reset-attempts", "retry"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "history": (("/back", "Return to the main command context.", "/back", "back"),),
    "jump": (
        ("/restore", "Restore skipped work to pending.", "/jump 0", "jump"),
        ("/position", "Skip to a validated 1-based alpha position.", "/jump /position N", "jump"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "settings": (
        ("/show", "Display current settings without revealing secrets.", "/settings --show", "settings"),
        ("/set", "Change a validated setting using key.path=value.", "/settings key.path=value", "settings"),
        ("/pack", "Choose the active dataset pack.", "/settings /pack PACK", "settings"),
        ("/submit-mode", "Set submit.mode to off, ask, auto, or dry.", "/settings /submit-mode off|dry|ask|auto", "settings"),
        ("/max-per-day", "Set the daily submission limit.", "/settings /max-per-day N", "settings"),
        ("/max-per-run", "Set the per-run submission limit.", "/settings /max-per-run N", "settings"),
        ("/polling", "Enable or disable submission polling output.", "/settings /polling on|off", "settings"),
        ("/focus", "Set saved field focus, or clear it.", "/settings /focus FIELD[,FIELD...]", "settings"),
        ("/provider", "Set the optional LLM provider (openrouter|mistral|openai|ollama|custom|template|none).", "/settings /provider PROVIDER", "settings"),
        ("/metadata-mode", "Set metadata mode to template or ai.", "/settings /metadata-mode template|ai", "settings"),
        ("/edit", "Open the existing config.yaml editing workflow.", "/settings /edit", "settings"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "doctor": (
        ("/check-model", "Check the optional AI metadata provider.", "/doctor --check-model", "doctor"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "reset": (
        ("/preview", "Show reset scope without changing progress.", "/reset --preview", "reset"),
        ("/confirm", "Clear local progress after confirmation.", "/reset", "reset"),
        ("/back", "Return to the main command context.", "/back", "back"),
    ),
    "exit": (),
}


def context_reference(context: str = "main", home: Path | None = None) -> str:
    """Render the active context from the same definitions used for dispatch."""
    if context == "main":
        return command_reference()
    title = context.replace("-", " ").title()
    lines = [title, "─" * max(12, len(title)), "", "Available options", ""]
    for name, description, usage, _route in CONTEXT_OPTIONS.get(context, ()):
        lines.extend((f"  {name:<12} {description}", f"               Usage: {usage}"))
    if home is not None and context in {"settings", "fields", "candidates", "run"}:
        try:
            from . import cli as _cli, config as _cfg, packs_api as _packs
            cfg = _cfg.load_config(home)
            pack = _packs.resolve_pack(cfg.pack, _cli._pack_dirs(Path(_cli.__file__).resolve(), home))
            if context in {"fields", "candidates", "run"}:
                lines.extend(("", "Available field values: " + ", ".join((*pack.field_ids(), "combo"))))
            if context == "settings":
                infos = _packs.list_pack_infos(_cli._pack_dirs(Path(_cli.__file__).resolve(), home))
                choices = [info.key for info in infos if not info.error and not info.shadowed_by]
                if choices:
                    lines.extend(("", "Available pack values: " + ", ".join(choices)))
        except Exception:
            pass
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


def _fullscreen_available() -> bool:
    """The persistent full-screen UI needs a real terminal; scripts, pipes
    and tests keep the legacy prompt loop."""
    flag = os.environ.get("ALPHAPILOT_FULLSCREEN", "").strip().lower()
    if flag in {"0", "off", "no", "false"}:
        return False
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, OSError, ValueError):
        return False


def main(home_arg=None):
    """Start the model-free interactive command shell.

    On a real terminal this is the persistent full-screen ALPHAS UI (fixed
    header, dynamic workspace, fixed input bar); otherwise it falls back to
    the plain prompt loop used by tests and piped sessions.
    """
    home = CFG.resolve_home(home_arg)
    terminal = CommandTerminal(home)
    try:
        if _fullscreen_available():
            from . import fullscreen

            return fullscreen.run(terminal)
        return asyncio.run(terminal.start())
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
        # When the full-screen UI drives this terminal it installs a cancel
        # token so Ctrl+C can stop long-running handlers that support it
        # (`/run`); None keeps the legacy one-shot invocation byte-identical.
        self.cancel_event = None
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
            self.console.print(context_reference(self.context, self.home), markup=False)
            return False
        try:
            argv = shlex.split(raw)
        except ValueError as exc:
            self.console.print(f"[red]Invalid command quoting:[/red] {exc}. Type ? for examples.")
            return False
        command = argv[0].lower() if argv else ""
        if len(argv) == 2 and argv[1] == "?" and command in self.SLASH:
            self.console.print(context_reference(self.SLASH[command][2], self.home), markup=False)
            return False
        if self.context != "main" and command == "/back":
            self.context = self.context_stack.pop() if self.context_stack else "main"
            self.console.print(context_reference(self.context, self.home), markup=False)
            return False
        if self.context != "main" and command in {name for name, *_ in CONTEXT_OPTIONS.get(self.context, ())}:
            option = next(item for item in CONTEXT_OPTIONS[self.context] if item[0] == command)
            _name, _description, usage, route = option
            if route == "back":
                self.context = self.context_stack.pop() if self.context_stack else "main"
                self.console.print(context_reference(self.context, self.home), markup=False)
                return False
            if self.context == "setup" and command == "/execute":
                from . import menu
                menu._quick_setup(self.home)
                return False
            if self.context == "run" and command == "/execute":
                return await self.execute("/run --resume")
            if self.context == "settings" and command == "/show":
                return self._settings(["--show"])
            if self.context == "reset" and command == "/confirm":
                return self._cli("reset", [])
            supplied = argv[1:]
            if self.context == "setup":
                if command == "/init":
                    return self._cli("init", supplied)
                if command == "/login":
                    return self._cli("login", supplied)
                if command == "/doctor":
                    return self._cli("doctor", supplied)
            if self.context == "run":
                if command == "/mode":
                    modes = {"simulate": "--simulate", "submit": "--submit", "dry-run": "--dry-run", "dry": "--dry-run"}
                    if not supplied or supplied[0] not in modes:
                        return self._missing_value(usage + " (MODE: simulate|submit|dry-run)")
                    return await self.execute("/run " + modes[supplied[0]])
                if command == "/focus":
                    return await self.execute("/run --focus " + " ".join(supplied)) if supplied else self._missing_value(usage)
                if command == "/stop-after":
                    return await self.execute("/run --stop-after " + " ".join(supplied)) if supplied else self._missing_value(usage)
            if self.context == "fields" and command == "/field":
                return self._cli("fields", ["--field", *supplied]) if supplied else self._missing_value(usage)
            if self.context == "errors" and command == "/limit":
                return self._cli("errors", ["--limit", *supplied]) if supplied else self._missing_value(usage)
            if self.context == "jump" and command == "/position":
                return await self.execute("/jump " + " ".join(supplied)) if supplied else self._missing_value(usage)
            if self.context == "retry":
                if command == "/filter":
                    return self._cli("retry-errors", ["--filter", *supplied]) if supplied else self._missing_value(usage)
                if command == "/reset-attempts":
                    return self._cli("retry-errors", ["--reset-attempts"])
            if self.context == "settings":
                setting_args = {
                    "/pack": "pack=",
                    "/submit-mode": "submit.mode=",
                    "/max-per-day": "submit.max_per_day=",
                    "/max-per-run": "submit.max_per_run=",
                    "/polling": "submit.show_polling=",
                    "/focus": "run.focus=",
                    "/provider": "llm.provider=",
                    "/metadata-mode": "llm.metadata_mode=",
                }
                if command in setting_args:
                    return self._settings([setting_args[command] + " ".join(supplied)]) if supplied else self._missing_value(usage)
                if command == "/edit":
                    return self._settings(["--edit"])
            if self.context == "candidates":
                flags = {
                    "/field": "--field", "/limit": "--limit", "/min-sharpe": "--min-sharpe",
                    "/min-fitness": "--min-fitness",
                }
                if command in flags:
                    return self._cli("candidates", [flags[command], *supplied]) if supplied else self._missing_value(usage)
                if command == "/check":
                    return self._cli("candidates", (["--check", "--candidate", supplied[0], "--candidate-action", "check"] if supplied else ["--check"]))
                if command == "/submit":
                    return self._cli("candidates", (["--eligible", "--submit", "--candidate", supplied[0], "--candidate-action", "submit"] if supplied else ["--eligible", "--submit"]))
                if command == "/eligible":
                    return self._cli("candidates", ["--eligible"])
                if command in ("/inspect", "/fail", "/manual-active"):
                    if not supplied:
                        return self._missing_value(usage)
                    action = {"/inspect": "inspect", "/fail": "fail", "/manual-active": "manual_active"}[command]
                    args = ["--eligible", "--candidate", supplied[0], "--candidate-action", action]
                    if command == "/fail" and len(supplied) > 1:
                        args.extend(("--reason", " ".join(supplied[1:])))
                    return self._cli("candidates", args)
            nested_args = shlex.split(usage)[1:]
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
        if not arguments and route in {"setup", "run", "candidates", "settings", "reset"}:
            self.console.print(context_reference(route, self.home), markup=False)
            return False
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
        argv = ["--home", str(self.home), command, *arguments]
        try:
            cancel_event = getattr(self, "cancel_event", None)
            if cancel_event is None:
                code = cli.main(argv)
            else:
                code = cli.main(argv, cancel_event=cancel_event)
        except SystemExit as exc:
            code = int(exc.code or 0)
        if code:
            self.console.print(f"[red]Command exited with status {code}.[/red]")
        return False

    def _missing_value(self, usage: str) -> bool:
        self.console.print(f"A value is required. Usage: {usage}\nType ? to see this context again.")
        return False

    def _run(self, arguments: list[str]) -> bool:
        return self._cli("run", arguments)

    def _settings(self, arguments: list[str]) -> bool:
        from . import config as C
        if arguments == ["--edit"]:
            self.console.print(f"Edit this file, then return to the CLI: {C.config_path(self.home)}")
            return False
        if arguments == ["--show"]:
            cfg = C.load_config(self.home)
            self.console.print(
                f"pack={cfg.pack}\n"
                f"simulation: pool_size={cfg.simulation.pool_size} batch_size={cfg.simulation.batch_size} "
                f"error_streak_halt={cfg.simulation.error_streak_halt}\n"
                f"submit: mode={cfg.submit.mode} max_per_day={cfg.submit.max_per_day} "
                f"max_per_run={cfg.submit.max_per_run} show_polling={cfg.submit.show_polling}\n"
                f"saved focus: {cfg['run'].get('focus') or '(none - whole pool)'}\n"
                f"llm: provider={cfg.llm.provider} metadata_mode={cfg.llm.metadata_mode} "
                f"model={cfg.llm.model or '(default)'}"
            )
            return False
        if not arguments:
            self.console.print(context_reference("settings", self.home), markup=False)
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
                    self.console.print(context_reference("jump", self.home), markup=False)
                    continue
                if answer != "y":
                    self.console.print("Cancelled; progress was not changed.")
                    return False
                break
        args = [str(parsed.n)] + [part for value in parsed.set for part in ("--set", value)]
        self._cli("jump", args)
        return False
