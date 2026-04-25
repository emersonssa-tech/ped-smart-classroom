"""
Cliente HTTP real para a NuvemPed (fake ou produção).

- Usa httpx.AsyncClient com timeout explícito.
- Retry simples (1 tentativa extra) em erros transientes de rede.
- Mapeia falhas pra exceções específicas (NuvemPedTimeout, NuvemPedUnavailable).
- Traduz JSON da API -> DTOs internos (ClassInfo / ScheduleEntry).

A separação entre este client e o ResilientNuvemPedClient (cache/fallback)
é proposital: este arquivo se preocupa só com "falar HTTP", nada mais.
"""
import asyncio
import logging
from datetime import datetime

import httpx

from .client import ClassInfo, NuvemPedTimeout, NuvemPedUnavailable, ScheduleEntry
from typing import Optional

logger = logging.getLogger(__name__)


class HttpNuvemPedClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: float = 3.0,
        retries: int = 1,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._retries = retries
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers=headers,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    # ---------- API pública ----------

    async def get_current_class(
        self,
        teacher_id: str,
        reference_time: Optional[datetime] = None,
    ) -> Optional[ClassInfo]:
        params = {}
        if reference_time is not None:
            params["at"] = reference_time.isoformat()

        data = await self._request(
            "GET",
            f"/teachers/{teacher_id}/current-class",
            params=params,
        )
        if data is None:
            return None
        return ClassInfo(
            turma=data["turma"],
            disciplina=data["disciplina"],
            conteudo=data["conteudo"],
            slot_id=data["slot"]["id"],
            slot_start=data["slot"]["start"],
            slot_end=data["slot"]["end"],
        )

    async def get_teacher_schedule(self, teacher_id: str) -> list[ScheduleEntry]:
        data = await self._request("GET", f"/teachers/{teacher_id}/schedule")
        if not data:
            return []
        return [
            ScheduleEntry(
                day_of_week=e["day_of_week"],
                turma=e["turma"],
                disciplina=e["disciplina"],
                slot_id=e["slot"]["id"],
                slot_start=e["slot"]["start"],
                slot_end=e["slot"]["end"],
            )
            for e in data
        ]

    # ---------- internals ----------

    async def _request(self, method: str, path: str, **kwargs):
        """
        Faz a chamada com retry. Converte exceções httpx -> NuvemPed*.
        Retorna o JSON parseado, ou None se o body for JSON null/vazio.
        """
        last_exc: Optional[Exception] = None
        attempts = self._retries + 1

        for attempt in range(1, attempts + 1):
            try:
                response = await self._http.request(method, path, **kwargs)
                # 4xx não repete (erro do lado do cliente)
                if 400 <= response.status_code < 500:
                    if response.status_code == 404:
                        logger.info(f"[NuvemPed:http] 404 em {path}")
                        return None
                    response.raise_for_status()
                # 5xx: tenta de novo
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"5xx: {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                # sucesso
                if response.status_code == 204 or not response.content:
                    return None
                return response.json()

            except httpx.TimeoutException as e:
                last_exc = e
                logger.warning(f"[NuvemPed:http] timeout tent.{attempt}/{attempts} em {path}")
            except httpx.ConnectError as e:
                last_exc = e
                logger.warning(f"[NuvemPed:http] connect error tent.{attempt}/{attempts}: {e}")
            except httpx.HTTPStatusError as e:
                last_exc = e
                logger.warning(
                    f"[NuvemPed:http] http error tent.{attempt}/{attempts}: "
                    f"status={e.response.status_code}"
                )
            except httpx.HTTPError as e:
                last_exc = e
                logger.warning(f"[NuvemPed:http] http error tent.{attempt}/{attempts}: {e}")

            if attempt < attempts:
                await asyncio.sleep(0.2 * attempt)  # backoff linear curto

        # esgotou retries
        assert last_exc is not None
        if isinstance(last_exc, httpx.TimeoutException):
            raise NuvemPedTimeout(f"Timeout após {attempts} tentativas em {path}") from last_exc
        raise NuvemPedUnavailable(
            f"NuvemPed inacessível após {attempts} tentativas em {path}: {last_exc}"
        ) from last_exc
