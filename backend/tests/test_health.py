import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.db.session import engine, SessionLocal
from app.models.schema import Camera, Zone, Event, Setting


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    """
    Verify GET /api/health returns HTTP 200 and {"status": "ok"}
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_connection_and_tables():
    """
    Verify SQLite connection and that core foundation tables exist.
    """
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1

        # Check table names in SQLite
        tables_res = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table';")
        ).fetchall()
        table_names = [row[0] for row in tables_res]
        
        assert "cameras" in table_names
        assert "zones" in table_names
        assert "events" in table_names
        assert "settings" in table_names


def test_schema_insertion_and_query():
    """
    Verify inserting and querying a Camera and Setting record.
    """
    db = SessionLocal()
    try:
        # Insert test camera
        test_cam = Camera(
            name="Test BOP Gate",
            source_type="VIDEO_FILE",
            source_uri="./data/demo/test.mp4",
            enabled=True,
            status="IDLE"
        )
        db.add(test_cam)
        db.commit()
        db.refresh(test_cam)

        assert test_cam.id is not None
        assert test_cam.name == "Test BOP Gate"

        # Insert test setting
        test_setting = Setting(
            key="test_key",
            value_json='{"night_mode": true}'
        )
        db.add(test_setting)
        db.commit()

        queried_setting = db.query(Setting).filter(Setting.key == "test_key").first()
        assert queried_setting is not None
        assert "night_mode" in queried_setting.value_json

        # Cleanup
        db.delete(test_cam)
        db.delete(test_setting)
        db.commit()
    finally:
        db.close()
