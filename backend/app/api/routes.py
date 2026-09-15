# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.api.routes
# Description: REST API router endpoints for cameras, video streams, YOLOX detection, ByteTrack tracking, and YuNet face detection.
# License: Apache-2.0
# ==============================================================================

import os
import json
import time
import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

APP_START_TIME = time.time()

from app.api.schemas import (
    CameraCreate,
    CameraUpdate,
    CameraResponse,
    ConnectionTestRequest,
    ConnectionTestResponse,
    DetectionItem,
    TrackItem,
    CameraTracksResponse,
    FaceItem,
    CameraFacesResponse,
    ANPRResultItem,
    CameraANPRResponse,
    ZoneCreate,
    ZoneUpdate,
    ZoneResponse,
    CameraZonesResponse,
    ZoneIntrusionItem,
    SuspiciousActivityItem,
    CameraActivitiesResponse,
    AnalyticsSettingsResponse,
    AnalyticsSettingsUpdate,
    InferenceSystemStatus,
    GeneralSettingsResponse,
    GeneralSettingsUpdate,
    ResetSettingsRequest,
    ResetSettingsResponse,
    SystemInfoResponse,
    EventItemResponse,
    EventListResponse,
    EventStatusUpdate,
    mask_rtsp_uri,
)
from app.core.config import settings
from app.core.logging import api_logger, camera_logger
from app.db.session import get_db
from app.db.settings_store import (
    get_all_settings,
    set_settings_batch,
    reset_settings_to_defaults,
    load_runtime_settings,
)
from app.models.schema import Camera, Zone, Event
from app.services.events import connection_manager, event_engine
from app.services.video.manager import camera_manager
from app.services.video.source import VideoSourceStatus
from app.services.inference.detector import YOLOXDetector, SURVEILLANCE_TARGET_CLASSES
from app.services.zone import validate_polygon, ZoneDefinition

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for IBVAP Foundation.
    Returns: {"status": "ok"}
    """
    return {"status": "ok"}


@router.get("/system/inference", response_model=InferenceSystemStatus, tags=["System"])
def get_inference_status():
    """
    Get active AI object detector, ByteTrack tracker, YuNet face detector, RapidOCR ANPR, Zone, and Rule Engine metadata.
    """
    try:
        detector = YOLOXDetector()
        info = detector.get_model_info()
        return InferenceSystemStatus(
            model_name=info["model_name"],
            variant=info["variant"],
            framework=info["framework"],
            device=info["device"],
            input_resolution=info["input_resolution"],
            confidence_threshold=info["default_confidence_threshold"],
            nms_threshold=info["nms_threshold"],
            license=info["license"],
            supported_classes=info["supported_classes"],
            tracker_engine="ByteTrack",
            track_buffer=30,
            match_threshold=0.70,
            face_model_name="YuNet",
            face_framework="OpenCV DNN (FaceDetectorYN)",
            face_license="MIT",
            anpr_engine="RapidOCR + PP-OCRv4 (ONNX)",
            anpr_detector="ch_PP-OCRv4_det_infer.onnx",
            anpr_recognizer="ch_PP-OCRv4_rec_infer.onnx",
            anpr_license="Apache-2.0",
            zone_engine="Point-in-Polygon (Ray-Casting)",
            zone_types_supported=["RESTRICTED", "MONITORING"],
            activity_engine="RuleEngine (Intrusion + Loitering)",
            activity_rules_supported=["RESTRICTED_ZONE_INTRUSION", "LOITERING"],
            loitering_threshold_sec=settings.LOITERING_THRESHOLD_SEC,
        )
    except Exception as exc:
        return InferenceSystemStatus(
            model_name="YOLOX",
            variant="yolox_tiny",
            framework="ONNX Runtime",
            device="CPU (Fallback)",
            input_resolution="416x416",
            confidence_threshold=settings.DETECTION_CONF_THRESHOLD,
            nms_threshold=settings.DETECTION_NMS_THRESHOLD,
            license="Apache-2.0",
            supported_classes=sorted(list(SURVEILLANCE_TARGET_CLASSES)),
            tracker_engine="ByteTrack",
            track_buffer=30,
            match_threshold=0.70,
            face_model_name="YuNet",
            face_framework="OpenCV DNN (FaceDetectorYN)",
            face_license="MIT",
            anpr_engine="RapidOCR + PP-OCRv4 (ONNX)",
            anpr_detector="ch_PP-OCRv4_det_infer.onnx",
            anpr_recognizer="ch_PP-OCRv4_rec_infer.onnx",
            anpr_license="Apache-2.0",
            zone_engine="Point-in-Polygon (Ray-Casting)",
            zone_types_supported=["RESTRICTED", "MONITORING"],
            activity_engine="RuleEngine (Intrusion + Loitering)",
            activity_rules_supported=["RESTRICTED_ZONE_INTRUSION", "LOITERING"],
            loitering_threshold_sec=settings.LOITERING_THRESHOLD_SEC,
        )


def format_camera_response(cam: Camera, status_info: dict, db_zones: Optional[List[Zone]] = None) -> CameraResponse:
    """Helper to build unified CameraResponse with operational, AI, face, ANPR, zone, and suspicious activity telemetry."""
    raw_anpr = status_info.get("anpr_results", [])
    anpr_items = [
        ANPRResultItem(
            track_id=item.get("track_id"),
            plate_text=item.get("plate_text", "UNKNOWN"),
            quality=item.get("quality", "UNREADABLE"),
            confidence=item.get("confidence", 0.0),
            timestamp=item.get("timestamp", datetime.datetime.utcnow().isoformat()),
            plate_bbox=item.get("plate_bbox"),
            vehicle_bbox=item.get("vehicle_bbox"),
            evidence_path=item.get("evidence_path"),
            state_code=item.get("state_code"),
        )
        for item in raw_anpr
    ]

    raw_zones = status_info.get("zones", [])
    if raw_zones:
        zone_items = [
            ZoneResponse(
                id=z.get("id", 0),
                camera_id=z.get("camera_id", cam.id),
                name=z.get("name", "Zone"),
                zone_type=z.get("zone_type", "RESTRICTED"),
                polygon=z.get("polygon", []),
                enabled=z.get("enabled", True),
                created_at=cam.created_at,
                updated_at=cam.updated_at,
            )
            for z in raw_zones
        ]
    elif db_zones:
        zone_items = []
        for z in db_zones:
            try:
                poly = json.loads(z.polygon_json) if isinstance(z.polygon_json, str) else z.polygon_json
            except Exception:
                poly = []
            zone_items.append(
                ZoneResponse(
                    id=z.id,
                    camera_id=z.camera_id,
                    name=z.name,
                    zone_type=z.zone_type,
                    polygon=poly,
                    enabled=z.enabled,
                    created_at=z.created_at,
                    updated_at=z.updated_at,
                )
            )
    else:
        zone_items = []

    raw_activities = status_info.get("activities", [])
    activity_items = [
        SuspiciousActivityItem(
            event_type=item.get("event_type", "SUSPICIOUS_ACTIVITY"),
            camera_id=item.get("camera_id", cam.id),
            track_id=item.get("track_id", 0),
            zone_id=item.get("zone_id"),
            zone_name=item.get("zone_name"),
            zone_type=item.get("zone_type"),
            object_type=item.get("object_type", "person"),
            timestamp=item.get("timestamp", datetime.datetime.utcnow().isoformat()),
            severity=item.get("severity", "HIGH"),
            reason=item.get("reason", "Suspicious activity detected."),
            confidence=item.get("confidence"),
            duration_sec=item.get("duration_sec"),
            anchor_point=item.get("anchor_point"),
        )
        for item in raw_activities
    ]

    return CameraResponse(
        id=cam.id,
        name=cam.name,
        source_type=cam.source_type,
        source_uri=cam.source_uri,
        enabled=cam.enabled,
        status=status_info.get("status", cam.status),
        created_at=cam.created_at,
        updated_at=cam.updated_at,
        resolution=status_info.get("resolution", "Unknown"),
        source_fps=status_info.get("source_fps", 0.0),
        measured_fps=status_info.get("measured_fps", 0.0),
        inference_device=status_info.get("inference_device", "CPU"),
        inference_latency_ms=status_info.get("inference_latency_ms", 0.0),
        inference_fps=status_info.get("inference_fps", 0.0),
        face_latency_ms=status_info.get("face_latency_ms", 0.0),
        anpr_latency_ms=status_info.get("anpr_latency_ms", 0.0),
        zone_latency_ms=status_info.get("zone_latency_ms", 0.0),
        activity_latency_ms=status_info.get("activity_latency_ms", 0.0),
        detections=status_info.get("detections", []),
        detection_counts=status_info.get("detection_counts", {"total": 0, "person": 0, "vehicle": 0}),
        tracks=status_info.get("tracks", []),
        tracking_counts=status_info.get("tracking_counts", {"total_active_tracks": 0, "tracked_persons": 0, "tracked_vehicles": 0}),
        faces=status_info.get("faces", []),
        faces_count=status_info.get("faces_count", 0),
        anpr_results=anpr_items,
        anpr_count=len(anpr_items),
        zones=zone_items,
        zones_count=len(zone_items),
        active_intrusions=status_info.get("active_intrusions", {}),
        activities=activity_items,
        activities_count=len(activity_items),
        active_loitering=status_info.get("active_loitering", []),
        tracker_engine=status_info.get("tracker_engine", "ByteTrack"),
        face_engine=status_info.get("face_engine", "OpenCV YuNet"),
        anpr_engine=status_info.get("anpr_engine", "RapidOCR + PP-OCRv4 (ONNX)"),
        zone_engine=status_info.get("zone_engine", "Point-in-Polygon (Ray-Casting)"),
        activity_engine=status_info.get("activity_engine", "RuleEngine (Intrusion + Loitering)"),
        error_message=status_info.get("error_message"),
    )


@router.get("/cameras", response_model=List[CameraResponse], tags=["Cameras"])
def list_cameras(db: Session = Depends(get_db)):
    """
    List all configured cameras with live operational, detection, tracking, face, ANPR, and zone telemetry.
    """
    cameras = db.query(Camera).order_by(Camera.id.asc()).all()
    results = []

    for cam in cameras:
        status_info = camera_manager.get_camera_status(cam.id)
        results.append(format_camera_response(cam, status_info, cam.zones))

    return results


@router.post("/cameras", response_model=CameraResponse, status_code=status.HTTP_201_CREATED, tags=["Cameras"])
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)):
    """
    Register a new camera source in the database and launch its ingestion worker if enabled.
    """
    api_logger.info(f"Creating camera '{payload.name}' [{payload.source_type}]")
    
    new_cam = Camera(
        name=payload.name,
        source_type=payload.source_type.upper(),
        source_uri=payload.source_uri,
        enabled=payload.enabled,
        status=VideoSourceStatus.CONNECTING if payload.enabled else VideoSourceStatus.STOPPED,
    )
    db.add(new_cam)
    db.commit()
    db.refresh(new_cam)

    # Register worker in manager
    worker = camera_manager.register_camera(
        camera_id=new_cam.id,
        name=new_cam.name,
        source_type=new_cam.source_type,
        source_uri=new_cam.source_uri,
        enabled=new_cam.enabled,
        enable_detection=True,
    )

    status_info = worker.get_status_info() if worker else {}
    return format_camera_response(new_cam, status_info, new_cam.zones)


@router.get("/cameras/{camera_id}", response_model=CameraResponse, tags=["Cameras"])
def get_camera(camera_id: int, db: Session = Depends(get_db)):
    """
    Retrieve single camera details and live telemetry.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    status_info = camera_manager.get_camera_status(cam.id)
    return format_camera_response(cam, status_info, cam.zones)


