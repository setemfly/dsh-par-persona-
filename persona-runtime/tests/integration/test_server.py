from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from par.audit.log import AuditLog
from par.config.settings import load_config
from par.identity.persona import load_persona
from par.llm.fake import FakeProvider
from par.llm.registry import ProviderRegistry, load_providers_file
from par.memory.store import MemoryStore
from par.orchestrator.agent import Agent
from par.server.app import Runtime, _LoopThread, _make_handler

ROOT = Path(__file__).resolve().parents[2]


def _start(tmp_path: Path) -> tuple[ThreadingHTTPServer, str, Agent]:
    config = load_config(ROOT / "configs" / "runtime.yaml").model_copy(
        update={"data_dir": str(tmp_path), "provider": "fake"}
    )
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    provider = FakeProvider(script=["你好呀，我是林汐。", "我记得你喜欢拿铁。"])
    registry = ProviderRegistry(load_providers_file(config.path(config.providers_file)), discover=False)
    registry._instances["fake"] = provider
    agent = Agent(
        config=config,
        persona=load_persona(config.path(config.persona)),
        store=MemoryStore(config.db_path),
        audit=AuditLog(config.db_path),
        registry=registry,
        provider_name="fake",
        model="fake-1",
    )
    loop = _LoopThread()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(Runtime(agent, loop)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    host, port = httpd.server_address[:2]
    return httpd, f"http://{host}:{port}", agent


def _post(base: str, path: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _get(base: str, path: str) -> tuple[int, dict]:
    with urllib.request.urlopen(base + path, timeout=20) as resp:
        body = resp.read().decode("utf-8")
        ctype = resp.headers.get("Content-Type", "")
        return resp.status, json.loads(body) if "json" in ctype else {"html": body}


def test_health_and_models(tmp_path: Path) -> None:
    httpd, base, _ = _start(tmp_path)
    try:
        status, body = _get(base, "/health")
        assert status == 200 and body["status"] == "ok"
        assert body["agent_id"] == "linxi"
        _, models = _get(base, "/v1/models")
        assert models["data"][0]["id"] == "par-lin_xi_v1"
        status, page = _get(base, "/")
        assert status == 200 and "林汐" in page["html"]
    finally:
        httpd.shutdown()


def test_api_chat_and_openai_shape(tmp_path: Path) -> None:
    httpd, base, _ = _start(tmp_path)
    try:
        status, body = _post(base, "/api/chat", {"message": "你好"})
        assert status == 200
        assert body["reply"] == "你好呀，我是林汐。"
        assert body["audit_seq"] >= 1

        status, out = _post(
            base,
            "/v1/chat/completions",
            {"model": "par-lin_xi_v1", "messages": [{"role": "user", "content": "再聊一句"}]},
        )
        assert status == 200
        assert out["object"] == "chat.completion"
        assert out["choices"][0]["message"]["role"] == "assistant"
        assert out["choices"][0]["message"]["content"] == "我记得你喜欢拿铁。"

        status, err = _post(base, "/v1/chat/completions", {"messages": []})
        assert status == 400 and err["error"] == "no_user_message"
    finally:
        httpd.shutdown()
