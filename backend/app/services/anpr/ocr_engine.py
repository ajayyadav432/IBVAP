# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.anpr.ocr_engine
# Description: OCR engine adapter wrapping RapidOCR + ONNX Runtime.
# License: Apache-2.0
# ==============================================================================

from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
from typing import Optional, Dict, Any, Tuple
import numpy as np
from rapidocr_onnxruntime import RapidOCR

from app.core.logging import model_logger, inference_logger
from app.services.anpr.preprocessing import validate_crop, enhance_plate_image


@dataclass
class OCRResult:
    """Normalized OCR engine character recognition output."""
    raw_text: str
    confidence: float
    latency_ms: float
    raw_results: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "confidence": round(float(self.confidence), 4),
            "latency_ms": round(float(self.latency_ms), 1),
        }


class OCREngine(ABC):
    """Abstract interface for Optical Character Recognition engines."""

    @abstractmethod
    def recognize(self, plate_crop: np.ndarray) -> OCRResult:
        """Extract alphanumeric text from cropped license plate image."""
        pass


class RapidOCREngine(OCREngine):
    """
    RapidOCR implementation utilizing PP-OCRv4 ONNX models.
    Operates locally with pure ONNX Runtime on CPU or CUDA.
    """
    def __init__(self):
        self._engine: Optional[RapidOCR] = None
        self._load_model()

    def _load_model(self) -> None:
        try:
            start_t = time.time()
            self._engine = RapidOCR()
            load_ms = (time.time() - start_t) * 1000.0
            model_logger.info(f"RapidOCREngine initialized successfully in {load_ms:.1f}ms using ONNX Runtime.")
        except Exception as exc:
            model_logger.error(f"Failed to initialize RapidOCREngine: {exc}")
            self._engine = None

    def get_model_info(self) -> Dict[str, Any]:
        """Return OCR model metadata."""
        return {
            "engine": "RapidOCR Text Recognizer",
            "model_name": "ch_PP-OCRv4_rec_infer.onnx",
            "framework": "ONNX Runtime",
            "license": "Apache-2.0",
        }

    def recognize(self, plate_crop: np.ndarray) -> OCRResult:
        """
        Run OCR on preprocessed license plate crop.
        """
        if not validate_crop(plate_crop, min_w=10, min_h=5) or self._engine is None:
            return OCRResult(raw_text="", confidence=0.0, latency_ms=0.0, raw_results=None)

        start_t = time.time()
        try:
            # Apply slight enhancement for small crops
            enhanced = enhance_plate_image(plate_crop, target_height=48)
            results, elapse = self._engine(enhanced)
            latency_ms = (time.time() - start_t) * 1000.0

            if not results:
                return OCRResult(raw_text="", confidence=0.0, latency_ms=latency_ms, raw_results=None)

            # Combine recognized text lines (if multiple lines exist)
            texts = []
            confs = []
            for item in results:
                txt = item[1].strip()
                conf = float(item[2])
                if txt:
                    texts.append(txt)
                    confs.append(conf)

            full_text = " ".join(texts)
            avg_conf = float(np.mean(confs)) if confs else 0.0

            return OCRResult(
                raw_text=full_text,
                confidence=avg_conf,
                latency_ms=latency_ms,
                raw_results=results,
            )
        except Exception as exc:
            inference_logger.error(f"RapidOCR recognition error: {exc}")
            latency_ms = (time.time() - start_t) * 1000.0
            return OCRResult(raw_text="", confidence=0.0, latency_ms=latency_ms, raw_results=None)