@router.post("/cameras/test-connection", response_model=ConnectionTestResponse, tags=["Cameras"])
def test_camera_connection(payload: ConnectionTestRequest):
    """
    Probe reachability and decodability of a video source (RTSP, VIDEO_FILE, WEBCAM)
    without registering a worker or exposing credentials.
    """
    success, message, info = camera_manager.test_connection(payload.source_type, payload.source_uri)
    clean_info = {}
    for k, v in info.items():
        if isinstance(v, str):
            clean_info[k] = mask_rtsp_uri(v)
        else:
            clean_info[k] = v

    clean_msg = mask_rtsp_uri(message)
    status_str = "CONNECTED" if success else "FAILED"
    return ConnectionTestResponse(
        status=status_str,
        success=success,
        message=clean_msg,
        details=clean_info,
    )


@router.patch("/cameras/{camera_id}", response_model=CameraResponse, tags=["Cameras"])
def update_camera(camera_id: int, payload: CameraUpdate, db: Session = Depends(get_db)):
    """
    Update camera details, source URI, or toggle enabled state.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    if payload.name is not None:
        cam.name = payload.name
    if payload.source_type is not None:
        cam.source_type = payload.source_type.upper()
    if payload.source_uri is not None:
        cam.source_uri = payload.source_uri
    if payload.enabled is not None:
        cam.enabled = payload.enabled

    cam.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(cam)

    # Update or restart worker in manager
    if cam.enabled:
        worker = camera_manager.get_worker(cam.id)
        if worker:
            if payload.source_uri is not None or payload.source_type is not None:
                camera_manager.unregister_camera(cam.id)
                worker = camera_manager.register_camera(
                    camera_id=cam.id,
                    name=cam.name,
                    source_type=cam.source_type,
                    source_uri=cam.source_uri,
                    enabled=True,
                )
                camera_manager.reload_camera_zones(cam.id, cam.zones)
        else:
            worker = camera_manager.register_camera(
                camera_id=cam.id,
                name=cam.name,
                source_type=cam.source_type,
                source_uri=cam.source_uri,
                enabled=True,
            )
            camera_manager.reload_camera_zones(cam.id, cam.zones)
    else:
        camera_manager.unregister_camera(cam.id)

    status_info = camera_manager.get_camera_status(cam.id)
    return format_camera_response(cam, status_info, cam.zones)


@router.delete("/cameras/{camera_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Cameras"])
def delete_camera(camera_id: int, db: Session = Depends(get_db)):
    """
    Delete a camera and stop its background worker.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    camera_manager.unregister_camera(camera_id)
    db.delete(cam)
    db.commit()
    api_logger.info(f"Deleted Camera #{camera_id} '{cam.name}'")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/cameras/{camera_id}/detections", response_model=List[DetectionItem], tags=["Detection"])
