# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: tests.test_night_movement
# Description: 16 comprehensive automated tests for Phase 8 Night-Time Movement Detection.
# License: Apache-2.0
# ==============================================================================

import os
import time
import pytest
from datetime import datetime, time as dt_time, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import init_db, SessionLocal
from app.models.schema import Camera, Zone
from app.services.tracking.tracker import Track, TrackState
from app.services.zone.models import ZoneType, ZoneDefinition, IntrusionEventCandidate
from app.services.rules.models import ActivityType, ActivitySeverity, SuspiciousActivityCandidate
from app.services.rules.night import NightMovementRule, parse_time_str, is_time_in_window
from app.services.rules.engine import SuspiciousActivityEngine
from app.services.video.worker import CameraWorker
from app.services.video.manager import camera_manager


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as test_client:
        yield test_client


def make_track(track_id: int, object_type: str, bbox: list = None, confidence: float = 0.90, current_zone: str = None) -> Track:
    if bbox is None:
        bbox = [100, 100, 150, 200]
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
        first_seen="2026-09-11T23:00:00Z",
        last_seen="2026-09-11T23:00:01Z",
        state=TrackState.ACTIVE,
        hits=10,
        age=10,
        current_zone=current_zone,
    )


# ------------------------------------------------------------------------------
# Test 1: Same-Day Window Inside (18:00 -> 23:00 at 21:00)
# ------------------------------------------------------------------------------
def test_1_same_day_window_inside():
    """Verify that a timestamp inside a same-day window (18:00->23:00 at 21:00) evaluates to True."""
    start_t = dt_time(18, 0)
    end_t = dt_time(23, 0)
    curr_t = dt_time(21, 0)
    
    assert is_time_in_window(curr_t, start_t, end_t) is True


# ------------------------------------------------------------------------------
# Test 2: Same-Day Window Outside (18:00 -> 23:00 at 01:00)
# ------------------------------------------------------------------------------
def test_2_same_day_window_outside():
    """Verify that a timestamp outside a same-day window (18:00->23:00 at 01:00) evaluates to False."""
    start_t = dt_time(18, 0)
    end_t = dt_time(23, 0)
    curr_t = dt_time(1, 0)
    
    assert is_time_in_window(curr_t, start_t, end_t) is False


# ------------------------------------------------------------------------------
# Test 3: Midnight-Crossing Inside Before Midnight (22:00 -> 05:00 at 23:30)
# ------------------------------------------------------------------------------
def test_3_midnight_crossing_inside_before_midnight():
    """Verify that 23:30 is inside a midnight-crossing window (22:00 -> 05:00)."""
    start_t = dt_time(22, 0)
    end_t = dt_time(5, 0)
    curr_t = dt_time(23, 30)
    
    assert is_time_in_window(curr_t, start_t, end_t) is True


# ------------------------------------------------------------------------------
# Test 4: Midnight-Crossing Inside After Midnight (22:00 -> 05:00 at 02:30)
# ------------------------------------------------------------------------------
def test_4_midnight_crossing_inside_after_midnight():
    """Verify that 02:30 is inside a midnight-crossing window (22:00 -> 05:00)."""
    start_t = dt_time(22, 0)
    end_t = dt_time(5, 0)
    curr_t = dt_time(2, 30)
    
    assert is_time_in_window(curr_t, start_t, end_t) is True


# ------------------------------------------------------------------------------
# Test 5: Midnight-Crossing Outside (22:00 -> 05:00 at 12:00)
# ------------------------------------------------------------------------------
def test_5_midnight_crossing_outside():
    """Verify that midday (12:00) is outside a midnight-crossing window (22:00 -> 05:00)."""
    start_t = dt_time(22, 0)
    end_t = dt_time(5, 0)
    curr_t = dt_time(12, 0)
    
    assert is_time_in_window(curr_t, start_t, end_t) is False


# ------------------------------------------------------------------------------
# Test 6: Start Boundary Policy (Start Time is Inclusive)
# ------------------------------------------------------------------------------
def test_6_start_boundary_inclusive():
    """Verify that the exact start_time (22:00:00) is treated as INSIDE the window."""
    start_t = dt_time(22, 0)
    end_t = dt_time(5, 0)
    curr_t = dt_time(22, 0)
    
    assert is_time_in_window(curr_t, start_t, end_t) is True


# ------------------------------------------------------------------------------
# Test 7: End Boundary Policy (End Time is Exclusive)
# ------------------------------------------------------------------------------
def test_7_end_boundary_exclusive():
    """Verify that the exact end_time (05:00:00) is treated as OUTSIDE the window."""
    start_t = dt_time(22, 0)
    end_t = dt_time(5, 0)
    curr_t = dt_time(5, 0)
    
    assert is_time_in_window(curr_t, start_t, end_t) is False


