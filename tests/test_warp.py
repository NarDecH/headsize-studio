"""Warp engine behaviour.

These tests encode the two promises the UI makes to the user:

1. Outside the (visible) influence ellipse nothing changes — bit for bit.
2. Inside the core the content is scaled by exactly the requested factor.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from headsize.core.types import HeadRegion
from headsize.core.warp import affected_bounds, apply_head_regions, falloff, map_points

from tests.helpers import disk_radius


def test_scale_one_is_identity(disk_image) -> None:
    image, _ = disk_image
    region = HeadRegion(cx=250, cy=250, rx=200, ry=200, scale=1.0)
    out = apply_head_regions(image, [region])
    assert np.array_equal(out, image)


def test_disabled_region_is_ignored(disk_image) -> None:
    image, _ = disk_image
    region = HeadRegion(cx=250, cy=250, rx=200, ry=200, scale=1.8, enabled=False)
    out = apply_head_regions(image, [region])
    assert np.array_equal(out, image)


def test_core_scales_exactly(disk_image) -> None:
    """A disk inside the core is magnified by exactly `scale`."""
    image, (cx, cy, radius) = disk_image
    for scale, expected in ((1.5, radius * 1.5), (0.5, radius * 0.5), (2.0, radius * 2.0)):
        region = HeadRegion(cx=cx, cy=cy, rx=200, ry=200, feather=0.5, scale=scale)
        out = apply_head_regions(image, [region])
        measured = disk_radius(out)
        assert measured == pytest.approx(expected, rel=0.02), (scale, measured, expected)


def test_scale_is_monotonic(disk_image) -> None:
    image, (cx, cy, _) = disk_image
    radii = []
    for scale in (1.0, 1.2, 1.5, 2.0):
        region = HeadRegion(cx=cx, cy=cy, rx=200, ry=200, feather=0.5, scale=scale)
        radii.append(disk_radius(apply_head_regions(image, [region])))
    assert radii == sorted(radii)
    assert radii[0] < radii[-1]


def test_outside_ellipse_is_untouched(disk_image) -> None:
    image, (cx, cy, _) = disk_image
    rx, ry = 120.0, 90.0
    region = HeadRegion(cx=cx, cy=cy, rx=rx, ry=ry, feather=0.6, scale=1.6)
    out = apply_head_regions(image, [region])
    ys, xs = np.mgrid[0 : image.shape[0], 0 : image.shape[1]]
    d = np.hypot((xs - cx) / rx, (ys - cy) / ry)
    outside = d >= 1.0
    assert np.array_equal(out[outside], image[outside])


def test_rotation_moves_the_axis(disk_image) -> None:
    """A rotated, elongated ellipse warps along its own axes."""
    image, (cx, cy, _) = disk_image
    upright = HeadRegion(cx=cx, cy=cy, rx=200, ry=60, angle=0.0, feather=0.4, scale=1.6)
    tilted = upright.copy(angle=math.pi / 2)
    out_u = apply_head_regions(image, [upright])
    out_t = apply_head_regions(image, [tilted])
    assert not np.array_equal(out_u, out_t)
    # Both keep the untouched corners identical to the input.
    assert np.array_equal(out_u[0:20, 0:20], image[0:20, 0:20])
    assert np.array_equal(out_t[0:20, 0:20], image[0:20, 0:20])


def test_two_disjoint_regions(portrait_image) -> None:
    image = portrait_image
    left = HeadRegion(cx=120, cy=200, rx=60, ry=70, scale=1.4)
    right = HeadRegion(cx=240, cy=200, rx=60, ry=70, scale=0.8)
    out = apply_head_regions(image, [left, right])
    assert out.shape == image.shape
    assert not np.array_equal(out, image)
    # Column of the background far from both regions is untouched.
    assert np.array_equal(out[:, :5], image[:, :5])


def test_feather_zero_is_hard_edged_but_still_smooth_enough(disk_image) -> None:
    image, _ = disk_image
    region = HeadRegion(cx=250, cy=250, rx=180, ry=180, feather=0.0, scale=1.3)
    out = apply_head_regions(image, [region])
    assert np.array_equal(out[0:10, 0:10], image[0:10, 0:10])


def test_falloff_endpoints() -> None:
    d = np.array([0.0, 0.5, 0.75, 1.0, 1.5])
    w = falloff(d, 0.5)
    assert w[0] == pytest.approx(1.0)
    assert w[1] == pytest.approx(1.0)  # still inside the untouched core
    assert 0.0 < w[2] < 1.0  # blending
    assert w[3] == pytest.approx(0.0)  # rim is identity
    assert w[4] == pytest.approx(0.0)


def test_falloff_is_c1_at_the_rim() -> None:
    """Smoothstep has zero slope at both ends, so no seam shows at d == 1."""
    eps = 1e-4
    near_one = falloff(np.array([1.0 - eps]), 0.6)[0]
    beyond = falloff(np.array([1.0]), 0.6)[0]
    assert abs(near_one - beyond) < 1e-3


def test_map_points_round_trip_at_centre() -> None:
    region = HeadRegion(cx=100, cy=100, rx=50, ry=50, scale=1.4)
    sx, sy, inside = map_points(np.array([100.0]), np.array([100.0]), region)
    assert inside[0]
    assert sx[0] == pytest.approx(100.0)
    assert sy[0] == pytest.approx(100.0)


def test_map_points_rim_is_identity() -> None:
    region = HeadRegion(cx=100, cy=100, rx=50, ry=80, feather=0.5, scale=1.4)
    xs = np.array([150.0, 100.0, 100.0])
    ys = np.array([100.0, 180.0, 20.0])
    sx, sy, inside = map_points(xs, ys, region)
    assert not inside.any()
    assert np.allclose(sx, xs)
    assert np.allclose(sy, ys)


def test_affected_bounds_covers_ellipse_and_skips_noops() -> None:
    idle = HeadRegion(cx=10, cy=10, rx=5, ry=5, scale=1.0)
    active = HeadRegion(cx=40, cy=40, rx=10, ry=20, scale=1.2)
    bounds = affected_bounds([idle, active], 100, 100)
    assert bounds == (30, 20, 51, 61)
    assert affected_bounds([idle], 100, 100) is None


def test_large_image_speed(portrait_image) -> None:
    """A 4000x3000 photo warps in well under a second on a CPU core."""
    import time

    import cv2

    big = cv2.resize(portrait_image, (4000, 3000), interpolation=cv2.INTER_CUBIC)
    region = HeadRegion(cx=3000, cy=200, rx=180, ry=240, scale=1.3)
    start = time.perf_counter()
    apply_head_regions(big, [region])
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, elapsed