def get_camera_detections(camera_id: int):
    """
    Fetch raw list of current detected objects for a camera.
    """
    worker = camera_manager.get_worker(camera_id)
    if not worker:
        return []
    return [
        DetectionItem(
            class_id=d.class_id,
            class_name=d.class_name,
            confidence=d.confidence,
            bbox=d.bbox,
        )
        for d in worker.get_latest_detections()
    ]


@router.get("/cameras/{camera_id}/tracks", response_model=CameraTracksResponse, tags=["Tracking"])
def get_camera_tracks(camera_id: int, db: Session = Depends(get_db)):
    """
    Fetch normalized active object tracks for a specific camera.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    worker = camera_manager.get_worker(camera_id)
    if not worker:
        return CameraTracksResponse(
            camera_id=cam.id,
            camera_name=cam.name,
            status=cam.status,
            tracks=[],
            tracking_counts={"total_active_tracks": 0, "tracked_persons": 0, "tracked_vehicles": 0},
        )

    tracks = worker.get_latest_tracks()
    track_items = [
        TrackItem(
            track_id=t.track_id,
            object_type=t.object_type,
            bbox=t.bbox,
            confidence=t.confidence,
            centroid=t.centroid,
            bottom_center=t.bottom_center,
            first_seen=t.first_seen,
            last_seen=t.last_seen,
            current_zone=t.current_zone,
            state=t.state.value if hasattr(t.state, "value") else str(t.state),
            hits=t.hits,
            age=t.age,
        )
        for t in tracks
    ]

    person_tracks = sum(1 for t in tracks if t.object_type == "person")
    vehicle_tracks = sum(1 for t in tracks if t.object_type in ("car", "motorcycle", "bus", "truck"))

    return CameraTracksResponse(
        camera_id=cam.id,
        camera_name=cam.name,
        status=worker.source.status,
        tracks=track_items,
        tracking_counts={
            "total_active_tracks": len(track_items),
            "tracked_persons": person_tracks,
            "tracked_vehicles": vehicle_tracks,
        },
    )


@router.get("/cameras/{camera_id}/faces", response_model=CameraFacesResponse, tags=["Face"])
def get_camera_faces(camera_id: int, db: Session = Depends(get_db)):
    """
    Fetch normalized detected faces for a specific camera.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    worker = camera_manager.get_worker(camera_id)
    if not worker:
        return CameraFacesResponse(
            camera_id=cam.id,
            camera_name=cam.name,
            status=cam.status,
            faces=[],
            faces_count=0,
        )

    faces = worker.get_latest_faces()
    face_items = [
        FaceItem(
            bbox=f.bbox,
            confidence=f.confidence,
            landmarks=f.landmarks,
        )
        for f in faces
    ]

    return CameraFacesResponse(
        camera_id=cam.id,
        camera_name=cam.name,
        status=worker.source.status,
        faces=face_items,
        faces_count=len(face_items),
    )


