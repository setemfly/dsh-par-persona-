"""LLM provider port (spec §15.1). Adapters are replaceable; the port is not."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(slots=True)
class ChatMessage:
    role: Role
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(slots=True)
class Completion:
    text: str
    model: str
    usage: Usage = field(default_factory=Usage)
    raw: dict[str, Any] | None = None
    finish_reason: str | None = None


@dataclass(slots=True)
class ProviderInfo:
    name: str
    kind: str
    model: str
    base_url: str | None = None


class ProviderError(RuntimeError):
    """Transport/HTTP/protocol failure. Never swallowed; callers decide degradation."""

    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


@runtime_checkable
class LLMProvider(Protocol):
    info: ProviderInfo

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Completion: ...

    async def aclose(self) -> None: ...
