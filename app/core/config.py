from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PED Smart Classroom"
    app_version: str = "0.1.0"
    debug: bool = True
    environment: str = "development"

    # NuvemPed client
    nuvemped_base_url: str = "http://localhost:8001"
    nuvemped_api_key: str = ""
    nuvemped_timeout: float = 3.0
    nuvemped_retries: int = 1
    nuvemped_cache_path: str = ".cache/nuvemped.json"
    nuvemped_cache_ttl: int = 3600
    nuvemped_current_class_ttl: int = 60

    # Vision / Webcam
    camera_enabled: bool = False              # default off: requer hardware
    camera_index: int = 0                     # geralmente 0 = webcam padrão
    camera_frame_width: int = 320             # resolução reduzida p/ performance
    camera_min_face_size: int = 60            # ignora rostos muito pequenos (ruído)
    camera_detection_interval: float = 0.5    # segundos entre detecções
    camera_detection_cooldown: float = 10.0   # debounce: evento 1x a cada N segs

    # Voice AI (LLM + STT)
    voice_ai_mode: str = "auto"                # "auto" | "online" | "offline"
    voice_ai_provider: str = "openai"          # "openai" | "anthropic"
    voice_ai_base_url: str = "https://api.openai.com/v1"
    voice_ai_api_key: str = ""                 # vazio → força modo offline em "auto"
    voice_ai_model: str = "gpt-4o-mini"        # qualquer modelo do provider
    voice_ai_timeout: float = 8.0              # LLM demora, 8s é razoável
    voice_ai_max_tokens: int = 200             # resposta é sempre JSON curto
    voice_ai_temperature: float = 0.0          # determinístico para intents
    voice_ai_json_mode: bool = True            # tenta response_format={"type":"json_object"}

    # Analytics
    analytics_backend: str = "sqlite"          # "sqlite" (futuro: "postgres")
    analytics_sqlite_path: str = ".analytics/events.db"

    # Telemetry (observabilidade do voice — accuracy LLM vs regras)
    telemetry_voice_path: str = ".telemetry/voice.jsonl"
    telemetry_recent_buffer_size: int = 500
    telemetry_shadow_rules: bool = True        # roda regras junto com LLM pra comparação

    # Memory (aprendizado contextual)
    memory_path: str = "memory/memory_store.json"
    memory_max_history: int = 500
    memory_history_min_confidence: float = 0.8
    memory_lookup_enabled: bool = True

    # Deploy (cloud)
    api_key: Optional[str] = None             # se None, API é pública. Se setada, exige header X-API-Key
    cors_origins: str = "*"                   # CSV de origens; "*" = qualquer
    public_paths: str = "/health,/ui,/docs,/openapi.json,/redoc"  # sem auth aqui

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Cache para não reler o .env a cada request."""
    return Settings()
