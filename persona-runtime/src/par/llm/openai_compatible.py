"""OpenAI-compatible adapter.

Covers: OpenAI (ChatGPT), DeepSeek, Ollama, LM Studio, OpenRouter, vLLM,
and any gateway exposing `POST {base_url}/chat/completions` with the same JSON
shape — including DeepSeek Harness bridges that forward an OpenAI-compatible
endpoint.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from par.llm.base import (
    ChatMessage,
    Completion,
    ProviderError,
    ProviderInfo,
    Usage,
)

DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "ollama": "http://127.0.0.1:11434/v1",
}


class OpenAICompatibleProvider:
    kind = "openai_compatible"

    def __init__(
        self,
        *,
        name: str,
        model: str,
        base_url: str | None = None,
        api_key: str | None = None,
        api_key_env: str | None = None,
        timeout_s: float = 60.0,
        extra_headers: dict[str, str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1200,
    ) -> None:
        resolved_base = base_url or DEFAULT_BASE_URLS.get(name) or "http://127.0.0.1:11434/v1"
        self.info = ProviderInfo(name=name, kind=self.kind, model=model, base_url=resolved_base)
        self._base_url = resolved_base.rstrip("/")
        self._api_key = api_key or (os.getenv(api_key_env) if api_key_env else None)
        self._timeout = timeout_s
        self._headers = {"Content-Type": "application/json"}
        if self._api_key:
            self._headers["Authorization"] = f"Bearer {self._api_key}"
        self._headers.update(extra_headers or {})
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Completion:
        body: dict[str, Any] = {
            "model": self.info.model,
            "messages": [m.as_dict() for m in messages],
            "temperature": self._temperature if temperature is None else temperature,
            "max_tokens": self._max_tokens if max_tokens is None else max_tokens,
            "stream": False,
        }
        url = f"{self._base_url}/chat/completions"
        try:
            resp = await self._http().post(url, json=body, headers=self._headers)
        except httpx.TimeoutException as exc:
            raise ProviderError(f"timeout calling {self.info.name}", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"transport error calling {self.info.name}: {exc}") from exc

        if resp.status_code >= 400:
            retryable = resp.status_code in (408, 409, 429) or resp.status_code >= 500
            snippet = resp.text[:300].replace("\n", " ")
            raise ProviderError(
                f"{self.info.name} HTTP {resp.status_code}: {snippet}",
                status=resp.status_code,
                retryable=retryable,
            )
        try:
            data = resp.json()
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
        except (KeyError, IndexError, ValueError) as exc:
            raise ProviderError(f"malformed response from {self.info.name}") from exc

        usage = data.get("usage") or {}
        return Completion(
            text=text,
            model=data.get("model", self.info.model),
            usage=Usage(
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
            ),
            raw=data,
            finish_reason=choice.get("finish_reason"),
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
