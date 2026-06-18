"""
Removes fake "+N" clickbait text from a collage using OpenCV inpainting.

The AI text box from api_detector is only approximate, so we expand it
generously, threshold the brightest pixels inside (the white glyphs), dilate to
cover anti-aliased edges, then Navier-Stokes inpaint. This removes the text
cleanly while reconstructing the surrounding texture. Faces are never touched —
"+N" text always sits in a corner tile, never over a face.
"""

from typing import List, Tuple
import numpy as np
import cv2
from PIL import Image

Box = Tuple[int, int, int, int]

_EXPAND_FRAC  = 0.6    # grow the AI box by 60% of its size on each side
_GLYPH_PCTL   = 97     # pixels brighter than this percentile inside box = glyph
_GLYPH_MIN    = 150    # but never threshold below this absolute luminance
_DILATE_PX    = 13     # cover glyph halo / anti-aliased edges
_INPAINT_RAD  = 7


def remove_fake_text(pil_image: Image.Image, text_boxes: List[Box]) -> Image.Image:
    """Return a copy of the image with the +N text regions inpainted out."""
    if not text_boxes:
        return pil_image

    bgr = cv2.cvtColor(np.array(pil_image.convert("RGB")), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    mask = np.zeros((h, w), dtype=np.uint8)

    for (x0, y0, x1, y1) in text_boxes:
        bw, bh = x1 - x0, y1 - y0
        ex0 = max(0, int(x0 - bw * _EXPAND_FRAC))
        ey0 = max(0, int(y0 - bh * _EXPAND_FRAC))
        ex1 = min(w, int(x1 + bw * _EXPAND_FRAC))
        ey1 = min(h, int(y1 + bh * _EXPAND_FRAC))
        if ex1 <= ex0 or ey1 <= ey0:
            continue
        region = gray[ey0:ey1, ex0:ex1]
        thr = max(_GLYPH_MIN, int(np.percentile(region, _GLYPH_PCTL)))
        mask[ey0:ey1, ex0:ex1] = (region > thr).astype(np.uint8) * 255

    if _DILATE_PX > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_DILATE_PX, _DILATE_PX))
        mask = cv2.dilate(mask, k, iterations=1)

    result = cv2.inpaint(bgr, mask, _INPAINT_RAD, cv2.INPAINT_NS)
    rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)
