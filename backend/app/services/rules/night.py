# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.rules.night
# Description: Rule 4 — Deterministic Night-Time Movement Detection (Time-Window Schedule).
# License: Apache-2.0
# ==============================================================================

import re
from datetime import datetime, time as dtime, timezone
from typing import List, Dict, Tuple, Optional, Any
from app.services.tracking.tracker import Track
from app.services.zone.models import ZoneDefinition, IntrusionEventCandidate
from app.services.rules.base import BaseActivityRule
from app.services.rules.models import (
    SuspiciousActivityCandidate,
    ActivityType,
    ActivitySeverity,
)


def parse_time_str(time_str: str) -> dtime:
    """
    Parse a 24-hour time string formatted as HH:MM or HH:MM:SS.
    Raises ValueError with descriptive message if format or range is invalid.
    """
    if not isinstance(time_str, str):
        raise ValueError("Time value must be a string in HH:MM format.")
    
    time_str = time_str.strip()
    match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", time_str)
    if not match:
        raise ValueError(f"Invalid time format '{time_str}'. Expected HH:MM (e.g. 22:00, 05:00).")
    
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = int(match.group(3)) if match.group(3) else 0

    if not (0 <= hours <= 23):
        raise ValueError(f"Hour '{hours}' must be between 00 and 23.")
    if not (0 <= minutes <= 59):
        raise ValueError(f"Minute '{minutes}' must be between 00 and 59.")
    if not (0 <= seconds <= 59):
        raise ValueError(f"Second '{seconds}' must be between 00 and 59.")

    return dtime(hour=hours, minute=minutes, second=seconds)


def is_time_in_window(current_time: dtime, start_time: dtime, end_time: dtime) -> bool:
    """
    Deterministic evaluation of whether a given time falls inside a configured schedule.
    
    Policy & Boundary Rules:
    - Same-day window (e.g. 18:00 to 23:00): True if start_time <= current_time < end_time.
    - Midnight-crossing window (e.g. 22:00 to 05:00): True if current_time >= start_time or current_time < end_time.
    - Start boundary: INCLUSIVE (at start_time -> INSIDE).
    - End boundary: EXCLUSIVE (at end_time -> OUTSIDE).
    - Equal start and end (start_time == end_time): Treated as 24-hour continuous window -> INSIDE.
    """
    if start_time == end_time:
        return True
    elif start_time < end_time:
        return start_time <= current_time < end_time
    else:
        # Crosses midnight (e.g. 22:00 to 05:00)
        return current_time >= start_time or current_time < end_time


class NightMovementRule(BaseActivityRule):
    """
    Rule 4 — Night-Time Movement Detection:
    Monitors movement of persons and vehicles during configured night-time schedule windows.
    Applies per-track cooldown to prevent duplicate per-frame alerting.
    
    NOTE: This is a deterministic TIME-WINDOW rule; it does NOT claim or infer physical darkness.
    """

    SUPPORTED_OBJECT_TYPES = {"person", "car", "motorcycle", "bus", "truck", "vehicle"}

    def __init__(
        self,
        camera_id: int = 1,
        enabled: bool = True,
        start_time_str: str = "22:00",
        end_time_str: str = "05:00",
        cooldown_sec: float = 60.0,
    ):
        self.camera_id = camera_id
        self.enabled = bool(enabled)
        self.start_time_str = start_time_str
        self.end_time_str = end_time_str
        self.start_time = parse_time_str(start_time_str)
        self.end_time = parse_time_str(end_time_str)
        self.cooldown_sec = max(1.0, float(cooldown_sec))

        # (camera_id, "NIGHT_MOVEMENT", track_id) -> last_triggered_time (float)
        self._last_triggered: Dict[Tuple[int, str, int], float] = {}

    def set_config(
        self,
        enabled: Optional[bool] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        cooldown_sec: Optional[float] = None,
    ) -> None:
        """Dynamically update rule schedule and cooldown."""
        if enabled is not None:
            self.enabled = bool(enabled)
        if start_time is not None:
            self.start_time = parse_time_str(start_time)
            self.start_time_str = start_time
        if end_time is not None:
            self.end_time = parse_time_str(end_time)
            self.end_time_str = end_time
        if cooldown_sec is not None:
            self.cooldown_sec = max(1.0, float(cooldown_sec))

    def evaluate(
        self,
        tracks: List[Track],
        zones: Optional[List[ZoneDefinition]] = None,
        zone_candidates: Optional[List[IntrusionEventCandidate]] = None,
        frame_time: Optional[float] = None,
        timestamp_iso: Optional[str] = None,
        frame_idx: int = 0,
        current_dt_time: Optional[dtime] = None,
        current_time_epoch: Optional[float] = None,
    ) -> List[SuspiciousActivityCandidate]:
        if not self.enabled:
            return []

        import time as pytime
        if frame_time is None:
            frame_time = current_time_epoch if current_time_epoch is not None else pytime.time()
        if timestamp_iso is None:
            timestamp_iso = datetime.now(timezone.utc).isoformat()

        # Determine time to evaluate
        if current_dt_time is not None:
            eval_time = current_dt_time
        else:
            try:
                # Attempt to extract time from ISO timestamp
                iso_clean = timestamp_iso.replace("Z", "+00:00")
                parsed_dt = datetime.fromisoformat(iso_clean)
                eval_time = parsed_dt.time()
            except Exception:
                # Fallback to local server clock
                eval_time = datetime.now().time()

        # Check if current time is within configured night window
        if not is_time_in_window(eval_time, self.start_time, self.end_time):
            return []

        candidates: List[SuspiciousActivityCandidate] = []
        active_track_ids = {t.track_id for t in tracks}

        for track in tracks:
            obj_type = (track.object_type or "person").lower()
            if obj_type not in self.SUPPORTED_OBJECT_TYPES:
                continue

            tid = track.track_id
            dedup_key = (self.camera_id, ActivityType.NIGHT_MOVEMENT.value, tid)

            # Enforce cooldown / single trigger per continuous stay
            last_time = self._last_triggered.get(dedup_key)
            if last_time is not None and (frame_time - last_time) < self.cooldown_sec:
                continue

            self._last_triggered[dedup_key] = frame_time

            # Format explainable human-readable reason
            if obj_type == "person":
                reason = "Person detected during configured night-time period."
            else:
                reason = "Vehicle detected during configured night-time period."

            ax = (float(track.bbox[0]) + float(track.bbox[2])) / 2.0
            ay = float(track.bbox[3])

            candidate = SuspiciousActivityCandidate(
                event_type=ActivityType.NIGHT_MOVEMENT.value,
                camera_id=self.camera_id,
                track_id=tid,
                zone_id=None,
                zone_name=track.current_zone if track.current_zone else None,
                zone_type=None,
                object_type=track.object_type,
                timestamp=timestamp_iso,
                severity=ActivitySeverity.WARNING.value,
                reason=reason,
                confidence=track.confidence,
                duration_sec=0.0,
                anchor_point=[ax, ay],
            )
            candidates.append(candidate)

        # Cleanup stale tracks no longer in view after cooldown has passed
        stale_keys = [
            k for k, last_t in self._last_triggered.items()
            if k[2] not in active_track_ids and (frame_time - last_t) > self.cooldown_sec
        ]
        for k in stale_keys:
            del self._last_triggered[k]

        return candidates

    def reset(self) -> None:
        """Reset internal trigger memory."""
        self._last_triggered.clear()
