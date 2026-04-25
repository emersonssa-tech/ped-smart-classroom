"""
Contratos do cliente NuvemPed.

- ClassInfo, ScheduleEntry: DTOs internos (dataclass). Propositalmente
  separados dos schemas da API externa: se a NuvemPed mudar o JSON,
  apenas o http.py precisa mapear.

- NuvemPedClient: Protocol async. Qualquer classe que implemente os
  dois métodos satisfaz o contrato (sem exigir herança).

- Exceções: hierarquia específica pra que o service capture só o que faz
  sentido, nunca `except Exception`.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Optional


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClassInfo:
    turma: str
    disciplina: str
    conteudo: str
    slot_id: str
    slot_start: str   # "HH:MM"
    slot_end: str     # "HH:MM"


@dataclass(frozen=True)
class ScheduleEntry:
    day_of_week: int   # 0=seg, 4=sex
    turma: str
    disciplina: str
    slot_id: str
    slot_start: str
    slot_end: str


# ---------------------------------------------------------------------------
# Exceções
# ---------------------------------------------------------------------------

class NuvemPedError(Exception):
    """Base para todas as falhas do cliente NuvemPed."""


class NuvemPedTimeout(NuvemPedError):
    """Timeout na chamada HTTP."""


class NuvemPedUnavailable(NuvemPedError):
    """API inacessível (offline, ECONNREFUSED, 5xx) e sem cache utilizável."""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class NuvemPedClient(Protocol):
    async def get_current_class(
        self,
        teacher_id: str,
        reference_time: Optional[datetime] = None,
    ) -> Optional[ClassInfo]:
        """
        Aula ativa do professor no horário de referência (ou now).
        Retorna None se o professor não estiver dando aula nesse momento.
        Pode levantar NuvemPedTimeout ou NuvemPedUnavailable.
        """
        ...

    async def get_teacher_schedule(
        self,
        teacher_id: str,
    ) -> list[ScheduleEntry]:
        """
        Grade completa do professor. Lista vazia se não houver escala.
        Pode levantar NuvemPedTimeout ou NuvemPedUnavailable.
        """
        ...

    async def aclose(self) -> None:
        """Libera recursos (connection pool, handles de arquivo, etc)."""
        ...
