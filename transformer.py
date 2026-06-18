"""
No-op transformer — images are returned exactly as-is.
All visual transforms have been removed per user requirement (ภาพเหมือนต้นฉบับ 100%).
"""

from typing import Optional, List
from PIL import Image


def transform(img: Image.Image, seed: Optional[int] = None) -> Image.Image:
    return img


def transform_all(images: List[Image.Image], base_seed: int = 42) -> List[Image.Image]:
    return list(images)
