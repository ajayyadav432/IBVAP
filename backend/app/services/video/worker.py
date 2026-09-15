# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.video.worker
# Description: Background worker integrating video ingestion, YOLOX detection, ByteTrack tracking, and YuNet face detection.
# License: Apache-2.0
# ==============================================================================

import threading
import time
from typing import Optional, Dict, Any, Tuple, List
import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import camera_logger, video_logger, inference_logger
from app.services.video.source import VideoSource, VideoSourceStatus, create_video_source
from app.services.inference.detector import YOLOXDetector, Detection
from app.services.inference.annotator import draw_detections, draw_tracks, draw_faces, draw_anpr_plates, draw_zones
from app.services.tracking.tracker import ByteTrackTracker, Track
from app.services.face.detector import YuNetFaceDetector, Face
from app.services.anpr.engine import ANPREngine, ANPRResult
from app.services.zone import ZoneEngine, ZoneDefinition, IntrusionEventCandidate
from app.services.rules import SuspiciousActivityEngine, SuspiciousActivityCandidate
from app.services.events import event_engine, EventCandidate


# Shared model singletons across camera workers (avoids redundant VRAM allocations)
_shared_detector: Optional[YOLOXDetector] = None
_shared_face_detector: Optional[YuNetFaceDetector] = None
_shared_anpr_engine: Optional[ANPREngine] = None
_shared_models_lock = threading.Lock()


def get_shared_detector(conf_threshold: float = 0.40) -> Optional[YOLOXDetector]:
    global _shared_detector
    with _shared_models_lock:
        if _shared_detector is None:
            try:
                _shared_detector = YOLOXDetector(conf_threshold=conf_threshold)
            except Exception as exc:
                camera_logger.error(f"Failed to initialize shared YOLOX detector: {exc}")
        return _shared_detector


def get_shared_face_detector(conf_threshold: float = 0.50) -> Optional[YuNetFaceDetector]:
    global _shared_face_detector
    with _shared_models_lock:
        if _shared_face_detector is None:
            try:
                _shared_face_detector = YuNetFaceDetector(conf_threshold=conf_threshold)
            except Exception as exc:
                camera_logger.error(f"Failed to initialize shared YuNet face detector: {exc}")
        return _shared_face_detector


def get_shared_anpr_engine() -> Optional[ANPREngine]:
    global _shared_anpr_engine
    with _shared_models_lock:
        if _shared_anpr_engine is None:
            try:
                _shared_anpr_engine = ANPREngine(sample_interval=6, conf_threshold=0.40)
            except Exception as exc:
                camera_logger.error(f"Failed to initialize shared ANPR engine: {exc}")
        return _shared_anpr_engine