@router.get("/cameras/{camera_id}/anpr", response_model=CameraANPRResponse, tags=["ANPR"])
def get_camera_anpr(camera_id: int, db: Session = Depends(get_db)):
    """
    Fetch normalized Automatic Number Plate Recognition (ANPR) readings for a specific camera.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    worker = camera_manager.get_worker(camera_id)
    if not worker:
        return CameraANPRResponse(
            camera_id=cam.id,
            camera_name=cam.name,
            status=cam.status,
            results=[],
            anpr_count=0,
            anpr_engine="RapidOCR + PP-OCRv4 (ONNX)",
        )

    raw_anpr = worker.get_latest_anpr()
    results = [
        ANPRResultItem(
            track_id=item.get("track_id"),
            plate_text=item.get("plate_text", "UNKNOWN"),
            quality=item.get("quality", "UNREADABLE"),
            confidence=item.get("confidence", 0.0),
            timestamp=item.get("timestamp", datetime.datetime.utcnow().isoformat()),
            plate_bbox=item.get("plate_bbox"),
            vehicle_bbox=item.get("vehicle_bbox"),
            evidence_path=item.get("evidence_path"),
            state_code=item.get("state_code"),
        )
        for item in raw_anpr
    ]

    return CameraANPRResponse(
        camera_id=cam.id,
        camera_name=cam.name,
        status=worker.source.status,
        results=results,
        anpr_count=len(results),
        anpr_engine="RapidOCR + PP-OCRv4 (ONNX)",
    )


# ==============================================================================
# Zone & Virtual Fence Endpoints
# ==============================================================================

@router.get("/cameras/{camera_id}/zones", response_model=CameraZonesResponse, tags=["Zones"])
def get_camera_zones(camera_id: int, db: Session = Depends(get_db)):
    """
    List all virtual fence/zones configured for a specific camera.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    zone_items = []
    for z in cam.zones:
        try:
            poly = json.loads(z.polygon_json) if isinstance(z.polygon_json, str) else z.polygon_json
        except Exception:
            poly = []
        zone_items.append(
            ZoneResponse(
                id=z.id,
                camera_id=z.camera_id,
                name=z.name,
                zone_type=z.zone_type,
                polygon=poly,
                enabled=z.enabled,
                created_at=z.created_at,
                updated_at=z.updated_at,
            )
        )

    return CameraZonesResponse(
        camera_id=cam.id,
        camera_name=cam.name,
        zones=zone_items,
        zones_count=len(zone_items),
    )


@router.post("/cameras/{camera_id}/zones", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED, tags=["Zones"])
def create_camera_zone(camera_id: int, payload: ZoneCreate, db: Session = Depends(get_db)):
    """
    Define and persist a new polygon zone/virtual fence for a camera.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    # Validate geometry: must have >= 3 points, normalized in [0.0, 1.0], no self-intersection
    valid, err = validate_polygon(payload.polygon)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid polygon geometry: {err}")

    # Check for duplicate zone name on same camera
    existing = db.query(Zone).filter(Zone.camera_id == camera_id, Zone.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Zone with name '{payload.name}' already exists on Camera #{camera_id}.")

    new_zone = Zone(
        camera_id=camera_id,
        name=payload.name,
        zone_type=payload.zone_type.upper(),
        polygon_json=json.dumps(payload.polygon),
        enabled=payload.enabled,
    )
    db.add(new_zone)
    db.commit()
    db.refresh(new_zone)

    # Reload zones in active worker
    all_zones = db.query(Zone).filter(Zone.camera_id == camera_id).all()
    camera_manager.reload_camera_zones(camera_id, all_zones)
    api_logger.info(f"Created Zone #{new_zone.id} '{new_zone.name}' [{new_zone.zone_type}] for Camera #{camera_id}")

    return ZoneResponse(
        id=new_zone.id,
        camera_id=new_zone.camera_id,
        name=new_zone.name,
        zone_type=new_zone.zone_type,
        polygon=payload.polygon,
        enabled=new_zone.enabled,
        created_at=new_zone.created_at,
        updated_at=new_zone.updated_at,
    )


@router.get("/zones/{zone_id}", response_model=ZoneResponse, tags=["Zones"])
def get_zone(zone_id: int, db: Session = Depends(get_db)):
    """
    Retrieve single zone details by ID.
    """
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone #{zone_id} not found.")

    try:
        poly = json.loads(zone.polygon_json) if isinstance(zone.polygon_json, str) else zone.polygon_json
    except Exception:
        poly = []

    return ZoneResponse(
        id=zone.id,
        camera_id=zone.camera_id,
        name=zone.name,
        zone_type=zone.zone_type,
        polygon=poly,
        enabled=zone.enabled,
        created_at=zone.created_at,
        updated_at=zone.updated_at,
    )


@router.patch("/zones/{zone_id}", response_model=ZoneResponse, tags=["Zones"])
def update_zone(zone_id: int, payload: ZoneUpdate, db: Session = Depends(get_db)):
    """
    Update zone properties, polygon geometry, or toggle enabled state.
    """
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone #{zone_id} not found.")

    if payload.name is not None:
        # Check duplicate name if name changed
        if payload.name != zone.name:
            dup = db.query(Zone).filter(Zone.camera_id == zone.camera_id, Zone.name == payload.name).first()
            if dup:
                raise HTTPException(status_code=400, detail=f"Zone with name '{payload.name}' already exists on Camera #{zone.camera_id}.")
        zone.name = payload.name

    if payload.zone_type is not None:
        zone.zone_type = payload.zone_type.upper()

    if payload.polygon is not None:
        valid, err = validate_polygon(payload.polygon)
        if not valid:
            raise HTTPException(status_code=400, detail=f"Invalid polygon geometry: {err}")
        zone.polygon_json = json.dumps(payload.polygon)

    if payload.enabled is not None:
        zone.enabled = payload.enabled

    zone.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(zone)

    # Reload zones in active worker
    all_zones = db.query(Zone).filter(Zone.camera_id == zone.camera_id).all()
    camera_manager.reload_camera_zones(zone.camera_id, all_zones)
    api_logger.info(f"Updated Zone #{zone.id} '{zone.name}' for Camera #{zone.camera_id}")

    try:
        poly = json.loads(zone.polygon_json) if isinstance(zone.polygon_json, str) else zone.polygon_json
    except Exception:
        poly = []

    return ZoneResponse(
        id=zone.id,
        camera_id=zone.camera_id,
        name=zone.name,
        zone_type=zone.zone_type,
        polygon=poly,
        enabled=zone.enabled,
        created_at=zone.created_at,
        updated_at=zone.updated_at,
    )


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Zones"])
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    """
    Delete a zone and synchronize the camera's active zone engine.
    """
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone #{zone_id} not found.")

    camera_id = zone.camera_id
    db.delete(zone)
    db.commit()

    # Reload zones in active worker
    all_zones = db.query(Zone).filter(Zone.camera_id == camera_id).all()
    camera_manager.reload_camera_zones(camera_id, all_zones)
    api_logger.info(f"Deleted Zone #{zone_id} from Camera #{camera_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/cameras/{camera_id}", response_model=CameraResponse, tags=["Cameras"])
def update_camera(camera_id: int, payload: CameraUpdate, db: Session = Depends(get_db)):
    """
    Update camera properties or toggle enable/disable state.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    if payload.name is not None:
        cam.name = payload.name
    if payload.source_type is not None:
        cam.source_type = payload.source_type.upper()
    if payload.source_uri is not None:
        cam.source_uri = payload.source_uri
    if payload.enabled is not None:
        cam.enabled = payload.enabled

    cam.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(cam)

    # Re-register or stop worker
    if cam.enabled:
        worker = camera_manager.register_camera(
            camera_id=cam.id,
            name=cam.name,
            source_type=cam.source_type,
            source_uri=cam.source_uri,
            enabled=True,
            enable_detection=True,
        )
        # Load zones
        all_zones = db.query(Zone).filter(Zone.camera_id == cam.id).all()
        camera_manager.reload_camera_zones(cam.id, all_zones)
    else:
        camera_manager.unregister_camera(cam.id)
        worker = None

    status_info = worker.get_status_info() if worker else {}
    return format_camera_response(cam, status_info, cam.zones)


