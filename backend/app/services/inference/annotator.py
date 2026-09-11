# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.inference.annotator
# Description: Video frame bounding box, track ID, face detection, and telemetry annotation.
# License: Apache-2.0
# ==============================================================================

from typing import List, Tuple, Union, Optional
import cv2
import numpy as np

from app.services.inference.detector import Detection
from app.services.tracking.tracker import Track
from app.services.face.detector import Face

# Approved Color Mapping (BGR format for OpenCV)
CLASS_COLORS = {
    "person": (24, 17, 255),      # IBVAP Accent Red (#FF1118)
    "car": (246, 130, 59),        # Blue (#3B82F6)
    "motorcycle": (212, 182, 6),  # Teal (#06B6D4)
    "bus": (11, 158, 245),        # Amber (#F59E0B)
    "truck": (12, 88, 234),       # Orange (#EA580C)
    "bicycle": (147, 197, 253),   # Light Blue
    "face": (220, 200, 0),        # Cyan/Yellow Face Accent
    "plate_high": (0, 215, 255),   # Bright Amber / Gold for Plates
    "plate_low": (140, 140, 140),  # Muted for unreadable
}

DEFAULT_COLOR = (200, 200, 200)


def get_class_color(class_name: str) -> Tuple[int, int, int]:
    """Retrieve BGR color tuple for a given object class."""
    return CLASS_COLORS.get(class_name.lower(), DEFAULT_COLOR)


def draw_faces(
    frame: np.ndarray,
    faces: List[Face],
    draw_landmarks: bool = True,
) -> np.ndarray:
    """
    Render subtle face detection bounding boxes and 5-point facial landmarks.
    """
    if frame is None or len(faces) == 0:
        return frame

    annotated = frame.copy()
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.38
    thickness = 1
    face_color = CLASS_COLORS["face"]

    for face in faces:
        x1, y1, x2, y2 = face.bbox

        # Face bounding box with clean thin border
        cv2.rectangle(annotated, (x1, y1), (x2, y2), face_color, 1)

        # 5-point facial landmarks
        if draw_landmarks and face.landmarks:
            for lx, ly in face.landmarks:
                if 0 <= lx < frame.shape[1] and 0 <= ly < frame.shape[0]:
                    cv2.circle(annotated, (lx, ly), 2, (0, 255, 255), -1)

        # Badge: "FACE 0.91"
        label_text = f"FACE {face.confidence:.2f}"
        (text_w, text_h), _ = cv2.getTextSize(label_text, font, font_scale, thickness)

        badge_y1 = max(0, y1 - text_h - 4)
        badge_y2 = y1
        badge_x1 = x1
        badge_x2 = min(frame.shape[1], x1 + text_w + 6)

        cv2.rectangle(annotated, (badge_x1, badge_y1), (badge_x2, badge_y2), (15, 15, 15), -1)
        cv2.rectangle(annotated, (badge_x1, badge_y1), (badge_x2, badge_y2), face_color, 1)

        text_pos_y = y1 - 3
        cv2.putText(
            annotated,
            label_text,
            (badge_x1 + 3, text_pos_y),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            lineType=cv2.LINE_AA,
        )

    return annotated


