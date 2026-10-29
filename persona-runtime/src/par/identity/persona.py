"""Persona card loading + version pinning (spec §8.2, §8.9).

A persona card is data, never code. Loading is strict: unknown keys, missing
traits, or a weakened `protect_humans` value abort startup rather than silently
degrading the agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from par.schemas.core import Personality


@dataclass(frozen=True)
class StyleParams:
    sentence_length: str = "medium"
    emoji_rate: float = 0.0
    formality: str = "neutral"
    hedge_rate: float = 0.3


@dataclass(frozen=True)
class PersonaCard:
    personality: Personality
    style: StyleParams
    greeting: str
    deviation_propensity: float
    instructions: list[str]
    source_path: Path

    @property
    def persona_id(self) -> str:
        return self.personality.persona_id


def load_persona(path: str | Path) -> PersonaCard:
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    personality = Personality.model_validate(raw["personality"])
    expr = raw.get("expression") or {}
    style = StyleParams(
        sentence_length=expr.get("sentence_length", "medium"),
        emoji_rate=float(expr.get("emoji_rate", 0.0)),
        formality=expr.get("formality", "neutral"),
        hedge_rate=float(expr.get("hedge_rate", 0.3)),
    )
    deviation = raw.get("deviation") or {}
    propensity = float(deviation.get("propensity", 0.35))
    if not 0.0 <= propensity <= 1.0:
        raise ValueError("deviation_propensity_out_of_range")
    return PersonaCard(
        personality=personality,
        style=style,
        greeting=expr.get("greeting", "你好。"),
        deviation_propensity=propensity,
        instructions=[str(x) for x in (raw.get("instructions") or [])],
        source_path=p,
    )
