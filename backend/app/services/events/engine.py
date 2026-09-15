# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.events.engine
# Description: Centralized Event Engine handling validation, deduplication, cooldown,
#              evidence capture, persistence, and real-time alert dispatch.
# License: Apache-2.0
# ==============================================================================

import os
import time
import datetime
import threading
from typing import Optional, Dict, Any, Tuple, List
import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import inference_logger, api_logger
from app.db.session import SessionLocal
from app.models.schema import Event, Camera, Zone
from app.services.events.models import (
    EventCandidate,
    EventSeverity,
    EventStatus,
    DEFAULT_SEVERITY_MAP,
)
from app.services.events.websocket import connection_manager, ConnectionManager


class EventEngine:
    """
    Centralized Event Processing and Real-Time Alert Engine for IBVAP.
    All analytics and rules submit normalized EventCandidates through this engine.
    """

    def __init__(
        self,
        cooldown_sec: Optional[float] = None,
        evidence_storage_path: Optional[str] = None,
        ws_manager: Optional[ConnectionManager] = None,
    ):
        self.cooldown_sec = max(1.0, float(cooldown_sec if cooldown_sec is not None else settings.ALERT_COOLDOWN_SEC))
        self.evidence_storage_path = evidence_storage_path or os.path.join(settings.EVIDENCE_STORAGE_PATH, "events")
        self.ws_manager = ws_manager or connection_manager
        
        # Ensure evidence directory exists
        try:
            os.makedirs(self.evidence_storage_path, exist_ok=True)
        except Exception as exc:
            inference_logger.warning(f"Could not create evidence directory '{self.evidence_storage_path}': {exc}")

        # Deduplication memory: logical_key -> last_triggered_epoch_time (float)
        self._last_triggered: Dict[Tuple, float] = {}
        self._lock = threading.Lock()

    def set_cooldown(self, cooldown_sec: float) -> None:
        """Dynamically update event cooldown threshold."""
        with self._lock:
            self.cooldown_sec = max(1.0, float(cooldown_sec))

    def process_candidate(
        self,
        candidate: EventCandidate,
        frame: Optional[np.ndarray] = None,
        db: Optional[Session] = None,
        current_time_epoch: Optional[float] = None,
    ) -> Optional[Event]:
        """
        Process a candidate event through the strict pipeline:
        1. Validation
        2. Deduplication & Cooldown check
        3. Severity resolution
        4. Evidence capture
        5. Database persistence
        6. WebSocket broadcast
        
        Returns:
            The persisted Event database object if created, or None if rejected/suppressed/failed.
        """
        # 1. Validation
        is_valid, err_msg = candidate.validate()
        if not is_valid:
            inference_logger.warning(f"Rejected invalid EventCandidate: {err_msg}")
            return None

        now_epoch = current_time_epoch if current_time_epoch is not None else time.time()
        logical_key = candidate.get_logical_key()

        # 2. Deduplication & Cooldown
        with self._lock:
            last_time = self._last_triggered.get(logical_key)
            if last_time is not None and (now_epoch - last_time) < self.cooldown_sec:
                # Suppressed by cooldown
                return None
            self._last_triggered[logical_key] = now_epoch

        # 3. Severity Resolution
        resolved_severity = candidate.resolve_severity()

        # Timestamp normalization
        if candidate.timestamp:
            try:
                clean_ts = candidate.timestamp.replace("Z", "+00:00")
                event_dt = datetime.datetime.fromisoformat(clean_ts)
            except Exception:
                event_dt = datetime.datetime.utcnow()
        else:
            event_dt = datetime.datetime.utcnow()

        # 4. Evidence Capture (Annotated Snapshot)
        evidence_path: Optional[str] = candidate.evidence_path
        if evidence_path is None and frame is not None and settings.EVIDENCE_CAPTURE_ENABLED:
            try:
                date_subdir = event_dt.strftime("%Y/%m/%d")
                target_dir = os.path.join(self.evidence_storage_path, date_subdir)
                os.makedirs(target_dir, exist_ok=True)
                timestamp_str = event_dt.strftime("%Y%m%d_%H%M%S_%f")
                safe_event_type = "".join(c for c in candidate.event_type if c.isalnum() or c in ("_", "-"))
                filename = f"event_{safe_event_type}_cam{candidate.camera_id}_{timestamp_str}.jpg"
                full_path = os.path.join(target_dir, filename)
                
                # Encode and write JPEG frame
                success = cv2.imwrite(full_path, frame)
                if success:
                    evidence_path = os.path.relpath(full_path, settings.ROOT_DIR).replace("\\", "/")
                else:
                    inference_logger.warning(f"cv2.imwrite returned False when saving evidence to {full_path}")
            except Exception as ev_exc:
                inference_logger.error(f"Evidence capture failed for event {candidate.event_type}: {ev_exc}")
                evidence_path = None

        # 5. Database Persistence
        db_session = db if db is not None else SessionLocal()
        should_close_db = db is None

        event_record: Optional[Event] = None
        try:
            event_record = Event(
                timestamp=event_dt,
                camera_id=candidate.camera_id,
                event_type=candidate.event_type,
                severity=resolved_severity,
                object_type=candidate.object_type,
                track_id=candidate.track_id,
                zone_id=candidate.zone_id,
                confidence=candidate.confidence,
                reason=candidate.reason,
                evidence_path=evidence_path,
                status=EventStatus.NEW.value,
            )
            db_session.add(event_record)
            db_session.commit()
            db_session.refresh(event_record)
        except Exception as db_exc:
            inference_logger.error(f"Database persistence failed for Event #{candidate.event_type}: {db_exc}")
            try:
                db_session.rollback()
            except Exception:
                pass
            return None
        finally:
            if should_close_db:
                db_session.close()

        # 6. WebSocket Real-Time Broadcast
        if event_record is not None and event_record.id is not None:
            try:
                broadcast_payload = {
                    "event_id": event_record.id,
                    "timestamp": event_record.timestamp.isoformat(),
                    "camera_id": event_record.camera_id,
                    "event_type": event_record.event_type,
                    "severity": event_record.severity,
                    "object_type": event_record.object_type,
                    "track_id": event_record.track_id,
                    "zone_id": event_record.zone_id,
                    "confidence": round(float(event_record.confidence), 4) if event_record.confidence is not None else None,
                    "reason": event_record.reason,
                    "evidence_path": event_record.evidence_path,
                    "status": event_record.status,
                }
                self.ws_manager.broadcast(broadcast_payload)
            except Exception as ws_exc:
                api_logger.warning(f"Error during WebSocket broadcast for Event #{event_record.id}: {ws_exc}")

        return event_record

    def reset(self) -> None:
        """Reset deduplication and cooldown state."""
        with self._lock:
            self._last_triggered.clear()


# Global Singleton instance
event_engine = EventEngine()