def draw_anpr_plates(
    frame: np.ndarray,
    anpr_results: list,
) -> np.ndarray:
    """
    Render license plate tags and bounding boxes on tracked vehicles.
    """
    if frame is None or not anpr_results:
        return frame

    annotated = frame.copy()
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.40
    thickness = 1

    for res in anpr_results:
        # Handle dict or ANPRResult dataclass
        ptext = getattr(res, "plate_text", None) or (res.get("plate_text") if isinstance(res, dict) else "")
        quality = getattr(res, "quality", None) or (res.get("quality") if isinstance(res, dict) else "LOW")
        pbox = getattr(res, "plate_bbox", None) or (res.get("plate_bbox") if isinstance(res, dict) else None)
        vbox = getattr(res, "vehicle_bbox", None) or (res.get("vehicle_bbox") if isinstance(res, dict) else None)
        conf = getattr(res, "confidence", 0.0) or (res.get("confidence", 0.0) if isinstance(res, dict) else 0.0)

        is_high = quality == "HIGH"
        badge_color = CLASS_COLORS["plate_high"] if is_high else CLASS_COLORS["plate_low"]

        # Draw plate bbox if available
        if pbox:
            px1, py1, px2, py2 = pbox
            cv2.rectangle(annotated, (px1, py1), (px2, py2), badge_color, 2)

        # Draw plate badge near bottom or top of vehicle box
        if vbox:
            vx1, vy1, vx2, vy2 = vbox
            label_text = f"PLATE: {ptext} [{quality}]" if ptext != "UNREADABLE" else "PLATE: UNREADABLE"
            (text_w, text_h), _ = cv2.getTextSize(label_text, font, font_scale, thickness)

            badge_x1 = max(0, vx1)
            badge_y2 = min(frame.shape[0], vy2 + text_h + 8)
            badge_y1 = max(0, badge_y2 - text_h - 6)
            badge_x2 = min(frame.shape[1], badge_x1 + text_w + 8)

            cv2.rectangle(annotated, (badge_x1, badge_y1), (badge_x2, badge_y2), (10, 10, 10), -1)
            cv2.rectangle(annotated, (badge_x1, badge_y1), (badge_x2, badge_y2), badge_color, 1)

            cv2.putText(
                annotated,
                label_text,
                (badge_x1 + 4, badge_y2 - 4),
                font,
                font_scale,
                (255, 255, 255) if is_high else (180, 180, 180),
                thickness,
                lineType=cv2.LINE_AA,
            )

    return annotated


