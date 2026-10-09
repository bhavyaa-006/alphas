import contextlib
import io
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from alphapilot import cli, state
from alphapilot.agent_cli import AgentTerminal, CommandTerminal, CONTEXT_OPTIONS, SLASH_COMMANDS, command_reference, context_reference
from alphapilot.terminal import COMMANDS as READLINE_COMMANDS


REQUIRED = {
    "/setup", "/run", "/candidates", "/status", "/fields", "/errors", "/retry",
    "/history", "/jump", "/settings", "/doctor", "/reset", "/exit",
}


class SlashRegistryTests(unittest.IsolatedAsyncioTestCase):
    def terminal(self, home):
        terminal = CommandTerminal(home)
        output = io.StringIO()
        terminal.console = Console(file=output, force_terminal=False)
        return terminal, output

    async def test_exactly_thirteen_slash_commands_are_shared_everywhere(self):
        self.assertEqual(set(SLASH_COMMANDS), REQUIRED)
        self.assertEqual(len(SLASH_COMMANDS), 13)
        self.assertEqual(set(AgentTerminal.__init__.__globals__["COMMANDS"]), REQUIRED)
        self.assertEqual(set(READLINE_COMMANDS), REQUIRED)
        self.assertNotIn("/", SLASH_COMMANDS)
        self.assertNotIn("?", SLASH_COMMANDS)

    async def test_question_mark_and_slash_repeat_registry_help_without_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal, output = self.terminal(Path(directory))
            with patch("alphapilot.cli.main", side_effect=AssertionError("help must not dispatch")):
                self.assertFalse(await terminal.execute("?"))
                self.assertFalse(await terminal.execute("/"))
                self.assertFalse(await terminal.execute("?"))
            rendered = output.getvalue()
            for command in REQUIRED:
                self.assertIn(command, rendered)
            self.assertIn("Usage: /run", rendered)
            self.assertEqual(rendered.count("/setup"), 6)

    async def test_unknown_slashes_and_ordinary_text_do_not_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal, output = self.terminal(Path(directory))
            with patch("alphapilot.cli.main", side_effect=AssertionError("unknown input must not dispatch")):
                self.assertFalse(await terminal.execute("/help"))
                await terminal.handle_input("just text")
            self.assertIn("Unknown command", output.getvalue())

    async def test_all_handler_routes_use_existing_cli_or_menu_handlers(self):
        routes = {
            "/run --resume": "run",
            "/run --simulate": "run",
            "/run --submit": "run",
            "/run --dry-run": "run",
            "/candidates --eligible": "candidates",
            "/status": "status",
            "/fields --field x": "fields",
            "/errors --limit 3": "errors",
            "/retry --dry-run": "retry-errors",
            "/history": "submissions",
            "/doctor": "doctor",
            "/reset --yes": "reset",
        }
        with tempfile.TemporaryDirectory() as directory:
            terminal, _ = self.terminal(Path(directory))
            for command, target in routes.items():
                with self.subTest(command=command), patch("alphapilot.cli.main", return_value=0) as handler:
                    self.assertFalse(await terminal.execute(command))
                    called = handler.call_args.args[0]
                    self.assertEqual(called[2], target)
            await terminal.execute("/setup")
            self.assertEqual(terminal.context, "setup")
            await terminal.execute("/settings")
            self.assertEqual(terminal.context, "settings")

    async def test_jump_shows_effect_and_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal, output = self.terminal(Path(directory))
            fake_store = unittest.mock.MagicMock()
            fake_store.pool_size.return_value = 8
            fake_store.conn.execute.return_value.fetchone.return_value = (3,)
            pack = type("Pack", (), {"name": "demo"})()
            with patch("alphapilot.cli._state_db_for", return_value=Path(directory) / "state.db"), \
                    patch("alphapilot.cli._ensure_pool", return_value=(pack, {}, {})), \
                    patch("alphapilot.state.Store", return_value=fake_store), \
                    patch("builtins.input", return_value="n") as confirm, \
                    patch.object(terminal, "_cli") as jump:
                await terminal.execute("/jump 5")
            confirm.assert_called_once()
            jump.assert_not_called()
            self.assertIn("skip 3 still-pending", output.getvalue())

    async def test_exit_is_clean_and_rejects_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal, output = self.terminal(Path(directory))
            self.assertFalse(await terminal.execute("/exit now"))
            self.assertTrue(await terminal.execute("/exit"))
            self.assertIn("takes no arguments", output.getvalue())

    async def test_cli_registry_validates_command_arguments(self):
        run_args = cli.build_parser().parse_args(["run", "--resume", "--simulate", "--focus", "field_x"])
        self.assertIs(run_args.func, cli.cmd_run)
        self.assertTrue(run_args.resume)
        self.assertEqual(run_args.run_mode, "simulate")
        self.assertEqual(run_args.focus, "field_x")
        candidate_args = cli.build_parser().parse_args(["candidates", "--eligible", "--field", "field_x", "--submit"])
        self.assertTrue(candidate_args.eligible)
        self.assertTrue(candidate_args.submit)
        self.assertEqual(candidate_args.field, "field_x")
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["run", "--simulate", "--dry-run"])
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["fields", "--field"])

    async def test_settings_argument_updates_only_validated_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal, output = self.terminal(Path(directory))
            await terminal.execute("/settings llm.provider=openai")
            from alphapilot import config
            cfg = config.load_config(Path(directory))
            self.assertEqual(cfg.llm.provider, "openai")
            previous = (Path(directory) / "config.yaml").read_text(encoding="utf-8")
            await terminal.execute("/settings llm.provider=not-a-provider")
            self.assertEqual((Path(directory) / "config.yaml").read_text(encoding="utf-8"), previous)
            self.assertIn("Invalid settings", output.getvalue())

    async def test_help_is_available_immediately_at_shell_start(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal, output = self.terminal(Path(directory))

            class Prompts:
                def __init__(self):
                    self.values = iter(("?", "/exit"))

                async def prompt_async(self, *_args):
                    return next(self.values)

            terminal.session = Prompts()
            with patch("alphapilot.cli.main", side_effect=AssertionError("startup help cannot dispatch")):
                await terminal.start()
            for command in REQUIRED:
                self.assertIn(command, output.getvalue())

    async def test_each_context_has_registry_driven_help_and_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal, output = self.terminal(Path(directory))
            for context in REQUIRED - {"/exit"}:
                route = SLASH_COMMANDS[context][2]
                self.assertIn(route, CONTEXT_OPTIONS)
                rendered = context_reference(route)
                self.assertIn(route.title(), rendered)
                for option, description, usage, _route in CONTEXT_OPTIONS[route]:
                    self.assertIn(option, rendered)
                    self.assertIn(description, rendered)
                    self.assertTrue(usage.startswith("/"))

            with patch("alphapilot.cli.main", return_value=0) as handler:
                await terminal.execute("/run")
                self.assertEqual(terminal.context, "run")
                await terminal.execute("?")
                self.assertIn("/simulate", output.getvalue())
                await terminal.execute("/simulate")
                self.assertEqual(handler.call_args.args[0][2:4], ["run", "--simulate"])
                await terminal.execute("/back")
                self.assertEqual(terminal.context, "main")

    async def test_nested_help_does_not_dispatch_or_change_context(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal, output = self.terminal(Path(directory))
            with patch("alphapilot.cli.main", side_effect=AssertionError("context help must not dispatch")):
                await terminal.execute("/settings ?")
            self.assertEqual(terminal.context, "main")
            self.assertIn("Settings", output.getvalue())

    async def test_nested_option_uses_real_settings_handler(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal, output = self.terminal(Path(directory))
            await terminal.execute("/settings")
            await terminal.execute("/set llm.provider=template")
            from alphapilot import config
            self.assertEqual(config.load_config(Path(directory)).llm.provider, "template")
            self.assertIn("Settings saved", output.getvalue())


class ResetProtectionTests(unittest.TestCase):
    def test_reset_retains_submitted_rows_submission_history_and_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            config_path = home / "config.yaml"
            credentials_path = home / ".env"
            config_path.write_text("pack: oth176_jpn\n", encoding="utf-8")
            credentials_path.write_text("BRAIN_CREDENTIAL_PASSWORD=secret\n", encoding="utf-8")
            db = cli._state_db_path(home, "oth176_jpn")
            store = state.Store(db)
            store.conn.execute("INSERT INTO alphas(expr,status,attempts) VALUES ('pending-x','pending',0)")
            store.conn.execute("INSERT INTO alphas(expr,status,alpha_id,attempts) VALUES ('submitted-x','submitted','a1',1)")
            store.conn.execute(
                "INSERT INTO submissions(alpha_id,expr,submitted_at,day,name,category,description_source) "
                "VALUES ('a1','submitted-x','2026-01-01','2026-01-01','name','PRICE_MOMENTUM','template')"
            )
            store.conn.commit()
            store.close()

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.cmd_reset(Namespace(home=str(home), set=[], yes=True)), 0)

            store = state.Store(db)
            try:
                self.assertEqual(store.counts().get("submitted"), 1)
                self.assertEqual(len(store.submissions_list()), 1)
                self.assertEqual(store.conn.execute("SELECT COUNT(*) FROM alphas WHERE status='pending'").fetchone()[0], 0)
            finally:
                store.close()
            self.assertEqual(config_path.read_text(encoding="utf-8"), "pack: oth176_jpn\n")
            self.assertIn("secret", credentials_path.read_text(encoding="utf-8"))


class NumberedMenuCompatibilityTests(unittest.TestCase):
    def test_original_menu_choices_still_route_to_their_handlers(self):
        from alphapilot import menu
        choices = ["setup", "run", "candidates", "status", "fields", "errors", "retry",
                   "submissions", "jump", "settings", "doctor", "reset", "exit"]
        with tempfile.TemporaryDirectory() as directory:
            patches = [
                patch.object(menu, "_quick_setup"), patch.object(menu, "_run_screen"),
                patch.object(menu, "_candidates_screen"), patch.object(menu, "_status_screen"),
                patch.object(menu, "_fields_screen"), patch.object(menu, "_errors_screen"),
                patch.object(menu, "_retry_screen"), patch.object(menu, "_submissions_screen"),
                patch.object(menu, "_jump_screen"), patch.object(menu, "_settings_screen"),
                patch.object(menu.C, "cmd_doctor"), patch.object(menu, "_reset_screen"),
                patch.object(menu, "_prompt_choice", side_effect=choices),
                patch.object(menu, "_pause"),
            ]
            entered = [p.start() for p in patches]
            try:
                self.assertEqual(menu.main_menu(directory), 0)
                for handler in entered[:12]:
                    handler.assert_called_once()
            finally:
                for p in patches:
                    p.stop()


if __name__ == "__main__":
    unittest.main()
