from abc import ABC, abstractmethod
import os
from pathlib import Path
import time
from typing import Dict, Optional, Tuple, Any
import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import video_logger, camera_logger


class VideoSourceStatus:
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"
    STOPPED = "STOPPED"


class VideoSource(ABC):
    """
    Abstract base class for normalized video ingestion.
    All sources (File, Webcam, RTSP) adhere to this contract.
    """
    def __init__(self, source_type: str, source_uri: str):
        self.source_type = source_type.upper()
        self.source_uri = source_uri
        self.status: str = VideoSourceStatus.DISCONNECTED
        self.error_message: Optional[str] = None
        self.fps: float = 0.0
        self.width: int = 0
        self.height: int = 0
        self.frame_count: int = 0
        self.last_frame_time: float = 0.0

    @abstractmethod
    def connect(self) -> bool:
        """Attempt to establish video stream connection."""
        pass

    @abstractmethod
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read the next available video frame."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close stream and release hardware/file resources."""
        pass

    def get_status(self) -> str:
        return self.status

    def get_info(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "status": self.status,
            "error_message": self.error_message,
            "fps": self.fps,
            "resolution": f"{self.width}x{self.height}" if self.width and self.height else "Unknown",
            "frame_count": self.frame_count,
        }


class FileSource(VideoSource):
    """
    Video file source (MP4/AVI/MKV) for deterministic demo, testing, and offline analysis.
    """
    def __init__(self, source_uri: str, loop: bool = True):
        super().__init__(source_type="VIDEO_FILE", source_uri=source_uri)
        self.loop = loop
        self._cap: Optional[cv2.VideoCapture] = None
        self._resolved_path: Optional[Path] = None

    def _resolve_file_path(self) -> Optional[Path]:
        path = Path(self.source_uri)
        if path.is_absolute() and path.exists():
            return path
        
        # Check relative to ROOT_DIR
        candidate = settings.ROOT_DIR / self.source_uri.lstrip("./")
        if candidate.exists():
            return candidate
        
        # Check in data/demo/
        demo_candidate = settings.DATA_DIR / "demo" / Path(self.source_uri).name
        if demo_candidate.exists():
            return demo_candidate
        
        return None

    def connect(self) -> bool:
        self.status = VideoSourceStatus.CONNECTING
        self.error_message = None
        resolved = self._resolve_file_path()
        if not resolved or not resolved.is_file():
            self.status = VideoSourceStatus.ERROR
            self.error_message = f"Video file not found: {self.source_uri}"
            video_logger.error(self.error_message)
            return False

        self._resolved_path = resolved
        try:
            self._cap = cv2.VideoCapture(str(resolved))
            if not self._cap.isOpened():
                self.status = VideoSourceStatus.ERROR
                self.error_message = f"Failed to open video file codec: {resolved.name}"
                video_logger.error(self.error_message)
                return False

            self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = float(self._cap.get(cv2.CAP_PROP_FPS)) or 25.0
            self.status = VideoSourceStatus.CONNECTED
            video_logger.info(f"FileSource connected: {resolved.name} ({self.width}x{self.height} @ {self.fps:.1f}fps)")
            return True
        except Exception as exc:
            self.status = VideoSourceStatus.ERROR
            self.error_message = f"FileSource connection exception: {exc}"
            video_logger.error(self.error_message)
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self._cap or not self._cap.isOpened() or self.status != VideoSourceStatus.CONNECTED:
            return False, None

        ret, frame = self._cap.read()
        if not ret or frame is None:
            if self.loop and self._cap.isOpened():
                # Rewind to frame 0
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
                if ret and frame is not None:
                    self.frame_count += 1
                    self.last_frame_time = time.time()
                    return True, frame
            
            # EOF reached and not loop or rewind failed
            self.status = VideoSourceStatus.DISCONNECTED
            return False, None

        self.frame_count += 1
        self.last_frame_time = time.time()
        return True, frame

    def disconnect(self) -> None:
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self.status = VideoSourceStatus.STOPPED
        video_logger.info(f"FileSource disconnected: {self.source_uri}")


