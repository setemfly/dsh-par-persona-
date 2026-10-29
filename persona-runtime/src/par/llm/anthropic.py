"""Anthropic Messages API adapter (Claude). Separate shape from OpenAI on purpose."""

from __future__ import annotations

import os

import httpx

from par.llm.base import ChatMessage, Completion, ProviderError, ProviderInfo, Usage


class AnthropicProvider:
    kind = "anthropic"

    def __init__(
        self,
        *,
        name: str = "anthropic",
        model: str,
        base_url: str = "https://api.anthropic.com/v1",
        api_key: str | None = None,
        api_key_env: str = "ANTHROPIC_API_KEY",
        timeout_s: float = 60.0,
        temperature: float = 0.7,
        max_tokens: int = 1200,
    ) -> None:
        self.info = ProviderInfo(name=name, kind=self.kind, model=model, base_url=base_url)
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or os.getenv(api_key_env)
        self._timeout = timeout_s
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
        if not self._api_key:
            raise ProviderError("missing ANTHROPIC_API_KEY", retryable=False)
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        convo = [
            {"role": m.role, "content": m.content} for m in messages if m.role in ("user", "assistant")
        ]
        body = {
            "model": self.info.model,
            "max_tokens": self._max_tokens if max_tokens is None else max_tokens,
            "temperature": self._temperature if temperature is None else temperature,
            "system": system,
            "messages": convo,
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        try:
            resp = await self._http().post(f"{self._base_url}/messages", json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout calling anthropic", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"transport error calling anthropic: {exc}") from exc

        if resp.status_code >= 400:
            raise ProviderError(
                f"anthropic HTTP {resp.status_code}: {resp.text[:300]}",
                status=resp.status_code,
                retryable=resp.status_code in (408, 429) or resp.status_code >= 500,
            )
        try:
            data = resp.json()
            text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("malformed response from anthropic") from exc

        usage = data.get("usage") or {}
        return Completion(
            text=text,
            model=data.get("model", self.info.model),
            usage=Usage(
                prompt_tokens=int(usage.get("input_tokens", 0)),
                completion_tokens=int(usage.get("output_tokens", 0)),
            ),
            raw=data,
            finish_reason=data.get("stop_reason"),
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
