from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from par.execution.executor import Executor
from par.execution.tools import ToolBox, ToolError, build_toolbox, calc_eval
from par.schemas.core import GateDecision, PlanProposal, Step, ToolSpec


def _gate(plan: PlanProposal, verdict: str = "allow") -> GateDecision:
    return GateDecision(
        plan_id=plan.plan_id,
        plan_hash=plan.plan_hash("policy-1", "env-1"),
        verdict=verdict,  # type: ignore[arg-type]
        approved_steps=[s.step_id for s in plan.steps] if verdict == "allow" else [],
        reasons=["test"],
    )


def _plan(tool: str, args: dict, side_effect: str = "none") -> PlanProposal:
    return PlanProposal(
        plan_id="plan_x",
        goal_id="goal_x",
        steps=[
            Step(
                step_id="s1",
                intent="test",
                tool=tool,
                args=args,
                side_effect=side_effect,  # type: ignore[arg-type]
                timeout_s=1.0,
            )
        ],
        rationale="test",
    )


def test_calc_eval_arithmetic() -> None:
    assert calc_eval({"expression": "(12+8)*3/5"})["value"] == pytest.approx(12.0)
    with pytest.raises(ToolError):
        calc_eval({"expression": "__import__('os').system('id')"})


def test_file_sandbox_blocks_escape(tmp_path: Path) -> None:
    (tmp_path / "ok.md").write_text("hello", encoding="utf-8")
    box = build_toolbox(tmp_path)
    read = box.handler("fs.read")
    assert read({"path": "ok.md"})["text"] == "hello"
    with pytest.raises(ToolError, match="path_outside_workspace"):
        read({"path": "../outside.md"})


def test_executor_runs_approved_step(tmp_path: Path) -> None:
    box = build_toolbox(tmp_path)
    ex = Executor(box, agent_id="a")
    plan = _plan("calc.eval", {"expression": "2+3"})
    out = asyncio.run(ex.run(plan, _gate(plan)))
    assert out.ok and out.results[0].status == "ok"
    assert out.results[0].observation is not None
    assert out.results[0].observation.content["value"] == pytest.approx(5.0)


def test_executor_refuses_unapproved(tmp_path: Path) -> None:
    box = build_toolbox(tmp_path)
    ex = Executor(box, agent_id="a")
    plan = _plan("calc.eval", {"expression": "2+3"})
    out = asyncio.run(ex.run(plan, _gate(plan, verdict="ask_user")))
    assert out.results[0].status == "denied"


def test_executor_honours_idempotency_key(tmp_path: Path) -> None:
    box = build_toolbox(tmp_path)
    ex = Executor(box, agent_id="a")
    plan = _plan("time.now", {})
    plan.steps[0].idempotency_key = "k1"
    gate = _gate(plan)
    first = asyncio.run(ex.run(plan, gate))
    second = asyncio.run(ex.run(plan, gate))
    assert first.results[0].observation is not None
    assert second.results[0].observation is first.results[0].observation


def test_executor_timeout(monkeypatch) -> None:
    box = ToolBox()
    box.register(ToolSpec(name="slow", side_effect="none"), lambda args: time.sleep(0.2) or {})
    ex = Executor(box, agent_id="a")
    plan = _plan("slow", {})
    plan.steps[0].timeout_s = 0.05
    out = asyncio.run(ex.run(plan, _gate(plan)))
    assert out.results[0].status == "timeout"


def test_executor_kill_switch(tmp_path: Path) -> None:
    box = build_toolbox(tmp_path)
    ex = Executor(box, agent_id="a")
    ex.kill()
    plan = _plan("time.now", {})
    out = asyncio.run(ex.run(plan, _gate(plan)))
    assert out.aborted and out.results[0].status == "skipped"


def test_executor_side_effect_mismatch(tmp_path: Path) -> None:
    box = build_toolbox(tmp_path)
    ex = Executor(box, agent_id="a")
    plan = _plan("fs.read", {"path": "x.md"}, side_effect="write")
    out = asyncio.run(ex.run(plan, _gate(plan)))
    assert out.results[0].status == "failed"
    assert out.results[0].error is not None
    assert out.results[0].error["type"] == "side_effect_mismatch"


def test_toolbox_describe_covers_builtins(tmp_path: Path) -> None:
    names = {t["name"] for t in build_toolbox(tmp_path).describe()}
    assert {"time.now", "calc.eval", "fs.read"} <= names


def test_gate_decision_requires_approved_steps_for_allow() -> None:
    with pytest.raises(ValueError):
        GateDecision(
            plan_id="p", plan_hash="h", verdict="allow", reasons=[], approved_steps=[]
        )


def test_step_timestamp_shape(tmp_path: Path) -> None:
    box = build_toolbox(tmp_path)
    ex = Executor(box, agent_id="a")
    plan = _plan("time.now", {})
    res = asyncio.run(ex.run(plan, _gate(plan))).results[0]
    assert res.started_at.tzinfo is not None
    assert res.ended_at >= res.started_at
    assert res.ended_at <= datetime.now(UTC)