@router.delete("/cameras/{camera_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Cameras"])
def delete_camera(camera_id: int, db: Session = Depends(get_db)):
    """
    Delete camera configuration and cleanly shutdown its ingestion worker.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    camera_manager.unregister_camera(camera_id)
    db.delete(cam)
    db.commit()
    api_logger.info(f"Deleted Camera #{camera_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/cameras/test", response_model=ConnectionTestResponse, tags=["Cameras"])
def test_probe_connection(payload: ConnectionTestRequest):
    """
    Probe a potential camera source before saving to check connectivity and decoding.
    """
    success, message, info = camera_manager.test_connection(
        source_type=payload.source_type,
        source_uri=payload.source_uri,
    )
    clean_info = {k: (mask_rtsp_uri(v) if isinstance(v, str) else v) for k, v in info.items()}
    clean_msg = mask_rtsp_uri(message)
    return ConnectionTestResponse(
        status="CONNECTED" if success else "FAILED",
        success=success,
        message=clean_msg,
        details=clean_info,
    )


@router.post("/cameras/{camera_id}/test", response_model=ConnectionTestResponse, tags=["Cameras"])
def test_existing_camera(camera_id: int, db: Session = Depends(get_db)):
    """
    Test connectivity for an already registered camera.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    success, message, info = camera_manager.test_connection(
        source_type=cam.source_type,
        source_uri=cam.source_uri,
    )
    clean_info = {k: (mask_rtsp_uri(v) if isinstance(v, str) else v) for k, v in info.items()}
    clean_msg = mask_rtsp_uri(message)
    return ConnectionTestResponse(
        status="CONNECTED" if success else "FAILED",
        success=success,
        message=clean_msg,
        details=clean_info,
    )


@router.get("/cameras/{camera_id}/stream", tags=["Stream"])
def stream_camera_mjpeg(camera_id: int, db: Session = Depends(get_db)):
    """
    Multipart MJPEG browser preview stream (`multipart/x-mixed-replace`) with live bounding boxes and faces.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    worker = camera_manager.get_worker(camera_id)
    if not worker and cam.enabled:
        camera_manager.register_camera(
            camera_id=cam.id,
            name=cam.name,
            source_type=cam.source_type,
            source_uri=cam.source_uri,
            enabled=True,
            enable_detection=True,
        )

    return StreamingResponse(
        camera_manager.generate_mjpeg_stream(camera_id=camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/cameras/{camera_id}/snapshot", tags=["Stream"])
def get_camera_snapshot(camera_id: int, db: Session = Depends(get_db)):
    """
    Capture single current frame as image/jpeg.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    worker = camera_manager.get_worker(camera_id)
    jpeg_bytes = worker.get_latest_jpeg() if worker else None

    if not jpeg_bytes:
        jpeg_bytes = camera_manager.get_placeholder_jpeg(
            text=f"CAM #{camera_id} OFFLINE",
            subtext="No frame available"
        )

    return Response(content=jpeg_bytes, media_type="image/jpeg")


# ==============================================================================
# Suspicious Activity & Analytics Endpoints
# ==============================================================================

