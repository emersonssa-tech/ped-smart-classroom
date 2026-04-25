"""
Classroom Engine — orquestra o fluxo da sala.

Etapa 5: zero acoplamento com outros módulos de domínio.
- Não importa nada de integrations/
- Só publica teacher_detected e lê o state_store
- Os handlers nos outros módulos fazem o trabalho real
"""
import logging
from datetime import datetime
from uuid import uuid4

from ..core import Event, EventNames, event_bus
from .schemas import LessonInfo, TeacherDetectedRequest, TeacherDetectedResponse
from .state_store import state_store

logger = logging.getLogger(__name__)


class ClassroomEngineService:
    async def handle_teacher_detected(
        self, payload: TeacherDetectedRequest
    ) -> TeacherDetectedResponse:
        correlation_id = str(uuid4())
        reference_time = payload.simulated_time or datetime.now()

        # Estado inicial — "detectamos, mas ainda não sabemos se há aula"
        state_store.init(correlation_id, {
            "status": "detected",
            "teacher_id": payload.teacher_id,
            "teacher_name": payload.teacher_name,
            "classroom_id": payload.classroom_id,
        })

        # Dispara a cadeia. asyncio.gather dentro do EventBus garante que
        # publish só retorna depois que TODOS os subscribers (e subpublishes
        # aninhados) resolveram.
        await event_bus.publish(Event(
            name=EventNames.TEACHER_DETECTED,
            payload={
                "correlation_id": correlation_id,
                "teacher_id": payload.teacher_id,
                "teacher_name": payload.teacher_name,
                "classroom_id": payload.classroom_id,
                "reference_time": reference_time.isoformat(),
            },
        ))

        # Lê snapshot final e limpa
        state = state_store.pop(correlation_id) or {}
        return self._build_response(state, reference_time, correlation_id)

    def _build_response(
        self,
        state: dict,
        reference_time: datetime,
        correlation_id: str,
    ) -> TeacherDetectedResponse:
        status = state.get("status", "detected")
        teacher_name = state.get("teacher_name", "?")

        if status == "content_loaded":
            lesson = LessonInfo(
                turma=state["turma"],
                disciplina=state["disciplina"],
                conteudo=state["conteudo"],
                slot_id=state["horario"]["slot_id"],
                slot_start=state["horario"]["inicio"],
                slot_end=state["horario"]["fim"],
            )
            message = (
                f"Professor {teacher_name} detectado. "
                f"Aula de {state['disciplina']} para a turma {state['turma']} "
                f"({state['horario']['inicio']}–{state['horario']['fim']})."
            )
        else:
            lesson = None
            message = (
                f"Professor {teacher_name} detectado, porém não há aula "
                f"agendada para este horário ({reference_time.strftime('%a %H:%M')})."
            )

        return TeacherDetectedResponse(
            accepted=True,
            event_name=EventNames.TEACHER_DETECTED,
            detected_at=reference_time,
            message=message,
            lesson=lesson,
            correlation_id=correlation_id,
            status=status,
        )


service = ClassroomEngineService()
