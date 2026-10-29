"""Affect dynamics (spec §8.4–§8.5).

Implementation notes:
- Every channel decays exponentially toward its baseline with λ = ln2 / T½.
- Appraisal impulse is bounded per tick, so no single turn can push a channel to
  an extreme. Arousal/stress/frustration are fast; trust/attachment are slow.
- The discrete labels (resolve/distress/closeness) are deterministic derivations,
  not model output — the expression layer may read them, never invent them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

from par.schemas.core import AFFECT_CHANNELS, AffectBaseline, AffectState, Appraisal, Personality

# channel -> (lo, hi, half_life_seconds, max_step, eta)
CHANNEL_PARAMS: dict[str, tuple[float, float, float, float, float]] = {
    "valence": (-1.0, 1.0, 6 * 3600.0, 0.15, 0.50),
    "arousal": (0.0, 1.0, 8 * 60.0, 0.20, 0.60),
    "dominance": (0.0, 1.0, 2 * 3600.0, 0.10, 0.35),
    "stress": (0.0, 1.0, 20 * 60.0, 0.25, 0.70),
    "curiosity": (0.0, 1.0, 3 * 3600.0, 0.15, 0.50),
    "frustration": (0.0, 1.0, 15 * 60.0, 0.25, 0.60),
    "confidence": (0.0, 1.0, 40 * 60.0, 0.10, 0.40),
    "trust": (0.0, 1.0, 14 * 86400.0, 0.05, 0.25),
    "attachment": (0.0, 1.0, 30 * 86400.0, 0.02, 0.15),
}

# rows = channels, cols = [goal_congruence, controllability, fairness, novelty, value_threat, social_warmth]
W: dict[str, tuple[float, float, float, float, float, float]] = {
    "valence": (0.30, 0.10, 0.15, 0.05, -0.25, 0.20),
    "arousal": (0.05, -0.05, 0.00, 0.25, 0.30, 0.05),
    "dominance": (0.10, 0.25, 0.05, 0.00, -0.15, 0.00),
    "stress": (0.00, -0.20, -0.10, 0.10, 0.35, -0.05),
    "curiosity": (0.05, 0.00, 0.00, 0.30, -0.10, 0.05),
    "frustration": (-0.30, -0.15, -0.10, 0.00, 0.20, -0.05),
    "confidence": (0.25, 0.20, 0.05, 0.00, -0.10, 0.05),
    "trust": (0.05, 0.00, 0.10, 0.00, -0.20, 0.25),
    "attachment": (0.05, 0.00, 0.00, 0.00, -0.05, 0.20),
}

DISCRETE_RESOLVE = 0.55
DISCRETE_DISTRESS = 0.60


@dataclass(frozen=True)
class TickResult:
    state: AffectState
    threat_ema: float
    labels: dict[str, float]


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def appraise_features(a: Appraisal) -> list[float]:
    return [
        a.goal_congruence,
        a.controllability,
        a.fairness,
        a.novelty,
        a.value_threat,
        a.social_warmth,
    ]


def update(
    state: AffectState,
    *,
    baseline: AffectBaseline,
    appraisal: Appraisal,
    salience: float,
    personality: Personality | None = None,
    threat_ema: float = 0.0,
    now: datetime | None = None,
) -> TickResult:
    """Apply decay + one bounded appraisal impulse to every channel."""
    now = now or datetime.now(UTC)
    dt = max((now - state.ts).total_seconds(), 0.0)
    features = appraise_features(appraisal)
    conf = appraisal.confidence
    sal = _clip(salience, 0.0, 1.0)
    values: dict[str, float] = {}
    for channel in AFFECT_CHANNELS:
        lo, hi, half_life, max_step, eta = CHANNEL_PARAMS[channel]
        current = getattr(state, channel)
        base = getattr(baseline, channel)
        lam = math.log(2.0) / half_life
        decayed = base + (current - base) * math.exp(-lam * dt)
        raw = math.tanh(sum(w * f for w, f in zip(W[channel], features, strict=True)))
        impulse = _clip(eta * sal * conf * raw, -max_step, max_step)
        values[channel] = _clip(decayed + impulse, lo, hi)

    new_ema = 0.7 * threat_ema + 0.3 * appraisal.value_threat
    conscientiousness = personality.traits.get("conscientiousness", 0.5) if personality else 0.5
    labels = {
        "resolve": _clip(
            0.35 * new_ema
            + 0.25 * conscientiousness
            + 0.20 * values["dominance"]
            + 0.20 * (1.0 - values["frustration"]),
            0.0,
            1.0,
        ),
        "distress": _clip(
            0.40 * values["stress"]
            + 0.30 * (1.0 - values["valence"]) / 2.0
            + 0.30 * new_ema,
            0.0,
            1.0,
        ),
        "closeness": _clip(
            0.50 * values["trust"] + 0.50 * values["attachment"], 0.0, 1.0
        ),
    }
    new_state = AffectState(
        ts=now,
        discrete=labels,
        version=state.version + 1,
        **values,
    )
    return TickResult(state=new_state, threat_ema=new_ema, labels=labels)


def apply_slow_penalty(
    state: AffectState,
    *,
    baseline: AffectBaseline,
    trust_delta: float = -0.05,
    now: datetime | None = None,
) -> AffectState:
    """commitment_violated: slow-channel penalty that a single turn cannot undo."""
    now = now or datetime.now(UTC)
    data = state.model_dump()
    data["ts"] = now
    data["trust"] = _clip(state.trust + trust_delta, 0.0, 1.0)
    data["version"] = state.version + 1
    return AffectState.model_validate(data)


def initial_state(baseline: AffectBaseline, *, now: datetime | None = None) -> AffectState:
    now = now or datetime.now(UTC)
    return AffectState(ts=now, version=0, **baseline.model_dump())


def throttle(
    *,
    kind: str,
    emotion_labels: dict[str, float],
    min_sustain: float = 60.0,
    last_seen: dict[str, datetime] | None = None,
    now: datetime | None = None,
) -> bool:
    """Anti-jitter: a deviation trigger must persist across ticks (spec §8.5)."""
    now = now or datetime.now(UTC)
    last_seen = last_seen if last_seen is not None else {}
    first = last_seen.get(kind)
    last_seen[kind] = now
    del emotion_labels
    if first is None:
        return False
    return (now - first).total_seconds() >= min_sustain
