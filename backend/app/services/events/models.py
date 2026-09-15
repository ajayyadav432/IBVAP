# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.events.models
# Description: Data structures, candidate schemas, and enumerations for Centralized Event Engine.
# License: Apache-2.0
# ==============================================================================

from dataclasses import dataclass, field
from enum import Enum
import datetime
from typing import Optional, Dict, Any, Tuple


class EventSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EventStatus(str, Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class SystemEventType(str, Enum):
    PERSON_DETECTED = "PERSON_DETECTED"
    VEHICLE_DETECTED = "VEHICLE_DETECTED"
    FACE_DETECTED = "FACE_DETECTED"
    ANPR_DETECTED = "ANPR_DETECTED"
    ZONE_INTRUSION = "ZONE_INTRUSION"
    LOITERING = "LOITERING"
    NIGHT_MOVEMENT = "NIGHT_MOVEMENT"


# Default severity mappings for normalized event types
DEFAULT_SEVERITY_MAP: Dict[str, EventSeverity] = {
    SystemEventType.PERSON_DETECTED.value: EventSeverity.INFO,
    SystemEventType.VEHICLE_DETECTED.value: EventSeverity.INFO,
    SystemEventType.FACE_DETECTED.value: EventSeverity.INFO,
    SystemEventType.ANPR_DETECTED.value: EventSeverity.INFO,
    SystemEventType.NIGHT_MOVEMENT.value: EventSeverity.WARNING,
    SystemEventType.LOITERING.value: EventSeverity.HIGH,
    SystemEventType.ZONE_INTRUSION.value: EventSeverity.CRITICAL,
}


@dataclass
class EventCandidate:
    """
    Normalized candidate submitted from upstream analytics/rules into the Central Event Engine.
    """
    event_type: str
    camera_id: int
    reason: str
    timestamp: Optional[str] = None
    severity: Optional[str] = None
    object_type: Optional[str] = None
    track_id: Optional[int] = None
    zone_id: Optional[int] = None
    confidence: Optional[float] = None
    evidence_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> Tuple[bool, Optional[str]]:
        """Validate candidate attributes."""
        if not self.event_type or not isinstance(self.event_type, str):
            return False, "Missing or invalid event_type."
        if self.camera_id is None or not isinstance(self.camera_id, int):
            return False, "Missing or invalid camera_id."
        if not self.reason or not isinstance(self.reason, str):
            return False, "Missing or invalid event reason."
        return True, None

    def get_logical_key(self) -> Tuple:
        """
        Generate deterministic deduplication key:
        (camera_id, event_type, track_id, zone_id)
        """
        return (
            self.camera_id,
            self.event_type,
            self.track_id if self.track_id is not None else "no_track",
            self.zone_id if self.zone_id is not None else "no_zone",
        )

    def resolve_severity(self) -> str:
        """Resolve severity to a valid EventSeverity string."""
        if self.severity:
            sev_upper = str(self.severity).upper()
            if sev_upper in {s.value for s in EventSeverity}:
                return sev_upper
        
        # Fallback to default mapping
        ev_type = str(self.event_type).upper()
        if ev_type in DEFAULT_SEVERITY_MAP:
            return DEFAULT_SEVERITY_MAP[ev_type].value
        return EventSeverity.INFO.value
