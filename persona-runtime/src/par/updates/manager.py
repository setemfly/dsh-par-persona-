"""Governed, versioned self-update (spec §14.4, ADR-007).

The runtime never rewrites its own code at run time. What it *can* do is stage a
new version of its declared state — persona card, policy envelope, runtime
config — and let a human approve it. Every step is audited, and every apply has
a rollback path to the last applied version.

    propose -> approved (human, named) -> apply -> rollback

Nothing here can be triggered by the model itself: the model has no tool that
reaches this module, and `apply` refuses unless status == approved.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml

from par.audit.log import AuditLog
from par.identity.persona import load_persona
from par.schemas.core import AuditRecord, canonical_json, sha256_hex

UpdateKind = Literal["persona", "policy", "runtime"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS config_version (
    version_id     TEXT PRIMARY KEY,
    agent_id       TEXT NOT NULL,
    kind           TEXT NOT NULL,
    base_version   TEXT,
    content_json   TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    status         TEXT NOT NULL,
    proposed_at    TEXT NOT NULL,
    proposed_by    TEXT NOT NULL,
    rationale      TEXT NOT NULL,
    approved_by    TEXT,
    approval_ref   TEXT,
    approved_at    TEXT,
    applied_at     TEXT,
    applied_path   TEXT,
    previous_version_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_cv_agent_kind ON config_version(agent_id, kind, status);
CREATE TABLE IF NOT EXISTS config_pointer (
    agent_id     TEXT NOT NULL,
    kind         TEXT NOT NULL,
    version_id   TEXT NOT NULL,
    path         TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (agent_id, kind)
);
"""

_TS = lambda: datetime.now(UTC).isoformat(timespec="seconds")  # noqa: E731


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Version:
    version_id: str
    agent_id: str
    kind: str
    base_version: str | None
    content: dict[str, Any]
    content_sha256: str
    status: str
    proposed_at: str
    proposed_by: str
    rationale: str
    approved_by: str | None
    approval_ref: str | None
    approved_at: str | None
    applied_at: str | None
    applied_path: str | None
    previous_version_id: str | None


class VersionStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --------------------------------------------------------------- reads
    def get(self, version_id: str) -> Version:
        row = self._conn.execute("SELECT * FROM config_version WHERE version_id=?", (version_id,)).fetchone()
        if row is None:
            raise UpdateError(f"unknown_version:{version_id}")
        return _to_version(row)

    def list(self, agent_id: str, kind: str | None = None, limit: int = 20) -> list[Version]:
        if kind:
            rows = self._conn.execute(
                "SELECT * FROM config_version WHERE agent_id=? AND kind=? ORDER BY proposed_at DESC LIMIT ?",
                (agent_id, kind, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM config_version WHERE agent_id=? ORDER BY proposed_at DESC LIMIT ?",
                (agent_id, limit),
            ).fetchall()
        return [_to_version(r) for r in rows]

    def current_pointer(self, agent_id: str, kind: str) -> tuple[str, str] | None:
        row = self._conn.execute(
            "SELECT version_id, path FROM config_pointer WHERE agent_id=? AND kind=?", (agent_id, kind)
        ).fetchone()
        return (row["version_id"], row["path"]) if row else None

    # -------------------------------------------------------------- writes
    def insert_proposed(self, *, agent_id: str, kind: str, content: dict, base_version: str | None,
                        proposed_by: str, rationale: str) -> Version:
        version_id = f"{kind}-{uuid.uuid4().hex[:12]}"
        payload = canonical_json(content)
        self._conn.execute(
            "INSERT INTO config_version (version_id, agent_id, kind, base_version, content_json, content_sha256,"
            " status, proposed_at, proposed_by, rationale) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (version_id, agent_id, kind, base_version, payload, sha256_hex(payload), "proposed",
             _TS(), proposed_by, rationale),
        )
        self._conn.commit()
        return self.get(version_id)

    def approve(self, version_id: str, *, approved_by: str, approval_ref: str) -> Version:
        v = self.get(version_id)
        if v.status != "proposed":
            raise UpdateError(f"cannot_approve_status:{v.status}")
        if not approved_by.strip() or not approval_ref.strip():
            raise UpdateError("approval_requires_named_approver_and_reference")
        self._conn.execute(
            "UPDATE config_version SET status='approved', approved_by=?, approval_ref=?, approved_at=? WHERE version_id=?",
            (approved_by, approval_ref, _TS(), version_id),
        )
        self._conn.commit()
        return self.get(version_id)

    def mark_applied(self, version_id: str, *, applied_path: str, previous_version_id: str | None) -> Version:
        v = self.get(version_id)
        if v.status != "approved":
            raise UpdateError(f"cannot_apply_status:{v.status}")
        self._conn.execute(
            "UPDATE config_version SET status='applied', applied_at=?, applied_path=?, previous_version_id=? WHERE version_id=?",
            (_TS(), applied_path, previous_version_id, version_id),
        )
        self._conn.commit()
        return self.get(version_id)

    def set_pointer(self, agent_id: str, kind: str, version_id: str, path: str) -> None:
        self._conn.execute(
            "INSERT INTO config_pointer (agent_id, kind, version_id, path, updated_at) VALUES (?,?,?,?,?)"
            " ON CONFLICT(agent_id, kind) DO UPDATE SET version_id=excluded.version_id, path=excluded.path, updated_at=excluded.updated_at",
            (agent_id, kind, version_id, path, _TS()),
        )
        self._conn.commit()

    def mark_rolled_back(self, version_id: str) -> None:
        self._conn.execute("UPDATE config_version SET status='rolled_back' WHERE version_id=?", (version_id,))
        self._conn.commit()


