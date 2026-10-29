from __future__ import annotations

from datetime import UTC, datetime

import pytest

from par.audit.log import AuditIntegrityError, AuditLog
from par.schemas.core import AuditRecord


def _record(i: int) -> AuditRecord:
    return AuditRecord(
        event_id=f"e{i}",
        seq=1,
        run_id="r1",
        agent_id="a",
        ts=datetime.now(UTC),
        kind="turn",
    )


def test_chain_verifies(tmp_path) -> None:
    log = AuditLog(tmp_path / "audit.db")
    for i in range(5):
        log.append(_record(i))
    report = log.verify()
    assert report["records"] == 5
    log.close()


def test_tampering_is_detected(tmp_path) -> None:
    log = AuditLog(tmp_path / "audit.db")
    for i in range(3):
        log.append(_record(i))
    conn = log._conn
    conn.execute("UPDATE audit SET record_json = replace(record_json, '\"turn\"', '\"gate\"') WHERE seq = 2")
    with pytest.raises(AuditIntegrityError):
        log.verify()
    log.close()


def test_prev_hash_links(tmp_path) -> None:
    log = AuditLog(tmp_path / "audit.db")
    a = log.append(_record(1))
    b = log.append(_record(2))
    assert b.prev_hash == a.record_hash
    log.close()
