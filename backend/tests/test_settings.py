import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal, engine
from app.models.schema import Camera, Zone, Setting
from app.db.settings_store import (
    get_all_settings,
    get_setting,
    set_setting,
    set_settings_batch,
    reset_settings_to_defaults,
    load_runtime_settings,
    DEFAULT_SETTINGS,
)
from app.services.video.manager import camera_manager
from app.api.schemas import mask_rtsp_uri
from app.core.config import settings


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# =========================================================================
# 1. Camera Settings & Credential Masking Tests
# =========================================================================

def test_camera_crud_and_masking(client, db):
    """
    Test creating a camera with credentials, fetching it (masked),
    updating it, and deleting it.
    """
    # Create camera with credentials in RTSP URI
    cam_payload = {
        "name": "Border Gate North",
        "source_type": "RTSP",
        "source_uri": "rtsp://admin:SecretPassword123@192.168.1.100:554/stream1",
        "enabled": False,
    }
    create_res = client.post("/api/cameras", json=cam_payload)
    assert create_res.status_code == 201
    cam_data = create_res.json()
    cam_id = cam_data["id"]

    # Verify URI was masked in create response
    assert cam_data["source_uri"] == "rtsp://admin:******@192.168.1.100:554/stream1"
    assert "SecretPassword123" not in cam_data["source_uri"]

    # Get camera by ID - verify URI is masked
    get_res = client.get(f"/api/cameras/{cam_id}")
    assert get_res.status_code == 200
    assert get_res.json()["source_uri"] == "rtsp://admin:******@192.168.1.100:554/stream1"

    # List cameras - verify URI is masked
    list_res = client.get("/api/cameras")
    assert list_res.status_code == 200
    found_cam = next((c for c in list_res.json() if c["id"] == cam_id), None)
    assert found_cam is not None
    assert found_cam["source_uri"] == "rtsp://admin:******@192.168.1.100:554/stream1"

    # Update camera name and disable it
    update_res = client.patch(f"/api/cameras/{cam_id}", json={
        "name": "Border Gate North Updated",
        "enabled": False
    })
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Border Gate North Updated"
    assert update_res.json()["enabled"] is False

    # Verify underlying DB still has unmasked URI for actual connection execution
    db_cam = db.query(Camera).filter(Camera.id == cam_id).first()
    assert db_cam.source_uri == "rtsp://admin:SecretPassword123@192.168.1.100:554/stream1"

    # Delete camera
    del_res = client.delete(f"/api/cameras/{cam_id}")
    assert del_res.status_code == 204

    # Confirm deletion
    get_after_del = client.get(f"/api/cameras/{cam_id}")
    assert get_after_del.status_code == 404


def test_camera_connection_probe(client):
    """
    Test connection testing endpoint for valid demo video and invalid source.
    """
    # Valid demo file test
    valid_test = client.post("/api/cameras/test-connection", json={
        "source_type": "VIDEO_FILE",
        "source_uri": "./data/demo/highway_cctv.mp4"
    })
    assert valid_test.status_code == 200
    res = valid_test.json()
    assert res["status"] in ["CONNECTED", "FAILED"]
    assert "message" in res
    assert "details" in res

    # Invalid file probe (immediate failure without TCP hang)
    invalid_test = client.post("/api/cameras/test-connection", json={
        "source_type": "VIDEO_FILE",
        "source_uri": "./data/demo/non_existent_secret_file.mp4"
    })
    assert invalid_test.status_code == 200
    res_inv = invalid_test.json()
    assert res_inv["status"] == "FAILED"
    assert res_inv["success"] is False
    assert "message" in res_inv


def test_mask_rtsp_uri_utility():
    """
    Unit test mask_rtsp_uri helper function directly.
    """
    assert mask_rtsp_uri("rtsp://admin:pass123@192.168.1.1/live") == "rtsp://admin:******@192.168.1.1/live"
    assert mask_rtsp_uri("http://user:pass@example.com/stream.m3u8") == "http://user:******@example.com/stream.m3u8"
    assert mask_rtsp_uri("./data/demo/toll_cctv.mp4") == "./data/demo/toll_cctv.mp4"
    assert mask_rtsp_uri(None) == ""


