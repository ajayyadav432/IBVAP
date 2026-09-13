# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.rules.engine
# Description: Orchestrator engine for Suspicious Activity Detection rules.
# License: Apache-2.0
# ==============================================================================

import time
import datetime
from typing import List, Dict, Any, Optional
from app.core.logging import inference_logger
from app.services.tracking.tracker import Track
from app.services.zone.models import ZoneDefinition, IntrusionEventCandidate
from app.services.rules.base import BaseActivityRule
from app.services.rules.models import SuspiciousActivityCandidate, LoiteringTrackState
from app.services.rules.intrusion import IntrusionRule
from app.services.rules.loitering import LoiteringRule
from app.services.rules.night import NightMovementRule


class SuspiciousActivityEngine:
    """
    High-level orchestrator for deterministic, explainable suspicious activity rules.
    Runs in the per-camera worker loop after ZoneEngine evaluation.
    """

    def __init__(
        self,
        camera_id: int,
        loitering_threshold_sec: float = 30.0,
        night_movement_enabled: bool = True,
        night_start_time: str = "22:00",
        night_end_time: str = "05:00",
        night_cooldown_sec: float = 60.0,
    ):
        self.camera_id = camera_id
        self.loitering_threshold_sec = max(1.0, float(loitering_threshold_sec))

        # Instantiate modular rules
        self.intrusion_rule = IntrusionRule(camera_id=self.camera_id)
        self.loitering_rule = LoiteringRule(camera_id=self.camera_id, threshold_sec=self.loitering_threshold_sec)
        self.night_rule = NightMovementRule(
            camera_id=self.camera_id,
            enabled=night_movement_enabled,
            start_time_str=night_start_time,
            end_time_str=night_end_time,
            cooldown_sec=night_cooldown_sec,
        )

        self.rules: List[BaseActivityRule] = [
            self.intrusion_rule,
            self.loitering_rule,
            self.night_rule,
        ]

    def set_loitering_threshold(self, threshold_sec: float) -> None:
        """Update loitering threshold across rules."""
        self.loitering_threshold_sec = max(1.0, float(threshold_sec))
        self.loitering_rule.set_threshold(self.loitering_threshold_sec)

    def set_night_movement_config(
        self,
        enabled: Optional[bool] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        cooldown_sec: Optional[float] = None,
    ) -> None:
        """Update night movement schedule and parameters."""
        self.night_rule.set_config(
            enabled=enabled,
            start_time=start_time,
            end_time=end_time,
            cooldown_sec=cooldown_sec,
        )

    def process(
        self,
        tracks: List[Track],
        zones: List[ZoneDefinition],
        zone_candidates: List[IntrusionEventCandidate],
        frame_time: Optional[float] = None,
        timestamp_iso: Optional[str] = None,
        frame_idx: int = 0,
        current_dt_time: Optional[datetime.time] = None,
    ) -> List[SuspiciousActivityCandidate]:
        """
        Evaluate all active rules on normalized tracks, zones, and candidates.
        
        Args:
            tracks: List of active Track objects from ByteTrack
            zones: List of ZoneDefinition objects for this camera
            zone_candidates: List of IntrusionEventCandidate from ZoneEngine
            frame_time: Virtual or real time (seconds) of the frame (defaults to time.time())
            timestamp_iso: ISO 8601 timestamp string (defaults to UTC now)
            frame_idx: Current frame index
            
        Returns:
            List of newly triggered SuspiciousActivityCandidate items
        """
        if frame_time is None:
            frame_time = time.time()
        if timestamp_iso is None:
            timestamp_iso = datetime.datetime.utcnow().isoformat()

        all_candidates: List[SuspiciousActivityCandidate] = []

        for rule in self.rules:
            try:
                if isinstance(rule, NightMovementRule) and current_dt_time is not None:
                    rule_candidates = rule.evaluate(
                        tracks=tracks,
                        zones=zones,
                        zone_candidates=zone_candidates,
                        frame_time=frame_time,
                        timestamp_iso=timestamp_iso,
                        frame_idx=frame_idx,
                        current_dt_time=current_dt_time,
                    )
                else:
                    rule_candidates = rule.evaluate(
                        tracks=tracks,
                        zones=zones,
                        zone_candidates=zone_candidates,
                        frame_time=frame_time,
                        timestamp_iso=timestamp_iso,
                        frame_idx=frame_idx,
                    )
                all_candidates.extend(rule_candidates)
            except Exception as exc:
                inference_logger.error(f"Error evaluating rule {rule.__class__.__name__} on Cam #{self.camera_id}: {exc}")

        return all_candidates

    def evaluate(
        self,
        tracks: List[Track],
        zones: Optional[List[ZoneDefinition]] = None,
        zone_candidates: Optional[List[IntrusionEventCandidate]] = None,
        frame_time: Optional[float] = None,
        timestamp_iso: Optional[str] = None,
        frame_idx: int = 0,
        current_dt_time: Optional[datetime.time] = None,
    ) -> List[SuspiciousActivityCandidate]:
        """Convenience alias for process()."""
        return self.process(
            tracks=tracks,
            zones=zones or [],
            zone_candidates=zone_candidates or [],
            frame_time=frame_time,
            timestamp_iso=timestamp_iso,
            frame_idx=frame_idx,
            current_dt_time=current_dt_time,
        )

    def process_frame(
        self,
        tracks: List[Track],
        zones: Optional[List[ZoneDefinition]] = None,
        intrusion_candidates: Optional[List[IntrusionEventCandidate]] = None,
        zone_candidates: Optional[List[IntrusionEventCandidate]] = None,
        frame_time: Optional[float] = None,
        timestamp_iso: Optional[str] = None,
        frame_idx: int = 0,
        current_dt_time: Optional[datetime.time] = None,
    ) -> List[SuspiciousActivityCandidate]:
        """Convenience alias for process() matching common test signatures."""
        return self.process(
            tracks=tracks,
            zones=zones or [],
            zone_candidates=intrusion_candidates or zone_candidates or [],
            frame_time=frame_time,
            timestamp_iso=timestamp_iso,
            frame_idx=frame_idx,
            current_dt_time=current_dt_time,
        )

    def get_active_loitering_states(self) -> List[Dict[str, Any]]:
        """Return list of active dwell/loitering timers for operator awareness."""
        states = self.loitering_rule.get_active_states()
        return [
            {
                "zone_id": s.zone_id,
                "zone_name": s.zone_name,
                "zone_type": s.zone_type,
                "track_id": s.track_id,
                "object_type": s.object_type,
                "current_duration_sec": round(s.current_duration, 1),
                "threshold_sec": self.loitering_threshold_sec,
                "triggered": s.triggered,
            }
            for s in states.values()
        ]

    def reset(self) -> None:
        """Reset all internal rule states."""
        for rule in self.rules:
            rule.reset()
