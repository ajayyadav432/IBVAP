import time
from pathlib import Path
import pytest
import cv2
import numpy as np

from app.core.config import settings
from app.services.inference.detector import (
    YOLOXDetector,
    Detection,
    SURVEILLANCE_TARGET_CLASSES,
)
from app.services.inference.annotator import draw_detections, get_class_color


@pytest.fixture
def cctv_video_path():
    path = settings.DATA_DIR / "demo" / "sample_cctv.mp4"
    assert path.exists(), f"Sample CCTV video must exist: {path}"
    return str(path)


@pytest.fixture
def sample_frame(cctv_video_path):
    cap = cv2.VideoCapture(cctv_video_path)
    # Seek to 1 second into video
    cap.set(cv2.CAP_PROP_POS_FRAMES, 30)
    ret, frame = cap.read()
    cap.release()
    assert ret and frame is not None, "Failed to read test frame from sample_cctv.mp4"
    return frame


# TEST 1 — Model Load
def test_yolox_model_load():
    detector = YOLOXDetector()
    info = detector.get_model_info()
    assert info["model_name"] == "YOLOX"
    assert info["variant"] == "yolox_tiny"
    assert any(dev in info["device"] for dev in ("CPU", "CUDA", "GPU", "TensorRT", "DirectML"))
    assert "car" in info["supported_classes"]


# TEST 2 — Person / Object Detection on sample_cctv.mp4
def test_detection_on_cctv_video(sample_frame):
    detector = YOLOXDetector(conf_threshold=0.30)
    detections = detector.detect(sample_frame)
    assert isinstance(detections, list)
    
    # Check that any detected object belongs to our surveillance target classes
    for det in detections:
        assert isinstance(det, Detection)
        assert det.class_name in SURVEILLANCE_TARGET_CLASSES
        assert 0.0 <= det.confidence <= 1.0


# TEST 3 — Vehicle & Person Multi-Frame Sweep
def test_multi_frame_detection_sweep(cctv_video_path):
    cap = cv2.VideoCapture(cctv_video_path)
    detector = YOLOXDetector(conf_threshold=0.30)
    detected_classes = set()

    for i in range(60):  # Sample first 2 seconds (60 frames)
        ret, frame = cap.read()
        if not ret:
            break
        dets = detector.detect(frame)
        for d in dets:
            detected_classes.add(d.class_name)

    cap.release()
    print(f"\nDetected classes in sample_cctv.mp4 sweep: {detected_classes}")
    # Verify at least one target class was identified
    assert len(detected_classes) > 0


# TEST 4 — Bounding Box Coordinates Validity
def test_bounding_box_validity(sample_frame):
    detector = YOLOXDetector(conf_threshold=0.20)
    detections = detector.detect(sample_frame)
    h, w = sample_frame.shape[:2]

    for det in detections:
        x1, y1, x2, y2 = det.bbox
        assert 0 <= x1 < x2 <= w, f"Invalid X coordinates: {x1}, {x2} for width {w}"
        assert 0 <= y1 < y2 <= h, f"Invalid Y coordinates: {y1}, {y2} for height {h}"

    # Test visual annotation
    annotated = draw_detections(sample_frame, detections)
    assert annotated.shape == sample_frame.shape


# TEST 5 — Confidence Filtering
def test_confidence_threshold_filtering(sample_frame):
    detector_low = YOLOXDetector(conf_threshold=0.15)
    detector_high = YOLOXDetector(conf_threshold=0.85)

    dets_low = detector_low.detect(sample_frame)
    dets_high = detector_high.detect(sample_frame)

    assert len(dets_low) >= len(dets_high), "Low threshold should yield >= detections than high threshold"
    for d in dets_high:
        assert d.confidence >= 0.85


# TEST 6 — Missing Model Handling
def test_missing_model_handling():
    with pytest.raises(FileNotFoundError) as exc_info:
        YOLOXDetector(model_path="non_existent_yolox_model.onnx")
    assert "not found" in str(exc_info.value).lower()


# TEST 7 — Inference Stability (Continuous Processing)
def test_inference_stability(cctv_video_path):
    cap = cv2.VideoCapture(cctv_video_path)
    detector = YOLOXDetector(conf_threshold=0.40)
    
    start_time = time.time()
    frames_processed = 0

    for _ in range(75):  # 75 frames
        ret, frame = cap.read()
        if not ret:
            break
        dets = detector.detect(frame)
        _ = draw_detections(frame, dets)
        frames_processed += 1

    cap.release()
    elapsed = time.time() - start_time
    fps = frames_processed / elapsed if elapsed > 0 else 0
    print(f"\nProcessed {frames_processed} frames in {elapsed:.2f}s (~{fps:.1f} FPS)")

    assert frames_processed == 75
