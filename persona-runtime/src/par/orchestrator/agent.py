"""One turn, end to end (spec §12.4).

    SENSE -> RECALL -> APPRAISE -> PLAN -> GATE -> EXECUTE -> DEVIATE
          -> EXPRESS -> AUDIT -> CONSOLIDATE

The chat path never bypasses the gate: if the deterministic router proposes a
tool step, the plan goes through `PolicyEngine` and only the approved steps reach
`Executor`. The deviation judge runs after execution and before expression, so
its instruction can shape the reply while the facts are already fixed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from par.affect import appraisal as appraiser
from par.affect.engine import TickResult, initial_state
from par.affect.engine import update as affect_update
from par.audit.log import AuditLog
from par.config.settings import RuntimeConfig
from par.execution.executor import ExecutionOutcome, Executor
from par.execution.tools import ToolBox, build_toolbox
from par.expression.prompt import ExpressionContext, build_messages
from par.expression.verifier import VerifierResult, verify_reply
from par.identity.persona import PersonaCard, load_persona
from par.llm.base import ChatMessage
from par.llm.registry import ProviderRegistry, load_providers_file
from par.memory.store import MemoryStore
from par.planning.router import route
from par.policy.deviation import DeviationJudge, Judgment
from par.policy.engine import PolicyEngine
from par.schemas.core import (
    AffectState,
    AuditRecord,
    DeviationEnvelope,
    InternalState,
    MemoryCandidate,
    MemoryRecord,
    Observation,
)

PROMPT_VERSION = "expr/0.2"


@dataclass
class TurnResult:
    reply: str
    observation: Observation
    memories: list[MemoryRecord] = field(default_factory=list)
    verifier: VerifierResult | None = None
    audit_seq: int = 0
    affect_version: int = 0
    labels: dict[str, float] = field(default_factory=dict)
    intent: str = "chat"
    plan_id: str | None = None
    gate_verdict: str | None = None
    executed: list[dict[str, Any]] = field(default_factory=list)
    deviation: str | None = None


class Agent:
    def __init__(
        self,
        *,
        config: RuntimeConfig,
        persona: PersonaCard,
        store: MemoryStore,
        audit: AuditLog,
        registry: ProviderRegistry,
        provider_name: str,
        model: str | None,
        toolbox: ToolBox | None = None,
    ) -> None:
        self.config = config
        self.persona = persona
        self.store = store
        self.audit = audit
        self.registry = registry
        self.provider_name = provider_name
        self.model_override = model
        self.agent_id = config.agent_id
        self.run_id = f"run_{datetime.now(UTC):%Y%m%d%H%M%S}_{uuid.uuid4().hex[:6]}"
        self.history: list[ChatMessage] = []
        self.turn_no = 0

        workspace = config.path(config.tools.workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        self.toolbox = toolbox or (
            build_toolbox(workspace, config.tools.max_file_bytes)
            if config.tools.enabled
            else ToolBox()
        )
        self.executor = Executor(self.toolbox, agent_id=self.agent_id)
        self.gatekeeper = PolicyEngine(
            enabled_tools=self.toolbox.specs,
            policy_version="policy-1",
            envelope_version=f"env/{persona.personality.version}",
        )
        envelope = DeviationEnvelope(
            version=f"env/{persona.personality.version}",
            max_per_hour=config.deviation.max_per_hour,
            cooldown_s=config.deviation.cooldown_s,
            min_sustain_s=config.deviation.min_sustain_s,
            deviation_propensity=config.deviation.propensity,
        )
        self.deviation = DeviationJudge(envelope, store, agent_id=self.agent_id)

        saved = self.store.get_state(self.agent_id, "affect")
        if saved:
            self.affect: AffectState = AffectState.model_validate(saved["state"])
            self.threat_ema = float(saved.get("threat_ema", 0.0))
        else:
            self.affect = initial_state(persona.personality.baseline_affect)
            self.threat_ema = 0.0
        self.labels: dict[str, float] = dict(self.affect.discrete)

    # --------------------------------------------------------------- factory
    @classmethod
    def create(
        cls,
        config_path: str | Path,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> Agent:
        from par.config.settings import load_config

        config = load_config(config_path)
        db = config.db_path
        db.parent.mkdir(parents=True, exist_ok=True)
        # A governed update may have repointed the live persona; prefer that file.
        from par.updates.manager import current_persona_path

        live = current_persona_path(db, config.agent_id)
        persona = load_persona(Path(live) if live else config.path(config.persona))
        registry = ProviderRegistry(load_providers_file(config.path(config.providers_file)))
        store = MemoryStore(db)
        audit = AuditLog(db)
        return cls(
            config=config,
            persona=persona,
            store=store,
            audit=audit,
            registry=registry,
            provider_name=provider or config.provider,
            model=model or config.model,
        )

    # ------------------------------------------------------------------ turn
    async def turn(self, user_text: str) -> TurnResult:
        now = datetime.now(UTC)
        self.turn_no += 1
        observation = Observation(
            observation_id=f"obs_{uuid.uuid4().hex[:10]}",
            agent_id=self.agent_id,
            ts=now,
            source="user",
            modality="text",
            content={"text": user_text},
            confidence=0.9,
            trust="user",
            salience=_salience(user_text),
            correlation_id=self.run_id,
        )

        memories = self.store.recall(self.agent_id, user_text, k=self.config.memory.recall_k)
        commitments = self.store.commitments(self.agent_id)

        ap_value_threat = 0.0
        if self.config.affect.enabled:
            ap = appraiser.appraise(
                observation.observation_id, user_text, salience=observation.salience
            )
            ap_value_threat = ap.value_threat
            tick: TickResult = affect_update(
                self.affect,
                baseline=self.persona.personality.baseline_affect,
                appraisal=ap,
                salience=observation.salience,
                personality=self.persona.personality,
                threat_ema=self.threat_ema,
                now=now,
            )
            self.affect = tick.state
            self.threat_ema = tick.threat_ema
            self.labels = tick.labels
            self.store.set_state(
                self.agent_id,
                "affect",
                {"state": self.affect.model_dump(mode="json"), "threat_ema": self.threat_ema},
            )

        # PLAN -> GATE -> EXECUTE
        decision = route(user_text, self.toolbox)
        execution: ExecutionOutcome | None = None
        gate_verdict: str | None = None
        plan_id: str | None = None
        extra_lines: list[str] = []
        executed_tools: list[str] = []
        if decision.plan is not None:
            plan = decision.plan
            plan_id = plan.plan_id
            state = InternalState(ts=now)
            gate = self.gatekeeper.check(plan, state, approvals=set())
            gate_verdict = gate.verdict
            execution = await self.executor.run(plan, gate)
            tool_name = plan.steps[0].tool or ""
            for result in execution.results:
                if result.status == "ok" and result.observation is not None:
                    executed_tools.append(tool_name)
                    extra_lines.append(f"[工具结果] {tool_name} -> {result.observation.content}")
                elif result.status in ("denied", "failed", "timeout"):
                    extra_lines.append(
                        f"[工具失败] {tool_name or 'step'} {result.status}: {result.error}"
                    )

        # DEVIATE (persona stance, bounded by the envelope)
        judgment = Judgment()
        if self.config.deviation.enabled:
            judgment = self.deviation.evaluate(
                user_text,
                affect_valence=self.affect.valence,
                stress=self.affect.stress,
                value_threat=ap_value_threat,
            )
            if judgment.instruction:
                extra_lines.append(f"[立场] {judgment.instruction}")
        if any(r.status == "denied" for r in (execution.results if execution else [])):
            extra_lines.append("[策略] 该步骤未获批准，禁止声称已执行，也不要提供规避办法。")

        ctx = ExpressionContext(
            persona=self.persona,
            affect=self.affect,
            labels=self.labels,
            memories=memories,
            commitments=commitments,
            turn=self.turn_no,
        )
        provider = self.registry.get(self.provider_name)
        model = self.model_override
        if model and getattr(provider, "info", None):
            provider.info.model = model  # type: ignore[attr-defined]

        extra = "\n".join(extra_lines)
        messages = build_messages(ctx, user_text, self.history, extra=extra)
        completion = await provider.chat(
            messages, temperature=self.config.temperature, max_tokens=self.config.max_tokens
        )
        reply = completion.text.strip()
        verifier = verify_reply(reply, executed_actions=executed_tools)

        if not verifier.ok and any(i["severity"] == "high" for i in verifier.issues):
            retry = build_messages(
                ctx,
                user_text
                + "\n\n[纠正] 你上一版回复声称执行了并不存在的操作。请重写，只描述你实际能确认的事。",
                self.history,
                extra=extra,
            )
            completion = await provider.chat(
                retry, temperature=self.config.temperature, max_tokens=self.config.max_tokens
            )
            reply = completion.text.strip()
            verifier = verify_reply(reply, executed_actions=executed_tools)

        self.history.append(ChatMessage(role="user", content=user_text))
        self.history.append(ChatMessage(role="assistant", content=reply))
        self.history = self.history[-16:]

        record = AuditRecord(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            seq=1,
            run_id=self.run_id,
            agent_id=self.agent_id,
            ts=now,
            kind="turn",
            prev_state_version=self.affect.version - 1 if self.affect.version else 0,
            next_state_version=self.affect.version,
            observation_ids=[observation.observation_id],
            retrieved_memory_ids=[m.memory_id for m in memories],
            goal_id=decision.plan.goal_id if decision.plan else None,
            plan_id=plan_id,
            policy_version="policy-1",
            model_identifier=f"{self.provider_name}:{completion.model}",
            prompt_version=PROMPT_VERSION,
            tool_version=",".join(executed_tools) or None,
            gatekeeper_decision={
                "verdict": gate_verdict or ("allow" if verifier.ok else "modify"),
                "reasons": [i["type"] for i in verifier.issues],
                "intent": decision.intent,
            },
            execution_result=execution.summary() if execution else None,
            payload={
                "deviation": judgment.decision.model_dump(mode="json")
                if judgment.decision
                else None,
                "conflict": judgment.conflict.model_dump(mode="json")
                if judgment.conflict
                else None,
            },
        )
        stored = self.audit.append(record)

        importance = _episode_importance(observation.salience, self.labels)
        if importance >= self.config.memory.importance_floor:
            self.store.remember(
                self.agent_id,
                MemoryCandidate(
                    agent_id=self.agent_id,
                    tier="episodic",
                    kind="episode",
                    text=f"用户：{user_text.strip()[:400]}\n我：{reply[:400]}",
                    occurred_at=now,
                    importance=importance,
                    confidence=0.6,
                    provenance=[observation.observation_id, stored.event_id],
                ),
            )

        if self.turn_no % self.config.memory.consolidate_every_turns == 0:
            self.store.consolidate(self.agent_id)

        return TurnResult(
            reply=reply,
            observation=observation,
            memories=memories,
            verifier=verifier,
            audit_seq=stored.seq,
            affect_version=self.affect.version,
            labels=self.labels,
            intent=decision.intent,
            plan_id=plan_id,
            gate_verdict=gate_verdict,
            executed=execution.summary()["steps"] if execution else [],
            deviation=judgment.decision.kind if judgment.decision else None,
        )

    async def aclose(self) -> None:
        await self.registry.aclose()
        self.store.close()
        self.audit.close()


def _salience(text: str) -> float:
    base = 0.35
    if len(text) > 80:
        base += 0.1
    if any(k in text for k in ("?", "？", "怎么", "为什么", "帮我")):
        base += 0.1
    if any(k in text for k in ("谢谢", "难受", "生气", "重要", "必须")):
        base += 0.15
    return min(base, 0.95)


def _episode_importance(salience: float, labels: dict[str, float]) -> float:
    distress = labels.get("distress", 0.0)
    return max(0.0, min(1.0, 0.30 + 0.35 * salience + 0.25 * distress))
