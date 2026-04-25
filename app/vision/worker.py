"""
Thread de background: captura webcam, detecta rosto, publica teacher_detected.

Payload do evento é compatível com os handlers existentes, mas com teacher_id
e teacher_name nulos (sem reconhecimento facial ainda). Os handlers do
classroom_engine e do nuvemped já tratam esse caso.
"""
import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Optional
from uuid import uuid4

import cv2

from ..core import Event, EventNames, event_bus
from .face_detector import FaceDetector

logger = logging.getLogger(__name__)


class FaceDetectorWorker:
    """Loop em thread separada. Seguro start/stop pelo lifespan do FastAPI."""

    def __init__(
        self,
        detector: FaceDetector,
        camera_index: int = 0,
        frame_width: int = 320,
        detection_interval_s: float = 0.5,
        cooldown_s: float = 10.0,
    ) -> None:
        self._detector = detector
        self._camera_index = camera_index
        self._frame_width = frame_width
        self._detection_interval = detection_interval_s
        self._cooldown = cooldown_s

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # métricas observáveis
        self.is_running: bool = False
        self.last_detection_at: Optional[datetime] = None
        self.total_detections: int = 0
        self.camera_opened: bool = False

    # ---------- lifecycle ----------

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._thread is not None:
            return
        self._loop = loop
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="face-detector-worker",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._thread = None
        self.is_running = False

    # ---------- thread body ----------

    def _run(self) -> None:
        cap = cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            logger.error(
                f"[FaceDetector] Não consegui abrir câmera {self._camera_index}. "
                f"Sistema segue rodando sem detecção."
            )
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._frame_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self._frame_width * 3 / 4))

        self.camera_opened = True
        self.is_running = True
        last_publish_ts = 0.0
        logger.info(
            f"[FaceDetector] Câmera {self._camera_index} aberta em "
            f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
            f"{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}. Loop iniciado."
        )

        try:
            while not self._stop.is_set():
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.1)
                    continue

                faces = self._detector.detect(frame)
                now_ts = time.monotonic()

                if faces and (now_ts - last_publish_ts) >= self._cooldown:
                    self._publish_detection(num_faces=len(faces))
                    last_publish_ts = now_ts

                time.sleep(self._detection_interval)
        except Exception as exc:
            logger.exception(f"[FaceDetector] Exceção no loop: {exc}")
        finally:
            cap.release()
            self.is_running = False
            self.camera_opened = False
            logger.info("[FaceDetector] Loop encerrado, câmera liberada.")

    # ---------- evento ----------

    def _publish_detection(self, num_faces: int) -> None:
        now = datetime.now()
        self.last_detection_at = now
        self.total_detections += 1
        correlation_id = str(uuid4())
        logger.info(
            f"[FaceDetector] Rosto detectado ({num_faces} rosto(s)) "
            f"cid={correlation_id[:8]} -> publicando {EventNames.TEACHER_DETECTED}"
        )
        event = Event(
            name=EventNames.TEACHER_DETECTED,
            payload={
                "correlation_id": correlation_id,
                "source": "camera",
                "teacher_id": None,
                "teacher_name": None,
                "classroom_id": None,
                "reference_time": now.isoformat(),
                "num_faces": num_faces,
            },
        )
        # publica no event loop do FastAPI de forma thread-safe
        if self._loop is not None and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(event_bus.publish(event), self._loop)
        else:
            logger.warning("[FaceDetector] Event loop indisponível, descartando evento.")
