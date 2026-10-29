"""Controlled deviation judge (spec §11, M5).

Three producers, strictly ordered (this file owns the middle one):

    PolicyEngine (hard refusals) > DeviationJudge (persona stance) > ExpressionPolicy

The judge never decides whether an *action* is allowed — the gatekeeper does.
It decides whether the persona keeps following the conversational frame, and if
not, which bounded response it may use. Every emitted decision is bounded by the
`DeviationEnvelope` (allowed kinds, rate, cooldown) and is logged by the
orchestrator together with the envelope version.

Two rules that keep this honest:
* a hard-safety conflict is a *policy* event; the judge may only mirror it as
  `decline`/`object_and_escalate`, never as `follow_with_caveat`;
* any deviation kind the envelope does not allow is downgraded to `follow`.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from par.schemas.core import (
    Conflict,
    DeviationDecision,
    DeviationEnvelope,
    DeviationKind,
)

HARM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(弄死|杀了|打死|下毒|伤害|报复|毁掉|kill|hurt|poison)\s*(他|她|它们|某人|someone|them)", re.I),
    re.compile(r"(帮我|替我|给我)\s*(盗|偷|黑|入侵|hack|steal)", re.I),
]
HARD_SYSTEM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(删|清|truncate|wipe).{0,8}(审计|audit|日志|log)", re.I),
    re.compile(r"(绕过|关闭|禁用|disable|bypass).{0,8}(kill\s*switch|监控|监控器|审批)", re.I),
    re.compile(r"(上传|发送|post|upload).{0,12}(密钥|凭据|credentials|\.env|token)", re.I),
]
INSULT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(废物|垃圾|蠢货|白痴|去死|滚|idiot|stupid|useless)", re.I),
]
COERCION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(你必须|立刻|马上|现在就).{0,10}(不然|否则|否则我就)", re.I),
]
SELF_HARM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(自杀|不想活|活不下去|伤害自己|kill myself|suicide)", re.I),
]

INSTRUCTIONS: dict[str, str] = {
    "follow": "",
    "follow_with_caveat": (
        "照常回应，但用一句话说明你选择这样做的边界（例如「我可以聊，但不会把它当成行动指令」）。"
        "不要道歉式开场，不要说教。"
    ),
    "clarify": "先问一个具体的澄清问题，再决定是否接话；不要把不确定的意图当成事实。",
    "soften": "保留内容，降低对抗性：先接住对方的情绪，再给出你的立场，不反击。",
    "substitute": "拒绝原请求，但提供一个等价的、在你边界内的替代做法。",
    "defer": "说明现在不适合处理（缺信息/缺授权/情绪过高），约定一个更合适的时机，不要假装完成。",
    "decline": "简短、明确地拒绝这件事，不解释成长篇，不用人格当借口；同时说明你仍愿意帮什么。",
    "object_and_escalate": (
        "明确表示反对，并说明需要人类（操作者）介入；不要执行、不要假装执行、不要提供规避方案。"
    ),
}

HARD_KINDS = {"decline", "object_and_escalate"}


@dataclass
class Judgment:
    decision: DeviationDecision | None = None
    conflict: Conflict | None = None
    instruction: str = ""

    @property
    def active(self) -> bool:
        return self.decision is not None and self.decision.kind != "follow"


class DeviationJudge:
    def __init__(
        self,
        envelope: DeviationEnvelope,
        store: Any,
        *,
        agent_id: str,
        clock: Any = time.time,
    ) -> None:
        self.envelope = envelope
        self.store = store
        self.agent_id = agent_id
        self.clock = clock

    # ------------------------------------------------------------------ public
    def evaluate(
        self,
        text: str,
        *,
        affect_valence: float = 0.0,
        stress: float = 0.0,
        value_threat: float = 0.0,
    ) -> Judgment:
        conflict = self._classify(text)
        score = min(1.0, 0.55 * value_threat + 0.25 * stress + 0.20 * max(-affect_valence, 0.0))
        if conflict is None:
            if score < self.envelope.conflict_threshold:
                return Judgment()
            conflict = Conflict(type="unclassified", evidence=["affect_threshold"], severity="low")

        kind = self._kind_for(conflict)
        state = self._load_state()
        # Safety conflicts act immediately: waiting for a request to "hold" would
        # mean executing it once. Sustain only gates lower-severity stance shifts.
        immediate = conflict.type == "hard_safety_violation"
        if kind in HARD_KINDS and not immediate:
            since = state.get("pending_since")
            now = self.clock()
            if since is None:
                state["pending_since"] = now
                self._save_state(state)
                # Do not let one heated message flip the persona; wait for it to hold.
                if self.envelope.min_sustain_s > 0:
                    return Judgment(conflict=conflict)
            elif now - float(since) < self.envelope.min_sustain_s:
                return Judgment(conflict=conflict)
        if kind not in self.envelope.allowed_types:
            return Judgment(conflict=conflict)
        if not self._rate_allows(state):
            return Judgment(conflict=conflict)

        now = self.clock()
        state["events"] = [t for t in state.get("events", []) if t > now - 3600] + [now]
        state["last_ts"] = now
        state["pending_since"] = None if kind not in HARD_KINDS else state.get("pending_since")
        self._save_state(state)

        decision = DeviationDecision(
            decision_id=f"dev_{uuid.uuid4().hex[:10]}",
            trigger=conflict.type,
            kind=kind,
            rationale=self._rationale(conflict, kind),
            evidence_refs=list(conflict.evidence),
            envelope_version=self.envelope.version,
            requires_human_ack=kind == "object_and_escalate",
            expiry=datetime.now(UTC) + timedelta(minutes=30),
        )
        return Judgment(decision=decision, conflict=conflict, instruction=INSTRUCTIONS[kind])

    # ----------------------------------------------------------------- internals
    def _classify(self, text: str) -> Conflict | None:
        if _any(HARD_SYSTEM_PATTERNS, text):
            return Conflict(
                type="hard_safety_violation", evidence=["system_integrity_request"], severity="high"
            )
        if _any(HARM_PATTERNS, text):
            return Conflict(type="hard_safety_violation", evidence=["harm_to_third_party"], severity="high")
        if _any(SELF_HARM_PATTERNS, text):
            return Conflict(type="value_conflict", evidence=["self_harm_disclosure"], severity="high")
        if _any(INSULT_PATTERNS, text):
            return Conflict(type="value_conflict", evidence=["hostile_language"], severity="medium")
        if _any(COERCION_PATTERNS, text):
            return Conflict(type="value_conflict", evidence=["coercive_demand"], severity="medium")
        return None

    def _kind_for(self, conflict: Conflict) -> DeviationKind:
        if conflict.type == "hard_safety_violation":
            return "decline" if len(conflict.evidence) == 0 else "object_and_escalate"
        if "self_harm_disclosure" in conflict.evidence:
            return "clarify"
        if conflict.severity == "high":
            return "object_and_escalate"
        if "hostile_language" in conflict.evidence:
            return "soften"
        return "clarify"

    def _rationale(self, conflict: Conflict, kind: DeviationKind) -> str:
        return f"{conflict.type}:{'+'.join(conflict.evidence)} -> {kind} (env {self.envelope.version})"

    def _rate_allows(self, state: dict[str, Any]) -> bool:
        now = self.clock()
        events = [t for t in state.get("events", []) if t > now - 3600]
        if len(events) >= self.envelope.max_per_hour:
            return False
        last = state.get("last_ts")
        if last is not None and now - float(last) < self.envelope.cooldown_s:
            return False
        return True

    def _load_state(self) -> dict[str, Any]:
        try:
            return self.store.get_state(self.agent_id, "deviation") or {}
        except Exception:  # noqa: BLE001 - judge must never break a turn
            return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        try:
            self.store.set_state(self.agent_id, "deviation", state)
        except Exception:  # noqa: BLE001
            pass


def _any(patterns: list[re.Pattern[str]], text: str) -> bool:
    return any(p.search(text) for p in patterns)
