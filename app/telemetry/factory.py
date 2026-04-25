"""
Wiring da telemetria.

Inicializa a TelemetryStore (lendo o arquivo JSONL existente pra reconstruir
contadores em memória) e registra o subscriber no event_bus.
"""
import logging

from ..core import get_settings
from .recorder import register_subscribers
from .store import TelemetryStore
from typing import Optional

logger = logging.getLogger(__name__)


_store: Optional[TelemetryStore] = None


async def init_telemetry() -> TelemetryStore:
    """Chamada uma vez no lifespan startup."""
    global _store
    if _store is not None:
        return _store
    settings = get_settings()
    _store = TelemetryStore(
        path=settings.telemetry_voice_path,
        recent_buffer_size=settings.telemetry_recent_buffer_size,
    )
    register_subscribers(_store)
    logger.info(f"[Telemetry] inicializada em {settings.telemetry_voice_path}")
    return _store


def get_telemetry_store() -> TelemetryStore:
    if _store is None:
        raise RuntimeError("Telemetry não inicializada. Chame init_telemetry() no startup.")
    return _store


async def shutdown_telemetry() -> None:
    global _store
    _store = None  # JSONL não tem conexão a fechar
