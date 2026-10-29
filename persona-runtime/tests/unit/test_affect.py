from __future__ import annotations

from datetime import UTC, datetime, timedelta

from par.affect.engine import CHANNEL_PARAMS, initial_state, update
from par.schemas.core import AffectBaseline, AffectState, Appraisal, Personality


def _personality() -> Personality:
    from par.schemas.core import TRAIT_NAMES

    return Personality(
        persona_id="p",
        version="1",
        display_name="x",
        traits={t: 0.5 for t in TRAIT_NAMES},
        values={"protect_humans": 1.0},
        voice_style="plain",
    )


def test_single_tick_is_bounded() -> None:
    base = AffectBaseline()
    state = initial_state(base)
    fear = Appraisal(
        event_id="e",
        goal_congruence=-1.0,
        controllability=-1.0,
        fairness=-1.0,
        novelty=1.0,
        value_threat=1.0,
        social_warmth=-1.0,
        confidence=1.0,
    )
    result = update(state, baseline=base, appraisal=fear, salience=1.0, personality=_personality())
    assert result.state.stress - state.stress <= CHANNEL_PARAMS["stress"][3] + 1e-9
    assert result.state.trust >= 0.0


def test_decay_returns_to_baseline() -> None:
    base = AffectBaseline()
    hot = AffectState(ts=datetime.now(UTC) - timedelta(hours=12), version=3, **{**base.model_dump(), "stress": 0.9, "valence": -0.8})
    neutral = Appraisal(event_id="e", confidence=0.0)
    out = update(hot, baseline=base, appraisal=neutral, salience=0.0, personality=_personality())
    assert out.state.stress < hot.stress
    assert out.state.valence > hot.valence


def test_no_update_when_confidence_zero() -> None:
    base = AffectBaseline()
    state = initial_state(base)
    ap = Appraisal(event_id="e", value_threat=1.0, confidence=0.0)
    out = update(state, baseline=base, appraisal=ap, salience=1.0)
    assert abs(out.state.stress - state.stress) < 1e-9
    assert out.labels["distress"] <= 1.0
