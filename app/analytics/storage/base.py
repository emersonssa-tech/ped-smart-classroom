"""
Contrato de persistência do analytics.

Hoje implementado por SQLite. Quando migrar pra Postgres, basta uma nova
classe satisfazendo este Protocol — factory troca em 1 linha.

Note: as funções de query estão aqui. Métricas (services/metrics.py)
montam queries de alto nível usando estes blocos.
"""
from typing import Any, Protocol, Optional

from ..models import AnalyticsEvent


class AnalyticsStorage(Protocol):
    async def init(self) -> None:
        """Cria schema/índices se necessário."""
        ...

    async def record(self, event: AnalyticsEvent) -> None:
        """Persiste um evento."""
        ...

    async def query(
        self,
        *,
        event_type: Optional[str] = None,
        teacher_id: Optional[str] = None,
        classroom_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Busca eventos com filtros opcionais."""
        ...

    async def count_by_type(
        self,
        *,
        teacher_id: Optional[str] = None,
        classroom_id: Optional[str] = None,
        since: Optional[str] = None,
    ) -> dict[str, int]:
        """Retorna {event_type: count} agregado."""
        ...

    async def class_durations(
        self,
        *,
        teacher_id: Optional[str] = None,
        classroom_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Retorna sessões pareadas (class_started + class_ended) com duração em minutos.
        Sessões sem class_ended (ativas) vêm com ended_at=None e duration_minutes=None.
        """
        ...

    async def daily_counts(self, *, days: int = 7) -> list[dict[str, Any]]:
        """Eventos por dia nos últimos N dias."""
        ...

    async def top_field(
        self,
        field: str,
        *,
        event_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Top N valores únicos de um campo (teacher_id, classroom_id, etc)."""
        ...

    async def aclose(self) -> None:
        ...
