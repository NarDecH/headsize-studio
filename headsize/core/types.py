"""Plain data types shared by the engine, the UI and the tests."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

#: Hair/skull padding applied on top of the detected face box when a head
#: region is estimated automatically. 1.0 = exactly the geometric head.
#:
#: A bounded warp can only push the head outwards as far as the influence rim,
#: so the maximum head growth is roughly ``1 / (head radius / zone radius)``.
#: These paddings put the head silhouette at ~0.7 of the zone radius, which
#: leaves room for about 1.4x; the UI lets the user drag the zone bigger for
#: extreme caricatures. See docs/research.md.
DEFAULT_PAD_X = 1.25
DEFAULT_PAD_Y = 1.22

#: Default blend width of the warp falloff (fraction of the ellipse radius).
#: With 0.25 the inner 75 % of the influence zone scales rigidly, so the head
#: outline grows by roughly the factor shown on the slider, while the remaining
#: 25 % blends smoothly into the hair and background. Measured numbers for
#: several values live in docs/research.md.
DEFAULT_FEATHER = 0.22

#: Scale bounds shared by the UI, the CLI and the engine.
MIN_SCALE = 0.30
MAX_SCALE = 3.00


@dataclass
class FaceDetection:
    """A face found by the detector, in image pixel coordinates."""

    x: float
    y: float
    w: float
    h: float
    score: float = 0.0
    #: (right_eye, left_eye, nose, right_mouth, left_mouth) as (x, y) pairs.
    landmarks: tuple[tuple[float, float], ...] = ()

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)

    def as_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "score": self.score,
            "landmarks": [list(p) for p in self.landmarks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FaceDetection:
        return cls(
            x=float(data["x"]),
            y=float(data["y"]),
            w=float(data["w"]),
            h=float(data["h"]),
            score=float(data.get("score", 0.0)),
            landmarks=tuple(
                (float(p[0]), float(p[1])) for p in data.get("landmarks", ())
            ),
        )


@dataclass
class HeadRegion:
    """An elliptical, rotated warp region with its own head scale.

    The ellipse is the *influence* zone: the image is scaled by ``scale`` about
    ``(cx, cy)`` inside it and left untouched outside. ``feather`` controls how
    much of the radius is used to blend from the full scale back to identity.
    With ``feather = 0.55`` the inner 45 % of the radius is scaled exactly by
    ``scale`` and the outer 55 % blends smoothly to 1.0.
    """

    cx: float
    cy: float
    rx: float
    ry: float
    angle: float = 0.0  # radians, positive = clockwise on screen
    scale: float = 1.0
    feather: float = DEFAULT_FEATHER
    enabled: bool = True
    origin: str = "manual"  # "auto" | "manual"
    score: float = 0.0
    name: str = ""
    """Optional user label ("Head 1"), shown in the region list."""

    # ---------------------------------------------------------------- helpers
    def copy(self, **changes: Any) -> HeadRegion:
        """Return a copy with ``changes`` applied (used for undo snapshots)."""
        return replace(self, **changes)

    @property
    def radius(self) -> float:
        return max(self.rx, self.ry)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Axis-aligned bounding box ``(x0, y0, x1, y1)`` of the rotated ellipse."""
        c, s = math.cos(self.angle), math.sin(self.angle)
        half_w = math.hypot(self.rx * c, self.ry * s)
        half_h = math.hypot(self.rx * s, self.ry * c)
        return (self.cx - half_w, self.cy - half_h, self.cx + half_w, self.cy + half_h)

    def clamped(self, width: int, height: int) -> HeadRegion:
        """Move the region back inside an image of the given size."""
        new = self.copy()
        new.rx = float(min(max(self.rx, 2.0), max(width, 2.0)))
        new.ry = float(min(max(self.ry, 2.0), max(height, 2.0)))
        new.cx = float(min(max(self.cx, 0.0), width))
        new.cy = float(min(max(self.cy, 0.0), height))
        new.angle = _normalize_angle(new.angle)
        new.scale = float(min(max(self.scale, MIN_SCALE), MAX_SCALE))
        new.feather = float(min(max(self.feather, 0.0), 0.95))
        return new

    def contains(self, x: float, y: float, tol: float = 0.0) -> bool:
        dx, dy = x - self.cx, y - self.cy
        c, s = math.cos(-self.angle), math.sin(-self.angle)
        lx, ly = dx * c - dy * s, dx * s + dy * c
        rx, ry = max(self.rx, 1e-6), max(self.ry, 1e-6)
        return (lx / rx) ** 2 + (ly / ry) ** 2 <= (1.0 + tol) ** 2

    # ------------------------------------------------------------ (de)serialise
    def as_dict(self) -> dict[str, Any]:
        return {
            "cx": self.cx,
            "cy": self.cy,
            "rx": self.rx,
            "ry": self.ry,
            "angle": self.angle,
            "scale": self.scale,
            "feather": self.feather,
            "enabled": self.enabled,
            "origin": self.origin,
            "score": self.score,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HeadRegion:
        return cls(
            cx=float(data["cx"]),
            cy=float(data["cy"]),
            rx=float(data["rx"]),
            ry=float(data["ry"]),
            angle=float(data.get("angle", 0.0)),
            scale=float(data.get("scale", 1.0)),
            feather=float(data.get("feather", DEFAULT_FEATHER)),
            enabled=bool(data.get("enabled", True)),
            origin=str(data.get("origin", "manual")),
            score=float(data.get("score", 0.0)),
            name=str(data.get("name", "")),
        )


def _normalize_angle(angle: float) -> float:
    """Wrap an angle into (-pi/2, pi/2] — an ellipse needs no more than that."""
    while angle <= -math.pi / 2:
        angle += math.pi
    while angle > math.pi / 2:
        angle -= math.pi
    return angle


__all__ = [
    "FaceDetection",
    "HeadRegion",
    "DEFAULT_FEATHER",
    "DEFAULT_PAD_X",
    "DEFAULT_PAD_Y",
    "MAX_SCALE",
    "MIN_SCALE",
]
