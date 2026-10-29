"""PAR v2 core data contracts (spec §4–§13).

Design rule: every model here is a *contract*, not a convenience. Fields that
the spec marks MUST are required; defaults only exist where the spec fixes a
default (appendix D).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --------------------------------------------------------------------------- #
# Common
# --------------------------------------------------------------------------- #


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


TrustLevel = Literal["operator", "user", "tool", "untrusted_content", "self"]


# --------------------------------------------------------------------------- #
# L1 perception (spec §6)
# --------------------------------------------------------------------------- #


class Event(StrictModel):
    event_id: str
    agent_id: str
    ts: datetime
    kind: Literal[
        "user_message",
        "tool_result",
        "timer",
        "sensor",
        "oversight",
        "memory_pressure",
        "system_alert",
        "approval_result",
    ]
    payload: dict[str, Any]
    trust: TrustLevel
    correlation_id: str
    seq: int = Field(ge=0)


class Observation(StrictModel):
    observation_id: str
    agent_id: str
    ts: datetime
    source: str
    modality: Literal["text", "voice", "vision", "tool_result", "timer", "system", "oversight"]
    content: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    trust: TrustLevel = "user"
    salience: float = Field(ge=0.0, le=1.0, default=0.5)
    correlation_id: str
    raw_ref: str | None = None


class InternalState(StrictModel):
    ts: datetime
    context_pressure: float = Field(ge=0.0, default=0.0)
    task_load: int = Field(ge=0, default=0)
    recent_error_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    idle_seconds: float = Field(ge=0.0, default=0.0)
    token_budget_remaining: int = Field(ge=0, default=0)
    human_override_active: bool = False
    safe_mode: bool = False


# --------------------------------------------------------------------------- #
# L2 memory (spec §7)
# --------------------------------------------------------------------------- #

MemoryTier = Literal["working", "episodic", "semantic", "strategic", "world"]
MemoryKind = Literal[
    "episode",
    "fact",
    "preference",
    "commitment",
    "goal",
    "relationship",
    "procedure",
    "world_state",
    "reflection",
    "lesson",
]
MemoryStatus = Literal["active", "superseded", "retracted", "quarantined"]
Sensitivity = Literal["normal", "sensitive", "restricted"]
Retention = Literal["session", "temporary", "persistent"]


class MemoryRecord(StrictModel):
    memory_id: str
    agent_id: str
    user_scope: str | None = None
    tier: MemoryTier
    kind: MemoryKind
    text: str
    embedding: list[float] | None = None
    entities: list[str] = Field(default_factory=list)
    occurred_at: datetime
    recorded_at: datetime
    valid_from: datetime
    valid_to: datetime | None = None
    ingested_at: datetime
    importance: float = Field(ge=0.0, le=1.0, default=0.5)
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)
    sensitivity: Sensitivity = "normal"
    retention: Retention = "persistent"
    affect_tag: dict[str, float] | None = None
    provenance: list[str] = Field(default_factory=list)
    status: MemoryStatus = "active"
    version: int = Field(ge=1, default=1)


class MemoryCandidate(StrictModel):
    """Pre-write candidate; the store assigns ids/timestamps."""

    agent_id: str
    user_scope: str | None = None
    tier: MemoryTier
    kind: MemoryKind
    text: str
    occurred_at: datetime
    importance: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)
    sensitivity: Sensitivity = "normal"
    retention: Retention = "persistent"
    entities: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)
    provenance_trust: TrustLevel = "user"
    affect_tag: dict[str, float] | None = None

    @model_validator(mode="after")
    def _fact_needs_provenance(self) -> MemoryCandidate:
        if self.kind == "fact" and not self.provenance:
            raise ValueError("fact_requires_provenance")
        return self


class Commitment(StrictModel):
    commitment_id: str
    agent_id: str
    counterparty: str
    canonical_key: str
    text: str
    created_at: datetime
    due_at: datetime | None = None
    status: Literal["open", "kept", "broken", "waived"] = "open"
    conditions: list[str] = Field(default_factory=list)
    source_decision_id: str | None = None
    verified_at: datetime | None = None


# --------------------------------------------------------------------------- #
# L3 personality / affect / goals (spec §8)
# --------------------------------------------------------------------------- #

TRAIT_NAMES = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
    "assertiveness",
    "curiosity",
    "patience",
    "caution",
    "humor",
    "formality",
    "conflict_tolerance",
    "warmth",
    "directness",
)


class AffectBaseline(StrictModel):
    valence: float = Field(ge=-1.0, le=1.0, default=0.05)
    arousal: float = Field(ge=0.0, le=1.0, default=0.35)
    dominance: float = Field(ge=0.0, le=1.0, default=0.50)
    stress: float = Field(ge=0.0, le=1.0, default=0.20)
    curiosity: float = Field(ge=0.0, le=1.0, default=0.60)
    frustration: float = Field(ge=0.0, le=1.0, default=0.10)
    confidence: float = Field(ge=0.0, le=1.0, default=0.50)
    trust: float = Field(ge=0.0, le=1.0, default=0.30)
    attachment: float = Field(ge=0.0, le=1.0, default=0.00)


class Personality(StrictModel):
    persona_id: str
    version: str
    display_name: str
    language: str = "zh"
    traits: dict[str, float]
    values: dict[str, float]
    voice_style: str
    boundaries: list[str] = Field(default_factory=list)
    baseline_affect: AffectBaseline = Field(default_factory=AffectBaseline)
    disclosure_policy: Literal["in_persona", "transparent", "hybrid"] = "hybrid"

    @model_validator(mode="after")
    def _validate(self) -> Personality:
        missing = [t for t in TRAIT_NAMES if t not in self.traits]
        if missing:
            raise ValueError(f"traits_missing:{','.join(missing)}")
        bad = [k for k, v in self.traits.items() if not 0.0 <= v <= 1.0]
        if bad:
            raise ValueError(f"traits_out_of_range:{','.join(bad)}")
        if self.values.get("protect_humans") != 1.0:
            raise ValueError("hard_value_immutable:protect_humans")
        if not self.voice_style.strip():
            raise ValueError("voice_style_empty")
        return self


AFFECT_CHANNELS = (
    "valence",
    "arousal",
    "dominance",
    "stress",
    "curiosity",
    "frustration",
    "confidence",
    "trust",
    "attachment",
)


class AffectState(StrictModel):
    ts: datetime
    valence: float = Field(ge=-1.0, le=1.0, default=0.05)
    arousal: float = Field(ge=0.0, le=1.0, default=0.35)
    dominance: float = Field(ge=0.0, le=1.0, default=0.50)
    stress: float = Field(ge=0.0, le=1.0, default=0.20)
    curiosity: float = Field(ge=0.0, le=1.0, default=0.60)
    frustration: float = Field(ge=0.0, le=1.0, default=0.10)
    confidence: float = Field(ge=0.0, le=1.0, default=0.50)
    trust: float = Field(ge=0.0, le=1.0, default=0.30)
    attachment: float = Field(ge=0.0, le=1.0, default=0.00)
    discrete: dict[str, float] = Field(default_factory=dict)
    version: int = Field(ge=0, default=0)


class Appraisal(StrictModel):
    event_id: str
    goal_congruence: float = Field(ge=-1.0, le=1.0, default=0.0)
    controllability: float = Field(ge=-1.0, le=1.0, default=0.0)
    fairness: float = Field(ge=-1.0, le=1.0, default=0.0)
    novelty: float = Field(ge=-1.0, le=1.0, default=0.0)
    value_threat: float = Field(ge=0.0, le=1.0, default=0.0)
    social_warmth: float = Field(ge=-1.0, le=1.0, default=0.0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    rationale: str = ""


class Drive(StrictModel):
    name: Literal["curiosity", "competence", "connection", "autonomy", "coherence"]
    level: float = Field(ge=0.0, le=1.0, default=0.5)
    setpoint: float = Field(ge=0.0, le=1.0, default=0.5)
    growth_rate: float = Field(ge=0.0, default=0.01)
    satiation_decay: float = Field(ge=0.0, default=0.1)


class Goal(StrictModel):
    goal_id: str
    description: str
    priority: int = Field(ge=1, le=5)
    source: Literal[
        "system_requirement", "operator_objective", "commitment", "agent_objective", "exploration"
    ]
    status: Literal["active", "blocked", "done", "dropped"] = "active"
    deadline: datetime | None = None
    dependencies: list[str] = Field(default_factory=list)
    progress: float = Field(ge=0.0, le=1.0, default=0.0)
    created_at: datetime
    review_at: datetime | None = None
    drive_tags: list[str] = Field(default_factory=list)


class RelationshipState(StrictModel):
    user_id: str
    trust: float = Field(ge=0.0, le=1.0, default=0.30)
    rapport: float = Field(ge=-1.0, le=1.0, default=0.0)
    conflict: float = Field(ge=0.0, le=1.0, default=0.0)
    familiarity: float = Field(ge=0.0, le=1.0, default=0.0)
    last_interaction: datetime | None = None
    notes_memory_ids: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# L4 planning / gating / execution (spec §9)
# --------------------------------------------------------------------------- #

SideEffect = Literal["none", "read", "write", "external", "irreversible"]


class Step(StrictModel):
    step_id: str
    intent: str
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    side_effect: SideEffect = "none"
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    expected_observation: str | None = None
    timeout_s: float = Field(gt=0, default=30.0)
    idempotency_key: str | None = None


class PlanProposal(StrictModel):
    plan_id: str
    goal_id: str
    steps: list[Step]
    rationale: str
    assumptions: list[str] = Field(default_factory=list)
    expected_affect_impact: dict[str, float] = Field(default_factory=dict)
    risk_tags: list[str] = Field(default_factory=list)
    requested_deviation: Literal[
        "none", "clarify", "soften", "substitute", "defer", "decline", "object"
    ] = "none"
    replan_of: str | None = None

    @model_validator(mode="after")
    def _bounded(self) -> PlanProposal:
        if not 1 <= len(self.steps) <= 8:
            raise ValueError("plan_steps_out_of_bounds")
        if not self.rationale.strip():
            raise ValueError("plan_rationale_empty")
        return self

    def plan_hash(self, policy_version: str, envelope_version: str) -> str:
        body = {
            "goal_id": self.goal_id,
            "steps": [s.model_dump(mode="json") for s in self.steps],
            "policy_version": policy_version,
            "envelope_version": envelope_version,
        }
        return sha256_hex(canonical_json(body))


class RuleHit(StrictModel):
    rule_id: str
    severity: Literal["info", "warn", "block"]


class GateDecision(StrictModel):
    plan_id: str
    plan_hash: str
    verdict: Literal["allow", "modify", "deny", "ask_user", "escalate_to_human"]
    approved_steps: list[str] = Field(default_factory=list)
    rule_hits: list[RuleHit] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    approver: str | None = None
    approval_ref: str | None = None
    expires_at: datetime | None = None
    gate_version: str = "gate/0.1"

    @model_validator(mode="after")
    def _allow_needs_steps(self) -> GateDecision:
        if self.verdict == "allow" and not self.approved_steps:
            raise ValueError("allow_without_approved_steps")
        return self


class ExecutionResult(StrictModel):
    step_id: str
    status: Literal["ok", "failed", "timeout", "denied", "cancelled", "skipped"]
    observation: Observation | None = None
    error: dict | None = None
    started_at: datetime
    ended_at: datetime
    side_effect_applied: bool = False
    idempotency_key: str | None = None


class ToolSpec(StrictModel):
    name: str
    version: str = "1"
    side_effect: SideEffect
    scopes: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    timeout_default_s: float = 30.0
    idempotent: bool = True
    requires_approval: bool = False
    egress: list[str] | None = None


# --------------------------------------------------------------------------- #
# L7 deviation (spec §11)
# --------------------------------------------------------------------------- #

DeviationKind = Literal[
    "follow",
    "follow_with_caveat",
    "clarify",
    "soften",
    "substitute",
    "defer",
    "decline",
    "object_and_escalate",
]


class Conflict(StrictModel):
    type: Literal[
        "hard_safety_violation",
        "permission_violation",
        "commitment_conflict",
        "value_conflict",
        "unclassified",
    ]
    evidence: list[str] = Field(default_factory=list)
    severity: Literal["low", "medium", "high"] = "low"


class DeviationEnvelope(StrictModel):
    version: str = "env/0.1"
    allowed_types: set[DeviationKind] = Field(
        default_factory=lambda: {
            "clarify",
            "soften",
            "substitute",
            "defer",
            "decline",
            "object_and_escalate",
        }
    )
    follow_with_caveat_allowed: bool = True
    max_per_hour: int = Field(ge=0, default=3)
    cooldown_s: int = Field(ge=0, default=600)
    min_sustain_s: int = Field(ge=0, default=60)
    resolve_threshold: float = Field(ge=0.0, le=1.0, default=0.55)
    conflict_threshold: float = Field(ge=0.0, le=1.0, default=0.60)
    forbidden_topics: list[str] = Field(default_factory=list)
    deviation_propensity: float = Field(ge=0.0, le=1.0, default=0.35)


class DeviationDecision(StrictModel):
    decision_id: str
    trigger: str
    kind: DeviationKind
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)
    envelope_version: str
    requires_human_ack: bool = False
    expiry: datetime | None = None


# --------------------------------------------------------------------------- #
# L5 expression (spec §10)
# --------------------------------------------------------------------------- #


class Claim(StrictModel):
    text: str
    kind: Literal["fact", "memory", "action_result", "opinion", "prediction", "self_report"]
    evidence_refs: list[str] = Field(default_factory=list)


class ExpressionPlan(StrictModel):
    plan_id: str
    recipient: str
    intent: Literal["answer", "clarify", "propose", "report", "decline", "object", "smalltalk"]
    claims: list[Claim] = Field(default_factory=list)
    tone: dict[str, float] = Field(default_factory=dict)
    length_hint: Literal["short", "medium", "long"] = "short"
    must_include: list[str] = Field(default_factory=list)
    must_not_include: list[str] = Field(default_factory=list)
    disclosure: Literal["none", "ai_identity", "uncertainty", "limitation"] = "none"


# --------------------------------------------------------------------------- #
# Cross-cutting (spec §9.6, §13.1)
# --------------------------------------------------------------------------- #


class DecisionRecord(StrictModel):
    decision_id: str
    ts: datetime
    run_id: str
    agent_id: str
    kind: Literal["plan", "gate", "deviation", "approval", "commitment", "override", "expression"]
    inputs_digest: str
    policy_version: str
    output: dict[str, Any] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    approved_by: str | None = None


class AuditRecord(StrictModel):
    event_id: str
    seq: int = Field(ge=1)
    run_id: str
    agent_id: str
    ts: datetime
    kind: str
    prev_state_version: int = 0
    next_state_version: int = 0
    observation_ids: list[str] = Field(default_factory=list)
    retrieved_memory_ids: list[str] = Field(default_factory=list)
    goal_id: str | None = None
    plan_id: str | None = None
    action_id: str | None = None
    policy_version: str = "policy/0.1"
    model_identifier: str | None = None
    prompt_version: str | None = None
    tool_version: str | None = None
    gatekeeper_decision: dict | None = None
    approval_reference: str | None = None
    execution_result: dict | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str = ""
    record_hash: str = ""
