"""Headless GUI tests.

The window is built offscreen, images are edited through the same code paths the
buttons use, and the result is asserted from the document and the rendered
pixels — not just "it did not crash".
"""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PyQt6.QtGui import QImage  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from headsize.core.config import AppConfig  # noqa: E402
from headsize.core.io import save_image  # noqa: E402
from headsize.core.types import HeadRegion  # noqa: E402
from headsize.ui import i18n  # noqa: E402
from headsize.ui.main_window import MainWindow  # noqa: E402
from headsize.ui.theme import LIGHT, DARK, build_qss  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, tmp_path, monkeypatch, portrait_image):
    """A MainWindow with a small portrait loaded, using a throwaway config."""
    monkeypatch.setenv("HEADSIZE_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("HEADSIZE_UPDATE_OWNER", "")
    config = AppConfig(check_updates_on_start=False, auto_detect_on_open=False)
    main = MainWindow(config)
    source = tmp_path / "portrait.png"
    save_image(portrait_image, source)
    main.open_path(str(source))
    yield main
    main.doc.dirty = False
    main.close()
    main.deleteLater()


# ------------------------------------------------------------------ structure
def test_window_has_the_expected_parts(window) -> None:
    assert window.centralWidget() is not None
    assert window.panel.isVisible() or not window.isVisible()
    assert window.canvas.width() > 200 and window.canvas.height() > 200
    assert window.menuBar().actions(), "menu bar must have menus"
    assert window.findChildren(type(window.toolbar)) or window.toolbar.actions()


def test_sidebar_and_canvas_do_not_overlap(window) -> None:
    window.resize(1200, 800)
    window.show()
    QApplication.processEvents()
    panel_rect = window.panel.geometry()
    canvas_rect = window.canvas.geometry()
    assert panel_rect.right() <= canvas_rect.left()
    assert canvas_rect.width() > 400


def test_all_sidebar_widgets_fit_inside(window) -> None:
    window.resize(1280, 900)
    window.show()
    QApplication.processEvents()
    for child in window.panel.findChildren(type(window.panel.scale_slider)):
        assert child.width() > 60 and child.height() > 10


# ---------------------------------------------------------------- document io
def test_image_is_loaded_and_displayed(window, portrait_image) -> None:
    assert window.doc.has_image
    assert window.doc.size == (portrait_image.shape[1], portrait_image.shape[0])
    assert window.canvas.has_image
    assert window.canvas.zoom > 0


def test_detect_or_manual_region_then_scale(window) -> None:
    window.detect_faces()
    window.workers.wait(20000)
    QApplication.processEvents()
    if not window.doc.regions:
        window.add_head_centred()
    assert window.doc.regions, "a head region must exist after detection or manual add"

    window._on_scale_changed(1.35, True)
    QApplication.processEvents()
    assert window.doc.regions[0].scale == pytest.approx(1.35)

    region = window.doc.regions[0]
    scaled = region.copy(
        cx=region.cx * 0.1, cy=region.cy * 0.1, rx=region.rx * 0.1, ry=region.ry * 0.1
    )
    from headsize.core.warp import apply_head_regions

    assert not np.array_equal(
        apply_head_regions(window.doc.array, [scaled]), window.doc.array
    )


def test_undo_redo_through_the_window(window) -> None:
    window.add_head_centred()
    count = len(window.doc.regions)
    window._on_scale_changed(1.5, True)
    assert window.doc.regions[0].scale == pytest.approx(1.5)
    window.undo()
    assert window.doc.regions[0].scale == pytest.approx(1.0)
    window.redo()
    assert window.doc.regions[0].scale == pytest.approx(1.5)
    assert len(window.doc.regions) == count


def test_zoom_and_compare_modes(window) -> None:
    window.add_head_centred()
    window.canvas.fit_to_window()
    fitted = window.canvas.zoom
    window.canvas.zoom_by(2.0)
    assert window.canvas.zoom > fitted
    window.canvas.reset_zoom()
    assert window.canvas.zoom == pytest.approx(1.0, rel=1e-6)

    for mode in ("original", "split", "result"):
        window._on_compare_changed(mode)
        assert window.canvas._compare == mode


def test_overlay_toggle(window) -> None:
    window._on_overlay_toggled(False)
    assert window.canvas._show_overlay is False
    assert window.config.show_region_overlay is False
    window._on_overlay_toggled(True)
    assert window.canvas._show_overlay is True


def test_save_writes_the_rendered_result(window, tmp_path) -> None:
    window.add_head_centred()
    window._on_scale_changed(1.4, True)
    target = tmp_path / "saved.jpg"
    window._last_save_path = target

    from headsize.core.io import load_image

    window.save_image()
    assert target.exists()
    rendered = load_image(target)
    expected = window.doc.render_full(quality=window.config.render_quality)
    difference = np.abs(
        rendered.array.astype(int)[:, :, :3] - expected.astype(int)
    ).mean()
    assert difference < 6.0
    assert window.doc.dirty is False


def test_reset_edits(window) -> None:
    window.add_head_centred()
    window._on_scale_changed(1.8, True)
    window.reset_edits()
    assert all(r.scale == pytest.approx(1.0) for r in window.doc.regions)


def test_regions_can_be_toggled_and_deleted(window) -> None:
    window.add_head_centred()
    window.add_head_centred()
    assert len(window.doc.regions) == 2
    window._on_region_toggle(0)
    assert window.doc.regions[0].enabled is False
    window._on_region_delete(0)
    assert len(window.doc.regions) == 1
    window.clear_regions()
    assert window.doc.regions == []


def test_scale_preset_applies_to_all(window) -> None:
    window.add_head_centred()
    window.add_head_centred()
    window._on_scale_changed(1.25, True)
    window.apply_scale_to_all()
    assert [r.scale for r in window.doc.regions] == pytest.approx([1.25, 1.25])


def test_canvas_drag_moves_a_region(window) -> None:
    window.add_head_centred()
    index = window.doc.selected
    region = window.doc.regions[index]
    before = region.copy()

    # Simulate the canvas drag callbacks directly (no real mouse in offscreen).
    window._on_region_changed(index, {"cx": before.cx + 30, "cy": before.cy + 12})
    assert window.doc.regions[index].cx == pytest.approx(before.cx + 30)
    window._on_region_committed(index, {"cx": before.cx + 30, "cy": before.cy + 12})
    assert window.doc.can_undo
    window.undo()
    assert window.doc.regions[index].cx == pytest.approx(before.cx)


def test_canvas_hit_testing_finds_the_region(window) -> None:
    window.add_head_centred()
    window.canvas.set_regions(window.doc.regions, window.doc.selected)
    region = window.doc.regions[0]
    view_point = window.canvas._to_view(region.cx, region.cy)
    index, handle = window.canvas._hit_test(view_point)
    assert index == 0
    assert handle == "move"

    outside = window.canvas._to_view(region.cx + region.rx * 3, region.cy)
    assert window.canvas._hit_test(outside)[0] == -1


def test_screenshot_is_a_rich_render(window, tmp_path) -> None:
    window.resize(1280, 840)
    window.add_head_centred()
    window.canvas.fit_to_window()
    window.show()
    QApplication.processEvents()

    image: QImage = window.grab().toImage()
    path = tmp_path / "ui.png"
    assert image.save(str(path))
    assert path.stat().st_size > 20_000

    buffer = image.convertToFormat(QImage.Format.Format_RGB888)
    pointer = buffer.constBits()
    pointer.setsize(buffer.sizeInBytes())
    pixels = np.frombuffer(pointer, np.uint8).reshape(
        buffer.height(), buffer.bytesPerLine() // 3, 3
    )[:, : buffer.width()]
    colors = np.unique(pixels.reshape(-1, 3), axis=0).shape[0]
    assert colors > 400, f"the UI screenshot looks too flat ({colors} colours)"
    assert pixels.std() > 12


def test_theme_switch_rebuilds_the_ui(window) -> None:
    window.add_head_centred()
    window.set_theme("light")
    assert window.config.theme == "light"
    assert window.palette_tokens.name == "light"
    assert window.doc.regions, "document survives a theme rebuild"
    window.set_theme("dark")
    assert window.palette_tokens.name == "dark"


def test_language_switch_updates_labels(window) -> None:
    window.set_language("en")
    assert i18n.current_language() == "en"
    assert window.panel.open_button.text() == "Open an image"
    window.set_language("th")
    assert window.panel.open_button.text() == "เปิดรูปภาพ"
    window.set_language("en")


def test_stylesheet_has_no_unsubstituted_tokens() -> None:
    for palette in (DARK, LIGHT):
        qss = build_qss(palette)
        assert "@" not in qss.replace("@media", "")
        assert "{" in qss and "}" in qss


def test_update_status_messages(window) -> None:
    window._on_update_failed("network down", silent=False)
    assert "network down" in window.panel.update_banner.text_label.text()
    window.panel.clear_update_status()
    assert not window.panel.update_banner.isVisible()
