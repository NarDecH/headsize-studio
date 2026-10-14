"""The head-scaling warp: a smooth, elliptical, radially weighted spatial scale.

Math
----
Every region defines an ellipse ``E`` (centre ``C``, radii ``rx``/``ry``, roll
``angle``) and a scale factor ``s``. We build an *inverse* coordinate map from
destination to source and hand it to :func:`cv2.remap`.

For a destination pixel ``p``:

1. ``u = R(-angle) * (p - C)``      — into the ellipse frame
2. ``d = |(u.x / rx, u.y / ry)|``   — normalised elliptical radius (1 = rim)
3. ``w = falloff(d, feather)``      — 1 at the centre, 0 at the rim (C1 smooth)
4. ``m = 1 + (1/s - 1) * w``        — radial sampling shrink
5. ``src = C + R(angle) * (u * m)``

Because ``w == 1`` whenever ``d <= 1 - feather``, the inner core is scaled by
*exactly* ``s`` and the outer band blends to identity. Two properties follow and
are asserted in the tests:

* ``d >= 1`` maps to itself, so pixels outside the ellipse are untouched and
  bit-identical to the input.
* ``s == 1`` is the identity everywhere.

For ``s < 1`` the destination samples from a wider source area, so the source is
pre-blurred to avoid aliasing (``blur_shrink``).

Multiple regions are applied in list order with one remap each. Regions that do
not overlap are exact; overlapping regions are resampled once per region.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import cv2
import numpy as np

from headsize.core.types import HeadRegion

#: Row band size (pixels) used when building the coordinate map. Keeps peak
#: memory bounded for very large photos and regions.
_BAND_ROWS = 256

#: A scale this close to 1.0 is treated as a no-op.
_EPSILON = 1e-4

_QUALITY_INTERP = {
    "fast": cv2.INTER_LINEAR,
    "balanced": cv2.INTER_LINEAR,
    "high": cv2.INTER_CUBIC,
}

_QUALITY_BANDS = {"fast": 512, "balanced": 256, "high": 128}


def falloff(d: np.ndarray, feather: float) -> np.ndarray:
    """Smooth (C1) weight: 1 inside the core, 0 at the rim, smoothstep between."""
    if feather <= 1e-6:
        return (d < 1.0).astype(np.float64)
    t = np.clip((1.0 - d) / float(feather), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def map_points(
    xs: np.ndarray, ys: np.ndarray, region: HeadRegion
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Map destination points to source points. Returns ``(sx, sy, inside)``."""
    c = math.cos(region.angle)
    s = math.sin(region.angle)
    rx = max(abs(region.rx), 1e-6)
    ry = max(abs(region.ry), 1e-6)
    dx = xs - region.cx
    dy = ys - region.cy
    lx = dx * c + dy * s
    ly = -dx * s + dy * c
    d = np.sqrt((lx / rx) ** 2 + (ly / ry) ** 2)
    w = falloff(d, region.feather)
    m = 1.0 + (1.0 / region.scale - 1.0) * w
    mx = lx * m
    my = ly * m
    sx = region.cx + mx * c - my * s
    sy = region.cy + mx * s + my * c
    return sx, sy, d < 1.0


