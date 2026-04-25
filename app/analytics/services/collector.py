"""
Event collector — ponte entre event_bus e analytics storage.

Mapeia eventos do domínio (publicados pelos outros módulos) em
AnalyticsEvents persistidos. Algumas regras importantes:

  - voice_next_slide / voice_previous_slide → registra DOIS eventos:
      voice_command (genérico, pra contagem total) +
      slide_changed (específico, pra métrica de feature)
  - voice_open_activity → voice_command + activity_opened
  - outros voice_* → só voice_command
  - teacher_detected / class_started / class_ended → 1:1

Por que o mapeamento está aqui e não no event_bus? Porque é regra de
analytics — o domínio não precisa saber que "next_slide" é parte da
métrica "slide_changed". Mantém os eventos de domínio puros.
"""
import logging
from typing import Any

from ...core import Event, EventNames, event_bus
from ..models import AnalyticsEvent, EventType, utcnow_iso
from ..storage import AnalyticsStorage

logger = logging.getLogger(__name__)


# Subset dos eventos voice_* que viram FEATURES específicas
_FEATURE_MAP: dict[str, str] = {
    EventNames.VOICE_NEXT_SLIDE:     EventType.SLIDE_CHANGED,
    EventNames.VOICE_PREVIOUS_SLIDE: EventType.SLIDE_CHANGED,
    EventNames.VOICE_OPEN_ACTIVITY:  EventType.ACTIVITY_OPENED,
}

# Todos os voice_* vão gerar voice_command (genérico). voice_unrecognized é exceção.
_VOICE_GENERIC_EVENTS: set[str] = {
    EventNames.VOICE_START_CLASS,
    EventNames.VOICE_NEXT_SLIDE,
    EventNames.VOICE_PREVIOUS_SLIDE,
    EventNames.VOICE_OPEN_ACTIVITY,
    EventNames.VOICE_PLAY_VIDEO,
    EventNames.VOICE_PAUSE_VIDEO,
    EventNames.VOICE_MARK_ATTENDANCE,
    EventNames.VOICE_TURN_ON_PROJECTOR,
    EventNames.VOICE_TURN_OFF_PROJECTOR,
    EventNames.VOICE_QUERY_CURRENT_CLASS,
}


class EventCollector:
    def __init__(self, storage: AnalyticsStorage) -> None:
        self._storage = storage

    # ---- handlers por tipo de evento ----

    async def on_teacher_detected(self, event: Event) -> None:
        p = event.payload
        await self._storage.record(AnalyticsEvent(
            event_type=EventType.TEACHER_DETECTED,
            timestamp=p.get("reference_time") or utcnow_iso(),
            correlation_id=p.get("correlation_id"),
            teacher_id=p.get("teacher_id"),
            classroom_id=p.get("classroom_id"),
            metadata={
                "teacher_name": p.get("teacher_name"),
                "is_simulated_time": p.get("is_simulated_time"),
                "source": p.get("source"),
            },
        ))

    async def on_class_started(self, event: Event) -> None:
        p = event.payload
        await self._storage.record(AnalyticsEvent(
            event_type=EventType.CLASS_STARTED,
            timestamp=p.get("reference_time") or utcnow_iso(),
            correlation_id=p.get("correlation_id"),
            teacher_id=p.get("teacher_id"),
            classroom_id=p.get("classroom_id"),
            metadata={
                "teacher_name": p.get("teacher_name"),
                "turma": p.get("turma"),
                "disciplina": p.get("disciplina"),
                "horario": p.get("horario"),
            },
        ))

    async def on_class_ended(self, event: Event) -> None:
        p = event.payload
        await self._storage.record(AnalyticsEvent(
            event_type=EventType.CLASS_ENDED,
            timestamp=p.get("ended_at") or utcnow_iso(),
            correlation_id=p.get("correlation_id"),
            teacher_id=p.get("teacher_id"),
            classroom_id=p.get("classroom_id"),
            metadata={"reason": p.get("reason", "manual")},
        ))

    async def on_voice_event(self, event: Event) -> None:
        """
        Recebe qualquer voice_* não-unrecognized. Grava 1 ou 2 entradas
        dependendo se há feature específica mapeada.
        """
        if event.name not in _VOICE_GENERIC_EVENTS:
            return  # voice_unrecognized não vira métrica de uso
        p = event.payload
        ts = p.get("received_at") or utcnow_iso()

        # Sempre voice_command (genérico)
        meta_common = {
            "intent": p.get("intent"),
            "entities": p.get("entities") or {},
            "source": p.get("source"),       # "rules" | "llm"
            "confidence": p.get("confidence"),
            "transcript": p.get("normalized_text") or p.get("raw_text"),
        }
        await self._storage.record(AnalyticsEvent(
            event_type=EventType.VOICE_COMMAND,
            timestamp=ts,
            correlation_id=p.get("correlation_id"),
            teacher_id=p.get("teacher_id"),
            classroom_id=p.get("classroom_id"),
            metadata=meta_common,
        ))

        # Feature específica, se mapeada
        feature = _FEATURE_MAP.get(event.name)
        if feature:
            await self._storage.record(AnalyticsEvent(
                event_type=feature,
                timestamp=ts,
                correlation_id=p.get("correlation_id"),
                teacher_id=p.get("teacher_id"),
                classroom_id=p.get("classroom_id"),
                metadata={
                    "intent": p.get("intent"),
                    "direction": "next" if event.name == EventNames.VOICE_NEXT_SLIDE
                                 else ("previous" if event.name == EventNames.VOICE_PREVIOUS_SLIDE else None),
                    "activity_id": (p.get("entities") or {}).get("activity_id"),
                },
            ))


def register_subscribers(collector: EventCollector) -> None:
    event_bus.subscribe(EventNames.TEACHER_DETECTED, collector.on_teacher_detected)
    event_bus.subscribe(EventNames.CLASS_STARTED,    collector.on_class_started)
    event_bus.subscribe(EventNames.CLASS_ENDED,      collector.on_class_ended)
    for name in _VOICE_GENERIC_EVENTS:
        event_bus.subscribe(name, collector.on_voice_event)
    logger.info(
        f"[Analytics] collector inscrito em "
        f"{3 + len(_VOICE_GENERIC_EVENTS)} eventos."
    )
