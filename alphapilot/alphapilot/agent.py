"""Async OpenAI-compatible streaming agent and bounded local alpha tools."""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from . import llm as LLM


class AgentState(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    STREAMING = "streaming"
    TOOL_RUNNING = "tool_running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentEvent:
    kind: str
    text: str = ""
    data: dict[str, Any] = field(default_factory=dict)


EventSink = Callable[[AgentEvent], Awaitable[None]]


TOOLS = [
    {"type": "function", "function": {"name": "inspect_project", "description": "Inspect the active alpha pack, its settings, fields, allowed operators, and current session progress.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "preview_candidates", "description": "Build and preview expressions from the active configured alpha pack. This does not call the platform or submit anything.", "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 30}}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "simulate_candidates", "description": "Run a bounded number of resumable simulation batches for the active pack. Submission is forcibly disabled for this tool; it never submits alphas.", "parameters": {"type": "object", "properties": {"batches": {"type": "integer", "minimum": 1, "maximum": 10}}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "recent_results", "description": "Read recent simulated alpha results and errors from the local progress database.", "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 30}}, "additionalProperties": False}}},
]


class AgentError(Exception):
    pass


class StreamClient:
    """Streaming transport for the OpenAI chat completions SSE protocol."""

    def __init__(self, provider: dict, timeout_s: float, transport=None):
        self.provider = provider
        self.timeout_s = max(1.0, float(timeout_s))
        self.transport = transport

    def _headers(self):
        p = self.provider
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        key_env = p.get("api_key_env")
        if key_env:
            key = os.environ.get(key_env, "").strip()
            if not key:
                raise AgentError(f"Set {key_env} to use the configured {p['provider']} model.")
            headers["Authorization"] = f"Bearer {key}"
            if p["provider"] == "openrouter":
                headers.update({"HTTP-Referer": "http://localhost", "X-Title": "alphapilot"})
        return headers

    async def complete(self, messages: list[dict], sink: EventSink, cancel: asyncio.Event) -> dict:
        payload = {"model": self.provider["model"], "messages": messages,
                   "temperature": self.provider.get("temperature", 0.3), "stream": True, "tools": TOOLS, "tool_choice": "auto"}
        headers = self._headers()
        content_seen = False
        streamed_text = ""
        streaming_notified = False
        for attempt in range(2):
            attempt_started = time.monotonic()
            calls: dict[int, dict] = {}
            saw_done = False
            if cancel.is_set():
                raise asyncio.CancelledError
            try:
                timeout = httpx.Timeout(self.timeout_s, connect=min(15.0, self.timeout_s), read=self.timeout_s,
                                        write=self.timeout_s, pool=min(15.0, self.timeout_s))
                async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
                    async with client.stream("POST", self.provider["base_url"], headers=headers,
                                             json=payload) as response:
                        if response.status_code != 200:
                            detail = (await response.aread()).decode("utf-8", "replace")[:400]
                            if response.status_code in (408, 429) or response.status_code >= 500:
                                if attempt == 0 and not content_seen:
                                    await sink(AgentEvent("state", "Retrying model request…", {"state": AgentState.RETRYING.value}))
                                    await asyncio.sleep(0.4)
                                    continue
                            raise AgentError(f"Model API returned HTTP {response.status_code}: {detail}")
                        async for line in response.aiter_lines():
                            if time.monotonic() - attempt_started >= self.timeout_s:
                                raise AgentError(f"Model stream exceeded the {self.timeout_s:.0f}s request deadline.")
                            if cancel.is_set():
                                raise asyncio.CancelledError
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if not data:
                                continue
                            if data == "[DONE]":
                                saw_done = True
                                break
                            try:
                                chunk = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            if chunk.get("error"):
                                error = chunk["error"]
                                message = error.get("message") if isinstance(error, dict) else error
                                raise AgentError(str(message or "streaming model returned an error"))
                            choices = chunk.get("choices") or []
                            if not choices:
                                continue
                            delta = choices[0].get("delta") or {}
                            text = delta.get("content")
                            if isinstance(text, str) and text:
                                content_seen = True
                                streamed_text += text
                                if not streaming_notified:
                                    streaming_notified = True
                                    await sink(AgentEvent("state", "Responding", {"state": AgentState.STREAMING.value}))
                                await sink(AgentEvent("text", text))
                            for tool_delta in delta.get("tool_calls") or []:
                                idx = int(tool_delta.get("index", 0))
                                call = calls.setdefault(idx, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                                if tool_delta.get("id"):
                                    call["id"] = tool_delta["id"]
                                fn = tool_delta.get("function") or {}
                                call["function"]["name"] += fn.get("name", "")
                                call["function"]["arguments"] += fn.get("arguments", "")
                if not saw_done:
                    if attempt == 0 and not content_seen:
                        await sink(AgentEvent("state", "Retrying interrupted stream…", {"state": AgentState.RETRYING.value}))
                        continue
                    raise AgentError("Model stream ended before its completion marker; the response may be incomplete.")
                return {"content": streamed_text,
                        "tool_calls": [calls[k] for k in sorted(calls)]}
            except asyncio.CancelledError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == 0 and not content_seen:
                    await sink(AgentEvent("state", "Retrying model connection…", {"state": AgentState.RETRYING.value}))
                    await asyncio.sleep(0.4)
                    continue
                detail = str(exc).strip() or "no additional details"
                raise AgentError(f"Model connection failed ({type(exc).__name__}): {detail}") from exc
        raise AgentError("Model stream ended without a response.")


class AlphaAgent:
    def __init__(self, home: Path, cfg):
        self.home = Path(home)
        self.cfg = cfg
        # Thread-safe because resumable simulation runs through asyncio.to_thread.
        self.cancel_event = threading.Event()
        provider = LLM.resolve_provider_config(cfg)
        if provider["provider"] == "template":
            raise AgentError("No chat model is configured. Set llm.provider and model credentials in config.yaml, then restart.")
        provider["temperature"] = cfg.llm.temperature
        self.client = StreamClient(provider, cfg.llm.timeout_s)
        self.messages = [{"role": "system", "content": (
            "You are AlphaPilot, a WorldQuant BRAIN alpha research agent. Help inspect the configured local pack, "
            "reason about FASTEXPR candidates, and operate its resumable simulation workflow. Use tools for local "
            "facts instead of guessing. Never claim an alpha was simulated unless the simulation tool reports it. "
            "The simulation tool never submits. Do not claim a submission occurred. Keep responses concise, explain "
            "uncertainty, and surface API/tool failures clearly.") }]

    async def run_turn(self, prompt: str, sink: EventSink) -> None:
        # Give every turn its own token. If a wrapped synchronous call outlives
        # its bounded cleanup window, a later turn cannot accidentally clear
        # the cancellation request it is still observing.
        self.cancel_event = threading.Event()
        self._trim_history()
        self.messages.append({"role": "user", "content": prompt})
        try:
            for _round in range(6):
                await sink(AgentEvent("state", "Thinking", {"state": AgentState.THINKING.value}))
                result = await self.client.complete(self.messages, sink, self.cancel_event)
                calls = result["tool_calls"]
                if not calls:
                    self.messages.append({"role": "assistant", "content": result["content"]})
                    await sink(AgentEvent("state", "Completed", {"state": AgentState.COMPLETED.value}))
                    return
                assistant_message = {"role": "assistant", "content": result["content"] or None, "tool_calls": calls}
                self.messages.append(assistant_message)
                for call in calls:
                    if self.cancel_event.is_set():
                        raise asyncio.CancelledError
                    fn = call.get("function", {})
                    name = fn.get("name", "")
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                        if not isinstance(args, dict):
                            raise ValueError("tool arguments must be a JSON object")
                    except (json.JSONDecodeError, ValueError) as exc:
                        output = {"error": f"Invalid tool arguments: {exc}"}
                    else:
                        await sink(AgentEvent("tool_start", name, {"tool": name, "args": args}))
                        try:
                            output = await self._tool(name, args, sink)
                            await sink(AgentEvent("tool_end", name, {"tool": name, "ok": True}))
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            output = {"error": f"{type(exc).__name__}: {exc}"}
                            await sink(AgentEvent("tool_end", str(exc), {"tool": name, "ok": False}))
                    self.messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                          "name": name, "content": json.dumps(output, ensure_ascii=False, default=str)[:12000]})
            raise AgentError("Reached the tool-call limit for one turn. Ask a narrower follow-up.")
        except asyncio.CancelledError:
            self.messages.append({"role": "assistant", "content": "(turn cancelled)"})
            await sink(AgentEvent("state", "Cancelled", {"state": AgentState.CANCELLED.value}))
            raise
        except Exception:
            await sink(AgentEvent("state", "Failed", {"state": AgentState.FAILED.value}))
            raise

    def _trim_history(self):
        if len(self.messages) <= 40:
            return
        groups = []
        current = []
        for message in self.messages[1:]:
            if message.get("role") == "user" and current:
                groups.append(current)
                current = []
            current.append(message)
        if current:
            groups.append(current)
        self.messages = self.messages[:1] + [message for group in groups[-6:] for message in group]

    async def _tool(self, name: str, args: dict, sink: EventSink) -> dict:
        if name == "inspect_project":
            return await asyncio.to_thread(self._inspect_project)
        if name == "preview_candidates":
            return await asyncio.to_thread(self._preview, args.get("limit", 10))
        if name == "recent_results":
            return await asyncio.to_thread(self._recent, args.get("limit", 10))
        if name == "simulate_candidates":
            batches = min(10, max(1, int(args.get("batches", 1))))
            await sink(AgentEvent("tool_progress", f"Simulating up to {batches} batches", {"current": 0, "total": batches}))
            return await self._simulate(batches, sink)
        return {"error": f"Unknown tool: {name}"}

    def _context(self):
        from . import cli as C
        from . import packs_api as P
        pack = P.load_pack(self.cfg.pack, C._pack_dirs(Path(C.__file__).resolve(), self.home))
        db = C._state_db_for(self.home, self.cfg)
        return C, pack, db

    def _inspect_project(self):
        C, pack, db = self._context()
        counts = {}
        if db.exists():
            from .state import Store
            store = Store(db)
            try:
                counts = store.counts()
            finally:
                store.close()
        return {"pack": pack.name, "pack_file": pack.key, "fields": pack.field_ids(),
                "field_count": len(pack.fields), "allowed_operators": sorted(pack.allowed_operators),
                "settings": pack.settings, "progress": counts, "database": str(db)}

    def _preview(self, limit):
        C, pack, _db = self._context()
        limit = min(30, max(1, int(limit)))
        exprs = pack.build(self.cfg.simulation.seed, self.cfg.simulation.pool_size)[:limit]
        return {"count": len(exprs), "expressions": exprs}

    def _recent(self, limit):
        C, pack, db = self._context()
        if not db.exists():
            return {"pack": pack.name, "results": [], "errors": []}
        from .state import Store
        store = Store(db)
        try:
            n = min(30, max(1, int(limit)))
            results = [{"expression": a.expr, "alpha_id": a.alpha_id, "status": a.status,
                        "sharpe": a.sharpe, "fitness": a.fitness, "turnover": a.turnover}
                       for a in store.top(n)]
            errors = store.error_summary(min(10, n))
            return {"pack": pack.name, "results": results, "errors": errors}
        finally:
            store.close()

    async def _simulate(self, batches, sink):
        """Use the existing resumable run command with submission explicitly disabled."""
        from argparse import Namespace
        from . import cli as C
        from . import util
        util.load_dotenv(self.home / ".env")
        if not (os.environ.get("BRAIN_CREDENTIAL_EMAIL") and os.environ.get("BRAIN_CREDENTIAL_PASSWORD")):
            return {"error": "BRAIN credentials are not configured. Run `alphapilot login` before simulation."}
        args = Namespace(home=str(self.home), set=["submit.mode=off"], focus=None,
                         stop_after=None, max_batches=batches, cancel_event=self.cancel_event)
        loop = asyncio.get_running_loop()

        def progress(message):
            loop.call_soon_threadsafe(lambda: asyncio.create_task(sink(AgentEvent("tool_progress", str(message)))))

        token = util.set_output_handler(progress)
        try:
            task = asyncio.create_task(asyncio.to_thread(C.cmd_run, args))
        finally:
            util.reset_output_handler(token)
        try:
            while not task.done():
                if self.cancel_event.is_set():
                    raise asyncio.CancelledError
                await asyncio.sleep(0.2)
            code = await task
            return {"exit_code": code, "cancelled": code == 130,
                    "progress": await asyncio.to_thread(self._inspect_project)}
        except asyncio.CancelledError:
            self.cancel_event.set()
            # The run loop checks this event between batches and polls; give it a bounded cleanup window.
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=max(10, self.cfg.api.timeout_s + 2))
            except (asyncio.TimeoutError, Exception):
                pass
            raise
