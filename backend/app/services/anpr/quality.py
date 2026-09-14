# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.anpr.quality
# Description: Explainable quality gate for candidate license plate crops.
# License: Apache-2.0
# ==============================================================================

from dataclasses import dataclass
from typing import Tuple, Dict, Any
import numpy as np

from app.services.anpr.preprocessing import (
    validate_crop,
    calculate_sharpness,
    calculate_brightness_contrast,
)


class QualityLevel:
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNREADABLE = "UNREADABLE"


PlateQuality = QualityLevel


@dataclass
class QualityAssessment:
    """Quality gate assessment result."""
    level: str
    is_usable: bool
    sharpness: float
    brightness: float
    contrast: float
    aspect_ratio: float
    width: int
    height: int
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "is_usable": self.is_usable,
            "sharpness": round(self.sharpness, 2),
            "brightness": round(self.brightness, 2),
            "contrast": round(self.contrast, 2),
            "aspect_ratio": round(self.aspect_ratio, 2),
            "width": self.width,
            "height": self.height,
            "reason": self.reason,
        }


class PlateQualityGate:
    """
    Evaluates candidate plate crop usability prior to OCR.
    Filters out severely degraded, blurred, or geometry-corrupted crops.
    """
    def __init__(
        self,
        min_width: int = 30,
        min_height: int = 12,
        min_aspect_ratio: float = 1.3,
        max_aspect_ratio: float = 7.0,
        blur_threshold: float = 15.0,
        high_sharpness_threshold: float = 80.0,
        min_contrast: float = 12.0,
    ):
        self.min_width = min_width
        self.min_height = min_height
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio
        self.blur_threshold = blur_threshold
        self.high_sharpness_threshold = high_sharpness_threshold
        self.min_contrast = min_contrast

    def assess(self, plate_crop: np.ndarray) -> QualityAssessment:
        """
        Evaluate crop and assign a QualityLevel.
        """
        if not validate_crop(plate_crop, min_w=5, min_h=5):
            return QualityAssessment(
                level=QualityLevel.UNREADABLE,
                is_usable=False,
                sharpness=0.0,
                brightness=0.0,
                contrast=0.0,
                aspect_ratio=0.0,
                width=0,
                height=0,
                reason="Invalid or empty crop image."
            )

        h, w = plate_crop.shape[:2]
        aspect_ratio = float(w) / float(h) if h > 0 else 0.0
        sharpness = calculate_sharpness(plate_crop)
        brightness, contrast = calculate_brightness_contrast(plate_crop)

        # Dimension checks
        if w < self.min_width or h < self.min_height:
            return QualityAssessment(
                level=QualityLevel.UNREADABLE,
                is_usable=False,
                sharpness=sharpness,
                brightness=brightness,
                contrast=contrast,
                aspect_ratio=aspect_ratio,
                width=w,
                height=h,
                reason=f"Crop resolution too small ({w}x{h}px; minimum {self.min_width}x{self.min_height}px required)."
            )

        # Aspect ratio check
        if aspect_ratio < self.min_aspect_ratio or aspect_ratio > self.max_aspect_ratio:
            return QualityAssessment(
                level=QualityLevel.LOW,
                is_usable=False,
                sharpness=sharpness,
                brightness=brightness,
                contrast=contrast,
                aspect_ratio=aspect_ratio,
                width=w,
                height=h,
                reason=f"Atypical aspect ratio ({aspect_ratio:.2f}; expected {self.min_aspect_ratio}-{self.max_aspect_ratio})."
            )

        # Severe blur check
        if sharpness < self.blur_threshold:
            return QualityAssessment(
                level=QualityLevel.UNREADABLE,
                is_usable=False,
                sharpness=sharpness,
                brightness=brightness,
                contrast=contrast,
                aspect_ratio=aspect_ratio,
                width=w,
                height=h,
                reason=f"Motion blur or severe defocus (sharpness {sharpness:.1f} < threshold {self.blur_threshold})."
            )

        # Low contrast check
        if contrast < self.min_contrast:
            return QualityAssessment(
                level=QualityLevel.LOW,
                is_usable=True,
                sharpness=sharpness,
                brightness=brightness,
                contrast=contrast,
                aspect_ratio=aspect_ratio,
                width=w,
                height=h,
                reason=f"Low contrast ({contrast:.1f} < {self.min_contrast})."
            )

        # High quality criteria
        if sharpness >= self.high_sharpness_threshold and w >= 80 and h >= 25:
            return QualityAssessment(
                level=QualityLevel.HIGH,
                is_usable=True,
                sharpness=sharpness,
                brightness=brightness,
                contrast=contrast,
                aspect_ratio=aspect_ratio,
                width=w,
                height=h,
                reason="High resolution, sharp edge definition, and optimal contrast."
            )

        # Medium quality
        return QualityAssessment(
            level=QualityLevel.MEDIUM,
            is_usable=True,
            sharpness=sharpness,
            brightness=brightness,
            contrast=contrast,
            aspect_ratio=aspect_ratio,
            width=w,
            height=h,
            reason="Adequate resolution and edge clarity for OCR recognition."
        )