class CameraWorker:
    """
    Isolated background worker that continuously manages the video source lifecycle,
    ingests frames, runs YOLOX detection, ByteTrack tracking, YuNet face detection, and ANPR.
    """
    def __init__(
        self,
        camera_id: int,
        camera_name: str,
        source_type: str,
        source_uri: str,
        loop: bool = True,
        enable_detection: bool = True,
        enable_tracking: bool = True,
        enable_face_detection: bool = True,
        enable_anpr: bool = True,
        conf_threshold: Optional[float] = None,
    ):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.source_type = source_type
        self.source_uri = source_uri
        self.loop = loop
        self.enable_detection = enable_detection
        self.enable_person_detection = settings.PERSON_DETECTION_ENABLED
        self.enable_vehicle_detection = settings.VEHICLE_DETECTION_ENABLED
        self.enable_tracking = enable_tracking
        self.enable_face_detection = enable_face_detection
        self.enable_anpr = enable_anpr
        self.enable_suspicious_activity = settings.SUSPICIOUS_ACTIVITY_ENABLED
        self.conf_threshold = conf_threshold or settings.DETECTION_CONF_THRESHOLD

        self.source: VideoSource = create_video_source(source_type, source_uri, loop=loop)
        
        # Detector instance (shared)
        self._detector: Optional[YOLOXDetector] = None
        if self.enable_detection:
            self._detector = get_shared_detector(conf_threshold=self.conf_threshold)

        # ByteTrack multi-object tracker instance (per-camera state)
        self._tracker: Optional[ByteTrackTracker] = None
        if self.enable_tracking:
            try:
                self._tracker = ByteTrackTracker(
                    track_thresh=0.35,
                    high_thresh=0.45,
                    match_thresh=0.70,
                    track_buffer=30,
                )
            except Exception as exc:
                camera_logger.error(f"Tracker initialization failed for Camera #{self.camera_id}: {exc}")
                self._tracker = None

        # OpenCV YuNet Face Detector instance (shared)
        self._face_detector: Optional[YuNetFaceDetector] = None
        if self.enable_face_detection:
            self._face_detector = get_shared_face_detector(conf_threshold=0.50)

        # ANPR Engine instance (shared)
        self._anpr_engine: Optional[ANPREngine] = None
        if self.enable_anpr:
            self._anpr_engine = get_shared_anpr_engine()

        # Virtual Fence / Zone Engine instance
        self._zone_engine: Optional[ZoneEngine] = ZoneEngine(camera_id=self.camera_id, debounce_frames=2)

        # Suspicious Activity Rule Engine instance
        self._activity_engine: Optional[SuspiciousActivityEngine] = SuspiciousActivityEngine(
            camera_id=self.camera_id,
            loitering_threshold_sec=settings.LOITERING_THRESHOLD_SEC,
            night_movement_enabled=settings.NIGHT_MOVEMENT_ENABLED,
            night_start_time=settings.NIGHT_START_TIME,
            night_end_time=settings.NIGHT_END_TIME,
            night_cooldown_sec=settings.NIGHT_COOLDOWN_SEC,
        )

        # Thread & lifecycle controls
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Bounded frame and metadata buffers
        self._latest_raw_frame: Optional[np.ndarray] = None
        self._latest_annotated_frame: Optional[np.ndarray] = None
        self._latest_jpeg: Optional[bytes] = None
        self._latest_detections: List[Detection] = []
        self._latest_tracks: List[Track] = []
        self._latest_faces: List[Face] = []
        self._latest_anpr_results: List[ANPRResult] = []
        self._latest_intrusion_candidates: List[IntrusionEventCandidate] = []
        self._active_intrusions: Dict[int, List[int]] = {}
        self._latest_activities: List[SuspiciousActivityCandidate] = []
        
        # Metrics
        self._frame_counter: int = 0
        self._last_frame_timestamp: float = 0.0
        self._fps_counter: int = 0
        self._current_fps: float = 0.0
        self._fps_timer: float = time.time()
        self._inference_latency_ms: float = 0.0
        self._inference_fps: float = 0.0
        self._inf_counter: int = 0
        self._inf_timer: float = time.time()
        self._face_latency_ms: float = 0.0
        self._anpr_latency_ms: float = 0.0
        self._zone_latency_ms: float = 0.0
        self._activity_latency_ms: float = 0.0

        # Backoff parameters
        self._initial_backoff: float = 2.0
        self._max_backoff: float = 30.0
        self._current_backoff: float = self._initial_backoff
        self._retry_count: int = 0

    def start(self) -> None:
        """Start the background ingestion and inference thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"CameraWorker-{self.camera_id}-{self.camera_name}",
            daemon=True
        )
        self._thread.start()
        camera_logger.info(f"Started worker for Camera #{self.camera_id} ({self.camera_name}) [{self.source_type}]")

    def stop(self, timeout: float = 2.0) -> None:
        """Signal worker to stop and disconnect source."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self.source.disconnect()
        with self._lock:
            self._latest_raw_frame = None
            self._latest_annotated_frame = None
            self._latest_jpeg = None
            self._latest_detections = []
            self._latest_tracks = []
            self._latest_faces = []
            self._latest_anpr_results = []
            self._latest_intrusion_candidates = []
            self._active_intrusions = {}
        camera_logger.info(f"Stopped worker for Camera #{self.camera_id} ({self.camera_name})")

    def _run_loop(self) -> None:
        """Main camera worker execution loop."""
        while not self._stop_event.is_set():
            # Ensure connection is established
            if self.source.status != VideoSourceStatus.CONNECTED:
                connected = self._attempt_connect()
                if not connected:
                    if self._sleep_interruptible(self._current_backoff):
                        break
                    self._current_backoff = min(self._current_backoff * 1.5, self._max_backoff)
                    self._retry_count += 1
                    continue
                else:
                    self._current_backoff = self._initial_backoff
                    self._retry_count = 0

            # Connection is active: Read and process frames
            try:
                frame_start_time = time.time()
                success, raw_frame = self.source.read_frame()
                if success and raw_frame is not None:
                    self._frame_counter += 1
                    detections: List[Detection] = []
                    tracks: List[Track] = []
                    faces: List[Face] = []
                    anpr_results: List[ANPRResult] = []
                    intrusion_candidates: List[IntrusionEventCandidate] = []
                    active_intrusions: Dict[int, List[int]] = {}
                    annotated_frame = raw_frame
                    
                    is_det_frame = (self._frame_counter % max(1, settings.DETECTION_STRIDE) == 0)

                    # 1. YOLOX Object Detection & ByteTrack Tracking
                    if self.enable_detection and self._detector is not None:
                        if is_det_frame:
                            inf_start = time.time()
                            detections = self._detector.detect(raw_frame, conf_threshold=self.conf_threshold)
                            self._inference_latency_ms = round((time.time() - inf_start) * 1000.0, 1)
                            self._update_inference_metrics()

                            # Apply class-level toggles
                            if not self.enable_person_detection:
                                detections = [d for d in detections if d.class_name != "person"]
                            if not self.enable_vehicle_detection:
                                detections = [d for d in detections if d.class_name not in ("car", "truck", "bus", "motorcycle")]

                            # 2. ByteTrack Multi-Object Tracking (Full association)
                            if self.enable_tracking and self._tracker is not None:
                                try:
                                    tracks = self._tracker.update(detections)
                                except Exception as trk_err:
                                    inference_logger.error(f"Tracking error for Camera #{self.camera_id}: {trk_err}")
                                    tracks = []
                            else:
                                tracks = []
                        else:
                            # Non-detection frame: advance Kalman predictions for seamless high-FPS tracking
                            detections = self._latest_detections
                            if self.enable_tracking and self._tracker is not None:
                                try:
                                    tracks = self._tracker.predict_only()
                                except Exception as trk_err:
                                    inference_logger.error(f"Tracking prediction error for Camera #{self.camera_id}: {trk_err}")
                                    tracks = self._latest_tracks
                            else:
                                tracks = []

                    # 3. OpenCV YuNet Face Detection
                    is_face_frame = (self._frame_counter % max(1, settings.FACE_DETECTION_STRIDE) == 0)
                    if self.enable_face_detection and self._face_detector is not None:
                        if is_face_frame:
                            try:
                                f_start = time.time()
                                faces = self._face_detector.detect(raw_frame)
                                self._face_latency_ms = round((time.time() - f_start) * 1000.0, 1)
                            except Exception as face_err:
                                inference_logger.error(f"Face detection error for Camera #{self.camera_id}: {face_err}")
                                faces = []
                        else:
                            faces = self._latest_faces
                    else:
                        faces = []

                    # 4. Automatic Number Plate Recognition (ANPR) on Vehicle Tracks
                    if self.enable_anpr and self._anpr_engine is not None and tracks:
                        try:
                            anpr_start = time.time()
                            anpr_results = self._anpr_engine.process_tracks(
                                frame=raw_frame,
                                tracks=tracks,
                                frame_idx=self._frame_counter,
                                camera_id=self.camera_id,
                            )
                            self._anpr_latency_ms = round((time.time() - anpr_start) * 1000.0, 1)
                        except Exception as anpr_err:
                            inference_logger.error(f"ANPR execution error for Camera #{self.camera_id}: {anpr_err}")
                            anpr_results = []
                    else:
                        anpr_results = []

                    # 5. Virtual Fence / Zone Engine Evaluation on Tracked Objects
                    if self._zone_engine is not None and tracks:
                        try:
                            z_start = time.time()
                            intrusion_candidates = self._zone_engine.process_tracks(
                                tracks=tracks,
                                frame_width=raw_frame.shape[1],
                                frame_height=raw_frame.shape[0],
                                frame_idx=self._frame_counter,
                            )
                            self._zone_latency_ms = round((time.time() - z_start) * 1000.0, 2)
                            active_intrusions = self._zone_engine.get_active_intrusions()
                        except Exception as z_err:
                            inference_logger.error(f"Zone processing error for Camera #{self.camera_id}: {z_err}")
                            intrusion_candidates = []
                            active_intrusions = {}

                    # 6. Suspicious Activity Detection Rules (Restricted Intrusion & Loitering)
                    activity_candidates: List[SuspiciousActivityCandidate] = []
                    if self.enable_suspicious_activity and self._activity_engine is not None and tracks:
                        try:
                            act_start = time.time()
                            configured_zones = self._zone_engine.get_zones() if self._zone_engine else []
                            activity_candidates = self._activity_engine.process(
                                tracks=tracks,
                                zones=configured_zones,
                                zone_candidates=intrusion_candidates,
                                frame_time=time.time(),
                                timestamp_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                frame_idx=self._frame_counter,
                            )
                            self._activity_latency_ms = round((time.time() - act_start) * 1000.0, 2)
                        except Exception as act_err:
                            inference_logger.error(f"Activity rule engine error for Camera #{self.camera_id}: {act_err}")
                            activity_candidates = []

                    # 7. Render Composite Annotation Overlays
                    configured_zones = self._zone_engine.get_zones() if self._zone_engine else []
                    if tracks or faces or anpr_results or configured_zones:
                        annotated_frame = draw_tracks(
                            raw_frame,
                            tracks,
                            faces=faces,
                            anpr_results=anpr_results,
                            zones=configured_zones,
                            active_intrusions=active_intrusions
                        )
                    elif detections:
                        annotated_frame = draw_detections(raw_frame, detections, faces=faces)

                    # 8. Centralized Event Engine Dispatch
                    if activity_candidates:
                        for act in activity_candidates:
                            try:
                                cand = EventCandidate(
                                    event_type=act.event_type,
                                    camera_id=self.camera_id,
                                    reason=act.reason,
                                    timestamp=act.timestamp,
                                    severity=act.severity,
                                    object_type=act.object_type,
                                    track_id=act.track_id,
                                    zone_id=act.zone_id,
                                    confidence=act.confidence,
                                    metadata=act.metadata,
                                )
                                event_engine.process_candidate(cand, frame=annotated_frame)
                            except Exception as ev_err:
                                inference_logger.error(f"Error dispatching activity candidate to EventEngine: {ev_err}")

                    if anpr_results:
                        for anpr in anpr_results:
                            if anpr.quality in ("HIGH", "MEDIUM"):
                                try:
                                    cand = EventCandidate(
                                        event_type="ANPR_DETECTED",
                                        camera_id=self.camera_id,
                                        reason=f"License plate {anpr.plate_text} detected ({anpr.quality} quality)",
                                        timestamp=anpr.timestamp,
                                        severity="INFO",
                                        object_type=anpr.vehicle_type,
                                        track_id=anpr.track_id,
                                        confidence=anpr.confidence,
                                        metadata={"plate_text": anpr.plate_text, "quality": anpr.quality},
                                    )
                                    event_engine.process_candidate(cand, frame=annotated_frame)
                                except Exception as ev_err:
                                    inference_logger.error(f"Error dispatching ANPR candidate to EventEngine: {ev_err}")

                    with self._lock:
                        self._latest_raw_frame = raw_frame
                        self._latest_annotated_frame = annotated_frame
                        self._latest_detections = detections
                        self._latest_tracks = tracks
                        self._latest_faces = faces
                        self._latest_anpr_results = anpr_results
                        self._latest_intrusion_candidates = intrusion_candidates
                        self._active_intrusions = active_intrusions
                        self._latest_activities = activity_candidates
                        self._latest_jpeg = None  # Invalidate cached JPEG
                        self._last_frame_timestamp = time.time()
                    
                    self._update_fps_metrics()

                    # Dynamic pacing: only sleep if processing finished ahead of target frame time
                    target_fps = self.source.fps if self.source.fps > 0 else 25.0
                    target_delay = 1.0 / target_fps
                    elapsed = time.time() - frame_start_time
                    remaining_sleep = target_delay - elapsed
                    if remaining_sleep > 0.001:
                        time.sleep(remaining_sleep)
                    else:
                        time.sleep(0.0005)
                else:
                    camera_logger.warning(
                        f"Frame read failed for Camera #{self.camera_id}. Transitioning to reconnect backoff."
                    )
                    self.source.disconnect()
                    self._sleep_interruptible(self._current_backoff)
            except Exception as exc:
                camera_logger.error(
                    f"Unexpected exception in CameraWorker #{self.camera_id}: {exc}"
                )
                self.source.disconnect()
                self._sleep_interruptible(self._current_backoff)

        self.source.disconnect()

    def _attempt_connect(self) -> bool:
        """Safely attempt source connection."""
        try:
            return self.source.connect()
        except Exception as exc:
            camera_logger.error(f"Connection attempt failed for Camera #{self.camera_id}: {exc}")
            return False

    def _sleep_interruptible(self, duration: float) -> bool:
        """Sleep for `duration` seconds while checking `_stop_event`."""
        end_time = time.time() + duration
        while time.time() < end_time:
            if self._stop_event.is_set():
                return True
            time.sleep(0.1)
        return False

    def _update_fps_metrics(self) -> None:
        """Track measured input FPS over 1-second intervals."""
        self._fps_counter += 1
        now = time.time()
        elapsed = now - self._fps_timer
        if elapsed >= 1.0:
            self._current_fps = round(self._fps_counter / elapsed, 1)
            self._fps_counter = 0
            self._fps_timer = now

    def _update_inference_metrics(self) -> None:
        """Track measured inference FPS."""
        self._inf_counter += 1
        now = time.time()
        elapsed = now - self._inf_timer
        if elapsed >= 1.0:
            self._inference_fps = round(self._inf_counter / elapsed, 1)
            self._inf_counter = 0
            self._inf_timer = now

    def get_latest_frame(self, annotated: bool = True) -> Optional[np.ndarray]:
        """Thread-safe getter for the current frame."""
        with self._lock:
            frame = self._latest_annotated_frame if annotated else self._latest_raw_frame
            if frame is None:
                return None
            return frame.copy()

    def get_latest_detections(self) -> List[Detection]:
        """Thread-safe getter for current raw detection objects."""
        with self._lock:
            return list(self._latest_detections)

    def get_latest_tracks(self) -> List[Track]:
        """Thread-safe getter for active Track objects."""
        with self._lock:
            return list(self._latest_tracks)

    def get_latest_faces(self) -> List[Face]:
        """Thread-safe getter for current detected Face objects."""
        with self._lock:
            return list(self._latest_faces)

    def get_latest_anpr_results(self) -> List[ANPRResult]:
        """Thread-safe getter for current recognized ANPR plate results."""
        with self._lock:
            return list(self._latest_anpr_results)

    def get_latest_anpr(self) -> List[Dict[str, Any]]:
        """Thread-safe getter for current recognized ANPR plate results as dictionaries."""
        with self._lock:
            return [r.to_dict() for r in self._latest_anpr_results]

    def get_latest_intrusion_candidates(self) -> List[IntrusionEventCandidate]:
        """Thread-safe getter for latest zone intrusion candidate events."""
        with self._lock:
            return list(self._latest_intrusion_candidates)

    def get_latest_activities(self) -> List[SuspiciousActivityCandidate]:
        """Thread-safe getter for latest suspicious activity candidate events (Intrusion + Loitering)."""
        with self._lock:
            return list(self._latest_activities)

    def get_active_loitering_states(self) -> List[Dict[str, Any]]:
        """Getter for active dwell/loitering timers."""
        if self._activity_engine:
            return self._activity_engine.get_active_loitering_states()
        return []

    def set_loitering_threshold(self, threshold_sec: float) -> None:
        """Update loitering duration threshold."""
        if self._activity_engine:
            self._activity_engine.set_loitering_threshold(threshold_sec)

    def set_zones(self, zones: List[ZoneDefinition]) -> None:
        """Update active zones on the camera worker."""
        if self._zone_engine:
            self._zone_engine.set_zones(zones)

    def add_zone(self, zone: ZoneDefinition) -> bool:
        """Add a single zone definition to the worker's zone engine."""
        if self._zone_engine:
            return self._zone_engine.add_zone(zone)
        return False

    def remove_zone(self, zone_id: int) -> None:
        """Remove a zone definition from the worker's zone engine."""
        if self._zone_engine:
            self._zone_engine.remove_zone(zone_id)

    def get_zones(self) -> List[ZoneDefinition]:
        """Get all zones configured on this worker."""
        if self._zone_engine:
            return self._zone_engine.get_zones()
        return []

    def toggle_face_detection(self, enabled: bool) -> None:
        """Toggle YuNet face detection execution at runtime."""
        self.enable_face_detection = bool(enabled)
        if self.enable_face_detection and self._face_detector is None:
            try:
                self._face_detector = YuNetFaceDetector(conf_threshold=0.50)
            except Exception as exc:
                camera_logger.error(f"Failed to enable face detector: {exc}")

    def toggle_anpr(self, enabled: bool) -> None:
        """Toggle ANPR execution at runtime."""
        self.enable_anpr = bool(enabled)
        if self.enable_anpr and self._anpr_engine is None:
            try:
                self._anpr_engine = ANPREngine(sample_interval=6, conf_threshold=0.40)
            except Exception as exc:
                camera_logger.error(f"Failed to enable ANPR engine: {exc}")

    def get_latest_jpeg(self, quality: int = 80, annotated: bool = True) -> Optional[bytes]:
        """Thread-safe getter for JPEG encoded frame byte representation."""
        with self._lock:
            if self._latest_jpeg is not None and annotated:
                return self._latest_jpeg
            
            frame = self._latest_annotated_frame if annotated else self._latest_raw_frame
            if frame is None:
                return None

            try:
                ret, buffer = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), quality]
                )
                if ret:
                    jpeg = buffer.tobytes()
                    if annotated:
                        self._latest_jpeg = jpeg
                    return jpeg
            except Exception as exc:
                video_logger.error(f"JPEG encoding error in CameraWorker #{self.camera_id}: {exc}")
            return None

    def set_conf_threshold(self, threshold: float) -> None:
        """Update detection confidence threshold on the fly."""
        val = max(0.01, min(1.0, float(threshold)))
        self.conf_threshold = val
        if self._detector:
            self._detector.conf_threshold = val

    def set_loitering_threshold(self, threshold_sec: float) -> None:
        """Update loitering duration threshold dynamically."""
        val = max(1.0, float(threshold_sec))
        if self._activity_engine:
            self._activity_engine.set_loitering_threshold(val)

    def set_night_movement_config(
        self,
        enabled: Optional[bool] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        cooldown_sec: Optional[float] = None,
    ) -> None:
        """Update night movement schedule and parameters dynamically."""
        if self._activity_engine:
            self._activity_engine.set_night_movement_config(
                enabled=enabled,
                start_time=start_time,
                end_time=end_time,
                cooldown_sec=cooldown_sec,
            )

    def set_analytics_config(
        self,
        person_detection_enabled: Optional[bool] = None,
        vehicle_detection_enabled: Optional[bool] = None,
        tracking_enabled: Optional[bool] = None,
        face_detection_enabled: Optional[bool] = None,
        anpr_enabled: Optional[bool] = None,
        suspicious_activity_enabled: Optional[bool] = None,
    ) -> None:
        """Update analytics feature toggles on the fly."""
        with self._lock:
            if person_detection_enabled is not None:
                self.enable_person_detection = person_detection_enabled
            if vehicle_detection_enabled is not None:
                self.enable_vehicle_detection = vehicle_detection_enabled
            if tracking_enabled is not None:
                self.enable_tracking = tracking_enabled
            if face_detection_enabled is not None:
                self.enable_face_detection = face_detection_enabled
                if self.enable_face_detection and self._face_detector is None:
                    try:
                        self._face_detector = YuNetFaceDetector(conf_threshold=0.50)
                    except Exception:
                        pass
            if anpr_enabled is not None:
                self.enable_anpr = anpr_enabled
                if self.enable_anpr and self._anpr_engine is None:
                    try:
                        self._anpr_engine = ANPREngine(sample_interval=6, conf_threshold=0.40)
                    except Exception:
                        pass
            if suspicious_activity_enabled is not None:
                self.enable_suspicious_activity = suspicious_activity_enabled

    def get_status_info(self) -> Dict[str, Any]:
        """Return comprehensive status, inference telemetry, active detections, tracks, faces, ANPR, zones, and suspicious activities."""
        source_info = self.source.get_info()
        with self._lock:
            detections_summary = [d.to_dict() for d in self._latest_detections]
            tracks_summary = [t.to_dict() for t in self._latest_tracks]
            faces_summary = [f.to_dict() for f in self._latest_faces]
            anpr_summary = [a.to_dict() for a in self._latest_anpr_results]
            intrusions_summary = [i.to_dict() for i in self._latest_intrusion_candidates]
            active_intrusions_summary = dict(self._active_intrusions)
            activities_summary = [a.to_dict() for a in self._latest_activities]
            
            person_detections = sum(1 for d in self._latest_detections if d.class_name == "person")
            vehicle_detections = sum(1 for d in self._latest_detections if d.class_name in ("car", "motorcycle", "bus", "truck"))

            person_tracks = sum(1 for t in self._latest_tracks if t.object_type == "person")
            vehicle_tracks = sum(1 for t in self._latest_tracks if t.object_type in ("car", "motorcycle", "bus", "truck"))

        model_info = self._detector.get_model_info() if self._detector else {}
        face_model_info = self._face_detector.get_model_info() if self._face_detector else {}
        zones_list = [z.to_dict() for z in self._zone_engine.get_zones()] if self._zone_engine else []
        active_loitering_list = self._activity_engine.get_active_loitering_states() if self._activity_engine else []

        return {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "source_type": self.source_type,
            "status": self.source.status,
            "error_message": self.source.error_message,
            "measured_fps": self._current_fps,
            "source_fps": self.source.fps,
            "resolution": source_info["resolution"],
            "frame_count": self.source.frame_count,
            "last_frame_time": self._last_frame_timestamp,
            "retry_count": self._retry_count,
            "is_running": self._thread.is_alive() if self._thread else False,
            "inference_device": model_info.get("device", "CPU"),
            "inference_latency_ms": self._inference_latency_ms,
            "inference_fps": self._inference_fps,
            "face_latency_ms": self._face_latency_ms,
            "anpr_latency_ms": self._anpr_latency_ms,
            "zone_latency_ms": self._zone_latency_ms,
            "activity_latency_ms": self._activity_latency_ms,
            "confidence_threshold": self.conf_threshold,
            "detections": detections_summary,
            "detection_counts": {
                "total": len(detections_summary),
                "person": person_detections,
                "vehicle": vehicle_detections,
            },
            "tracks": tracks_summary,
            "tracking_counts": {
                "total_active_tracks": len(tracks_summary),
                "tracked_persons": person_tracks,
                "tracked_vehicles": vehicle_tracks,
            },
            "faces": faces_summary,
            "faces_count": len(faces_summary),
            "anpr_results": anpr_summary,
            "anpr_count": len(anpr_summary),
            "zones": zones_list,
            "zones_count": len(zones_list),
            "intrusion_candidates": intrusions_summary,
            "active_intrusions": active_intrusions_summary,
            "activities": activities_summary,
            "activities_count": len(activities_summary),
            "active_loitering": active_loitering_list,
            "tracker_engine": "ByteTrack" if self.enable_tracking else "DISABLED",
            "face_engine": "OpenCV YuNet" if self.enable_face_detection else "DISABLED",
            "anpr_engine": "RapidOCR + PP-OCRv4 (ONNX)" if self.enable_anpr else "DISABLED",
            "zone_engine": "Point-in-Polygon (Ray-Casting)" if self._zone_engine else "DISABLED",
            "activity_engine": "RuleEngine (Intrusion + Loitering + Night)" if self._activity_engine else "DISABLED",
        }

    @property
    def activity_engine(self) -> Optional[SuspiciousActivityEngine]:
        """Accessor for the worker's SuspiciousActivityEngine instance."""
        return self._activity_engine