# ------------------------------------------------------------------------------
# Test 8: Night Movement Disabled Configuration
# ------------------------------------------------------------------------------
def test_8_night_movement_disabled():
    """Verify that when night_movement_enabled is False, no candidates are emitted even during the window."""
    rule = NightMovementRule(camera_id=1, enabled=False, start_time_str="22:00", end_time_str="05:00")
    trk = make_track(track_id=1, object_type="person")
    
    # Evaluate at 23:30 (inside window)
    candidates = rule.evaluate(tracks=[trk], current_dt_time=dt_time(23, 30))
    assert len(candidates) == 0


# ------------------------------------------------------------------------------
# Test 9: Person Detected in Night Window
# ------------------------------------------------------------------------------
def test_9_person_detected_in_window():
    """Verify that a person track detected inside the night window generates a valid NIGHT_MOVEMENT candidate."""
    engine = SuspiciousActivityEngine(
        camera_id=1,
        night_movement_enabled=True,
        night_start_time="22:00",
        night_end_time="05:00",
        night_cooldown_sec=60.0,
    )
    
    trk = make_track(track_id=10, object_type="person", confidence=0.94)
    candidates = engine.process_frame(
        tracks=[trk],
        zones=[],
        intrusion_candidates=[],
        current_dt_time=dt_time(23, 15),
    )
    
    night_candidates = [c for c in candidates if c.event_type == ActivityType.NIGHT_MOVEMENT]
    assert len(night_candidates) == 1
    c = night_candidates[0]
    assert c.camera_id == 1
    assert c.track_id == 10
    assert c.object_type == "person"
    assert c.severity == ActivitySeverity.WARNING
    assert c.confidence == 0.94
    assert "Person detected during configured night-time period." in c.reason


# ------------------------------------------------------------------------------
# Test 10: Vehicle Detected in Night Window
# ------------------------------------------------------------------------------
def test_10_vehicle_detected_in_window():
    """Verify that a vehicle track (car/truck/bus/motorcycle) detected inside the night window generates a candidate."""
    engine = SuspiciousActivityEngine(
        camera_id=2,
        night_movement_enabled=True,
        night_start_time="20:00",
        night_end_time="06:00",
    )
    
    for v_type in ["car", "truck", "bus", "motorcycle"]:
        trk = make_track(track_id=20 + hash(v_type) % 100, object_type=v_type, confidence=0.88)
        candidates = engine.process_frame(
            tracks=[trk],
            zones=[],
            intrusion_candidates=[],
            current_dt_time=dt_time(22, 0),
        )
        night_candidates = [c for c in candidates if c.event_type == ActivityType.NIGHT_MOVEMENT]
        assert len(night_candidates) == 1
        assert night_candidates[0].object_type == v_type
        assert "Vehicle detected during configured night-time period." in night_candidates[0].reason


# ------------------------------------------------------------------------------
# Test 11: Duplicate Suppression Cooldown
# ------------------------------------------------------------------------------
def test_11_duplicate_suppression_cooldown():
    """Verify that continuous detections of the same track within cooldown are suppressed."""
    rule = NightMovementRule(camera_id=1, enabled=True, start_time_str="22:00", end_time_str="05:00", cooldown_sec=10.0)
    trk = make_track(track_id=30, object_type="person")
    
    # Frame 1: Generates candidate
    c1 = rule.evaluate(tracks=[trk], current_dt_time=dt_time(23, 0), current_time_epoch=1000.0)
    assert len(c1) == 1
    
    # Frame 2 (2s later): Suppressed
    c2 = rule.evaluate(tracks=[trk], current_dt_time=dt_time(23, 0), current_time_epoch=1002.0)
    assert len(c2) == 0
    
    # Frame 3 (9.9s later): Still suppressed
    c3 = rule.evaluate(tracks=[trk], current_dt_time=dt_time(23, 0), current_time_epoch=1009.9)
    assert len(c3) == 0
    
    # Frame 4 (11s later): Cooldown expired, generates new candidate
    c4 = rule.evaluate(tracks=[trk], current_dt_time=dt_time(23, 0), current_time_epoch=1011.0)
    assert len(c4) == 1


# ------------------------------------------------------------------------------
# Test 12: New Track Produces Candidate
# ------------------------------------------------------------------------------
def test_12_new_track_produces_candidate():
    """Verify that multiple distinct tracks independently trigger candidates."""
    rule = NightMovementRule(camera_id=1, enabled=True, start_time_str="22:00", end_time_str="05:00")
    trk_a = make_track(track_id=41, object_type="person")
    trk_b = make_track(track_id=42, object_type="car")
    
    candidates = rule.evaluate(tracks=[trk_a, trk_b], current_dt_time=dt_time(1, 30))
    assert len(candidates) == 2
    track_ids = {c.track_id for c in candidates}
    assert track_ids == {41, 42}


