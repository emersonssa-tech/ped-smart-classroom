"""
State store por correlation_id.

Cada request HTTP gera um correlation_id. Os event handlers do classroom_engine
escrevem aqui conforme os eventos chegam. O endpoint lê o snapshot final
depois que a cadeia de publishes resolveu.

In-memory, não persiste entre restarts. Chaves ficam até serem limpas —
o endpoint chama .pop() depois de ler, evitando crescimento.
"""
from typing import Any, Optional


class StateStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def init(self, correlation_id: str, initial: dict[str, Any]) -> None:
        self._data[correlation_id] = dict(initial)

    def update(self, correlation_id: str, patch: dict[str, Any]) -> None:
        if correlation_id in self._data:
            self._data[correlation_id].update(patch)

    def get(self, correlation_id: str) -> Optional[dict[str, Any]]:
        return self._data.get(correlation_id)

    def pop(self, correlation_id: str) -> Optional[dict[str, Any]]:
        return self._data.pop(correlation_id, None)


# Singleton compartilhado dentro do classroom_engine
state_store = StateStore()
