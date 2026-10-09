import unittest
import builtins
from types import SimpleNamespace
from unittest.mock import patch

from alphapilot import engine


class Response:
    status_code = 200
    headers = {"Location": "parent"}
    text = ""


class BatchRecoveryTests(unittest.TestCase):
    def test_partial_child_failure_falls_back_only_for_failed_item(self):
        cfg = SimpleNamespace(
            simulation=SimpleNamespace(batch_timeout_min=3),
            api=SimpleNamespace(max_retry_after_s=1),
        )
        alpha_dicts = [{"regular": "a"}, {"regular": "b"}]
        poll_results = [
            {"children": ["child-a", "child-b"]},
            {"alpha": "alpha-a"},
            {"status": "ERROR", "message": "one child failed"},
        ]

        class Ace:
            def start_simulation(self, _session, _alphas):
                return Response()

        real_import = builtins.__import__

        def forbid_model_import(name, *args, **kwargs):
            if name == "alphapilot.llm" or name.endswith(".llm"):
                raise AssertionError(f"simulation batch attempted a model import: {name}")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=forbid_model_import), \
             patch.object(engine, "_poll_simulation", side_effect=poll_results) as poll, \
             patch.object(engine, "_simulate_one", return_value={"alpha_id": "alpha-b-recovered", "simulate_data": alpha_dicts[1], "error": None}) as fallback:
            results = engine._simulate_batch_with_fallback(Ace(), object(), cfg, alpha_dicts)

        self.assertEqual([r["alpha_id"] for r in results], ["alpha-a", "alpha-b-recovered"])
        self.assertEqual([r["simulate_data"] for r in results], alpha_dicts)
        self.assertEqual(poll.call_count, 3)
        fallback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
