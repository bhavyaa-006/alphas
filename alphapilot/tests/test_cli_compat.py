import contextlib
import io
import sys
import unittest
from unittest.mock import patch

from alphapilot import cli


class OriginalCliCompatibilityTests(unittest.TestCase):
    def test_original_commands_and_aliases_remain_registered(self):
        parser = cli.build_parser()
        commands = parser._subparsers._group_actions[0].choices
        original = {
            "init": cli.cmd_init,
            "login": cli.cmd_login,
            "packs": cli.cmd_packs,
            "doctor": cli.cmd_doctor,
            "run": cli.cmd_run,
            "fields": cli.cmd_fields,
            "status": cli.cmd_status,
            "submissions": cli.cmd_submissions,
            "candidates": cli.cmd_candidates,
            "review": cli.cmd_candidates,
            "jump": cli.cmd_jump,
            "reset": cli.cmd_reset,
            "retry-errors": cli.cmd_retry,
        }
        for name, handler in original.items():
            with self.subTest(command=name):
                self.assertIs(commands[name].get_default("func"), handler)

    def test_help_lists_original_commands(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            cli.build_parser().print_help()
        for name in ("init", "login", "packs", "doctor", "run", "fields", "status",
                     "submissions", "candidates", "review", "jump", "reset", "retry-errors",
                     "legacy-menu"):
            with self.subTest(command=name):
                self.assertIn(name, output.getvalue())

    def test_bare_piped_invocation_shows_help_without_starting_agent(self):
        output = io.StringIO()
        with patch.object(sys, "stdin", io.StringIO("")), \
                patch.object(cli, "cmd_menu") as menu, \
                contextlib.redirect_stdout(output):
            result = cli.main([])
        self.assertEqual(result, 0)
        self.assertIn("retry-errors", output.getvalue())
        menu.assert_not_called()

    def test_original_run_arguments_are_retained(self):
        args = cli.build_parser().parse_args([
            "run", "--focus", "field_a,combo", "--stop-after", "4",
            "--set", "submit.mode=off",
        ])
        self.assertIs(args.func, cli.cmd_run)
        self.assertEqual(args.focus, "field_a,combo")
        self.assertEqual(args.stop_after, 4)
        self.assertEqual(args.set, ["submit.mode=off"])


if __name__ == "__main__":
    unittest.main()
