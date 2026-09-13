# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.rules.loitering
# Description: Rule 2 — Deterministic Loitering Detection with single-trigger gate.
# License: Apache-2.0
# ==============================================================================

from typing import List, Dict, Tuple, Optional
from app.services.tracking.tracker import Track
from app.services.zone.models import ZoneDefinition, IntrusionEventCandidate, ZoneType
from app.services.rules.base import BaseActivityRule
from app.services.rules.models import (
    SuspiciousActivityCandidate,
    LoiteringTrackState,
    ActivityType,
    ActivitySeverity,
)


class LoiteringRule(BaseActivityRule):
    """
    Rule 2 — Loitering Detection:
    Tracks dwell time of objects inside configured RESTRICTED or MONITORING zones.
    Emits exactly ONE event candidate when the configured duration threshold is reached.
    Resets cleanly on zone exit or track loss.
    """

    def __init__(self, camera_id: int, threshold_sec: float = 30.0):
        self.camera_id = camera_id
        self.threshold_sec = max(1.0, float(threshold_sec))
        
        # (zone_id, track_id) -> LoiteringTrackState
        self._states: Dict[Tuple[int, int], LoiteringTrackState] = {}

    def set_threshold(self, threshold_sec: float) -> None:
        """Update loitering threshold with validation."""
        self.threshold_sec = max(1.0, min(3600.0, float(threshold_sec)))

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
        active_track_ids = {t.track_id for t in tracks}
        zone_map = {z.id: z for z in zones if z.enabled}
        zone_name_to_id = {z.name: z.id for z in zones if z.enabled}

        # Step 1: Track objects currently occupying zones
        # An object is inside a zone if track.current_zone matches a configured zone name
        current_occupancies: set = set()

        for track in tracks:
            tid = track.track_id
            if not track.current_zone or track.current_zone not in zone_name_to_id:
                continue

            zid = zone_name_to_id[track.current_zone]
            zone = zone_map.get(zid)
            if not zone:
                continue

            current_occupancies.add((zid, tid))
            key = (zid, tid)

            # Compute normalized anchor point
            ax = (float(track.bbox[0]) + float(track.bbox[2])) / 2.0
            ay = float(track.bbox[3])

            if key not in self._states:
                # First observation of track inside this zone: start timer
                self._states[key] = LoiteringTrackState(
                    camera_id=self.camera_id,
                    zone_id=zid,
                    track_id=tid,
                    zone_name=zone.name,
                    zone_type=zone.zone_type,
                    object_type=track.object_type,
                    entered_at=frame_time,
                    last_seen=frame_time,
                    current_duration=0.0,
                    triggered=False,
                    confidence=track.confidence,
                    anchor_point=[ax, ay],
                )
            else:
                # Track remains inside zone: update dwell time
                state = self._states[key]
                state.last_seen = frame_time
                state.current_duration = max(0.0, frame_time - state.entered_at)
                state.confidence = track.confidence
                state.anchor_point = [ax, ay]

                # Check threshold gate
                if state.current_duration >= self.threshold_sec and not state.triggered:
                    state.triggered = True  # Guarantee single trigger per stay

                    is_restricted = (zone.zone_type or "").upper() == "RESTRICTED"
                    severity = ActivitySeverity.HIGH.value if is_restricted else ActivitySeverity.WARNING.value
                    
                    obj_label = track.object_type.capitalize() if track.object_type else "Person"
                    duration_int = int(round(state.current_duration))
                    zone_type_label = "Restricted" if is_restricted else "Monitoring"
                    reason = f"{obj_label} remained in {zone_type_label} Zone '{zone.name}' for {duration_int} seconds."

                    candidate = SuspiciousActivityCandidate(
                        event_type=ActivityType.LOITERING.value,
                        camera_id=self.camera_id,
                        track_id=tid,
                        zone_id=zid,
                        zone_name=zone.name,
                        zone_type=zone.zone_type,
                        object_type=track.object_type,
                        timestamp=timestamp_iso,
                        severity=severity,
                        reason=reason,
                        confidence=track.confidence,
                        duration_sec=state.current_duration,
                        anchor_point=[ax, ay],
                    )
                    candidates.append(candidate)

        # Step 2: Clean up tracks that have EXITED zones or were LOST
        stale_keys = [
            k for k in self._states.keys()
            if k not in current_occupancies or k[1] not in active_track_ids
        ]
        for k in stale_keys:
            del self._states[k]

        return candidates

    def get_active_states(self) -> Dict[Tuple[int, int], LoiteringTrackState]:
        """Return snapshot of active loitering timers."""
        return self._states

    def reset(self) -> None:
        """Reset all loitering timers."""
        self._states.clear()
