"""
Generates ordered photo lists for each variant (no pre-composing).

Composing is done live in app.py so layout changes always produce correct results.
"""

from typing import List
from PIL import Image
from transformer import transform_all

MAIN_AREA_THRESHOLD = 0.35
LAYOUT_NEEDS = {"1+2": 3, "1+3": 4, "2+3": 5}


def generate_variant_parts(
    raw_parts: List[Image.Image],
    layout: str,
    n: int = 4,
) -> List[List[Image.Image]]:
    """
    Returns n lists of ordered sub-images for each variant.
    Each list has at most LAYOUT_NEEDS[layout] photos.
    No composing — caller composes live with current layout.
    """
    total = len(raw_parts)
    if total < 1:
        return []

    areas     = [p.width * p.height for p in raw_parts]
    area_rank = sorted(range(total), key=lambda i: areas[i], reverse=True)

    # Every photo can take the main slot so each variant shows a different main.
    # Ordered largest-first → variant 1 uses the biggest (highest quality) photo.
    main_pool = area_rank

    needed = LAYOUT_NEEDS.get(layout, 4)
    result: List[List[Image.Image]] = []

    for v in range(n):
        seed     = 42 + v * 19
        main_idx = main_pool[v % len(main_pool)]
        rest     = [i for i in area_rank if i != main_idx]
        shift    = (v // len(main_pool)) % max(1, len(rest)) if rest else 0
        rest_shifted = rest[shift:] + rest[:shift]

        ordered = ([raw_parts[main_idx]] + [raw_parts[i] for i in rest_shifted])[:needed]
        result.append(transform_all(ordered, base_seed=seed))

    return result
