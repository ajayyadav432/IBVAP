# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.zone.models
# Description: Data models, enums, and event candidate schemas for Virtual Fence / Zone Engine.
# License: Apache-2.0
# ==============================================================================

from dataclasses import dataclass, field
from enum import Enum
import json
from typing import List, Dict, Any, Optional


class ZoneType(str, Enum):
    RESTRICTED = "RESTRICTED"
    MONITORING = "MONITORING"


class ZoneState(str, Enum):
    OUTSIDE = "OUTSIDE"
    ENTERED = "ENTERED"
    INSIDE = "INSIDE"
    EXITED = "EXITED"


@dataclass
class ZoneDefinition:
    """Normalized in-memory representation of a camera polygon zone."""
    id: int
    camera_id: int
    name: str
    zone_type: str
    polygon: List[List[float]]  # List of normalized [x, y] coordinates (0.0 to 1.0)
    enabled: bool = True

    @classmethod
    def from_orm(cls, zone_obj: Any) -> "ZoneDefinition":
        """Construct from SQLAlchemy Zone ORM entity."""
        try:
            poly = json.loads(zone_obj.polygon_json) if isinstance(zone_obj.polygon_json, str) else zone_obj.polygon_json
        except Exception:
            poly = []
        return cls(
            id=zone_obj.id,
            camera_id=zone_obj.camera_id,
            name=zone_obj.name,
            zone_type=zone_obj.zone_type,
            polygon=poly,
            enabled=zone_obj.enabled,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "name": self.name,
            "zone_type": self.zone_type,
            "polygon": self.polygon,
            "enabled": self.enabled,
        }


@dataclass
class IntrusionEventCandidate:
    """Normalized intrusion event candidate generated upon zone boundary crossing."""
    event_type: str  # Always "ZONE_INTRUSION"
    camera_id: int
    zone_id: int
    zone_name: str
    zone_type: str
    track_id: int
    object_type: str
    anchor_point: List[float]  # [norm_x, norm_y] or [px_x, px_y]
    reason: str
    timestamp: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "camera_id": self.camera_id,
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "zone_type": self.zone_type,
            "track_id": self.track_id,
            "object_type": self.object_type,
            "anchor_point": self.anchor_point,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "confidence": round(float(self.confidence), 4),
        }


@dataclass
class TrackZoneState:
    """Internal state tracking per (zone_id, track_id) pair for jitter suppression."""
    zone_id: int
    track_id: int
    current_state: ZoneState = ZoneState.OUTSIDE
    consecutive_inside_frames: int = 0
    consecutive_outside_frames: int = 0
    entry_timestamp: Optional[str] = None
    last_evaluated_frame: int = 0
