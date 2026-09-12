# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: tests.test_tracking
# Description: Automated test suite for Phase 3 ByteTrack tracking and lifecycle.
# License: Apache-2.0
# ==============================================================================

import pytest
import numpy as np
import cv2
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.services.inference.detector import Detection
from app.services.tracking.tracker import ByteTrackTracker, Track, TrackState, STrack
from app.services.tracking.kalman_filter import KalmanFilter
from app.services.tracking.matching import box_ious, iou_distance, linear_assignment

from app.core.config import settings

client = TestClient(app)
SAMPLE_CCTV_PATH = settings.DATA_DIR / "demo" / "sample_cctv.mp4"


@pytest.fixture(autouse=True)
def reset_strack_ids():
    """Ensure clean track IDs before each test execution."""
    STrack.reset_id()


def test_kalman_filter_init_predict_update():
    """Verify Kalman filter measurement projection and state transitions."""
    kf = KalmanFilter()
    measurement = np.array([100.0, 150.0, 0.5, 200.0], dtype=np.float32)
    mean, cov = kf.initiate(measurement)
    assert mean.shape == (8,)
    assert cov.shape == (8, 8)

    pred_mean, pred_cov = kf.predict(mean, cov)
    assert pred_mean.shape == (8,)

    # Small displacement update
    new_measurement = np.array([102.0, 152.0, 0.5, 200.0], dtype=np.float32)
    upd_mean, upd_cov = kf.update(pred_mean, pred_cov, new_measurement)
    assert upd_mean.shape == (8,)
    assert abs(upd_mean[0] - 102.0) < 10.0


def test_iou_calculation_and_matching():
    """Verify IoU calculation and bipartite matching."""
    box_a = np.array([[100, 100, 200, 200]], dtype=np.float32)
    box_b = np.array([[100, 100, 200, 200], [300, 300, 400, 400]], dtype=np.float32)
    
    ious = box_ious(box_a, box_b)
    assert ious.shape == (1, 2)
    assert np.isclose(ious[0, 0], 1.0)
    assert np.isclose(ious[0, 1], 0.0)

    cost_matrix = 1.0 - ious
    matches, u_a, u_b = linear_assignment(cost_matrix, thresh=0.5)
    assert len(matches) == 1
    assert matches[0][0] == 0 and matches[0][1] == 0
    assert len(u_a) == 0
    assert 1 in u_b


def test_1_single_person_tracking():
    """TEST 1: Single Person — One person receives a track ID."""
    tracker = ByteTrackTracker(track_thresh=0.35, high_thresh=0.45)
    
    det = Detection(class_id=0, class_name="person", confidence=0.88, bbox=[100, 100, 200, 300])
    tracks = tracker.update([det])

    assert len(tracks) == 1
    t = tracks[0]
    assert t.track_id == 1
    assert t.object_type == "person"
    assert t.confidence == 0.88
    assert t.state == TrackState.ACTIVE


def test_2_moving_person_continuity():
    """TEST 2: Moving Person — The same person keeps the same ID across nearby frames."""
    tracker = ByteTrackTracker(track_thresh=0.35, high_thresh=0.45)

    # Frame 1
    det1 = Detection(class_id=0, class_name="person", confidence=0.90, bbox=[100, 100, 200, 300])
    tracks1 = tracker.update([det1])
    assert len(tracks1) == 1
    initial_id = tracks1[0].track_id

    # Frame 2: Slight motion right and down
    det2 = Detection(class_id=0, class_name="person", confidence=0.89, bbox=[106, 104, 206, 304])
    tracks2 = tracker.update([det2])
    assert len(tracks2) == 1
    assert tracks2[0].track_id == initial_id

    # Frame 3: Continued smooth motion
    det3 = Detection(class_id=0, class_name="person", confidence=0.91, bbox=[112, 108, 212, 308])
    tracks3 = tracker.update([det3])
    assert len(tracks3) == 1
    assert tracks3[0].track_id == initial_id


def test_3_multiple_people():
    """TEST 3: Multiple People — Different visible people receive separate IDs."""
    tracker = ByteTrackTracker(track_thresh=0.35, high_thresh=0.45)

    det_a = Detection(class_id=0, class_name="person", confidence=0.85, bbox=[50, 50, 150, 250])
    det_b = Detection(class_id=0, class_name="person", confidence=0.82, bbox=[400, 100, 500, 300])
    
    tracks = tracker.update([det_a, det_b])
    assert len(tracks) == 2
    track_ids = {t.track_id for t in tracks}
    assert len(track_ids) == 2


def test_4_vehicle_tracking():
    """TEST 4: Vehicle — A detected vehicle receives a track ID."""
    tracker = ByteTrackTracker(track_thresh=0.35, high_thresh=0.45)

    det_car = Detection(class_id=2, class_name="car", confidence=0.92, bbox=[300, 200, 600, 450])
    tracks = tracker.update([det_car])

    assert len(tracks) == 1
    assert tracks[0].object_type == "car"
    assert tracks[0].track_id > 0


