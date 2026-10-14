"""Reusable widgets: cards, sliders, segmented controls, region rows."""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from headsize.ui import icons
from headsize.ui.theme import Palette, palette as current_palette


def _p() -> Palette:
    return current_palette(_active_theme_name())


_THEME_NAME = {"value": "dark"}


def _active_theme_name() -> str:
    return _THEME_NAME["value"]


def set_active_theme(name: str) -> None:
    """Remember which palette the widgets should tint their custom painting with."""
    _THEME_NAME["value"] = name if name in ("dark", "light") else "dark"


class Card(QFrame):
    """A rounded panel with a small uppercase title."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 14)
        self._layout.setSpacing(10)

        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        self.header.addWidget(self.title_label)
        self.header.addStretch(1)
        self._layout.addLayout(self.header)

        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        self._layout.addLayout(self.body)

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)

    def add_header_widget(self, widget: QWidget) -> None:
        self.header.addWidget(widget)

    def add(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget

    def add_layout(self, layout) -> None:
        self.body.addLayout(layout)

    def add_row(self, *widgets: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        for widget in widgets:
            row.addWidget(widget)
        self.body.addLayout(row)
        return row

    def add_divider(self) -> None:
        line = QFrame()
        line.setObjectName("CardHeaderLine")
        line.setFixedHeight(1)
        self.body.addWidget(line)


class SliderRow(QWidget):
    """A labelled slider with a live value readout.

    Double-clicking the label resets the slider to its default value.
    """

    value_changed = pyqtSignal(float)
    editing_finished = pyqtSignal(float)

    def __init__(
        self,
        label: str,
        minimum: float,
        maximum: float,
        value: float,
        *,
        decimals: int = 2,
        suffix: str = "",
        formatter: Callable[[float], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._minimum = float(minimum)
        self._maximum = float(maximum)
        self._default = float(value)
        self._decimals = decimals
        self._suffix = suffix
        self._formatter = formatter
        self._scale = 10**decimals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.label = QLabel(label)
        self.label.setObjectName("Muted")
        self.value_label = QLabel()
        self.value_label.setObjectName("ValueSmall")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.label)
        header.addStretch(1)
        header.addWidget(self.value_label)
        layout.addLayout(header)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(self._minimum * self._scale), int(self._maximum * self._scale))
        self.slider.setValue(int(round(self._default * self._scale)))
        self.slider.setSingleStep(max(1, int(self._scale / 10)))
        self.slider.setPageStep(max(1, int(self._scale)))
        self.slider.valueChanged.connect(self._on_slider)
        self.slider.sliderReleased.connect(self._on_released)
        layout.addWidget(self.slider)

        self._update_label(self._default)

    # ------------------------------------------------------------------ value
    def value(self) -> float:
        return self.slider.value() / self._scale

    def set_value(self, value: float, *, emit: bool = False) -> None:
        clamped = min(max(float(value), self._minimum), self._maximum)
        blocked = self.slider.blockSignals(not emit)
        self.slider.setValue(int(round(clamped * self._scale)))
        self.slider.blockSignals(blocked)
        self._update_label(clamped)

    def set_default(self, value: float) -> None:
        self._default = float(value)

    def set_range(self, minimum: float, maximum: float) -> None:
        self._minimum, self._maximum = float(minimum), float(maximum)
        self.slider.setRange(int(minimum * self._scale), int(maximum * self._scale))

    def set_suffix(self, suffix: str) -> None:
        self._suffix = suffix
        self._update_label(self.value())

    def set_label(self, text: str) -> None:
        self.label.setText(text)

    def reset(self, *, emit: bool = True) -> None:
        self.set_value(self._default)
        if emit:
            self.value_changed.emit(self.value())
            self.editing_finished.emit(self.value())

    # ------------------------------------------------------------------ events
    def _on_slider(self, raw: int) -> None:
        value = raw / self._scale
        self._update_label(value)
        self.value_changed.emit(value)

    def _on_released(self) -> None:
        self.editing_finished.emit(self.value())

    def _update_label(self, value: float) -> None:
        if self._formatter is not None:
            text = self._formatter(value)
        else:
            text = f"{value:.{self._decimals}f}{self._suffix}"
        self.value_label.setText(text)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self.reset()
        super().mouseDoubleClickEvent(event)


class SegmentedControl(QWidget):
    """A row of exclusive chip buttons."""

    changed = pyqtSignal(str)

    def __init__(
        self,
        options: Sequence[tuple[str, str]],
        current: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for key, label in options:
            button = QPushButton(label)
            button.setObjectName("Chip")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked, k=key: self.set_current(k, emit=True))
            layout.addWidget(button)
            self._buttons[key] = button
        layout.addStretch(1)
        self.set_current(current or (options[0][0] if options else ""))

    def set_current(self, key: str, *, emit: bool = False) -> None:
        for name, button in self._buttons.items():
            button.blockSignals(True)
            button.setChecked(name == key)
            button.blockSignals(False)
        self._current = key
        if emit:
            self.changed.emit(key)

    def current(self) -> str:
        return getattr(self, "_current", "")

    def set_labels(self, options: Sequence[tuple[str, str]]) -> None:
        for key, label in options:
            if key in self._buttons:
                self._buttons[key].setText(label)


class PresetGrid(QWidget):
    """A compact grid of scale presets."""

    chosen = pyqtSignal(float)

    def __init__(self, presets: Iterable[tuple[str, float]], columns: int = 3, parent=None) -> None:
        super().__init__(parent)
        self._buttons: list[tuple[QPushButton, float]] = []
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        for index, (label, value) in enumerate(presets):
            button = QPushButton(label)
            button.setObjectName("Chip")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"{value:.2f}×")
            button.clicked.connect(lambda _c, v=value: self.chosen.emit(v))
            grid.addWidget(button, index // columns, index % columns)
            self._buttons.append((button, value))

    def set_presets(self, presets: Iterable[tuple[str, float]]) -> None:
        for (button, _), (label, value) in zip(self._buttons, presets):
            button.setText(label)
            button.setToolTip(f"{value:.2f}×")

    def highlight(self, scale: float, tolerance: float = 0.005) -> None:
        for button, value in self._buttons:
            button.setChecked(abs(value - scale) <= tolerance)


class ColorDot(QWidget):
    """A small coloured dot used to identify a region."""

    COLORS = ("#6c8cff", "#45d7b0", "#ffc86b", "#ff8fb1", "#9d8bff", "#57c8ff")

    def __init__(self, index: int = 0, size: int = 10, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size + 2, size + 2)
        self.set_color_for(index)

    def set_color_for(self, index: int) -> None:
        self._color = QColor(self.COLORS[index % len(self.COLORS)])
        self.update()

    @property
    def color(self) -> QColor:
        return self._color

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self._color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(1, 1, self._size, self._size)
        painter.end()


class RegionRow(QFrame):
    """One row of the head-region list."""

    select_requested = pyqtSignal(int)
    toggle_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, index: int, name: str, scale: float, enabled: bool, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("RegionRow")
        self.index = index
        self.setProperty("selected", "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 6, 6)
        layout.setSpacing(8)

        self.dot = ColorDot(index)
        layout.addWidget(self.dot)

        self.name_label = QLabel(name)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.name_label)

        self.scale_label = QLabel(f"{scale:.2f}×")
        self.scale_label.setObjectName("Faint")
        layout.addWidget(self.scale_label)

        self.eye = QToolButton()
        self.eye.setCheckable(True)
        self.eye.setChecked(enabled)
        self.eye.setAutoRaise(True)
        self.eye.clicked.connect(lambda: self.toggle_requested.emit(self.index))
        layout.addWidget(self.eye)

        self.delete = QToolButton()
        self.delete.setAutoRaise(True)
        self.delete.clicked.connect(lambda: self.delete_requested.emit(self.index))
        layout.addWidget(self.delete)

        self.refresh_icons()

    def refresh_icons(self, theme: str = "", palette: Palette | None = None) -> None:
        pal = palette or _p()
        self.eye.setIcon(icons.icon("eye" if self.eye.isChecked() else "eye_off", pal.text_muted, 16))
        self.delete.setIcon(icons.icon("trash", pal.text_muted, 16))
        self.dot.set_color_for(self.index)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def update_values(self, name: str, scale: float, enabled: bool) -> None:
        self.name_label.setText(name)
        self.scale_label.setText(f"{scale:.2f}×")
        self.eye.blockSignals(True)
        self.eye.setChecked(enabled)
        self.eye.blockSignals(False)
        self.refresh_icons()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self.select_requested.emit(self.index)
        super().mousePressEvent(event)


class Banner(QFrame):
    """An inline message with an optional action button."""

    action_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Banner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 8, 8)
        layout.setSpacing(8)
        self.icon_label = QLabel()
        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.button = QPushButton()
        self.button.setObjectName("Tiny")
        self.button.clicked.connect(self.action_clicked.emit)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.button)
        self.hide()

    def show_message(self, text: str, *, icon: str = "info", action: str = "") -> None:
        pal = _p()
        color = {
            "info": pal.accent,
            "check": pal.success,
            "alert": pal.warning,
            "download": pal.accent,
        }.get(icon, pal.accent)
        self.icon_label.setPixmap(icons.pixmap(icon, color, 16))
        self.text_label.setText(text)
        self.button.setText(action)
        self.button.setVisible(bool(action))
        self.show()

    def clear(self) -> None:
        self.hide()


class KeyValueRow(QWidget):
    """A muted label next to a value, used for image metadata."""

    def __init__(self, label: str, value: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.key = QLabel(label)
        self.key.setObjectName("Faint")
        self.value = QLabel(value)
        self.value.setObjectName("Muted")
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.key)
        layout.addWidget(self.value)

    def set_value(self, value: str) -> None:
        self.value.setText(value)

    def set_key(self, label: str) -> None:
        self.key.setText(label)


class FlowButtons(QWidget):
    """A wrapping row of small buttons (used for presets and quick actions)."""

    def __init__(self, items: Sequence[tuple[str, str]], parent: QWidget | None = None, columns: int = 3):
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(6)
        self._columns = columns
        for index, (key, label) in enumerate(items):
            button = QPushButton(label)
            button.setObjectName("Chip")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._grid.addWidget(button, index // columns, index % columns)
            self._buttons[key] = button

    def button(self, key: str) -> QPushButton | None:
        return self._buttons.get(key)


def make_tool_button(
    name: str,
    tooltip: str,
    *,
    checkable: bool = False,
    color: str = "",
    size: int = 18,
) -> QToolButton:
    """Create a flat toolbar button with an SVG icon."""
    button = QToolButton()
    button.setIcon(icons.icon(name, color or _p().text_muted, size))
    button.setToolTip(tooltip)
    button.setCheckable(checkable)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def refresh_button_icons(button: QToolButton, name: str, color: str, size: int = 18) -> None:
    button.setIcon(icons.icon(name, color, size))


__all__ = [
    "Banner",
    "Card",
    "ColorDot",
    "FlowButtons",
    "KeyValueRow",
    "PresetGrid",
    "RegionRow",
    "SegmentedControl",
    "SliderRow",
    "make_tool_button",
    "refresh_button_icons",
    "set_active_theme",
]
