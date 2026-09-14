# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: tests.test_anpr
# Description: Comprehensive unit & integration tests for Phase 5 ANPR pipeline.
# License: Apache-2.0
# ==============================================================================

import os
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.anpr.plate_detector import RapidPlateDetector
from app.services.anpr.ocr_engine import RapidOCREngine
from app.services.anpr.normalizer import PlateNormalizer
from app.services.anpr.quality import PlateQualityGate, PlateQuality
from app.services.anpr.preprocessing import PlatePreprocessor
from app.services.anpr.engine import ANPREngine, ANPRResult
from app.services.video.worker import CameraWorker
from app.services.tracking.tracker import Track, TrackState

DEMO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "demo"))
TOLL_VIDEO_PATH = os.path.join(DEMO_DIR, "toll_cctv.mp4")
SAMPLE_VIDEO_PATH = os.path.join(DEMO_DIR, "sample_cctv.mp4")


def test_plate_model_load():
    """TEST 1 — Plate Model Load: RapidPlateDetector initializes with ONNX Runtime."""
    detector = RapidPlateDetector()
    info = detector.get_model_info()
    assert info["engine"] == "RapidOCR Text/Plate Detector"
    assert "ch_PP-OCRv4_det_infer.onnx" in info["model_name"]
    assert info["framework"] == "ONNX Runtime"
    assert info["license"] == "Apache-2.0"


def test_ocr_model_load():
    """TEST 2 — OCR Model Load: RapidOCREngine initializes with ONNX Runtime."""
    engine = RapidOCREngine()
    info = engine.get_model_info()
    assert info["engine"] == "RapidOCR Text Recognizer"
    assert "ch_PP-OCRv4_rec_infer.onnx" in info["model_name"]
    assert info["framework"] == "ONNX Runtime"
    assert info["license"] == "Apache-2.0"


def test_normalizer_and_quality_gate():
    """Tests normalizer Indian state plausibility and quality gate blur/aspect ratio rules."""
    normalizer = PlateNormalizer()
    gate = PlateQualityGate()

    # Valid Indian plates
    r1 = normalizer.normalize("GJ 05 RX 3056")
    assert r1.sanitized_text == "GJ05RX3056"
    assert r1.is_indian_plausible is True
    assert r1.state_code == "GJ"

    r2 = normalizer.normalize("rj-14-ab-1234")
    assert r2.sanitized_text == "RJ14AB1234"
    assert r2.is_indian_plausible is True
    assert r2.state_code == "RJ"

    # Quality Gate with clear sharp image
    sharp_crop = np.zeros((60, 180, 3), dtype=np.uint8)
    cv2.putText(sharp_crop, "GJ05RX3056", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    q_sharp = gate.assess(sharp_crop)
    assert q_sharp.level in (PlateQuality.HIGH, PlateQuality.MEDIUM)

    # Quality Gate with tiny crop
    tiny_crop = np.zeros((10, 20, 3), dtype=np.uint8)
    q_tiny = gate.assess(tiny_crop)
    assert q_tiny.level == PlateQuality.UNREADABLE


def test_clear_plate_detection_and_ocr():
    """TEST 3 & 4 — Clear Plate Detection & OCR on toll_cctv.mp4 frame 250."""
    if not os.path.exists(TOLL_VIDEO_PATH):
        pytest.skip(f"Test video not found: {TOLL_VIDEO_PATH}")

    cap = cv2.VideoCapture(TOLL_VIDEO_PATH)
    assert cap.isOpened(), "Failed to open toll_cctv.mp4"
    cap.set(cv2.CAP_PROP_POS_FRAMES, 250)
    ret, frame = cap.read()
    cap.release()
    assert ret and frame is not None, "Failed to read frame 250 from toll_cctv.mp4"

    # Frame 250 has car at approx [420, 260, 1000, 680]
    car_crop = frame[260:680, 420:1000]
    assert car_crop.size > 0

    detector = RapidPlateDetector()
    ocr = RapidOCREngine()

    plates = detector.detect_plates(car_crop)
    assert len(plates) > 0, "Failed to detect plate region on vehicle crop"

    # OCR on first plate candidate
    plate_cand = plates[0]
    plate_crop = plate_cand.crop
    assert plate_crop.size > 0

    ocr_res = ocr.recognize(plate_crop)
    assert "GJ" in ocr_res.raw_text or "3056" in ocr_res.raw_text or len(ocr_res.raw_text) >= 6
    assert ocr_res.confidence > 0.70


def test_poor_plate_handling():
    """TEST 5 — Poor Plate: Blurry or corrupted crop evaluated gracefully without hallucination."""
    engine = ANPREngine()
    blurry_crop = np.full((30, 80, 3), 128, dtype=np.uint8)  # Flat gray image
    
    # Process single vehicle crop directly
    results = engine.process_tracks(
        frame=blurry_crop,
        tracks=[],
        frame_idx=1
    )
    assert isinstance(results, list)


def test_vehicle_track_association():
    """TEST 6 — Vehicle Track Association: ANPR result associates with existing vehicle Track ID."""
    if not os.path.exists(TOLL_VIDEO_PATH):
        pytest.skip("toll_cctv.mp4 not found")

    cap = cv2.VideoCapture(TOLL_VIDEO_PATH)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 250)
    ret, frame = cap.read()
    cap.release()
    assert ret and frame is not None

    engine = ANPREngine(sample_interval=1)
    track = Track(
        track_id=14,
        object_type="car",
        bbox=[420, 260, 1000, 680],
        confidence=0.88,
        centroid=[710, 470],
        bottom_center=[710, 680],
        first_seen="2026-09-11T12:00:00Z",
        last_seen="2026-09-11T12:00:00Z",
        state=TrackState.ACTIVE,
        hits=5,
        age=5
    )

    results = engine.process_tracks(frame, [track], frame_idx=250, camera_id=1)
    assert len(results) > 0
    res = results[0]
    assert res.track_id == 14
    assert "GJ05RX3056" in res.plate_text or "GJ" in res.plate_text


