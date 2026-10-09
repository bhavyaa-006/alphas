import asyncio
import json
import threading
import unittest

import httpx

from alphapilot.agent import AgentError, AgentEvent, AlphaAgent, StreamClient


def sse(*objects):
    return "".join("data: " + (obj if isinstance(obj, str) else json.dumps(obj)) + "\n\n" for obj in objects).encode()


class StreamClientTests(unittest.IsolatedAsyncioTestCase):
    def provider(self):
        return {"provider": "test", "model": "test-model", "base_url": "https://test.invalid/chat"}

    async def test_streams_incremental_content_and_reassembles_tool_calls(self):
        frames = [
            {"choices": [{"delta": {"content": "Hi "}}]},
            {"choices": [{"delta": {"content": "there"}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "inspect_", "arguments": "{\"x\":"}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "project", "arguments": "1}"}}]}}]},
            "[DONE]",
        ]

        async def handler(request):
            self.assertTrue(json.loads(request.content)["stream"])
            return httpx.Response(200, content=sse(*frames), headers={"content-type": "text/event-stream"})

        events = []
        async def sink(event):
            events.append(event)

        client = StreamClient(self.provider(), 2, httpx.MockTransport(handler))
        result = await client.complete([], sink, asyncio.Event())
        self.assertEqual("".join(e.text for e in events if e.kind == "text"), "Hi there")
        self.assertEqual(result["content"], "Hi there")
        self.assertEqual(result["tool_calls"][0]["function"], {"name": "inspect_project", "arguments": '{"x":1}'})

    async def test_ignores_malformed_and_empty_sse_frames(self):
        async def handler(_request):
            return httpx.Response(200, content=b"data: nope\n\ndata: {\"choices\": []}\n\ndata: [DONE]\n\n")

        async def sink(_event):
            self.fail("no events expected")

        client = StreamClient(self.provider(), 2, httpx.MockTransport(handler))
        result = await client.complete([], sink, asyncio.Event())
        self.assertEqual(result, {"content": "", "tool_calls": []})

    async def test_http_error_is_human_readable(self):
        async def handler(_request):
            return httpx.Response(503, text="upstream unavailable")

        async def sink(_event):
            pass

        client = StreamClient(self.provider(), 2, httpx.MockTransport(handler))
        with self.assertRaisesRegex(AgentError, "HTTP 503"):
            await client.complete([], sink, asyncio.Event())

    async def test_cancelled_before_request(self):
        async def handler(_request):
            self.fail("request should not start")

        async def sink(_event):
            pass

        cancel = asyncio.Event()
        cancel.set()
        client = StreamClient(self.provider(), 2, httpx.MockTransport(handler))
        with self.assertRaises(asyncio.CancelledError):
            await client.complete([], sink, cancel)

    async def test_agent_runs_tool_then_streams_follow_up(self):
        requests_seen = 0
        tool_request = {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "type": "function",
                          "function": {"name": "inspect_project", "arguments": "{}"}}]}}]}
        final_text = {"choices": [{"delta": {"content": "Pack looks healthy."}}]}

        async def handler(_request):
            nonlocal requests_seen
            requests_seen += 1
            payload = [tool_request, "[DONE]"] if requests_seen == 1 else [final_text, "[DONE]"]
            return httpx.Response(200, content=sse(*payload))

        agent = object.__new__(AlphaAgent)
        agent.cancel_event = threading.Event()
        agent.messages = [{"role": "system", "content": "test"}]
        agent.client = StreamClient(self.provider(), 2, httpx.MockTransport(handler))
        called = []

        async def fake_tool(name, args, _sink):
            called.append((name, args))
            return {"pack": "test_pack"}

        agent._tool = fake_tool
        events = []
        async def sink(event):
            events.append(event)

        await agent.run_turn("inspect the pack", sink)
        self.assertEqual(called, [("inspect_project", {})])
        self.assertEqual(requests_seen, 2)
        self.assertTrue(any(e.kind == "text" and e.text == "Pack looks healthy." for e in events))
        self.assertEqual(agent.messages[-1]["content"], "Pack looks healthy.")

    async def test_cancellation_closes_an_active_stream(self):
        stream_state = {"closed": False}

        class SlowStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                await asyncio.Event().wait()
                yield b"data: [DONE]\n\n"

            async def aclose(self):
                stream_state["closed"] = True

        async def handler(_request):
            return httpx.Response(200, stream=SlowStream())

        async def sink(_event):
            pass

        client = StreamClient(self.provider(), 5, httpx.MockTransport(handler))
        task = asyncio.create_task(client.complete([], sink, asyncio.Event()))
        await asyncio.sleep(0.02)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(stream_state["closed"])

    async def test_stream_error_frame_surfaces_as_agent_error(self):
        async def handler(_request):
            return httpx.Response(200, content=sse({"error": {"message": "invalid API key"}}))

        async def sink(_event):
            pass

        client = StreamClient(self.provider(), 2, httpx.MockTransport(handler))
        with self.assertRaisesRegex(AgentError, "invalid API key"):
            await client.complete([], sink, asyncio.Event())


if __name__ == "__main__":
    unittest.main()
