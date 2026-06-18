"""
Detects the grid layout of an input collage image.

Strategy (2-level):
1. Find horizontal separators across the full image → horizontal bands
2. For each band, find vertical separators independently → cells
3. Filter out slivers (< 20% of image dimension) to exclude text overlays / watermarks

Relative variance threshold (% of max) catches thin separator lines without
splitting uniform photo areas, because those areas occupy full rows/columns
and so their contribution is already baked into the max.
"""

import cv2
import numpy as np
from PIL import Image


def detect_layout(pil_image: Image.Image) -> dict:
    """
    Returns:
        {
            "cells": [(x0, y0, x1, y1), ...],
            "grid_hint": str,
        }
    """
    img_np = np.array(pil_image.convert("RGB"))
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY).astype(np.float32)
    h, w = gray.shape

    # Minimum cell size to ignore thin banners / watermark rows
    min_cell_h = max(int(h * 0.18), 60)
    min_cell_w = max(int(w * 0.18), 60)

    h_splits = _find_splits(gray, axis="horizontal", min_gap=min_cell_h)

    cells = []
    for i in range(len(h_splits) - 1):
        y0, y1 = h_splits[i], h_splits[i + 1]
        if (y1 - y0) < min_cell_h:
            continue
        band = gray[y0:y1, :]
        v_splits = _find_splits(band, axis="vertical", min_gap=min_cell_w)
        for j in range(len(v_splits) - 1):
            x0, x1 = v_splits[j], v_splits[j + 1]
            if (x1 - x0) < min_cell_w:
                continue
            cells.append((x0, y0, x1, y1))

    cells.sort(key=lambda c: (c[1], c[0]))
    return {"cells": cells, "grid_hint": f"{len(cells)} photos"}


def _find_splits(region: np.ndarray, axis: str, min_gap: int) -> list:
    """
    Find separator positions using relative variance thresholds.
    Small window smoothing retains thin separator lines.
    """
    if axis == "horizontal":
        signal = np.var(region, axis=1)
        length = region.shape[0]
    else:
        signal = np.var(region, axis=0)
        length = region.shape[1]

    signal = _smooth(signal, window=5)
    max_val = signal.max()
    if max_val == 0:
        return [0, length]

    for pct in (0.04, 0.08, 0.15):
        threshold = max_val * pct
        positions = _threshold_to_positions(signal, threshold, min_gap, length)
        if len(positions) > 2:
            return positions

    return [0, length]


def _threshold_to_positions(signal, threshold, min_gap, length) -> list:
    is_low = signal <= threshold
    positions = [0]
    in_low = False
    low_start = 0

    for i, v in enumerate(is_low):
        if v and not in_low:
            in_low = True
            low_start = i
        elif not v and in_low:
            in_low = False
            mid = (low_start + i) // 2
            if mid - positions[-1] >= min_gap:
                positions.append(mid)

    positions.append(length)
    return positions


def _smooth(arr: np.ndarray, window: int = 5) -> np.ndarray:
    kernel = np.ones(window) / window
    return np.convolve(arr, kernel, mode="same")
