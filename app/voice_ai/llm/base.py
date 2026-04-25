"""
Contrato do LLMClient.

Minimalista de propósito: `complete(system, user) -> str`. Nada de
streaming, functions calling, tool use, multi-turn — tudo isso pode
virar extensão depois via novos métodos. Hoje só precisamos de
"manda um prompt, me devolve texto".

Exceções são mapeadas para um conjunto pequeno — o processor decide
se cai em fallback ou não.
"""
from typing import Protocol


class LLMError(Exception):
    """Base de todas as falhas do LLMClient."""


class LLMTimeout(LLMError):
    pass


class LLMUnavailable(LLMError):
    """Rede/servidor indisponível (ECONNREFUSED, 5xx após retries, etc)."""


class LLMAuthError(LLMError):
    """401/403 — credencial inválida."""


class LLMClient(Protocol):
    async def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 200,
        temperature: float = 0.0,
        json_mode: bool = True,
    ) -> str:
        """
        Envia (system, user) e retorna o texto completo da resposta.
        Pode levantar LLMTimeout / LLMUnavailable / LLMAuthError.
        """
        ...

    async def aclose(self) -> None:
        ...
