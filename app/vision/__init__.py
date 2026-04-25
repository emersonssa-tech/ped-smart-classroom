from .lifecycle import start_face_detector, stop_face_detector
from .router import router

# FaceDetector e Worker ficam como import tardio (evita custo do cv2
# quando a câmera está desligada)
__all__ = ["start_face_detector", "stop_face_detector", "router"]
