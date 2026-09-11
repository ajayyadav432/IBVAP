from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    IBVAP Application Settings
    """
    # System
    APP_NAME: str = "IBVAP — Intelligent Border Video Analytics Platform"
    APP_VERSION: str = "0.1.0"
    IBVAP_ENV: str = "development"
    IBVAP_DEBUG: bool = True
    IBVAP_HOST: str = "127.0.0.1"
    IBVAP_PORT: int = 8000
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Paths
    ROOT_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    DATA_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent / "data"
    
    # Database
    DATABASE_URL: str = f"sqlite:///{(Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'ibvap.db').as_posix()}"
    EVIDENCE_STORAGE_PATH: str = str((Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'evidence').as_posix())
    DEMO_STORAGE_PATH: str = str((Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'demo').as_posix())


    # Detection Settings (YOLOX)
    YOLOX_MODEL_PATH: str = str((Path(__file__).resolve().parent.parent.parent.parent / "models" / "detection" / "yolox_tiny.onnx").as_posix())
    DETECTION_CONF_THRESHOLD: float = 0.40
    DETECTION_NMS_THRESHOLD: float = 0.45
    DETECTION_INPUT_WIDTH: int = 416
    DETECTION_INPUT_HEIGHT: int = 416
    DETECTION_STRIDE: int = 2  # Run heavy YOLOX detector every N frames; use Kalman prediction on intermediate frames

    # Face Detection Settings (YuNet)
    YUNET_MODEL_PATH: str = str((Path(__file__).resolve().parent.parent.parent.parent / "models" / "face" / "face_detection_yunet_2023mar.onnx").as_posix())
    FACE_CONF_THRESHOLD: float = 0.50
    FACE_NMS_THRESHOLD: float = 0.30
    FACE_DETECTION_STRIDE: int = 3  # Run Face detector every N frames

    # Video Stream Settings
    MJPEG_TARGET_FPS: int = 25

    # Analytics Feature Toggles (Global Defaults)
    PERSON_DETECTION_ENABLED: bool = True
    VEHICLE_DETECTION_ENABLED: bool = True
    TRACKING_ENABLED: bool = True
    FACE_DETECTION_ENABLED: bool = True
    ANPR_ENABLED: bool = True
    SUSPICIOUS_ACTIVITY_ENABLED: bool = True

    # Suspicious Activity & Rule Settings
    LOITERING_THRESHOLD_SEC: float = 30.0
    NIGHT_MOVEMENT_ENABLED: bool = True
    NIGHT_START_TIME: str = "22:00"
    NIGHT_END_TIME: str = "05:00"
    NIGHT_COOLDOWN_SEC: float = 60.0

    # Event Engine & Alert Delivery Settings
    ALERT_COOLDOWN_SEC: float = 30.0
    ALERT_MIN_SEVERITY: str = "INFO"  # INFO, WARNING, HIGH, CRITICAL
    ALERT_SOUND_ENABLED: bool = True
    EVIDENCE_CAPTURE_ENABLED: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"

    # Secrets placeholders
    SECRET_KEY: str = "insecure-placeholder-key-for-dev"
    RTSP_DEFAULT_USERNAME: str = ""
    RTSP_DEFAULT_PASSWORD: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
