"""
Splits a collage image into individual sub-images.

Detection priority:
1. api_key provided → Claude Vision API (api_detector.py)
2. No api_key         → Variance scan fallback (layout_detector.py)

NOTE on "+N" marks (+1 … +15): these are FAKE clickbait text stamped onto a
real photo — there are NO hidden extra photos. Every visible cell, including a
"+N" cell, is a genuine photo and must be kept and counted.

Filters applied after cell detection:
1. Size  — cells < 80px in either dimension are ignored
2. Dedup — near-identical cells (RGB MSE < 1.5% on 16×16 thumbnail) are dropped
"""

import numpy as np
from PIL import Image
from layout_detector import detect_layout

MIN_CELL_PX     = 80
_THUMB_SIZE     = (16, 16)
_DUP_MSE_PCT    = 0.015  # near-identical only (was 0.04 → killed distinct photos)


def _thumb_rgb(img: Image.Image) -> "list[float]":
    t = img.resize(_THUMB_SIZE, Image.LANCZOS).convert("RGB")
    return [v / 255.0 for px in t.getdata() for v in px]


def _mse(a: "list[float]", b: "list[float]") -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)


# ── Public API ────────────────────────────────────────────────────────────────

def split(pil_image: Image.Image, api_key: str = "") -> "list[Image.Image]":
    """
    Split a collage into individual sub-images.
    api_key: Anthropic API key → uses Claude Vision for detection.
             Empty string     → falls back to variance scan.
    """
    # ── Detect cells (+ erase fake "+N" text) ─────────────────────────────────
    cells: "list[tuple]" = []
    used_api = False

    if api_key:
        from api_detector import analyze
        info  = analyze(pil_image, api_key)
        cells = info["tiles"]
        if cells:
            used_api = True
            if info["fake_text"]:
                from inpaint import remove_fake_text
                pil_image = remove_fake_text(pil_image, info["fake_text"])

    if not cells:
        layout = detect_layout(pil_image)
        cells  = layout["cells"]

    # ── Crop, filter, dedup ───────────────────────────────────────────────────
    sub_images: "list[Image.Image]" = []
    thumbs:     "list[list[float]]" = []

    for (x0, y0, x1, y1) in cells:
        if (x1 - x0) < MIN_CELL_PX or (y1 - y0) < MIN_CELL_PX:
            continue
        crop = pil_image.crop((x0, y0, x1, y1))

        # NOTE: "+N" cells are real photos with fake clickbait text — keep them.
        # No overlay skipping at all.

        t = _thumb_rgb(crop)
        if any(_mse(t, prev) < _DUP_MSE_PCT for prev in thumbs):
            continue

        thumbs.append(t)
        sub_images.append(crop)

    return sub_images


def split_from_path(path: str, api_key: str = "") -> "list[Image.Image]":
    img = Image.open(path).convert("RGB")
    return split(img, api_key=api_key)
