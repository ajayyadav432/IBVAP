# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.api.schemas
# Description: Pydantic request/response validation models for cameras, detections, tracks, and faces.
# License: Apache-2.0
# ==============================================================================

import datetime
import re
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


def mask_rtsp_uri(uri: Optional[str]) -> str:
    """Mask credentials in RTSP/HTTP URIs for safe client responses."""
    if not uri:
        return ""
    # Mask proto://user:pass@host -> proto://user:******@host
    return re.sub(r'([a-zA-Z0-9+.-]+://[^:]+:)([^@]+)(@)', r'\1******\3', uri)


class CameraBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Descriptive camera identifier")
    source_type: str = Field("VIDEO_FILE", description="VIDEO_FILE, WEBCAM, or RTSP")
    source_uri: str = Field(..., min_length=1, max_length=500, description="RTSP URL, video file path, or webcam index")
    enabled: bool = Field(True, description="Enable automated ingestion worker")


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    source_type: Optional[str] = None
    source_uri: Optional[str] = Field(None, min_length=1, max_length=500)
    enabled: Optional[bool] = None


class DetectionItem(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox: List[int]


class DetectionCounts(BaseModel):
    total: int = 0
    person: int = 0
    vehicle: int = 0


class TrackItem(BaseModel):
    track_id: int
    object_type: str
    bbox: List[int]
    confidence: float
    centroid: List[int]
    bottom_center: List[int]
    first_seen: str
    last_seen: str
    current_zone: Optional[str] = None
    state: str = "ACTIVE"
    hits: int = 1
    age: int = 1


class TrackingCounts(BaseModel):
    total_active_tracks: int = 0
    tracked_persons: int = 0
    tracked_vehicles: int = 0


class CameraTracksResponse(BaseModel):
    camera_id: int
    camera_name: str
    status: str
    tracks: List[TrackItem] = Field(default_factory=list)
    tracking_counts: TrackingCounts = Field(default_factory=TrackingCounts)


class FaceItem(BaseModel):
    bbox: List[int]
    confidence: float
    landmarks: Optional[List[List[int]]] = None


class CameraFacesResponse(BaseModel):
    camera_id: int
    camera_name: str
    status: str
    faces: List[FaceItem] = Field(default_factory=list)
    faces_count: int = 0
    face_engine: str = "OpenCV YuNet"


class ANPRResultItem(BaseModel):
    track_id: Optional[int] = None
    plate_text: str
    quality: str
    confidence: float
    timestamp: str
    plate_bbox: Optional[List[int]] = None
    vehicle_bbox: Optional[List[int]] = None
    evidence_path: Optional[str] = None
    state_code: Optional[str] = None


class CameraANPRResponse(BaseModel):
    camera_id: int
    camera_name: str
    status: str
    results: List[ANPRResultItem] = Field(default_factory=list)
    anpr_count: int = 0
    anpr_engine: str = "RapidOCR + PP-OCRv4 (ONNX)"


class ZoneBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Descriptive zone identifier")
    zone_type: str = Field("RESTRICTED", description="RESTRICTED or MONITORING")
    polygon: List[List[float]] = Field(..., description="Array of normalized [x, y] coordinates (0.0 to 1.0)")
    enabled: bool = Field(True, description="Enable active zone intrusion monitoring")


class ZoneCreate(ZoneBase):
    pass


class ZoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    zone_type: Optional[str] = None
    polygon: Optional[List[List[float]]] = None
    enabled: Optional[bool] = None


class ZoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    name: str
    zone_type: str
    polygon: List[List[float]]
    enabled: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class CameraZonesResponse(BaseModel):
    camera_id: int
    camera_name: str
    zones: List[ZoneResponse] = Field(default_factory=list)
    zones_count: int = 0


class ZoneIntrusionItem(BaseModel):
    event_type: str = "ZONE_INTRUSION"
    camera_id: int
    zone_id: int
    zone_name: str
    zone_type: str
    track_id: int
    object_type: str
    anchor_point: List[float]
    reason: str
    timestamp: str
    confidence: float


class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_type: str
    source_uri: str
    enabled: bool
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    resolution: Optional[str] = "Unknown"
    source_fps: Optional[float] = 0.0
    measured_fps: Optional[float] = 0.0
    inference_device: Optional[str] = "CPU"
    inference_latency_ms: Optional[float] = 0.0
    inference_fps: Optional[float] = 0.0
    face_latency_ms: Optional[float] = 0.0
    anpr_latency_ms: Optional[float] = 0.0
    zone_latency_ms: Optional[float] = 0.0
    activity_latency_ms: Optional[float] = 0.0
    detections: Optional[List[DetectionItem]] = Field(default_factory=list)
    detection_counts: Optional[DetectionCounts] = Field(default_factory=DetectionCounts)
    tracks: Optional[List[TrackItem]] = Field(default_factory=list)
    tracking_counts: Optional[TrackingCounts] = Field(default_factory=TrackingCounts)
    faces: Optional[List[FaceItem]] = Field(default_factory=list)
    faces_count: Optional[int] = 0
    anpr_results: Optional[List[ANPRResultItem]] = Field(default_factory=list)
    anpr_count: Optional[int] = 0
    zones: Optional[List[ZoneResponse]] = Field(default_factory=list)
    zones_count: Optional[int] = 0
    active_intrusions: Optional[Dict[Any, List[int]]] = Field(default_factory=dict)
    activities: Optional[List["SuspiciousActivityItem"]] = Field(default_factory=list)
    activities_count: Optional[int] = 0
    active_loitering: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    tracker_engine: Optional[str] = "ByteTrack"
    face_engine: Optional[str] = "OpenCV YuNet"
    anpr_engine: Optional[str] = "RapidOCR + PP-OCRv4 (ONNX)"
    zone_engine: Optional[str] = "Point-in-Polygon (Ray-Casting)"
    activity_engine: Optional[str] = "RuleEngine (Intrusion + Loitering)"
    error_message: Optional[str] = None

    @field_validator("source_uri", mode="after")
    @classmethod
    def sanitize_uri(cls, v: str) -> str:
        return mask_rtsp_uri(v)


# ==============================================================================
# Suspicious Activity Schemas
# ==============================================================================

class SuspiciousActivityItem(BaseModel):
    event_type: str                   # "ZONE_INTRUSION" or "LOITERING"
    camera_id: int
    track_id: int
    zone_id: Optional[int] = None
    zone_name: Optional[str] = None
    zone_type: Optional[str] = None
    object_type: str = "person"
    timestamp: str
    severity: str = "HIGH"            # "INFO", "WARNING", "HIGH", "CRITICAL"
    reason: str
    confidence: Optional[float] = None
    duration_sec: Optional[float] = None
    anchor_point: Optional[List[float]] = None


class CameraActivitiesResponse(BaseModel):
    camera_id: int
    camera_name: str
    status: str
    activities: List[SuspiciousActivityItem] = Field(default_factory=list)
    activities_count: int = 0
    active_loitering: List[Dict[str, Any]] = Field(default_factory=list)
    activity_engine: str = "RuleEngine (Intrusion + Loitering)"


class AnalyticsSettingsResponse(BaseModel):
    loitering_threshold_sec: float
    detection_conf_threshold: float
    face_conf_threshold: float
    night_movement_enabled: bool = True
    night_start_time: str = "22:00"
    night_end_time: str = "05:00"
    night_cooldown_sec: float = 60.0
    supported_rules: List[str] = ["RESTRICTED_ZONE_INTRUSION", "LOITERING", "NIGHT_MOVEMENT"]


class AnalyticsSettingsUpdate(BaseModel):
    loitering_threshold_sec: Optional[float] = Field(default=None, ge=1.0, le=3600.0)
    detection_conf_threshold: Optional[float] = Field(default=None, ge=0.01, le=1.0)
    night_movement_enabled: Optional[bool] = None
    night_start_time: Optional[str] = None
    night_end_time: Optional[str] = None
    night_cooldown_sec: Optional[float] = Field(default=None, ge=1.0, le=3600.0)

    @field_validator("night_start_time", "night_end_time", mode="after")
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        import re
        v_clean = v.strip()
        match = re.match(r"^(\d{1,2}):(\d{2})$", v_clean)
        if not match:
            raise ValueError(f"Invalid time format '{v}'. Must be HH:MM (e.g. 22:00, 05:00).")
        h, m = int(match.group(1)), int(match.group(2))
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError(f"Time '{v}' out of valid range (00:00 - 23:59).")
        return f"{h:02d}:{m:02d}"


class InferenceSystemStatus(BaseModel):
    model_name: str
    variant: str
    framework: str
    device: str
    input_resolution: str
    confidence_threshold: float
    nms_threshold: float
    license: str
    supported_classes: List[str]
    tracker_engine: str = "ByteTrack"
    track_buffer: int = 30
    match_threshold: float = 0.70
    face_model_name: str = "YuNet"
    face_framework: str = "OpenCV DNN (FaceDetectorYN)"
    face_license: str = "MIT"
    anpr_engine: str = "RapidOCR + PP-OCRv4 (ONNX)"
    anpr_detector: str = "ch_PP-OCRv4_det_infer.onnx"
    anpr_recognizer: str = "ch_PP-OCRv4_rec_infer.onnx"
    anpr_license: str = "Apache-2.0"
    zone_engine: str = "Point-in-Polygon (Ray-Casting)"
    zone_types_supported: List[str] = ["RESTRICTED", "MONITORING"]
    activity_engine: str = "RuleEngine (Intrusion + Loitering + NightMovement)"
    activity_rules_supported: List[str] = ["RESTRICTED_ZONE_INTRUSION", "LOITERING", "NIGHT_MOVEMENT"]
    loitering_threshold_sec: float = 30.0
    night_movement_enabled: bool = True
    night_start_time: str = "22:00"
    night_end_time: str = "05:00"
    night_cooldown_sec: float = 60.0



class ConnectionTestRequest(BaseModel):
    source_type: str = Field(..., description="RTSP, VIDEO_FILE, or WEBCAM")
    source_uri: str = Field(..., description="URI or path to video source")


class ConnectionTestResponse(BaseModel):
    status: str = Field("CONNECTED", description="CONNECTED, CONNECTING, FAILED")
    success: bool
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class GeneralSettingsResponse(BaseModel):
    # Analytics
    person_detection_enabled: bool = True
    vehicle_detection_enabled: bool = True
    tracking_enabled: bool = True
    face_detection_enabled: bool = True
    anpr_enabled: bool = True
    suspicious_activity_enabled: bool = True
    
    # Thresholds
    detection_conf_threshold: float = 0.40
    loitering_threshold_sec: float = 30.0
    
    # Alerts
    alert_cooldown_sec: float = 30.0
    alert_min_severity: str = "INFO"
    alert_sound_enabled: bool = True
    evidence_capture_enabled: bool = True
    
    # Night Schedule
    night_movement_enabled: bool = True
    night_start_time: str = "22:00"
    night_end_time: str = "05:00"
    night_cooldown_sec: float = 60.0


class GeneralSettingsUpdate(BaseModel):
    # Analytics
    person_detection_enabled: Optional[bool] = None
    vehicle_detection_enabled: Optional[bool] = None
    tracking_enabled: Optional[bool] = None
    face_detection_enabled: Optional[bool] = None
    anpr_enabled: Optional[bool] = None
    suspicious_activity_enabled: Optional[bool] = None
    
    # Thresholds
    detection_conf_threshold: Optional[float] = Field(default=None, ge=0.01, le=1.0)
    loitering_threshold_sec: Optional[float] = Field(default=None, ge=1.0, le=3600.0)
    
    # Alerts
    alert_cooldown_sec: Optional[float] = Field(default=None, ge=1.0, le=3600.0)
    alert_min_severity: Optional[str] = Field(default=None, description="INFO, WARNING, HIGH, CRITICAL")
    alert_sound_enabled: Optional[bool] = None
    evidence_capture_enabled: Optional[bool] = None
    
    # Night Schedule
    night_movement_enabled: Optional[bool] = None
    night_start_time: Optional[str] = None
    night_end_time: Optional[str] = None
    night_cooldown_sec: Optional[float] = Field(default=None, ge=1.0, le=3600.0)

    @field_validator("night_start_time", "night_end_time", mode="after")
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        import re
        v_clean = v.strip()
        match = re.match(r"^(\d{1,2}):(\d{2})$", v_clean)
        if not match:
            raise ValueError(f"Invalid time format '{v}'. Must be HH:MM (e.g. 22:00, 05:00).")
        h, m = int(match.group(1)), int(match.group(2))
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError(f"Time '{v}' out of valid range (00:00 - 23:59).")
        return f"{h:02d}:{m:02d}"

    @field_validator("alert_min_severity", mode="after")
    @classmethod
    def validate_severity(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v_clean = v.strip().upper()
        if v_clean not in ("INFO", "WARNING", "HIGH", "CRITICAL"):
            raise ValueError(f"Invalid alert severity '{v}'. Must be INFO, WARNING, HIGH, or CRITICAL.")
        return v_clean


class ResetSettingsRequest(BaseModel):
    category: str = Field("all", description="'analytics', 'alerts', 'night', or 'all'")


class ResetSettingsResponse(BaseModel):
    success: bool
    message: str
    settings: GeneralSettingsResponse


class SystemInfoResponse(BaseModel):
    app_name: str
    app_version: str
    environment: str
    detector_model: str
    face_model: str
    ocr_model: str
    inference_device: str
    database_type: str
    database_status: str
    system_status: str
    uptime_seconds: float


class EventItemResponse(BaseModel):
    id: int
    timestamp: str
    camera_id: int
    camera_name: Optional[str] = None
    event_type: str
    severity: str
    object_type: Optional[str] = None
    track_id: Optional[int] = None
    zone_id: Optional[int] = None
    zone_name: Optional[str] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None
    evidence_path: Optional[str] = None
    status: str = "NEW"


class EventListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    events: List[EventItemResponse]


class EventStatusUpdate(BaseModel):
    status: str = Field(..., description="NEW, ACKNOWLEDGED, RESOLVED")