class WebcamSource(VideoSource):
    """
    Local webcam / USB capture device ingestion.
    """
    def __init__(self, source_uri: str = "0"):
        super().__init__(source_type="WEBCAM", source_uri=source_uri)
        self._cap: Optional[cv2.VideoCapture] = None
        self._device_index: int = 0
        try:
            self._device_index = int(source_uri)
        except ValueError:
            self._device_index = 0

    def connect(self) -> bool:
        self.status = VideoSourceStatus.CONNECTING
        self.error_message = None
        try:
            # Attempt to open local capture device
            self._cap = cv2.VideoCapture(self._device_index)
            if not self._cap.isOpened():
                self.status = VideoSourceStatus.ERROR
                self.error_message = f"Webcam device index {self._device_index} unavailable or busy."
                video_logger.warning(self.error_message)
                return False

            self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
            self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
            self.fps = float(self._cap.get(cv2.CAP_PROP_FPS)) or 30.0
            self.status = VideoSourceStatus.CONNECTED
            video_logger.info(f"WebcamSource connected on device {self._device_index} ({self.width}x{self.height})")
            return True
        except Exception as exc:
            self.status = VideoSourceStatus.ERROR
            self.error_message = f"Webcam exception: {exc}"
            video_logger.error(self.error_message)
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self._cap or not self._cap.isOpened() or self.status != VideoSourceStatus.CONNECTED:
            return False, None

        ret, frame = self._cap.read()
        if not ret or frame is None:
            self.status = VideoSourceStatus.ERROR
            self.error_message = "Webcam frame capture failed."
            return False, None

        self.frame_count += 1
        self.last_frame_time = time.time()
        return True, frame

    def disconnect(self) -> None:
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self.status = VideoSourceStatus.STOPPED
        video_logger.info(f"WebcamSource device {self._device_index} disconnected.")


class RTSPSource(VideoSource):
    """
    RTSP / IP CCTV camera stream ingestion.
    Credentials remain exclusively on the backend and are never exposed.
    """
    def __init__(self, source_uri: str):
        super().__init__(source_type="RTSP", source_uri=source_uri)
        self._cap: Optional[cv2.VideoCapture] = None

    def connect(self) -> bool:
        self.status = VideoSourceStatus.CONNECTING
        self.error_message = None
        if not self.source_uri or not self.source_uri.lower().startswith(("rtsp://", "http://", "https://")):
            self.status = VideoSourceStatus.ERROR
            self.error_message = "Invalid RTSP/IP stream URL format."
            video_logger.error("Invalid RTSP URL format provided.")
            return False

        try:
            # OpenCV RTSP Capture with FFmpeg backend
            # Configure network timeouts via OS environment or cv2 properties if supported
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000"
            self._cap = cv2.VideoCapture(self.source_uri, cv2.CAP_FFMPEG)
            
            if not self._cap.isOpened():
                self.status = VideoSourceStatus.ERROR
                self.error_message = "Could not connect to RTSP stream. Check URL, network, or credentials."
                video_logger.error("RTSP stream connection failed.")
                return False

            self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
            self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
            self.fps = float(self._cap.get(cv2.CAP_PROP_FPS)) or 25.0
            self.status = VideoSourceStatus.CONNECTED
            video_logger.info(f"RTSPSource connected ({self.width}x{self.height} @ {self.fps:.1f}fps)")
            return True
        except Exception as exc:
            self.status = VideoSourceStatus.ERROR
            self.error_message = f"RTSP connection exception: {exc}"
            video_logger.error(f"RTSP connection error: {exc}")
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self._cap or not self._cap.isOpened() or self.status != VideoSourceStatus.CONNECTED:
            return False, None

        ret, frame = self._cap.read()
        if not ret or frame is None:
            self.status = VideoSourceStatus.ERROR
            self.error_message = "RTSP frame read timeout or corrupted packet."
            return False, None

        self.frame_count += 1
        self.last_frame_time = time.time()
        return True, frame

    def disconnect(self) -> None:
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self.status = VideoSourceStatus.STOPPED
        video_logger.info("RTSPSource disconnected.")


def create_video_source(source_type: str, source_uri: str, loop: bool = True) -> VideoSource:
    """Factory helper to instantiate the appropriate VideoSource implementation."""
    stype = source_type.upper().strip()
    if stype in ("VIDEO_FILE", "FILE", "MP4", "SAMPLE_VIDEO", "DEMO"):
        return FileSource(source_uri=source_uri, loop=loop)
    elif stype in ("WEBCAM", "USB"):
        return WebcamSource(source_uri=source_uri)
    elif stype in ("RTSP", "IP_CAMERA", "STREAM", "HTTP"):
        return RTSPSource(source_uri=source_uri)
    else:
        raise ValueError(f"Unsupported video source type: {source_type}")
