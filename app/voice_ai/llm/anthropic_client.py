"""
Cliente nativo da API Anthropic Messages via httpx puro.

Formato difere do OpenAI-compat: system vem em campo separado,
messages só tem user/assistant.

Docs: https://docs.claude.com/en/api/messages
"""
import logging

import httpx

from .base import LLMAuthError, LLMTimeout, LLMUnavailable
from typing import Optional

logger = logging.getLogger(__name__)


class AnthropicLLMClient:
    DEFAULT_BASE = "https://api.anthropic.com/v1"
    API_VERSION = "2023-06-01"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        base_url: Optional[str] = None,
        timeout: float = 8.0,
    ) -> None:
        self._model = model
        self._http = httpx.AsyncClient(
            base_url=(base_url or self.DEFAULT_BASE).rstrip("/"),
            timeout=timeout,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": self.API_VERSION,
            },
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 200,
        temperature: float = 0.0,
        json_mode: bool = True,  # Anthropic: não existe; prompt faz o trabalho
    ) -> str:
        body = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }

        try:
            response = await self._http.post("/messages", json=body)
        except httpx.TimeoutException as exc:
            raise LLMTimeout(f"Anthropic timeout: {exc}") from exc
        except httpx.ConnectError as exc:
            raise LLMUnavailable(f"Anthropic conexão falhou: {exc}") from exc

        if response.status_code in (401, 403):
            raise LLMAuthError(f"Anthropic auth falhou ({response.status_code})")
        if response.status_code >= 500:
            raise LLMUnavailable(f"Anthropic 5xx: {response.status_code}")
        if response.status_code >= 400:
            raise LLMUnavailable(
                f"Anthropic erro {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        try:
            # content é uma lista de blocks: [{"type": "text", "text": "..."}]
            blocks = data["content"]
            text_parts = [b["text"] for b in blocks if b.get("type") == "text"]
            return "".join(text_parts)
        except (KeyError, TypeError) as exc:
            raise LLMUnavailable(f"Anthropic resposta inesperada: {data}") from exc
