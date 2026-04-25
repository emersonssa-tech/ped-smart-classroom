"""
Integração de painel (stub).

Hoje só loga o que seria enviado. Representa um sistema externo (painel LED,
TV da sala, app mobile dos alunos) que reage aos eventos do domínio.

Importante: se inscreve em eventos emitidos pelo classroom_engine/nuvemped,
sem conhecer a existência dos outros módulos.
"""
import logging

from ..core import Event, EventNames, event_bus

logger = logging.getLogger(__name__)


async def on_class_started(event: Event) -> None:
    p = event.payload
    logger.info(
        f"[Panel] (stub) Exibiria cabeçalho da aula cid={p['correlation_id'][:8]} "
        f"{p['disciplina']} — turma {p['turma']} "
        f"({p['horario']['inicio']}–{p['horario']['fim']})"
    )


async def on_content_loaded(event: Event) -> None:
    p = event.payload
    logger.info(
        f"[Panel] (stub) Atualizaria conteúdo cid={p['correlation_id'][:8]} "
        f"'{p['conteudo']}' para turma {p['turma']}"
    )


def register_subscribers() -> None:
    event_bus.subscribe(EventNames.CLASS_STARTED, on_class_started)
    event_bus.subscribe(EventNames.CONTENT_LOADED, on_content_loaded)