def _to_version(row: sqlite3.Row) -> Version:
    return Version(
        version_id=row["version_id"],
        agent_id=row["agent_id"],
        kind=row["kind"],
        base_version=row["base_version"],
        content=json.loads(row["content_json"]),
        content_sha256=row["content_sha256"],
        status=row["status"],
        proposed_at=row["proposed_at"],
        proposed_by=row["proposed_by"],
        rationale=row["rationale"],
        approved_by=row["approved_by"],
        approval_ref=row["approval_ref"],
        approved_at=row["approved_at"],
        applied_at=row["applied_at"],
        applied_path=row["applied_path"],
        previous_version_id=row["previous_version_id"],
    )


class UpdateManager:
    """Persona/policy/config versioning with human approval and rollback."""

    def __init__(self, *, agent_id: str, db_path: str | Path, versions_dir: str | Path, audit: AuditLog) -> None:
        self.agent_id = agent_id
        self.store = VersionStore(db_path)
        self.versions_dir = Path(versions_dir)
        self.audit = audit

    def close(self) -> None:
        self.store.close()

    # ------------------------------------------------------------- propose
    def propose(self, *, kind: UpdateKind, content: dict, rationale: str, proposed_by: str) -> Version:
        if not rationale.strip():
            raise UpdateError("proposal_requires_rationale")
        if kind == "persona":
            self._validate_persona(content)
        elif kind not in ("policy", "runtime"):
            raise UpdateError(f"unknown_kind:{kind}")
        base = self.store.current_pointer(self.agent_id, kind)
        version = self.store.insert_proposed(
            agent_id=self.agent_id, kind=kind, content=content,
            base_version=base[0] if base else None, proposed_by=proposed_by, rationale=rationale,
        )
        self._audit("config_update.proposed", version, {"kind": kind, "status": "proposed"})
        return version

    @staticmethod
    def _validate_persona(content: dict[str, Any]) -> None:
        p = content.get("personality")
        if not isinstance(p, dict):
            raise UpdateError("persona_content_requires_personality")
        values = p.get("values") or {}
        if values.get("protect_humans") != 1.0:
            raise UpdateError("hard_value_immutable:protect_humans")
        if not p.get("boundaries"):
            raise UpdateError("persona_requires_boundaries")
        # Round-trip through the schema so 14 traits / ranges / voice_style are enforced.
        from par.schemas.core import Personality

        Personality.model_validate(p)
        prop = content.get("deviation_propensity")
        if prop is not None and not (0.0 <= float(prop) <= 1.0):
            raise UpdateError("deviation_propensity_out_of_range")

    # -------------------------------------------------------------- approve
    def approve(self, version_id: str, *, approved_by: str, approval_ref: str) -> Version:
        v = self.store.approve(version_id, approved_by=approved_by, approval_ref=approval_ref)
        self._audit("config_update.approved", v, {"approved_by": approved_by, "approval_ref": approval_ref})
        return v

    # ---------------------------------------------------------------- apply
    def apply(self, version_id: str) -> Version:
        v = self.store.get(version_id)
        if v.status != "approved":
            raise UpdateError(f"apply_requires_approved:{v.status}")
        target_dir = self.versions_dir / self.agent_id / v.kind
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{v.version_id}.yaml"
        target.write_text(yaml.safe_dump(v.content, allow_unicode=True, sort_keys=False), encoding="utf-8")
        previous = self.store.current_pointer(self.agent_id, v.kind)
        applied = self.store.mark_applied(
            version_id, applied_path=str(target), previous_version_id=previous[0] if previous else None
        )
        self.store.set_pointer(self.agent_id, v.kind, version_id, str(target))
        self._audit("config_update.applied", applied, {"path": str(target), "previous": previous[0] if previous else None})
        return applied

    def rollback(self, kind: UpdateKind) -> Version:
        pointer = self.store.current_pointer(self.agent_id, kind)
        if pointer is None:
            raise UpdateError("nothing_to_roll_back")
        current = self.store.get(pointer[0])
        if current.previous_version_id:
            prev = self.store.get(current.previous_version_id)
            self.store.set_pointer(self.agent_id, kind, prev.version_id, prev.applied_path or "")
            self.store.mark_rolled_back(current.version_id)
            self._audit("config_update.rolled_back", current, {"restored": prev.version_id})
            return prev
        raise UpdateError("no_previous_version")

    # ------------------------------------------------------------- plumbing
    def _audit(self, event: str, version: Version, extra: dict[str, Any]) -> None:
        record = AuditRecord(
            event_id=f"aud-{uuid.uuid4().hex[:12]}",
            seq=1,
            run_id=f"update-{uuid.uuid4().hex[:8]}",
            agent_id=self.agent_id,
            ts=_TS(),
            kind=event,
            policy_version="policy-1",
            model_identifier="none",
            prompt_version="none",
            tool_version="par-update/0.1",
            gatekeeper_decision={"verdict": "allow", "reasons": [f"{event}:{version.version_id}"]},
        )
        self.audit.append(record)
        _ = extra  # extra context is already inside the version row


def current_persona_path(db_path: str | Path, agent_id: str) -> str | None:
    """Resolve the live persona file, if any version has been applied."""
    path = Path(db_path)
    if not path.exists():
        return None
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute(
            "SELECT path FROM config_pointer WHERE agent_id=? AND kind='persona'", (agent_id,)
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
    return row[0] if row and Path(row[0]).exists() else None


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise UpdateError("yaml_object_required")
    return data


def validate_persona_file(path: str | Path) -> None:
    load_persona(Path(path))  # raises with the schema reason
