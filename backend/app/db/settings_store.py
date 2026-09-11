# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.db.settings_store
# Description: Helper utilities for persistent configuration storage in the SQLite settings table.
# License: Apache-2.0
# ==============================================================================

import json
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import db_logger, sys_logger
from app.db.session import SessionLocal
from app.models.schema import Setting


# Default configuration values
DEFAULT_SETTINGS: Dict[str, Any] = {
    # Analytics Toggles
    "person_detection_enabled": True,
    "vehicle_detection_enabled": True,
    "tracking_enabled": True,
    "face_detection_enabled": True,
    "anpr_enabled": True,
    "suspicious_activity_enabled": True,
    
    # Thresholds
    "detection_conf_threshold": 0.40,
    "loitering_threshold_sec": 30.0,
    
    # Alerts
    "alert_cooldown_sec": 30.0,
    "alert_min_severity": "INFO",
    "alert_sound_enabled": True,
    "evidence_capture_enabled": True,
    
    # Night Schedule
    "night_movement_enabled": True,
    "night_start_time": "22:00",
    "night_end_time": "05:00",
    "night_cooldown_sec": 60.0,
}


def get_all_settings(db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Retrieve all configuration settings from the database merged with defaults.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        results = dict(DEFAULT_SETTINGS)
        records = db.query(Setting).all()
        for r in records:
            try:
                results[r.key] = json.loads(r.value_json)
            except Exception as exc:
                db_logger.warning(f"Error deserializing setting '{r.key}': {exc}")
        return results
    finally:
        if close_db:
            db.close()


def get_setting(key: str, default: Any = None, db: Optional[Session] = None) -> Any:
    """
    Retrieve a single setting by key.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        record = db.query(Setting).filter(Setting.key == key).first()
        if record:
            try:
                return json.loads(record.value_json)
            except Exception:
                return record.value_json
        return default if default is not None else DEFAULT_SETTINGS.get(key)
    finally:
        if close_db:
            db.close()


def set_setting(key: str, value: Any, db: Optional[Session] = None) -> None:
    """
    Persist a single setting key-value pair.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        val_json = json.dumps(value)
        record = db.query(Setting).filter(Setting.key == key).first()
        if record:
            record.value_json = val_json
            record.updated_at = datetime.datetime.utcnow()
        else:
            record = Setting(key=key, value_json=val_json)
            db.add(record)
        db.commit()
    except Exception as exc:
        db.rollback()
        db_logger.error(f"Failed to persist setting '{key}': {exc}")
        raise
    finally:
        if close_db:
            db.close()


def set_settings_batch(updates: Dict[str, Any], db: Optional[Session] = None) -> None:
    """
    Persist multiple settings atomically in a single transaction.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        for key, value in updates.items():
            val_json = json.dumps(value)
            record = db.query(Setting).filter(Setting.key == key).first()
            if record:
                record.value_json = val_json
                record.updated_at = datetime.datetime.utcnow()
            else:
                record = Setting(key=key, value_json=val_json)
                db.add(record)
        db.commit()
    except Exception as exc:
        db.rollback()
        db_logger.error(f"Failed to persist batch settings: {exc}")
        raise
    finally:
        if close_db:
            db.close()


def load_runtime_settings(db: Optional[Session] = None) -> None:
    """
    Load persisted settings from database into memory and apply to runtime components.
    """
    current = get_all_settings(db)
    
    # Apply to core settings singleton
    settings.PERSON_DETECTION_ENABLED = bool(current.get("person_detection_enabled", True))
    settings.VEHICLE_DETECTION_ENABLED = bool(current.get("vehicle_detection_enabled", True))
    settings.TRACKING_ENABLED = bool(current.get("tracking_enabled", True))
    settings.FACE_DETECTION_ENABLED = bool(current.get("face_detection_enabled", True))
    settings.ANPR_ENABLED = bool(current.get("anpr_enabled", True))
    settings.SUSPICIOUS_ACTIVITY_ENABLED = bool(current.get("suspicious_activity_enabled", True))
    
    settings.DETECTION_CONF_THRESHOLD = float(current.get("detection_conf_threshold", 0.40))
    settings.LOITERING_THRESHOLD_SEC = float(current.get("loitering_threshold_sec", 30.0))
    
    settings.ALERT_COOLDOWN_SEC = float(current.get("alert_cooldown_sec", 30.0))
    settings.ALERT_MIN_SEVERITY = str(current.get("alert_min_severity", "INFO"))
    settings.ALERT_SOUND_ENABLED = bool(current.get("alert_sound_enabled", True))
    settings.EVIDENCE_CAPTURE_ENABLED = bool(current.get("evidence_capture_enabled", True))
    
    settings.NIGHT_MOVEMENT_ENABLED = bool(current.get("night_movement_enabled", True))
    settings.NIGHT_START_TIME = str(current.get("night_start_time", "22:00"))
    settings.NIGHT_END_TIME = str(current.get("night_end_time", "05:00"))
    settings.NIGHT_COOLDOWN_SEC = float(current.get("night_cooldown_sec", 60.0))

    sys_logger.info("Runtime settings loaded successfully from database.")


def reset_settings_to_defaults(category: str = "all", db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Reset settings in the specified category ('analytics', 'alerts', 'night', 'all') to defaults.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        keys_to_reset = []
        if category in ("all", "analytics"):
            keys_to_reset.extend([
                "person_detection_enabled",
                "vehicle_detection_enabled",
                "tracking_enabled",
                "face_detection_enabled",
                "anpr_enabled",
                "suspicious_activity_enabled",
            ])
        if category in ("all", "thresholds"):
            keys_to_reset.extend([
                "detection_conf_threshold",
                "loitering_threshold_sec",
            ])
        if category in ("all", "alerts"):
            keys_to_reset.extend([
                "alert_cooldown_sec",
                "alert_min_severity",
                "alert_sound_enabled",
                "evidence_capture_enabled",
            ])
        if category in ("all", "night", "night_schedule"):
            keys_to_reset.extend([
                "night_movement_enabled",
                "night_start_time",
                "night_end_time",
                "night_cooldown_sec",
            ])

        for k in keys_to_reset:
            if k in DEFAULT_SETTINGS:
                set_setting(k, DEFAULT_SETTINGS[k], db=db)

        load_runtime_settings(db=db)
        return get_all_settings(db=db)
    finally:
        if close_db:
            db.close()
