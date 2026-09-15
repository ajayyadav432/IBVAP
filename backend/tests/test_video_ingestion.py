import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import numpy as np

from app.main import app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.schema import Camera
from app.services.video.source import (
    FileSource,
    WebcamSource,
    RTSPSource,
    VideoSourceStatus,
    create_video_source,
)
from app.services.video.worker import CameraWorker
from app.services.video.manager import camera_manager


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def demo_video_path():
    path = settings.DATA_DIR / "demo" / "sample_feed.mp4"
    assert path.exists(), f"Demo video must exist for tests: {path}"
    return str(path)


# TEST 1 — MP4 Source Valid
def test_file_source_valid(demo_video_path):
    source = FileSource(source_uri=demo_video_path, loop=True)
    connected = source.connect()
    assert connected is True
    assert source.status == VideoSourceStatus.CONNECTED
    assert source.width == 640
    assert source.height == 360
    assert source.fps > 0

    # Read multiple frames
    for _ in range(10):
        success, frame = source.read_frame()
        assert success is True
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (360, 640, 3)

    source.disconnect()
    assert source.status == VideoSourceStatus.STOPPED


# TEST 2 — MP4 Source Invalid/Missing
def test_file_source_invalid():
    source = FileSource(source_uri="non_existent_file_9999.mp4", loop=True)
    connected = source.connect()
    assert connected is False
    assert source.status == VideoSourceStatus.ERROR
    assert source.error_message is not None
    assert "not found" in source.error_message.lower()

    success, frame = source.read_frame()
    assert success is False
    assert frame is None

    source.disconnect()


# TEST 3 — Webcam Source (Graceful failure when device not present)
def test_webcam_source_graceful():
    # Use invalid device index 9999
    source = WebcamSource(source_uri="9999")
    connected = source.connect()
    # On headless/servers without index 9999, connect should return False gracefully
    if not connected:
        assert source.status == VideoSourceStatus.ERROR
        assert source.error_message is not None
        success, frame = source.read_frame()
        assert success is False
        assert frame is None
    else:
        # If webcam exists, read frame should work
        success, frame = source.read_frame()
        assert success is True
    source.disconnect()


# TEST 4 & 5 — RTSP Source (Format check, probe, invalid URL handling)
def test_rtsp_source_invalid_format():
    source = RTSPSource(source_uri="invalid-url-string")
    connected = source.connect()
    assert connected is False
    assert source.status == VideoSourceStatus.ERROR
    assert "Invalid RTSP" in source.error_message


def test_rtsp_source_unreachable():
    # Unreachable RTSP address
    source = RTSPSource(source_uri="rtsp://127.0.0.1:8999/live/test")
    connected = source.connect()
    assert connected is False
    assert source.status == VideoSourceStatus.ERROR
    assert source.error_message is not None


# TEST 6 — CameraWorker Thread & Reconnect Backoff
def test_camera_worker_mp4_lifecycle(demo_video_path):
    worker = CameraWorker(
        camera_id=101,
        camera_name="Test Outpost Worker",
        source_type="VIDEO_FILE",
        source_uri=demo_video_path,
        loop=True,
    )
    worker.start()
    for _ in range(30):
        if worker.get_latest_frame() is not None:
            break
        time.sleep(0.1)

    info = worker.get_status_info()
    assert info["is_running"] is True
    assert info["status"] == VideoSourceStatus.CONNECTED

    # Check frame and JPEG generation
    frame = worker.get_latest_frame()
    assert frame is not None
    jpeg = worker.get_latest_jpeg()
    assert jpeg is not None
    assert len(jpeg) > 0

    worker.stop()
    time.sleep(0.2)
    assert worker.source.status == VideoSourceStatus.STOPPED


# TEST 7 — Multiple Camera Isolation
def test_multiple_camera_isolation(demo_video_path):
    """
    Ensure a failing camera does not interrupt an active valid camera.
    """
    valid_worker = CameraWorker(
        camera_id=201,
        camera_name="Valid MP4 Cam",
        source_type="VIDEO_FILE",
        source_uri=demo_video_path,
    )
    invalid_worker = CameraWorker(
        camera_id=202,
        camera_name="Failing RTSP Cam",
        source_type="RTSP",
        source_uri="rtsp://127.0.0.1:9999/unreachable_stream",
    )

    valid_worker.start()
    invalid_worker.start()

    for _ in range(30):
        if valid_worker.get_latest_frame() is not None:
            break
        time.sleep(0.1)

    # Valid worker should be healthy and serving frames
    assert valid_worker.source.status == VideoSourceStatus.CONNECTED
    assert valid_worker.get_latest_frame() is not None

    # Invalid worker should be in backoff/error without throwing uncaught exceptions
    assert invalid_worker.source.status in (VideoSourceStatus.ERROR, VideoSourceStatus.CONNECTING)

    # Clean stop
    valid_worker.stop()
    invalid_worker.stop()


# TEST 8 — API Endpoints & CRUD
def test_camera_api_crud(client, demo_video_path):
    # 1. Test probe connection
    test_probe_res = client.post("/api/cameras/test", json={
        "source_type": "VIDEO_FILE",
        "source_uri": demo_video_path
    })
    assert test_probe_res.status_code == 200
    assert test_probe_res.json()["success"] is True

    # 2. Create camera
    create_res = client.post("/api/cameras", json={
        "name": "BOP Main Perimeter",
        "source_type": "VIDEO_FILE",
        "source_uri": demo_video_path,
        "enabled": True,
    })
    assert create_res.status_code == 201
    cam_data = create_res.json()
    cam_id = cam_data["id"]
    assert cam_data["name"] == "BOP Main Perimeter"

    # 3. List cameras
    list_res = client.get("/api/cameras")
    assert list_res.status_code == 200
    cameras = list_res.json()
    assert any(c["id"] == cam_id for c in cameras)

    # 4. Get camera by ID
    get_res = client.get(f"/api/cameras/{cam_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == cam_id

    # 5. Snapshot endpoint
    time.sleep(0.3)
    snap_res = client.get(f"/api/cameras/{cam_id}/snapshot")
    assert snap_res.status_code == 200
    assert snap_res.headers["content-type"] == "image/jpeg"

    # 6. Update camera
    patch_res = client.patch(f"/api/cameras/{cam_id}", json={
        "name": "BOP Main Perimeter (Updated)",
        "enabled": False,
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "BOP Main Perimeter (Updated)"
    assert patch_res.json()["enabled"] is False

    # 7. Delete camera
    del_res = client.delete(f"/api/cameras/{cam_id}")
    assert del_res.status_code == 204

    # Verify deleted
    get_del_res = client.get(f"/api/cameras/{cam_id}")
    assert get_del_res.status_code == 404
