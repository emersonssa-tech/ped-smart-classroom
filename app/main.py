import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .classroom_engine import register_subscribers as register_classroom_subs
from .classroom_engine import router as classroom_router
from .core import get_settings
from .core.models import HealthResponse
from .integrations import register_subscribers as register_integration_subs
from .vision import router as vision_router
from .vision import start_face_detector, stop_face_detector
from .voice_engine import register_subscribers as register_voice_subs
from .voice_engine import router as voice_router
from .voice_ai import router as voice_ai_router
from .analytics import init_analytics, shutdown_analytics, router as analytics_router
from .telemetry import init_telemetry, shutdown_telemetry, router as telemetry_router
from .memory import init_memory, shutdown_memory, router as memory_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando PED Smart Classroom...")
    register_classroom_subs()
    register_integration_subs()
    register_voice_subs()
    await init_analytics()
    await init_telemetry()
    await init_memory()
    logger.info("Subscribers de eventos registrados.")

    # Face detector (opcional, config via CAMERA_ENABLED)
    await start_face_detector(app)

    yield
    logger.info("Encerrando PED Smart Classroom...")

    # Para o worker da câmera antes de fechar http client
    await stop_face_detector(app)

    # fecha connection pool do httpx
    from .integrations.nuvemped import get_nuvemped_client
    try:
        await get_nuvemped_client().aclose()
    except Exception as e:
        logger.warning(f"Falha ao fechar NuvemPedClient: {e}")

    # fecha clients do voice_ai (LLM + STT)
    from .voice_ai import get_voice_ai_processor
    try:
        await get_voice_ai_processor().aclose()
    except Exception as e:
        logger.warning(f"Falha ao fechar VoiceAIProcessor: {e}")

    # fecha analytics storage
    try:
        await shutdown_analytics()
    except Exception as e:
        logger.warning(f"Falha ao fechar Analytics: {e}")

    try:
        await shutdown_telemetry()
    except Exception as e:
        logger.warning(f"Falha ao fechar Telemetry: {e}")

    try:
        await shutdown_memory()
    except Exception as e:
        logger.warning(f"Falha ao fechar Memory: {e}")


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)


# CORS configurável via env CORS_ORIGINS (CSV); default "*" pra dev.
_cors = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key opcional — só ativa se env API_KEY estiver setada
from .core.middleware import api_key_middleware  # noqa: E402
app.middleware("http")(api_key_middleware)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        timestamp=datetime.utcnow(),
    )


# Monta os routers de domínio
app.include_router(classroom_router)
app.include_router(vision_router)
app.include_router(voice_router)
app.include_router(voice_ai_router)
app.include_router(analytics_router)
app.include_router(telemetry_router)
app.include_router(memory_router)


# --- Frontend estático ---
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Atalho: / -> /ui/"""
    return RedirectResponse(url="/ui/")
