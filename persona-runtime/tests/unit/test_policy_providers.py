from __future__ import annotations

from datetime import UTC, datetime

from par.llm.fake import FakeProvider
from par.llm.registry import ProviderConfig, build_provider
from par.policy.engine import PolicyEngine
from par.schemas.core import (
    GateDecision,
    InternalState,
    PlanProposal,
    Step,
    ToolSpec,
)


def _state() -> InternalState:
    return InternalState(ts=datetime.now(UTC), token_budget_remaining=1000)


def _plan(*steps: Step) -> PlanProposal:
    return PlanProposal(plan_id="p1", goal_id="g1", steps=list(steps), rationale="test")


def test_unknown_tool_is_denied() -> None:
    engine = PolicyEngine()
    decision = engine.check(_plan(Step(step_id="s1", intent="x", tool="shell")), _state())
    assert decision.verdict == "deny"
    assert decision.rule_hits[0].rule_id == "unknown_tool"


def test_irreversible_requires_approval() -> None:
    tool = ToolSpec(name="deploy", side_effect="irreversible", scopes=["deploy"], requires_approval=True)
    engine = PolicyEngine(enabled_tools={"deploy": tool})
    step = Step(step_id="s1", intent="deploy", tool="deploy", side_effect="irreversible")
    decision = engine.check(_plan(step), _state())
    assert decision.verdict == "ask_user"


def test_forbidden_args_denied() -> None:
    tool = ToolSpec(name="run", side_effect="write", scopes=[])
    engine = PolicyEngine(enabled_tools={"run": tool})
    step = Step(step_id="s1", intent="rm", tool="run", side_effect="write", args={"cmd": "rm -rf /var/log/audit"})
    assert engine.check(_plan(step), _state()).verdict == "deny"


def test_allow_requires_steps() -> None:
    tool = ToolSpec(name="read_file", side_effect="read", scopes=[])
    engine = PolicyEngine(enabled_tools={"read_file": tool})
    step = Step(step_id="s1", intent="read", tool="read_file", side_effect="read")
    decision = engine.check(_plan(step), _state())
    assert isinstance(decision, GateDecision) and decision.verdict == "allow"


def test_fake_provider_scripted() -> None:
    async def run() -> str:
        p = FakeProvider(script=["你好"])
        c = await p.chat([])
        return c.text

    import asyncio

    assert asyncio.run(run()) == "你好"


def test_build_provider_kinds() -> None:
    assert isinstance(build_provider("x", ProviderConfig(kind="fake", model="f")), FakeProvider)
