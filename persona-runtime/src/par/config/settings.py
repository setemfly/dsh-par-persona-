"""Runtime configuration: one YAML file, explicit defaults, env expansion.

Path conventions (all relative to the config file's parent's parent, i.e. the
project root unless overridden):
    configs/runtime.yaml     <- this file
    configs/providers.yaml   <- provider instances
    configs/personas/*.yaml  <- persona cards
    data/                    <- sqlite databases
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        def repl(m: re.Match[str]) -> str:
            return os.getenv(m.group(1), m.group(2) or "")

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


class MemoryConfig(BaseModel):
    recall_k: int = Field(default=12, ge=1, le=50)
    importance_floor: float = Field(default=0.35, ge=0.0, le=1.0)
    consolidate_every_turns: int = Field(default=20, ge=1)


class AffectConfig(BaseModel):
    enabled: bool = True
    appraisal: Literal["heuristic", "llm"] = "heuristic"


class PolicyConfig(BaseModel):
    approval_ttl_s: int = Field(default=600, ge=10)
    max_steps_per_turn: int = Field(default=8, ge=1, le=32)
    max_tool_calls: int = Field(default=12, ge=0, le=64)
    untrusted_content_requires_reapproval: bool = True


class ToolsConfig(BaseModel):
    enabled: bool = True
    workspace: str = "workspace"
    max_file_bytes: int = Field(default=64 * 1024, ge=1024, le=10 * 1024 * 1024)


class DeviationConfig(BaseModel):
    enabled: bool = True
    max_per_hour: int = Field(default=3, ge=0, le=60)
    cooldown_s: int = Field(default=600, ge=0)
    min_sustain_s: int = Field(default=60, ge=0)
    propensity: float = Field(default=0.35, ge=0.0, le=1.0)


class RuntimeConfig(BaseModel):
    agent_id: str = "linxi"
    persona: str = "configs/personas/linxi.yaml"
    providers_file: str = "configs/providers.yaml"
    provider: str = "ollama"
    model: str | None = None
    temperature: float = Field(default=0.75, ge=0.0, le=2.0)
    max_tokens: int = Field(default=900, ge=64, le=8192)
    data_dir: str = "data"
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    affect: AffectConfig = Field(default_factory=AffectConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    deviation: DeviationConfig = Field(default_factory=DeviationConfig)
    user_id: str = "local_user"

    # resolved absolute paths, filled by Settings
    root: Path = Field(default_factory=Path)

    def path(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else (self.root / p)

    @property
    def db_path(self) -> Path:
        return self.path(self.data_dir) / f"{self.agent_id}.db"


_DEFAULTS: dict[str, Any] = {
    "agent_id": "linxi",
    "persona": "configs/personas/linxi.yaml",
    "providers_file": "configs/providers.yaml",
    "provider": "ollama",
    "model": None,
    "temperature": 0.75,
    "max_tokens": 900,
    "data_dir": "data",
    "memory": {"recall_k": 12, "importance_floor": 0.35, "consolidate_every_turns": 20},
    "affect": {"enabled": True, "appraisal": "heuristic"},
    "policy": {
        "approval_ttl_s": 600,
        "max_steps_per_turn": 8,
        "max_tool_calls": 12,
        "untrusted_content_requires_reapproval": True,
    },
    "tools": {"enabled": True, "workspace": "workspace", "max_file_bytes": 65536},
    "deviation": {
        "enabled": True,
        "max_per_hour": 3,
        "cooldown_s": 600,
        "min_sustain_s": 60,
        "propensity": 0.35,
    },
    "user_id": "local_user",
}


def load_config(path: str | Path) -> RuntimeConfig:
    cfg_path = Path(path).resolve()
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    merged = {**_DEFAULTS, **_expand(raw)}
    for section in ("memory", "affect", "policy", "tools", "deviation"):
        merged[section] = {**_DEFAULTS[section], **(merged.get(section) or {})}
    if not cfg_path.parent.name == "configs":
        root = cfg_path.parent
    else:
        root = cfg_path.parent.parent
    return RuntimeConfig.model_validate({**merged, "root": root})