# ------------------------------------------------------------------------------
# Test 13: Zone Intrusion and Night Movement Coexistence
# ------------------------------------------------------------------------------
def test_13_zone_combination_coexistence():
    """Verify that a track inside a restricted zone produces both ZONE_INTRUSION and NIGHT_MOVEMENT candidates."""
    engine = SuspiciousActivityEngine(
        camera_id=1,
        night_movement_enabled=True,
        night_start_time="22:00",
        night_end_time="05:00",
    )
    
    trk = make_track(track_id=50, object_type="person", current_zone="Vault Area")
    intrusion_candidate = IntrusionEventCandidate(
        event_type="ZONE_INTRUSION",
        camera_id=1,
        zone_id=10,
        zone_name="Vault Area",
        zone_type="RESTRICTED",
        track_id=50,
        object_type="person",
        anchor_point=[125, 200],
        confidence=0.95,
        reason="Person entered RESTRICTED zone Vault Area",
        timestamp="2026-09-11T23:45:00Z",
    )
    
    all_candidates = engine.process_frame(
        tracks=[trk],
        zones=[],
        intrusion_candidates=[intrusion_candidate],
        current_dt_time=dt_time(23, 45),
    )
    
    event_types = [c.event_type for c in all_candidates]
    assert ActivityType.ZONE_INTRUSION in event_types
    assert ActivityType.NIGHT_MOVEMENT in event_types
    assert len(all_candidates) == 2


# ------------------------------------------------------------------------------
# Test 14: Dynamic Configuration Change
# ------------------------------------------------------------------------------
def test_14_configuration_change_dynamic():
    """Verify that dynamic changes to night movement parameters via API / engine method take effect immediately."""
    engine = SuspiciousActivityEngine(
        camera_id=1,
        night_movement_enabled=False,
        night_start_time="22:00",
        night_end_time="05:00",
    )
    
    trk = make_track(track_id=60, object_type="person")
    
    # Disabled -> no candidates
    c1 = engine.process_frame(tracks=[trk], zones=[], intrusion_candidates=[], current_dt_time=dt_time(23, 0))
    assert len(c1) == 0
    
    # Enable dynamically
    engine.set_night_movement_config(enabled=True, start_time="20:00", end_time="04:00", cooldown_sec=30.0)
    
    # Now enabled -> candidate generated
    c2 = engine.process_frame(tracks=[trk], zones=[], intrusion_candidates=[], current_dt_time=dt_time(21, 0))
    assert len(c2) == 1
    assert c2[0].event_type == ActivityType.NIGHT_MOVEMENT


# ------------------------------------------------------------------------------
# Test 15: Invalid Time Format Validation
# ------------------------------------------------------------------------------
def test_15_invalid_time_format_validation(client):
    """Verify that invalid time formats are rejected with a 422 Unprocessable Entity error by the API."""
    # Test invalid start_time format
    res1 = client.patch("/api/system/analytics", json={"night_start_time": "25:00"})
    assert res1.status_code == 422
    
    res2 = client.patch("/api/system/analytics", json={"night_end_time": "invalid_time"})
    assert res2.status_code == 422
    
    # Test helper parser ValueError
    with pytest.raises(ValueError):
        parse_time_str("99:99")
        
    with pytest.raises(ValueError):
        parse_time_str("12:65")
        
    # Valid time passes
    t = parse_time_str("22:30")
    assert t == dt_time(22, 30)


# ------------------------------------------------------------------------------
# Test 16: CameraWorker Full Pipeline Regression
# ------------------------------------------------------------------------------
def test_16_camera_worker_full_pipeline_regression():
    """Verify that CameraWorker initializes and executes with Night Movement rule enabled."""
    worker = CameraWorker(
        camera_id=99,
        camera_name="Test Regression Camera",
        source_type="VIDEO_FILE",
        source_uri="./data/demo/sample_cctv.mp4",
    )
    
    assert hasattr(worker, "activity_engine")
    assert worker.activity_engine.night_rule is not None
    assert worker.activity_engine.night_rule.enabled is True
    
    # Update config on worker
    worker.set_night_movement_config(enabled=True, start_time="21:00", end_time="06:00", cooldown_sec=45.0)
    assert worker.activity_engine.night_rule.start_time == dt_time(21, 0)
    assert worker.activity_engine.night_rule.end_time == dt_time(6, 0)
    assert worker.activity_engine.night_rule.cooldown_sec == 45.0
