"""Interactive image canvas: zoom, pan, region handles and split compare.

Everything is stored in *image* coordinates (full resolution). The view
transform is a single scalar ``zoom`` (widget pixels per image pixel) plus an
offset, so widget <-> image conversion stays trivial.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QMenu, QWidget

from headsize.core.types import HeadRegion
from headsize.ui import icons
from headsize.ui.i18n import t
from headsize.ui.theme import Palette
from headsize.ui.widgets import ColorDot

MIN_ZOOM = 0.02
MAX_ZOOM = 16.0
#: Distance (widget pixels) at which a handle is grabbed.
HANDLE_HIT_RADIUS = 11.0
HANDLE_RADIUS = 5.0
ROTATE_ARM = 26.0
PADDING = 24.0

_HANDLE_CURSORS = {
    "n": Qt.CursorShape.SizeVerCursor,
    "s": Qt.CursorShape.SizeVerCursor,
    "e": Qt.CursorShape.SizeHorCursor,
    "w": Qt.CursorShape.SizeHorCursor,
    "move": Qt.CursorShape.SizeAllCursor,
    "rot": Qt.CursorShape.CrossCursor,
}


def numpy_to_pixmap(array: np.ndarray) -> QPixmap:
    """RGB uint8 array -> QPixmap (copies the buffer so numpy can be freed)."""
    array = np.ascontiguousarray(array)
    height, width = array.shape[:2]
    image = QImage(
        array.data, width, height, 3 * width, QImage.Format.Format_RGB888
    ).copy()
    return QPixmap.fromImage(image)


class ImageCanvas(QWidget):
    """The image area: pan/zoom, drag head regions, compare original/result."""

    region_changed = pyqtSignal(int, dict)  # live drag feedback (no undo entry)
    region_committed = pyqtSignal(int, dict)  # drag finished
    selection_changed = pyqtSignal(int)
    region_requested = pyqtSignal(float, float)  # add a head at these image coords
    delete_requested = pyqtSignal(int)
    zoom_changed = pyqtSignal(float)
    cursor_position = pyqtSignal(float, float)
    file_dropped = pyqtSignal(str)

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Canvas")
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(320, 240)

        self._palette = palette
        self._source: QPixmap | None = None
        self._result: QPixmap | None = None
        self._image_size = (0, 0)
        self._regions: list[HeadRegion] = []
        self._selected = -1
        self._zoom = 1.0
        self._offset = QPointF(0.0, 0.0)
        self._fit_pending = True
        self._show_overlay = True
        self._compare = "result"
        self._split = 0.5
        self._drag: dict | None = None
        self._pan_start = QPointF(0.0, 0.0)
        self._space_down = False
        self._hover_handle = ""

    # ------------------------------------------------------------------ state
    @property
    def has_image(self) -> bool:
        return self._source is not None

    @property
    def zoom(self) -> float:
        return self._zoom

    def set_palette_tokens(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def set_images(
        self,
        source: np.ndarray | None,
        result: np.ndarray | None,
        image_size: tuple[int, int],
    ) -> None:
        """Set both the original and rendered proxies (same size)."""
        self._source = numpy_to_pixmap(source) if source is not None else None
        self._result = numpy_to_pixmap(result) if result is not None else None
        self._image_size = image_size
        if self._fit_pending and self._source is not None:
            self.fit_to_window()
        self.update()

    def set_regions(self, regions: Sequence[HeadRegion], selected: int) -> None:
        self._regions = list(regions)
        self._selected = selected
        self.update()

    def set_overlay_visible(self, visible: bool) -> None:
        self._show_overlay = bool(visible)
        self.update()

    def set_compare(self, mode: str) -> None:
        self._compare = mode if mode in ("result", "original", "split") else "result"
        self.update()

    def set_split(self, fraction: float) -> None:
        self._split = min(max(float(fraction), 0.0), 1.0)
        self.update()

    # ----------------------------------------------------------- view helpers
    def request_fit(self) -> None:
        """Fit the next image that is loaded (also used after opening a file)."""
        self._fit_pending = True
        if self._source is not None:
            self.fit_to_window()

    def fit_to_window(self) -> None:
        if self._source is None or not self._image_size[0]:
            return
        width, height = self._image_size
        available_w = max(1.0, self.width() - 2 * PADDING)
        available_h = max(1.0, self.height() - 2 * PADDING)
        self._set_zoom(min(available_w / width, available_h / height), anchor=None)
        self._center_on_image()
        self._fit_pending = False

    def reset_zoom(self) -> None:
        if not self.has_image:
            return
        center = self._view_center_image_point()
        self._set_zoom(1.0, anchor=QPointF(self.width() / 2, self.height() / 2), image_anchor=center)
        self._fit_pending = False

    def zoom_by(self, factor: float, anchor: QPointF | None = None) -> None:
        if not self.has_image:
            return
        self._set_zoom(self._zoom * factor, anchor=anchor)
        self._fit_pending = False

    def _set_zoom(self, zoom: float, anchor: QPointF | None = None, image_anchor=None) -> None:
        zoom = min(max(zoom, MIN_ZOOM), MAX_ZOOM)
        if zoom == self._zoom:
            return
        if image_anchor is not None and anchor is not None:
            point = image_anchor
        elif anchor is not None:
            point = self._to_image(anchor)
        else:
            point = self._view_center_image_point()
        self._zoom = zoom
        if anchor is not None:
            self._offset = QPointF(anchor.x() - point.x() * zoom, anchor.y() - point.y() * zoom)
        else:
            self._offset = QPointF(
                self.width() / 2 - point.x() * zoom, self.height() / 2 - point.y() * zoom
            )
        self.zoom_changed.emit(zoom)
        self.update()

    def _center_on_image(self) -> None:
        width, height = self._image_size
        self._offset = QPointF(
            (self.width() - width * self._zoom) / 2,
            (self.height() - height * self._zoom) / 2,
        )

    def _view_center_image_point(self) -> QPointF:
        return self._to_image(QPointF(self.width() / 2, self.height() / 2))

    def _to_image(self, point: QPointF) -> QPointF:
        return QPointF(
            (point.x() - self._offset.x()) / self._zoom,
            (point.y() - self._offset.y()) / self._zoom,
        )

    def _to_view(self, x: float, y: float) -> QPointF:
        return QPointF(x * self._zoom + self._offset.x(), y * self._zoom + self._offset.y())

    def _image_rect(self) -> QRectF:
        width, height = self._image_size
        top_left = self._to_view(0, 0)
        return QRectF(top_left, QPointF(top_left.x() + width * self._zoom, top_left.y() + height * self._zoom))

    # -------------------------------------------------------------- handle math
    def _handle_points(self, region: HeadRegion) -> dict[str, QPointF]:
        """Handle positions in *view* space for one region."""
        c, s = math.cos(region.angle), math.sin(region.angle)
        arm = ROTATE_ARM / max(self._zoom, 1e-6)
        local = {
            "e": (region.rx, 0.0),
            "w": (-region.rx, 0.0),
            "n": (0.0, -region.ry),
            "s": (0.0, region.ry),
            "rot": (0.0, -region.ry - arm),
            "move": (0.0, 0.0),
        }
        points: dict[str, QPointF] = {}
        for key, (lx, ly) in local.items():
            gx = region.cx + lx * c - ly * s
            gy = region.cy + lx * s + ly * c
            points[key] = self._to_view(gx, gy)
        return points

    def _hit_test(self, view_point: QPointF):
        """Return ``(index, handle)`` under a view point, or ``(-1, "")``."""
        order = ("rot", "e", "w", "n", "s")
        if 0 <= self._selected < len(self._regions):
            points = self._handle_points(self._regions[self._selected])
            for key in order:
                point = points[key]
                if math.hypot(point.x() - view_point.x(), point.y() - view_point.y()) <= HANDLE_HIT_RADIUS:
                    return self._selected, key
        image_point = self._to_image(view_point)
        for index in range(len(self._regions) - 1, -1, -1):
            region = self._regions[index]
            if region.contains(image_point.x(), image_point.y(), tol=0.0):
                return index, "move"
        return -1, ""

    def _local_point(self, region: HeadRegion, image_point: QPointF) -> tuple[float, float]:
        c, s = math.cos(-region.angle), math.sin(-region.angle)
        dx = image_point.x() - region.cx
        dy = image_point.y() - region.cy
        return (dx * c - dy * s, dx * s + dy * c)

    # ------------------------------------------------------------------ events
    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if not self.has_image:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        self.zoom_by(factor, anchor=event.position())
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if not self.has_image:
            return
        position = event.position()
        button = event.button()

        if button == Qt.MouseButton.MiddleButton or self._space_down:
            self._drag = {"mode": "pan", "origin": position, "offset": QPointF(self._offset)}
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if button == Qt.MouseButton.RightButton:
            self._show_context_menu(event)
            return

        if button != Qt.MouseButton.LeftButton:
            return

        index, handle = self._hit_test(position)
        if index < 0:
            if self._compare == "split" and abs(position.x() - self._split_x()) <= 10:
                self._drag = {"mode": "split"}
                return
            self._drag = {"mode": "pan", "origin": position, "offset": QPointF(self._offset)}
            if self._selected != -1 and self._show_overlay:
                self._selected = -1
                self.selection_changed.emit(-1)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if index != self._selected:
            self._selected = index
            self.selection_changed.emit(index)
            self.update()

        region = self._regions[index]
        self._drag = {
            "mode": handle if handle != "move" else "move",
            "index": index,
            "origin": position,
            "region": region.copy(),
        }
        self.setCursor(_HANDLE_CURSORS.get(handle, Qt.CursorShape.SizeAllCursor))

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt naming
        position = event.position()
        image_point = self._to_image(position)
        self.cursor_position.emit(image_point.x(), image_point.y())

        if self._drag is None:
            self._update_hover_cursor(position)
            return

        mode = self._drag["mode"]
        if mode == "pan":
            delta = position - self._drag["origin"]
            self._offset = self._drag["offset"] + delta
            self.update()
            return
        if mode == "split":
            self._split = min(max((position.x() - self._offset.x()) / max(1.0, self._image_size[0] * self._zoom), 0.0), 1.0)
            self.update()
            return

        index = self._drag["index"]
        original: HeadRegion = self._drag["region"]
        changes = self._drag_changes(mode, original, image_point, event.modifiers())
        if changes is None:
            return
        region = original.copy(**changes)
        if mode == "move":
            width, height = self._image_size
            region.cx = min(max(region.cx, 0.0), float(width))
            region.cy = min(max(region.cy, 0.0), float(height))
        else:
            region.rx = max(region.rx, 6.0)
            region.ry = max(region.ry, 6.0)
        self._regions[index] = region
        self.region_changed.emit(index, region.as_dict())
        self.update()

    def _drag_changes(self, mode: str, original: HeadRegion, point: QPointF, modifiers) -> dict | None:
        if mode == "move":
            dx = point.x() - original.cx
            dy = point.y() - original.cy
            return {"cx": original.cx + dx, "cy": original.cy + dy}
        if mode == "rot":
            angle = math.atan2(point.y() - original.cy, point.x() - original.cx) + math.pi / 2
            while angle <= -math.pi / 2:
                angle += math.pi
            while angle > math.pi / 2:
                angle -= math.pi
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                step = math.radians(5)
                angle = round(angle / step) * step
            return {"angle": angle}
        lx, ly = self._local_point(original, point)
        keep_ratio = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if mode in ("e", "w"):
            if mode == "e":
                rx = max(lx, 6.0)
            else:
                rx = max(-lx, 6.0)
            ry = original.ry * (rx / original.rx) if keep_ratio and original.rx else original.ry
            return {"rx": rx, "ry": max(ry, 6.0)}
        if mode in ("n", "s"):
            ry = max(-ly, 6.0) if mode == "n" else max(ly, 6.0)
            rx = original.rx * (ry / original.ry) if keep_ratio and original.ry else original.rx
            return {"ry": ry, "rx": max(rx, 6.0)}
        return None

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self._drag is not None:
            mode = self._drag["mode"]
            index = self._drag.get("index", -1)
            if mode not in ("pan", "split") and 0 <= index < len(self._regions):
                self.region_committed.emit(index, self._regions[index].as_dict())
        self._drag = None
        self._update_hover_cursor(event.position())

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if not self.has_image:
            return
        index, _handle = self._hit_test(event.position())
        if index < 0 and event.button() == Qt.MouseButton.LeftButton:
            point = self._to_image(event.position())
            self.region_requested.emit(point.x(), point.y())

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self.unsetCursor()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self._fit_pending or not self.has_image:
            self.fit_to_window()
        super().resizeEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.key() == Qt.Key.Key_Space:
            self._space_down = True
            if not self._drag:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.key() == Qt.Key.Key_Space:
            self._space_down = False
            self.unsetCursor()
        super().keyReleaseEvent(event)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt naming
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.file_dropped.emit(url.toLocalFile())
                event.acceptProposedAction()
                return

    def _update_hover_cursor(self, position: QPointF) -> None:
        if self._space_down:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return
        index, handle = self._hit_test(position)
        if handle:
            self.setCursor(_HANDLE_CURSORS.get(handle, Qt.CursorShape.SizeAllCursor))
            self._hover_handle = handle
        else:
            self.unsetCursor()
            self._hover_handle = ""

    def _show_context_menu(self, event) -> None:
        palette = self._palette
        menu = QMenu(self)
        index, _handle = self._hit_test(event.position())
        point = self._to_image(event.position())

        add = QAction(t("action.add_head"), menu)
        add.triggered.connect(lambda: self.region_requested.emit(point.x(), point.y()))
        menu.addAction(add)

        if index >= 0:
            delete = QAction(t("action.remove_head"), menu)
            delete.triggered.connect(lambda: self.delete_requested.emit(index))
            menu.addAction(delete)
        menu.addSeparator()
        fit = QAction(t("action.zoom_fit"), menu)
        fit.triggered.connect(self.fit_to_window)
        menu.addAction(fit)
        actual = QAction(t("action.zoom_reset"), menu)
        actual.triggered.connect(self.reset_zoom)
        menu.addAction(actual)
        menu.exec(event.globalPosition().toPoint())

    # ------------------------------------------------------------------ paint
    def _split_x(self) -> float:
        width = self._image_size[0] * self._zoom
        return self._offset.x() + width * self._split

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor(self._palette.canvas))

        if self._source is None:
            self._paint_empty_state(painter)
            painter.end()
            return

        rect = self._image_rect()
        self._paint_checkerboard(painter, rect)

        if self._compare == "original":
            painter.drawPixmap(rect, self._source, QRectF(self._source.rect()))
        elif self._compare == "split":
            painter.drawPixmap(rect, self._result or self._source, QRectF((self._result or self._source).rect()))
            split_x = self._split_x()
            painter.save()
            painter.setClipRect(QRectF(rect.left(), rect.top(), split_x - rect.left(), rect.height()))
            painter.drawPixmap(rect, self._source, QRectF(self._source.rect()))
            painter.restore()
        else:
            painter.drawPixmap(rect, self._result or self._source, QRectF((self._result or self._source).rect()))

        if self._show_overlay:
            for index, region in enumerate(self._regions):
                self._paint_region(painter, index, region)

        if self._compare == "split":
            self._paint_split_handle(painter)
        painter.end()

    def _paint_checkerboard(self, painter: QPainter, rect: QRectF) -> None:
        light = QColor(self._palette.checker_light)
        dark = QColor(self._palette.checker_dark)
        painter.fillRect(rect, light)
        cell = 12.0
        painter.save()
        painter.setClipRect(rect)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dark)
        columns = int(rect.width() / cell) + 2
        rows = int(rect.height() / cell) + 2
        for row in range(rows):
            for column in range(columns):
                if (row + column) % 2:
                    continue
                painter.drawRect(
                    QRectF(
                        rect.left() + column * cell,
                        rect.top() + row * cell,
                        cell,
                        cell,
                    )
                )
        painter.restore()

    def _paint_region(self, painter: QPainter, index: int, region: HeadRegion) -> None:
        selected = index == self._selected
        base = QColor(ColorDot.COLORS[index % len(ColorDot.COLORS)])

        painter.save()
        painter.translate(self._to_view(region.cx, region.cy))
        painter.rotate(math.degrees(region.angle))
        ellipse = QRectF(-region.rx * self._zoom, -region.ry * self._zoom, 2 * region.rx * self._zoom, 2 * region.ry * self._zoom)

        fill = QColor(base)
        fill.setAlpha(38 if selected else 18)
        painter.setBrush(fill)
        pen = QPen(base, 2.4 if selected else 1.6)
        if not selected:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawEllipse(ellipse)
        painter.restore()

        # centre crosshair
        centre = self._to_view(region.cx, region.cy)
        painter.save()
        painter.setPen(QPen(base, 1.4))
        painter.drawLine(QPointF(centre.x() - 5, centre.y()), QPointF(centre.x() + 5, centre.y()))
        painter.drawLine(QPointF(centre.x(), centre.y() - 5), QPointF(centre.x(), centre.y() + 5))
        painter.restore()

        self._paint_label(painter, index, region, selected)
        if selected:
            self._paint_handles(painter, region)

    def _paint_label(self, painter: QPainter, index: int, region: HeadRegion, selected: bool) -> None:
        text = f"{region.name or t('region.title', index=index + 1)}  {region.scale:.2f}×"
        font = QFont(self.font())
        font.setPointSizeF(max(8.0, font.pointSizeF() - 1))
        painter.save()
        painter.setFont(font)
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(text) + 16
        height = metrics.height() + 6
        anchor = self._to_view(region.cx, region.cy - region.ry)
        box = QRectF(anchor.x() - width / 2, anchor.y() - height - 8, width, height)
        colour = QColor(ColorDot.COLORS[index % len(ColorDot.COLORS)])
        painter.setBrush(QColor(15, 18, 26, 220) if self._palette.name == "dark" else QColor(255, 255, 255, 235))
        painter.setPen(QPen(colour if selected else QColor(colour.red(), colour.green(), colour.blue(), 150), 1.0))
        painter.drawRoundedRect(box, 7, 7)
        painter.setPen(QColor(self._palette.text))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def _paint_handles(self, painter: QPainter, region: HeadRegion) -> None:
        points = self._handle_points(region)
        painter.save()
        painter.setPen(QPen(QColor("#ffffff"), 1.6))
        painter.setBrush(QColor(self._palette.accent))
        for key in ("n", "s", "e", "w"):
            point = points[key]
            painter.drawEllipse(point, HANDLE_RADIUS, HANDLE_RADIUS)
        # rotation arm + knob
        painter.setPen(QPen(QColor(self._palette.accent), 1.4, Qt.PenStyle.DotLine))
        painter.drawLine(points["n"], points["rot"])
        painter.setPen(QPen(QColor("#ffffff"), 1.6))
        painter.setBrush(QColor(self._palette.accent_hover))
        painter.drawEllipse(points["rot"], HANDLE_RADIUS, HANDLE_RADIUS)
        painter.restore()

    def _paint_split_handle(self, painter: QPainter) -> None:
        rect = self._image_rect()
        x = self._split_x()
        painter.save()
        painter.setPen(QPen(QColor(self._palette.accent), 2.0))
        painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        knob = QPainterPath()
        knob.addRoundedRect(QRectF(x - 7, rect.center().y() - 22, 14, 44), 7, 7)
        painter.setPen(QPen(QColor("#ffffff"), 1.4))
        painter.setBrush(QColor(self._palette.accent))
        painter.drawPath(knob)
        painter.setPen(QPen(QColor("#ffffff"), 1.4))
        painter.drawLine(QPointF(x - 2.5, rect.center().y() - 6), QPointF(x - 2.5, rect.center().y() + 6))
        painter.drawLine(QPointF(x + 2.5, rect.center().y() - 6), QPointF(x + 2.5, rect.center().y() + 6))
        painter.restore()

    def _paint_empty_state(self, painter: QPainter) -> None:
        palette = self._palette
        painter.save()
        centre = self.rect().center()
        painter.setPen(QPen(QColor(palette.border_strong), 2.0, Qt.PenStyle.DashLine))
        box = QRectF(centre.x() - 240, centre.y() - 120, 480, 240)
        painter.setBrush(QColor(255, 255, 255, 8))
        painter.drawRoundedRect(box, 18, 18)

        pixmap = icons.pixmap("open", palette.text_faint, 54)
        painter.drawPixmap(int(centre.x() - 27), int(centre.y() - 74), pixmap)
        font = QFont(self.font())
        font.setPointSizeF(font.pointSizeF() + 3)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(palette.text_muted))
        painter.drawText(
            QRectF(box.left(), centre.y() - 8, box.width(), 30),
            Qt.AlignmentFlag.AlignHCenter,
            t("empty.title"),
        )
        font.setPointSizeF(font.pointSizeF() - 3)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(palette.text_faint))
        painter.drawText(
            QRectF(box.left() + 20, centre.y() + 24, box.width() - 40, 70),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
            t("empty.body"),
        )
        painter.restore()


__all__ = ["ImageCanvas", "numpy_to_pixmap"]