def draw_zones(
    frame: np.ndarray,
    zones: list,
    active_intrusions: Optional[dict] = None,
) -> np.ndarray:
    """
    Render polygon zone overlays, labels, and active intrusion warning states.
    """
    if frame is None or not zones:
        return frame

    h, w = frame.shape[:2]
    annotated = frame.copy()
    overlay = frame.copy()
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.40
    thickness = 1

    active_intrusions = active_intrusions or {}

    for z in zones:
        # Handle dict or ZoneDefinition
        zid = getattr(z, "id", None) or (z.get("id") if isinstance(z, dict) else None)
        zname = getattr(z, "name", None) or (z.get("name") if isinstance(z, dict) else "Zone")
        ztype = getattr(z, "zone_type", None) or (z.get("zone_type") if isinstance(z, dict) else "RESTRICTED")
        poly = getattr(z, "polygon", None) or (z.get("polygon") if isinstance(z, dict) else [])
        enabled = getattr(z, "enabled", True) if hasattr(z, "enabled") else (z.get("enabled", True) if isinstance(z, dict) else True)

        if not enabled or not poly or len(poly) < 3:
            continue

        # Check if zone has active track intrusions
        intruding_tracks = active_intrusions.get(zid, []) if zid is not None else []
        has_intrusion = len(intruding_tracks) > 0

        # Denormalize polygon points to frame resolution
        pts = np.array(
            [[int(round(p[0] * w)), int(round(p[1] * h))] for p in poly],
            dtype=np.int32
        ).reshape((-1, 1, 2))

        # Color scheme
        if has_intrusion:
            fill_color = (24, 17, 255)   # Bright Red
            border_color = (24, 17, 255)
            alpha = 0.30
        elif ztype.upper() == "RESTRICTED":
            fill_color = (30, 20, 200)   # Deep Red
            border_color = (40, 30, 240)
            alpha = 0.18
        else:  # MONITORING
            fill_color = (200, 150, 20)  # Cyan/Blue
            border_color = (230, 180, 30)
            alpha = 0.15

        # Draw semi-transparent polygon fill
        cv2.fillPoly(overlay, [pts], fill_color)

        # Draw crisp boundary line
        cv2.polylines(annotated, [pts], isClosed=True, color=border_color, thickness=2, lineType=cv2.LINE_AA)

        # Draw Zone Name Badge at top-most vertex or polygon centroid
        pts_2d = pts.reshape((-1, 2))
        top_idx = int(np.argmin(pts_2d[:, 1]))
        bx, by = int(pts_2d[top_idx][0]), int(pts_2d[top_idx][1])

        label_text = f"⚠ INTRUSION: {zname.upper()}" if has_intrusion else f"{zname.upper()} [{ztype}]"
        (text_w, text_h), _ = cv2.getTextSize(label_text, font, font_scale, thickness)

        badge_x1 = max(0, min(w - text_w - 10, bx - text_w // 2))
        badge_y1 = max(0, by - text_h - 6)
        badge_x2 = min(w, badge_x1 + text_w + 8)
        badge_y2 = min(h, badge_y1 + text_h + 6)

        cv2.rectangle(annotated, (badge_x1, badge_y1), (badge_x2, badge_y2), (10, 10, 10), -1)
        cv2.rectangle(annotated, (badge_x1, badge_y1), (badge_x2, badge_y2), border_color, 1)

        cv2.putText(
            annotated,
            label_text,
            (badge_x1 + 4, badge_y2 - 4),
            font,
            font_scale,
            (255, 255, 255) if not has_intrusion else (24, 17, 255),
            thickness,
            lineType=cv2.LINE_AA,
        )

    # Blend semi-transparent fill onto frame
    annotated = cv2.addWeighted(overlay, 0.20, annotated, 0.80, 0)
    return annotated


def draw_tracks(
    frame: np.ndarray,
    tracks: List[Track],
    faces: Optional[List[Face]] = None,
    anpr_results: Optional[list] = None,
    zones: Optional[list] = None,
    active_intrusions: Optional[dict] = None,
    draw_box: bool = True,
    draw_label: bool = True,
    draw_centroid: bool = True,
) -> np.ndarray:
    """
    Render bounding boxes, track IDs (e.g. PERSON #17), centroids, intrusion anchors, faces, ANPR badges, and zones.
    """
    if frame is None:
        return frame

    # 1. Overlay zones first so they appear in background
    annotated = draw_zones(frame, zones, active_intrusions) if zones else frame.copy()
    
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.42
    thickness = 1

    for trk in tracks:
        x1, y1, x2, y2 = trk.bbox
        color = get_class_color(trk.object_type)

        # Highlight in red if track is currently in a restricted zone
        is_intruding = False
        if active_intrusions:
            for zid, tids in active_intrusions.items():
                if trk.track_id in tids:
                    is_intruding = True
                    color = (24, 17, 255)  # IBVAP Alert Red
                    break

        if draw_box:
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            corner_len = min(15, int((x2 - x1) * 0.2), int((y2 - y1) * 0.2))
            if corner_len > 3:
                cv2.line(annotated, (x1, y1), (x1 + corner_len, y1), color, 3)
                cv2.line(annotated, (x1, y1), (x1, y1 + corner_len), color, 3)
                cv2.line(annotated, (x2, y1), (x2 - corner_len, y1), color, 3)
                cv2.line(annotated, (x2, y1), (x2, y1 + corner_len), color, 3)
                cv2.line(annotated, (x1, y2), (x1 + corner_len, y2), color, 3)
                cv2.line(annotated, (x1, y2), (x1, y2 - corner_len), color, 3)
                cv2.line(annotated, (x2, y2), (x2 - corner_len, y2), color, 3)
                cv2.line(annotated, (x2, y2), (x2, y2 - corner_len), color, 3)

        if draw_centroid:
            cx, cy = trk.centroid
            if 0 <= cx < frame.shape[1] and 0 <= cy < frame.shape[0]:
                cv2.circle(annotated, (cx, cy), 3, (0, 255, 255), -1)
            
            # Ground-contact anchor point (bottom-center)
            bcx, bcy = trk.bottom_center
            if 0 <= bcx < frame.shape[1] and 0 <= bcy < frame.shape[0]:
                anchor_color = (24, 17, 255) if is_intruding else (0, 255, 255)
                cv2.circle(annotated, (bcx, bcy), 4, anchor_color, -1)

        if draw_label:
            zone_tag = f" [{trk.current_zone}]" if trk.current_zone else ""
            label_text = f"{trk.object_type.upper()} #{trk.track_id:02d}{zone_tag}  {trk.confidence:.2f}"
            (text_w, text_h), baseline = cv2.getTextSize(label_text, font, font_scale, thickness)

            badge_y1 = max(0, y1 - text_h - 6)
            badge_y2 = y1
            badge_x1 = x1
            badge_x2 = min(frame.shape[1], x1 + text_w + 8)

            cv2.rectangle(annotated, (badge_x1, badge_y1), (badge_x2, badge_y2), (15, 15, 15), -1)
            cv2.rectangle(annotated, (badge_x1, badge_y1), (badge_x2, badge_y2), color, 1)

            text_pos_y = y1 - 4
            cv2.putText(
                annotated,
                label_text,
                (badge_x1 + 4, text_pos_y),
                font,
                font_scale,
                (255, 255, 255),
                thickness,
                lineType=cv2.LINE_AA,
            )

    # Overlay ANPR plates if provided
    if anpr_results and len(anpr_results) > 0:
        annotated = draw_anpr_plates(annotated, anpr_results)

    # Overlay faces on top if provided
    if faces and len(faces) > 0:
        annotated = draw_faces(annotated, faces)

    return annotated



def draw_detections(
    frame: np.ndarray,
    detections: List[Detection],
    faces: Optional[List[Face]] = None,
    draw_box: bool = True,
    draw_label: bool = True,
) -> np.ndarray:
    """
    Render raw detections and optional faces when no active tracker is configured.
    """
    if frame is None:
        return frame

    annotated = frame.copy()
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.45
    thickness = 1

    for det in detections:
        x1, y1, x2, y2 = det.bbox
        color = get_class_color(det.class_name)

        if draw_box:
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            corner_len = min(15, int((x2 - x1) * 0.2), int((y2 - y1) * 0.2))
            if corner_len > 3:
                cv2.line(annotated, (x1, y1), (x1 + corner_len, y1), color, 3)
                cv2.line(annotated, (x1, y1), (x1, y1 + corner_len), color, 3)
                cv2.line(annotated, (x2, y1), (x2 - corner_len, y1), color, 3)
                cv2.line(annotated, (x2, y1), (x2, y1 + corner_len), color, 3)
                cv2.line(annotated, (x1, y2), (x1 + corner_len, y2), color, 3)
                cv2.line(annotated, (x1, y2), (x1, y2 - corner_len), color, 3)
                cv2.line(annotated, (x2, y2), (x2 - corner_len, y2), color, 3)
                cv2.line(annotated, (x2, y2), (x2, y2 - corner_len), color, 3)

        if draw_label:
            label_text = f"{det.class_name.upper()} {det.confidence:.2f}"
            (text_w, text_h), baseline = cv2.getTextSize(label_text, font, font_scale, thickness)

            badge_y1 = max(0, y1 - text_h - 6)
            badge_y2 = y1
            badge_x1 = x1
            badge_x2 = min(frame.shape[1], x1 + text_w + 8)

            cv2.rectangle(annotated, (badge_x1, badge_y1), (badge_x2, badge_y2), (15, 15, 15), -1)
            cv2.rectangle(annotated, (badge_x1, badge_y1), (badge_x2, badge_y2), color, 1)

            text_pos_y = y1 - 4
            cv2.putText(
                annotated,
                label_text,
                (badge_x1 + 4, text_pos_y),
                font,
                font_scale,
                (255, 255, 255),
                thickness,
                lineType=cv2.LINE_AA,
            )

    if faces and len(faces) > 0:
        annotated = draw_faces(annotated, faces)

    return annotated