def test_5_mixed_scene():
    """TEST 5: Mixed Scene — People and vehicles are tracked separately."""
    tracker = ByteTrackTracker(track_thresh=0.35, high_thresh=0.45)

    det_person = Detection(class_id=0, class_name="person", confidence=0.88, bbox=[100, 150, 180, 350])
    det_truck = Detection(class_id=7, class_name="truck", confidence=0.94, bbox=[500, 100, 850, 450])
    det_moto = Detection(class_id=3, class_name="motorcycle", confidence=0.79, bbox=[300, 200, 400, 320])

    tracks = tracker.update([det_person, det_truck, det_moto])
    assert len(tracks) == 3

    types = {t.object_type for t in tracks}
    assert types == {"person", "truck", "motorcycle"}
    ids = {t.track_id for t in tracks}
    assert len(ids) == 3


def test_6_temporary_miss_recovery():
    """TEST 6: Temporary Miss — Tracker maintains state across short detection interruption."""
    tracker = ByteTrackTracker(track_thresh=0.35, high_thresh=0.45, track_buffer=10)

    # Frame 1: Person detected
    det1 = Detection(class_id=0, class_name="person", confidence=0.90, bbox=[200, 200, 300, 450])
    tracks1 = tracker.update([det1])
    assert len(tracks1) == 1
    track_id = tracks1[0].track_id

    # Frame 2: Missed detection (empty list)
    tracks2 = tracker.update([])
    # Confirmed track is temporarily lost but preserved in lost_stracks buffer
    assert len(tracker.lost_stracks) == 1
    assert tracker.lost_stracks[0].track_id == track_id

    # Frame 3: Object reappears nearby
    det3 = Detection(class_id=0, class_name="person", confidence=0.87, bbox=[205, 204, 305, 454])
    tracks3 = tracker.update([det3])
    assert len(tracks3) == 1
    assert tracks3[0].track_id == track_id


def test_7_track_expiry_and_memory_growth():
    """TEST 7: Track Expiry — Disappeared objects are pruned after track_buffer frames."""
    tracker = ByteTrackTracker(track_thresh=0.35, high_thresh=0.45, track_buffer=5)

    det = Detection(class_id=0, class_name="person", confidence=0.88, bbox=[100, 100, 200, 300])
    tracker.update([det])
    assert len(tracker.tracked_stracks) == 1

    # Simulate object disappearing for 10 consecutive frames (> track_buffer of 5)
    for _ in range(10):
        tracker.update([])

    # Verify expired tracks are evicted from active and lost tracking memory
    assert len(tracker.tracked_stracks) == 0
    assert len(tracker.lost_stracks) == 0


def test_8_centroid_and_bottom_center():
    """TEST 8: Centroid & Bottom-Center — Exact mathematical calculations."""
    tracker = ByteTrackTracker(track_thresh=0.35, high_thresh=0.45)

    # Box: x1=100, y1=200, x2=300, y2=600 -> cx=200, cy=400, bottom_center=[200, 600]
    det = Detection(class_id=0, class_name="person", confidence=0.92, bbox=[100, 200, 300, 600])
    tracks = tracker.update([det])

    assert len(tracks) == 1
    t = tracks[0]
    # Centroid is center (x1+x2)/2, (y1+y2)/2
    assert t.centroid == [200, 400]
    # Bottom center is (x1+x2)/2, y2
    assert t.bottom_center == [200, 600]


def test_9_full_sample_video_pipeline():
    """TEST 9: Full Sample Video — Ingest sample_cctv.mp4 through detection + ByteTrack pipeline."""
    assert SAMPLE_CCTV_PATH.exists(), f"Sample CCTV video not found at: {SAMPLE_CCTV_PATH}"

    from app.services.inference.detector import YOLOXDetector

    detector = YOLOXDetector(conf_threshold=0.25)
    tracker = ByteTrackTracker(track_thresh=0.25, high_thresh=0.35, track_buffer=30)

    cap = cv2.VideoCapture(str(SAMPLE_CCTV_PATH))
    assert cap.isOpened(), "Failed to open sample_cctv.mp4"

    frame_count = 0
    max_test_frames = 90  # Test 90 frames for performance and tracking evaluation
    total_active_tracks_seen = 0

    while frame_count < max_test_frames:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1

        detections = detector.detect(frame)
        tracks = tracker.update(detections)
        total_active_tracks_seen += len(tracks)

    cap.release()
    assert frame_count == max_test_frames
    assert total_active_tracks_seen > 0, "No tracks generated across 60 frames of sample_cctv.mp4"


def test_10_api_tracks_endpoint():
    """TEST 10: API — Verify GET /api/cameras/{id}/tracks endpoint structure and response."""
    # List cameras to find registered camera ID
    res = client.get("/api/cameras")
    assert res.status_code == 200
    cameras = res.json()
    assert len(cameras) > 0

    target_cam_id = cameras[0]["id"]
    tracks_res = client.get(f"/api/cameras/{target_cam_id}/tracks")
    assert tracks_res.status_code == 200
    data = tracks_res.json()

    assert "camera_id" in data
    assert "camera_name" in data
    assert "tracks" in data
    assert "tracking_counts" in data
    assert "total_active_tracks" in data["tracking_counts"]


def test_11_fault_tolerance_and_invalid_data():
    """TEST 11: Fault Tolerance — Gracefully handle corrupted boxes and empty detections."""
    tracker = ByteTrackTracker()

    # Empty list
    tracks = tracker.update([])
    assert isinstance(tracks, list)

    # Inverted / degenerate bounding box
    bad_det = Detection(class_id=0, class_name="person", confidence=0.90, bbox=[200, 200, 100, 100])
    tracks = tracker.update([bad_det])
    assert isinstance(tracks, list)
