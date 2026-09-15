# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: tests.test_event_history_evidence
# Description: 20 comprehensive automated tests for Phase 10 Event History + Evidence Hardening.
# License: Apache-2.0
# ==============================================================================

import os
import json
import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
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
)
from app.services.events.websocket import connection_manager
from app.services.events.engine import event_engine


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
    if db.query(Camera).count() == 0:
        cam = Camera(
            name="Border Post Alpha",
            source_type="VIDEO_FILE",
            source_uri="data/demo/sample_cctv.mp4",
            status="ONLINE",
            enabled=True,
        )
        db.add(cam)
        db.commit()
    db.close()
    event_engine.reset()


def make_dummy_frame() -> np.ndarray:
    """Create a dummy BGR test image frame."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[100:300, 100:300] = [0, 128, 255]
    return frame


def create_camera_and_zone():
    """Helper to create a test camera and test zone in database."""
    db = SessionLocal()
    cam = Camera(
        name="Border Post Alpha",
        source_type="VIDEO_FILE",
        source_uri="data/demo/test.mp4",
        status="ONLINE",
        enabled=False,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    cam_id = cam.id

    zone = Zone(
        camera_id=cam_id,
        name="Perimeter Zone 1",
        zone_type="RESTRICTED",
        polygon_json=json.dumps([[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]),
        enabled=True,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    zone_id = zone.id
    db.close()
    return cam_id, zone_id


# -----------------------------------------------------------------------------
# 1. test_1_create_event: Event persisted with status NEW
# -----------------------------------------------------------------------------
def test_1_create_event():
    cam_id, zone_id = create_camera_and_zone()
    candidate = EventCandidate(
        event_type=SystemEventType.ZONE_INTRUSION.value,
        camera_id=cam_id,
        zone_id=zone_id,
        object_type="person",
        track_id=101,
        severity=EventSeverity.CRITICAL.value,
        reason="Intrusion into restricted perimeter",
    )
    db = SessionLocal()
    saved = event_engine.process_candidate(candidate, frame=make_dummy_frame(), db=db)
    assert saved is not None
    event_id = saved.id
    db.close()

    db = SessionLocal()
    record = db.query(Event).filter(Event.id == event_id).first()
    assert record is not None
    assert record.status == EventStatus.NEW.value
    assert record.camera_id == cam_id
    assert record.zone_id == zone_id
    assert record.severity == "CRITICAL"
    db.close()


# -----------------------------------------------------------------------------
# 2. test_2_retrieve_event: Retrieve event by ID via GET /api/events/{id}
# -----------------------------------------------------------------------------
def test_2_retrieve_event(client):
    cam_id, zone_id = create_camera_and_zone()
    candidate = EventCandidate(
        event_type=SystemEventType.LOITERING.value,
        camera_id=cam_id,
        zone_id=zone_id,
        object_type="person",
        track_id=102,
        severity=EventSeverity.WARNING.value,
        reason="Subject loitering near fence",
    )
    db = SessionLocal()
    saved = event_engine.process_candidate(candidate, frame=make_dummy_frame(), db=db)
    event_id = saved.id
    db.close()

    res = client.get(f"/api/events/{event_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == event_id
    assert data["event_type"] == SystemEventType.LOITERING.value
    assert data["camera_name"] == "Border Post Alpha"
    assert data["zone_name"] == "Perimeter Zone 1"
    assert data["reason"] == "Subject loitering near fence"


# -----------------------------------------------------------------------------
# 3. test_3_event_id_stable: Canonical ID matches across DB, WebSocket payload, and API
# -----------------------------------------------------------------------------
def test_3_event_id_stable(client):
    cam_id, zone_id = create_camera_and_zone()
    broadcasts = []

    def fake_broadcast(msg):
        broadcasts.append(msg)

    orig_broadcast = connection_manager.broadcast
    connection_manager.broadcast = fake_broadcast
    try:
        candidate = EventCandidate(
            event_type=SystemEventType.ZONE_INTRUSION.value,
            camera_id=cam_id,
            zone_id=zone_id,
            object_type="car",
            track_id=103,
            severity=EventSeverity.HIGH.value,
            reason="Unusual vehicle stop",
        )
        db = SessionLocal()
        saved = event_engine.process_candidate(candidate, frame=make_dummy_frame(), db=db)
        event_id = saved.id
        db.close()

        assert len(broadcasts) == 1
        ws_event_id = broadcasts[0]["event_id"]
        assert ws_event_id == event_id

        res = client.get(f"/api/events/{event_id}")
        assert res.status_code == 200
        assert res.json()["id"] == event_id
    finally:
        connection_manager.broadcast = orig_broadcast


# -----------------------------------------------------------------------------
# 4. test_4_persistence_after_restart: Event survives database session restart
# -----------------------------------------------------------------------------
def test_4_persistence_after_restart():
    cam_id, _ = create_camera_and_zone()
    candidate = EventCandidate(
        event_type=SystemEventType.NIGHT_MOVEMENT.value,
        camera_id=cam_id,
        severity=EventSeverity.CRITICAL.value,
        reason="Night-time activity detected",
    )
    db1 = SessionLocal()
    saved = event_engine.process_candidate(candidate, db=db1)
    event_id = saved.id
    db1.close()

    # Simulate fresh app startup & new db session
    db2 = SessionLocal()
    record = db2.query(Event).filter(Event.id == event_id).first()
    assert record is not None
    assert record.id == event_id
    assert record.event_type == SystemEventType.NIGHT_MOVEMENT.value
    db2.close()


# -----------------------------------------------------------------------------
# 5. test_5_filtering_camera_severity_type: Query filtering by camera, severity, and event_type
# -----------------------------------------------------------------------------
def test_5_filtering_camera_severity_type(client):
    cam_id, _ = create_camera_and_zone()
    db = SessionLocal()
    cam2 = Camera(name="Post Bravo", source_type="VIDEO_FILE", source_uri="demo2.mp4", status="ONLINE", enabled=False)
    db.add(cam2)
    db.commit()
    db.refresh(cam2)
    cam2_id = cam2.id

    # Create 3 distinct events
    e1 = EventCandidate(event_type=SystemEventType.ZONE_INTRUSION.value, camera_id=cam_id, severity=EventSeverity.CRITICAL.value, reason="Ev 1")
    e2 = EventCandidate(event_type=SystemEventType.LOITERING.value, camera_id=cam_id, severity=EventSeverity.WARNING.value, reason="Ev 2")
    e3 = EventCandidate(event_type=SystemEventType.ZONE_INTRUSION.value, camera_id=cam2_id, severity=EventSeverity.CRITICAL.value, reason="Ev 3")
    
    event_engine.process_candidate(e1, db=db)
    event_engine.process_candidate(e2, db=db)
    event_engine.process_candidate(e3, db=db)
    db.close()

    # Filter by camera
    res_cam = client.get(f"/api/events?camera_id={cam_id}")
    assert res_cam.status_code == 200
    assert len(res_cam.json()["events"]) == 2

    # Filter by severity
    res_sev = client.get("/api/events?severity=WARNING")
    assert res_sev.status_code == 200
    events_sev = res_sev.json()["events"]
    assert len(events_sev) == 1
    assert events_sev[0]["event_type"] == "LOITERING"

    # Filter by event_type
    res_type = client.get("/api/events?event_type=ZONE_INTRUSION")
    assert res_type.status_code == 200
    assert len(res_type.json()["events"]) == 2


# -----------------------------------------------------------------------------
# 6. test_6_date_filtering: Query filtering by start_time and end_time
# -----------------------------------------------------------------------------
def test_6_date_filtering(client):
    cam_id, _ = create_camera_and_zone()
    db = SessionLocal()

    now = datetime.now(timezone.utc)
    t_mid = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    ev1 = Event(
        camera_id=cam_id,
        event_type="ZONE_INTRUSION",
        severity="HIGH",
        status="NEW",
        timestamp=now - timedelta(days=2),
        reason="Old event",
    )
    ev2 = Event(
        camera_id=cam_id,
        event_type="ZONE_INTRUSION",
        severity="HIGH",
        status="NEW",
        timestamp=now,
        reason="Recent event",
    )
    db.add_all([ev1, ev2])
    db.commit()
    db.close()

    # Query with start_time after ev1
    res = client.get(f"/api/events?start_time={t_mid}")
    assert res.status_code == 200
    items = res.json()["events"]
    assert len(items) == 1
    assert items[0]["reason"] == "Recent event"


# -----------------------------------------------------------------------------
# 7. test_7_pagination: Bounded query results with limit and offset
# -----------------------------------------------------------------------------
def test_7_pagination(client):
    cam_id, _ = create_camera_and_zone()
    db = SessionLocal()
    for i in range(10):
        ev = Event(
            camera_id=cam_id,
            event_type="ZONE_INTRUSION",
            severity="HIGH",
            status="NEW",
            reason=f"Event {i}",
        )
        db.add(ev)
    db.commit()
    db.close()

    res = client.get("/api/events?limit=4&offset=0")
    assert res.status_code == 200
    assert len(res.json()["events"]) == 4
    assert res.json()["total"] == 10

    res2 = client.get("/api/events?limit=4&offset=4")
    assert res2.status_code == 200
    assert len(res2.json()["events"]) == 4

    res3 = client.get("/api/events?limit=4&offset=8")
    assert res3.status_code == 200
    assert len(res3.json()["events"]) == 2


# -----------------------------------------------------------------------------
# 8. test_8_evidence_capture_hierarchy: Evidence saved to data/evidence/YYYY/MM/DD/
# -----------------------------------------------------------------------------
def test_8_evidence_capture_hierarchy():
    cam_id, _ = create_camera_and_zone()
    candidate = EventCandidate(
        event_type=SystemEventType.ZONE_INTRUSION.value,
        camera_id=cam_id,
        severity=EventSeverity.CRITICAL.value,
        reason="Hierarchical evidence test",
    )
    db = SessionLocal()
    frame = make_dummy_frame()
    saved = event_engine.process_candidate(candidate, frame=frame, db=db)
    evidence_path = saved.evidence_path
    db.close()

    assert evidence_path is not None
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y/%m/%d")
    normalized_path = evidence_path.replace("\\", "/")
    assert "evidence" in normalized_path
    assert date_part in normalized_path
    full_path = os.path.join(settings.ROOT_DIR, normalized_path)
    if not os.path.exists(full_path):
        full_path = os.path.join(settings.DATA_DIR, normalized_path)
    assert os.path.exists(full_path)


# -----------------------------------------------------------------------------
# 9. test_9_evidence_link_and_retrieval: Evidence served via GET /api/events/{id}/evidence
# -----------------------------------------------------------------------------
def test_9_evidence_link_and_retrieval(client):
    cam_id, _ = create_camera_and_zone()
    candidate = EventCandidate(
        event_type=SystemEventType.ZONE_INTRUSION.value,
        camera_id=cam_id,
        severity=EventSeverity.CRITICAL.value,
        reason="Evidence endpoint test",
    )
    db = SessionLocal()
    saved = event_engine.process_candidate(candidate, frame=make_dummy_frame(), db=db)
    event_id = saved.id
    db.close()

    res = client.get(f"/api/events/{event_id}/evidence")
    assert res.status_code == 200
    assert res.headers["content-type"] in ["image/jpeg", "image/jpg"]
    assert len(res.content) > 0


# -----------------------------------------------------------------------------
# 10. test_10_evidence_failure_graceful: Event retained with evidence_path=None if snapshot fails
# -----------------------------------------------------------------------------
def test_10_evidence_failure_graceful():
    cam_id, _ = create_camera_and_zone()
    candidate = EventCandidate(
        event_type=SystemEventType.LOITERING.value,
        camera_id=cam_id,
        severity=EventSeverity.WARNING.value,
        reason="No frame event candidate",
    )
    db = SessionLocal()
    # Passing frame=None triggers graceful fallback to evidence_path=None
    saved = event_engine.process_candidate(candidate, frame=None, db=db)
    event_id = saved.id
    db.close()

    assert event_id is not None
    assert saved.evidence_path is None
    assert saved.status == EventStatus.NEW.value


# -----------------------------------------------------------------------------
# 11. test_11_filesystem_safety_traversal: Path traversal attempts blocked with 400/403
# -----------------------------------------------------------------------------
def test_11_filesystem_safety_traversal(client):
    cam_id, _ = create_camera_and_zone()
    db = SessionLocal()
    ev_bad = Event(
        camera_id=cam_id,
        event_type="ZONE_INTRUSION",
        severity="HIGH",
        status="NEW",
        evidence_path="../../etc/passwd",
    )
    db.add(ev_bad)
    db.commit()
    db.refresh(ev_bad)
    bad_id = ev_bad.id
    db.close()

    res = client.get(f"/api/events/{bad_id}/evidence")
    assert res.status_code in [400, 403, 404]


# -----------------------------------------------------------------------------
# 12. test_12_realtime_consistency: WebSocket broadcast contains exact same event_id as DB
# -----------------------------------------------------------------------------
def test_12_realtime_consistency():
    cam_id, _ = create_camera_and_zone()
    received_msgs = []

    def mock_broadcast(msg):
        received_msgs.append(msg)

    orig_broadcast = connection_manager.broadcast
    connection_manager.broadcast = mock_broadcast
    try:
        cand = EventCandidate(
            event_type=SystemEventType.ANPR_DETECTED.value,
            camera_id=cam_id,
            severity=EventSeverity.INFO.value,
            reason="Plate DL01AB1234 recognized",
        )
        db = SessionLocal()
        saved = event_engine.process_candidate(cand, frame=make_dummy_frame(), db=db)
        event_id = saved.id
        db_ev = db.query(Event).filter(Event.id == event_id).first()
        db.close()

        assert len(received_msgs) == 1
        ws_id = received_msgs[0]["event_id"]
        assert ws_id == event_id
        assert ws_id == db_ev.id
    finally:
        connection_manager.broadcast = orig_broadcast


# -----------------------------------------------------------------------------
# 13. test_13_refresh_consistency: Refreshing displays exact same persisted record
# -----------------------------------------------------------------------------
def test_13_refresh_consistency(client):
    cam_id, _ = create_camera_and_zone()
    cand = EventCandidate(
        event_type=SystemEventType.ZONE_INTRUSION.value,
        camera_id=cam_id,
        severity=EventSeverity.CRITICAL.value,
        reason="Refresh test event",
    )
    db = SessionLocal()
    saved = event_engine.process_candidate(cand, frame=make_dummy_frame(), db=db)
    event_id = saved.id
    db.close()

    res1 = client.get(f"/api/events/{event_id}")
    res2 = client.get(f"/api/events/{event_id}")
    assert res1.json() == res2.json()


# -----------------------------------------------------------------------------
# 14. test_14_browser_disconnect_resilience: Disconnected socket does not disrupt persistence or future alerts
# -----------------------------------------------------------------------------
def test_14_browser_disconnect_resilience():
    cam_id, _ = create_camera_and_zone()

    def fail_broadcast(msg):
        raise ConnectionResetError("Client connection closed unexpectedly")

    orig_broadcast = connection_manager.broadcast
    connection_manager.broadcast = fail_broadcast
    try:
        cand = EventCandidate(
            event_type=SystemEventType.LOITERING.value,
            camera_id=cam_id,
            severity=EventSeverity.WARNING.value,
            reason="Resilience test",
        )
        db = SessionLocal()
        saved = event_engine.process_candidate(cand, db=db)
        record = db.query(Event).filter(Event.id == saved.id).first()
        db.close()

        # Should still persist without unhandled exception
        assert saved is not None
        assert record is not None
        assert record.reason == "Resilience test"
    finally:
        connection_manager.broadcast = orig_broadcast


# -----------------------------------------------------------------------------
# 15. test_15_event_list_entity_names: Camera name and zone name properly resolved in response
# -----------------------------------------------------------------------------
def test_15_event_list_entity_names(client):
    cam_id, zone_id = create_camera_and_zone()
    cand = EventCandidate(
        event_type=SystemEventType.ZONE_INTRUSION.value,
        camera_id=cam_id,
        zone_id=zone_id,
        severity=EventSeverity.CRITICAL.value,
        reason="Entity resolution test",
    )
    db = SessionLocal()
    event_engine.process_candidate(cand, db=db)
    db.close()

    res = client.get("/api/events")
    assert res.status_code == 200
    events = res.json()["events"]
    assert len(events) == 1
    assert events[0]["camera_name"] == "Border Post Alpha"
    assert events[0]["zone_name"] == "Perimeter Zone 1"


# -----------------------------------------------------------------------------
# 16. test_16_search_filtering: Text search query across reason, type, and camera
# -----------------------------------------------------------------------------
def test_16_search_filtering(client):
    cam_id, _ = create_camera_and_zone()
    db = SessionLocal()
    e1 = Event(camera_id=cam_id, event_type="ZONE_INTRUSION", severity="HIGH", status="NEW", reason="Suspicious bag left")
    e2 = Event(camera_id=cam_id, event_type="LOITERING", severity="WARNING", status="NEW", reason="Person wandering around")
    db.add_all([e1, e2])
    db.commit()
    db.close()

    # Search for "bag"
    res = client.get("/api/events?search=bag")
    assert res.status_code == 200
    items = res.json()["events"]
    assert len(items) == 1
    assert items[0]["reason"] == "Suspicious bag left"

    # Search for "wandering"
    res2 = client.get("/api/events?search=wandering")
    assert res2.status_code == 200
    items2 = res2.json()["events"]
    assert len(items2) == 1
    assert items2[0]["reason"] == "Person wandering around"


# -----------------------------------------------------------------------------
# 17. test_17_event_details_breakdown: Complete breakdown returned for event modal
# -----------------------------------------------------------------------------
def test_17_event_details_breakdown(client):
    cam_id, zone_id = create_camera_and_zone()
    cand = EventCandidate(
        event_type=SystemEventType.ZONE_INTRUSION.value,
        camera_id=cam_id,
        zone_id=zone_id,
        object_type="person",
        track_id=88,
        severity=EventSeverity.CRITICAL.value,
        reason="Detailed breakdown test",
        confidence=0.95,
    )
    db = SessionLocal()
    saved = event_engine.process_candidate(cand, frame=make_dummy_frame(), db=db)
    event_id = saved.id
    db.close()

    res = client.get(f"/api/events/{event_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == event_id
    assert data["camera_name"] == "Border Post Alpha"
    assert data["zone_name"] == "Perimeter Zone 1"
    assert data["object_type"] == "person"
    assert data["track_id"] == 88
    assert data["reason"] == "Detailed breakdown test"
    assert data["confidence"] == 0.95
    assert data["evidence_path"] is not None


# -----------------------------------------------------------------------------
# 18. test_18_camera_relation_preserved: Camera removal leaves historical event record intact
# -----------------------------------------------------------------------------
def test_18_camera_relation_preserved(client):
    db = SessionLocal()
    ev = Event(
        camera_id=99999,
        event_type="ZONE_INTRUSION",
        severity="CRITICAL",
        status="NEW",
        reason="Archived camera event",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    event_id = ev.id
    db.close()

    # Event must still be retrievable with fallback camera name
    res = client.get(f"/api/events/{event_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == event_id
    assert "Camera #99999 (Archived)" in data["camera_name"]


# -----------------------------------------------------------------------------
# 19. test_19_zone_relation_preserved: Zone modification/removal preserves event record
# -----------------------------------------------------------------------------
def test_19_zone_relation_preserved(client):
    cam_id, zone_id = create_camera_and_zone()
    cand = EventCandidate(
        event_type=SystemEventType.ZONE_INTRUSION.value,
        camera_id=cam_id,
        zone_id=zone_id,
        severity=EventSeverity.CRITICAL.value,
        reason="Zone deletion test",
    )
    db = SessionLocal()
    saved = event_engine.process_candidate(cand, db=db)
    event_id = saved.id

    # Delete zone
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    db.delete(zone)
    db.commit()
    db.close()

    # Event remains intact and accessible
    res = client.get(f"/api/events/{event_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == event_id


# -----------------------------------------------------------------------------
# 20. test_20_full_pipeline_end_to_end: Complete flow from detector/rules to DB, evidence, WebSocket, and history API
# -----------------------------------------------------------------------------
def test_20_full_pipeline_end_to_end(client):
    cam_id, zone_id = create_camera_and_zone()
    ws_events = []

    def mock_broadcast(msg):
        ws_events.append(msg)

    orig_broadcast = connection_manager.broadcast
    connection_manager.broadcast = mock_broadcast
    try:
        # 1. Pipeline trigger (e.g. zone intrusion candidate)
        cand = EventCandidate(
            event_type=SystemEventType.ZONE_INTRUSION.value,
            camera_id=cam_id,
            zone_id=zone_id,
            object_type="person",
            track_id=999,
            severity=EventSeverity.CRITICAL.value,
            reason="Full pipeline E2E perimeter breach",
            confidence=0.98,
        )
        frame = make_dummy_frame()

        # 2. Record event via EventEngine
        db = SessionLocal()
        saved = event_engine.process_candidate(cand, frame=frame, db=db)
        event_id = saved.id
        db.close()

        # 3. Verify WebSocket broadcast occurred with same event_id
        assert len(ws_events) == 1
        assert ws_events[0]["event_id"] == event_id
        assert ws_events[0]["severity"] == "CRITICAL"

        # 4. Verify History list API returns the event
        res_list = client.get("/api/events?event_type=ZONE_INTRUSION")
        assert res_list.status_code == 200
        items = res_list.json()["events"]
        assert any(item["id"] == event_id for item in items)

        # 5. Verify Detail API returns full entity names and metadata
        res_detail = client.get(f"/api/events/{event_id}")
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["id"] == event_id
        assert detail["camera_name"] == "Border Post Alpha"
        assert detail["zone_name"] == "Perimeter Zone 1"
        assert detail["confidence"] == 0.98

        # 6. Verify Evidence snapshot retrieval
        res_evidence = client.get(f"/api/events/{event_id}/evidence")
        assert res_evidence.status_code == 200
        assert len(res_evidence.content) > 0
    finally:
        connection_manager.broadcast = orig_broadcast
