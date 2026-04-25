"""
Cliente OpenAI-compat via httpx puro.

Compatível com:
 - OpenAI API (api.openai.com/v1)
 - Groq (api.groq.com/openai/v1)
 - Ollama local (http://localhost:11434/v1)
 - llama.cpp server (http://localhost:8080/v1)
 - vLLM, LM Studio, LiteLLM proxy — todos falam esse protocolo.

JSON mode é opt-in: alguns servidores locais rejeitam o parâmetro.
Se rejeitar, tenta de novo sem.
"""
import logging

import httpx

from .base import LLMAuthError, LLMTimeout, LLMUnavailable

logger = logging.getLogger(__name__)


class OpenAICompatLLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 8.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers=headers,
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
        json_mode: bool = True,
    ) -> str:
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        try:
            response = await self._http.post("/chat/completions", json=body)
        except httpx.TimeoutException as exc:
            raise LLMTimeout(f"LLM timeout: {exc}") from exc
        except httpx.ConnectError as exc:
            raise LLMUnavailable(f"LLM conexão falhou: {exc}") from exc

        # json_mode pode não ser suportado — retenta sem
        if response.status_code == 400 and json_mode:
            logger.warning("[LLM] 400 com json_mode; retentando sem response_format")
            body.pop("response_format", None)
            try:
                response = await self._http.post("/chat/completions", json=body)
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                raise LLMUnavailable(f"LLM falhou no retry: {exc}") from exc

        if response.status_code in (401, 403):
            raise LLMAuthError(f"LLM auth falhou ({response.status_code})")
        if response.status_code >= 500:
            raise LLMUnavailable(f"LLM servidor erro {response.status_code}")
        if response.status_code >= 400:
            raise LLMUnavailable(f"LLM erro {response.status_code}: {response.text[:200]}")

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as exc:
            raise LLMUnavailable(f"LLM resposta inesperada: {data}") from exc
