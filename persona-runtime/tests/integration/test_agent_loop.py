from __future__ import annotations

import pytest

from par.audit.log import AuditLog
from par.config.settings import load_config
from par.identity.persona import load_persona
from par.llm.registry import ProviderConfig, ProviderRegistry, ProviderSpec
from par.memory.store import MemoryStore
from par.orchestrator.agent import Agent


@pytest.fixture()
def agent(tmp_path, project_root):
    config = load_config(project_root / "configs" / "runtime.yaml").model_copy(
        update={"data_dir": str(tmp_path), "provider": "fake"}
    )
    persona = load_persona(config.path(config.persona))
    store = MemoryStore(config.db_path)
    audit = AuditLog(config.db_path)
    registry = ProviderRegistry(
        [ProviderSpec(name="fake", config=ProviderConfig(kind="fake", model="fake-1"))],
        discover=False,
    )
    a = Agent(
        config=config,
        persona=persona,
        store=store,
        audit=audit,
        registry=registry,
        provider_name="fake",
        model=None,
    )
    a._registry_override = None  # keep mypy quiet about dynamic attrs
    return a


@pytest.mark.asyncio
async def test_turn_writes_memory_and_audit(agent) -> None:
    result = await agent.turn("你好，我叫阿羽，喜欢拿铁")
    assert result.reply
    assert result.audit_seq >= 1
    assert agent.store.counts("linxi")["total"] >= 1
    assert agent.audit.verify()["records"] >= 1
    await agent.aclose()


@pytest.mark.asyncio
async def test_second_turn_recalls_first(agent) -> None:
    await agent.turn("我叫阿羽，喜欢拿铁")
    result = await agent.turn("我刚才说我叫什么？")
    assert result.memories, "expected recall of the previous episode"
    await agent.aclose()


@pytest.mark.asyncio
async def test_affect_moves_and_persists(agent) -> None:
    before = agent.affect.version
    await agent.turn("谢谢你，这很有帮助")
    assert agent.affect.version > before
    saved = agent.store.get_state("linxi", "affect")
    assert saved is not None and saved["state"]["version"] == agent.affect.version
    await agent.aclose()
