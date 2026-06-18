"""
Composes sub-images into Facebook-style collage layouts.

Output always 1080×1080 px.
Left panel ≥ 55% canvas width. Right photos always SQUARE.
All photos are inset by BORDER px on every edge (same as GAP width).
"""

from typing import Optional, List, Tuple
from PIL import Image

CANVAS_SIZE  = (1080, 1080)
GAP          = 6    # gap between photos
BORDER       = 6    # outer white border (same thickness as inner gaps)
BG           = (255, 255, 255)
MIN_LEFT_PCT = 0.55

Offset = Tuple[float, float]


# ── Public API ────────────────────────────────────────────────────────────────

def compose(
    sub_images: List[Image.Image],
    layout: str = "1+3",
    respect_order: bool = False,
    offsets: Optional[List[Offset]] = None,
) -> Image.Image:
    if len(sub_images) < 2:
        raise ValueError("Need at least 2 sub-images.")

    ranked = list(sub_images) if respect_order else \
             sorted(sub_images, key=lambda i: i.width * i.height, reverse=True)

    fn = {
        "1+2": lambda r: _left_right(r, right_n=2, offsets=offsets),
        "1+3": lambda r: _left_right(r, right_n=3, offsets=offsets),
        "2+3": lambda r: _two_three(r, offsets=offsets),
    }.get(layout, lambda r: _left_right(r, right_n=3, offsets=offsets))

    return fn(ranked)


# ── Layout builders ───────────────────────────────────────────────────────────

def _left_right(
    ranked: List[Image.Image],
    right_n: int,
    offsets: Optional[List[Offset]] = None,
) -> Image.Image:
    right_n = min(right_n, max(1, len(ranked) - 1))
    photos  = list(ranked[:1 + right_n])
    n_slots = len(photos)
    if offsets is None:
        offsets = [(0.0, 0.0)] * n_slots
    while len(offsets) < n_slots:
        offsets.append((0.0, 0.0))

    cw, ch = CANVAS_SIZE
    aw, ah = cw - 2 * BORDER, ch - 2 * BORDER   # available area inside border

    rsize_h = (ah - GAP * (right_n - 1)) // right_n
    rsize_w = int(aw * (1 - MIN_LEFT_PCT)) - GAP
    rsize   = min(rsize_h, rsize_w)
    lw      = aw - rsize - GAP

    right_col_h = right_n * rsize + GAP * (right_n - 1)
    y0          = BORDER + (ah - right_col_h) // 2
    rx          = BORDER + lw + GAP

    canvas = Image.new("RGB", CANVAS_SIZE, BG)
    canvas.paste(_fit(photos[0], lw, ah, *offsets[0]), (BORDER, BORDER))
    for i, img in enumerate(photos[1:]):
        off = offsets[i + 1] if (i + 1) < len(offsets) else (0.0, 0.0)
        canvas.paste(_fit(img, rsize, rsize, *off), (rx, y0 + i * (rsize + GAP)))
    return canvas


def _two_three(
    ranked: List[Image.Image],
    offsets: Optional[List[Offset]] = None,
) -> Image.Image:
    photos = ranked[:5]
    while len(photos) < 5:
        photos.append(photos[-1])
    if offsets is None:
        offsets = [(0.0, 0.0)] * 5
    while len(offsets) < 5:
        offsets.append((0.0, 0.0))

    cw, ch = CANVAS_SIZE
    aw, ah = cw - 2 * BORDER, ch - 2 * BORDER

    rsize = (ah - GAP * 2) // 3
    lw    = aw - rsize - GAP
    lh    = (ah - GAP) // 2
    rx    = BORDER + lw + GAP

    canvas = Image.new("RGB", CANVAS_SIZE, BG)
    canvas.paste(_fit(photos[0], lw, lh, *offsets[0]), (BORDER, BORDER))
    canvas.paste(_fit(photos[1], lw, lh, *offsets[1]), (BORDER, BORDER + lh + GAP))
    for i, img in enumerate(photos[2:]):
        off = offsets[i + 2] if (i + 2) < len(offsets) else (0.0, 0.0)
        canvas.paste(_fit(img, rsize, rsize, *off), (rx, BORDER + i * (rsize + GAP)))
    return canvas


