"""
Event subscribers do módulo integrations/nuvemped.

Dois handlers independentes que, juntos, transformam uma detecção em dois
eventos separados (class_started e content_loaded):

  1. on_teacher_detected:  chama NuvemPed, publica class_started.
  2. on_class_started:     puxa o conteúdo da aula, publica content_loaded.

Por que dois handlers e não um só? Porque num sistema real o schedule e o
content viriam de APIs diferentes. Mantendo handlers separados, quando isso
acontecer de verdade, só o método do client precisa mudar — a topologia
dos eventos continua.

Como o client atual retorna turma+disciplina+conteúdo numa tirada só, usamos
uma cache local (_scoped_cache) para o segundo handler enxergar o conteúdo
que a primeira chamada trouxe, sem fazer uma requisição HTTP duplicada.
"""
import logging
from datetime import datetime
from typing import Any

from ...core import Event, EventNames, event_bus
from .client import ClassInfo, NuvemPedError
from .factory import get_nuvemped_client

logger = logging.getLogger(__name__)


# Cache request-scoped: correlation_id -> ClassInfo da chamada inicial.
# Entries são criadas em on_teacher_detected e removidas em on_class_started.
_scoped_cache: dict[str, ClassInfo] = {}


async def on_teacher_detected(event: Event) -> None:
    """Chama NuvemPed → se achou aula, publica class_started."""
    p: dict[str, Any] = event.payload
    cid = p["correlation_id"]
    teacher_id = p.get("teacher_id")
    ref_time = datetime.fromisoformat(p["reference_time"])

    # Detecção sem identificação (ex: câmera ainda sem reconhecimento facial).
    # Não há como consultar schedule sem teacher_id — pula silenciosamente.
    if teacher_id is None:
        logger.info(
            f"[NuvemPed/handler] teacher_detected sem teacher_id cid={cid[:8]} "
            f"(source={p.get('source', '?')}). Aguardando etapa de reconhecimento."
        )
        return

    client = get_nuvemped_client()
    try:
        class_info = await client.get_current_class(teacher_id, ref_time)
    except NuvemPedError as exc:
        logger.warning(
            f"[NuvemPed/handler] NuvemPed indisponível cid={cid[:8]}: {exc}. "
            f"Não publicará class_started."
        )
        return

    if class_info is None:
        logger.info(
            f"[NuvemPed/handler] Sem aula para teacher_id={teacher_id} "
            f"em {ref_time.strftime('%a %H:%M')} cid={cid[:8]}"
        )
        return

    # Guarda pro handler de class_started achar o conteudo depois
    _scoped_cache[cid] = class_info

    await event_bus.publish(Event(
        name=EventNames.CLASS_STARTED,
        payload={
            "correlation_id": cid,
            "teacher_id": teacher_id,
            "teacher_name": p["teacher_name"],
            "turma": class_info.turma,
            "disciplina": class_info.disciplina,
            "horario": {
                "slot_id": class_info.slot_id,
                "inicio": class_info.slot_start,
                "fim": class_info.slot_end,
            },
            "reference_time": p["reference_time"],
        },
    ))


async def on_class_started(event: Event) -> None:
    """Class started → busca conteúdo (do cache local) → publica content_loaded."""
    p: dict[str, Any] = event.payload
    cid = p["correlation_id"]

    class_info = _scoped_cache.pop(cid, None)
    if class_info is None:
        # Em produção: seria uma chamada separada pro content service.
        # Sem o cache, não temos o conteudo disponível — só logga.
        logger.warning(
            f"[NuvemPed/handler] class_started sem cache cid={cid[:8]}. "
            f"Num content-service real, faríamos GET /content aqui."
        )
        return

    await event_bus.publish(Event(
        name=EventNames.CONTENT_LOADED,
        payload={
            "correlation_id": cid,
            "turma": class_info.turma,
            "disciplina": class_info.disciplina,
            "conteudo": class_info.conteudo,
        },
    ))


def register_subscribers() -> None:
    event_bus.subscribe(EventNames.TEACHER_DETECTED, on_teacher_detected)
    event_bus.subscribe(EventNames.CLASS_STARTED, on_class_started)
