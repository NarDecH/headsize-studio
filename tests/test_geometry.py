"""Head-region estimation from detector output."""

from __future__ import annotations

import math

import pytest

from headsize.core.geometry import (
    estimate_head_region,
    head_height_from_box,
    scale_region,
)
from headsize.core.types import FaceDetection, HeadRegion


def test_head_height_proportion() -> None:
    # The detection box covers 30 %..100 % of the head, so head = box / 0.7.
    assert head_height_from_box(140.0) == pytest.approx(200.0)


def test_region_is_centred_on_the_eye_line(face_detection) -> None:
    region = estimate_head_region(face_detection)
    assert region.cx == pytest.approx(100.0)  # 50 + 100 / 2
    assert region.cy == pytest.approx(120.5)  # mean of the two eye landmarks
    assert region.origin == "auto"
    assert region.scale == 1.0


def test_region_is_wider_than_the_face_box(face_detection) -> None:
    region = estimate_head_region(face_detection)
    # 1.30 (skull) * 1.25 (pad) / 2 = 0.8125 of the box width.
    assert region.rx == pytest.approx(face_detection.w * 0.8125)
    assert region.ry == pytest.approx(140.0 / 0.7 * 1.22 / 2.0)
    assert region.rx < region.ry  # a head ellipse is taller than it is wide
    assert region.feather == pytest.approx(0.22)


def test_region_without_landmarks_falls_back_to_box_geometry() -> None:
    detection = FaceDetection(x=0, y=0, w=100, h=140, score=0.9)
    region = estimate_head_region(detection)
    # box top 0.30 -> eyes at 0.50 of a 200 px head => cy = 60 + 40 = 100.
    assert region.cy == pytest.approx(100.0)


def test_roll_angle_from_eye_line() -> None:
    detection = FaceDetection(
        x=0,
        y=0,
        w=100,
        h=140,
        score=0.9,
        landmarks=((50.0, 100.0), (100.0, 110.0)),
    )
    region = estimate_head_region(detection)
    assert region.angle == pytest.approx(math.atan2(10.0, 50.0), abs=1e-6)


def test_roll_angle_is_orientation_independent() -> None:
    a = FaceDetection(
        x=0, y=0, w=100, h=140, landmarks=((50.0, 100.0), (100.0, 110.0))
    )
    b = FaceDetection(
        x=0, y=0, w=100, h=140, landmarks=((100.0, 110.0), (50.0, 100.0))
    )
    assert estimate_head_region(a).angle == pytest.approx(estimate_head_region(b).angle)


def test_crazy_landmark_is_rejected() -> None:
    detection = FaceDetection(
        x=0, y=0, w=100, h=140, landmarks=((50.0, -900.0), (100.0, -900.0))
    )
    region = estimate_head_region(detection)
    assert 0 <= region.cy <= 140


def test_scale_region_grows_both_radii() -> None:
    region = HeadRegion(cx=10, cy=10, rx=10, ry=20)
    grown = scale_region(region, 1.5)
    assert (grown.rx, grown.ry) == (15.0, 30.0)
    assert region.rx == 10.0  # original untouched


def test_clamped_keeps_region_usable() -> None:
    region = HeadRegion(cx=-50, cy=9999, rx=1, ry=1e9, scale=99, feather=5)
    fixed = region.clamped(300, 400)
    assert 0 <= fixed.cx <= 300
    assert 0 <= fixed.cy <= 400
    assert fixed.rx >= 2 and fixed.rx <= 300
    assert fixed.ry <= 400
    assert fixed.scale == 3.0
    assert fixed.feather == 0.95


def test_bbox_accounts_for_rotation() -> None:
    tilted = HeadRegion(cx=100, cy=100, rx=100, ry=10, angle=math.pi / 2)
    x0, y0, x1, y1 = tilted.bbox
    assert x1 - x0 == pytest.approx(20.0, abs=1e-6)
    assert y1 - y0 == pytest.approx(200.0, abs=1e-6)
