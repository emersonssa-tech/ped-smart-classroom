from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class VoiceCommandAIRequest(BaseModel):
    audio_input: str = Field(
        ...,
        description=(
            "Hoje: texto simulando áudio (passthrough STT). "
            "Amanhã: base64 de áudio WAV/MP3 quando Whisper entrar."
        ),
    )
    classroom_id: Optional[str] = Field(None, description="Identificador da sala.")
    teacher_id: Optional[str] = Field(
        None, description="Identificador do professor (necessário para analytics por professor)."
    )
    force_mode: Optional[Literal["auto", "online", "offline"]] = Field(
        None,
        description="Override do modo global (settings.voice_ai_mode). Útil pra debug.",
    )


class VoiceCommandAIResponse(BaseModel):
    recognized: bool
    intent: Optional[str]
    entities: dict = Field(default_factory=dict)
    confidence: float
    transcript: str
    source: Literal["llm", "rules", "memory"] = Field(
        ..., description="De onde veio a decisão final."
    )
    mode: Literal["online", "offline"]
    event_name: str
    correlation_id: str
    latency_ms: int
    received_at: datetime
    warning: Optional[str] = None     # preenche quando cai no fallback
