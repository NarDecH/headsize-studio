"""High level operations used by both the GUI and the command line."""

from __future__ import annotations

from typing import Iterable, Sequence

import cv2
import numpy as np

from headsize.core.types import HeadRegion
from headsize.core.warp import apply_head_regions

#: Long side of the interactive preview proxy.
PREVIEW_MAX_SIDE = 1400
#: Long side above which detection runs on a downscaled copy.
DETECT_MAX_SIDE = 1600


def make_proxy(image: np.ndarray, max_side: int = PREVIEW_MAX_SIDE) -> tuple[np.ndarray, float]:
    """Downscale ``image`` so its long side fits ``max_side``.

    Returns ``(proxy, scale)`` where ``scale <= 1``; multiply region coordinates
    by ``scale`` to move them into proxy space.
    """
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_side:
        return image, 1.0
    scale = max_side / float(longest)
    proxy = cv2.resize(
        image,
        (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
        interpolation=cv2.INTER_AREA,
    )
    return proxy, scale


def scale_regions(regions: Iterable[HeadRegion], factor: float) -> list[HeadRegion]:
    if factor == 1.0:
        return list(regions)
    return [
        r.copy(cx=r.cx * factor, cy=r.cy * factor, rx=r.rx * factor, ry=r.ry * factor)
        for r in regions
    ]


def render_regions(
    image: np.ndarray,
    regions: Sequence[HeadRegion],
    *,
    quality: str = "high",
) -> np.ndarray:
    """Apply ``regions`` to ``image`` and return a new array."""
    return apply_head_regions(image, regions, quality=quality)


def render_preview(
    image: np.ndarray,
    regions: Sequence[HeadRegion],
    *,
    max_side: int = PREVIEW_MAX_SIDE,
    quality: str = "balanced",
) -> tuple[np.ndarray, float]:
    """Proxy-sized render, returned with the scale that produced it."""
    proxy, scale = make_proxy(image, max_side)
    scaled = scale_regions(regions, scale)
    return apply_head_regions(proxy, scaled, quality=quality), scale


__all__ = [
    "DETECT_MAX_SIDE",
    "PREVIEW_MAX_SIDE",
    "make_proxy",
    "render_preview",
    "render_regions",
    "scale_regions",
]
