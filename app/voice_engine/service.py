"""
Voice Engine Service.

Orquestração:
  1) Recebe texto transcrito.
  2) Passa pelo IntentRecognizer (Protocol).
  3) Publica evento no event_bus:
     - intent reconhecido → evento específico (ex: voice_next_slide)
     - nada bateu        → voice_unrecognized (útil pra telemetria)
  4) Retorna resposta com tudo o que o cliente precisa saber.

Não contém lógica de negócio. Quem reage aos eventos são os subscribers.
"""
import logging
import uuid
from datetime import datetime

from ..core import Event, EventNames, event_bus
from .intents import INTENT_BY_NAME
from .recognizer import recognizer
from .schemas import VoiceCommandRequest, VoiceCommandResponse

logger = logging.getLogger(__name__)


class VoiceEngineService:
    async def handle_command(self, payload: VoiceCommandRequest) -> VoiceCommandResponse:
        now = datetime.utcnow()
        correlation_id = str(uuid.uuid4())

        result = recognizer.recognize(payload.text)

        if result.intent is not None:
            rule = INTENT_BY_NAME[result.intent]
            event_name = rule.event_name
            logger.info(
                f"[Voice] cid={correlation_id[:8]} intent={result.intent} "
                f"entities={result.entities} raw={payload.text!r}"
            )
        else:
            event_name = EventNames.VOICE_UNRECOGNIZED
            logger.warning(
                f"[Voice] cid={correlation_id[:8]} UNRECOGNIZED "
                f"normalized={result.normalized_text!r} raw={payload.text!r}"
            )

        await event_bus.publish(Event(
            name=event_name,
            payload={
                "correlation_id": correlation_id,
                "intent": result.intent,
                "entities": result.entities,
                "confidence": result.confidence,
                "raw_text": payload.text,
                "normalized_text": result.normalized_text,
                "classroom_id": payload.classroom_id,
                "teacher_id": payload.teacher_id,
                "source": "rules",                  # voice_engine sempre é regras
                "received_at": now.isoformat(),
            },
        ))

        return VoiceCommandResponse(
            recognized=result.intent is not None,
            intent=result.intent,
            entities=result.entities,
            confidence=result.confidence,
            normalized_text=result.normalized_text,
            event_name=event_name,
            correlation_id=correlation_id,
            received_at=now,
        )


service = VoiceEngineService()
