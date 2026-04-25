"""
Factory do VoiceAIProcessor.

Lê settings e monta a cadeia STT + LLM + processor. Singleton por processo.

Modos:
  - voice_ai_mode="auto":    se tem api_key → online com llm; senão offline
  - voice_ai_mode="online":  força construir o llm (erro em runtime se não tiver key)
  - voice_ai_mode="offline": não constrói llm, só regras

Providers suportados: "openai" (qualquer endpoint OpenAI-compat) e "anthropic".
"""
import logging
from functools import lru_cache

from ..core import get_settings
from .llm import AnthropicLLMClient, LLMClient, OpenAICompatLLMClient
from .processor import VoiceAIProcessor
from .stt import PassthroughSTT
from typing import Optional

logger = logging.getLogger(__name__)


def _build_llm(settings) -> Optional[LLMClient]:
    """Retorna None se não houver credencial — processor cairá em offline."""
    if not settings.voice_ai_api_key:
        logger.info("[VoiceAI] Sem API key; processor rodará apenas em modo offline.")
        return None

    provider = (settings.voice_ai_provider or "openai").lower()
    if provider == "anthropic":
        logger.info(
            f"[VoiceAI] LLM provider=anthropic model={settings.voice_ai_model}"
        )
        return AnthropicLLMClient(
            api_key=settings.voice_ai_api_key,
            model=settings.voice_ai_model,
            base_url=settings.voice_ai_base_url or None,
            timeout=settings.voice_ai_timeout,
        )

    # default: openai-compat
    logger.info(
        f"[VoiceAI] LLM provider=openai-compat base={settings.voice_ai_base_url} "
        f"model={settings.voice_ai_model}"
    )
    return OpenAICompatLLMClient(
        base_url=settings.voice_ai_base_url,
        api_key=settings.voice_ai_api_key,
        model=settings.voice_ai_model,
        timeout=settings.voice_ai_timeout,
    )


@lru_cache
def get_voice_ai_processor() -> VoiceAIProcessor:
    settings = get_settings()
    return VoiceAIProcessor(
        stt=PassthroughSTT(),
        llm=_build_llm(settings),
        mode=(settings.voice_ai_mode or "auto").lower(),
        max_tokens=settings.voice_ai_max_tokens,
        temperature=settings.voice_ai_temperature,
        json_mode=settings.voice_ai_json_mode,
        shadow_rules_enabled=settings.telemetry_shadow_rules,
        memory_lookup_enabled=settings.memory_lookup_enabled,
    )
