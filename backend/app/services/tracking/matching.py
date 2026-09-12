# ==============================================================================
# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)
# Module: app.services.tracking.matching
# Description: IoU calculation and bipartite matching algorithms for ByteTrack.
# License: Apache-2.0
# ==============================================================================

from typing import List, Tuple, Any
import numpy as np
from scipy.optimize import linear_sum_assignment


def box_ious(atlbrs: np.ndarray, btlbrs: np.ndarray) -> np.ndarray:
    """
    Calculate IoU between two sets of bounding boxes [x1, y1, x2, y2].
    atlbrs: (N, 4)
    btlbrs: (M, 4)
    Returns: (N, M) IoU matrix
    """
    if atlbrs.size == 0 or btlbrs.size == 0:
        return np.zeros((len(atlbrs), len(btlbrs)), dtype=np.float32)

    atlbrs = np.ascontiguousarray(atlbrs, dtype=np.float32)
    btlbrs = np.ascontiguousarray(btlbrs, dtype=np.float32)

    # Coordinates of intersection
    x1 = np.maximum(atlbrs[:, None, 0], btlbrs[None, :, 0])
    y1 = np.maximum(atlbrs[:, None, 1], btlbrs[None, :, 1])
    x2 = np.minimum(atlbrs[:, None, 2], btlbrs[None, :, 2])
    y2 = np.minimum(atlbrs[:, None, 3], btlbrs[None, :, 3])

    intersection_w = np.maximum(0.0, x2 - x1)
    intersection_h = np.maximum(0.0, y2 - y1)
    intersection_area = intersection_w * intersection_h

    area_a = np.maximum(0.0, atlbrs[:, 2] - atlbrs[:, 0]) * np.maximum(0.0, atlbrs[:, 3] - atlbrs[:, 1])
    area_b = np.maximum(0.0, btlbrs[:, 2] - btlbrs[:, 0]) * np.maximum(0.0, btlbrs[:, 3] - btlbrs[:, 1])

    union_area = area_a[:, None] + area_b[None, :] - intersection_area
    iou = np.zeros_like(intersection_area, dtype=np.float32)
    valid = union_area > 0
    iou[valid] = intersection_area[valid] / union_area[valid]
    return iou


def iou_distance(atracks: List[Any], btracks: List[Any]) -> np.ndarray:
    """
    Compute 1 - IoU distance between two lists of tracks / detections.
    Each item in atracks and btracks must expose a `.tlbr` property or `.bbox` property.
    """
    if len(atracks) == 0 or len(btracks) == 0:
        return np.zeros((len(atracks), len(btracks)), dtype=np.float32)

    atlbrs = np.array([getattr(t, "tlbr", getattr(t, "bbox", None)) for t in atracks], dtype=np.float32)
    btlbrs = np.array([getattr(t, "tlbr", getattr(t, "bbox", None)) for t in btracks], dtype=np.float32)

    ious = box_ious(atlbrs, btlbrs)
    return 1.0 - ious


def linear_assignment(
    cost_matrix: np.ndarray, thresh: float
) -> Tuple[np.ndarray, List[int], List[int]]:
    """
    Solve minimum cost bipartite matching using Hungarian algorithm (linear_sum_assignment).
    Returns:
        matches: np.ndarray of shape (K, 2) containing paired indices [row_idx, col_idx]
        unmatched_a: List of unmatched row indices
        unmatched_b: List of unmatched column indices
    """
    if cost_matrix.size == 0:
        return np.empty((0, 2), dtype=int), list(range(cost_matrix.shape[0])), list(range(cost_matrix.shape[1]))

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    matches = []
    unmatched_a = list(range(cost_matrix.shape[0]))
    unmatched_b = list(range(cost_matrix.shape[1]))

    for r, c in zip(row_ind, col_ind):
        if cost_matrix[r, c] <= thresh:
            matches.append([r, c])
            if r in unmatched_a:
                unmatched_a.remove(r)
            if c in unmatched_b:
                unmatched_b.remove(c)

    matches_arr = np.array(matches, dtype=int) if len(matches) > 0 else np.empty((0, 2), dtype=int)
    return matches_arr, unmatched_a, unmatched_b
