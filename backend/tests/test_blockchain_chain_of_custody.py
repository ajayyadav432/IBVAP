"""Tests for Blockchain Evidence Chain-of-Custody and Tamper-Proof Verification.

Verifies:
1. SHA-256 cryptographic hashing utility.
2. PrivateBlockchain creation, block appending, and integrity validation.
3. Deliberate block corruption / tamper detection.
4. POST /api/alerts/log endpoint (saving image, DB record, and anchoring hash to blockchain).
5. POST /api/alerts/verify endpoint (authentic evidence vs tampered evidence).
6. GET /api/blockchain/ledger and POST /api/blockchain/verify endpoints.
"""

import io
import os
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.crypto import hash_image_bytes
from app.services.blockchain import Block, PrivateBlockchain, blockchain_ledger
from app.db.session import SessionLocal
from app.models.schema import Camera, Event


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def test_camera():
    db = SessionLocal()
    cam = db.query(Camera).first()
    if not cam:
        cam = Camera(
            name="Sector-4 Perimeter Alpha",
            source_type="VIDEO_FILE",
            source_uri="test.mp4",
            enabled=True,
            status="CONNECTED",
        )
        db.add(cam)
        db.commit()
        db.refresh(cam)
    cam_id = cam.id
    db.close()
    return cam_id


def test_crypto_sha256_hashing():
    """Verify SHA-256 calculation behaves deterministically and handles edge cases."""
    data1 = b"IBVAP Tamper Proof Evidence Snapshot"
    data2 = b"IBVAP Tamper Proof Evidence Snapshot"
    data3 = b"IBVAP Tamper Proof Evidence Snapshot (Tampered)"

    h1 = hash_image_bytes(data1)
    h2 = hash_image_bytes(data2)
    h3 = hash_image_bytes(data3)

    assert len(h1) == 64
    assert h1 == h2, "Identical inputs must produce identical SHA-256 hashes."
    assert h1 != h3, "Different inputs must produce completely distinct hashes."

    with pytest.raises(ValueError):
        hash_image_bytes(b"")

    with pytest.raises(TypeError):
        hash_image_bytes(None)  # type: ignore


def test_private_blockchain_ledger_integrity():
    """Verify clean PrivateBlockchain creation, chaining, and tamper detection."""
    bc = PrivateBlockchain(ledger_file=None)
    assert len(bc.chain) == 1
    assert bc.chain[0].index == 0
    assert bc.chain[0].previous_hash == "0" * 64

    # Add block 1
    sample_hash = hash_image_bytes(b"frame_camera_1_sample")
    b1 = bc.add_block(data={"image_hash": sample_hash, "camera_id": 1})
    assert b1.index == 1
    assert b1.previous_hash == bc.chain[0].hash

    # Add block 2
    sample_hash_2 = hash_image_bytes(b"frame_camera_2_sample")
    b2 = bc.add_block(data={"image_hash": sample_hash_2, "camera_id": 2})
    assert b2.index == 2
    assert b2.previous_hash == b1.hash

    # Check validity
    valid, err = bc.is_chain_valid()
    assert valid is True
    assert err is None

    # Search by hash
    found = bc.find_block_by_image_hash(sample_hash)
    assert found is not None
    assert found.index == 1

    # Tamper test 1: Alter data in block 1
    original_data = b1.data.copy()
    b1.data["camera_id"] = 999  # Rogue modification!
    valid_after_tamper, tamper_err = bc.is_chain_valid()
    assert valid_after_tamper is False
    assert "tampered" in tamper_err.lower()

    # Restore data, but alter hash
    b1.data = original_data
    original_hash = b1.hash
    b1.hash = "f" * 64
    valid_after_hash_tamper, hash_err = bc.is_chain_valid()
    assert valid_after_hash_tamper is False

    # Restore block 1
    b1.hash = original_hash
    valid_restored, _ = bc.is_chain_valid()
    assert valid_restored is True


import uuid