# ── Utility ───────────────────────────────────────────────────────────────────

def get_slot_layout(layout: str) -> List[Tuple[int, int, int, int]]:
    """Returns [(x, y, w, h), ...] for each photo slot, including BORDER offset."""
    cw, ch = CANVAS_SIZE
    aw, ah = cw - 2 * BORDER, ch - 2 * BORDER

    if layout == "1+2":
        right_n = 2
        rsize_h = (ah - GAP * (right_n - 1)) // right_n
        rsize_w = int(aw * (1 - MIN_LEFT_PCT)) - GAP
        rsize   = min(rsize_h, rsize_w)
        lw      = aw - rsize - GAP
        rcol_h  = right_n * rsize + GAP * (right_n - 1)
        y0      = BORDER + (ah - rcol_h) // 2
        rx      = BORDER + lw + GAP
        return [(BORDER, BORDER, lw, ah)] + \
               [(rx, y0 + i * (rsize + GAP), rsize, rsize) for i in range(right_n)]

    if layout == "1+3":
        right_n = 3
        rsize_h = (ah - GAP * (right_n - 1)) // right_n
        rsize_w = int(aw * (1 - MIN_LEFT_PCT)) - GAP
        rsize   = min(rsize_h, rsize_w)
        lw      = aw - rsize - GAP
        rcol_h  = right_n * rsize + GAP * (right_n - 1)
        y0      = BORDER + (ah - rcol_h) // 2
        rx      = BORDER + lw + GAP
        return [(BORDER, BORDER, lw, ah)] + \
               [(rx, y0 + i * (rsize + GAP), rsize, rsize) for i in range(right_n)]

    if layout == "2+3":
        rsize = (ah - GAP * 2) // 3
        lw    = aw - rsize - GAP
        lh    = (ah - GAP) // 2
        rx    = BORDER + lw + GAP
        return (
            [(BORDER, BORDER, lw, lh), (BORDER, BORDER + lh + GAP, lw, lh)]
            + [(rx, BORDER + i * (rsize + GAP), rsize, rsize) for i in range(3)]
        )

    return []


def compose_direct(
    crops: List[Image.Image],
    layout: str,
) -> Image.Image:
    slots  = get_slot_layout(layout)
    canvas = Image.new("RGB", CANVAS_SIZE, BG)
    for i, (x, y, w, h) in enumerate(slots):
        if i >= len(crops) or crops[i] is None:
            break
        img = crops[i].resize((w, h), Image.LANCZOS)
        canvas.paste(img, (x, y))
    return canvas


def _fit(
    img: Image.Image,
    target_w: int,
    target_h: int,
    x_off: float = 0.0,
    y_off: float = 0.0,
) -> Image.Image:
    sw, sh    = img.size
    min_scale = max(target_w / sw, target_h / sh)
    pan_mag   = max(abs(x_off), abs(y_off))
    scale     = min_scale * (1.0 + 0.35 * min(pan_mag, 1.0))

    nw = max(target_w, int(sw * scale))
    nh = max(target_h, int(sh * scale))
    img = img.resize((nw, nh), Image.LANCZOS)

    excess_x = nw - target_w
    excess_y = nh - target_h
    def_l    = excess_x // 2
    def_t    = excess_y // 2   # center crop by default
    half_ex  = excess_x // 2

    l = def_l + int(half_ex * x_off)
    if y_off <= 0:
        t = int(def_t * (1.0 + y_off))
    else:
        t = def_t + int((excess_y - def_t) * y_off)

    l = max(0, min(excess_x, l))
    t = max(0, min(excess_y, t))

    return img.crop((l, t, l + target_w, t + target_h))
