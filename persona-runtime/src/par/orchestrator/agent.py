"""One turn, end to end (spec §12.4).

SENSE → RECALL → APPRAISE → EXPRESS → AUDIT → CONSOLIDATE

Planning/execution are wired but empty in v0: the single step is "reply", so the
gate sees a plan with no tool calls and the executor has nothing to run. That is
intentional — the chat path must not bypass the gate, and M4 extends the planner
without changing this loop.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from par.affect import appraisal as appraiser
from par.affect.engine import TickResult, initial_state
from par.affect.engine import update as affect_update
from par.audit.log import AuditLog
from par.config.settings import RuntimeConfig
from par.expression.prompt import ExpressionContext, build_messages
from par.expression.verifier import VerifierResult, verify_reply
from par.identity.persona import PersonaCard, load_persona
from par.llm.base import ChatMessage
from par.llm.registry import ProviderRegistry, load_providers_file
from par.memory.store import MemoryStore
from par.schemas.core import (
    AffectState,
    AuditRecord,
    MemoryCandidate,
    MemoryRecord,
    Observation,
)

PROMPT_VERSION = "expr/0.1"


@dataclass
class TurnResult:
    reply: str
    observation: Observation
    memories: list[MemoryRecord] = field(default_factory=list)
    verifier: VerifierResult | None = None
    audit_seq: int = 0
    affect_version: int = 0
    labels: dict[str, float] = field(default_factory=dict)


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
        provider_name = provider or config.provider
        store = MemoryStore(db)
        audit = AuditLog(db)
        return cls(
            config=config,
            persona=persona,
            store=store,
            audit=audit,
            registry=registry,
            provider_name=provider_name,
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

        memories = self.store.recall(
            self.agent_id, user_text, k=self.config.memory.recall_k
        )
        commitments = self.store.commitments(self.agent_id)

        if self.config.affect.enabled:
            ap = appraiser.appraise(observation.observation_id, user_text, salience=observation.salience)
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

        messages = build_messages(ctx, user_text, self.history)
        completion = await provider.chat(
            messages, temperature=self.config.temperature, max_tokens=self.config.max_tokens
        )
        reply = completion.text.strip()
        verifier = verify_reply(reply, executed_actions=[])

        if not verifier.ok and any(i["severity"] == "high" for i in verifier.issues):
            retry = build_messages(
                ctx,
                user_text
                + "\n\n[纠正] 你上一版回复声称执行了并不存在的操作。请重写，只描述你实际能确认的事。",
                self.history,
            )
            completion = await provider.chat(
                retry, temperature=self.config.temperature, max_tokens=self.config.max_tokens
            )
            reply = completion.text.strip()
            verifier = verify_reply(reply, executed_actions=[])

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
            policy_version="policy-1",
            model_identifier=f"{self.provider_name}:{completion.model}",
            prompt_version=PROMPT_VERSION,
            gatekeeper_decision={
                "verdict": "allow" if verifier.ok else "modify",
                "reasons": [i["type"] for i in verifier.issues],
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

        return TurnResult(
            reply=reply,
            observation=observation,
            memories=memories,
            verifier=verifier,
            audit_seq=stored.seq,
            affect_version=self.affect.version,
            labels=self.labels,
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
