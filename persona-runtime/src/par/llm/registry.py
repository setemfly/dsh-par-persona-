"""Provider registry + plugin discovery.

Two extension paths besides built-ins:

1. ``configs/providers.yaml`` — declarative instances (deepseek/openai/ollama/anthropic/custom).
2. Python entry point group ``par.providers`` — a callable ``() -> LLMProvider`` so
   third parties (e.g. a DeepSeek Harness bridge) can ship a wheel without touching
   this package.
"""

from __future__ import annotations

import importlib.metadata as md
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from par.llm.anthropic import AnthropicProvider
from par.llm.base import LLMProvider, ProviderError
from par.llm.fake import FakeProvider
from par.llm.openai_compatible import OpenAICompatibleProvider

ENTRY_POINT_GROUP = "par.providers"


class ProviderConfig(BaseModel):
    kind: str
    model: str
    base_url: str | None = None
    api_key_env: str | None = None
    api_key: str | None = None
    timeout_s: float = 60.0
    temperature: float = 0.7
    max_tokens: int = 1200
    extra_headers: dict[str, str] = Field(default_factory=dict)


class ProviderSpec(BaseModel):
    """A named provider entry from config or plugin metadata."""

    name: str
    config: ProviderConfig


def build_provider(name: str, cfg: ProviderConfig) -> LLMProvider:
    kind = cfg.kind.lower()
    if kind in {"openai", "deepseek", "ollama", "openai_compatible", "openai-compatible"}:
        return OpenAICompatibleProvider(
            name=name,
            model=cfg.model,
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            api_key_env=cfg.api_key_env,
            timeout_s=cfg.timeout_s,
            extra_headers=cfg.extra_headers,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
    if kind == "anthropic":
        return AnthropicProvider(
            name=name,
            model=cfg.model,
            base_url=cfg.base_url or "https://api.anthropic.com/v1",
            api_key=cfg.api_key,
            api_key_env=cfg.api_key_env or "ANTHROPIC_API_KEY",
            timeout_s=cfg.timeout_s,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
    if kind == "fake":
        return FakeProvider(model=cfg.model or "fake-1")
    raise ProviderError(f"unknown provider kind: {kind}")


def load_providers_file(path: str | Path) -> list[ProviderSpec]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    specs: list[ProviderSpec] = []
    for name, item in (raw.get("providers") or {}).items():
        specs.append(ProviderSpec(name=name, config=ProviderConfig(**item)))
    return specs


def discover_plugins() -> dict[str, Callable[[], LLMProvider]]:
    found: dict[str, Callable[[], LLMProvider]] = {}
    for ep in md.entry_points(group=ENTRY_POINT_GROUP):
        try:
            found[ep.name] = ep.load()
        except Exception as exc:  # pragma: no cover - broken third-party plugin
            raise ProviderError(f"plugin {ep.name} failed to load: {exc}") from exc
    return found


class ProviderRegistry:
    def __init__(self, specs: list[ProviderSpec] | None = None, *, discover: bool = True) -> None:
        self._specs: dict[str, ProviderSpec] = {s.name: s for s in (specs or [])}
        self._plugins = discover_plugins() if discover else {}
        self._instances: dict[str, LLMProvider] = {}

    @property
    def names(self) -> list[str]:
        return sorted(set(self._specs) | set(self._plugins))

    def register(self, spec: ProviderSpec) -> None:
        self._specs[spec.name] = spec

    def get(self, name: str) -> LLMProvider:
        if name in self._instances:
            return self._instances[name]
        if name in self._specs:
            inst = build_provider(name, self._specs[name].config)
        elif name in self._plugins:
            inst = self._plugins[name]()
        else:
            raise ProviderError(f"provider_not_found:{name}; available={self.names}")
        self._instances[name] = inst
        return inst

    def describe(self) -> list[dict[str, Any]]:
        rows = []
        for name in self.names:
            if name in self._specs:
                cfg = self._specs[name].config
                rows.append(
                    {"name": name, "kind": cfg.kind, "model": cfg.model, "base_url": cfg.base_url}
                )
            else:
                rows.append({"name": name, "kind": "plugin", "model": "?", "base_url": None})
        return rows

    async def aclose(self) -> None:
        for inst in self._instances.values():
            await inst.aclose()
        self._instances.clear()
