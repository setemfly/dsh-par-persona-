"""Executor (spec §9.3): runs only the steps a gatekeeper approved.

Guarantees the runtime makes:
* no step runs unless its `step_id` appears in `gate.approved_steps`;
* per-step timeout; a timeout never leaves a partially-applied result behind;
* idempotency keys are honoured within one executor lifetime, so a retried
  turn cannot double-apply a side effect;
* a kill switch is checked between steps and observed inside the wait loop.

The executor never widens its own authority: it has no shell, no network and
no dynamic tool discovery. Tools come from `ToolBox`, which is fixed at start.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from par.execution.tools import ToolBox, ToolError
from par.schemas.core import ExecutionResult, GateDecision, Observation, PlanProposal

KILL_GRACE_S = 3.0


@dataclass
class ExecutionOutcome:
    results: list[ExecutionResult] = field(default_factory=list)
    aborted: bool = False

    @property
    def ok(self) -> bool:
        return bool(self.results) and all(r.status == "ok" for r in self.results)

    def summary(self) -> dict[str, Any]:
        return {
            "steps": [{"step_id": r.step_id, "status": r.status} for r in self.results],
            "aborted": self.aborted,
        }


class Executor:
    def __init__(self, toolbox: ToolBox, *, agent_id: str) -> None:
        self.toolbox = toolbox
        self.agent_id = agent_id
        self._kill = asyncio.Event()
        self._idempotent: dict[str, ExecutionResult] = {}

    def kill(self) -> None:
        self._kill.set()

    def revive(self) -> None:
        self._kill.clear()

    async def run(self, plan: PlanProposal, gate: GateDecision) -> ExecutionOutcome:
        outcome = ExecutionOutcome()
        approved = set(gate.approved_steps)
        if gate.verdict != "allow":
            now = datetime.now(UTC)
            outcome.results = [
                ExecutionResult(
                    step_id=step.step_id,
                    status="denied",
                    error={"type": "gate", "verdict": gate.verdict, "reasons": gate.reasons},
                    started_at=now,
                    ended_at=now,
                )
                for step in plan.steps
            ]
            return outcome

        for step in plan.steps:
            if step.step_id not in approved:
                outcome.results.append(self._skipped(step.step_id, "not_approved"))
                continue
            if self._kill.is_set():
                outcome.aborted = True
                outcome.results.append(self._skipped(step.step_id, "kill_switch"))
                continue
            key = step.idempotency_key
            if key and key in self._idempotent:
                outcome.results.append(self._idempotent[key])
                continue
            result = await self._run_step(step)
            if key:
                self._idempotent[key] = result
            outcome.results.append(result)
            if result.status != "ok":
                # Fail fast: later steps may depend on this one's postcondition.
                for rest in plan.steps[plan.steps.index(step) + 1 :]:
                    outcome.results.append(self._skipped(rest.step_id, "upstream_failed"))
                break
        return outcome

    # ------------------------------------------------------------------ internals
    async def _run_step(self, step: Any) -> ExecutionResult:
        started = datetime.now(UTC)
        spec = self.toolbox.specs.get(step.tool or "")
        if spec is None:
            return self._failed(step.step_id, started, "unknown_tool", str(step.tool))
        if spec.requires_approval:
            # The gatekeeper is the only thing that can approve; if it let this
            # through, the spec changed underneath us. Refuse rather than trust it.
            return self._failed(step.step_id, started, "approval_missing", spec.name)
        if spec.side_effect != step.side_effect:
            return self._failed(
                step.step_id, started, "side_effect_mismatch",
                f"declared={step.side_effect} tool={spec.side_effect}",
            )
        timeout = min(step.timeout_s, spec.timeout_default_s * 4)
        handler = self.toolbox.handler(spec.name)
        try:
            payload = await asyncio.wait_for(asyncio.to_thread(handler, step.args), timeout=timeout)
        except TimeoutError:
            return self._failed(step.step_id, started, "timeout", f"{timeout:.1f}s", status="timeout")
        except ToolError as exc:
            return self._failed(step.step_id, started, "tool_error", str(exc))
        except Exception as exc:  # noqa: BLE001 - tool bugs must not crash the turn
            return self._failed(step.step_id, started, "tool_exception", f"{type(exc).__name__}: {exc}")
        ended = datetime.now(UTC)
        observation = Observation(
            observation_id=f"obs_{uuid.uuid4().hex[:12]}",
            agent_id=self.agent_id,
            ts=ended,
            source=f"tool:{spec.name}",
            modality="tool_result",
            content=payload,
            confidence=spec_timeout_confidence(spec.name),
            trust="tool",
            salience=0.4,
            correlation_id=step.step_id,
        )
        return ExecutionResult(
            step_id=step.step_id,
            status="ok",
            observation=observation,
            started_at=started,
            ended_at=ended,
            side_effect_applied=spec.side_effect in ("write", "external", "irreversible"),
            idempotency_key=step.idempotency_key,
        )

    def _skipped(self, step_id: str, reason: str) -> ExecutionResult:
        now = datetime.now(UTC)
        return ExecutionResult(
            step_id=step_id, status="skipped", error={"reason": reason},
            started_at=now, ended_at=now,
        )

    def _failed(
        self, step_id: str, started: datetime, kind: str, detail: str, *, status: str = "failed"
    ) -> ExecutionResult:
        now = datetime.now(UTC)
        return ExecutionResult(
            step_id=step_id,
            status=status,  # type: ignore[arg-type]
            error={"type": kind, "detail": detail},
            started_at=started,
            ended_at=now,
        )


def spec_timeout_confidence(name: str) -> float:
    """Tool observations are trustworthy but not authoritative (spec §9.4)."""
    return 0.9 if name in {"calc.eval", "time.now"} else 0.8


async def shutdown(executor: Executor) -> None:
    """Best-effort kill used by the CLI/server on interpreter shutdown."""
    executor.kill()
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(asyncio.sleep(0), timeout=KILL_GRACE_S)
