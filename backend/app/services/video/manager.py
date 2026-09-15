import threading
import time
from typing import Dict, List, Optional, Tuple, Any, Generator
import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import camera_logger, video_logger
from app.services.video.source import VideoSourceStatus, create_video_source
from app.services.video.worker import CameraWorker


class CameraManager:
    """
    Central manager coordinating all active CameraWorkers, MJPEG stream generation,
    and source connectivity probes.
    """
    _instance: Optional["CameraManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "CameraManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._workers: Dict[int, CameraWorker] = {}
        self._workers_lock = threading.Lock()
        self._initialized = True

    def register_camera(
        self,
        camera_id: int,
        name: str,
        source_type: str,
        source_uri: str,
        enabled: bool = True,
        loop: bool = True,
        enable_detection: bool = True,
        enable_face_detection: bool = True,
        enable_anpr: bool = True,
        conf_threshold: Optional[float] = None,
    ) -> CameraWorker:
        """Register and optionally start a camera worker."""
        with self._workers_lock:
            # Stop existing worker if present
            if camera_id in self._workers:
                self._workers[camera_id].stop()

            worker = CameraWorker(
                camera_id=camera_id,
                camera_name=name,
                source_type=source_type,
                source_uri=source_uri,
                loop=loop,
                enable_detection=enable_detection,
                enable_face_detection=enable_face_detection,
                enable_anpr=enable_anpr,
                conf_threshold=conf_threshold,
            )
            self._workers[camera_id] = worker
            if enabled:
                worker.start()
            return worker

    def unregister_camera(self, camera_id: int) -> None:
        """Stop and remove camera worker."""
        with self._workers_lock:
            if camera_id in self._workers:
                worker = self._workers.pop(camera_id)
                worker.stop()

    def get_worker(self, camera_id: int) -> Optional[CameraWorker]:
        """Get the active worker instance for a camera."""
        with self._workers_lock:
            return self._workers.get(camera_id)

    def get_all_workers(self) -> List[CameraWorker]:
        """Return list of all registered CameraWorker instances."""
        with self._workers_lock:
            return list(self._workers.values())

    def reload_camera_zones(self, camera_id: int, zones_list: Optional[List[Any]] = None) -> None:
        """Dynamically reload configured zones into the camera worker."""
        worker = self.get_worker(camera_id)
        if not worker:
            return
        
        if zones_list is not None:
            from app.services.zone.models import ZoneDefinition
            zone_defs = [
                ZoneDefinition.from_orm(z) if hasattr(z, "polygon_json") else z
                for z in zones_list
            ]
            worker.set_zones(zone_defs)

    def get_camera_status(self, camera_id: int) -> Dict[str, Any]:
        """Fetch live status of a camera."""
        worker = self.get_worker(camera_id)
        if worker:
            return worker.get_status_info()
        return {
            "camera_id": camera_id,
            "status": VideoSourceStatus.DISCONNECTED,
            "error_message": "Worker not registered or camera disabled.",
            "is_running": False,
        }

    def stop_all(self) -> None:
        """Cleanly stop all active camera workers."""
        with self._workers_lock:
            for worker in self._workers.values():
                worker.stop()
            self._workers.clear()
        camera_logger.info("All camera workers stopped.")

    def broadcast_analytics_config(
        self,
        person_detection_enabled: Optional[bool] = None,
        vehicle_detection_enabled: Optional[bool] = None,
        tracking_enabled: Optional[bool] = None,
        face_detection_enabled: Optional[bool] = None,
        anpr_enabled: Optional[bool] = None,
        suspicious_activity_enabled: Optional[bool] = None,
    ) -> None:
        """Propagate analytics toggle updates to all active workers."""
        for worker in self.get_all_workers():
            worker.set_analytics_config(
                person_detection_enabled=person_detection_enabled,
                vehicle_detection_enabled=vehicle_detection_enabled,
                tracking_enabled=tracking_enabled,
                face_detection_enabled=face_detection_enabled,
                anpr_enabled=anpr_enabled,
                suspicious_activity_enabled=suspicious_activity_enabled,
            )

    def broadcast_conf_threshold(self, threshold: float) -> None:
        """Propagate detection confidence threshold update to all active workers."""
        for worker in self.get_all_workers():
            worker.set_conf_threshold(threshold)

    def broadcast_loitering_threshold(self, threshold_sec: float) -> None:
        """Propagate loitering threshold update to all active workers."""
        for worker in self.get_all_workers():
            worker.set_loitering_threshold(threshold_sec)

    def broadcast_night_movement_config(
        self,
        enabled: Optional[bool] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        cooldown_sec: Optional[float] = None,
    ) -> None:
        """Propagate night schedule update to all active workers."""
        for worker in self.get_all_workers():
            worker.set_night_movement_config(
                enabled=enabled,
                start_time=start_time,
                end_time=end_time,
                cooldown_sec=cooldown_sec,
            )

    def test_connection(self, source_type: str, source_uri: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Synchronously probe video source reachability without registering a worker.
        """
        camera_logger.info(f"Testing connectivity for probe source: [{source_type}]")
        try:
            source = create_video_source(source_type=source_type, source_uri=source_uri, loop=False)
            connected = source.connect()
            if not connected:
                msg = source.error_message or "Could not connect to the video stream. Check the URL, credentials and network reachability."
                return False, msg, source.get_info()

            # Attempt single test frame read
            success, frame = source.read_frame()
            source.disconnect()

            if success and frame is not None:
                info = source.get_info()
                return True, f"Successfully connected. Stream: {info['resolution']} @ {info['fps']:.1f} FPS", info
            else:
                return False, "Could not decode video stream. Check source format and reachability.", source.get_info()
        except Exception as exc:
            camera_logger.error(f"Test probe exception: {exc}")
            return False, "Could not connect to the stream. Check URL, credentials and network reachability.", {}

    def get_placeholder_jpeg(self, text: str = "NO ACTIVE FEED", subtext: str = "IBVAP Security Hub") -> bytes:
        """Generate a clean dark control-room placeholder frame."""
        width, height = 640, 360
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:] = (15, 15, 15)  # Dark surface #151515

        # Border outline in #2A2A2A
        cv2.rectangle(img, (2, 2), (width - 3, height - 3), (42, 42, 42), 1)

        # Center indicator
        cv2.circle(img, (width // 2, height // 2 - 30), 28, (25, 25, 25), -1)
        cv2.circle(img, (width // 2, height // 2 - 30), 28, (24, 17, 255), 2)  # Red ring

        # Text labels
        cv2.putText(img, "IBVAP", (width // 2 - 24, height // 2 - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.putText(img, text, (width // 2 - int(len(text) * 4.5), height // 2 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(img, subtext, (width // 2 - int(len(subtext) * 3.5), height // 2 + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (160, 160, 160), 1)

        ret, buffer = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        return buffer.tobytes() if ret else b""

    def generate_mjpeg_stream(
        self, camera_id: int, target_fps: Optional[int] = None
    ) -> Generator[bytes, None, None]:
        """
        Yield multipart MJPEG chunks for real-time browser preview streaming.
        """
        active_target_fps = target_fps or getattr(settings, "MJPEG_TARGET_FPS", 25)
        frame_interval = 1.0 / max(1, active_target_fps)

        while True:
            worker = self.get_worker(camera_id)
            jpeg_bytes: Optional[bytes] = None

            if worker and worker.source.status == VideoSourceStatus.CONNECTED:
                jpeg_bytes = worker.get_latest_jpeg()

            if jpeg_bytes is None:
                # Provide placeholder if disconnected or connecting
                status_text = worker.source.status if worker else "OFFLINE"
                jpeg_bytes = self.get_placeholder_jpeg(
                    text=f"CAM #{camera_id} [{status_text}]",
                    subtext="Waiting for stream connection..."
                )

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
            )
            time.sleep(frame_interval)


camera_manager = CameraManager()
