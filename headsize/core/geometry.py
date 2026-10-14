"""Turn a detected face box into the head region used by the warp engine.

Canonical head proportions (the classic "eyes on the midline" rule) drive the
estimation, which makes the automatic region predictable and independent of the
detector's exact box:

============================  ==================================
Landmark on the head          Fraction of total head height
============================  ==================================
vertex (top of skull)         0.00
face detection box top        0.30
eye line                      0.50
face detection box bottom     1.00 (chin)
============================  ==================================

So ``head_height = box_height / 0.70`` and the head centre sits on the eye line.
"""

from __future__ import annotations

import math

from headsize.core.types import (
    DEFAULT_FEATHER,
    DEFAULT_PAD_X,
    DEFAULT_PAD_Y,
    FaceDetection,
    HeadRegion,
)

#: Face-box top measured from the vertex, as a fraction of head height.
BOX_TOP_RATIO = 0.30
#: Face-box bottom (chin) as a fraction of head height.
BOX_BOTTOM_RATIO = 1.00
#: The eye line sits halfway between vertex and chin.
EYE_RATIO = 0.50
#: Skull width relative to the detected face box width (cheeks are narrower).
HEAD_WIDTH_RATIO = 1.30


def head_height_from_box(box_height: float) -> float:
    """Total vertex-to-chin height implied by a detector box height."""
    span = BOX_BOTTOM_RATIO - BOX_TOP_RATIO
    return max(box_height, 1.0) / span


def estimate_head_region(
    detection: FaceDetection,
    *,
    pad_x: float = DEFAULT_PAD_X,
    pad_y: float = DEFAULT_PAD_Y,
    feather: float = DEFAULT_FEATHER,
    scale: float = 1.0,
) -> HeadRegion:
    """Estimate the head ellipse (hair included) for one detected face."""
    head_h = head_height_from_box(detection.h)
    rx = detection.w * HEAD_WIDTH_RATIO / 2.0 * pad_x
    ry = head_h / 2.0 * pad_y

    eye_y = _eye_line_y(detection)
    cx = detection.x + detection.w / 2.0
    angle = _roll_from_eyes(detection)

    return HeadRegion(
        cx=cx,
        cy=eye_y,
        rx=max(rx, 4.0),
        ry=max(ry, 4.0),
        angle=angle,
        scale=scale,
        feather=feather,
        origin="auto",
        score=detection.score,
    )


def _eye_line_y(detection: FaceDetection) -> float:
    """Eye-line y: from the two eye landmarks when present, else box geometry."""
    eyes = detection.landmarks[:2] if len(detection.landmarks) >= 2 else ()
    if len(eyes) == 2:
        y = (eyes[0][1] + eyes[1][1]) / 2.0
        # Guard against a freak detection: never trust it blindly.
        if detection.y <= y <= detection.y + detection.h:
            return y
    top = detection.y + BOX_TOP_RATIO * head_height_from_box(detection.h)
    return top + (EYE_RATIO - BOX_TOP_RATIO) * head_height_from_box(detection.h)


def _roll_from_eyes(detection: FaceDetection) -> float:
    """Head roll in radians from the eye line, normalised to (-pi/2, pi/2]."""
    if len(detection.landmarks) < 2:
        return 0.0
    (ax, ay), (bx, by) = detection.landmarks[0], detection.landmarks[1]
    if math.hypot(bx - ax, by - ay) < 1e-3:
        return 0.0
    angle = math.atan2(by - ay, bx - ax)
    while angle <= -math.pi / 2:
        angle += math.pi
    while angle > math.pi / 2:
        angle -= math.pi
    return angle


def scale_region(region: HeadRegion, factor: float) -> HeadRegion:
    """Grow/shrink a region's ellipse (used by the UI resize handles)."""
    return region.copy(rx=region.rx * factor, ry=region.ry * factor)


__all__ = [
    "BOX_BOTTOM_RATIO",
    "BOX_TOP_RATIO",
    "EYE_RATIO",
    "HEAD_WIDTH_RATIO",
    "estimate_head_region",
    "head_height_from_box",
    "scale_region",
]
