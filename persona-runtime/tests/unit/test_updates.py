from __future__ import annotations

from pathlib import Path

import pytest

from par.audit.log import AuditLog
from par.config.settings import RuntimeConfig
from par.identity.persona import load_persona
from par.updates.manager import UpdateError, UpdateManager, current_persona_path

ROOT = Path(__file__).resolve().parents[2]


def _manager(config: RuntimeConfig, tmp_path: Path) -> UpdateManager:
    db = config.db_path
    db.parent.mkdir(parents=True, exist_ok=True)
    return UpdateManager(
        agent_id=config.agent_id,
        db_path=db,
        versions_dir=tmp_path / "versions",
        audit=AuditLog(db),
    )


def _persona_content() -> dict:
    card = load_persona(ROOT / "configs" / "personas" / "linxi.yaml")
    content = {"personality": card.personality.model_dump(mode="json"), "deviation_propensity": 0.4}
    content["expression"] = {"greeting": card.greeting, "sentence_length": card.style.sentence_length}
    return content


def test_propose_approve_apply_rollback(config: RuntimeConfig, tmp_path: Path) -> None:
    mgr = _manager(config, tmp_path)
    try:
        v1 = mgr.propose(
            kind="persona", content=_persona_content(), rationale="tone down directness", proposed_by="ops"
        )
        assert v1.status == "proposed"
        with pytest.raises(UpdateError):
            mgr.apply(v1.version_id)  # not approved yet

        mgr.approve(v1.version_id, approved_by="alice", approval_ref="TICKET-1")
        applied = mgr.apply(v1.version_id)
        assert applied.status == "applied"
        assert Path(applied.applied_path or "").exists()
        assert current_persona_path(config.db_path, config.agent_id) == applied.applied_path

        content2 = _persona_content()
        content2["deviation_propensity"] = 0.2
        v2 = mgr.propose(kind="persona", content=content2, rationale="reduce deviation", proposed_by="ops")
        mgr.approve(v2.version_id, approved_by="alice", approval_ref="TICKET-2")
        mgr.apply(v2.version_id)

        restored = mgr.rollback("persona")
        assert restored.version_id == v1.version_id
        v1_row = mgr.store.get(v1.version_id)
        assert current_persona_path(config.db_path, config.agent_id) == v1_row.applied_path
    finally:
        mgr.close()


def test_rejects_protect_humans_edit(config: RuntimeConfig, tmp_path: Path) -> None:
    mgr = _manager(config, tmp_path)
    try:
        content = _persona_content()
        content["personality"]["values"]["protect_humans"] = 0.5
        with pytest.raises(UpdateError, match="hard_value_immutable"):
            mgr.propose(kind="persona", content=content, rationale="nope", proposed_by="ops")
    finally:
        mgr.close()


def test_requires_named_approver(config: RuntimeConfig, tmp_path: Path) -> None:
    mgr = _manager(config, tmp_path)
    try:
        v = mgr.propose(kind="policy", content={"approval_ttl_s": 900}, rationale="longer ttl", proposed_by="ops")
        with pytest.raises(UpdateError):
            mgr.approve(v.version_id, approved_by="  ", approval_ref="T-1")
        with pytest.raises(UpdateError):
            mgr.approve(v.version_id, approved_by="bob", approval_ref="")
    finally:
        mgr.close()
