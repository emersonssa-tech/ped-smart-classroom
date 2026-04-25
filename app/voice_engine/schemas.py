from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class VoiceCommandRequest(BaseModel):
    text: str = Field(..., description="Texto transcrito do comando de voz.")
    classroom_id: Optional[str] = Field(
        None, description="Identificador da sala, se conhecido."
    )
    teacher_id: Optional[str] = Field(
        None, description="Identificador do professor (necessário para analytics por professor)."
    )


class VoiceCommandResponse(BaseModel):
    recognized: bool
    intent: Optional[str]
    entities: dict[str, str] = Field(default_factory=dict)
    confidence: float
    normalized_text: str
    event_name: str              # nome do evento publicado
    correlation_id: str
    received_at: datetime
