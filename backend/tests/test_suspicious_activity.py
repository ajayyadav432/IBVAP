# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: tests.test_suspicious_activity
# Description: 12 comprehensive automated tests for Phase 7 Suspicious Activity Detection.
# License: Apache-2.0
# ==============================================================================

import json
import os
import time
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import init_db, SessionLocal
from app.models.schema import Camera, Zone
from app.services.tracking.tracker import Track, TrackState
from app.services.zone.models import ZoneType, ZoneDefinition, IntrusionEventCandidate
from app.services.zone.engine import ZoneEngine
from app.services.rules.models import ActivityType, ActivitySeverity, SuspiciousActivityCandidate
from app.services.rules.intrusion import IntrusionRule
from app.services.rules.loitering import LoiteringRule
from app.services.rules.engine import SuspiciousActivityEngine
from app.services.video.worker import CameraWorker
from app.services.video.manager import camera_manager


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def cleanup_zones_and_cameras():
    """Clean up test zones and camera DB entries."""
    db = SessionLocal()
    db.query(Zone).delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(Zone).delete()
    db.commit()
    db.close()


def make_track(track_id: int, object_type: str, bbox: list, current_zone: str = None, confidence: float = 0.92) -> Track:
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    return Track(
        track_id=track_id,
        object_type=object_type,
        bbox=bbox,
        confidence=confidence,
        centroid=[cx, cy],
        bottom_center=[cx, y2],
        first_seen="2026-09-11T12:00:00Z",
        last_seen="2026-09-11T12:00:01Z",
        state=TrackState.ACTIVE,
        hits=10,
        age=10,
        current_zone=current_zone,
    )


def make_zone(zone_id: int, name: str, zone_type: ZoneType, polygon: list, camera_id: int = 1) -> ZoneDefinition:
    return ZoneDefinition(
        id=zone_id,
        camera_id=camera_id,
        name=name,
        zone_type=zone_type.value if hasattr(zone_type, "value") else str(zone_type),
        polygon=polygon,
        enabled=True,
    )


# ------------------------------------------------------------------------------
# Test 1: Restricted Zone Intrusion Rule
# ------------------------------------------------------------------------------
def test_1_restricted_zone_intrusion():
    """Verify that a person entering a RESTRICTED zone generates an explainable HIGH-severity intrusion event."""
    engine = SuspiciousActivityEngine(camera_id=1, loitering_threshold_sec=30.0)
    
    restricted_zone = make_zone(1, "Red Zone Alpha", ZoneType.RESTRICTED, [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]])
    zones = [restricted_zone]
    
    trk = make_track(track_id=101, object_type="person", bbox=[100, 100, 150, 200], current_zone="Red Zone Alpha", confidence=0.95)
    
    # Phase 6 ZoneEngine intrusion candidate (OUTSIDE -> INSIDE)
    intrusion_candidate = IntrusionEventCandidate(
        event_type="ZONE_INTRUSION",
        camera_id=1,
        zone_id=1,
        zone_name="Red Zone Alpha",
        zone_type="RESTRICTED",
        track_id=101,
        object_type="person",
        anchor_point=[125, 200],
        reason="Object entered zone Red Zone Alpha",
        timestamp="2026-09-11T12:00:00Z",
        confidence=0.95,
    )
    
    activities = engine.process(
        tracks=[trk],
        zones=zones,
        zone_candidates=[intrusion_candidate],
        frame_time=1000.0,
    )
    
    assert len(activities) == 1
    act = activities[0]
    assert act.event_type == ActivityType.ZONE_INTRUSION.value
    assert act.severity == ActivitySeverity.HIGH.value
    assert act.track_id == 101
    assert act.zone_id == 1
    assert act.confidence == 0.95
    assert "Red Zone Alpha" in act.reason
    assert "Restricted" in act.reason


# ------------------------------------------------------------------------------
# Test 2: Person Outside Zone
# ------------------------------------------------------------------------------
def test_2_person_outside_no_events():
    """Verify that a person remaining outside configured zones triggers no intrusion or loitering events."""
    engine = SuspiciousActivityEngine(camera_id=1, loitering_threshold_sec=30.0)
    
    restricted_zone = make_zone(1, "Perimeter Fence", ZoneType.RESTRICTED, [[0.0, 0.0], [0.2, 0.0], [0.2, 0.2], [0.0, 0.2]])
    zones = [restricted_zone]
    
    # Track outside zone (current_zone = None)
    trk = make_track(track_id=102, object_type="person", bbox=[800, 800, 850, 900], current_zone=None, confidence=0.88)
    
    for t in [100.0, 110.0, 120.0, 140.0, 200.0]:
        activities = engine.process(
            tracks=[trk],
            zones=zones,
            zone_candidates=[],
            frame_time=t,
        )
        assert len(activities) == 0
        assert len(engine.get_active_loitering_states()) == 0


