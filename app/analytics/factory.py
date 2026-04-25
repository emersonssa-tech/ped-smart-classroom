"""
Wiring do analytics.

Hoje só SQLite. Pra Postgres, é uma linha aqui.
"""
import logging

from ..core import get_settings
from .services import EventCollector, MetricsService, register_subscribers
from .storage import AnalyticsStorage, SQLiteAnalyticsStorage
from typing import Optional

logger = logging.getLogger(__name__)


_storage: Optional[AnalyticsStorage] = None
_metrics: Optional[MetricsService] = None
_collector: Optional[EventCollector] = None


def _build_storage(settings) -> AnalyticsStorage:
    backend = (settings.analytics_backend or "sqlite").lower()
    if backend == "sqlite":
        return SQLiteAnalyticsStorage(path=settings.analytics_sqlite_path)
    raise ValueError(f"Backend desconhecido: {backend!r} (só 'sqlite' implementado)")


async def init_analytics() -> tuple[AnalyticsStorage, EventCollector, MetricsService]:
    """Chamada uma vez no lifespan startup."""
    global _storage, _metrics, _collector
    if _storage is not None:
        return _storage, _collector, _metrics  # type: ignore[return-value]
    settings = get_settings()
    _storage = _build_storage(settings)
    await _storage.init()
    _collector = EventCollector(_storage)
    _metrics = MetricsService(_storage)
    register_subscribers(_collector)
    logger.info("[Analytics] inicializado.")
    return _storage, _collector, _metrics


def get_storage() -> AnalyticsStorage:
    if _storage is None:
        raise RuntimeError("Analytics não inicializado. Chame init_analytics() no startup.")
    return _storage


def get_metrics() -> MetricsService:
    if _metrics is None:
        raise RuntimeError("Analytics não inicializado.")
    return _metrics


async def shutdown_analytics() -> None:
    global _storage
    if _storage is not None:
        await _storage.aclose()
        _storage = None
