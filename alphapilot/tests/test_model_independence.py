import contextlib
import builtins
import io
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from alphapilot import cli, config, engine
from alphapilot.agent_cli import CommandTerminal


class ModelIndependentCliTests(unittest.IsolatedAsyncioTestCase):
    async def test_core_help_status_and_dispatch_do_not_import_model_or_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            import builtins
            real_import = builtins.__import__

            def guarded_import(name, *args, **kwargs):
                if name in ("alphapilot.llm", "alphapilot.agent") or name.endswith(".llm") or name.endswith(".agent"):
                    raise AssertionError(f"unexpected optional AI import: {name}")
                return real_import(name, *args, **kwargs)

            output = io.StringIO()
            with patch.dict(os.environ, {"OPENAI_API_KEY": "", "MISTRAL_API_KEY": ""}), \
                    patch("builtins.__import__", side_effect=guarded_import), \
                    contextlib.redirect_stdout(output):
                with self.assertRaises(SystemExit) as help_exit:
                    cli.main(["--help"])
                self.assertEqual(help_exit.exception.code, 0)
                self.assertEqual(cli.main(["--home", str(home), "status"]), 0)
                self.assertEqual(cli.main(["--home", str(home), "init"]), 0)
            self.assertIn("retry-errors", output.getvalue())
            self.assertTrue((home / "config.yaml").exists())

    async def test_interactive_shell_dispatches_to_registered_handler(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal = CommandTerminal(Path(directory))
            with patch.object(cli, "cmd_status", return_value=0) as status:
                self.assertFalse(await terminal.execute("/status"))
            status.assert_called_once()

    async def test_default_submission_metadata_is_deterministic_and_model_free(self):
        cfg = config.load_config(Path(tempfile.mkdtemp()))
        candidate = SimpleNamespace(expr="rank(close)", sharpe=1.2, fitness=0.8, turnover=0.2)
        pack = SimpleNamespace(name="demo", fields={"close": "closing price"})
        real_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.endswith(".llm") or name == "alphapilot.llm":
                raise AssertionError(f"unexpected model import: {name}")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded_import):
            metadata = engine._submission_metadata(cfg, candidate, pack)
        self.assertEqual(metadata.source, "template")
        self.assertIn("close", metadata.description)

    async def test_explicit_ai_metadata_without_key_fails_before_submission(self):
        cfg = config.load_config(Path(tempfile.mkdtemp()), ["llm.provider=openai", "llm.metadata_mode=ai"])
        candidate = SimpleNamespace(expr="rank(close)", sharpe=1.2, fitness=0.8, turnover=0.2)
        pack = SimpleNamespace(name="demo", fields={"close": "closing price"}, settings={
            "region": "USA", "universe": "TOP3000", "delay": 1, "decay": 0,
            "neutralization": "SUBINDUSTRY", "truncation": 0.08, "pasteurization": "ON",
            "unit_handling": "VERIFY", "nan_handling": "OFF",
        })
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaisesRegex(engine.MetadataGenerationError, "No submission was made"):
                engine._submission_metadata(cfg, candidate, pack)

    async def test_submission_handler_uses_real_template_path_without_model_call(self):
        cfg = config.load_config(Path(tempfile.mkdtemp()))
        candidate = SimpleNamespace(expr="rank(close)", alpha_id="alpha-test", sharpe=1.2,
                                    fitness=0.8, turnover=0.2)
        settings = {"region": "USA", "universe": "TOP3000", "delay": 1, "decay": 0,
                    "neutralization": "SUBINDUSTRY", "truncation": 0.08}
        pack = SimpleNamespace(name="demo", fields={"close": "closing price"}, settings=settings)

        class Response:
            status_code = 200
            text = ""

        class Session:
            def get(self, _url):
                class StatusResponse:
                    status_code = 200

                    @staticmethod
                    def json():
                        return {"status": "PENDING"}
                return StatusResponse()

        class Ace:
            brain_api_url = "https://brain.invalid"

            @staticmethod
            def set_alpha_properties(*_args, **_kwargs):
                return Response()

        store = SimpleNamespace(mark_submitted=unittest.mock.Mock(), log_event=unittest.mock.Mock())
        submitted = SimpleNamespace(ok=True, halt=False)
        real_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.endswith(".llm") or name == "alphapilot.llm":
                raise AssertionError(f"unexpected model import: {name}")
            return real_import(name, *args, **kwargs)

        with patch.object(engine.BC, "submit_alpha", return_value=submitted), \
                patch.object(engine, "notify"), \
                patch("builtins.__import__", side_effect=guarded_import):
            ok, message = engine.submit_candidate_now(Ace(), Session(), cfg, pack, store, candidate)
        self.assertTrue(ok)
        self.assertIn("SUBMITTED", message)
        store.mark_submitted.assert_called_once()


if __name__ == "__main__":
    unittest.main()
