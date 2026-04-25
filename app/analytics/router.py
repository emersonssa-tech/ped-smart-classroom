from fastapi import APIRouter, HTTPException, Query

from .factory import get_metrics, get_storage
from typing import Optional

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/system", summary="Visão geral do sistema")
async def system_metrics() -> dict:
    return await get_metrics().get_system_metrics()


@router.get("/teacher/{teacher_id}", summary="Performance de um professor")
async def teacher_performance(teacher_id: str) -> dict:
    return await get_metrics().get_teacher_performance(teacher_id)


@router.get("/class/{classroom_id}", summary="Uso de uma sala/turma")
async def class_usage(classroom_id: str) -> dict:
    return await get_metrics().get_class_usage(classroom_id)


# Endpoint utilitário pra inspeção bruta
@router.get("/events", summary="Lista eventos brutos com filtros")
async def list_events(
    event_type: Optional[str] = None,
    teacher_id: Optional[str] = None,
    classroom_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    items = await get_storage().query(
        event_type=event_type,
        teacher_id=teacher_id,
        classroom_id=classroom_id,
        correlation_id=correlation_id,
        limit=limit,
    )
    return {"count": len(items), "items": items}