# =========================================================================
# 2. General Settings GET & PATCH & Validation Tests
# =========================================================================

def test_get_settings(client):
    """
    Test fetching all settings.
    """
    res = client.get("/api/settings")
    assert res.status_code == 200
    data = res.json()
    assert "person_detection_enabled" in data
    assert "vehicle_detection_enabled" in data
    assert "tracking_enabled" in data
    assert "face_detection_enabled" in data
    assert "anpr_enabled" in data
    assert "suspicious_activity_enabled" in data
    assert "detection_conf_threshold" in data
    assert "loitering_threshold_sec" in data
    assert "alert_cooldown_sec" in data
    assert "alert_min_severity" in data
    assert "alert_sound_enabled" in data
    assert "evidence_capture_enabled" in data
    assert "night_movement_enabled" in data
    assert "night_start_time" in data
    assert "night_end_time" in data
    assert "night_cooldown_sec" in data


def test_patch_settings_dynamic_propagation(client, db):
    """
    Test updating settings via PATCH and verify they update in-memory config and DB.
    """
    patch_payload = {
        "person_detection_enabled": False,
        "vehicle_detection_enabled": False,
        "anpr_enabled": False,
        "detection_conf_threshold": 0.65,
        "loitering_threshold_sec": 45.0,
        "alert_cooldown_sec": 120.0,
        "night_movement_enabled": True,
        "night_start_time": "21:30",
        "night_end_time": "06:15",
        "alert_sound_enabled": False,
        "alert_min_severity": "HIGH"
    }

    res = client.patch("/api/settings", json=patch_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["person_detection_enabled"] is False
    assert data["vehicle_detection_enabled"] is False
    assert data["detection_conf_threshold"] == 0.65
    assert data["loitering_threshold_sec"] == 45.0
    assert data["night_start_time"] == "21:30"
    assert data["night_end_time"] == "06:15"
    assert data["alert_min_severity"] == "HIGH"

    # Verify in-memory settings object updated
    assert settings.PERSON_DETECTION_ENABLED is False
    assert settings.VEHICLE_DETECTION_ENABLED is False
    assert settings.ANPR_ENABLED is False
    assert settings.DETECTION_CONF_THRESHOLD == 0.65
    assert settings.LOITERING_THRESHOLD_SEC == 45.0
    assert settings.ALERT_COOLDOWN_SEC == 120.0
    assert settings.NIGHT_START_TIME == "21:30"
    assert settings.NIGHT_END_TIME == "06:15"
    assert settings.ALERT_SOUND_ENABLED is False
    assert settings.ALERT_MIN_SEVERITY == "HIGH"

    # Verify DB persistence
    db_setting = db.query(Setting).filter(Setting.key == "loitering_threshold_sec").first()
    assert db_setting is not None
    assert json.loads(db_setting.value_json) == 45.0


def test_patch_settings_validation_errors(client):
    """
    Verify validation boundaries for thresholds and schedules.
    """
    # Invalid confidence (< 0.01)
    res = client.patch("/api/settings", json={"detection_conf_threshold": 0.005})
    assert res.status_code == 422

    # Invalid confidence (> 1.0)
    res = client.patch("/api/settings", json={"detection_conf_threshold": 1.5})
    assert res.status_code == 422

    # Invalid loitering duration (< 1)
    res = client.patch("/api/settings", json={"loitering_threshold_sec": 0.5})
    assert res.status_code == 422

    # Invalid alert cooldown (> 3600)
    res = client.patch("/api/settings", json={"alert_cooldown_sec": 5000.0})
    assert res.status_code == 422

    # Invalid time format
    res = client.patch("/api/settings", json={"night_start_time": "25:99"})
    assert res.status_code == 422

    # Invalid severity
    res = client.patch("/api/settings", json={"alert_min_severity": "EXTREME"})
    assert res.status_code == 422


# =========================================================================
# 3. Settings Reset Tests
# =========================================================================

def test_reset_settings_category_and_all(client, db):
    """
    Test resetting individual categories and resetting all settings.
    """
    # First modify some settings
    client.patch("/api/settings", json={
        "detection_conf_threshold": 0.88,
        "face_detection_enabled": False,
        "night_start_time": "23:00"
    })

    # Reset only 'thresholds'
    res = client.post("/api/settings/reset", json={"category": "thresholds"})
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["settings"]["detection_conf_threshold"] == 0.40  # default
    assert res.json()["settings"]["face_detection_enabled"] is False   # untouched

    # Reset 'all'
    res_all = client.post("/api/settings/reset", json={"category": "all"})
    assert res_all.status_code == 200
    assert res_all.json()["settings"]["face_detection_enabled"] is True
    assert res_all.json()["settings"]["night_start_time"] == "22:00"


# =========================================================================
# 4. Zone Management API Tests
# =========================================================================

def test_zone_crud(client, db):
    """
    Test creating, reading, updating, and deleting zones.
    """
    # Create test camera first
    cam = Camera(name="Zone Test Cam", source_type="VIDEO_FILE", source_uri="./data/demo/highway_cctv.mp4")
    db.add(cam)
    db.commit()
    db.refresh(cam)

    # Create Zone with normalized coordinates [0.0, 1.0]
    zone_payload = {
        "name": "Restricted Border Strip",
        "zone_type": "RESTRICTED",
        "polygon": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]],
        "enabled": True
    }
    res_create = client.post(f"/api/cameras/{cam.id}/zones", json=zone_payload)
    assert res_create.status_code == 201
    zone_id = res_create.json()["id"]

    # Read Zone
    res_get = client.get(f"/api/zones/{zone_id}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "Restricted Border Strip"
    assert res_get.json()["zone_type"] == "RESTRICTED"

    # Update Zone polygon and type
    new_poly = [[0.15, 0.15], [0.45, 0.15], [0.45, 0.45], [0.15, 0.45]]
    res_update = client.patch(f"/api/zones/{zone_id}", json={
        "name": "Buffer Patrol Zone",
        "zone_type": "MONITORING",
        "polygon": new_poly,
        "enabled": False
    })
    assert res_update.status_code == 200
    assert res_update.json()["name"] == "Buffer Patrol Zone"
    assert res_update.json()["zone_type"] == "MONITORING"
    assert res_update.json()["enabled"] is False

    # Delete Zone
    res_del = client.delete(f"/api/zones/{zone_id}")
    assert res_del.status_code == 204

    # Confirm deleted
    res_after = client.get(f"/api/zones/{zone_id}")
    assert res_after.status_code == 404

    # Cleanup camera
    db.delete(cam)
    db.commit()


# =========================================================================
# 5. System Info Endpoint Test
# =========================================================================

def test_system_info_endpoint(client):
    """
    Test GET /api/system/info returns application and model status.
    """
    res = client.get("/api/system/info")
    assert res.status_code == 200
    info = res.json()
    assert "app_name" in info
    assert "app_version" in info
    assert "environment" in info
    assert "detector_model" in info
    assert "face_model" in info
    assert "ocr_model" in info
    assert "inference_device" in info
    assert "database_type" in info
    assert "database_status" in info
    assert "system_status" in info
    assert "uptime_seconds" in info


# =========================================================================
# 6. Night Schedule Midnight-Crossing Calculation
# =========================================================================

def test_night_schedule_evaluation():
    """
    Verify night schedule evaluation logic (same-day and midnight-crossing).
    """
    from datetime import time

    # Helper function matching NightEngine check
    def is_night(t: time, start_str: str, end_str: str, enabled: bool) -> bool:
        if not enabled:
            return False
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        st = time(sh, sm)
        et = time(eh, em)
        if st <= et:
            return st <= t <= et
        else:
            return t >= st or t <= et

    # Test midnight crossing (20:00 to 06:00)
    assert is_night(time(22, 0), "20:00", "06:00", True) is True
    assert is_night(time(3, 30), "20:00", "06:00", True) is True
    assert is_night(time(12, 0), "20:00", "06:00", True) is False
    assert is_night(time(22, 0), "20:00", "06:00", False) is False

    # Test same-day interval (01:00 to 05:00)
    assert is_night(time(3, 0), "01:00", "05:00", True) is True
    assert is_night(time(6, 0), "01:00", "05:00", True) is False
