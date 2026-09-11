from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import threading
import time
import cv2
import numpy as np
import onnxruntime as ort

from app.core.config import settings
from app.core.logging import inference_logger, model_logger

# Standard COCO 80 Class Names
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

# Target Classes for Surveillance MVP
SURVEILLANCE_TARGET_CLASSES = {
    "person", "car", "motorcycle", "bus", "truck", "bicycle"
}


@dataclass
class Detection:
    """Normalized object detection structure."""
    class_id: int
    class_name: str
    confidence: float
    bbox: List[int]  # [x1, y1, x2, y2]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(float(self.confidence), 4),
            "bbox": [int(v) for v in self.bbox],
        }


class Detector(ABC):
    """Abstract base class for object detectors."""
    
    @abstractmethod
    def detect(self, frame: np.ndarray, conf_threshold: Optional[float] = None) -> List[Detection]:
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        pass


class YOLOXDetector(Detector):
    """
    YOLOX Object Detector implementation using ONNX Runtime.
    Performs Letterbox preprocessing, grid decoding, and Non-Maximum Suppression (NMS).
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        input_size: Tuple[int, int] = (416, 416),
        conf_threshold: float = 0.40,
        nms_threshold: float = 0.45,
    ):
        self.model_path = Path(model_path or settings.YOLOX_MODEL_PATH)
        self.input_size = input_size
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        self.session: Optional[ort.InferenceSession] = None
        self.input_name: str = ""
        self.output_name: str = ""
        self.device: str = "CPU"
        self.load_time_ms: float = 0.0
        self._lock = threading.Lock()

        # Precompute anchor grids and strides for YOLOX decoding
        self._init_grids()
        self._load_model()

    def _init_grids(self) -> None:
        """Precompute meshgrids and strides for multi-level FPN outputs (8, 16, 32)."""
        strides = [8, 16, 32]
        grids = []
        expanded_strides = []
        for stride in strides:
            feat_h = self.input_size[0] // stride
            feat_w = self.input_size[1] // stride
            grid_y, grid_x = np.meshgrid(np.arange(feat_h), np.arange(feat_w), indexing="ij")
            grid = np.stack((grid_x, grid_y), 2).reshape(-1, 2)
            grids.append(grid)
            expanded_strides.append(np.full((grid.shape[0], 1), stride))
        self.grids = np.concatenate(grids, axis=0)
        self.expanded_strides = np.concatenate(expanded_strides, axis=0)

    def _load_model(self) -> None:
        start_t = time.time()
        if not self.model_path.exists():
            err_msg = f"YOLOX model file not found at: {self.model_path}"
            model_logger.error(err_msg)
            raise FileNotFoundError(err_msg)

        # Detect Execution Providers (TensorRT / CUDA / DirectML GPU if available, fallback to CPU)
        available_providers = ort.get_available_providers()
        selected_providers = []
        if "TensorrtExecutionProvider" in available_providers:
            selected_providers.append("TensorrtExecutionProvider")
            self.device = "NVIDIA TensorRT"
        if "CUDAExecutionProvider" in available_providers:
            selected_providers.append("CUDAExecutionProvider")
            self.device = "NVIDIA GPU (CUDA)"
        if "DmlExecutionProvider" in available_providers:
            selected_providers.append("DmlExecutionProvider")
            if self.device == "CPU" or not selected_providers:
                self.device = "GPU (DirectML Acceleration)"
        
        if not selected_providers:
            self.device = "CPU"
            
        selected_providers.append("CPUExecutionProvider")

        sess_options = ort.SessionOptions()
        # Use BASIC graph optimization for driver stability across DirectX adapters
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC

        try:
            self.session = ort.InferenceSession(
                str(self.model_path),
                sess_options=sess_options,
                providers=selected_providers
            )
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            self.load_time_ms = (time.time() - start_t) * 1000.0

            active_provider = self.session.get_providers()[0]
            model_logger.info(
                f"Loaded YOLOX model '{self.model_path.name}' successfully in {self.load_time_ms:.1f}ms "
                f"using [{active_provider}] (Device: {self.device})"
            )
        except Exception as exc:
            model_logger.error(f"Failed to initialize ONNX Runtime session: {exc}")
            raise

    def _fallback_to_cpu(self) -> None:
        """Gracefully switch to CPUExecutionProvider if GPU driver experiences a transient fault."""
        try:
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(
                str(self.model_path),
                sess_options=sess_options,
                providers=["CPUExecutionProvider"]
            )
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            self.device = "CPU"
            model_logger.info("Successfully transitioned YOLOX detector to CPU Execution Provider.")
        except Exception as exc:
            model_logger.error(f"Failed to fallback to CPU: {exc}")

    def _preprocess(self, img: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Letterbox aspect-ratio preserving resize + padding with 114.0.
        Returns: (preprocessed_chw_tensor, scale_ratio)
        """
        target_h, target_w = self.input_size
        img_h, img_w = img.shape[:2]

        r = min(target_h / img_h, target_w / img_w)
        resized_w = int(img_w * r)
        resized_h = int(img_h * r)

        resized_img = cv2.resize(img, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
        
        # Padded canvas (YOLOX standard value: 114)
        padded_img = np.full((target_h, target_w, 3), 114.0, dtype=np.float32)
        padded_img[:resized_h, :resized_w] = resized_img

        # HWC (BGR) -> CHW (BGR)
        padded_img = padded_img.transpose(2, 0, 1)
        padded_img = np.ascontiguousarray(padded_img[np.newaxis, ...], dtype=np.float32)

        return padded_img, r

    def _postprocess(
        self, outputs: np.ndarray, r: float, original_shape: Tuple[int, int], conf_thresh: float
    ) -> List[Detection]:
        """
        Decode YOLOX grids, filter by class confidence, apply NMS, and un-pad bounding boxes.
        """
        # outputs shape: (1, num_anchors, 85)
        predictions = outputs[0]
        
        raw_boxes = predictions[:, :4]
        obj_scores = predictions[:, 4]
        class_scores = predictions[:, 5:]

        # Decode multi-level FPN grid coordinates and stride scales
        decoded_boxes = np.zeros_like(raw_boxes)
        decoded_boxes[:, 0:2] = (raw_boxes[:, 0:2] + self.grids) * self.expanded_strides
        decoded_boxes[:, 2:4] = np.exp(raw_boxes[:, 2:4]) * self.expanded_strides

        # Multiply objectness with class probabilities
        class_ids = np.argmax(class_scores, axis=-1)
        max_class_scores = np.max(class_scores, axis=-1)
        confidences = obj_scores * max_class_scores

        # Filter by confidence threshold
        mask = confidences >= conf_thresh
        if not np.any(mask):
            return []

        filtered_boxes = decoded_boxes[mask]
        filtered_confs = confidences[mask]
        filtered_class_ids = class_ids[mask]

        # Convert [cx, cy, w, h] -> [x1, y1, x2, y2]
        x1 = filtered_boxes[:, 0] - filtered_boxes[:, 2] / 2
        y1 = filtered_boxes[:, 1] - filtered_boxes[:, 3] / 2
        x2 = filtered_boxes[:, 0] + filtered_boxes[:, 2] / 2
        y2 = filtered_boxes[:, 1] + filtered_boxes[:, 3] / 2

        # Rescale back to original image dimensions
        orig_h, orig_w = original_shape[:2]
        x1 = np.clip(x1 / r, 0, orig_w)
        y1 = np.clip(y1 / r, 0, orig_h)
        x2 = np.clip(x2 / r, 0, orig_w)
        y2 = np.clip(y2 / r, 0, orig_h)

        boxes_for_nms = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1).tolist()
        confs_for_nms = filtered_confs.tolist()

        # Non-Maximum Suppression via OpenCV DNN NMSBoxes
        indices = cv2.dnn.NMSBoxes(
            bboxes=boxes_for_nms,
            scores=confs_for_nms,
            score_threshold=float(conf_thresh),
            nms_threshold=float(self.nms_threshold)
        )

        detections: List[Detection] = []
        if len(indices) == 0:
            return detections

        for idx in indices.flatten():
            cid = int(filtered_class_ids[idx])
            cname = COCO_CLASSES[cid] if cid < len(COCO_CLASSES) else f"class_{cid}"
            
            # Filter for surveillance target classes
            if cname in SURVEILLANCE_TARGET_CLASSES:
                bx1 = int(round(x1[idx]))
                by1 = int(round(y1[idx]))
                bx2 = int(round(x2[idx]))
                by2 = int(round(y2[idx]))
                
                # Ensure valid box area
                if bx2 > bx1 and by2 > by1:
                    detections.append(
                        Detection(
                            class_id=cid,
                            class_name=cname,
                            confidence=float(filtered_confs[idx]),
                            bbox=[bx1, by1, bx2, by2]
                        )
                    )

        return detections

    def detect(self, frame: np.ndarray, conf_threshold: Optional[float] = None) -> List[Detection]:
        """
        Run inference on a BGR video frame and return normalized Detection objects.
        """
        if frame is None or frame.size == 0 or self.session is None:
            return []

        active_conf = conf_threshold if conf_threshold is not None else self.conf_threshold
        # Clamp confidence threshold to 0.0 - 1.0
        active_conf = max(0.01, min(1.0, float(active_conf)))

        with self._lock:
            try:
                tensor, r = self._preprocess(frame)
                outputs = self.session.run([self.output_name], {self.input_name: tensor})[0]
                detections = self._postprocess(outputs, r, frame.shape, active_conf)
                return detections
            except Exception as exc:
                inference_logger.error(f"Inference execution error: {exc}")
                if self.device != "CPU":
                    inference_logger.warning("GPU execution error encountered; automatically falling back to CPU.")
                    self._fallback_to_cpu()
                return []

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": "YOLOX",
            "variant": "yolox_tiny",
            "framework": "ONNX Runtime",
            "model_path": str(self.model_path),
            "device": self.device,
            "input_resolution": f"{self.input_size[0]}x{self.input_size[1]}",
            "default_confidence_threshold": self.conf_threshold,
            "nms_threshold": self.nms_threshold,
            "license": "Apache-2.0",
            "supported_classes": sorted(list(SURVEILLANCE_TARGET_CLASSES)),
        }
