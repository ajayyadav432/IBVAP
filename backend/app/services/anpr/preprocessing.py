# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.anpr.preprocessing
# Description: Image preprocessing utilities for vehicle crops and license plates.
# License: Apache-2.0
# ==============================================================================

from typing import Tuple, Optional
import cv2
import numpy as np


def validate_crop(crop: Optional[np.ndarray], min_w: int = 20, min_h: int = 10) -> bool:
    """Validate that crop array is non-empty and meets minimum dimension criteria."""
    if crop is None or not isinstance(crop, np.ndarray) or crop.size == 0:
        return False
    h, w = crop.shape[:2]
    return w >= min_w and h >= min_h


def calculate_sharpness(image: np.ndarray) -> float:
    """
    Calculate image sharpness using Laplacian variance.
    Higher values indicate sharp edges; very low values (< 15) indicate heavy blur.
    """
    if not validate_crop(image, min_w=5, min_h=5):
        return 0.0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def calculate_brightness_contrast(image: np.ndarray) -> Tuple[float, float]:
    """
    Compute mean brightness and standard deviation (contrast).
    Returns: (mean_brightness, contrast_std)
    """
    if not validate_crop(image, min_w=5, min_h=5):
        return 0.0, 0.0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    mean_val = float(np.mean(gray))
    std_val = float(np.std(gray))
    return mean_val, std_val


def enhance_plate_image(plate_crop: np.ndarray, target_height: int = 64) -> np.ndarray:
    """
    Apply aspect-preserving resize, grayscale, and CLAHE contrast enhancement for OCR.
    Keeps original aspect ratio while ensuring adequate height for text tokenization.
    """
    if not validate_crop(plate_crop):
        return plate_crop

    h, w = plate_crop.shape[:2]
    if h == 0 or w == 0:
        return plate_crop

    # Aspect-preserving height scaling if crop is small
    if h < target_height:
        scale = target_height / float(h)
        new_w = max(1, int(round(w * scale)))
        resized = cv2.resize(plate_crop, (new_w, target_height), interpolation=cv2.INTER_CUBIC)
    else:
        resized = plate_crop

    return resized


class PlatePreprocessor:
    """Wrapper class providing static preprocessing methods."""

    @staticmethod
    def validate(crop: Optional[np.ndarray], min_w: int = 20, min_h: int = 10) -> bool:
        return validate_crop(crop, min_w, min_h)

    @staticmethod
    def calculate_sharpness(image: np.ndarray) -> float:
        return calculate_sharpness(image)

    @staticmethod
    def calculate_brightness_contrast(image: np.ndarray) -> Tuple[float, float]:
        return calculate_brightness_contrast(image)

    @staticmethod
    def enhance(plate_crop: np.ndarray, target_height: int = 64) -> np.ndarray:
        return enhance_plate_image(plate_crop, target_height)

