from fastapi import APIRouter, Query

from .factory import get_telemetry_store

router = APIRouter(prefix="/telemetry/voice", tags=["telemetry"])


@router.get("/summary", summary="Agregação de telemetria de voz")
async def telemetry_summary():
    return get_telemetry_store().summary()


@router.get("/recent", summary="Últimos N eventos gravados")
async def telemetry_recent(limit: int = Query(50, ge=1, le=500)):
    return {"items": get_telemetry_store().recent(limit=limit)}


@router.get(
    "/disagreements",
    summary="Casos onde LLM e regras (shadow) divergiram",
)
async def telemetry_disagreements(limit: int = Query(50, ge=1, le=500)):
    return {"items": get_telemetry_store().disagreements(limit=limit)}


@router.get(
    "/unrecognized",
    summary="Comandos não reconhecidos (queue de melhoria)",
)
async def telemetry_unrecognized(limit: int = Query(50, ge=1, le=500)):
    return {"items": get_telemetry_store().unrecognized(limit=limit)}


@router.post(
    "/clear",
    summary="Apaga arquivo de telemetria e zera memória (dev/teste)",
)
async def telemetry_clear():
    await get_telemetry_store().clear()
    return {"cleared": True}
