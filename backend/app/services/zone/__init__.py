# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.zone
# Description: Virtual Fence / Zone Engine exports.
# License: Apache-2.0
# ==============================================================================

from app.services.zone.geometry import (
    get_object_anchor,
    normalize_point,
    denormalize_point,
    denormalize_polygon,
    validate_polygon,
    point_in_polygon,
)
from app.services.zone.models import (
    ZoneType,
    ZoneState,
    ZoneDefinition,
    IntrusionEventCandidate,
    TrackZoneState,
)
from app.services.zone.engine import ZoneEngine

__all__ = [
    "get_object_anchor",
    "normalize_point",
    "denormalize_point",
    "denormalize_polygon",
    "validate_polygon",
    "point_in_polygon",
    "ZoneType",
    "ZoneState",
    "ZoneDefinition",
    "IntrusionEventCandidate",
    "TrackZoneState",
    "ZoneEngine",
]