def test_api_log_alert_and_verify(client, test_camera):
    """End-to-end API test: log alert with image, anchor to blockchain, and verify authenticity."""
    # 1. Create dummy image bytes with unique seed
    unique_tag = str(uuid.uuid4()).encode("utf-8")
    original_image_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + unique_tag + b"REAL_AUTHENTIC_BORDER_INTRUSION_SNAPSHOT" * 20
    computed_original_hash = hash_image_bytes(original_image_content)

    # 2. Call POST /api/alerts/log
    file_payload = {
        "file": ("snapshot_cam4.jpg", io.BytesIO(original_image_content), "image/jpeg"),
    }
    form_data = {
        "camera_id": str(test_camera),
        "event_type": "PERIMETER_BREACH",
        "severity": "CRITICAL",
        "reason": "Unauthorized crossing detected at Fence Sector 4",
        "object_type": "person",
        "confidence": "0.94",
    }

    response = client.post("/api/alerts/log", files=file_payload, data=form_data)
    assert response.status_code == 200, f"Logging failed: {response.text}"
    log_data = response.json()

    assert log_data["success"] is True
    assert log_data["image_hash"] == computed_original_hash
    assert log_data["blockchain_block"]["index"] >= 1
    assert log_data["blockchain_block"]["data"]["image_hash"] == computed_original_hash
    assert log_data["chain_valid"] is True
    event_id = log_data["event_id"]

    # 3. Call POST /api/alerts/verify with AUTHENTIC image
    verify_payload_authentic = {
        "file": ("test_verify.jpg", io.BytesIO(original_image_content), "image/jpeg"),
    }
    verify_resp = client.post(
        "/api/alerts/verify",
        files=verify_payload_authentic,
        data={"alert_id": str(event_id)},
    )
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()

    assert verify_data["is_authentic"] is True
    assert verify_data["status"] == "AUTHENTIC"
    assert verify_data["image_hash"] == computed_original_hash
    assert verify_data["block_index"] == log_data["blockchain_block"]["index"]
    assert verify_data["chain_valid"] is True

    # 4. Call POST /api/alerts/verify with TAMPERED image (1 byte changed)
    tampered_image_content = original_image_content + b"_ALTERED_BY_ROGUE_OPERATOR"
    tampered_hash = hash_image_bytes(tampered_image_content)
    assert tampered_hash != computed_original_hash

    verify_payload_tampered = {
        "file": ("test_verify.jpg", io.BytesIO(tampered_image_content), "image/jpeg"),
    }
    tamper_resp = client.post(
        "/api/alerts/verify",
        files=verify_payload_tampered,
        data={"alert_id": str(event_id)},
    )
    assert tamper_resp.status_code == 200
    tamper_data = tamper_resp.json()

    assert tamper_data["is_authentic"] is False
    assert tamper_data["status"] == "TAMPERED"
    assert tamper_data["image_hash"] == tampered_hash
    assert "verification FAILED" in tamper_data["message"] or "not found" in tamper_data["message"].lower()

    # 5. Call GET /api/blockchain/ledger
    ledger_resp = client.get("/api/blockchain/ledger")
    assert ledger_resp.status_code == 200
    ledger_data = ledger_resp.json()

    assert ledger_data["total_blocks"] >= 2
    assert ledger_data["chain_valid"] is True
    assert len(ledger_data["blocks"]) == ledger_data["total_blocks"]

    # 6. Call POST /api/blockchain/verify
    chain_audit_resp = client.post("/api/blockchain/verify")
    assert chain_audit_resp.status_code == 200
    audit_data = chain_audit_resp.json()
    assert audit_data["chain_valid"] is True
    assert audit_data["status"] == "SECURE"


def test_blockchain_persistence_reload(tmp_path):
    """Verify that blockchain serializes to disk and correctly restores on reboot."""
    ledger_path = str(tmp_path / "test_ledger.json")

    # Instance 1: Create chain and append blocks
    bc1 = PrivateBlockchain(ledger_file=ledger_path)
    b1 = bc1.add_block(data={"image_hash": "1" * 64, "camera_id": 10})
    b2 = bc1.add_block(data={"image_hash": "2" * 64, "camera_id": 20})
    assert len(bc1.chain) == 3

    # Instance 2: Reload from same ledger file
    bc2 = PrivateBlockchain(ledger_file=ledger_path)
    assert len(bc2.chain) == 3
    valid, err = bc2.is_chain_valid()
    assert valid is True
    assert bc2.chain[1].hash == b1.hash
    assert bc2.chain[2].hash == b2.hash
    assert bc2.chain[2].previous_hash == b1.hash


def test_blockchain_chain_break_in_middle():
    """Verify that tampering with any block in the middle breaks all subsequent links."""
    bc = PrivateBlockchain(ledger_file=None)
    bc.add_block({"image_hash": "a" * 64, "camera_id": 1})
    b2 = bc.add_block({"image_hash": "b" * 64, "camera_id": 2})
    bc.add_block({"image_hash": "c" * 64, "camera_id": 3})
    bc.add_block({"image_hash": "d" * 64, "camera_id": 4})
    assert len(bc.chain) == 5
    assert bc.is_chain_valid()[0] is True

    # Tamper with previous_hash of Block 2
    original_prev = b2.previous_hash
    b2.previous_hash = "deadbeef" * 8
    valid, err = bc.is_chain_valid()
    assert valid is False
    assert "cryptographic link broken" in err.lower() or "tampered" in err.lower()

    # Restore
    b2.previous_hash = original_prev
    assert bc.is_chain_valid()[0] is True


def test_crypto_file_hash_streaming(tmp_path):
    """Verify streaming SHA-256 calculation on disk files."""
    from app.services.crypto import hash_file
    sample_file = tmp_path / "sample_evidence.jpg"
    test_bytes = b"MULTI_CHUNK_EVIDENCE_PAYLOAD" * 5000
    sample_file.write_bytes(test_bytes)

    expected_hash = hash_image_bytes(test_bytes)
    calculated_hash = hash_file(str(sample_file))
    assert calculated_hash == expected_hash

    # Test non-existent file
    with pytest.raises(FileNotFoundError):
        hash_file(str(tmp_path / "non_existent.jpg"))

    # Test empty file
    empty_file = tmp_path / "empty.jpg"
    empty_file.write_bytes(b"")
    with pytest.raises(ValueError):
        hash_file(str(empty_file))


