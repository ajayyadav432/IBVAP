# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.face.detector
# Description: OpenCV YuNet face detection adapter and normalized Face schema.
# License: Apache-2.0 (Application) / MIT (YuNet model)
# ==============================================================================

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
from pathlib import Path
import threading
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import inference_logger


@dataclass
class Face:
    """
    Normalized face detection structure.
    NOTE: Represents visual face localization ONLY, not biometric identity or recognition.
    """
    bbox: List[int]                                    # [x1, y1, x2, y2]
    confidence: float                                  # Detection confidence score [0.0, 1.0]
    landmarks: Optional[List[List[int]]] = None       # 5 facial landmarks: [[x, y], ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": [int(v) for v in self.bbox],
            "confidence": round(float(self.confidence), 4),
            "landmarks": self.landmarks,
        }


class FaceDetector(ABC):
    """Abstract base class for face detectors."""

    @abstractmethod
    def detect(self, frame: np.ndarray, conf_threshold: Optional[float] = None) -> List[Face]:
        """Detect visible faces in a BGR image frame."""
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata and runtime parameters."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if model is loaded and ready."""
        pass


class YuNetFaceDetector(FaceDetector):
    """
    OpenCV YuNet Face Detector adapter using cv2.FaceDetectorYN.
    Performs fast, lightweight face localization and 5-point facial landmark extraction.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf_threshold: float = 0.50,
        nms_threshold: float = 0.30,
        top_k: int = 5000,
    ):
        self.model_path = Path(model_path or settings.YUNET_MODEL_PATH)
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.top_k = top_k
        self._detector: Optional[cv2.FaceDetectorYN] = None
        self._current_input_size: Tuple[int, int] = (320, 320)
        self.device: str = "CPU"
        self._lock = threading.Lock()

        self._load_model()

    def _load_model(self) -> None:
        """Initialize OpenCV FaceDetectorYN instance."""
        if not self.model_path.exists():
            err_msg = f"YuNet face model file not found at: {self.model_path}"
            inference_logger.error(err_msg)
            raise FileNotFoundError(err_msg)

        try:
            self._detector = cv2.FaceDetectorYN.create(
                model=str(self.model_path),
                config="",
                input_size=self._current_input_size,
                score_threshold=float(self.conf_threshold),
                nms_threshold=float(self.nms_threshold),
                top_k=int(self.top_k),
                backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
                target_id=cv2.dnn.DNN_TARGET_CPU,
            )
            self.device = "CPU (OpenCV DNN)"
            inference_logger.info(f"Loaded YuNet Face Detector '{self.model_path.name}' successfully.")
        except Exception as exc:
            inference_logger.error(f"Failed to initialize YuNet FaceDetectorYN: {exc}")
            raise

    def detect(self, frame: np.ndarray, conf_threshold: Optional[float] = None) -> List[Face]:
        """
        Detect faces in a BGR video frame and return normalized Face objects.
        """
        if frame is None or frame.size == 0 or self._detector is None:
            return []

        h, w = frame.shape[:2]
        active_conf = conf_threshold if conf_threshold is not None else self.conf_threshold
        active_conf = max(0.01, min(1.0, float(active_conf)))

        with self._lock:
            try:
                if (w, h) != self._current_input_size:
                    self._detector.setInputSize((w, h))
                    self._current_input_size = (w, h)

                self._detector.setScoreThreshold(active_conf)
                ret_val, raw_faces = self._detector.detect(frame)
                if raw_faces is None or len(raw_faces) == 0:
                    return []

                faces: List[Face] = []
                for row in raw_faces:
                    # YuNet format: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rcm, y_rcm, x_lcm, y_lcm, conf]
                    fx, fy, fw, fh = row[:4]
                    conf = float(row[14])

                    if not (math.isfinite(fx) and math.isfinite(fy) and math.isfinite(fw) and math.isfinite(fh) and math.isfinite(conf)):
                        continue

                    x1 = max(0, int(round(fx)))
                    y1 = max(0, int(round(fy)))
                    x2 = min(w, int(round(fx + fw)))
                    y2 = min(h, int(round(fy + fh)))

                    if x2 <= x1 or y2 <= y1:
                        continue

                    # Extract 5 facial keypoints
                    landmarks = []
                    valid_landmarks = True
                    for k in range(5):
                        lx_raw = row[4 + 2 * k]
                        ly_raw = row[5 + 2 * k]
                        if not (math.isfinite(lx_raw) and math.isfinite(ly_raw)):
                            valid_landmarks = False
                            break
                        lx = int(round(lx_raw))
                        ly = int(round(ly_raw))
                        landmarks.append([lx, ly])

                    faces.append(
                        Face(
                            bbox=[x1, y1, x2, y2],
                            confidence=conf,
                            landmarks=landmarks if valid_landmarks else None,
                        )
                    )

                return faces
            except Exception as exc:
                inference_logger.error(f"YuNet face detection execution error: {exc}")
                return []

    def get_model_info(self) -> Dict[str, Any]:
        """Return model metadata."""
        return {
            "model_name": "YuNet",
            "variant": "face_detection_yunet_2023mar",
            "framework": "OpenCV DNN (FaceDetectorYN)",
            "model_path": str(self.model_path),
            "device": self.device,
            "default_confidence_threshold": self.conf_threshold,
            "nms_threshold": self.nms_threshold,
            "license": "MIT",
            "capabilities": ["face_detection", "5_point_landmarks"],
        }

    def is_available(self) -> bool:
        """Check if OpenCV FaceDetectorYN is active."""
        return self._detector is not None
