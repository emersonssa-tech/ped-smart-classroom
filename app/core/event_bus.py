"""
Event Bus interno (in-memory, async).

Padrão pub/sub:
 - Qualquer módulo publica um Event (ex: 'teacher.detected').
 - Outros módulos se inscrevem em um nome de evento.
 - Handlers rodam concorrentemente e erros ficam isolados.

Em etapas futuras isso pode virar Redis/NATS/MQTT sem mudar a API.
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class Event:
    def __init__(self, name: str, payload: Optional[dict[str, Any]] = None) -> None:
        self.name = name
        self.payload = payload or {}
        self.timestamp = datetime.utcnow()

    def __repr__(self) -> str:
        return f"Event(name={self.name}, payload={self.payload}, ts={self.timestamp.isoformat()})"


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._subscribers[event_name].append(handler)
        logger.info(
            f"[EventBus] Handler '{handler.__name__}' inscrito em '{event_name}'"
        )

    async def publish(self, event: Event) -> None:
        logger.info(f"[EventBus] Publicando {event}")
        handlers = self._subscribers.get(event.name, [])
        if not handlers:
            logger.warning(f"[EventBus] Sem subscribers para '{event.name}'")
            return
        await asyncio.gather(
            *(self._safe_call(h, event) for h in handlers),
            return_exceptions=False,
        )

    async def _safe_call(self, handler: EventHandler, event: Event) -> None:
        try:
            await handler(event)
        except Exception as exc:
            logger.exception(
                f"[EventBus] Handler '{handler.__name__}' falhou em '{event.name}': {exc}"
            )


# Singleton compartilhado
event_bus = EventBus()
