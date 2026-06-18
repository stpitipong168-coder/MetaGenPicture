"""
AI-powered collage analysis using Claude Vision API.

Returns both:
- tiles      — bounding box of every real photo tile
- fake_text  — bounding boxes of fake "+N" clickbait text to erase via inpaint

Robust for asymmetric Facebook layouts (1+3, 2+3, 2+2) and dark photos that
confuse the variance-scan fallback.
"""

import io
import json
import re
import base64
from typing import List, Tuple, Dict
import numpy as np
from PIL import Image

Box = Tuple[int, int, int, int]


def analyze(pil_image: Image.Image, api_key: str) -> Dict[str, List[Box]]:
    """
    Ask Claude Vision for photo tiles + fake "+N" text regions.
    Returns {"tiles": [(x0,y0,x1,y1), ...], "fake_text": [(x0,y0,x1,y1), ...]}
    Pixel coords. Returns {"tiles": [], "fake_text": []} on any error.
    """
    empty = {"tiles": [], "fake_text": []}
    try:
        import anthropic
    except ImportError:
        return empty

    w, h = pil_image.size

    max_side = 1024
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        send_img = pil_image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    else:
        send_img = pil_image

    buf = io.BytesIO()
    send_img.save(buf, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    prompt = (
        "This image is a social media collage made of several real photos in a grid.\n\n"
        "Return a JSON object with two keys:\n"
        '1. "tiles": bounding box of EVERY real photo tile in the grid.\n'
        "   - A tile showing text like '+6' or '+8' is a REAL photo with fake clickbait "
        "text stamped on it — INCLUDE it as a normal tile.\n"
        "   - One box per visible tile, covering the full tile rectangle.\n"
        "   - Do NOT split one photo into pieces or merge two tiles into one.\n"
        "   - IMPORTANT: rows can have DIFFERENT numbers of photos (e.g. 2 photos on "
        "the top row and 3 photos on the bottom row). Look at each row separately and "
        "count every single distinct photo — do not assume a uniform grid.\n"
        "   - Ignore thin text banners/watermarks shorter than 10% of image height.\n"
        '2. "fake_text": tight bounding box around any fake "+N" clickbait number text '
        "(e.g. '+6', '+8'). Empty array if none. Box ONLY the text glyphs, not the whole tile.\n\n"
        "All coordinates are fractions 0.0-1.0 of (image width, image height).\n"
        "Example:\n"
        '{"tiles":[{"x0":0.0,"y0":0.0,"x1":0.58,"y1":1.0},'
        '{"x0":0.59,"y0":0.0,"x1":1.0,"y1":0.33}],'
        '"fake_text":[{"x0":0.78,"y0":0.85,"x1":0.92,"y1":0.95}]}\n\n'
        "Output the JSON object only — no explanation, no markdown."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            temperature=0,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
    except Exception:
        return empty

    text = response.content[0].text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return empty

    try:
        data = json.loads(match.group())
    except (json.JSONDecodeError, ValueError):
        return empty

    def _to_px(items, min_px) -> List[Box]:
        out: List[Box] = []
        for c in items or []:
            try:
                x0 = max(0, int(float(c["x0"]) * w))
                y0 = max(0, int(float(c["y0"]) * h))
                x1 = min(w, int(float(c["x1"]) * w))
                y1 = min(h, int(float(c["y1"]) * h))
            except (KeyError, TypeError, ValueError):
                continue
            if (x1 - x0) >= min_px and (y1 - y0) >= min_px:
                out.append((x0, y0, x1, y1))
        return out

    tiles = _to_px(data.get("tiles"), 80)
    tiles = _clip_overlaps(tiles)
    tiles = _snap_edges(pil_image, tiles)
    tiles.sort(key=lambda c: (c[2] - c[0]) * (c[3] - c[1]), reverse=True)
    fake_text = _to_px(data.get("fake_text"), 6)

    return {"tiles": tiles, "fake_text": fake_text}


def _snap_edges(pil_image: Image.Image, tiles: List[Box], win_frac: float = 0.045) -> List[Box]:
    """The AI's tile boundaries can land a little inside a neighbour, leaving a
    thin strip of the wrong photo at a cell edge. Snap each shared internal edge
    to the strongest image gradient (the real seam) within a small window."""
    if len(tiles) < 2:
        return tiles

    gray = np.array(pil_image.convert("L"), dtype=np.float32)
    h, w = gray.shape
    gx = np.abs(np.diff(gray, axis=1)).mean(axis=0)   # per-column gradient
    gy = np.abs(np.diff(gray, axis=0)).mean(axis=1)   # per-row gradient

    def snap(coord: int, grad: np.ndarray, length: int) -> int:
        if coord <= 2 or coord >= length - 2:
            return coord   # outer edge — leave at image border
        win = max(6, int(length * win_frac))
        lo, hi = max(1, coord - win), min(len(grad) - 1, coord + win)
        if hi <= lo:
            return coord
        return lo + int(np.argmax(grad[lo:hi]))

    def cluster(vals, length):
        """Map each near-equal coordinate to a single snapped value."""
        uniq = sorted(set(vals))
        mapping, group = {}, []
        tol = max(4, int(length * 0.02))
        for v in uniq:
            if group and v - group[-1] > tol:
                rep = group[len(group) // 2]
                snapped = snap(rep, gx if length == w else gy, length)
                for g in group:
                    mapping[g] = snapped
                group = []
            group.append(v)
        if group:
            rep = group[len(group) // 2]
            snapped = snap(rep, gx if length == w else gy, length)
            for g in group:
                mapping[g] = snapped
        return mapping

    xmap = cluster([t[0] for t in tiles] + [t[2] for t in tiles], w)
    ymap = cluster([t[1] for t in tiles] + [t[3] for t in tiles], h)

    # Trim the original collage's thin separator line at internal (shared) edges.
    inset = max(6, int(min(w, h) * 0.012))

    out = []
    for (x0, y0, x1, y1) in tiles:
        nx0, nx1 = xmap.get(x0, x0), xmap.get(x1, x1)
        ny0, ny1 = ymap.get(y0, y0), ymap.get(y1, y1)
        # inset only edges that touch a neighbour (not the image border)
        if nx0 > 2:          nx0 += inset
        if nx1 < w - 2:      nx1 -= inset
        if ny0 > 2:          ny0 += inset
        if ny1 < h - 2:      ny1 -= inset
        if nx1 - nx0 >= 80 and ny1 - ny0 >= 80:
            out.append((nx0, ny0, nx1, ny1))
        else:
            out.append((x0, y0, x1, y1))
    return out


def _area(b: Box) -> int:
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def _overlap(a: Box, b: Box) -> int:
    ox = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    oy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return ox * oy


def _clip_overlaps(tiles: List[Box]) -> List[Box]:
    """The LLM sometimes returns the main tile as the whole image, overlapping
    the smaller tiles. Clip any large tile so it doesn't cover smaller ones that
    sit clearly to its right or below (the only Facebook collage arrangements)."""
    if len(tiles) < 2:
        return tiles

    ordered = sorted(tiles, key=_area, reverse=True)
    out: List[Box] = []
    for i, big in enumerate(ordered):
        bx0, by0, bx1, by1 = big
        smaller = ordered[i + 1:]
        # tiles that the big one substantially covers
        covered = [s for s in smaller if _overlap(big, s) > 0.5 * _area(s)]
        if covered:
            bw, bh = bx1 - bx0, by1 - by0
            to_right = all(s[0] >= bx0 + 0.4 * bw for s in covered)
            below    = all(s[1] >= by0 + 0.4 * bh for s in covered)
            if to_right:
                bx1 = min(s[0] for s in covered)
            elif below:
                by1 = min(s[1] for s in covered)
        out.append((bx0, by0, bx1, by1))
    return out


def detect_cells(pil_image: Image.Image, api_key: str) -> List[Box]:
    """Backward-compatible: return only the photo tiles."""
    return analyze(pil_image, api_key)["tiles"]
