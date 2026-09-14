# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.anpr
# Description: ANPR Package Interface
# License: Apache-2.0
# ==============================================================================

from app.services.anpr.plate_detector import PlateDetector, RapidPlateDetector, PlateCandidate
from app.services.anpr.ocr_engine import OCREngine, RapidOCREngine, OCRResult
from app.services.anpr.quality import PlateQualityGate, QualityAssessment, QualityLevel
from app.services.anpr.normalizer import normalize_plate_text
from app.services.anpr.engine import ANPREngine, ANPRResult

__all__ = [
    "PlateDetector",
    "RapidPlateDetector",
    "PlateCandidate",
    "OCREngine",
    "RapidOCREngine",
    "OCRResult",
    "PlateQualityGate",
    "QualityAssessment",
    "QualityLevel",
    "normalize_plate_text",
    "ANPREngine",
    "ANPRResult",
]
