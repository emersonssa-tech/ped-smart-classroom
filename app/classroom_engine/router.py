from datetime import datetime

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from ..core import Event, EventNames, event_bus
from .schemas import TeacherDetectedRequest, TeacherDetectedResponse
from .service import service
from typing import Optional

router = APIRouter(prefix="/classroom", tags=["classroom-engine"])


@router.post(
    "/simulate-teacher",
    response_model=TeacherDetectedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Simula a detecção de um professor na sala",
)
async def simulate_teacher(payload: TeacherDetectedRequest) -> TeacherDetectedResponse:
    return await service.handle_teacher_detected(payload)


# --- Encerramento de aula ----------------------------------------------------

class EndClassRequest(BaseModel):
    correlation_id: str = Field(
        ...,
        description=(
            "ID do class_started que está sendo encerrado. "
            "Sem isso, analytics não consegue parear início↔fim e calcular duração."
        ),
    )
    teacher_id: Optional[str] = None
    classroom_id: Optional[str] = None
    reason: str = "manual"


class EndClassResponse(BaseModel):
    accepted: bool
    correlation_id: str
    ended_at: datetime


@router.post(
    "/end-class",
    response_model=EndClassResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encerra uma aula (publica class_ended pareando com class_started por correlation_id)",
)
async def end_class(payload: EndClassRequest) -> EndClassResponse:
    now = datetime.utcnow()
    await event_bus.publish(Event(
        name=EventNames.CLASS_ENDED,
        payload={
            "correlation_id": payload.correlation_id,
            "teacher_id": payload.teacher_id,
            "classroom_id": payload.classroom_id,
            "ended_at": now.isoformat(),
            "reason": payload.reason,
        },
    ))
    return EndClassResponse(
        accepted=True,
        correlation_id=payload.correlation_id,
        ended_at=now,
    )
