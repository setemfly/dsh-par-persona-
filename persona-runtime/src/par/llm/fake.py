"""Deterministic offline provider. Used by tests, `par doctor`, and demos.

It never touches the network. Scripted replies let behavioural tests pin exact
output; the fallback reply is intentionally boring so nobody mistakes it for a
real model.
"""

from __future__ import annotations

from par.llm.base import ChatMessage, Completion, ProviderInfo, Usage


class FakeProvider:
    kind = "fake"

    def __init__(self, *, model: str = "fake-1", script: list[str] | None = None) -> None:
        self.info = ProviderInfo(name="fake", kind=self.kind, model=model)
        self._script = list(script or [])
        self.calls: list[list[ChatMessage]] = []

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Completion:
        self.calls.append(list(messages))
        if self._script:
            text = self._script.pop(0)
        else:
            last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
            text = f"[fake:{self.info.model}] 收到：{last_user[:80]}"
        return Completion(
            text=text,
            model=self.info.model,
            usage=Usage(prompt_tokens=sum(len(m.content) for m in messages) // 4, completion_tokens=len(text) // 4),
            finish_reason="stop",
        )

    async def aclose(self) -> None:
        return None
