"""
Modelo do evento de analytics (independente do Event do event_bus).

Escolha por dataclass simples (não Pydantic): este é um modelo de DOMÍNIO
interno do analytics, não um schema de API. Pydantic fica nas bordas.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


def utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


class EventType:
    """
    Tipos de evento que o analytics persiste. Note: NÃO são os mesmos
    nomes do event_bus — são uma camada acima, semântica de negócio.
    O collector traduz event_bus → EventType.
    """
    TEACHER_DETECTED = "teacher_detected"
    CLASS_STARTED = "class_started"
    CLASS_ENDED = "class_ended"
    VOICE_COMMAND = "voice_command"      # genérico — todo intent gera 1
    SLIDE_CHANGED = "slide_changed"      # next_slide e previous_slide
    ACTIVITY_OPENED = "activity_opened"  # open_activity


@dataclass
class AnalyticsEvent:
    event_type: str
    timestamp: str = field(default_factory=utcnow_iso)
    correlation_id: Optional[str] = None
    teacher_id: Optional[str] = None
    classroom_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
