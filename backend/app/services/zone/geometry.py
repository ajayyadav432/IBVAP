# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.zone.geometry
# Description: Point-in-polygon tests, normalized coordinates, and object anchor points.
# License: Apache-2.0
# ==============================================================================

from typing import List, Tuple, Optional
import cv2
import numpy as np


def get_object_anchor(bbox: List[int], object_type: str = "person") -> Tuple[float, float]:
    """
    Calculate the ground-contact anchor point for a bounding box.
    For both people and vehicles, uses bottom-center: ((x1 + x2) / 2.0, y2).
    
    Args:
        bbox: [x1, y1, x2, y2] bounding box coordinates
        object_type: 'person', 'car', 'truck', etc.
        
    Returns:
        (anchor_x, anchor_y)
    """
    x1, y1, x2, y2 = bbox
    center_x = (float(x1) + float(x2)) / 2.0
    bottom_y = float(y2)
    return center_x, bottom_y


def normalize_point(x: float, y: float, width: int, height: int) -> Tuple[float, float]:
    """Convert absolute pixel coordinates to normalized [0.0, 1.0] coordinates."""
    if width <= 0 or height <= 0:
        return 0.0, 0.0
    norm_x = max(0.0, min(1.0, x / float(width)))
    norm_y = max(0.0, min(1.0, y / float(height)))
    return norm_x, norm_y


def denormalize_point(norm_x: float, norm_y: float, width: int, height: int) -> Tuple[int, int]:
    """Convert normalized [0.0, 1.0] coordinates to absolute pixel coordinates."""
    px = int(round(norm_x * width))
    py = int(round(norm_y * height))
    return max(0, min(width - 1, px)), max(0, min(height - 1, py))


def denormalize_polygon(
    polygon: List[List[float]],
    width: int,
    height: int
) -> np.ndarray:
    """
    Convert a list of normalized [norm_x, norm_y] vertices into pixel coordinate array for OpenCV.
    
    Returns:
        np.ndarray with shape (N, 1, 2) and dtype int32
    """
    pts = []
    for pt in polygon:
        px, py = denormalize_point(pt[0], pt[1], width, height)
        pts.append([px, py])
    return np.array(pts, dtype=np.int32).reshape((-1, 1, 2))


def validate_polygon(polygon: List[List[float]]) -> Tuple[bool, Optional[str]]:
    """
    Validate polygon geometry rules:
    1. Must be a list of coordinate pairs
    2. Must contain at least 3 distinct vertices
    3. All normalized coordinates must be in [0.0, 1.0] range
    4. Must have non-zero geometric area
    """
    if not isinstance(polygon, (list, tuple)):
        return False, "Polygon must be an array of coordinate points."

    if len(polygon) < 3:
        return False, "A zone requires at least 3 valid points."

    for idx, pt in enumerate(polygon):
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            return False, f"Vertex #{idx + 1} is invalid. Expected [x, y] format."
        x, y = float(pt[0]), float(pt[1])
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            return False, f"Vertex #{idx + 1} ({x:.3f}, {y:.3f}) is outside normalized [0.0, 1.0] range."

    # Verify non-zero area using Shoelace formula
    n = len(polygon)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += polygon[i][0] * polygon[j][1]
        area -= polygon[j][0] * polygon[i][1]
    area = abs(area) / 2.0

    if area < 1e-6:
        return False, "Polygon has zero or degenerate geometric area."

    return True, None


def point_in_polygon(
    point: Tuple[float, float],
    polygon: List[List[float]],
    measure_dist: bool = False
) -> Tuple[bool, float]:
    """
    Deterministic Point-in-Polygon test supporting convex, concave, and boundary cases.
    Uses OpenCV cv2.pointPolygonTest with normalized coordinates scaled to a reference unit space.
    
    Args:
        point: (norm_x, norm_y)
        polygon: [[x1, y1], [x2, y2], ...] normalized vertices
        measure_dist: if True, returns signed distance to boundary (positive = inside, negative = outside)
        
    Returns:
        (is_inside, signed_distance)
    """
    # Scale normalized coords by 10000 for high integer precision in cv2.pointPolygonTest
    SCALE = 10000.0
    pts = np.array(
        [[int(round(p[0] * SCALE)), int(round(p[1] * SCALE))] for p in polygon],
        dtype=np.int32
    ).reshape((-1, 1, 2))

    px = int(round(point[0] * SCALE))
    py = int(round(point[1] * SCALE))

    # cv2.pointPolygonTest returns:
    # > 0: point inside
    # = 0: point on boundary edge
    # < 0: point outside
    dist = cv2.pointPolygonTest(pts, (px, py), measureDist=True)
    norm_dist = dist / SCALE

    # Boundary rule: Points strictly inside or on the boundary edge (dist >= 0) are considered INSIDE
    is_inside = (dist >= 0.0)
    return is_inside, norm_dist