@router.get("/cameras/{camera_id}/activities", response_model=CameraActivitiesResponse, tags=["Analytics"])
def get_camera_activities(camera_id: int, db: Session = Depends(get_db)):
    """
    Fetch active suspicious activity candidates (Restricted Intrusion & Loitering) for a specific camera.
    """
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera #{camera_id} not found.")

    worker = camera_manager.get_worker(camera_id)
    if not worker:
        return CameraActivitiesResponse(
            camera_id=cam.id,
            camera_name=cam.name,
            status=cam.status,
            activities=[],
            activities_count=0,
            active_loitering=[],
            activity_engine="RuleEngine (Intrusion + Loitering)",
        )

    raw_activities = worker.get_latest_activities()
    activity_items = [
        SuspiciousActivityItem(
            event_type=item.event_type,
            camera_id=item.camera_id,
            track_id=item.track_id,
            zone_id=item.zone_id,
            zone_name=item.zone_name,
            zone_type=item.zone_type,
            object_type=item.object_type,
            timestamp=item.timestamp,
            severity=item.severity,
            reason=item.reason,
            confidence=item.confidence,
            duration_sec=item.duration_sec,
            anchor_point=item.anchor_point,
        )
        for item in raw_activities
    ]
    loitering_states = worker.get_active_loitering_states()

    return CameraActivitiesResponse(
        camera_id=cam.id,
        camera_name=cam.name,
        status=worker.source.status,
        activities=activity_items,
        activities_count=len(activity_items),
        active_loitering=loitering_states,
        activity_engine="RuleEngine (Intrusion + Loitering + NightMovement)",
        activity_rules_supported=["RESTRICTED_ZONE_INTRUSION", "LOITERING", "NIGHT_MOVEMENT"],
        night_movement_enabled=settings.NIGHT_MOVEMENT_ENABLED,
        night_start_time=settings.NIGHT_START_TIME,
        night_end_time=settings.NIGHT_END_TIME,
        night_cooldown_sec=settings.NIGHT_COOLDOWN_SEC,
    )


@router.get("/system/analytics", response_model=AnalyticsSettingsResponse, tags=["Analytics"])
def get_analytics_settings():
    """
    Retrieve global analytics and suspicious activity rule configuration parameters.
    """
    return AnalyticsSettingsResponse(
        loitering_threshold_sec=settings.LOITERING_THRESHOLD_SEC,
        detection_conf_threshold=settings.DETECTION_CONF_THRESHOLD,
        face_conf_threshold=settings.FACE_CONF_THRESHOLD,
        night_movement_enabled=settings.NIGHT_MOVEMENT_ENABLED,
        night_start_time=settings.NIGHT_START_TIME,
        night_end_time=settings.NIGHT_END_TIME,
        night_cooldown_sec=settings.NIGHT_COOLDOWN_SEC,
        supported_rules=["RESTRICTED_ZONE_INTRUSION", "LOITERING", "NIGHT_MOVEMENT"],
    )


@router.patch("/system/analytics", response_model=AnalyticsSettingsResponse, tags=["Analytics"])
def update_analytics_settings(payload: AnalyticsSettingsUpdate, db: Session = Depends(get_db)):
    """
    Update global analytics thresholds (e.g. loitering dwell time, night schedule, detection confidence) and propagate to active camera workers.
    """
    updates = {}
    if payload.loitering_threshold_sec is not None:
        val = max(1.0, min(3600.0, float(payload.loitering_threshold_sec)))
        settings.LOITERING_THRESHOLD_SEC = val
        updates["loitering_threshold_sec"] = val
        for worker in camera_manager.get_all_workers():
            worker.set_loitering_threshold(val)
        api_logger.info(f"Updated global LOITERING_THRESHOLD_SEC to {val}s")

    if payload.detection_conf_threshold is not None:
        cval = max(0.01, min(1.0, float(payload.detection_conf_threshold)))
        settings.DETECTION_CONF_THRESHOLD = cval
        updates["detection_conf_threshold"] = cval
        for worker in camera_manager.get_all_workers():
            worker.set_conf_threshold(cval)
        api_logger.info(f"Updated global DETECTION_CONF_THRESHOLD to {cval}")

    night_changed = False
    if payload.night_movement_enabled is not None:
        settings.NIGHT_MOVEMENT_ENABLED = payload.night_movement_enabled
        updates["night_movement_enabled"] = payload.night_movement_enabled
        night_changed = True
    if payload.night_start_time is not None:
        settings.NIGHT_START_TIME = payload.night_start_time
        updates["night_start_time"] = payload.night_start_time
        night_changed = True
    if payload.night_end_time is not None:
        settings.NIGHT_END_TIME = payload.night_end_time
        updates["night_end_time"] = payload.night_end_time
        night_changed = True
    if payload.night_cooldown_sec is not None:
        settings.NIGHT_COOLDOWN_SEC = max(1.0, float(payload.night_cooldown_sec))
        updates["night_cooldown_sec"] = max(1.0, float(payload.night_cooldown_sec))
        night_changed = True

    if night_changed:
        for worker in camera_manager.get_all_workers():
            worker.set_night_movement_config(
                enabled=settings.NIGHT_MOVEMENT_ENABLED,
                start_time=settings.NIGHT_START_TIME,
                end_time=settings.NIGHT_END_TIME,
                cooldown_sec=settings.NIGHT_COOLDOWN_SEC,
            )
        api_logger.info(f"Updated global Night Movement config: enabled={settings.NIGHT_MOVEMENT_ENABLED}, window={settings.NIGHT_START_TIME}->{settings.NIGHT_END_TIME}")

    if updates:
        set_settings_batch(updates, db=db)

    return AnalyticsSettingsResponse(
        loitering_threshold_sec=settings.LOITERING_THRESHOLD_SEC,
        detection_conf_threshold=settings.DETECTION_CONF_THRESHOLD,
        face_conf_threshold=settings.FACE_CONF_THRESHOLD,
        night_movement_enabled=settings.NIGHT_MOVEMENT_ENABLED,
        night_start_time=settings.NIGHT_START_TIME,
        night_end_time=settings.NIGHT_END_TIME,
        night_cooldown_sec=settings.NIGHT_COOLDOWN_SEC,
        supported_rules=["RESTRICTED_ZONE_INTRUSION", "LOITERING", "NIGHT_MOVEMENT"],
    )


