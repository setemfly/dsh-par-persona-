"""Append-only audit log with a SHA-256 hash chain (spec §13.1).

The agent cannot delete or rewrite records through this API: there is no update
and no delete. Rebuilding the chain from scratch is detectable because every
record commits to its predecessor.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from par.schemas.core import AuditRecord, canonical_json, sha256_hex

GENESIS = "0" * 64

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
  seq          INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id       TEXT NOT NULL,
  agent_id     TEXT NOT NULL,
  ts           TEXT NOT NULL,
  kind         TEXT NOT NULL,
  record_json  TEXT NOT NULL,
  prev_hash    TEXT NOT NULL,
  record_hash  TEXT NOT NULL,
  created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_anchor (
  seq INTEGER PRIMARY KEY,
  record_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


class AuditIntegrityError(RuntimeError):
    pass


class AuditLog:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)

    # ------------------------------------------------------------------ write
    def append(self, record: AuditRecord) -> AuditRecord:
        with self._lock:
            prev = self._head_hash()
            seq = self._next_seq()
            rec = record.model_copy(deep=True)
            rec.seq = seq
            rec.prev_hash = prev
            rec.record_hash = self._hash_for(rec)
            payload = rec.model_dump(mode="json")
            self._conn.execute(
                "INSERT INTO audit (seq, run_id, agent_id, ts, kind, record_json, prev_hash, record_hash, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    seq,
                    rec.run_id,
                    rec.agent_id,
                    rec.ts.isoformat(),
                    rec.kind,
                    canonical_json(payload),
                    prev,
                    rec.record_hash,
                    datetime.now(UTC).isoformat(),
                ),
            )
            if seq % 1000 == 0:
                self._conn.execute(
                    "INSERT OR REPLACE INTO audit_anchor (seq, record_hash, created_at) VALUES (?,?,?)",
                    (seq, rec.record_hash, datetime.now(UTC).isoformat()),
                )
            return rec

    # ----------------------------------------------------------------- verify
    def verify(self) -> dict[str, object]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT seq, record_json, prev_hash, record_hash FROM audit ORDER BY seq"
            ).fetchall()
        prev = GENESIS
        for seq, record_json, prev_hash, record_hash in rows:
            if seq < 1:
                raise AuditIntegrityError(f"bad seq {seq}")
            if prev_hash != prev:
                raise AuditIntegrityError(f"seq {seq}: prev_hash mismatch")
            rec = AuditRecord.model_validate_json(record_json)
            if self._hash_for(rec) != record_hash:
                raise AuditIntegrityError(f"seq {seq}: record_hash mismatch")
            prev = record_hash
        anchors = self._anchors()
        for seq, expected in anchors.items():
            actual = next((h for s, h in self._hashes() if s == seq), None)
            if actual != expected:
                raise AuditIntegrityError(f"anchor mismatch at seq {seq}")
        return {"records": len(rows), "head": prev, "anchors": len(anchors)}

    def head(self) -> dict[str, object]:
        rows = self._conn.execute("SELECT seq, record_hash, ts FROM audit ORDER BY seq DESC LIMIT 1")
        row = rows.fetchone()
        return {"seq": row[0], "hash": row[1], "ts": row[2]} if row else {"seq": 0, "hash": GENESIS}

    def read(self, *, limit: int = 50, offset: int = 0) -> list[dict]:
        rows = self._conn.execute(
            "SELECT seq, kind, ts, record_json FROM audit ORDER BY seq DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [{"seq": s, "kind": k, "ts": t, "record": r} for s, k, t, r in rows]

    def close(self) -> None:
        self._conn.close()

    # ---------------------------------------------------------------- helpers
    def _hash_for(self, rec: AuditRecord) -> str:
        body = rec.model_dump(mode="json")
        body.pop("record_hash", None)
        return sha256_hex(canonical_json(body) + rec.prev_hash)

    def _head_hash(self) -> str:
        row = self._conn.execute("SELECT record_hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        return row[0] if row else GENESIS

    def _next_seq(self) -> int:
        row = self._conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM audit").fetchone()
        return int(row[0])

    def _anchors(self) -> dict[int, str]:
        return {
            int(s): h
            for s, h in self._conn.execute("SELECT seq, record_hash FROM audit_anchor").fetchall()
        }

    def _hashes(self) -> list[tuple[int, str]]:
        return [
            (int(s), h)
            for s, h in self._conn.execute("SELECT seq, record_hash FROM audit").fetchall()
        ]
