# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: tests.test_event_engine
# Description: 19 comprehensive automated tests for Phase 9 Event Engine + Real-Time Alerts.
# License: Apache-2.0
# ==============================================================================

import os
import time
import pytest
import numpy as np
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.db.session import init_db, SessionLocal
from app.models.schema import Camera, Zone, Event
from app.services.events.models import (
    EventCandidate,
    EventSeverity,
    EventStatus,
    SystemEventType,
    DEFAULT_SEVERITY_MAP,
)
from app.services.events.websocket import ConnectionManager, connection_manager
from app.services.events.engine import EventEngine, event_engine
from app.services.video.worker import CameraWorker
from app.services.tracking.tracker import Track, TrackState
from app.services.zone.models import ZoneType, ZoneDefinition, IntrusionEventCandidate
from app.services.rules.models import SuspiciousActivityCandidate, ActivityType, ActivitySeverity
from app.services.rules.engine import SuspiciousActivityEngine


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_events_and_state():
    """Ensure clean events table and reset event engine state before each test."""
    db = SessionLocal()
    db.query(Event).delete()
    db.commit()
    db.close()
    event_engine.reset()
    yield
    db = SessionLocal()
    db.query(Event).delete()
    db.commit()
    db.close()
    event_engine.reset()


def make_dummy_frame() -> np.ndarray:
    """Create a dummy BGR test image frame."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


# ------------------------------------------------------------------------------
# Test 1: Candidate Validation (Valid candidate accepted)
# ------------------------------------------------------------------------------
def test_1_candidate_validation():
    """Verify that a valid EventCandidate passes validation."""
    cand = EventCandidate(
        event_type="ZONE_INTRUSION",
        camera_id=1,
        reason="Person entered Restricted Zone Alpha",
        object_type="person",
        track_id=101,
        zone_id=1,
        confidence=0.92,
    )
    is_valid, err = cand.validate()
    assert is_valid is True
    assert err is None


# ------------------------------------------------------------------------------
# Test 2: Invalid Candidate (Missing required fields rejected)
# ------------------------------------------------------------------------------
def test_2_invalid_candidate():
    """Verify that malformed candidates (missing event_type, camera_id, or reason) are safely rejected."""
    # Missing event_type
    cand1 = EventCandidate(event_type="", camera_id=1, reason="Test reason")
    assert cand1.validate()[0] is False

    # Missing camera_id
    cand2 = EventCandidate(event_type="ZONE_INTRUSION", camera_id=None, reason="Test reason")
    assert cand2.validate()[0] is False

    # Missing reason
    cand3 = EventCandidate(event_type="ZONE_INTRUSION", camera_id=1, reason="")
    assert cand3.validate()[0] is False

    # EventEngine rejects without crashing or persisting
    engine = EventEngine()
    result = engine.process_candidate(cand1)
    assert result is None


# ------------------------------------------------------------------------------
# Test 3: Event Persistence (SQLite record created)
# ------------------------------------------------------------------------------
def test_3_event_persistence():
    """Verify that a valid candidate is persisted as an Event record in SQLite with status NEW."""
    engine = EventEngine(cooldown_sec=1.0)
    cand = EventCandidate(
        event_type="ZONE_INTRUSION",
        camera_id=1,
        reason="Person entered Restricted Zone Alpha",
        object_type="person",
        track_id=105,
        zone_id=2,
        confidence=0.94,
    )

    persisted = engine.process_candidate(cand)
    assert persisted is not None
    assert persisted.id is not None
    assert persisted.status == "NEW"
    assert persisted.event_type == "ZONE_INTRUSION"
    assert persisted.severity == "CRITICAL"
    assert persisted.confidence == 0.94

    # Verify query from database
    db = SessionLocal()
    found = db.query(Event).filter(Event.id == persisted.id).first()
    assert found is not None
    assert found.camera_id == 1
    assert found.reason == "Person entered Restricted Zone Alpha"
    db.close()


# ------------------------------------------------------------------------------
# Test 4: WebSocket Broadcast (Connected client receives payload)
# ------------------------------------------------------------------------------
def test_4_websocket_broadcast(client):
    """Verify that when a client is connected to /ws/events, it receives the normalized event payload."""
    with client.websocket_connect("/ws/events") as websocket:
        engine = EventEngine(cooldown_sec=1.0)
        cand = EventCandidate(
            event_type="LOITERING",
            camera_id=1,
            reason="Person loitering in Monitoring Zone for 35.0s",
            object_type="person",
            track_id=202,
            confidence=0.88,
        )
        persisted = engine.process_candidate(cand)
        assert persisted is not None

        # Receive broadcast on websocket
        data = websocket.receive_json()
        assert data["event_id"] == persisted.id
        assert data["event_type"] == "LOITERING"
        assert data["severity"] == "HIGH"
        assert data["track_id"] == 202
        assert "Person loitering" in data["reason"]


# ------------------------------------------------------------------------------
# Test 5: No Client (Event persists normally with 0 connected clients)
# ------------------------------------------------------------------------------
def test_5_no_client():
    """Verify that when no clients are connected to WebSocket, event persistence proceeds without errors."""
    engine = EventEngine(cooldown_sec=1.0)
    assert connection_manager.client_count == 0

    cand = EventCandidate(
        event_type="NIGHT_MOVEMENT",
        camera_id=2,
        reason="Vehicle detected during configured night-time period.",
        object_type="car",
        track_id=303,
        confidence=0.91,
    )
    persisted = engine.process_candidate(cand)
    assert persisted is not None
    assert persisted.id is not None
    assert persisted.severity == "WARNING"


# ------------------------------------------------------------------------------
# Test 6: Duplicate Event Cooldown (Suppressed within window)
# ------------------------------------------------------------------------------
def test_6_duplicate_event_cooldown():
    """Verify that repeated candidate submissions within the cooldown window are suppressed."""
    engine = EventEngine(cooldown_sec=10.0)
    cand = EventCandidate(
        event_type="ZONE_INTRUSION",
        camera_id=1,
        reason="Intrusion candidate",
        object_type="person",
        track_id=404,
        zone_id=1,
    )

    # Frame 1: Generates event
    e1 = engine.process_candidate(cand, current_time_epoch=1000.0)
    assert e1 is not None

    # Frame 2 (2s later): Suppressed
    e2 = engine.process_candidate(cand, current_time_epoch=1002.0)
    assert e2 is None

    # Frame 3 (9.9s later): Still suppressed
    e3 = engine.process_candidate(cand, current_time_epoch=1009.9)
    assert e3 is None

    # Frame 4 (11s later): Cooldown expired -> new event generated
    e4 = engine.process_candidate(cand, current_time_epoch=1011.0)
    assert e4 is not None
    assert e4.id != e1.id


# ------------------------------------------------------------------------------
# Test 7: Intrusion Event Generation
# ------------------------------------------------------------------------------
def test_7_zone_intrusion_event():
    """Verify that a ZONE_INTRUSION candidate yields a persisted CRITICAL severity event."""
    engine = EventEngine(cooldown_sec=5.0)
    cand = EventCandidate(
        event_type="ZONE_INTRUSION",
        camera_id=1,
        reason="Person entered Restricted Zone Alpha",
        object_type="person",
        track_id=505,
        zone_id=10,
        confidence=0.96,
    )

    event = engine.process_candidate(cand)
    assert event is not None
    assert event.event_type == "ZONE_INTRUSION"
    assert event.severity == "CRITICAL"
    assert event.track_id == 505
    assert event.zone_id == 10


# ------------------------------------------------------------------------------
# Test 8: Loitering Event Generation
# ------------------------------------------------------------------------------
def test_8_loitering_event():
    """Verify that a LOITERING candidate yields a persisted HIGH severity event."""
    engine = EventEngine(cooldown_sec=5.0)
    cand = EventCandidate(
        event_type="LOITERING",
        camera_id=1,
        reason="Person loitering in Perimeter Area for 42.0s",
        object_type="person",
        track_id=606,
        zone_id=5,
        confidence=0.89,
    )

    event = engine.process_candidate(cand)
    assert event is not None
    assert event.event_type == "LOITERING"
    assert event.severity == "HIGH"


# ------------------------------------------------------------------------------
# Test 9: Night Movement Event Generation
# ------------------------------------------------------------------------------
def test_9_night_movement_event():
    """Verify that a NIGHT_MOVEMENT candidate yields a persisted WARNING severity event."""
    engine = EventEngine(cooldown_sec=5.0)
    cand = EventCandidate(
        event_type="NIGHT_MOVEMENT",
        camera_id=3,
        reason="Person detected during configured night-time period.",
        object_type="person",
        track_id=707,
        confidence=0.93,
    )

    event = engine.process_candidate(cand)
    assert event is not None
    assert event.event_type == "NIGHT_MOVEMENT"
    assert event.severity == "WARNING"


# ------------------------------------------------------------------------------
# Test 10: ANPR Duplicate Control (Repeated plate on same track does not flood)
# ------------------------------------------------------------------------------
def test_10_anpr_duplicate_control():
    """Verify that repeated ANPR detections for the same track are throttled by cooldown."""
    engine = EventEngine(cooldown_sec=15.0)
    cand = EventCandidate(
        event_type="ANPR_DETECTED",
        camera_id=1,
        reason="License plate RJ14AB1234 detected (HIGH quality)",
        object_type="car",
        track_id=808,
        confidence=0.98,
        metadata={"plate_text": "RJ14AB1234", "quality": "HIGH"},
    )

    e1 = engine.process_candidate(cand, current_time_epoch=2000.0)
    assert e1 is not None

    # Immediate next frame OCR -> suppressed
    e2 = engine.process_candidate(cand, current_time_epoch=2000.5)
    assert e2 is None


# ------------------------------------------------------------------------------
# Test 11: Severity Mapping Defaults
# ------------------------------------------------------------------------------
def test_11_severity_mapping():
    """Verify default severity resolution across all supported event types."""
    assert EventCandidate(event_type="PERSON_DETECTED", camera_id=1, reason="r").resolve_severity() == "INFO"
    assert EventCandidate(event_type="VEHICLE_DETECTED", camera_id=1, reason="r").resolve_severity() == "INFO"
    assert EventCandidate(event_type="FACE_DETECTED", camera_id=1, reason="r").resolve_severity() == "INFO"
    assert EventCandidate(event_type="ANPR_DETECTED", camera_id=1, reason="r").resolve_severity() == "INFO"
    assert EventCandidate(event_type="NIGHT_MOVEMENT", camera_id=1, reason="r").resolve_severity() == "WARNING"
    assert EventCandidate(event_type="LOITERING", camera_id=1, reason="r").resolve_severity() == "HIGH"
    assert EventCandidate(event_type="ZONE_INTRUSION", camera_id=1, reason="r").resolve_severity() == "CRITICAL"


# ------------------------------------------------------------------------------
# Test 12: Evidence Capture (Snapshot saved and linked)
# ------------------------------------------------------------------------------
def test_12_evidence_capture():
    """Verify that providing a frame snapshot creates an evidence image on disk and populates evidence_path."""
    engine = EventEngine(cooldown_sec=1.0)
    frame = make_dummy_frame()
    cand = EventCandidate(
        event_type="ZONE_INTRUSION",
        camera_id=1,
        reason="Intrusion with evidence",
        object_type="person",
        track_id=909,
    )

    event = engine.process_candidate(cand, frame=frame)
    assert event is not None
    assert event.evidence_path is not None
    assert "data/evidence/events" in event.evidence_path or "data" in event.evidence_path
    
    # Check that file exists on disk
    full_path = os.path.join(settings.ROOT_DIR, event.evidence_path)
    assert os.path.exists(full_path)


# ------------------------------------------------------------------------------
# Test 13: Evidence Failure Handling (Graceful continuation)
# ------------------------------------------------------------------------------
def test_13_evidence_failure_graceful(monkeypatch):
    """Verify that if cv2.imwrite fails, event is still persisted with evidence_path=None."""
    def broken_imwrite(path, img):
        raise IOError("Disk write simulated failure")

    monkeypatch.setattr("cv2.imwrite", broken_imwrite)

    engine = EventEngine(cooldown_sec=1.0)
    frame = make_dummy_frame()
    cand = EventCandidate(
        event_type="ZONE_INTRUSION",
        camera_id=1,
        reason="Intrusion with failing evidence",
        object_type="person",
        track_id=910,
    )

    event = engine.process_candidate(cand, frame=frame)
    assert event is not None
    assert event.id is not None
    assert event.evidence_path is None


# ------------------------------------------------------------------------------
# Test 14: Database Failure Handling (No false success broadcast)
# ------------------------------------------------------------------------------
def test_14_database_failure_handling():
    """Verify that when database persistence fails, engine returns None and does not crash."""
    class BrokenSession:
        def add(self, item): pass
        def commit(self): raise RuntimeError("Simulated DB lock/failure")
        def rollback(self): pass
        def refresh(self, item): pass

    engine = EventEngine(cooldown_sec=1.0)
    cand = EventCandidate(
        event_type="ZONE_INTRUSION",
        camera_id=1,
        reason="Intrusion with failing DB",
        object_type="person",
        track_id=911,
    )

    result = engine.process_candidate(cand, db=BrokenSession())
    assert result is None


# ------------------------------------------------------------------------------
# Test 15: WebSocket Disconnect (Backend continues normally)
# ------------------------------------------------------------------------------
def test_15_websocket_disconnect(client):
    """Verify that a client disconnect does not affect subsequent event processing."""
    with client.websocket_connect("/ws/events") as ws:
        pass  # Closes connection immediately

    engine = EventEngine(cooldown_sec=1.0)
    cand = EventCandidate(
        event_type="LOITERING",
        camera_id=1,
        reason="Post-disconnect event",
        object_type="person",
        track_id=912,
    )
    event = engine.process_candidate(cand)
    assert event is not None
    assert event.id is not None


# ------------------------------------------------------------------------------
# Test 16: WebSocket Reconnect (Client receives future events)
# ------------------------------------------------------------------------------
def test_16_websocket_reconnect(client):
    """Verify that a reconnected client receives subsequent events."""
    # First connection
    with client.websocket_connect("/ws/events") as ws1:
        pass

    # Reconnection
    with client.websocket_connect("/ws/events") as ws2:
        engine = EventEngine(cooldown_sec=1.0)
        cand = EventCandidate(
            event_type="NIGHT_MOVEMENT",
            camera_id=1,
            reason="Reconnected stream event",
            object_type="person",
            track_id=913,
        )
        engine.process_candidate(cand)

        data = ws2.receive_json()
        assert data["track_id"] == 913
        assert data["event_type"] == "NIGHT_MOVEMENT"


# ------------------------------------------------------------------------------
# Test 17: Multiple Clients (All receive broadcasts)
# ------------------------------------------------------------------------------
def test_17_multiple_clients(client):
    """Verify that multiple simultaneous connected clients all receive event broadcasts."""
    with client.websocket_connect("/ws/events") as ws1:
        with client.websocket_connect("/ws/events") as ws2:
            engine = EventEngine(cooldown_sec=1.0)
            cand = EventCandidate(
                event_type="ZONE_INTRUSION",
                camera_id=1,
                reason="Multi-client broadcast event",
                object_type="person",
                track_id=914,
            )
            engine.process_candidate(cand)

            data1 = ws1.receive_json()
            data2 = ws2.receive_json()
            assert data1["track_id"] == 914
            assert data2["track_id"] == 914
            assert data1["event_id"] == data2["event_id"]


# ------------------------------------------------------------------------------
# Test 18: Event History Retrieval (GET /api/events)
# ------------------------------------------------------------------------------
def test_18_event_history_retrieval(client):
    """Verify that persisted events are correctly retrievable via GET /api/events with filters."""
    engine = EventEngine(cooldown_sec=1.0)
    cand = EventCandidate(
        event_type="ZONE_INTRUSION",
        camera_id=5,
        reason="Historical event check",
        object_type="person",
        track_id=915,
        severity="CRITICAL",
    )
    saved = engine.process_candidate(cand)
    assert saved is not None

    # Retrieve all events
    res = client.get("/api/events")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    found = next((e for e in data["events"] if e["id"] == saved.id), None)
    assert found is not None
    assert found["camera_id"] == 5
    assert found["event_type"] == "ZONE_INTRUSION"
    assert found["severity"] == "CRITICAL"

    # Test single event endpoint
    single_res = client.get(f"/api/events/{saved.id}")
    assert single_res.status_code == 200
    assert single_res.json()["id"] == saved.id

    # Test status patch endpoint
    patch_res = client.patch(f"/api/events/{saved.id}", json={"status": "ACKNOWLEDGED"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "ACKNOWLEDGED"


# ------------------------------------------------------------------------------
# Test 19: Full Pipeline Integration
# ------------------------------------------------------------------------------
def test_19_full_pipeline_integration():
    """Verify end-to-end event flow through SuspiciousActivityEngine into EventEngine."""
    engine = SuspiciousActivityEngine(
        camera_id=1,
        loitering_threshold_sec=10.0,
        night_movement_enabled=True,
        night_start_time="20:00",
        night_end_time="06:00",
    )

    trk = Track(
        track_id=999,
        object_type="person",
        bbox=[100, 100, 150, 200],
        confidence=0.95,
        centroid=[125, 150],
        bottom_center=[125, 200],
        first_seen="2026-09-11T22:00:00Z",
        last_seen="2026-09-11T22:00:01Z",
        state=TrackState.ACTIVE,
        hits=5,
        age=5,
    )

    candidates = engine.process(
        tracks=[trk],
        zones=[],
        zone_candidates=[],
        timestamp_iso="2026-09-11T23:00:00Z",
    )

    assert len(candidates) > 0
    night_cand = candidates[0]
    assert night_cand.event_type == ActivityType.NIGHT_MOVEMENT

    # Process through central EventEngine
    event = event_engine.process_candidate(
        EventCandidate(
            event_type=night_cand.event_type,
            camera_id=1,
            reason=night_cand.reason,
            timestamp=night_cand.timestamp,
            severity=night_cand.severity,
            object_type=night_cand.object_type,
            track_id=night_cand.track_id,
            confidence=night_cand.confidence,
        )
    )

    assert event is not None
    assert event.id is not None
    assert event.event_type == "NIGHT_MOVEMENT"
    assert event.severity == "WARNING"
