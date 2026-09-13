# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.zone.engine
# Description: Virtual Fence & Zone Engine with state transitions, debounce, and intrusion candidates.
# License: Apache-2.0
# ==============================================================================

import datetime
import time
from typing import List, Dict, Tuple, Optional, Any

from app.core.logging import inference_logger
from app.services.tracking.tracker import Track
from app.services.zone.geometry import (
    get_object_anchor,
    normalize_point,
    point_in_polygon,
    validate_polygon,
)
from app.services.zone.models import (
    ZoneDefinition,
    ZoneType,
    ZoneState,
    IntrusionEventCandidate,
    TrackZoneState,
)


class ZoneEngine:
    """
    Virtual Fence / Zone Rule Engine for a specific camera view.
    Evaluates tracked objects against configured polygon zones using bottom-center anchor points.
    Implements per-track state tracking, boundary jitter debouncing, and candidate generation.
    """
    def __init__(self, camera_id: int = 1, debounce_frames: int = 2):
        self.camera_id = camera_id
        self.debounce_frames = max(1, debounce_frames)
        
        # Zone ID -> ZoneDefinition
        self._zones: Dict[int, ZoneDefinition] = {}
        
        # (zone_id, track_id) -> TrackZoneState
        self._track_states: Dict[Tuple[int, int], TrackZoneState] = {}
        
        # Current active intrusions: List of active track_ids per zone
        self._active_intrusions: Dict[int, List[int]] = {}

    def set_zones(self, zones: List[ZoneDefinition]) -> None:
        """Replace all active zones with a new set of zone definitions."""
        valid_zones = {}
        for z in zones:
            is_valid, err = validate_polygon(z.polygon)
            if is_valid:
                valid_zones[z.id] = z
            else:
                inference_logger.warning(f"Zone #{z.id} '{z.name}' rejected: {err}")
        self._zones = valid_zones
        
        # Prune track states for deleted zones
        current_zone_ids = set(self._zones.keys())
        self._track_states = {
            k: v for k, v in self._track_states.items()
            if k[0] in current_zone_ids
        }

    def add_zone(self, zone: ZoneDefinition) -> bool:
        """Add or update a single zone definition."""
        is_valid, err = validate_polygon(zone.polygon)
        if not is_valid:
            inference_logger.error(f"Cannot add invalid zone '{zone.name}': {err}")
            return False
        self._zones[zone.id] = zone
        return True

    def remove_zone(self, zone_id: int) -> None:
        """Remove a zone by ID."""
        if zone_id in self._zones:
            del self._zones[zone_id]
            self._track_states = {
                k: v for k, v in self._track_states.items()
                if k[0] != zone_id
            }

    def get_zones(self) -> List[ZoneDefinition]:
        """Return all configured zones."""
        return list(self._zones.values())

    def process_tracks(
        self,
        tracks: List[Track],
        frame_width: int,
        frame_height: int,
        frame_idx: int = 0
    ) -> List[IntrusionEventCandidate]:
        """
        Evaluate active tracks against all enabled zones for this camera.
        
        Returns:
            List of newly emitted IntrusionEventCandidate items for this frame.
        """
        if not self._zones or not tracks or frame_width <= 0 or frame_height <= 0:
            return []

        candidates: List[IntrusionEventCandidate] = []
        active_track_ids = {t.track_id for t in tracks}
        now_iso = datetime.datetime.utcnow().isoformat()

        # Reset active intrusions map
        current_intrusions: Dict[int, List[int]] = {zid: [] for zid in self._zones.keys()}

        for zone_id, zone in self._zones.items():
            if not zone.enabled:
                continue

            for track in tracks:
                tid = track.track_id
                key = (zone_id, tid)

                if key not in self._track_states:
                    self._track_states[key] = TrackZoneState(
                        zone_id=zone_id,
                        track_id=tid,
                        current_state=ZoneState.OUTSIDE
                    )

                state = self._track_states[key]
                state.last_evaluated_frame = frame_idx

                # Step 1: Calculate bottom-center anchor point
                ax, ay = get_object_anchor(track.bbox, track.object_type)
                norm_ax, norm_ay = normalize_point(ax, ay, frame_width, frame_height)

                # Step 2: Deterministic Point-in-Polygon test
                is_inside, signed_dist = point_in_polygon((norm_ax, norm_ay), zone.polygon)

                # Step 3: State Machine with Jitter Debounce
                if is_inside:
                    state.consecutive_inside_frames += 1
                    state.consecutive_outside_frames = 0

                    if state.current_state == ZoneState.OUTSIDE:
                        if state.consecutive_inside_frames >= self.debounce_frames:
                            # State Transition: OUTSIDE -> ENTERED -> INSIDE
                            state.current_state = ZoneState.INSIDE
                            state.entry_timestamp = now_iso
                            track.current_zone = zone.name

                            # Generate normalized intrusion event candidate
                            reason = f"{track.object_type.capitalize()} #{tid} entered {zone.zone_type.lower()} zone '{zone.name}'"
                            candidate = IntrusionEventCandidate(
                                event_type="ZONE_INTRUSION",
                                camera_id=self.camera_id,
                                zone_id=zone.id,
                                zone_name=zone.name,
                                zone_type=zone.zone_type,
                                track_id=tid,
                                object_type=track.object_type,
                                anchor_point=[round(norm_ax, 4), round(norm_ay, 4)],
                                reason=reason,
                                timestamp=now_iso,
                                confidence=track.confidence,
                            )
                            candidates.append(candidate)
                            current_intrusions[zone_id].append(tid)
                    elif state.current_state == ZoneState.INSIDE:
                        # Remains inside - update track current_zone, but do not flood candidate events
                        track.current_zone = zone.name
                        current_intrusions[zone_id].append(tid)

                else:
                    state.consecutive_outside_frames += 1
                    state.consecutive_inside_frames = 0

                    if state.current_state == ZoneState.INSIDE:
                        if state.consecutive_outside_frames >= self.debounce_frames:
                            # State Transition: INSIDE -> EXITED -> OUTSIDE
                            state.current_state = ZoneState.OUTSIDE
                            if track.current_zone == zone.name:
                                track.current_zone = None

        # Clean up stale tracks from internal state machine
        stale_keys = [
            k for k in self._track_states.keys()
            if k[1] not in active_track_ids
        ]
        for k in stale_keys:
            del self._track_states[k]

        self._active_intrusions = current_intrusions
        return candidates

    def get_active_intrusions(self) -> Dict[int, List[int]]:
        """Return dict of zone_id -> list of track_ids currently inside the zone."""
        return self._active_intrusions

    def is_track_in_zone(self, zone_id: int, track_id: int) -> bool:
        """Check if a specific track is currently in INSIDE state for a zone."""
        state = self._track_states.get((zone_id, track_id))
        return state is not None and state.current_state == ZoneState.INSIDE
