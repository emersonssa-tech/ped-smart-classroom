"""
Wrapper resiliente em cima do HttpNuvemPedClient.

Padrão decorator: implementa o mesmo Protocol, chama o client real por baixo
e adiciona cache + fallback.

Fluxo por método:
  1. Tenta chamar o client HTTP.
  2. Se sucesso -> cacheia resposta (inclusive None, pra economizar chamada)
     e retorna.
  3. Se falha (timeout/unavailable) -> tenta servir do cache.
     3a. Cache hit -> retorna + loga warning.
     3b. Cache miss -> propaga a exceção (NuvemPedTimeout / Unavailable).

O service em classroom_engine decide o que fazer quando a exceção chega.
"""
import logging
from dataclasses import asdict
from datetime import datetime

from typing import Optional

from .cache import FileCache
from .client import (
    ClassInfo,
    NuvemPedError,
    NuvemPedTimeout,
    NuvemPedUnavailable,
    ScheduleEntry,
)
from .http import HttpNuvemPedClient

logger = logging.getLogger(__name__)


class ResilientNuvemPedClient:
    def __init__(
        self,
        inner: HttpNuvemPedClient,
        cache: FileCache,
        current_class_ttl: int = 60,    # aula atual: cache curto
        schedule_ttl: int = 3600,       # grade: cache longo
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._current_class_ttl = current_class_ttl
        self._schedule_ttl = schedule_ttl

    async def aclose(self) -> None:
        await self._inner.aclose()

    # ---------- API ----------

    async def get_current_class(
        self,
        teacher_id: str,
        reference_time: Optional[datetime] = None,
    ) -> Optional[ClassInfo]:
        cache_key = self._key_current_class(teacher_id, reference_time)
        try:
            result = await self._inner.get_current_class(teacher_id, reference_time)
            self._cache.set(
                cache_key,
                asdict(result) if result else None,
                ttl=self._current_class_ttl,
            )
            return result
        except NuvemPedError as exc:
            cached = self._cache.get(cache_key)
            if cached is None and not self._cache_has(cache_key):
                # sem cache -> não tem como servir
                logger.error(f"[NuvemPed:resilient] API falhou e sem cache para {cache_key}: {exc}")
                raise
            logger.warning(
                f"[NuvemPed:resilient] API falhou ({type(exc).__name__}); "
                f"servindo do cache: {cache_key}"
            )
            return ClassInfo(**cached) if cached else None

    async def get_teacher_schedule(self, teacher_id: str) -> list[ScheduleEntry]:
        cache_key = self._key_schedule(teacher_id)
        try:
            result = await self._inner.get_teacher_schedule(teacher_id)
            self._cache.set(
                cache_key,
                [asdict(e) for e in result],
                ttl=self._schedule_ttl,
            )
            return result
        except NuvemPedError as exc:
            cached = self._cache.get(cache_key)
            if cached is None and not self._cache_has(cache_key):
                logger.error(f"[NuvemPed:resilient] API falhou e sem cache para {cache_key}: {exc}")
                raise
            logger.warning(
                f"[NuvemPed:resilient] API falhou ({type(exc).__name__}); "
                f"servindo schedule do cache: {cache_key}"
            )
            return [ScheduleEntry(**e) for e in (cached or [])]

    # ---------- helpers ----------

    @staticmethod
    def _key_current_class(teacher_id: str, reference_time: Optional[datetime]) -> str:
        rt = reference_time.isoformat() if reference_time else "now"
        return f"current_class:{teacher_id}:{rt}"

    @staticmethod
    def _key_schedule(teacher_id: str) -> str:
        return f"schedule:{teacher_id}"

    def _cache_has(self, key: str) -> bool:
        """
        Diferencia 'cache miss' de 'cache hit com valor None'.
        get() retorna None em ambos os casos, então precisamos olhar pro dict interno.
        """
        with self._cache._lock:  # noqa: SLF001 — acesso interno consciente
            entry = self._cache._data.get(key)
            if entry is None:
                return False
            return not FileCache._is_expired(entry)