# ------------------------------------------------------------------------------
# Test 3: Loitering Below Threshold
# ------------------------------------------------------------------------------
def test_3_loitering_below_threshold():
    """Verify that a person dwelling in a zone for duration < threshold triggers no loitering event."""
    engine = SuspiciousActivityEngine(camera_id=1, loitering_threshold_sec=30.0)
    zone = make_zone(2, "Monitoring Zone B", ZoneType.MONITORING, [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]])
    zones = [zone]
    trk = make_track(track_id=103, object_type="person", bbox=[300, 300, 350, 400], current_zone="Monitoring Zone B", confidence=0.91)
    
    # Start dwelling at t=50.0
    activities = engine.process(
        tracks=[trk],
        zones=zones,
        zone_candidates=[],
        frame_time=50.0,
    )
    assert len(activities) == 0
    
    # Dwell at t=79.9 (29.9s dwell < 30.0s threshold)
    activities = engine.process(
        tracks=[trk],
        zones=zones,
        zone_candidates=[],
        frame_time=79.9,
    )
    assert len(activities) == 0
    
    active_states = engine.get_active_loitering_states()
    assert len(active_states) == 1
    assert active_states[0]["track_id"] == 103
    assert active_states[0]["triggered"] is False
    assert abs(active_states[0]["current_duration_sec"] - 29.9) < 0.1


# ------------------------------------------------------------------------------
# Test 4: Loitering At Threshold
# ------------------------------------------------------------------------------
def test_4_loitering_at_threshold():
    """Verify that a person dwelling in a zone for duration >= threshold triggers exactly one loitering event."""
    engine = SuspiciousActivityEngine(camera_id=1, loitering_threshold_sec=30.0)
    zone = make_zone(3, "Restricted Vault", ZoneType.RESTRICTED, [[0.0, 0.0], [0.8, 0.0], [0.8, 0.8], [0.0, 0.8]])
    zones = [zone]
    trk = make_track(track_id=104, object_type="person", bbox=[200, 200, 250, 300], current_zone="Restricted Vault", confidence=0.94)
    
    # Entry at t=100.0
    engine.process(
        tracks=[trk],
        zones=zones,
        zone_candidates=[],
        frame_time=100.0,
    )
    
    # Threshold reached at t=130.0 (30.0s duration)
    activities = engine.process(
        tracks=[trk],
        zones=zones,
        zone_candidates=[],
        frame_time=130.0,
    )
    
    assert len(activities) == 1
    act = activities[0]
    assert act.event_type == ActivityType.LOITERING.value
    assert act.severity == ActivitySeverity.HIGH.value
    assert act.track_id == 104
    assert act.zone_id == 3
    assert act.duration_sec == 30.0
    assert "Restricted Vault" in act.reason
    assert "30 seconds" in act.reason
    
    active_states = engine.get_active_loitering_states()
    assert active_states[0]["triggered"] is True


