"""
Generates visually distinct composition variants from the same sub-images.

Returns (variants, variant_parts):
  variants       — list of 4 × 1080×1080 PIL Images (final composed)
  variant_parts  — list of 4 × list[PIL.Image] (transformed sub-images, pre-compose)
                   used by the UI pan/reposition feature to recompose with new offsets
"""

from typing import List, Tuple
from PIL import Image
from transformer import transform_all
from composer import compose

MAIN_AREA_THRESHOLD = 0.35
LAYOUT_NEEDS = {"1+2": 3, "1+3": 4, "2+3": 5}


def generate_variants(
    raw_parts: List[Image.Image],
    layout: str,
    n: int = 4,
) -> Tuple[List[Image.Image], List[List[Image.Image]]]:
    """
    Returns:
        variants      — n composed 1080×1080 images
        variant_parts — n lists of transformed sub-images (one list per variant)
    """
    total = len(raw_parts)
    if total < 2:
        return [], []

    areas     = [p.width * p.height for p in raw_parts]
    max_area  = max(areas)
    area_rank = sorted(range(total), key=lambda i: areas[i], reverse=True)

    main_pool = [i for i in area_rank if areas[i] >= max_area * MAIN_AREA_THRESHOLD]
    if not main_pool:
        main_pool = area_rank[:1]

    variants:      List[Image.Image]       = []
    variant_parts: List[List[Image.Image]] = []

    for v in range(n):
        seed     = 42 + v * 19
        main_idx = main_pool[v % len(main_pool)]
        rest     = [i for i in area_rank if i != main_idx]
        shift    = (v // len(main_pool)) % max(1, len(rest))
        rest_shifted = rest[shift:] + rest[:shift]

        ordered = [raw_parts[main_idx]] + [raw_parts[i] for i in rest_shifted]
        # Pad to fill layout slots by cycling right-column photos
        needed = LAYOUT_NEEDS.get(layout, 4)
        if len(rest_shifted) > 0:
            while len(ordered) < needed:
                fill = rest_shifted[(len(ordered) - 1) % len(rest_shifted)]
                ordered.append(raw_parts[fill])
        else:
            ordered = (ordered * needed)[:needed]

        transformed = transform_all(ordered, base_seed=seed)
        result      = compose(transformed, layout=layout, respect_order=True)

        variants.append(result)
        variant_parts.append(transformed)

    return variants, variant_parts
