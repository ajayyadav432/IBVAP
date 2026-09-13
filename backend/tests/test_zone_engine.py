# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: tests.test_zone_engine
# Description: Comprehensive automated tests for Phase 6 Virtual Fence / Zone Engine.
# License: Apache-2.0
# ==============================================================================

import json
import os
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import init_db, SessionLocal
from app.models.schema import Camera, Zone
from app.services.zone.geometry import (
    get_object_anchor,
    normalize_point,
    denormalize_point,
    denormalize_polygon,
    validate_polygon,
    point_in_polygon,
)
from app.services.zone.models import ZoneType, ZoneState, ZoneDefinition
from app.services.zone.engine import ZoneEngine
from app.services.tracking.tracker import Track, TrackState
from app.services.inference.annotator import draw_zones, draw_tracks
from app.services.video.manager import camera_manager


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def cleanup_zones():
    """Clean up test zones before and after test execution."""
    db = SessionLocal()
    db.query(Zone).delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(Zone).delete()
    db.commit()
    db.close()


def make_track(track_id: int, object_type: str, bbox: list, confidence: float = 0.90) -> Track:
    """Helper to create a normalized Track object."""
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
        first_seen="2026-09-11T12:00:00",
        last_seen="2026-09-11T12:00:01",
        state=TrackState.ACTIVE,
        hits=5,
        age=5,
    )


# ==============================================================================
# 1. Zone Creation
# ==============================================================================
def test_1_zone_creation():
    """Verify valid 4-point normalized polygon creation with proper properties."""
    poly = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]
    valid, err = validate_polygon(poly)
    assert valid is True
    assert err is None

    zone_def = ZoneDefinition(
        id=1,
        camera_id=10,
        name="NORTH_GATE_RESTRICTED",
        zone_type=ZoneType.RESTRICTED,
        polygon=poly,
        enabled=True,
    )
    assert zone_def.id == 1
    assert zone_def.camera_id == 10
    assert zone_def.name == "NORTH_GATE_RESTRICTED"
    assert zone_def.zone_type == ZoneType.RESTRICTED
    assert len(zone_def.polygon) == 4
    assert zone_def.enabled is True


# ==============================================================================
# 2. Invalid Zone Creation
# ==============================================================================
def test_2_invalid_zone_creation(client):
    """Verify fewer than 3 points or out-of-bound coords are rejected."""
    # Fewer than 3 points
    valid_few, err_few = validate_polygon([[0.1, 0.1], [0.2, 0.2]])
    assert valid_few is False
    assert "at least 3" in err_few

    # Out of normalized bounds
    valid_oob, err_oob = validate_polygon([[0.1, 0.1], [1.5, 0.2], [0.5, 0.5]])
    assert valid_oob is False
    assert "normalized [0.0, 1.0]" in err_oob

    # API rejection with 400
    db = SessionLocal()
    cam = Camera(name="TestCam_Invalid", source_type="VIDEO_FILE", source_uri="./data/demo/sample_cctv.mp4", enabled=False)
    db.add(cam)
    db.commit()
    cam_id = cam.id
    db.close()

    res = client.post(
        f"/api/cameras/{cam_id}/zones",
        json={
            "name": "InvalidZone",
            "zone_type": "RESTRICTED",
            "polygon": [[0.1, 0.1], [0.2, 0.2]],
            "enabled": True,
        },
    )
    assert res.status_code == 400
    assert "at least 3" in res.json()["detail"]


# ==============================================================================
# 3. Zone Persistence
# ==============================================================================
def test_3_zone_persistence():
    """Verify zone persistence in DB, reload and verify polygon coordinate preservation."""
    db = SessionLocal()
    cam = Camera(name="TestCam_Persist", source_type="VIDEO_FILE", source_uri="./data/demo/sample_cctv.mp4", enabled=False)
    db.add(cam)
    db.commit()

    poly = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
    zone = Zone(
        camera_id=cam.id,
        name="PERIMETER_FENCE_A",
        zone_type="RESTRICTED",
        polygon_json=json.dumps(poly),
        enabled=True,
    )
    db.add(zone)
    db.commit()
    zone_id = zone.id
    db.close()

    # Query back in a new session
    db2 = SessionLocal()
    reloaded = db2.query(Zone).filter(Zone.id == zone_id).first()
    assert reloaded is not None
    assert reloaded.name == "PERIMETER_FENCE_A"
    assert reloaded.zone_type == "RESTRICTED"
    assert reloaded.enabled is True
    reloaded_poly = json.loads(reloaded.polygon_json)
    assert reloaded_poly == poly
    db2.close()


