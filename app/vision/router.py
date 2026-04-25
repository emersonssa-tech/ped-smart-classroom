"""
Endpoints de observabilidade da visão computacional.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/vision", tags=["vision"])


class VisionStatus(BaseModel):
    enabled: bool
    is_running: bool
    camera_opened: bool
    total_detections: int
    last_detection_at: Optional[datetime]


@router.get("/status", response_model=VisionStatus)
async def vision_status(request: Request) -> VisionStatus:
    worker = getattr(request.app.state, "face_worker", None)
    if worker is None:
        return VisionStatus(
            enabled=False,
            is_running=False,
            camera_opened=False,
            total_detections=0,
            last_detection_at=None,
        )
    return VisionStatus(
        enabled=True,
        is_running=worker.is_running,
        camera_opened=worker.camera_opened,
        total_detections=worker.total_detections,
        last_detection_at=worker.last_detection_at,
    )
