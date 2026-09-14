# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.anpr.plate_detector
# Description: Plate detector adapter using ONNX DBNet text detector & geometric filters.
# License: Apache-2.0
# ==============================================================================

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

from app.core.logging import model_logger
from app.services.anpr.preprocessing import validate_crop


@dataclass
class PlateCandidate:
    """Detected license plate candidate region."""
    local_bbox: List[int]   # [x1, y1, x2, y2] relative to vehicle crop
    global_bbox: List[int]  # [x1, y1, x2, y2] relative to full camera frame
    crop: np.ndarray        # Cropped BGR plate image
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "local_bbox": self.local_bbox,
            "global_bbox": self.global_bbox,
            "confidence": round(float(self.confidence), 4),
        }


class PlateDetector(ABC):
    """Abstract base class for license plate detectors."""

    @abstractmethod
    def detect_plates(
        self,
        vehicle_crop: np.ndarray,
        vehicle_bbox: Optional[List[int]] = None
    ) -> List[PlateCandidate]:
        """Locate plate candidate regions within a vehicle crop."""
        pass


class RapidPlateDetector(PlateDetector):
    """
    PP-OCRv4 DBNet text/plate detector implementation running on ONNX Runtime.
    Isolates license plate quadrilaterals and filters candidates by aspect ratio & geometry.
    """
    def __init__(self, conf_threshold: float = 0.40):
        self.conf_threshold = conf_threshold
        self._engine: Optional[RapidOCR] = None
        self._load_model()

    def _load_model(self) -> None:
        try:
            self._engine = RapidOCR()
            model_logger.info("RapidPlateDetector initialized successfully with PP-OCRv4 DBNet ONNX engine.")
        except Exception as exc:
            model_logger.error(f"Failed to initialize RapidPlateDetector: {exc}")
            self._engine = None

    def get_model_info(self) -> Dict[str, Any]:
        """Return plate detector metadata."""
        return {
            "engine": "RapidOCR Text/Plate Detector",
            "model_name": "ch_PP-OCRv4_det_infer.onnx",
            "framework": "ONNX Runtime",
            "confidence_threshold": self.conf_threshold,
            "license": "Apache-2.0",
        }

    def detect_plates(
        self,
        vehicle_crop: np.ndarray,
        vehicle_bbox: Optional[List[int]] = None
    ) -> List[PlateCandidate]:
        """
        Detect license plate candidates within the vehicle crop.
        """
        if not validate_crop(vehicle_crop, min_w=30, min_h=30) or self._engine is None:
            return []

        vh, vw = vehicle_crop.shape[:2]
        vx1, vy1 = (vehicle_bbox[0], vehicle_bbox[1]) if vehicle_bbox else (0, 0)

        candidates: List[PlateCandidate] = []

        try:
            # Run RapidOCR detection on the vehicle crop
            results, elapse = self._engine(vehicle_crop)
            if not results:
                # Fallback to direct vehicle crop lower-half region if aspect ratio fits
                return candidates

            for item in results:
                # item: [polygon_box, text, confidence]
                poly = np.array(item[0], dtype=np.int32)
                conf = float(item[2])

                if conf < self.conf_threshold:
                    continue

                # Compute bounding rect for the polygon
                px1 = max(0, int(np.min(poly[:, 0])))
                py1 = max(0, int(np.min(poly[:, 1])))
                px2 = min(vw, int(np.max(poly[:, 0])))
                py2 = min(vh, int(np.max(poly[:, 1])))

                pw = px2 - px1
                ph = py2 - py1

                if pw <= 15 or ph <= 8:
                    continue

                aspect_ratio = float(pw) / float(ph)
                
                # License plates are predominantly horizontal (aspect ratio 1.3 to 7.0)
                if 1.3 <= aspect_ratio <= 7.0:
                    # Add margin padding (5% on each side) for clean OCR
                    pad_x = int(pw * 0.05)
                    pad_y = int(ph * 0.08)

                    cx1 = max(0, px1 - pad_x)
                    cy1 = max(0, py1 - pad_y)
                    cx2 = min(vw, px2 + pad_x)
                    cy2 = min(vh, py2 + pad_y)

                    plate_crop = vehicle_crop[cy1:cy2, cx1:cx2]
                    if validate_crop(plate_crop, min_w=10, min_h=5):
                        gx1 = vx1 + cx1
                        gy1 = vy1 + cy1
                        gx2 = vx1 + cx2
                        gy2 = vy1 + cy2

                        candidates.append(
                            PlateCandidate(
                                local_bbox=[cx1, cy1, cx2, cy2],
                                global_bbox=[gx1, gy1, gx2, gy2],
                                crop=plate_crop,
                                confidence=conf,
                            )
                        )

            return candidates
        except Exception as exc:
            model_logger.error(f"Plate candidate detection exception: {exc}")
            return []
