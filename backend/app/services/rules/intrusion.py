# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.rules.intrusion
# Description: Rule 1 — Restricted-Zone Intrusion Detection.
# License: Apache-2.0
# ==============================================================================

from typing import List
from app.services.tracking.tracker import Track
from app.services.zone.models import ZoneDefinition, IntrusionEventCandidate, ZoneType
from app.services.rules.base import BaseActivityRule
from app.services.rules.models import SuspiciousActivityCandidate, ActivityType, ActivitySeverity


class IntrusionRule(BaseActivityRule):
    """
    Rule 1 — Restricted-Zone Intrusion:
    Triggered when a tracked object transitions OUTSIDE -> INSIDE a configured RESTRICTED zone.
    Reuses Phase 6 ZoneEngine candidates directly without redundant point-in-polygon tests.
    """

    def __init__(self, camera_id: int):
        self.camera_id = camera_id

    def evaluate(
        self,
        tracks: List[Track],
        zones: List[ZoneDefinition],
        zone_candidates: List[IntrusionEventCandidate],
        frame_time: float,
        timestamp_iso: str,
        frame_idx: int = 0,
    ) -> List[SuspiciousActivityCandidate]:
        candidates: List[SuspiciousActivityCandidate] = []

        if not zone_candidates:
            return candidates

        for zc in zone_candidates:
            # We classify entries into RESTRICTED zones as HIGH-severity suspicious intrusions
            zone_type_str = (zc.zone_type or "").upper()
            is_restricted = zone_type_str == ZoneType.RESTRICTED.value or zone_type_str == "RESTRICTED"

            severity = ActivitySeverity.HIGH.value if is_restricted else ActivitySeverity.INFO.value
            object_label = zc.object_type.capitalize() if zc.object_type else "Object"
            zone_label = zc.zone_name or f"Zone #{zc.zone_id}"

            if is_restricted:
                reason = f"{object_label} entered Restricted Zone '{zone_label}'."
            else:
                reason = f"{object_label} entered Monitoring Zone '{zone_label}'."

            candidate = SuspiciousActivityCandidate(
                event_type=ActivityType.ZONE_INTRUSION.value,
                camera_id=self.camera_id,
                track_id=zc.track_id,
                zone_id=zc.zone_id,
                zone_name=zc.zone_name,
                zone_type=zc.zone_type,
                object_type=zc.object_type,
                timestamp=timestamp_iso or zc.timestamp,
                severity=severity,
                reason=reason,
                confidence=zc.confidence,
                duration_sec=0.0,
                anchor_point=zc.anchor_point,
            )
            candidates.append(candidate)

        return candidates

    def reset(self) -> None:
        """Intrusion rule is stateless and delegates transitions to ZoneEngine."""
        pass