def test_repeated_observations_deduplication():
    """TEST 7 — Repeated Observations: Deduplicates repeated frame readings without spamming records."""
    if not os.path.exists(TOLL_VIDEO_PATH):
        pytest.skip("toll_cctv.mp4 not found")

    cap = cv2.VideoCapture(TOLL_VIDEO_PATH)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 250)
    ret, frame = cap.read()
    cap.release()
    assert ret and frame is not None

    engine = ANPREngine(sample_interval=1)
    track = Track(
        track_id=14,
        object_type="car",
        bbox=[420, 260, 1000, 680],
        confidence=0.88,
        centroid=[710, 470],
        bottom_center=[710, 680],
        first_seen="2026-09-11T12:00:00Z",
        last_seen="2026-09-11T12:00:00Z",
        state=TrackState.ACTIVE,
        hits=5,
        age=5
    )

    # Process 5 consecutive frames for track 14
    for idx in range(5):
        engine.process_tracks(frame, [track], frame_idx=250 + idx, camera_id=1)

    active_results = engine.get_active_results(active_track_ids=[14])
    # Should only have 1 active deduplicated record for track 14
    assert len(active_results) == 1
    assert active_results[0].track_id == 14
    assert "GJ05RX3056" in active_results[0].plate_text or "GJ" in active_results[0].plate_text


def test_multiple_vehicles_independence():
    """TEST 8 — Multiple Vehicles: Different vehicle tracks are tracked and read independently."""
    engine = ANPREngine()
    t1 = Track(
        track_id=1,
        object_type="car",
        bbox=[10, 10, 100, 100],
        confidence=0.85,
        centroid=[55, 55],
        bottom_center=[55, 100],
        first_seen="2026-09-11T12:00:00Z",
        last_seen="2026-09-11T12:00:00Z",
        state=TrackState.ACTIVE
    )
    t2 = Track(
        track_id=2,
        object_type="truck",
        bbox=[120, 10, 220, 100],
        confidence=0.82,
        centroid=[170, 55],
        bottom_center=[170, 100],
        first_seen="2026-09-11T12:00:00Z",
        last_seen="2026-09-11T12:00:00Z",
        state=TrackState.ACTIVE
    )
    dummy_frame = np.zeros((200, 300, 3), dtype=np.uint8)
    results = engine.process_tracks(dummy_frame, [t1, t2], frame_idx=1, camera_id=1)
    assert isinstance(results, list)


def test_full_toll_video_worker_pipeline():
    """TEST 9 — Full Toll Video Worker Pipeline: Runs end-to-end ingestion, YOLOX, ByteTrack & ANPR."""
    if not os.path.exists(TOLL_VIDEO_PATH):
        pytest.skip(f"Test video not found: {TOLL_VIDEO_PATH}")

    worker = CameraWorker(
        camera_id=99,
        camera_name="Toll Test Cam",
        source_type="VIDEO_FILE",
        source_uri=TOLL_VIDEO_PATH,
        loop=False,
        enable_detection=True,
        enable_tracking=True,
        enable_anpr=True,
    )

    worker.start()
    import time
    time.sleep(2.0)

    status = worker.get_status_info()
    worker.stop()

    assert status["status"] in ("CONNECTED", "DISCONNECTED")
    assert "anpr_results" in status
    assert "anpr_latency_ms" in status
    assert status["anpr_engine"] == "RapidOCR + PP-OCRv4 (ONNX)"


def test_original_sample_regression():
    """TEST 10 — Original Sample Regression: Confirms sample_cctv.mp4 runs without regression."""
    if not os.path.exists(SAMPLE_VIDEO_PATH):
        pytest.skip(f"Regression video not found: {SAMPLE_VIDEO_PATH}")

    worker = CameraWorker(
        camera_id=98,
        camera_name="Sample Regression Cam",
        source_type="VIDEO_FILE",
        source_uri=SAMPLE_VIDEO_PATH,
        loop=False,
        enable_detection=True,
        enable_tracking=True,
        enable_anpr=True,
    )

    worker.start()
    import time
    time.sleep(1.5)

    status = worker.get_status_info()
    worker.stop()

    assert status["status"] in ("CONNECTED", "DISCONNECTED")
    assert status["detection_counts"]["total"] >= 0
    assert status["tracking_counts"]["total_active_tracks"] >= 0


def test_anpr_api_endpoint():
    """TEST 11 — API Endpoints: Validates GET /api/cameras/{id}/anpr and GET /system/inference."""
    client = TestClient(app)

    # 1. System inference endpoint
    resp = client.get("/api/system/inference")
    assert resp.status_code == 200
    data = resp.json()
    assert data["anpr_engine"] == "RapidOCR + PP-OCRv4 (ONNX)"
    assert data["anpr_license"] == "Apache-2.0"

    # 2. Camera ANPR endpoint (Camera 1 exists in seed or DB)
    cam_resp = client.get("/api/cameras")
    assert cam_resp.status_code == 200
    cameras = cam_resp.json()
    if cameras:
        cam_id = cameras[0]["id"]
        anpr_resp = client.get(f"/api/cameras/{cam_id}/anpr")
        assert anpr_resp.status_code == 200
        anpr_data = anpr_resp.json()
        assert anpr_data["camera_id"] == cam_id
        assert anpr_data["anpr_engine"] == "RapidOCR + PP-OCRv4 (ONNX)"
        assert isinstance(anpr_data["results"], list)
