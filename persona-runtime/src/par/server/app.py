"""Local OpenAI-compatible façade + built-in web chat.

Why this exists: the persona runtime is *not* a model. To use it from DeepSeek
Harness, ChatGPT-compatible clients, or any OpenAI SDK, it speaks the OpenAI
chat-completions shape and adds the persona layer underneath.

    POST /v1/chat/completions   OpenAI-compatible (non-streaming)
    GET  /v1/models
    GET  /health
    POST /api/chat              {message} -> {reply, labels, memories}
    GET  /                      built-in chat page

One agent process = one conversation stream. This is a deliberate v0 boundary:
per-end-user isolation belongs to the deployment layer, not this server.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from par.orchestrator.agent import Agent

STATIC = Path(__file__).parent / "static"


class _LoopThread:
    """One long-lived asyncio loop so provider clients stay on their loop."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def call(self, coro: Any, timeout: float = 180.0) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)


class Runtime:
    def __init__(self, agent: Agent, loop: _LoopThread) -> None:
        self.agent = agent
        self.loop = loop
        self.lock = threading.Lock()

    def chat(self, text: str) -> dict[str, Any]:
        with self.lock:
            result = self.loop.call(self.agent.turn(text))
        return {
            "reply": result.reply,
            "labels": result.labels,
            "memories": [{"id": m.memory_id, "text": m.text, "kind": m.kind} for m in result.memories[:5]],
            "audit_seq": result.audit_seq,
            "verifier_ok": result.verifier.ok if result.verifier else True,
            "intent": result.intent,
            "gate_verdict": result.gate_verdict,
            "executed": result.executed,
            "deviation": result.deviation,
        }


def _make_handler(runtime: Runtime) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "par/0.1"

        def log_message(self, fmt: str, *args: Any) -> None:  # quieter default
            if self.path.startswith("/v1"):
                return

        # ------------------------------------------------------------- utils
        def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: dict) -> None:
            self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"))

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except ValueError as exc:
                raise ValueError("invalid_json") from exc
            if not isinstance(data, dict):
                raise ValueError("json_object_expected")
            return data

        # -------------------------------------------------------------- GET
        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/index.html"):
                page = STATIC / "index.html"
                if not page.exists():
                    self._json(500, {"error": "ui_missing"})
                    return
                self._send(200, page.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/health":
                a = runtime.agent
                self._json(
                    200,
                    {
                        "status": "ok",
                        "agent_id": a.agent_id,
                        "persona": a.persona.persona_id,
                        "version": a.persona.personality.version,
                        "provider": a.provider_name,
                        "affect_version": a.affect.version,
                        "turns": a.turn_no,
                    },
                )
            elif self.path == "/api/state":
                a = runtime.agent
                state = a.affect.model_dump(mode="json")
                self._json(
                    200,
                    {
                        "agent_id": a.agent_id,
                        "persona": a.persona.personality.display_name,
                        "version": a.persona.personality.version,
                        "provider": a.provider_name,
                        "turns": a.turn_no,
                        "affect": state,
                        "labels": a.labels,
                        "audit_head": a.audit.head(),
                    },
                )
            elif self.path == "/api/tools":
                self._json(200, {"tools": runtime.agent.toolbox.describe()})
            elif self.path == "/api/audit/verify":
                a = runtime.agent
                try:
                    a.audit.verify()
                except Exception as exc:  # audit tamper is a 409, not a 500
                    self._json(
                        409,
                        {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:300], "head": a.audit.head()},
                    )
                    return
                self._json(200, {"ok": True, "head": a.audit.head()})
            elif self.path == "/v1/models":
                self._json(
                    200,
                    {
                        "object": "list",
                        "data": [
                            {
                                "id": f"par-{runtime.agent.persona.personality.persona_id}",
                                "object": "model",
                                "owned_by": "par-runtime",
                            }
                        ],
                    },
                )
            else:
                self._json(404, {"error": "not_found"})

        # ------------------------------------------------------------- POST
        def do_POST(self) -> None:  # noqa: N802
            try:
                payload = self._read_json()
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            try:
                if self.path in ("/v1/chat/completions", "/api/chat"):
                    self._handle_chat(payload)
                elif self.path == "/v1/audio/speech":
                    self._handle_tts(payload)
                else:
                    self._json(404, {"error": "not_found"})
            except Exception as exc:  # keep the server alive; report the failure
                self._json(500, {"error": type(exc).__name__, "detail": str(exc)[:500]})

        def _handle_chat(self, payload: dict) -> None:
            messages = payload.get("messages") or []
            user_text = ""
            for m in reversed(messages):
                if isinstance(m, dict) and m.get("role") == "user":
                    user_text = str(m.get("content") or "")
                    break
            if not user_text:
                user_text = str(payload.get("message") or "")
            if not user_text:
                self._json(400, {"error": "no_user_message"})
                return
            out = runtime.chat(user_text)
            if self.path == "/api/chat":
                self._json(200, out)
                return
            per_message = out["reply"]
            self._json(
                200,
                {
                    "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                    "object": "chat.completion",
                    "created": 0,
                    "model": payload.get("model") or f"par-{runtime.agent.persona.persona_id}",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": per_message},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "par": {"labels": out["labels"], "audit_seq": out["audit_seq"]},
                },
            )

        def _handle_tts(self, payload: dict) -> None:
            from par.voice.tts import synthesize_wav

            text = str(payload.get("input") or "")
            if not text:
                self._json(400, {"error": "empty_input"})
                return
            try:
                wav = synthesize_wav(text)
            except Exception as exc:
                self._json(501, {"error": "tts_unavailable", "detail": str(exc)[:300]})
                return
            self._send(200, wav, "audio/wav")

    return Handler


def serve(
    config_path: str,
    *,
    host: str = "127.0.0.1",
    port: int = 7860,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    agent = Agent.create(config_path, provider=provider, model=model)
    loop = _LoopThread()
    runtime = Runtime(agent, loop)
    httpd = ThreadingHTTPServer((host, port), _make_handler(runtime))
    print(f"par listening on http://{host}:{port}  (agent={agent.agent_id}, provider={agent.provider_name})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        loop.call(agent.aclose(), timeout=10)
