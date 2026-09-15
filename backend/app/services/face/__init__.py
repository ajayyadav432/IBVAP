# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.face
# Description: Face detection package export.
# License: Apache-2.0
# ==============================================================================

from app.services.face.detector import (
    Face,
    FaceDetector,
    YuNetFaceDetector,
)

__all__ = [
    "Face",
    "FaceDetector",
    "YuNetFaceDetector",
]
