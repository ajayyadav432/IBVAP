# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.anpr.engine
# Description: ANPR Engine orchestrating plate detection, OCR, quality gate, and track-based temporal deduplication.
# License: Apache-2.0
# ==============================================================================

from dataclasses import dataclass
import datetime
import time
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

from app.core.logging import inference_logger
from app.services.tracking.tracker import Track
from app.services.anpr.plate_detector import PlateDetector, RapidPlateDetector, PlateCandidate
from app.services.anpr.ocr_engine import OCREngine, RapidOCREngine
from app.services.anpr.quality import PlateQualityGate, QualityLevel
from app.services.anpr.normalizer import normalize_plate_text
from app.services.anpr.preprocessing import validate_crop


# Target vehicle classes for ANPR processing
ANPR_VEHICLE_CLASSES = {"car", "bus", "truck", "motorcycle"}


@dataclass
class ANPRResult:
    """Normalized license plate recognition result."""
    plate_text: str
    quality: str             # HIGH, MEDIUM, LOW, UNREADABLE
    confidence: float        # 0.0 - 1.0
    track_id: Optional[int]
    camera_id: int
    timestamp: str
    plate_bbox: Optional[List[int]]    # [gx1, gy1, gx2, gy2] relative to full frame
    vehicle_bbox: List[int]            # [vx1, vy1, vx2, vy2] relative to full frame
    vehicle_type: str                  # car, bus, truck, motorcycle
    evidence_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plate_text": self.plate_text,
            "quality": self.quality,
            "confidence": round(float(self.confidence), 4),
            "track_id": self.track_id,
            "camera_id": self.camera_id,
            "timestamp": self.timestamp,
            "plate_bbox": [int(v) for v in self.plate_bbox] if self.plate_bbox else None,
            "vehicle_bbox": [int(v) for v in self.vehicle_bbox],
            "vehicle_type": self.vehicle_type,
            "evidence_path": self.evidence_path,
        }


@dataclass
class TrackANPRState:
    """Internal state tracker per vehicle track ID."""
    track_id: int
    last_sampled_frame: int
    best_result: ANPRResult
    read_count: int
    last_seen_time: float


