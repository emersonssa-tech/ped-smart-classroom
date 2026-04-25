from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class TeacherDetectedRequest(BaseModel):
    teacher_id: str = Field(..., description="Identificador único do professor")
    teacher_name: str = Field(..., description="Nome completo do professor")
    classroom_id: Optional[str] = Field(None, description="Identificador da sala, se conhecido")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confiança da detecção (0-1)")
    simulated_time: Optional[datetime] = Field(
        None,
        description=(
            "Horário simulado para teste. Se omitido, usa o horário atual do servidor. "
            "Ex: '2026-04-27T07:45:00' (segunda, 1º horário)."
        ),
    )


class LessonInfo(BaseModel):
    turma: str
    disciplina: str
    conteudo: str
    slot_id: str
    slot_start: str
    slot_end: str


class TeacherDetectedResponse(BaseModel):
    accepted: bool
    event_name: str
    detected_at: datetime
    message: str
    lesson: Optional[LessonInfo] = Field(
        None,
        description="Aula ativa para este professor no horário de referência. Null se não houver.",
    )
    correlation_id: str = Field(..., description="UUID que rastreia a request pela cadeia de eventos")
    status: str = Field(..., description="Estágio final da cadeia: detected | class_started | content_loaded")
    degraded: bool = Field(
        False,
        description="True se o NuvemPed não respondeu e estamos em modo degradado.",
    )
    warning: Optional[str] = Field(
        None,
        description="Mensagem adicional quando algo digno de atenção aconteceu.",
    )
