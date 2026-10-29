from __future__ import annotations

import asyncio
from pathlib import Path

from par.evals.scenarios import run_scenarios, scenario_summary


def test_all_scenarios_pass(config) -> None:
    root = Path(__file__).resolve().parents[2]
    report = asyncio.run(run_scenarios(config, root / "evals" / "scenarios.yaml"))
    summary = scenario_summary(report)
    assert summary["total"] >= 8
    assert summary["failed"] == [], summary["failed"]
    assert summary["audit_integrity"] == "ok"


def test_scenarios_are_structural() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "evals" / "scenarios.yaml").read_text(encoding="utf-8")
    assert "expect:" in text
    # No wording assertions: eval must not reward parroting.
    assert "reply_contains" not in text
