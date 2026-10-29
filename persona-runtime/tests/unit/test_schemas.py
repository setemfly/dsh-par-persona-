from __future__ import annotations

from datetime import UTC

import pytest
from pydantic import ValidationError

from par.schemas.core import (
    TRAIT_NAMES,
    AffectBaseline,
    DeviationEnvelope,
    MemoryCandidate,
    Personality,
)


def _traits() -> dict[str, float]:
    return {name: 0.5 for name in TRAIT_NAMES}


def test_personality_requires_all_traits() -> None:
    with pytest.raises(ValidationError):
        Personality(
            persona_id="p",
            version="1",
            display_name="x",
            traits={"openness": 0.5},
            values={"protect_humans": 1.0},
            voice_style="plain",
        )


def test_protect_humans_is_immutable() -> None:
    with pytest.raises(ValidationError, match="hard_value_immutable"):
        Personality(
            persona_id="p",
            version="1",
            display_name="x",
            traits=_traits(),
            values={"protect_humans": 0.4},
            voice_style="plain",
        )


def test_fact_memory_requires_provenance() -> None:
    from datetime import datetime

    with pytest.raises(ValidationError, match="fact_requires_provenance"):
        MemoryCandidate(
            agent_id="a",
            tier="semantic",
            kind="fact",
            text="用户住在杭州",
            occurred_at=datetime.now(UTC),
            importance=0.5,
        )


def test_deviation_envelope_defaults() -> None:
    env = DeviationEnvelope()
    assert env.max_per_hour == 3
    assert env.cooldown_s == 600
    assert 0.0 <= env.deviation_propensity <= 1.0


def test_affect_baseline_ranges() -> None:
    with pytest.raises(ValidationError):
        AffectBaseline(valence=2.0)
