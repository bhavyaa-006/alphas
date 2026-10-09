import threading
import unittest

from alphapilot.engine import EngineCancelled, _poll_simulation


class NeverCalledSession:
    def get(self, _url):
        raise AssertionError("cancelled poll must not start another request")


class EngineCancellationTests(unittest.TestCase):
    def test_pre_cancelled_poll_returns_immediately(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(EngineCancelled):
            _poll_simulation(type("Ace", (), {"brain_api_url": "https://example.invalid"})(), NeverCalledSession(), "sim-1", 1, 1, cancel)

    def test_retry_after_wait_is_interruptible(self):
        cancel = threading.Event()
        called = threading.Event()

        class Response:
            status_code = 200
            headers = {"Retry-After": "10"}

        class Session:
            def get(self, _url):
                called.set()
                return Response()

        timer = threading.Timer(0.03, cancel.set)
        timer.start()
        try:
            with self.assertRaises(EngineCancelled):
                _poll_simulation(type("Ace", (), {"brain_api_url": "https://example.invalid"})(), Session(), "sim-1", 1, 20, cancel)
            self.assertTrue(called.is_set())
        finally:
            timer.cancel()


if __name__ == "__main__":
    unittest.main()
