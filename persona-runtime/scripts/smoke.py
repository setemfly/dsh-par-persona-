"""Ad-hoc smoke checks during M0 development. Not shipped as a test."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from par.memory.store import MemoryStore
from par.schemas.core import MemoryCandidate

db = Path(__file__).resolve().parents[1] / "data" / "smoke.db"
if db.exists():
    db.unlink()
store = MemoryStore(db)
now = datetime.now(timezone.utc)
store.remember(
    "a",
    MemoryCandidate(
        agent_id="a",
        tier="episodic",
        kind="episode",
        text="用户喜欢拿铁咖啡，不加糖",
        occurred_at=now,
        importance=0.6,
    ),
)
hits = store.recall("a", "拿铁")
print("hits:", [h.text for h in hits])
assert hits and "拿铁" in hits[0].text
print("ok")
