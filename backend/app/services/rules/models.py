# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.rules.models
# Description: Data models and enums for Suspicious Activity Detection.
# License: Apache-2.0
# ==============================================================================

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class ActivityType(str, Enum):
    ZONE_INTRUSION = "ZONE_INTRUSION"
    LOITERING = "LOITERING"
    NIGHT_MOVEMENT = "NIGHT_MOVEMENT"


class ActivitySeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class SuspiciousActivityCandidate:
    """
    Normalized suspicious activity event candidate emitted by the rule engine.
    """
    event_type: str                   # "ZONE_INTRUSION" or "LOITERING"
    camera_id: int                    # Associated camera integer ID
    track_id: int                     # Track ID of the object triggering the rule
    zone_id: Optional[int]            # Zone ID where activity occurred
    zone_name: Optional[str]          # Human-readable zone name
    zone_type: Optional[str]          # "RESTRICTED" or "MONITORING"
    object_type: str                  # "person", "car", etc.
    timestamp: str                    # ISO 8601 UTC timestamp
    severity: str                     # ActivitySeverity ("HIGH", "WARNING", etc.)
    reason: str                       # Human-readable explainable reason
    confidence: Optional[float] = None  # Inherited from object detection/track (not fabricated)
    duration_sec: Optional[float] = None  # Elapsed dwell time for loitering events
    anchor_point: Optional[List[float]] = None  # [norm_x, norm_y] ground contact point

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "zone_type": self.zone_type,
            "object_type": self.object_type,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "confidence": round(self.confidence, 4) if self.confidence is not None else None,
            "duration_sec": round(self.duration_sec, 2) if self.duration_sec is not None else None,
            "anchor_point": self.anchor_point,
            "reason": self.reason,
        }


@dataclass
class LoiteringTrackState:
    """
    Internal state tracking for an object within a specific zone.
    Maintained per (camera_id, zone_id, track_id).
    """
    camera_id: int
    zone_id: int
    track_id: int
    zone_name: str
    zone_type: str
    object_type: str
    entered_at: float                 # Epoch timestamp (seconds) when entry was confirmed
    last_seen: float                  # Epoch timestamp (seconds) of most recent frame inside
    current_duration: float = 0.0     # Elapsed seconds inside the zone
    triggered: bool = False           # Flag to ensure single emission (no per-frame candidate flood)
    confidence: float = 0.0
    anchor_point: Optional[List[float]] = None
