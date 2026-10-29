"""SQLite memory store (spec §7).

v0 deliberately keeps one file and one process: FTS5 for lexical recall,
deterministic scoring, no embeddings until an embedding provider is configured
(M2). The scoring shape matches §7.3 so the semantic term can drop in later.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from par.schemas.core import MemoryCandidate, MemoryRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (
  memory_id    TEXT PRIMARY KEY,
  agent_id     TEXT NOT NULL,
  user_scope   TEXT,
  tier         TEXT NOT NULL,
  kind         TEXT NOT NULL,
  text         TEXT NOT NULL,
  embedding_json TEXT,
  entities_json  TEXT NOT NULL DEFAULT '[]',
  occurred_at  TEXT NOT NULL,
  recorded_at  TEXT NOT NULL,
  valid_from   TEXT NOT NULL,
  valid_to     TEXT,
  ingested_at  TEXT NOT NULL,
  importance   REAL NOT NULL,
  confidence   REAL NOT NULL,
  sensitivity  TEXT NOT NULL,
  retention    TEXT NOT NULL,
  affect_json  TEXT NOT NULL DEFAULT '{}',
  provenance_json TEXT NOT NULL DEFAULT '[]',
  status       TEXT NOT NULL,
  version      INTEGER NOT NULL DEFAULT 1,
  superseded_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_memory_agent_status ON memory(agent_id, status);
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
  memory_id UNINDEXED, text, tokenize='unicode61'
);
CREATE TABLE IF NOT EXISTS commitment (
  commitment_id TEXT PRIMARY KEY,
  agent_id   TEXT NOT NULL,
  counterparty TEXT NOT NULL DEFAULT 'user',
  canonical_key TEXT NOT NULL,
  text       TEXT NOT NULL,
  status     TEXT NOT NULL,
  due_at     TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(agent_id, canonical_key)
);
CREATE TABLE IF NOT EXISTS state_kv (
  agent_id TEXT NOT NULL,
  key      TEXT NOT NULL,
  value    TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (agent_id, key)
);
"""

W_LEXICAL = 0.35
W_RECENCY = 0.20
W_IMPORTANCE = 0.20
W_GOAL = 0.15
W_CONFIDENCE = 0.10


def _now() -> datetime:
    return datetime.now(UTC)


class MemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)

    # ------------------------------------------------------------------ write
    def remember(self, agent_id: str, cand: MemoryCandidate) -> MemoryRecord:
        now = _now()
        rec = MemoryRecord(
            memory_id=f"mem_{uuid.uuid4().hex[:12]}",
            agent_id=agent_id,
            user_scope=cand.user_scope,
            tier=cand.tier,
            kind=cand.kind,
            text=cand.text,
            entities=cand.entities,
            occurred_at=cand.occurred_at,
            recorded_at=now,
            valid_from=cand.occurred_at,
            ingested_at=now,
            importance=cand.importance,
            confidence=cand.confidence,
            sensitivity=cand.sensitivity,
            retention=cand.retention,
            affect_tag=cand.affect_tag,
            provenance=cand.provenance,
            status="active",
            version=1,
        )
        with self._lock:
            # Idempotent write: an identical active record is reinforced, not duplicated.
            # Long chats replay near-identical turns; without this every replay would
            # surface as a separate memory in `recall`.
            existing = self._conn.execute(
                "SELECT memory_id, importance, confidence FROM memory"
                " WHERE agent_id=? AND kind=? AND text=? AND status='active' LIMIT 1",
                (agent_id, rec.kind, rec.text),
            ).fetchone()
            if existing is not None:
                self._conn.execute(
                    "UPDATE memory SET importance=?, confidence=?, version=version+1"
                    " WHERE memory_id=?",
                    (
                        max(existing["importance"], rec.importance),
                        max(existing["confidence"], rec.confidence),
                        existing["memory_id"],
                    ),
                )
                self._conn.commit()
                refreshed = self.get(existing["memory_id"])
                assert refreshed is not None
                return refreshed
            self._conn.execute(
                """INSERT INTO memory (memory_id, agent_id, user_scope, tier, kind, text, entities_json,
                    occurred_at, recorded_at, valid_from, valid_to, ingested_at, importance, confidence,
                    sensitivity, retention, affect_json, provenance_json, status, version)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    rec.memory_id, agent_id, rec.user_scope, rec.tier, rec.kind, rec.text,
                    json.dumps(rec.entities, ensure_ascii=False),
                    rec.occurred_at.isoformat(), rec.recorded_at.isoformat(),
                    rec.valid_from.isoformat(), None, rec.ingested_at.isoformat(),
                    rec.importance, rec.confidence, rec.sensitivity, rec.retention,
                    json.dumps(rec.affect_tag or {}, ensure_ascii=False),
                    json.dumps(rec.provenance, ensure_ascii=False),
                    rec.status, rec.version,
                ),
            )
            self._conn.execute(
                "INSERT INTO memory_fts (memory_id, text) VALUES (?,?)",
                (rec.memory_id, _segment_cjk(rec.text)),
            )
        return rec

    def supersede(self, old_id: str, new_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE memory SET status='superseded', superseded_by=? WHERE memory_id=?",
                (new_id, old_id),
            )

    def quarantine(self, memory_id: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE memory SET status='quarantined' WHERE memory_id=?", (memory_id,))

    def forget(self, memory_id: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE memory SET status='retracted' WHERE memory_id=?", (memory_id,))

    # ------------------------------------------------------------------- read
    def get(self, memory_id: str) -> MemoryRecord | None:
        row = self._conn.execute("SELECT * FROM memory WHERE memory_id=?", (memory_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def recall(
        self,
        agent_id: str,
        query: str,
        *,
        k: int = 12,
        goal_terms: list[str] | None = None,
        viewer: str = "agent",
    ) -> list[MemoryRecord]:
        """Rank active memories; lexical rank is a monotone position score."""
        terms = " OR ".join(_fts_terms(query))
        rows: list[sqlite3.Row] = []
        lexical: dict[str, float] = {}
        if terms:
            with self._lock:
                rows = self._conn.execute(
                    """SELECT m.*, bm25(memory_fts) AS rank FROM memory_fts
                       JOIN memory m ON m.memory_id = memory_fts.memory_id
                       WHERE memory_fts MATCH ? AND m.agent_id=? AND m.status='active'
                       ORDER BY rank LIMIT 100""",
                    (terms, agent_id),
                ).fetchall()
            n = max(len(rows), 1)
            for i, row in enumerate(rows):
                lexical[str(row["memory_id"])] = 1.0 - (i / n)
        else:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT * FROM memory WHERE agent_id=? AND status='active' ORDER BY importance DESC LIMIT 100",
                    (agent_id,),
                ).fetchall()
        if not rows:
            return []
        now = _now()
        goal_terms = [t.lower() for t in (goal_terms or [])]
        scored: list[tuple[float, MemoryRecord]] = []
        for row in rows:
            rec = self._row_to_record(row)
            if viewer != "operator" and rec.sensitivity == "restricted":
                continue
            lex = lexical.get(rec.memory_id, 0.0)
            goal = 1.0 if any(t in rec.text.lower() for t in goal_terms) else 0.0
            score = (
                W_LEXICAL * lex
                + W_RECENCY * _recency(now, rec)
                + W_IMPORTANCE * rec.importance
                + W_GOAL * goal
                + W_CONFIDENCE * rec.confidence
            )
            scored.append((score, rec))
        scored.sort(key=lambda p: p[0], reverse=True)
        return [rec for _, rec in scored[:k]]

    # ------------------------------------------------------------ commitments
    def upsert_commitment(
        self,
        agent_id: str,
        canonical_key: str,
        text: str,
        *,
        counterparty: str = "user",
        due_at: datetime | None = None,
    ) -> None:
        now = _now().isoformat()
        with self._lock:
            self._conn.execute(
                """INSERT INTO commitment (commitment_id, agent_id, counterparty, canonical_key, text, status, due_at, created_at, updated_at)
                   VALUES (?,?,?,?,?,'open',?,?,?)
                   ON CONFLICT(agent_id, canonical_key) DO UPDATE SET
                     text=excluded.text, due_at=excluded.due_at, updated_at=excluded.updated_at""",
                (f"cm_{uuid.uuid4().hex[:10]}", agent_id, counterparty, canonical_key, text,
                 due_at.isoformat() if due_at else None, now, now),
            )

    def commitments(self, agent_id: str, *, status: str = "open") -> list[dict]:
        rows = self._conn.execute(
            "SELECT canonical_key, text, status, due_at FROM commitment WHERE agent_id=? AND status=? ORDER BY created_at",
            (agent_id, status),
        ).fetchall()
        return [{"key": r["canonical_key"], "text": r["text"], "status": r["status"], "due_at": r["due_at"]} for r in rows]

    # ------------------------------------------------------------- state kv
    def get_state(self, agent_id: str, key: str) -> dict | None:
        row = self._conn.execute(
            "SELECT value FROM state_kv WHERE agent_id=? AND key=?", (agent_id, key)
        ).fetchone()
        return json.loads(row["value"]) if row else None

    def set_state(self, agent_id: str, key: str, value: dict) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO state_kv (agent_id, key, value, updated_at) VALUES (?,?,?,?)
                   ON CONFLICT(agent_id, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (agent_id, key, json.dumps(value, ensure_ascii=False), _now().isoformat()),
            )

    def counts(self, agent_id: str) -> dict[str, int]:
        total = self._conn.execute("SELECT COUNT(*) c FROM memory WHERE agent_id=?", (agent_id,)).fetchone()["c"]
        active = self._conn.execute(
            "SELECT COUNT(*) c FROM memory WHERE agent_id=? AND status='active'", (agent_id,)
        ).fetchone()["c"]
        return {"total": int(total), "active": int(active)}

    def close(self) -> None:
        self._conn.close()

    # ---------------------------------------------------------------- helper
    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
        affect = json.loads(row["affect_json"] or "{}")
        return MemoryRecord(
            memory_id=row["memory_id"],
            agent_id=row["agent_id"],
            user_scope=row["user_scope"],
            tier=row["tier"],
            kind=row["kind"],
            text=row["text"],
            entities=json.loads(row["entities_json"] or "[]"),
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
            valid_from=datetime.fromisoformat(row["valid_from"]),
            valid_to=datetime.fromisoformat(row["valid_to"]) if row["valid_to"] else None,
            ingested_at=datetime.fromisoformat(row["ingested_at"]),
            importance=row["importance"],
            confidence=row["confidence"],
            sensitivity=row["sensitivity"],
            retention=row["retention"],
            affect_tag=affect or None,
            provenance=json.loads(row["provenance_json"] or "[]"),
            status=row["status"],
            version=row["version"],
        )


def _segment_cjk(text: str) -> str:
    """Space-separate CJK characters so unicode61 yields per-character tokens.

    unicode61 treats a run of Han characters as one token, which makes substring
    recall ("拿铁" inside "用户喜欢拿铁") impossible. Segmenting both sides keeps
    the FTS index small and the query syntax safe.
    """
    out: list[str] = []
    for ch in text:
        if _is_cjk(ch):
            out.append(f" {ch} ")
        else:
            out.append(ch)
    return "".join(out)


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x4E00 <= cp <= 0x9FFF  # CJK Unified Ideographs
        or 0x3400 <= cp <= 0x4DBF  # Extension A
        or 0x3040 <= cp <= 0x30FF  # Hiragana / Katakana
        or 0xAC00 <= cp <= 0xD7AF  # Hangul syllables
    )


def _fts_terms(query: str) -> list[str]:
    """Quote tokens so user text cannot inject FTS5 syntax."""
    cleaned = "".join(c if (c.isalnum() or c in " _-") else " " for c in _segment_cjk(query))
    tokens = [t for t in cleaned.split() if t]
    return [f'"{t}"' for t in tokens[:16]]


def _recency(now: datetime, rec: MemoryRecord) -> float:
    anchor = rec.occurred_at or rec.recorded_at
    days = max((now - anchor).total_seconds() / 86400.0, 0.0)
    return 1.0 / (1.0 + days / 30.0)
