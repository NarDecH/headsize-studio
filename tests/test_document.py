"""Document model: history, selection and preview caching."""

from __future__ import annotations

import numpy as np
import pytest

from headsize.core.document import Document
from headsize.core.io import ImageData
from headsize.core.types import HeadRegion


@pytest.fixture
def doc(portrait_image) -> Document:
    return Document(ImageData(array=portrait_image))


def test_add_and_remove_regions(doc) -> None:
    index = doc.add_region(HeadRegion(cx=180, cy=200, rx=70, ry=90, scale=1.2))
    assert index == 0
    assert doc.active_region is not None
    assert doc.active_region.name == "Head 1"
    doc.add_region(HeadRegion(cx=90, cy=200, rx=30, ry=40))
    assert len(doc.regions) == 2
    assert doc.regions[1].name == "Head 2"
    doc.remove_region(0)
    assert len(doc.regions) == 1
    assert doc.selected == 0


def test_undo_redo_restores_parameters(doc) -> None:
    doc.add_region(HeadRegion(cx=180, cy=200, rx=70, ry=90, scale=1.0))
    doc.update_region(0, scale=1.4, label="scale")
    assert doc.regions[0].scale == 1.4
    assert doc.undo() is True
    assert doc.regions[0].scale == 1.0
    assert doc.undo() is True
    assert doc.regions == []
    assert doc.undo() is False
    assert doc.redo() is True
    assert len(doc.regions) == 1
    assert doc.redo() is True
    assert doc.regions[0].scale == 1.4
    assert doc.redo() is False


def test_edit_block_is_one_undo_step(doc) -> None:
    doc.add_region(HeadRegion(cx=180, cy=200, rx=70, ry=90))
    with doc.edit("drag"):
        doc.regions[0] = doc.regions[0].copy(cx=200)
        doc.regions[0] = doc.regions[0].copy(cx=210)
        doc.regions[0] = doc.regions[0].copy(cx=220)
    assert doc.regions[0].cx == 220
    doc.undo()
    assert doc.regions[0].cx == 180


def test_no_op_edit_is_not_recorded(doc) -> None:
    doc.add_region(HeadRegion(cx=180, cy=200, rx=70, ry=90))
    depth = len(doc._undo)
    with doc.edit("nothing"):
        pass
    assert len(doc._undo) == depth


def test_new_edit_clears_redo(doc) -> None:
    doc.add_region(HeadRegion(cx=180, cy=200, rx=70, ry=90))
    doc.update_region(0, scale=1.3)
    doc.undo()
    assert doc.can_redo
    doc.update_region(0, scale=0.9)
    assert not doc.can_redo


def test_preview_is_cached_and_invalidated(doc) -> None:
    doc.add_region(HeadRegion(cx=180, cy=200, rx=70, ry=90, scale=1.5))
    first, scale = doc.preview()
    second, _ = doc.preview()
    assert first is second  # served from cache
    assert scale == pytest.approx(1.0)
    doc.update_region(0, scale=1.6)
    third, _ = doc.preview()
    assert third is not first
    assert not np.array_equal(third, first)


def test_preview_shrinks_large_images(portrait_image) -> None:
    import cv2

    big = cv2.resize(portrait_image, (2800, 2000))
    doc = Document(ImageData(array=big))
    doc.add_region(HeadRegion(cx=1400, cy=800, rx=300, ry=380, scale=1.3))
    result, scale = doc.preview(max_side=1400)
    assert scale == pytest.approx(0.5)
    assert max(result.shape[:2]) <= 1400
    assert result.shape[2] == 3


def test_full_render_matches_engine(portrait_image) -> None:
    from headsize.core.warp import apply_head_regions

    doc = Document(ImageData(array=portrait_image))
    region = HeadRegion(cx=180, cy=200, rx=70, ry=90, scale=1.2)
    doc.add_region(region)
    expected = apply_head_regions(portrait_image, doc.regions)
    assert np.array_equal(doc.render_full(), expected)


def test_update_all_only_touches_matching(doc) -> None:
    doc.add_region(HeadRegion(cx=180, cy=200, rx=70, ry=90, scale=1.0))
    doc.add_region(HeadRegion(cx=90, cy=200, rx=30, ry=40, scale=1.5))
    changed = doc.update_all(where=lambda r: r.origin == "manual", scale=1.9)
    assert changed == 2
    assert [r.scale for r in doc.regions] == [1.9, 1.9]


def test_selection_is_clamped(doc) -> None:
    doc.add_region(HeadRegion(cx=180, cy=200, rx=70, ry=90))
    doc.select(5)
    assert doc.selected == -1
    doc.select(0)
    assert doc.selected == 0


def test_dirty_flag_lifecycle(doc) -> None:
    assert doc.dirty is False
    doc.add_region(HeadRegion(cx=180, cy=200, rx=70, ry=90))
    assert doc.dirty is True
    doc.dirty = False
    doc.select(0)
    assert doc.dirty is False
