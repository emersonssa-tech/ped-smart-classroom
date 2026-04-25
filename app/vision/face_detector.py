"""
Detector de face com Haar Cascade (OpenCV built-in).

Propositalmente isolado de câmera e event bus: só recebe um frame np.array
e retorna bounding boxes. Facilita testar sem hardware e trocar a
implementação (ex: DNN) no futuro sem tocar em worker.py.
"""
import logging
from pathlib import Path

import cv2
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)


class FaceDetector:
    def __init__(
        self,
        cascade_path: Optional[str] = None,
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
        min_size_px: int = 60,
    ) -> None:
        path = cascade_path or (
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        if not Path(path).exists():
            raise FileNotFoundError(f"Haar cascade não encontrado: {path}")
        self._cascade = cv2.CascadeClassifier(path)
        if self._cascade.empty():
            raise RuntimeError(f"Falha ao carregar Haar cascade: {path}")
        self._scale_factor = scale_factor
        self._min_neighbors = min_neighbors
        self._min_size = (min_size_px, min_size_px)
        logger.info(
            f"[FaceDetector] Carregado (scale={scale_factor}, "
            f"min_neighbors={min_neighbors}, min_size={min_size_px}px)"
        )

    def detect(self, frame_bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
        """
        Retorna bounding boxes (x, y, w, h) de rostos frontais detectados.
        Frame esperado em BGR (padrão do cv2.VideoCapture).
        Lista vazia se não encontrou nada.
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return []
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        # equaliza histograma -> mais robusto a variação de luz
        gray = cv2.equalizeHist(gray)
        faces = self._cascade.detectMultiScale(
            gray,
            scaleFactor=self._scale_factor,
            minNeighbors=self._min_neighbors,
            minSize=self._min_size,
        )
        return [tuple(int(v) for v in b) for b in faces]
