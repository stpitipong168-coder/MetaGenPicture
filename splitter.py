"""
Splits a collage image into individual sub-images using layout_detector.

Filters applied (in order):
1. Size   — cells < 80px in either dimension are ignored
2. Overlay — cells where > 30% of pixels have luminance < 30 are ignored
             (catches Facebook '+N' overlay thumbnails which have a solid dark mask)
3. Dedup  — near-identical cells (RGB MSE < 4% on 16×16 thumbnail) are dropped
"""

import numpy as np
from PIL import Image
from layout_detector import detect_layout

MIN_CELL_PX     = 80    # minimum cell dimension (px)
_DARK_LUM       = 30   # luminance threshold for "dark pixel"
_DARK_FRACTION  = 0.30 # if > 30% pixels are very dark → overlay cell
_OVERLAY_MEAN   = 85   # secondary: mean lum < 85 AND std < 55 → semi-transparent overlay (+8)
_OVERLAY_STD    = 55
_THUMB_SIZE     = (16, 16)
_DUP_MSE_PCT    = 0.04  # normalised MSE < 4% on 16×16 thumb → duplicate


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_overlay(img: Image.Image) -> bool:
    """True when the cell looks like a '+N' dark-mask overlay thumbnail."""
    arr = np.array(img.convert("L"), dtype=np.uint8)
    if float((arr < _DARK_LUM).mean()) > _DARK_FRACTION:
        return True
    # Catch semi-transparent Facebook "+N" overlay: image is uniformly darkened
    return float(arr.mean()) < _OVERLAY_MEAN and float(arr.std()) < _OVERLAY_STD


def _thumb_rgb(img: Image.Image) -> "list[float]":
    t = img.resize(_THUMB_SIZE, Image.LANCZOS).convert("RGB")
    return [v / 255.0 for px in t.getdata() for v in px]   # type: ignore[union-attr]


def _mse(a: "list[float]", b: "list[float]") -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)


# ── Public API ────────────────────────────────────────────────────────────────

def split(pil_image: Image.Image) -> "list[Image.Image]":
    """
    Split a collage into individual sub-images.
    Returns a list of PIL Images ordered left-to-right, top-to-bottom,
    after filtering overlays and near-identical duplicates.
    """
    layout     = detect_layout(pil_image)
    sub_images: "list[Image.Image]" = []
    thumbs:     "list[list[float]]" = []

    for (x0, y0, x1, y1) in layout["cells"]:
        # 1. Size filter
        if (x1 - x0) < MIN_CELL_PX or (y1 - y0) < MIN_CELL_PX:
            continue
        crop = pil_image.crop((x0, y0, x1, y1))

        # 2. Overlay filter ('+N' dark-mask thumbnails)
        if _is_overlay(crop):
            continue

        # 3. Dedup filter
        t = _thumb_rgb(crop)
        if any(_mse(t, prev) < _DUP_MSE_PCT for prev in thumbs):
            continue

        thumbs.append(t)
        sub_images.append(crop)

    return sub_images


def split_from_path(path: str) -> "list[Image.Image]":
    img = Image.open(path).convert("RGB")
    return split(img)