def _build_map(
    region: HeadRegion,
    width: int,
    height: int,
    grid_x0: int,
    grid_y0: int,
    offset_x: int,
    offset_y: int,
    *,
    quality: str = "high",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build remap tables for a ``height x width`` destination ROI.

    The grid runs over the *destination* pixels starting at
    ``(grid_x0, grid_y0)`` in image space, while the values stored in the table
    are relative to ``(offset_x, offset_y)`` — the origin of the source slice
    handed to :func:`cv2.remap`.
    """
    bands = _QUALITY_BANDS.get(quality, _BAND_ROWS)
    map_x = np.empty((height, width), dtype=np.float32)
    map_y = np.empty((height, width), dtype=np.float32)
    inside = np.empty((height, width), dtype=bool)

    xs = np.arange(grid_x0, grid_x0 + width, dtype=np.float64)[None, :]
    for row in range(0, height, bands):
        stop = min(row + bands, height)
        ys = np.arange(grid_y0 + row, grid_y0 + stop, dtype=np.float64)[:, None]
        sx, sy, mask = map_points(xs, ys, region)
        map_x[row:stop] = (sx - offset_x).astype(np.float32)
        map_y[row:stop] = (sy - offset_y).astype(np.float32)
        inside[row:stop] = mask
    return map_x, map_y, inside


def _apply_single_inplace(
    image: np.ndarray,
    region: HeadRegion,
    *,
    quality: str,
    blur_shrink: bool,
) -> bool:
    """Warp one region into ``image`` (modified in place). True if anything changed."""
    if not region.enabled or abs(region.scale - 1.0) < _EPSILON:
        return False
    if region.scale <= 0 or not math.isfinite(region.scale):
        return False

    height, width = image.shape[:2]
    bx0, by0, bx1, by1 = region.bbox

    # Destination ROI = the ellipse bounding box (clipped to the image).
    dx0 = max(0, int(math.floor(bx0)))
    dy0 = max(0, int(math.floor(by0)))
    dx1 = min(width, int(math.ceil(bx1)) + 1)
    dy1 = min(height, int(math.ceil(by1)) + 1)
    if dx1 - dx0 < 1 or dy1 - dy0 < 1:
        return False

    # Source padding: a shrink of s samples up to 1/s times further out, so the
    # slice handed to remap must be larger, otherwise edge replication smears.
    reach = max(0.0, abs(1.0 / region.scale - 1.0)) * region.radius
    pad = int(math.ceil(reach)) + 2
    sx0 = max(0, dx0 - pad)
    sy0 = max(0, dy0 - pad)
    sx1 = min(width, dx1 + pad)
    sy1 = min(height, dy1 + pad)

    source = image[sy0:sy1, sx0:sx1]
    if blur_shrink and region.scale < 1.0:
        sigma = 0.6 * (1.0 / region.scale - 1.0)
        if sigma > 0.05:
            source = cv2.GaussianBlur(
                source, (0, 0), sigma, sigma, borderType=cv2.BORDER_REFLECT_101
            )

    map_x, map_y, inside = _build_map(
        region,
        dx1 - dx0,
        dy1 - dy0,
        dx0,
        dy0,
        sx0,
        sy0,
        quality=quality,
    )
    interp = _QUALITY_INTERP.get(quality, cv2.INTER_CUBIC)
    # The output of remap takes the shape of the map tables, i.e. exactly the
    # destination ROI — the *source* slice only provides the samples, which is
    # why it is padded beyond the destination region.
    warped = cv2.remap(
        source,
        map_x,
        map_y,
        interp,
        borderMode=cv2.BORDER_REFLECT_101,
    )

    destination = image[dy0:dy1, dx0:dx1]
    if not inside.all():
        # Outside the ellipse the map is the identity; keep the original pixels
        # so untouched areas stay bit-exact.
        warped = np.where(inside[..., None], warped, destination)
    destination[:] = warped
    return True


def apply_head_regions(
    image: np.ndarray,
    regions: Iterable[HeadRegion],
    *,
    quality: str = "high",
    blur_shrink: bool = True,
) -> np.ndarray:
    """Return a copy of ``image`` with every region's head rescaled."""
    out = np.array(image, copy=True)
    for region in regions:
        _apply_single_inplace(out, region, quality=quality, blur_shrink=blur_shrink)
    return out


def render_inplace(
    image: np.ndarray,
    regions: Sequence[HeadRegion],
    *,
    quality: str = "high",
    blur_shrink: bool = True,
) -> np.ndarray:
    """Warp regions into ``image`` in place (the caller owns the array)."""
    for region in regions:
        _apply_single_inplace(image, region, quality=quality, blur_shrink=blur_shrink)
    return image


def affected_bounds(
    regions: Iterable[HeadRegion], width: int, height: int
) -> tuple[int, int, int, int] | None:
    """Union of the regions' clamped bounding boxes, or ``None`` when empty."""
    x0 = y0 = math.inf
    x1 = y1 = -math.inf
    for region in regions:
        if not region.enabled or abs(region.scale - 1.0) < _EPSILON:
            continue
        bx0, by0, bx1, by1 = region.bbox
        x0, y0 = min(x0, bx0), min(y0, by0)
        x1, y1 = max(x1, bx1), max(y1, by1)
    if not math.isfinite(x0):
        return None
    return (
        max(0, int(math.floor(x0))),
        max(0, int(math.floor(y0))),
        min(width, int(math.ceil(x1)) + 1),
        min(height, int(math.ceil(y1)) + 1),
    )


__all__ = [
    "affected_bounds",
    "apply_head_regions",
    "falloff",
    "map_points",
    "render_inplace",
]
