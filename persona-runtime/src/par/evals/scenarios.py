"""Offline eval harness (spec §16, M8).

Scenarios are YAML, assertions are structural on purpose: intent routing, gate
verdicts, execution status, deviation kind, audit growth. Text quality is judged
by humans (docs/evals.md), not by substring matching — string assertions would
reward parroting and punish good paraphrases.

Run with `par eval --file evals/scenarios.yaml`; the provider is forced to
`fake`, so the run is deterministic and network-free.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import yaml

from par.audit.log import AuditLog
from par.config.settings import RuntimeConfig
from par.execution.tools import build_toolbox
from par.identity.persona import load_persona
from par.llm.fake import FakeProvider
from par.llm.registry import ProviderConfig, ProviderRegistry, ProviderSpec
from par.memory.store import MemoryStore
from par.orchestrator.agent import Agent


def _check(result: Any, expect: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if "intent" in expect and result.intent != expect["intent"]:
        failures.append(f"intent {result.intent!r} != {expect['intent']!r}")
    if "deviation" in expect and result.deviation != expect["deviation"]:
        failures.append(f"deviation {result.deviation!r} != {expect['deviation']!r}")
    if "gate_verdict" in expect and result.gate_verdict != expect["gate_verdict"]:
        failures.append(f"gate {result.gate_verdict!r} != {expect['gate_verdict']!r}")
    if expect.get("tool_ok"):
        if not result.executed or any(s["status"] != "ok" for s in result.executed):
            failures.append(f"executed={result.executed!r} expected all ok")
    if expect.get("no_tool"):
        if result.executed:
            failures.append(f"executed={result.executed!r} expected none")
    if expect.get("reply_nonempty") and not result.reply.strip():
        failures.append("empty reply")
    return failures


async def run_scenarios(
    config: RuntimeConfig, scenarios_path: str | Path, *, limit: int | None = None
) -> dict[str, Any]:
    doc = yaml.safe_load(Path(scenarios_path).read_text(encoding="utf-8")) or {}
    scenarios = doc.get("scenarios") or []
    if limit:
        scenarios = scenarios[:limit]

    with tempfile.TemporaryDirectory(prefix="par_eval_") as tmp:
        tmp_path = Path(tmp)
        cfg = config.model_copy(
            update={
                "data_dir": str(tmp_path / "data"),
                "provider": "fake",
                "tools": config.tools.model_copy(
                    update={"workspace": str(tmp_path / "workspace")}
                ),
                "deviation": config.deviation.model_copy(
                    update={"min_sustain_s": 0, "cooldown_s": 0}
                ),
                "memory": config.memory.model_copy(update={"consolidate_every_turns": 10_000}),
            }
        )
        (tmp_path / "workspace").mkdir()
        (tmp_path / "workspace" / "README.md").write_text(
            "# eval workspace\n\n这是一份用于离线场景的只读文件。\n",
            encoding="utf-8",
        )
        (cfg.db_path).parent.mkdir(parents=True, exist_ok=True)
        db = cfg.db_path
        persona = load_persona(config.path(config.persona))
        registry = ProviderRegistry(
            [ProviderSpec(name="fake", config=ProviderConfig(kind="fake", model="fake-1"))]
        )
        registry._instances["fake"] = FakeProvider()  # noqa: SLF001 - deterministic offline run
        store = MemoryStore(db)
        audit = AuditLog(db)
        agent = Agent(
            config=cfg,
            persona=persona,
            store=store,
            audit=audit,
            registry=registry,
            provider_name="fake",
            model=None,
            toolbox=build_toolbox(Path(cfg.tools.workspace), cfg.tools.max_file_bytes),
        )
        results: list[dict[str, Any]] = []
        for scenario in scenarios:
            name = str(scenario.get("name") or "unnamed")
            message = str(scenario.get("message") or "")
            try:
                out = await agent.turn(message)
                failures = _check(out, scenario.get("expect") or {})
                results.append(
                    {
                        "name": name,
                        "ok": not failures,
                        "failures": failures,
                        "intent": out.intent,
                        "deviation": out.deviation,
                        "gate_verdict": out.gate_verdict,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - a scenario crash is a failure row
                results.append({"name": name, "ok": False, "failures": [f"{type(exc).__name__}: {exc}"]})
        await registry.aclose()
        store.close()
        audit.close()
        integrity = "ok"
        check = AuditLog(db)
        try:
            check.verify()
        except Exception as exc:  # noqa: BLE001
            integrity = f"failed: {exc}"
        check.close()

    return {
        "total": len(results),
        "passed": sum(1 for r in results if r["ok"]),
        "audit_integrity": integrity,
        "results": results,
    }


def scenario_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "total": report["total"],
        "passed": report["passed"],
        "failed": [r["name"] for r in report["results"] if not r["ok"]],
        "audit_integrity": report["audit_integrity"],
    }


__all__ = ["run_scenarios", "scenario_summary", "ProviderConfig"]
