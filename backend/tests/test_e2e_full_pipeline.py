"""End-to-End Full Pipeline Integration Test for IBVAP.

Validates the complete surveillance life cycle:
1. Camera registration.
2. Zone definition.
3. Intrusion / Event detection candidate processing.
4. Auto-anchoring of event evidence SHA-256 to PrivateBlockchain.
5. REST API event querying.
6. Blockchain-backed evidence verification (AUTHENTIC).
7. Tampering simulation on disk and real-time cryptographic rejection (TAMPERED).
8. Full ledger audit.
"""

import os
import io
import json
import uuid
import numpy as np
import cv2
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.schema import Camera, Zone, Event
from app.services.events.engine import EventEngine, EventCandidate
from app.services.crypto import hash_image_bytes, hash_file
from app.services.blockchain import blockchain_ledger


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_e2e_detection_to_blockchain_custody_pipeline(client, tmp_path):
    """Full lifecycle integration test from camera setup to tamper detection."""
    db = SessionLocal()

    # 1. Register Camera
    camera_name = f"E2E Sector Gate {uuid.uuid4().hex[:6]}"
    cam = Camera(
        name=camera_name,
        source_type="VIDEO_FILE",
        source_uri="simulated_border_stream.mp4",
        enabled=True,
        status="CONNECTED",
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    cam_id = cam.id

    # 2. Register Zone
    zone_polygon = [[100, 100], [500, 100], [500, 500], [100, 500]]
    zone = Zone(
        camera_id=cam_id,
        name="Sector-9 High Security Perimeter",
        zone_type="RESTRICTED",
        polygon_json=json.dumps(zone_polygon),
        enabled=True,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    zone_id = zone.id

    # 3. Create synthetic surveillance frame with unique runtime nonce
    unique_nonce = uuid.uuid4().hex
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    # Draw simulated boundary & bounding box with unique nonce
    cv2.rectangle(frame, (200, 200), (450, 600), (0, 0, 255), 3)
    cv2.putText(frame, f"INTRUSION DETECTED [SECTOR 9] {unique_nonce}", (210, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    # 4. Trigger Event Engine Candidate
    engine = EventEngine()
    candidate = EventCandidate(
        event_type="PERIMETER_BREACH",
        camera_id=cam_id,
        track_id=101,
        object_type="person",
        zone_id=zone_id,
        confidence=0.96,
        reason="Target crossed restricted border zone line at 02:45 UTC",
        severity="CRITICAL",
        metadata={"bbox": [200, 200, 450, 600], "sector": "Northern Outpost"},
    )

    recorded_event = engine.process_candidate(candidate, frame=frame, db=db)
    assert recorded_event is not None, "EventEngine must record candidate"
    assert recorded_event.id is not None
    event_id = recorded_event.id
    evidence_rel_path = recorded_event.evidence_path
    assert evidence_rel_path is not None, "Evidence frame must be saved"

    # Verify physical file existence
    clean_ev_path = evidence_rel_path.replace("\\", "/").lstrip("/")
    candidates = [
        os.path.abspath(os.path.join(settings.ROOT_DIR, clean_ev_path)),
        os.path.abspath(os.path.join(settings.DATA_DIR, clean_ev_path.replace("backend/data/", "").replace("data/", ""))),
        os.path.abspath(os.path.join(settings.DATA_DIR, clean_ev_path)),
        os.path.abspath(os.path.join(settings.EVIDENCE_STORAGE_PATH, clean_ev_path.split("evidence/")[-1] if "evidence/" in clean_ev_path else clean_ev_path)),
    ]
    target_evidence_file = next((c for c in candidates if os.path.isfile(c)), None)
    assert target_evidence_file is not None, f"Evidence file was not created on disk at any candidate path {candidates}"

    # Compute expected hash from disk
    expected_image_hash = hash_file(target_evidence_file)

    # Verify block was anchored in blockchain_ledger
    anchored_block = blockchain_ledger.find_block_by_image_hash(expected_image_hash)
    assert anchored_block is not None, "EventEngine must automatically anchor evidence hash to blockchain ledger"
    assert anchored_block.data.get("camera_id") == cam_id
    assert anchored_block.data.get("event_id") == event_id

    # 5. Test REST API: Query event details
    event_api_resp = client.get(f"/api/events/{event_id}")
    assert event_api_resp.status_code == 200
    event_data = event_api_resp.json()
    assert event_data["event_type"] == "PERIMETER_BREACH"
    assert event_data["severity"] == "CRITICAL"
    assert event_data["camera_id"] == cam_id

    # 6. Test REST API: Authenticate evidence via /api/events/{id}/blockchain-verify
    verify_resp = client.get(f"/api/events/{event_id}/blockchain-verify")
    assert verify_resp.status_code == 200
    verify_json = verify_resp.json()
    assert verify_json["is_authentic"] is True
    assert verify_json["status"] == "AUTHENTIC"
    assert verify_json["image_hash"] == expected_image_hash
    assert verify_json["block_index"] == anchored_block.index
    assert verify_json["chain_valid"] is True
    assert "AUTHENTIC" in verify_json["message"]

    # 7. Test REST API: Evidence image download
    image_download_resp = client.get(f"/api/events/{event_id}/evidence")
    assert image_download_resp.status_code == 200
    assert image_download_resp.headers["content-type"] in ("image/jpeg", "image/jpg")
    downloaded_hash = hash_image_bytes(image_download_resp.content)
    assert downloaded_hash == expected_image_hash

    # 8. Simulate Rogue Operator: Tamper with evidence file on disk
    with open(target_evidence_file, "r+b") as f:
        # Flip bytes in the image
        f.seek(50)
        f.write(b"\x00\xFF\x00\xFF_TAMPERED_FRAME_DATA_")

    tampered_hash_on_disk = hash_file(target_evidence_file)
    assert tampered_hash_on_disk != expected_image_hash

    # 9. Test REST API: Re-verify after tampering
    tampered_verify_resp = client.get(f"/api/events/{event_id}/blockchain-verify")
    assert tampered_verify_resp.status_code == 200
    tampered_verify_json = tampered_verify_resp.json()

    assert tampered_verify_json["is_authentic"] is False
    assert tampered_verify_json["status"] == "TAMPERED"
    assert tampered_verify_json["image_hash"] == tampered_hash_on_disk
    assert "TAMPERING DETECTED" in tampered_verify_json["message"]

    try:
        # 10. Audit full chain to ensure blockchain itself wasn't corrupted
        audit_resp = client.post("/api/blockchain/verify")
        assert audit_resp.status_code == 200
        assert audit_resp.json()["chain_valid"] is True
    finally:
        try:
            db.query(Event).filter(Event.id == event_id).delete()
            db.query(Zone).filter(Zone.id == zone_id).delete()
            db.query(Camera).filter(Camera.id == cam_id).delete()
            db.commit()
        except Exception:
            pass
        finally:
            db.close()