def test_api_verify_stored_event_evidence_authentic_and_tampered(client, test_camera, tmp_path):
    """Verify GET /api/events/{id}/blockchain-verify against on-disk evidence."""
    unique_tag = str(uuid.uuid4()).encode("utf-8")
    img_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + unique_tag + b"_STORED_EVIDENCE_TEST_" * 15

    # 1. Log alert
    file_payload = {"file": ("alert.jpg", io.BytesIO(img_bytes), "image/jpeg")}
    log_resp = client.post(
        "/api/alerts/log",
        files=file_payload,
        data={"camera_id": str(test_camera), "event_type": "LOITERING"},
    )
    assert log_resp.status_code == 200
    ev_id = log_resp.json()["event_id"]
    ev_path = log_resp.json()["evidence_path"]

    # 2. Verify authentic
    verify_resp = client.get(f"/api/events/{ev_id}/blockchain-verify")
    assert verify_resp.status_code == 200
    assert verify_resp.json()["is_authentic"] is True
    assert verify_resp.json()["status"] == "AUTHENTIC"

    # 3. Simulate rogue operator tampering: modify the file on disk
    from app.core.config import settings
    candidates = [
        os.path.join(settings.ROOT_DIR, ev_path),
        os.path.join(settings.DATA_DIR, ev_path),
        os.path.join(settings.ROOT_DIR, "backend", ev_path),
    ]
    target_file = next((c for c in candidates if os.path.isfile(c)), None)
    assert target_file is not None, f"Evidence file was not found on disk at {candidates}"

    # Rogue operator modifies snapshot on disk
    with open(target_file, "wb") as f:
        f.write(img_bytes + b"_ROGUE_MODIFICATION_ON_DISK")

    # 4. Verify tampering detected
    tamper_verify_resp = client.get(f"/api/events/{ev_id}/blockchain-verify")
    assert tamper_verify_resp.status_code == 200
    res_data = tamper_verify_resp.json()
    assert res_data["is_authentic"] is False
    assert res_data["status"] == "TAMPERED"
    assert "TAMPERING DETECTED" in res_data["message"]


def test_api_log_alert_validation_errors(client):
    """Verify API handles invalid or empty inputs gracefully."""
    # Empty file
    resp = client.post(
        "/api/alerts/log",
        files={"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")},
        data={"camera_id": "1", "event_type": "BREACH"},
    )
    assert resp.status_code == 400

    # Missing camera ID
    resp = client.post(
        "/api/alerts/log",
        files={"file": ("valid.jpg", io.BytesIO(b"some_bytes"), "image/jpeg")},
        data={"event_type": "BREACH"},
    )
    assert resp.status_code == 422


def test_api_verify_empty_file_rejected(client):
    """Verify /api/alerts/verify properly rejects 0-byte uploaded files with HTTP 400."""
    resp = client.post(
        "/api/alerts/verify",
        files={"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")},
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_blockchain_corrupted_ledger_recovery(tmp_path):
    """Verify PrivateBlockchain gracefully recovers and initializes genesis block if disk ledger is corrupted."""
    corrupted_ledger = tmp_path / "corrupted_ledger.json"
    corrupted_ledger.write_text("{{INVALID JSON CORRUPTED DATA BY POWER LOSS", encoding="utf-8")

    # Should not crash; should log warning and initialize fresh genesis chain
    bc = PrivateBlockchain(ledger_file=str(corrupted_ledger))
    assert len(bc.chain) == 1
    assert bc.chain[0].index == 0
    valid, _ = bc.is_chain_valid()
    assert valid is True


def test_api_events_blockchain_verify_nonexistent_or_no_evidence(client):
    """Verify /api/events/{id}/blockchain-verify returns 404 for non-existent events."""
    resp = client.get("/api/events/99999999/blockchain-verify")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_concurrent_block_appends_thread_safety():
    """Verify PrivateBlockchain block appending maintains index order and link integrity under concurrency."""
    import concurrent.futures

    bc = PrivateBlockchain(ledger_file=None)
    num_threads = 8
    blocks_per_thread = 5

    def worker(worker_id):
        created_blocks = []
        for i in range(blocks_per_thread):
            h = hash_image_bytes(f"thread_{worker_id}_block_{i}".encode("utf-8"))
            blk = bc.add_block({"image_hash": h, "camera_id": worker_id})
            created_blocks.append(blk)
        return created_blocks

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, wid) for wid in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    # Total blocks = 1 (genesis) + num_threads * blocks_per_thread
    assert len(bc.chain) == 1 + (num_threads * blocks_per_thread)

    # Indices must be strictly contiguous 0, 1, 2, ..., N
    for i in range(len(bc.chain)):
        assert bc.chain[i].index == i

    # Validate overall chain integrity
    valid, err = bc.is_chain_valid()
    assert valid is True, f"Concurrent chaining corrupted integrity: {err}"