# ------------------------------------------------------------------------------
# Test 5: Loitering No Flood
# ------------------------------------------------------------------------------
def test_5_loitering_no_flood():
    """Verify that continued dwell past threshold does not generate flood / duplicate candidates per frame."""
    engine = SuspiciousActivityEngine(camera_id=1, loitering_threshold_sec=30.0)
    zone = make_zone(1, "Gate Zone", ZoneType.RESTRICTED, [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    zones = [zone]
    trk = make_track(track_id=105, object_type="person", bbox=[200, 200, 250, 300], current_zone="Gate Zone", confidence=0.90)
    
    # t=0.0 entry
    engine.process(tracks=[trk], zones=zones, zone_candidates=[], frame_time=0.0)
    # t=30.0 trigger
    first_acts = engine.process(tracks=[trk], zones=zones, zone_candidates=[], frame_time=30.0)
    assert len(first_acts) == 1
    
    # Next timestamps from t=30.1 to t=100.0
    for t in [30.1, 31.0, 35.0, 40.0, 50.0, 75.0, 100.0]:
        subsequent_acts = engine.process(tracks=[trk], zones=zones, zone_candidates=[], frame_time=t)
        assert len(subsequent_acts) == 0, f"Loitering flooded at t={t}"


# ------------------------------------------------------------------------------
# Test 6: Exit Reset
# ------------------------------------------------------------------------------
def test_6_loitering_exit_reset():
    """Verify that when a person leaves a zone, the dwell timer resets, and re-entry starts a fresh timer."""
    engine = SuspiciousActivityEngine(camera_id=1, loitering_threshold_sec=30.0)
    zone = make_zone(1, "Gate Zone", ZoneType.RESTRICTED, [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    zones = [zone]
    trk_inside = make_track(track_id=106, object_type="person", bbox=[200, 200, 250, 300], current_zone="Gate Zone", confidence=0.90)
    trk_outside = make_track(track_id=106, object_type="person", bbox=[200, 200, 250, 300], current_zone=None, confidence=0.90)
    
    # Episode 1: Dwell and trigger
    engine.process(tracks=[trk_inside], zones=zones, zone_candidates=[], frame_time=0.0)
    act1 = engine.process(tracks=[trk_inside], zones=zones, zone_candidates=[], frame_time=30.0)
    assert len(act1) == 1
    
    # Person exits at t=35.0
    engine.process(tracks=[trk_outside], zones=zones, zone_candidates=[], frame_time=35.0)
    assert len(engine.get_active_loitering_states()) == 0
    
    # Person re-enters at t=50.0
    engine.process(tracks=[trk_inside], zones=zones, zone_candidates=[], frame_time=50.0)
    
    # At t=70.0 (dwell=20.0s < 30.0s), no event
    act_mid = engine.process(tracks=[trk_inside], zones=zones, zone_candidates=[], frame_time=70.0)
    assert len(act_mid) == 0
    
    # At t=80.0 (dwell=30.0s >= 30.0s), second loitering trigger fires
    act2 = engine.process(tracks=[trk_inside], zones=zones, zone_candidates=[], frame_time=80.0)
    assert len(act2) == 1
    assert act2[0].event_type == ActivityType.LOITERING.value
    assert act2[0].duration_sec == 30.0


# ------------------------------------------------------------------------------
# Test 7: Track Loss Cleanup
# ------------------------------------------------------------------------------
def test_7_loitering_track_loss_cleanup():
    """Verify that when a track is lost or disappears, internal dwell tracking state is cleaned up."""
    engine = SuspiciousActivityEngine(camera_id=1, loitering_threshold_sec=30.0)
    zone = make_zone(1, "Gate Zone", ZoneType.RESTRICTED, [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    zones = [zone]
    trk = make_track(track_id=107, object_type="person", bbox=[200, 200, 250, 300], current_zone="Gate Zone", confidence=0.90)
    
    # Dwell at t=10.0 and t=20.0
    engine.process(tracks=[trk], zones=zones, zone_candidates=[], frame_time=10.0)
    engine.process(tracks=[trk], zones=zones, zone_candidates=[], frame_time=20.0)
    assert len(engine.get_active_loitering_states()) == 1
    
    # Track disappears (empty tracks list)
    engine.process(tracks=[], zones=zones, zone_candidates=[], frame_time=21.0)
    assert len(engine.get_active_loitering_states()) == 0


# ------------------------------------------------------------------------------
# Test 8: Multiple People Independent Evaluation
# ------------------------------------------------------------------------------
def test_8_multiple_people_independent_evaluation():
    """Verify that multiple tracks dwelling in a zone are tracked independently and trigger at their own timestamps."""
    engine = SuspiciousActivityEngine(camera_id=1, loitering_threshold_sec=30.0)
    zone = make_zone(1, "Compound Area", ZoneType.RESTRICTED, [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    zones = [zone]
    
    p1 = make_track(track_id=1, object_type="person", bbox=[100, 100, 150, 200], current_zone="Compound Area")
    p2 = make_track(track_id=2, object_type="person", bbox=[300, 300, 350, 400], current_zone="Compound Area")
    
    # p1 enters at t=0.0
    engine.process(tracks=[p1], zones=zones, zone_candidates=[], frame_time=0.0)
    
    # p2 enters at t=15.0
    engine.process(tracks=[p1, p2], zones=zones, zone_candidates=[], frame_time=15.0)
    
    # At t=30.0: p1 hits 30s (triggers), p2 is at 15s (no trigger)
    acts_t30 = engine.process(tracks=[p1, p2], zones=zones, zone_candidates=[], frame_time=30.0)
    assert len(acts_t30) == 1
    assert acts_t30[0].track_id == 1
    
    # At t=45.0: p2 hits 30s (triggers), p1 is at 45s (no duplicate flood)
    acts_t45 = engine.process(tracks=[p1, p2], zones=zones, zone_candidates=[], frame_time=45.0)
    assert len(acts_t45) == 1
    assert acts_t45[0].track_id == 2


# ------------------------------------------------------------------------------
# Test 9: Multiple Zones Transition
# ------------------------------------------------------------------------------
def test_9_multiple_zones_transition():
    """Verify person moving from Zone A to Zone B resets Zone A timer and begins Zone B timer with appropriate severity."""
    engine = SuspiciousActivityEngine(camera_id=1, loitering_threshold_sec=30.0)
    zone_a = make_zone(1, "Restricted Zone A", ZoneType.RESTRICTED, [[0.0, 0.0], [0.4, 0.4], [0.4, 0.4], [0.0, 0.4]])
    zone_b = make_zone(2, "Monitoring Zone B", ZoneType.MONITORING, [[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]])
    zones = [zone_a, zone_b]
    
    trk_za = make_track(track_id=109, object_type="person", bbox=[100, 100, 150, 200], current_zone="Restricted Zone A")
    trk_zb = make_track(track_id=109, object_type="person", bbox=[100, 100, 150, 200], current_zone="Monitoring Zone B")
    
    # 20 seconds in Zone A
    engine.process(tracks=[trk_za], zones=zones, zone_candidates=[], frame_time=0.0)
    engine.process(tracks=[trk_za], zones=zones, zone_candidates=[], frame_time=20.0)
    
    # Moves directly to Zone B at t=25.0
    engine.process(tracks=[trk_zb], zones=zones, zone_candidates=[], frame_time=25.0)
    active = engine.get_active_loitering_states()
    assert len(active) == 1
    assert active[0]["zone_id"] == 2
    assert active[0]["current_duration_sec"] == 0.0
    
    # Reaches 30s in Zone B at t=55.0
    acts = engine.process(tracks=[trk_zb], zones=zones, zone_candidates=[], frame_time=55.0)
    assert len(acts) == 1
    assert acts[0].event_type == ActivityType.LOITERING.value
    assert acts[0].severity == ActivitySeverity.WARNING.value  # MONITORING zone = WARNING
    assert acts[0].zone_id == 2


# ------------------------------------------------------------------------------
# Test 10: Multiple Cameras Isolation
# ------------------------------------------------------------------------------
def test_10_multiple_cameras_isolation():
    """Verify that multiple SuspiciousActivityEngine instances on different cameras isolate state and events."""
    engine_cam1 = SuspiciousActivityEngine(camera_id=1, loitering_threshold_sec=30.0)
    engine_cam2 = SuspiciousActivityEngine(camera_id=2, loitering_threshold_sec=30.0)
    
    zone_c1 = make_zone(1, "Cam 1 Restricted", ZoneType.RESTRICTED, [[0.0, 0.0], [1.0, 1.0]], camera_id=1)
    zone_c2 = make_zone(2, "Cam 2 Restricted", ZoneType.RESTRICTED, [[0.0, 0.0], [1.0, 1.0]], camera_id=2)
    
    trk1 = make_track(track_id=1, object_type="person", bbox=[100, 100, 150, 200], current_zone="Cam 1 Restricted")
    trk2 = make_track(track_id=1, object_type="person", bbox=[100, 100, 150, 200], current_zone="Cam 2 Restricted")
    
    engine_cam1.process(tracks=[trk1], zones=[zone_c1], zone_candidates=[], frame_time=0.0)
    engine_cam2.process(tracks=[trk2], zones=[zone_c2], zone_candidates=[], frame_time=20.0)
    
    # At t=30.0: Cam 1 fires, Cam 2 does not (only 10s dwell)
    acts1 = engine_cam1.process(tracks=[trk1], zones=[zone_c1], zone_candidates=[], frame_time=30.0)
    acts2 = engine_cam2.process(tracks=[trk2], zones=[zone_c2], zone_candidates=[], frame_time=30.0)
    
    assert len(acts1) == 1
    assert acts1[0].camera_id == 1
    assert len(acts2) == 0


# ------------------------------------------------------------------------------
# Test 11: Threshold Configuration
# ------------------------------------------------------------------------------
def test_11_threshold_configuration():
    """Verify that loitering threshold can be dynamically reconfigured and is strictly respected."""
    engine = SuspiciousActivityEngine(camera_id=1, loitering_threshold_sec=15.0)
    zone = make_zone(1, "Short Dwell Zone", ZoneType.RESTRICTED, [[0.0, 0.0], [1.0, 1.0]])
    zones = [zone]
    trk = make_track(track_id=111, object_type="person", bbox=[100, 100, 150, 200], current_zone="Short Dwell Zone")
    
    engine.process(tracks=[trk], zones=zones, zone_candidates=[], frame_time=0.0)
    
    # At t=14.9: no trigger
    acts_14 = engine.process(tracks=[trk], zones=zones, zone_candidates=[], frame_time=14.9)
    assert len(acts_14) == 0
    
    # At t=15.0: triggers loitering candidate
    acts_15 = engine.process(tracks=[trk], zones=zones, zone_candidates=[], frame_time=15.0)
    assert len(acts_15) == 1
    assert acts_15[0].duration_sec == 15.0


# ------------------------------------------------------------------------------
# Test 12: Full Sample Video Regression & API Integration
# ------------------------------------------------------------------------------
def test_12_full_sample_video_regression(client):
    """Verify that Suspicious Activity Detection runs in the CameraWorker pipeline and exposes working API endpoints."""
    demo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "demo"))
    demo_path = os.path.join(demo_dir, "sample_cctv.mp4")
    if not os.path.exists(demo_path):
        demo_path = os.path.join(demo_dir, "toll_cctv.mp4")
    if not os.path.exists(demo_path):
        pytest.skip("Sample video in data/demo not found")

    # Add a camera and a restricted zone in DB
    db = SessionLocal()
    db.query(Camera).filter(Camera.name == "Activity Test Cam").delete()
    db.commit()
    
    test_cam = Camera(
        name="Activity Test Cam",
        source_type="VIDEO_FILE",
        source_uri=demo_path,
        enabled=True,
    )
    db.add(test_cam)
    db.commit()
    db.refresh(test_cam)
    cam_id = test_cam.id

    test_zone = Zone(
        camera_id=cam_id,
        name="Border Patrol Zone",
        zone_type="RESTRICTED",
        polygon_json=json.dumps([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]),
        enabled=True,
    )
    db.add(test_zone)
    db.commit()
    db.close()

    # Create worker and start
    worker = CameraWorker(
        camera_id=cam_id,
        camera_name="Activity Test Cam",
        source_type="VIDEO_FILE",
        source_uri=demo_path,
        loop=True,
        enable_detection=True,
        enable_tracking=True,
        enable_anpr=False,
    )
    
    # Ensure loitering threshold is set
    worker.set_loitering_threshold(2.0)
    worker.start()
    time.sleep(2.0)

    status = worker.get_status_info()
    worker.stop()
    
    assert "activities" in status
    assert "active_loitering" in status
    assert "activity_latency_ms" in status
    assert "RuleEngine" in status["activity_engine"]
    assert isinstance(status["activities"], list)
    assert isinstance(status["active_loitering"], list)

    # Test API Endpoints
    # 1. GET /api/cameras/{id}/activities
    resp = client.get(f"/api/cameras/{cam_id}/activities")
    assert resp.status_code == 200
    data = resp.json()
    assert "activities" in data
    assert "active_loitering" in data
    assert data["camera_id"] == cam_id

    # 2. GET /api/system/analytics
    resp_analytics = client.get("/api/system/analytics")
    assert resp_analytics.status_code == 200
    analytics_data = resp_analytics.json()
    assert "loitering_threshold_sec" in analytics_data

    # 3. PATCH /api/system/analytics
    resp_patch = client.patch("/api/system/analytics", json={"loitering_threshold_sec": 20.0})
    assert resp_patch.status_code == 200
    assert resp_patch.json()["loitering_threshold_sec"] == 20.0
    
    # Clean up
    db = SessionLocal()
    db.query(Zone).filter(Zone.camera_id == cam_id).delete()
    db.query(Camera).filter(Camera.id == cam_id).delete()
    db.commit()
    db.close()

