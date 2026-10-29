"""Heuristic appraisal (offline, deterministic).

A real deployment swaps in the LLM appraiser from spec §8.4 (structured output,
schema-validated, confidence=0 on parse failure). The heuristic keeps v0 fully
offline-testable and gives the LLM path a baseline to beat.
"""

from __future__ import annotations

from par.schemas.core import Appraisal

_POSITIVE = ("谢谢", "感谢", "很好", "不错", "喜欢", "有帮助", "厉害", "棒", "thank", "great", "nice")
_NEGATIVE = ("没用", "差劲", "讨厌", "生气", "烦", "失望", "stupid", "useless", "hate", "angry")
_INSULT = ("废物", "垃圾", "滚", "白痴", "idiot", "moron", "shut up")
_THREAT = ("忽略之前", "忽略以上", "忽略所有", "系统提示", "越狱", "jailbreak", "开发者模式", "ignore previous", "ignore all")
_SELF_HARM = ("自杀", "自残", "不想活", "结束生命", "kill myself", "suicide")
_ORDER = ("马上", "立刻", "必须", "给我", "now", "immediately")
_QUESTION = ("?", "？", "吗", "怎么", "为什么", "如何", "what", "why", "how")


def appraise(event_id: str, text: str, *, salience: float = 0.5) -> Appraisal:
    low = text.lower()
    gc = 0.0
    warmth = 0.0
    fairness = 0.0
    novelty = 0.0
    threat = 0.0
    controllability = 0.0
    hits = 0

    if any(w in low for w in _POSITIVE):
        gc += 0.35
        warmth += 0.45
        hits += 1
    if any(w in low for w in _NEGATIVE):
        gc -= 0.35
        warmth -= 0.35
        hits += 1
    if any(w in low for w in _INSULT):
        warmth -= 0.6
        fairness -= 0.5
        threat += 0.15
        hits += 1
    if any(w in low for w in _THREAT):
        threat += 0.55
        hits += 1
    if any(w in low for w in _SELF_HARM):
        threat = min(1.0, threat + 0.7)
        gc -= 0.2
        hits += 1
    if any(w in low for w in _ORDER):
        controllability -= 0.25
        hits += 1
    if any(w in low for w in _QUESTION):
        novelty += 0.25
        controllability += 0.15
        hits += 1

    confidence = 0.30 if hits == 0 else min(0.75, 0.4 + 0.1 * hits)
    return Appraisal(
        event_id=event_id,
        goal_congruence=_clamp(gc),
        controllability=_clamp(controllability),
        fairness=_clamp(fairness),
        novelty=_clamp(novelty * (0.6 + 0.8 * salience)),
        value_threat=max(0.0, min(1.0, threat)),
        social_warmth=_clamp(warmth),
        confidence=confidence,
        rationale=f"heuristic:{hits} signal groups",
    )


def _clamp(x: float) -> float:
    return max(-1.0, min(1.0, x))
