"""Gatekeeper (spec §9.2). Deterministic checks, fail closed.

The planner is an LLM, so its output is untrusted input here. Same plan + same
context must yield the same verdict — that is what makes replay meaningful.
"""

from __future__ import annotations

import json
import re

from par.schemas.core import GateDecision, InternalState, PlanProposal, RuleHit, ToolSpec

FORBIDDEN_ARG_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("log_tamper", re.compile(r"(rm\s+-rf?\s+.*(audit|log)|delete\s+.*audit|truncate\s+.*audit)", re.I)),
    ("killswitch_bypass", re.compile(r"(kill_?switch|pause_?handler).*(disable|bypass|ignore)", re.I)),
    ("self_exfil", re.compile(r"(upload|post|send).*(\.env|credentials|token|keychain)", re.I)),
    ("shell_injection", re.compile(r"(\$\(|`[^`]+`\s*\|)")),
]

MAX_ARGS_BYTES = 4096


class PolicyEngine:
    def __init__(
        self,
        *,
        enabled_tools: dict[str, ToolSpec] | None = None,
        policy_version: str = "policy-1",
        envelope_version: str = "env-1",
    ) -> None:
        self.tools = enabled_tools or {}
        self.policy_version = policy_version
        self.envelope_version = envelope_version

    def check(
        self,
        plan: PlanProposal,
        state: InternalState,
        *,
        approvals: set[str] | None = None,
        untrusted_sources: bool = False,
    ) -> GateDecision:
        approvals = approvals or set()
        ph = plan.plan_hash(self.policy_version, self.envelope_version)

        def reject(
            verdict: str, rule_id: str, reason: str, severity: str = "block"
        ) -> GateDecision:
            return GateDecision(
                plan_id=plan.plan_id,
                plan_hash=ph,
                verdict=verdict,  # type: ignore[arg-type]
                approved_steps=[],
                rule_hits=[RuleHit(rule_id=rule_id, severity=severity)],  # type: ignore[arg-type]
                reasons=[reason],
                gate_version="gate/0.1",
            )

        if state.safe_mode:
            return reject("deny", "safe_mode", "runtime is in safe mode", "warn")
        if len(plan.steps) > 8:
            return reject("deny", "plan_too_long", "more than 8 steps")

        for step in plan.steps:
            blob = json.dumps(step.args, ensure_ascii=False)
            if len(blob.encode("utf-8")) > MAX_ARGS_BYTES:
                return reject("deny", "args_oversize", f"{step.step_id}: args too large")
            for rule_id, pattern in FORBIDDEN_ARG_PATTERNS:
                if pattern.search(blob):
                    return reject("deny", rule_id, f"{step.step_id}: forbidden pattern in args")
            if step.tool is None:
                if step.side_effect != "none":
                    return reject("deny", "no_tool_side_effect", f"{step.step_id}: side effect without tool")
                continue
            spec = self.tools.get(step.tool)
            if spec is None:
                return reject("deny", "unknown_tool", f"{step.tool} is not enabled")
            if step.side_effect != spec.side_effect and step.side_effect != "none":
                return reject("deny", "side_effect_mismatch", f"{step.step_id}: declared effect differs from tool")
            needs_approval = spec.requires_approval or step.side_effect == "irreversible"
            if needs_approval and ph not in approvals:
                return reject("ask_user", "approval_required", f"{step.step_id}: explicit approval missing")
            if untrusted_sources and spec.egress and ph not in approvals:
                return reject(
                    "escalate_to_human",
                    "untrusted_egress",
                    "untrusted content would flow to an external tool",
                )

        if any(s.side_effect in ("external", "irreversible") for s in plan.steps) and not approvals:
            return reject("escalate_to_human", "external_effect", "external effect without human approval")

        return GateDecision(
            plan_id=plan.plan_id,
            plan_hash=ph,
            verdict="allow",
            approved_steps=[s.step_id for s in plan.steps],
            rule_hits=[],
            reasons=["all checks passed"],
            gate_version="gate/0.1",
        )
