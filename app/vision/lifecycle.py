"""
Wire-up do face detector ao lifespan do FastAPI.

Motivo de existir em arquivo separado: isola o import de cv2 — se OpenCV
não estiver instalado (ou CAMERA_ENABLED=false), o main.py nem importa
esse módulo. Mantém o cold path enxuto.
"""
import asyncio
import logging
from typing import Optional

from fastapi import FastAPI

from ..core import get_settings
from .worker import FaceDetectorWorker

logger = logging.getLogger(__name__)


async def start_face_detector(app: FastAPI) -> Optional[FaceDetectorWorker]:
    """
    Tenta iniciar o worker. Retorna None em caso de falha — sistema segue
    funcionando sem câmera.
    """
    settings = get_settings()
    if not settings.camera_enabled:
        logger.info("[Vision] CAMERA_ENABLED=false, pulando start do face detector.")
        return None

    try:
        # import tardio pra não pagar o custo do cv2 quando câmera está desligada
        from .face_detector import FaceDetector

        detector = FaceDetector(min_size_px=settings.camera_min_face_size)
        worker = FaceDetectorWorker(
            detector=detector,
            camera_index=settings.camera_index,
            frame_width=settings.camera_frame_width,
            detection_interval_s=settings.camera_detection_interval,
            cooldown_s=settings.camera_detection_cooldown,
        )
        loop = asyncio.get_running_loop()
        worker.start(loop)
        app.state.face_worker = worker
        logger.info("[Vision] Face detector iniciado.")
        return worker
    except ImportError as e:
        logger.error(
            f"[Vision] OpenCV não disponível ({e}). "
            f"Instale com: pip install opencv-python-headless"
        )
    except Exception as e:
        logger.exception(f"[Vision] Falha ao iniciar face detector: {e}")
    return None


async def stop_face_detector(app: FastAPI) -> None:
    worker: Optional[FaceDetectorWorker] = getattr(app.state, "face_worker", None)
    if worker is not None:
        logger.info("[Vision] Parando face detector...")
        worker.stop()
