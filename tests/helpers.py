"""Small measurement helpers shared by the tests."""

from __future__ import annotations

import cv2
import numpy as np


def disk_radius(image: np.ndarray, threshold: int = 128) -> float:
    """Radius of the largest bright blob, derived from its area."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image
    area = float(np.count_nonzero(gray > threshold))
    return float(np.sqrt(area / np.pi)) if area else 0.0


def bright_centroid(image: np.ndarray, threshold: int = 128) -> tuple[float, float]:
    """Centroid of the bright pixels, or ``(0, 0)`` when there are none."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image
    mask = gray > threshold
    if not mask.any():
        return (0.0, 0.0)
    ys, xs = np.nonzero(mask)
    return (float(xs.mean()), float(ys.mean()))


__all__ = ["bright_centroid", "disk_radius"]
