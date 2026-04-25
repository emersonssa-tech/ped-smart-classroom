"""
Factory do NuvemPedClient.

Monta a cadeia de responsabilidades:
    ResilientNuvemPedClient(
        inner=HttpNuvemPedClient(...),
        cache=FileCache(...),
    )

Singleton por processo (lru_cache). Troca do fake para produção é só mudar
NUVEMPED_BASE_URL no .env.
"""
import logging
from functools import lru_cache

from ...core import get_settings
from .cache import FileCache
from .client import NuvemPedClient
from .http import HttpNuvemPedClient
from .resilient import ResilientNuvemPedClient

logger = logging.getLogger(__name__)


@lru_cache
def get_nuvemped_client() -> NuvemPedClient:
    settings = get_settings()
    logger.info(
        f"[NuvemPed] Cliente http={settings.nuvemped_base_url} "
        f"timeout={settings.nuvemped_timeout}s retries={settings.nuvemped_retries} "
        f"cache={settings.nuvemped_cache_path}"
    )
    http = HttpNuvemPedClient(
        base_url=settings.nuvemped_base_url,
        api_key=settings.nuvemped_api_key,
        timeout=settings.nuvemped_timeout,
        retries=settings.nuvemped_retries,
    )
    cache = FileCache(
        path=settings.nuvemped_cache_path,
        default_ttl=settings.nuvemped_cache_ttl,
    )
    return ResilientNuvemPedClient(
        inner=http,
        cache=cache,
        current_class_ttl=settings.nuvemped_current_class_ttl,
        schedule_ttl=settings.nuvemped_cache_ttl,
    )
