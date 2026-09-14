# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.anpr.normalizer
# Description: Plate text normalization, sanitization, and Indian plate format validation.
# License: Apache-2.0
# ==============================================================================

import re
from typing import Tuple

# Recognized 2-Letter Indian State / Union Territory Codes
INDIAN_STATE_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN", "GA", "GJ",
    "HP", "HR", "JH", "JK", "KA", "KL", "LA", "LD", "MH", "ML", "MN", "MP",
    "MZ", "NL", "OD", "PB", "PY", "RJ", "SK", "TN", "TR", "TS", "UK", "UP",
    "WB", "BH"  # BH = Bharat Series
}


def normalize_plate_text(raw_text: str, ocr_confidence: float) -> Tuple[str, str, float]:
    """
    Sanitize raw OCR output and perform lightweight plausibility validation.
    
    Returns:
        (normalized_plate_text, quality_level, final_confidence)
    
    Rules:
    - Uppercase conversion
    - Strip whitespace, hyphens, dots, underscores, and special characters
    - Only retain standard ASCII alphanumeric characters (A-Z, 0-9)
    - Check Indian State Code prefix plausibility without fabricating missing characters
    - Quality scoring: HIGH (>=0.75 + valid format), MEDIUM (>=0.50), LOW (<0.50), UNREADABLE (empty/too short/failed)
    """
    if not raw_text or not isinstance(raw_text, str):
        return "UNREADABLE", "UNREADABLE", 0.0

    # 1. Strip special symbols and noise
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw_text).upper()

    if len(cleaned) < 4:
        return "UNREADABLE", "UNREADABLE", 0.0

    # 2. Plausibility checks
    state_prefix = cleaned[:2]
    has_valid_state = state_prefix in INDIAN_STATE_CODES
    
    # Standard Indian plate length is usually 8-10 characters (e.g. GJ05RX3056, RJ14AB1234)
    is_standard_length = 6 <= len(cleaned) <= 12

    # 3. Determine Quality Rating
    if ocr_confidence >= 0.75 and (has_valid_state or is_standard_length):
        quality = "HIGH"
    elif ocr_confidence >= 0.50:
        quality = "MEDIUM"
    elif ocr_confidence > 0.0:
        quality = "LOW"
    else:
        quality = "UNREADABLE"

    return cleaned, quality, round(float(ocr_confidence), 4)


class NormalizedPlate:
    def __init__(self, sanitized_text: str, quality: str, confidence: float, state_code: str = None, is_indian_plausible: bool = False):
        self.sanitized_text = sanitized_text
        self.quality = quality
        self.confidence = confidence
        self.state_code = state_code
        self.is_indian_plausible = is_indian_plausible


class PlateNormalizer:
    """Wrapper class for Indian vehicle plate normalization and validation."""

    def __init__(self):
        self.state_codes = INDIAN_STATE_CODES

    def normalize(self, raw_text: str, ocr_confidence: float = 0.90) -> NormalizedPlate:
        cleaned, quality, conf = normalize_plate_text(raw_text, ocr_confidence)
        state_prefix = cleaned[:2] if len(cleaned) >= 2 else None
        is_plausible = state_prefix in self.state_codes if state_prefix else False
        return NormalizedPlate(
            sanitized_text=cleaned,
            quality=quality,
            confidence=conf,
            state_code=state_prefix if is_plausible else None,
            is_indian_plausible=is_plausible
        )

