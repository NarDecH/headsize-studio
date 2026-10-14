"""Document model: image + regions + undo history + preview cache.

The engine is *parametric*: the source image is never modified, only the list of
:class:`~headsize.core.types.HeadRegion` objects. Undo/redo therefore stores
cheap parameter snapshots instead of pixels, and any rendering can be redone at
any quality from the original pixels.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import cv2
import numpy as np

from headsize.core.io import ImageData, load_image
from headsize.core.types import HeadRegion
from headsize.core.warp import apply_head_regions

#: Preview proxies are capped to this many pixels on the long side.
PREVIEW_MAX_SIDE = 1400

_HISTORY_LIMIT = 80


@dataclass
class _Snapshot:
    regions: list[HeadRegion]
    selected: int
    label: str = ""


class Document:
    """Editable document: one image plus the list of head regions."""

    def __init__(self, image: ImageData | None = None) -> None:
        self.source: ImageData | None = image
        self.regions: list[HeadRegion] = []
        self.selected: int = -1
        self.dirty: bool = False
        self._undo: list[_Snapshot] = []
        self._redo: list[_Snapshot] = []
        self._edit_depth = 0
        self._pending: _Snapshot | None = None
        self._preview_key: tuple | None = None
        self._preview_cache: np.ndarray | None = None
        self._preview_source: np.ndarray | None = None
        self._preview_scale: float = 1.0

    # ------------------------------------------------------------- image
    @property
    def has_image(self) -> bool:
        return self.source is not None

    @property
    def array(self) -> np.ndarray:
        if self.source is None:
            raise RuntimeError("No image loaded")
        return self.source.array

    @property
    def size(self) -> tuple[int, int]:
        return self.source.size if self.source else (0, 0)

    def load(self, path: str | Path) -> None:
        self.source = load_image(path)
        self.regions = []
        self.selected = -1
        self.dirty = False
        self._undo.clear()
        self._redo.clear()
        self.invalidate()

    def replace_image(self, image: ImageData) -> None:
        self.source = image
        self.regions = []
        self.selected = -1
        self.dirty = False
        self._undo.clear()
        self._redo.clear()
        self.invalidate()

    # ----------------------------------------------------------- regions
    @property
    def active_region(self) -> HeadRegion | None:
        if 0 <= self.selected < len(self.regions):
            return self.regions[self.selected]
        return None

    def add_region(self, region: HeadRegion, *, select: bool = True, label: str = "") -> int:
        width, height = self.size
        region = region.clamped(width, height) if width else region
        if not region.name:
            region.name = _default_name(self.regions)
        with self.edit(label or "add-region"):
            self.regions.append(region)
            index = len(self.regions) - 1
            if select:
                self.selected = index
        return index

    def set_regions(
        self, regions: Iterable[HeadRegion], *, select: int = 0, label: str = ""
    ) -> None:
        width, height = self.size
        cleaned = [r.clamped(width, height) for r in regions] if width else list(regions)
        for index, region in enumerate(cleaned):
            if not region.name:
                region.name = _default_name(cleaned[:index])
        with self.edit(label or "set-regions"):
            self.regions = cleaned
            self.selected = min(select, len(cleaned) - 1) if cleaned else -1

    def remove_region(self, index: int) -> None:
        if not (0 <= index < len(self.regions)):
            return
        with self.edit("remove-region"):
            self.regions.pop(index)
            if not self.regions:
                self.selected = -1
            else:
                self.selected = min(index, len(self.regions) - 1)

    def clear_regions(self) -> None:
        if not self.regions:
            return
        with self.edit("clear-regions"):
            self.regions = []
            self.selected = -1

    def update_region(self, index: int, *, label: str = "", **changes) -> None:
        """Change fields of one region inside a single undo entry."""
        if not (0 <= index < len(self.regions)):
            return
        with self.edit(label or "update-region"):
            region = self.regions[index].copy(**changes)
            width, height = self.size
            self.regions[index] = region.clamped(width, height) if width else region

    def apply_live(self, index: int, **changes) -> HeadRegion | None:
        """Mutate a region without creating an undo entry (live drag feedback).

        The caller is expected to call :meth:`push_history` once the interaction
        finishes, with the state captured before the drag started.
        """
        if not (0 <= index < len(self.regions)):
            return None
        region = self.regions[index].copy(**changes)
        width, height = self.size
        self.regions[index] = region.clamped(width, height) if width else region
        self.dirty = True
        self.invalidate()
        return self.regions[index]

    def push_history(self, regions: Iterable[HeadRegion], label: str = "") -> None:
        """Record an explicit undo step (used to close a drag interaction)."""
        snapshot = [r.copy() for r in regions]
        if _same_regions(snapshot, self.regions):
            return
        self._undo.append(_Snapshot(regions=snapshot, selected=self.selected, label=label))
        if len(self._undo) > _HISTORY_LIMIT:
            self._undo.pop(0)
        self._redo.clear()
        self.dirty = True

    def update_all(self, *, label: str = "", where=None, **changes) -> int:
        """Apply the same field changes to every region. Returns how many changed."""
        changed = 0
        width, height = self.size
        with self.edit(label or "update-all"):
            new_regions = []
            for region in self.regions:
                if where is not None and not where(region):
                    new_regions.append(region)
                    continue
                updated = region.copy(**changes)
                if width:
                    updated = updated.clamped(width, height)
                new_regions.append(updated)
                changed += 1
            self.regions = new_regions
        return changed

    def select(self, index: int) -> None:
        self.selected = index if 0 <= index < len(self.regions) else -1

    # ----------------------------------------------------------- history
    @contextmanager
    def edit(self, label: str = "") -> Iterator[None]:
        """Group mutations into a single undo step (nestable)."""
        outer = self._edit_depth == 0
        if outer:
            self._pending = self._snapshot(label)
        self._edit_depth += 1
        try:
            yield
        finally:
            self._edit_depth -= 1
            if outer:
                self._commit()
        self.invalidate()

    def _snapshot(self, label: str) -> _Snapshot:
        return _Snapshot(
            regions=[r.copy() for r in self.regions], selected=self.selected, label=label
        )

    def _commit(self) -> None:
        if self._pending is None:
            return
        before = self._pending
        self._pending = None
        if _same_regions(before.regions, self.regions) and before.selected == self.selected:
            return
        self._undo.append(before)
        if len(self._undo) > _HISTORY_LIMIT:
            self._undo.pop(0)
        self._redo.clear()
        self.dirty = True

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> bool:
        if not self._undo:
            return False
        current = self._snapshot(self._undo[-1].label)
        snapshot = self._undo.pop()
        self._redo.append(current)
        self.regions = [r.copy() for r in snapshot.regions]
        self.selected = snapshot.selected
        self.dirty = True
        self.invalidate()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        current = self._snapshot(self._redo[-1].label)
        snapshot = self._redo.pop()
        self._undo.append(current)
        self.regions = [r.copy() for r in snapshot.regions]
        self.selected = snapshot.selected
        self.dirty = True
        self.invalidate()
        return True

    def reset_scales(self) -> None:
        self.update_all(label="reset-scales", scale=1.0)

    # ----------------------------------------------------------- render
    def invalidate(self) -> None:
        self._preview_key = None
        self._preview_cache = None
        self._preview_source = None

    def preview(self, max_side: int = PREVIEW_MAX_SIDE) -> tuple[np.ndarray, float]:
        """Cached scaled-down render for display. Returns ``(image, scale)``."""
        _source, result, scale = self.preview_bundle(max_side)
        return result, scale

    def preview_bundle(
        self, max_side: int = PREVIEW_MAX_SIDE
    ) -> tuple[np.ndarray, np.ndarray, float]:
        """``(original proxy, rendered proxy, scale)`` for the interactive view."""
        if self.source is None:
            raise RuntimeError("No image loaded")
        key = (
            max_side,
            tuple(_region_key(r) for r in self.regions),
            id(self.source),
        )
        if (
            self._preview_key == key
            and self._preview_cache is not None
            and self._preview_source is not None
        ):
            return self._preview_source, self._preview_cache, self._preview_scale

        image = self.array
        height, width = image.shape[:2]
        scale = 1.0
        if max(height, width) > max_side:
            scale = max_side / float(max(height, width))
        if scale < 1.0:
            small = cv2.resize(
                image,
                (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
                interpolation=cv2.INTER_AREA,
            )
        else:
            small = image

        regions = [_scaled_region(r, scale) for r in self.regions]
        result = apply_head_regions(
            small, regions, quality="balanced" if scale < 1.0 else "high"
        )
        self._preview_key = key
        self._preview_cache = result
        self._preview_source = small
        self._preview_scale = scale
        return small, result, scale

    def render_full(self, *, quality: str = "high") -> np.ndarray:
        """Full resolution result (used when saving/exporting)."""
        if self.source is None:
            raise RuntimeError("No image loaded")
        return apply_head_regions(self.array, self.regions, quality=quality)

    # ----------------------------------------------------------- misc
    def summary(self) -> str:
        if self.source is None:
            return "no-image"
        width, height = self.size
        scaled = sum(1 for r in self.regions if abs(r.scale - 1.0) > 1e-4)
        return f"{width}x{height} regions={len(self.regions)} scaled={scaled}"


def _region_key(region: HeadRegion) -> tuple:
    return (
        round(region.cx, 3),
        round(region.cy, 3),
        round(region.rx, 3),
        round(region.ry, 3),
        round(region.angle, 5),
        round(region.scale, 5),
        round(region.feather, 4),
        bool(region.enabled),
    )


def _scaled_region(region: HeadRegion, scale: float) -> HeadRegion:
    if scale == 1.0:
        return region
    return region.copy(
        cx=region.cx * scale,
        cy=region.cy * scale,
        rx=region.rx * scale,
        ry=region.ry * scale,
    )


def _default_name(existing: Sequence[HeadRegion]) -> str:
    used = {r.name for r in existing}
    index = len(existing) + 1
    while f"Head {index}" in used:
        index += 1
    return f"Head {index}"


def _same_regions(a: Sequence[HeadRegion], b: Sequence[HeadRegion]) -> bool:
    if len(a) != len(b):
        return False
    return all(_region_key(x) == _region_key(y) for x, y in zip(a, b))


__all__ = ["Document", "PREVIEW_MAX_SIDE"]