# ==============================================================================
# Settings & Configuration API Endpoints
# ==============================================================================

@router.get("/settings", response_model=GeneralSettingsResponse, tags=["Settings"])
def get_settings(db: Session = Depends(get_db)):
    """
    Retrieve consolidated system and analytics settings from SQLite settings store.
    """
    raw = get_all_settings(db)
    return GeneralSettingsResponse(**raw)


@router.patch("/settings", response_model=GeneralSettingsResponse, tags=["Settings"])
def update_settings(payload: GeneralSettingsUpdate, db: Session = Depends(get_db)):
    """
    Update consolidated settings, persist to SQLite database, and propagate dynamically to runtime components.
    """
    updates = {}
    for field_name, field_value in payload.model_dump(exclude_unset=True).items():
        if field_value is not None:
            updates[field_name] = field_value

    if updates:
        set_settings_batch(updates, db=db)
        load_runtime_settings(db=db)

        # Propagate changes to active camera workers
        camera_manager.broadcast_analytics_config(
            person_detection_enabled=settings.PERSON_DETECTION_ENABLED,
            vehicle_detection_enabled=settings.VEHICLE_DETECTION_ENABLED,
            tracking_enabled=settings.TRACKING_ENABLED,
            face_detection_enabled=settings.FACE_DETECTION_ENABLED,
            anpr_enabled=settings.ANPR_ENABLED,
            suspicious_activity_enabled=settings.SUSPICIOUS_ACTIVITY_ENABLED,
        )
        camera_manager.broadcast_conf_threshold(settings.DETECTION_CONF_THRESHOLD)
        camera_manager.broadcast_loitering_threshold(settings.LOITERING_THRESHOLD_SEC)
        camera_manager.broadcast_night_movement_config(
            enabled=settings.NIGHT_MOVEMENT_ENABLED,
            start_time=settings.NIGHT_START_TIME,
            end_time=settings.NIGHT_END_TIME,
            cooldown_sec=settings.NIGHT_COOLDOWN_SEC,
        )
        event_engine.set_cooldown(settings.ALERT_COOLDOWN_SEC)
        api_logger.info(f"Applied and propagated settings update: {list(updates.keys())}")

    raw = get_all_settings(db)
    return GeneralSettingsResponse(**raw)


@router.post("/settings/reset", response_model=ResetSettingsResponse, tags=["Settings"])
def reset_settings(payload: ResetSettingsRequest, db: Session = Depends(get_db)):
    """
    Reset settings to project defaults for a specific category ('analytics', 'alerts', 'night', 'all').
    """
    category = payload.category.lower().strip()
    if category not in ("all", "analytics", "thresholds", "alerts", "night", "night_schedule"):
        raise HTTPException(status_code=400, detail="Invalid category. Must be 'analytics', 'thresholds', 'alerts', 'night', 'night_schedule', or 'all'.")

    updated = reset_settings_to_defaults(category=category, db=db)

    # Propagate reset values to active camera workers
    camera_manager.broadcast_analytics_config(
        person_detection_enabled=settings.PERSON_DETECTION_ENABLED,
        vehicle_detection_enabled=settings.VEHICLE_DETECTION_ENABLED,
        tracking_enabled=settings.TRACKING_ENABLED,
        face_detection_enabled=settings.FACE_DETECTION_ENABLED,
        anpr_enabled=settings.ANPR_ENABLED,
        suspicious_activity_enabled=settings.SUSPICIOUS_ACTIVITY_ENABLED,
    )
    camera_manager.broadcast_conf_threshold(settings.DETECTION_CONF_THRESHOLD)
    camera_manager.broadcast_loitering_threshold(settings.LOITERING_THRESHOLD_SEC)
    camera_manager.broadcast_night_movement_config(
        enabled=settings.NIGHT_MOVEMENT_ENABLED,
        start_time=settings.NIGHT_START_TIME,
        end_time=settings.NIGHT_END_TIME,
        cooldown_sec=settings.NIGHT_COOLDOWN_SEC,
    )
    event_engine.set_cooldown(settings.ALERT_COOLDOWN_SEC)
    api_logger.info(f"Reset settings for category '{category}' to defaults.")

    return ResetSettingsResponse(
        success=True,
        message=f"Settings for '{category}' reset to defaults.",
        settings=GeneralSettingsResponse(**updated),
    )


@router.get("/system/info", response_model=SystemInfoResponse, tags=["System"])
def get_system_info(db: Session = Depends(get_db)):
    """
    Retrieve high-level system operational metadata and component health without exposing secrets.
    """
    db_status = "Connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "Degraded"

    detector = YOLOXDetector()
    info = detector.get_model_info()

    return SystemInfoResponse(
        app_name=settings.APP_NAME,
        app_version=settings.APP_VERSION,
        environment=settings.IBVAP_ENV,
        detector_model=f"YOLOX-Tiny ({info.get('variant', 'tiny')})",
        face_model="YuNet (OpenCV DNN)",
        ocr_model="RapidOCR + PP-OCRv4 (ONNX)",
        inference_device=info.get("device", "CPU"),
        database_type="SQLite (WAL Mode)",
        database_status=db_status,
        system_status="Operational",
        uptime_seconds=round(time.time() - APP_START_TIME, 1),
    )


# ==============================================================================
# Events & Real-Time Alerts API Endpoints
# ==============================================================================