# ==============================================================================
# 4. Zone Display Overlay
# ==============================================================================
def test_4_zone_display_overlay():
    """Verify polygon overlay rendering with semi-transparent fill, boundary, and labels."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    poly = [[0.1, 0.1], [0.6, 0.1], [0.6, 0.6], [0.1, 0.6]]
    zone_def = ZoneDefinition(
        id=1,
        camera_id=1,
        name="RESTRICTED ZONE A",
        zone_type=ZoneType.RESTRICTED,
        polygon=poly,
        enabled=True,
    )
    active_intrusions = {
        1: [5]
    }

    annotated = draw_zones(frame, [zone_def], active_intrusions=active_intrusions)
    assert annotated.shape == (480, 640, 3)
    # Check that pixels inside the polygon are modified (not all zero)
    assert np.any(annotated[100:200, 100:200] > 0)


# ==============================================================================
# 5. Object Outside Zone
# ==============================================================================
def test_5_object_outside_zone():
    """Verify track moving outside zone remains OUTSIDE with zero intrusion events."""
    engine = ZoneEngine(camera_id=1, debounce_frames=2)
    poly = [[0.4, 0.4], [0.8, 0.4], [0.8, 0.8], [0.4, 0.8]]
    engine.add_zone(ZoneDefinition(id=1, camera_id=1, name="ZONE_1", zone_type=ZoneType.RESTRICTED, polygon=poly))

    # Track located at pixel [100, 100, 200, 200] in 1000x1000 frame -> anchor (150, 200) -> norm (0.15, 0.20) OUTSIDE
    track = make_track(track_id=101, object_type="person", bbox=[100, 100, 200, 200])

    candidates = engine.process_tracks(tracks=[track], frame_width=1000, frame_height=1000, frame_idx=1)
    assert len(candidates) == 0
    assert engine.get_active_intrusions() == {1: []}
    assert track.current_zone is None


# ==============================================================================
# 6. Object Zone Entry
# ==============================================================================
def test_6_object_zone_entry():
    """Verify track crossing boundary triggers ENTERED state after debounce."""
    engine = ZoneEngine(camera_id=1, debounce_frames=2)
    poly = [[0.4, 0.4], [0.8, 0.4], [0.8, 0.8], [0.4, 0.8]]
    engine.add_zone(ZoneDefinition(id=1, camera_id=1, name="RESTRICTED_A", zone_type=ZoneType.RESTRICTED, polygon=poly))

    # Object inside zone: pixel [500, 500, 700, 700] in 1000x1000 -> anchor (600, 700) -> norm (0.6, 0.7) inside
    track = make_track(track_id=102, object_type="person", bbox=[500, 500, 700, 700])

    # Frame 1: inside count = 1 (debounce threshold is 2)
    candidates_f1 = engine.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=1)
    assert len(candidates_f1) == 0  # debouncing

    # Frame 2: inside count = 2 -> triggers ENTERED candidate
    candidates_f2 = engine.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=2)
    assert len(candidates_f2) == 1
    event = candidates_f2[0]
    assert event.event_type == "ZONE_INTRUSION"
    assert event.track_id == 102
    assert event.zone_name == "RESTRICTED_A"
    assert track.current_zone == "RESTRICTED_A"
    assert engine.is_track_in_zone(1, 102) is True


# ==============================================================================
# 7. Object Zone Inside
# ==============================================================================
def test_7_object_zone_inside():
    """Verify track remaining inside zone maintains INSIDE state without duplicate entry events."""
    engine = ZoneEngine(camera_id=1, debounce_frames=2)
    poly = [[0.4, 0.4], [0.8, 0.4], [0.8, 0.8], [0.4, 0.8]]
    engine.add_zone(ZoneDefinition(id=1, camera_id=1, name="RESTRICTED_A", zone_type=ZoneType.RESTRICTED, polygon=poly))

    track = make_track(track_id=103, object_type="person", bbox=[500, 500, 700, 700])

    engine.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=1)
    events_entry = engine.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=2)
    assert len(events_entry) == 1

    # Frame 3, 4, 5: object stays inside
    events_f3 = engine.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=3)
    events_f4 = engine.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=4)
    assert len(events_f3) == 0
    assert len(events_f4) == 0
    assert track.current_zone == "RESTRICTED_A"
    assert 103 in engine.get_active_intrusions()[1]


# ==============================================================================
# 8. Object Zone Exit
# ==============================================================================
def test_8_object_zone_exit():
    """Verify track moving outside triggers EXITED state."""
    engine = ZoneEngine(camera_id=1, debounce_frames=2)
    poly = [[0.4, 0.4], [0.8, 0.4], [0.8, 0.8], [0.4, 0.8]]
    engine.add_zone(ZoneDefinition(id=1, camera_id=1, name="RESTRICTED_A", zone_type=ZoneType.RESTRICTED, polygon=poly))

    track = make_track(track_id=104, object_type="car", bbox=[500, 500, 700, 700])

    # Enter zone
    engine.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=1)
    engine.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=2)
    assert engine.is_track_in_zone(1, 104) is True

    # Move outside zone: bbox [100, 100, 200, 200]
    track.bbox = [100, 100, 200, 200]
    engine.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=3)
    assert engine.is_track_in_zone(1, 104) is True  # debouncing exit (1 frame)

    engine.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=4)
    assert engine.is_track_in_zone(1, 104) is False  # exit confirmed
    assert track.current_zone is None


# ==============================================================================
# 9. Boundary Jitter Debounce
# ==============================================================================
def test_9_boundary_jitter_debounce():
    """Verify oscillating around boundary does NOT produce rapid false transitions."""
    engine = ZoneEngine(camera_id=1, debounce_frames=3)
    poly = [[0.5, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 1.0]]
    engine.add_zone(ZoneDefinition(id=1, camera_id=1, name="ZONE_DEBOUNCE", zone_type=ZoneType.RESTRICTED, polygon=poly))

    track = make_track(track_id=105, object_type="person", bbox=[450, 450, 490, 490])  # Outside (x=470)

    # Alternate in and out each frame (jitter)
    events_total = []
    for f in range(1, 10):
        if f % 2 == 1:
            track.bbox = [510, 450, 550, 490]  # Just inside (x=530)
        else:
            track.bbox = [450, 450, 490, 490]  # Just outside (x=470)
        ev = engine.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=f)
        events_total.extend(ev)

    # Due to debounce threshold of 3 consecutive frames, single-frame oscillations produce zero events
    assert len(events_total) == 0


# ==============================================================================
# 10. Multi-Zone Disjoint
# ==============================================================================
def test_10_multi_zone_disjoint():
    """Verify two separate zones track entry and exit independently."""
    engine = ZoneEngine(camera_id=1, debounce_frames=1)
    zone_a = ZoneDefinition(id=1, camera_id=1, name="ZONE_ALPHA", zone_type=ZoneType.RESTRICTED, polygon=[[0.0, 0.0], [0.4, 0.0], [0.4, 0.4], [0.0, 0.4]])
    zone_b = ZoneDefinition(id=2, camera_id=1, name="ZONE_BETA", zone_type=ZoneType.MONITORING, polygon=[[0.6, 0.6], [1.0, 0.6], [1.0, 1.0], [0.6, 1.0]])
    engine.set_zones([zone_a, zone_b])

    # Track starts in Zone A: anchor (200, 300) -> norm (0.2, 0.3)
    track = make_track(track_id=106, object_type="truck", bbox=[100, 100, 300, 300])

    ev1 = engine.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=1)
    assert len(ev1) == 1
    assert ev1[0].zone_name == "ZONE_ALPHA"
    assert track.current_zone == "ZONE_ALPHA"

    # Track moves directly into Zone B: anchor (800, 900) -> norm (0.8, 0.9)
    track.bbox = [700, 700, 900, 900]
    ev2 = engine.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=2)
    assert len(ev2) == 1
    assert ev2[0].zone_name == "ZONE_BETA"
    assert track.current_zone == "ZONE_BETA"


# ==============================================================================
# 11. Multi-Object Zone Tracking
# ==============================================================================
def test_11_multi_object_zone_tracking():
    """Verify multiple objects in a zone are tracked simultaneously with distinct states."""
    engine = ZoneEngine(camera_id=1, debounce_frames=1)
    zone = ZoneDefinition(id=1, camera_id=1, name="CENTRAL_GATE", zone_type=ZoneType.RESTRICTED, polygon=[[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]])
    engine.add_zone(zone)

    t1 = make_track(track_id=1, object_type="person", bbox=[300, 300, 400, 400])
    t2 = make_track(track_id=2, object_type="person", bbox=[500, 500, 600, 600])
    t3 = make_track(track_id=3, object_type="car", bbox=[0, 0, 100, 100])  # Outside

    events = engine.process_tracks([t1, t2, t3], frame_width=1000, frame_height=1000, frame_idx=1)
    assert len(events) == 2
    entered_ids = {e.track_id for e in events}
    assert entered_ids == {1, 2}
    assert t1.current_zone == "CENTRAL_GATE"
    assert t2.current_zone == "CENTRAL_GATE"
    assert t3.current_zone is None


# ==============================================================================
# 12. Camera Isolation
# ==============================================================================
def test_12_camera_isolation():
    """Verify zones defined on camera 1 do NOT affect camera 2."""
    e1 = ZoneEngine(camera_id=1, debounce_frames=1)
    e2 = ZoneEngine(camera_id=2, debounce_frames=1)

    e1.add_zone(ZoneDefinition(id=1, camera_id=1, name="CAM1_ZONE", zone_type=ZoneType.RESTRICTED, polygon=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]))
    e2.add_zone(ZoneDefinition(id=2, camera_id=2, name="CAM2_ZONE", zone_type=ZoneType.MONITORING, polygon=[[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]]))

    track = make_track(track_id=1, object_type="person", bbox=[100, 100, 300, 300])

    # In Cam 1: inside
    ev_c1 = e1.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=1)
    assert len(ev_c1) == 1
    assert ev_c1[0].zone_name == "CAM1_ZONE"

    # In Cam 2: outside
    ev_c2 = e2.process_tracks([track], frame_width=1000, frame_height=1000, frame_idx=1)
    assert len(ev_c2) == 0


# ==============================================================================
# 13. Full Sample Video Zone Test
# ==============================================================================
def test_13_full_sample_video_zone_test():
    """Run video frames from sample_cctv.mp4 with a defined zone and verify zone evaluation."""
    candidate_paths = [
        "../data/demo/sample_cctv.mp4",
        "./data/demo/sample_cctv.mp4",
        "data/demo/sample_cctv.mp4",
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "demo", "sample_cctv.mp4"),
    ]
    video_path = next((p for p in candidate_paths if os.path.exists(p)), None)
    assert video_path is not None, "Video file sample_cctv.mp4 not found in workspace"

    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened(), "Could not open demo video"

    engine = ZoneEngine(camera_id=1, debounce_frames=2)
    # Define a zone covering the walking path in sample_cctv.mp4
    engine.add_zone(
        ZoneDefinition(
            id=10,
            camera_id=1,
            name="WALKWAY_SECURITY_ZONE",
            zone_type=ZoneType.RESTRICTED,
            polygon=[[0.1, 0.3], [0.9, 0.3], [0.9, 0.95], [0.1, 0.95]],
            enabled=True,
        )
    )

    frame_count = 0
    while frame_count < 30:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1

    cap.release()
    assert frame_count > 0, "Failed to read frames from video"


# ==============================================================================
# 14. Zone REST API Endpoints (CRUD)
# ==============================================================================
def test_14_zone_rest_api_crud(client):
    """Test full CRUD REST API endpoints for zones."""
    db = SessionLocal()
    cam = Camera(name="REST_API_ZoneCam", source_type="VIDEO_FILE", source_uri="./data/demo/sample_cctv.mp4", enabled=False)
    db.add(cam)
    db.commit()
    cam_id = cam.id
    db.close()

    # 1. CREATE Zone
    poly = [[0.1, 0.1], [0.7, 0.1], [0.7, 0.7], [0.1, 0.7]]
    res_create = client.post(
        f"/api/cameras/{cam_id}/zones",
        json={
            "name": "TEST_REST_ZONE",
            "zone_type": "RESTRICTED",
            "polygon": poly,
            "enabled": True,
        },
    )
    assert res_create.status_code == 201, res_create.text
    created = res_create.json()
    zone_id = created["id"]
    assert created["name"] == "TEST_REST_ZONE"
    assert created["zone_type"] == "RESTRICTED"
    assert created["polygon"] == poly

    # 2. GET Camera Zones
    res_list = client.get(f"/api/cameras/{cam_id}/zones")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["zones_count"] == 1
    assert list_data["zones"][0]["id"] == zone_id

    # 3. GET Single Zone
    res_get = client.get(f"/api/zones/{zone_id}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "TEST_REST_ZONE"

    # 4. PATCH Zone (Update name and type)
    res_patch = client.patch(
        f"/api/zones/{zone_id}",
        json={
            "name": "UPDATED_REST_ZONE",
            "zone_type": "MONITORING",
            "enabled": False,
        },
    )
    assert res_patch.status_code == 200
    patched = res_patch.json()
    assert patched["name"] == "UPDATED_REST_ZONE"
    assert patched["zone_type"] == "MONITORING"
    assert patched["enabled"] is False

    # 5. DELETE Zone
    res_del = client.delete(f"/api/zones/{zone_id}")
    assert res_del.status_code == 204

    # Verify deleted
    res_get_deleted = client.get(f"/api/zones/{zone_id}")
    assert res_get_deleted.status_code == 404