class ANPREngine:
    """
    Automatic Number Plate Recognition (ANPR) Engine.
    Operates on tracked vehicle candidates using periodic temporal sampling,
    explainable quality gating, and result deduplication across frames.
    """
    def __init__(
        self,
        sample_interval: int = 6,
        conf_threshold: float = 0.40,
        plate_detector: Optional[PlateDetector] = None,
        ocr_engine: Optional[OCREngine] = None,
        quality_gate: Optional[PlateQualityGate] = None,
    ):
        self.sample_interval = sample_interval
        self.conf_threshold = conf_threshold
        self.detector = plate_detector or RapidPlateDetector(conf_threshold=conf_threshold)
        self.ocr = ocr_engine or RapidOCREngine()
        self.quality_gate = quality_gate or PlateQualityGate()

        # Track ID -> TrackANPRState mapping
        self._track_states: Dict[int, TrackANPRState] = {}
        self._last_anpr_latency_ms: float = 0.0

    def process_tracks(
        self,
        frame: np.ndarray,
        tracks: List[Track],
        frame_idx: int,
        camera_id: int = 1,
    ) -> List[ANPRResult]:
        """
        Process active tracks in the current frame, sampling vehicle tracks for ANPR.
        """
        if frame is None or frame.size == 0 or not tracks:
            return []

        start_t = time.time()
        active_results: List[ANPRResult] = []
        active_track_ids = [t.track_id for t in tracks if t.object_type in ANPR_VEHICLE_CLASSES]

        # Purge stale tracks that are no longer active
        self._clean_stale_tracks(active_track_ids)

        for track in tracks:
            if track.object_type not in ANPR_VEHICLE_CLASSES:
                continue

            tid = track.track_id
            vbox = [int(v) for v in track.bbox]
            vx1, vy1, vx2, vy2 = vbox
            vw = max(0, vx2 - vx1)
            vh = max(0, vy2 - vy1)

            # Skip vehicles that are too small for any reliable ANPR reading (< 40x30 px)
            if vw < 40 or vh < 30:
                if tid in self._track_states:
                    active_results.append(self._track_states[tid].best_result)
                continue

            state = self._track_states.get(tid)
            should_sample = (state is None) or (frame_idx - state.last_sampled_frame >= self.sample_interval)

            if not should_sample and state is not None:
                # Update current vehicle bbox and include best cached result
                state.best_result.vehicle_bbox = vbox
                active_results.append(state.best_result)
                continue

            # Extract vehicle crop safely
            fh, fw = frame.shape[:2]
            cvx1 = max(0, min(fw - 1, vx1))
            cvy1 = max(0, min(fh - 1, vy1))
            cvx2 = max(cvx1 + 1, min(fw, vx2))
            cvy2 = max(cvy1 + 1, min(fh, vy2))

            vehicle_crop = frame[cvy1:cvy2, cvx1:cvx2]
            if not validate_crop(vehicle_crop, min_w=20, min_h=20):
                continue

            # Step 1: Detect Plate Candidate Regions
            candidates = self.detector.detect_plates(vehicle_crop, vehicle_bbox=[cvx1, cvy1, cvx2, cvy2])

            best_candidate_result: Optional[ANPRResult] = None

            if candidates:
                for cand in candidates:
                    # Step 2: Quality Gate Assessment
                    assessment = self.quality_gate.assess(cand.crop)
                    
                    if assessment.is_usable:
                        # Step 3: Optical Character Recognition
                        ocr_res = self.ocr.recognize(cand.crop)
                        
                        # Step 4: Normalization and Plausibility Check
                        plate_text, quality, conf = normalize_plate_text(ocr_res.raw_text, ocr_res.confidence)
                    else:
                        plate_text = "UNREADABLE"
                        quality = QualityLevel.LOW
                        conf = 0.0

                    cand_res = ANPRResult(
                        plate_text=plate_text,
                        quality=quality,
                        confidence=conf,
                        track_id=tid,
                        camera_id=camera_id,
                        timestamp=datetime.datetime.utcnow().isoformat(),
                        plate_bbox=cand.global_bbox,
                        vehicle_bbox=vbox,
                        vehicle_type=track.object_type,
                    )

                    if best_candidate_result is None or cand_res.confidence > best_candidate_result.confidence:
                        best_candidate_result = cand_res
            else:
                # Fallback: Assess lower 45% of vehicle crop as standard plate mounting area
                lh_y1 = int(vh * 0.55)
                lower_crop = vehicle_crop[lh_y1:vh, :]
                assessment = self.quality_gate.assess(lower_crop)
                
                if assessment.is_usable and (assessment.level in (QualityLevel.HIGH, QualityLevel.MEDIUM)):
                    ocr_res = self.ocr.recognize(lower_crop)
                    plate_text, quality, conf = normalize_plate_text(ocr_res.raw_text, ocr_res.confidence)
                    if plate_text != "UNREADABLE":
                        best_candidate_result = ANPRResult(
                            plate_text=plate_text,
                            quality=quality,
                            confidence=conf,
                            track_id=tid,
                            camera_id=camera_id,
                            timestamp=datetime.datetime.utcnow().isoformat(),
                            plate_bbox=[cvx1, cvy1 + lh_y1, cvx2, cvy2],
                            vehicle_bbox=vbox,
                            vehicle_type=track.object_type,
                        )

            # Step 5: Temporal Deduplication & Best-Result Retention
            now_t = time.time()
            if best_candidate_result is not None:
                if state is None:
                    self._track_states[tid] = TrackANPRState(
                        track_id=tid,
                        last_sampled_frame=frame_idx,
                        best_result=best_candidate_result,
                        read_count=1,
                        last_seen_time=now_t,
                    )
                else:
                    state.last_sampled_frame = frame_idx
                    state.last_seen_time = now_t
                    state.read_count += 1
                    
                    # Update best result if new result has higher confidence or non-unreadable
                    if (
                        best_candidate_result.confidence > state.best_result.confidence
                        or (state.best_result.plate_text == "UNREADABLE" and best_candidate_result.plate_text != "UNREADABLE")
                    ):
                        state.best_result = best_candidate_result
                    else:
                        state.best_result.vehicle_bbox = vbox

                active_results.append(self._track_states[tid].best_result)
            elif state is not None:
                state.last_sampled_frame = frame_idx
                state.best_result.vehicle_bbox = vbox
                active_results.append(state.best_result)

        self._last_anpr_latency_ms = round((time.time() - start_t) * 1000.0, 1)
        return active_results

    def _clean_stale_tracks(self, active_track_ids: List[int], max_idle_seconds: float = 10.0) -> None:
        """Purge tracks that have disappeared from active tracking."""
        now = time.time()
        stale = [
            tid for tid, s in self._track_states.items()
            if (tid not in active_track_ids) and (now - s.last_seen_time > max_idle_seconds)
        ]
        for tid in stale:
            del self._track_states[tid]

    def get_active_results(self, active_track_ids: Optional[List[int]] = None) -> List[ANPRResult]:
        """Return list of active deduplicated ANPR results."""
        if active_track_ids is None:
            return [s.best_result for s in self._track_states.values()]
        return [
            s.best_result for tid, s in self._track_states.items()
            if tid in active_track_ids
        ]

    def get_latency_ms(self) -> float:
        return self._last_anpr_latency_ms