def _serialize_event_item(e: Event) -> EventItemResponse:
    """Helper to convert Event ORM object to EventItemResponse with resolved names."""
    cam_name = e.camera.name if e.camera else f"Camera #{e.camera_id} (Archived)"
    zn_name = e.zone.name if e.zone else (f"Zone #{e.zone_id}" if e.zone_id else None)
    return EventItemResponse(
        id=e.id,
        timestamp=e.timestamp.isoformat(),
        camera_id=e.camera_id,
        camera_name=cam_name,
        event_type=e.event_type,
        severity=e.severity,
        object_type=e.object_type,
        track_id=e.track_id,
        zone_id=e.zone_id,
        zone_name=zn_name,
        confidence=round(float(e.confidence), 4) if e.confidence is not None else None,
        reason=e.reason,
        evidence_path=e.evidence_path,
        status=e.status,
    )

def _parse_iso_datetime(dt_str: str) -> datetime.datetime:
    """Parse ISO datetime string with tolerance for Z, offsets, or simple date/time."""
    clean = dt_str.strip().rstrip("Z").replace("+00:00", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(clean, fmt)
        except Exception:
            continue
    try:
        return datetime.datetime.fromisoformat(clean)
    except Exception:
        raise ValueError(f"Cannot parse datetime '{dt_str}'")


@router.get("/events", response_model=EventListResponse, tags=["Events"])
def list_events(
    camera_id: Optional[int] = Query(default=None, description="Filter by Camera ID"),
    event_type: Optional[str] = Query(default=None, description="Filter by Event Type"),
    severity: Optional[str] = Query(default=None, description="Filter by Severity (INFO, WARNING, HIGH, CRITICAL)"),
    status: Optional[str] = Query(default=None, description="Filter by Status (NEW, ACKNOWLEDGED, RESOLVED)"),
    start_time: Optional[str] = Query(default=None, description="Filter by Start Datetime (ISO format)"),
    end_time: Optional[str] = Query(default=None, description="Filter by End Datetime (ISO format)"),
    search: Optional[str] = Query(default=None, description="Search string across reason, event_type, or camera name"),
    limit: int = Query(default=50, ge=1, le=500, description="Page limit"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
):
    """
    List historical and real-time security events with filtering, date range, search, and pagination.
    Ordered by timestamp DESC (newest first).
    """
    query = db.query(Event)
    if camera_id is not None:
        query = query.filter(Event.camera_id == camera_id)
    if event_type:
        query = query.filter(Event.event_type == event_type.strip().upper())
    if severity:
        query = query.filter(Event.severity == severity.strip().upper())
    if status:
        query = query.filter(Event.status == status.strip().upper())
    if start_time:
        try:
            s_dt = _parse_iso_datetime(start_time)
            query = query.filter(Event.timestamp >= s_dt)
        except Exception:
            raise HTTPException(status_code=422, detail=f"Invalid start_time format '{start_time}'. Expected ISO 8601.")
    if end_time:
        try:
            e_dt = _parse_iso_datetime(end_time)
            query = query.filter(Event.timestamp <= e_dt)
        except Exception:
            raise HTTPException(status_code=422, detail=f"Invalid end_time format '{end_time}'. Expected ISO 8601.")
    if search:
        s_term = f"%{search.strip()}%"
        query = query.outerjoin(Camera, Event.camera_id == Camera.id).filter(
            (Event.reason.ilike(s_term)) | (Event.event_type.ilike(s_term)) | (Camera.name.ilike(s_term))
        )

    total = query.count()
    events = query.order_by(Event.timestamp.desc()).offset(offset).limit(limit).all()

    return EventListResponse(
        total=total,
        limit=limit,
        offset=offset,
        events=[_serialize_event_item(e) for e in events],
    )


@router.get("/events/{event_id}", response_model=EventItemResponse, tags=["Events"])
def get_event(event_id: int, db: Session = Depends(get_db)):
    """
    Retrieve single event details by canonical Event ID.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Event #{event_id} not found.")
    return _serialize_event_item(event)


@router.patch("/events/{event_id}", response_model=EventItemResponse, tags=["Events"])
def update_event_status(event_id: int, update: EventStatusUpdate, db: Session = Depends(get_db)):
    """
    Update the triage status of an event (NEW, ACKNOWLEDGED, RESOLVED).
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Event #{event_id} not found.")

    target_status = update.status.strip().upper()
    if target_status not in ["NEW", "ACKNOWLEDGED", "RESOLVED"]:
        raise HTTPException(status_code=400, detail="Status must be one of: NEW, ACKNOWLEDGED, RESOLVED")

    event.status = target_status
    db.commit()
    db.refresh(event)

    return _serialize_event_item(event)


@router.get("/events/{event_id}/evidence", tags=["Events"])
def get_event_evidence(event_id: int, db: Session = Depends(get_db)):
    """
    Safely retrieve captured evidence snapshot image for an event with path traversal protection.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Event #{event_id} not found.")
    if not event.evidence_path:
        raise HTTPException(status_code=404, detail="Evidence image not found or unavailable.")

    # Sanitize and verify relative path
    rel_path = event.evidence_path.replace("\\", "/").lstrip("/")
    if ".." in rel_path or rel_path.startswith("/") or "\x00" in rel_path:
        raise HTTPException(status_code=400, detail="Invalid evidence file path.")

    if rel_path.startswith("data/"):
        full_path = os.path.abspath(os.path.join(settings.ROOT_DIR, rel_path))
    else:
        full_path = os.path.abspath(os.path.join(settings.DATA_DIR, rel_path))

    allowed_root = os.path.abspath(settings.DATA_DIR)

    if not full_path.startswith(allowed_root):
        raise HTTPException(status_code=403, detail="Access to evidence path outside data directory is forbidden.")

    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="Evidence file does not exist on disk.")

    return FileResponse(full_path, media_type="image/jpeg")


@router.websocket("/ws/events")
async def websocket_events_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time security alert delivery.
    Connected clients receive normalized JSON event payloads.
    """
    try:
        connection_manager.set_loop(asyncio.get_running_loop())
    except Exception:
        pass
    await connection_manager.connect(websocket)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
            except asyncio.TimeoutError:
                await asyncio.sleep(0.01)
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception:
        connection_manager.disconnect(websocket)


