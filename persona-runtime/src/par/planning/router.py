"""Deterministic planner (spec §9.1, M4).

v0 planning is a rule router, not an LLM. That is intentional: the plan contract
(goal, steps, side effects, preconditions) and the gatekeeper have to be proven
before a model is allowed to fill them in. When an intent matches, the router
emits at most one tool step; everything else stays a pure conversation turn.

Only tools present in `ToolBox` can appear here, so the planner cannot invent
capability — an LLM planner would run into the same gate afterwards.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from par.execution.tools import ToolBox
from par.schemas.core import PlanProposal, Step

ARITH_RE = re.compile(r"[0-9(][0-9\s.+\-*/()%]{1,120}")
CALC_VERB_RE = re.compile(r"(算一下|计算|帮我算|求值|compute|calculate|evaluate)", re.I)
TIME_RE = re.compile(r"(现在几[点點]|几[点點]了|当前时间|现在的时间|what\s+time|current\s+time)", re.I)
FILE_RE = re.compile(
    r"(?:读|打开|看一下|查看|cat|read)\s*(?:一下)?\s*(?:文件)?\s*[「\"'“]?"
    r"([^\s\"'”」]+\.[A-Za-z0-9]{1,8})"
)
FILE_EXT_ALLOWED = {"md", "txt", "py", "json", "yaml", "yml", "toml", "csv"}


@dataclass
class RouterDecision:
    plan: PlanProposal | None
    intent: str


def _expr_from(text: str) -> str | None:
    if not any(ch.isdigit() for ch in text):
        return None
    best: str | None = None
    for match in ARITH_RE.finditer(text):
        candidate = match.group(0).strip()
        if any(op in candidate for op in "+-*/%()"):
            if best is None or len(candidate) > len(best):
                best = candidate
    return best


def route(text: str, toolbox: ToolBox, *, goal_id: str = "chat_turn") -> RouterDecision:
    plan_id = f"plan_{uuid.uuid4().hex[:12]}"
    names = toolbox.specs

    if "time.now" in names and TIME_RE.search(text):
        return RouterDecision(
            plan=PlanProposal(
                plan_id=plan_id,
                goal_id=goal_id,
                steps=[
                    Step(
                        step_id="s1",
                        intent="report current local time",
                        tool="time.now",
                        args={},
                        side_effect="none",
                        timeout_s=2.0,
                    )
                ],
                rationale="deterministic_router:time_query",
                risk_tags=["low"],
            ),
            intent="time",
        )

    if "calc.eval" in names and CALC_VERB_RE.search(text):
        expr = _expr_from(text)
        if expr:
            return RouterDecision(
                plan=PlanProposal(
                    plan_id=plan_id,
                    goal_id=goal_id,
                    steps=[
                        Step(
                            step_id="s1",
                            intent="evaluate arithmetic expression",
                            tool="calc.eval",
                            args={"expression": expr},
                            side_effect="none",
                            timeout_s=2.0,
                        )
                    ],
                    rationale="deterministic_router:arithmetic",
                    risk_tags=["low"],
                ),
                intent="calc",
            )

    if "fs.read" in names:
        match = FILE_RE.search(text)
        if match:
            candidate = match.group(1)
            ext = candidate.rsplit(".", 1)[-1].lower()
            if ext in FILE_EXT_ALLOWED:
                return RouterDecision(
                    plan=PlanProposal(
                        plan_id=plan_id,
                        goal_id=goal_id,
                        steps=[
                            Step(
                                step_id="s1",
                                intent=f"read workspace file {candidate}",
                                tool="fs.read",
                                args={"path": candidate},
                                side_effect="read",
                                timeout_s=10.0,
                            )
                        ],
                        rationale="deterministic_router:file_read",
                        risk_tags=["read_only"],
                    ),
                    intent="read_file",
                )

    return RouterDecision(plan=None, intent="chat")
