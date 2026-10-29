from __future__ import annotations

from datetime import UTC, datetime

from par.memory.store import MemoryStore
from par.schemas.core import MemoryCandidate


def _cand(text: str, *, importance: float = 0.6, kind: str = "episode") -> MemoryCandidate:
    return MemoryCandidate(
        agent_id="a",
        tier="episodic",
        kind=kind,  # type: ignore[arg-type]
        text=text,
        occurred_at=datetime.now(UTC),
        importance=importance,
        provenance=["obs_1"],
    )


def test_remember_and_recall_cjk(tmp_path) -> None:
    store = MemoryStore(tmp_path / "m.db")
    store.remember("a", _cand("用户喜欢拿铁咖啡，不加糖"))
    hits = store.recall("a", "拿铁")
    assert hits and "拿铁" in hits[0].text
    store.close()


def test_recall_ranks_importance(tmp_path) -> None:
    store = MemoryStore(tmp_path / "m.db")
    store.remember("a", _cand("会议安排在周三下午三点整", importance=0.2))
    store.remember("a", _cand("会议很重要：用户要辞职", importance=0.95))
    hits = store.recall("a", "会议", k=2)
    assert hits[0].importance >= hits[1].importance
    store.close()


def test_scope_filters_other_agents(tmp_path) -> None:
    store = MemoryStore(tmp_path / "m.db")
    store.remember("a", _cand("A 的秘密"))
    store.remember("b", _cand("B 的秘密"))
    assert all("B" not in h.text for h in store.recall("a", "秘密", k=10))
    store.close()


def test_commitment_upsert(tmp_path) -> None:
    store = MemoryStore(tmp_path / "m.db")
    store.upsert_commitment("a", "send-report", "周五前给报告")
    store.upsert_commitment("a", "send-report", "周五前给报告（修订）")
    rows = store.commitments("a")
    assert len(rows) == 1 and "修订" in rows[0]["text"]
    store.close()


def test_supersede_hides_old(tmp_path) -> None:
    store = MemoryStore(tmp_path / "m.db")
    old = store.remember("a", _cand("用户住在北京"))
    new = store.remember("a", _cand("用户搬到上海"))
    store.supersede(old.memory_id, new.memory_id)
    hits = store.recall("a", "住在", k=10)
    assert all(h.memory_id != old.memory_id for h in hits)
    store.close()


def test_identical_replay_is_reinforced_not_duplicated(tmp_path) -> None:
    store = MemoryStore(tmp_path / "m.db")
    first = store.remember("a", _cand("用户喜欢拿铁"))
    second = store.remember("a", _cand("用户喜欢拿铁"))
    assert second.memory_id == first.memory_id
    assert second.version == first.version + 1
    assert store.counts("a")["total"] == 1
    store.close()
