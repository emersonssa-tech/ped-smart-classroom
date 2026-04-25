"""
Event subscribers do classroom_engine.

Este módulo é o ÚNICO dono do state_store. Integrações externas publicam
eventos; aqui a gente reage e registra no estado da request.
"""
import logging

from ..core import Event, EventNames, event_bus
from .state_store import state_store

logger = logging.getLogger(__name__)


async def on_teacher_detected(event: Event) -> None:
    """Audita a detecção. Não toca no schedule — isso é responsabilidade da integração."""
    p = event.payload
    logger.info(
        f"[ClassroomEngine] teacher_detected cid={p['correlation_id'][:8]} "
        f"teacher={p['teacher_name']} ref={p['reference_time']}"
    )


async def on_class_started(event: Event) -> None:
    """Registra que a aula começou (com turma/disciplina/horário)."""
    p = event.payload
    cid = p["correlation_id"]
    state_store.update(cid, {
        "status": "class_started",
        "turma": p["turma"],
        "disciplina": p["disciplina"],
        "horario": p["horario"],
    })
    logger.info(
        f"[ClassroomEngine] class_started cid={cid[:8]} "
        f"{p['disciplina']}/{p['turma']} "
        f"{p['horario']['inicio']}–{p['horario']['fim']}"
    )


async def on_content_loaded(event: Event) -> None:
    """Anexa o conteúdo da aula ao estado."""
    p = event.payload
    cid = p["correlation_id"]
    state_store.update(cid, {
        "status": "content_loaded",
        "conteudo": p["conteudo"],
    })
    logger.info(
        f"[ClassroomEngine] content_loaded cid={cid[:8]} "
        f"conteudo='{p['conteudo']}'"
    )


def register_subscribers() -> None:
    event_bus.subscribe(EventNames.TEACHER_DETECTED, on_teacher_detected)
    event_bus.subscribe(EventNames.CLASS_STARTED, on_class_started)
    event_bus.subscribe(EventNames.CONTENT_LOADED, on_content_loaded)
