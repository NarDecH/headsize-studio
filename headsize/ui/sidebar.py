"""The controls sidebar: image, heads, size, influence zone, view, updates."""

from __future__ import annotations

import math
from typing import Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from headsize.core import presets as preset_module
from headsize.core.types import HeadRegion
from headsize.ui import icons
from headsize.ui.i18n import t
from headsize.ui.theme import Palette
from headsize.ui.widgets import (
    Banner,
    Card,
    KeyValueRow,
    PresetGrid,
    RegionRow,
    SegmentedControl,
    SliderRow,
)


class ControlsPanel(QWidget):
    """All editing controls in one scrollable column."""

    open_requested = pyqtSignal()
    save_requested = pyqtSignal()
    reset_requested = pyqtSignal()

    detect_requested = pyqtSignal()
    add_head_requested = pyqtSignal()
    apply_all_requested = pyqtSignal()
    autofit_requested = pyqtSignal()

    region_selected = pyqtSignal(int)
    region_toggled = pyqtSignal(int)
    region_deleted = pyqtSignal(int)

    scale_changed = pyqtSignal(float, bool)  # value, committed
    feather_changed = pyqtSignal(float, bool)
    zone_changed = pyqtSignal(str, float, bool)  # field ("rx"|"ry"|"angle"), value, committed

    overlay_toggled = pyqtSignal(bool)
    compare_changed = pyqtSignal(str)
    quality_changed = pyqtSignal(str)
    theme_changed = pyqtSignal(str)
    language_changed = pyqtSignal(str)
    metadata_toggled = pyqtSignal(bool)

    update_check_requested = pyqtSignal()
    update_action_requested = pyqtSignal()
    auto_update_toggled = pyqtSignal(bool)
    channel_changed = pyqtSignal(str)

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        # A plain QWidget subclass only paints border/background from the
        # stylesheet when this attribute is set.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._palette = palette
        self._syncing = False
        self._regions: list[HeadRegion] = []
        self._selected = -1
        self._rows: list[RegionRow] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("SidebarScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(scroll)

        container = QWidget()
        container.setObjectName("SidebarInner")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll.setWidget(container)
        self.layout_ = QVBoxLayout(container)
        self.layout_.setContentsMargins(14, 14, 14, 18)
        self.layout_.setSpacing(12)

        self._build_header()
        self._build_image_card()
        self._build_faces_card()
        self._build_size_card()
        self._build_zone_card()
        self._build_view_card()
        self._build_update_card()
        self.layout_.addStretch(1)

    # ------------------------------------------------------------------ header
    def _build_header(self) -> None:
        header = QHBoxLayout()
        header.setSpacing(9)
        self.logo = QLabel()
        self.logo.setPixmap(icons.pixmap("target", self._palette.accent, 26))
        header.addWidget(self.logo)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.title_label = QLabel(t("app.title"))
        self.title_label.setObjectName("Title")
        self.tagline = QLabel(t("app.tagline"))
        self.tagline.setObjectName("Hint")
        self.tagline.setWordWrap(True)
        titles.addWidget(self.title_label)
        titles.addWidget(self.tagline)
        header.addLayout(titles)
        header.addStretch(1)
        self.layout_.addLayout(header)

    # -------------------------------------------------------------- image card
    def _build_image_card(self) -> None:
        self.image_card = Card(t("card.image"))
        self.layout_.addWidget(self.image_card)

        self.file_name = QLabel(t("label.no_file"))
        self.file_name.setObjectName("ValueSmall")
        self.file_name.setWordWrap(True)
        self.image_card.add(self.file_name)

        self.info_size = KeyValueRow(t("label.size_key"), "—")
        self.info_faces = KeyValueRow(t("label.faces_key"), "0")
        self.image_card.add(self.info_size)
        self.image_card.add(self.info_faces)

        self.open_button = QPushButton(t("button.open"))
        self.open_button.setObjectName("Primary")
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_button.clicked.connect(self.open_requested.emit)
        self.image_card.add(self.open_button)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.save_button = QPushButton(t("button.save"))
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.clicked.connect(self.save_requested.emit)
        self.reset_button = QPushButton(t("button.reset"))
        self.reset_button.setObjectName("Ghost")
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.clicked.connect(self.reset_requested.emit)
        row.addWidget(self.save_button)
        row.addWidget(self.reset_button)
        self.image_card.add_layout(row)

        self.hint = QLabel(t("hint.drop"))
        self.hint.setObjectName("Hint")
        self.hint.setWordWrap(True)
        self.image_card.add(self.hint)

        self.save_button.setEnabled(False)
        self.reset_button.setEnabled(False)

    # -------------------------------------------------------------- faces card
    def _build_faces_card(self) -> None:
        self.faces_card = Card(t("card.faces"))
        self.layout_.addWidget(self.faces_card)

        self.faces_badge = QLabel("0")
        self.faces_badge.setObjectName("Badge")
        self.faces_card.add_header_widget(self.faces_badge)

        self.faces_status = QLabel(t("faces.none"))
        self.faces_status.setObjectName("Hint")
        self.faces_status.setWordWrap(True)
        self.faces_card.add(self.faces_status)

        self.region_container = QWidget()
        self.region_layout = QVBoxLayout(self.region_container)
        self.region_layout.setContentsMargins(0, 0, 0, 0)
        self.region_layout.setSpacing(6)
        self.faces_card.add(self.region_container)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.detect_button = QPushButton(t("button.detect"))
        self.detect_button.setIcon(icons.icon("scan", self._palette.text, 16))
        self.detect_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.detect_button.clicked.connect(self.detect_requested.emit)
        self.add_button = QPushButton(t("button.add_manual"))
        self.add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_button.clicked.connect(self.add_head_requested.emit)
        row.addWidget(self.detect_button)
        row.addWidget(self.add_button)
        self.faces_card.add_layout(row)

        self.apply_all_button = QPushButton(t("button.apply_all"))
        self.apply_all_button.setObjectName("Ghost")
        self.apply_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_all_button.clicked.connect(self.apply_all_requested.emit)
        self.faces_card.add(self.apply_all_button)

        self.detect_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.apply_all_button.setEnabled(False)

    # --------------------------------------------------------------- size card
    def _build_size_card(self) -> None:
        self.size_card = Card(t("card.size"))
        self.layout_.addWidget(self.size_card)

        self.scale_label = QLabel(t("scale.value", value=1.0))
        self.scale_label.setObjectName("Value")
        self.size_card.add(self.scale_label)

        self.scale_slider = SliderRow(
            t("scale.smaller") + " ← → " + t("scale.bigger"),
            0.50,
            2.50,
            1.00,
            decimals=2,
            formatter=lambda v: f"{v:.2f}×",
        )
        self.scale_slider.value_changed.connect(lambda v: self._on_slider("scale", v, False))
        self.scale_slider.editing_finished.connect(lambda v: self._on_slider("scale", v, True))
        self.size_card.add(self.scale_slider)

        self.preset_grid = PresetGrid([(p.hint, p.scale) for p in preset_module.PRESETS])
        self.preset_grid.chosen.connect(self._on_preset)
        self.size_card.add(self.preset_grid)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.scale_input = QDoubleSpinBox()
        self.scale_input.setRange(0.30, 3.00)
        self.scale_input.setSingleStep(0.01)
        self.scale_input.setDecimals(2)
        self.scale_input.setSuffix("×")
        self.scale_input.setValue(1.00)
        self.scale_input.valueChanged.connect(self._on_scale_input)
        self.scale_reset = QPushButton(t("scale.reset"))
        self.scale_reset.setObjectName("Ghost")
        self.scale_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scale_reset.clicked.connect(lambda: self._on_preset(1.0))
        row.addWidget(self.scale_input, 1)
        row.addWidget(self.scale_reset)
        self.size_card.add_layout(row)

        self.scale_hint = QLabel(t("scale.hint"))
        self.scale_hint.setObjectName("Hint")
        self.scale_hint.setWordWrap(True)
        self.size_card.add(self.scale_hint)

        self._set_size_enabled(False)

    # --------------------------------------------------------------- zone card
    def _build_zone_card(self) -> None:
        self.zone_card = Card(t("card.region"))
        self.layout_.addWidget(self.zone_card)

        self.zone_width = SliderRow(t("region.width"), 10.0, 1200.0, 200.0, decimals=0, suffix=" px")
        self.zone_height = SliderRow(t("region.height"), 10.0, 1200.0, 200.0, decimals=0, suffix=" px")
        self.zone_tilt = SliderRow(t("region.rotation"), -45.0, 45.0, 0.0, decimals=0, suffix="°")
        self.feather = SliderRow(
            t("region.feather"),
            0.0,
            0.90,
            0.55,
            decimals=2,
            formatter=lambda v: f"{v * 100:.0f}%",
        )
        for slider, field in (
            (self.zone_width, "rx"),
            (self.zone_height, "ry"),
            (self.zone_tilt, "angle"),
        ):
            slider.value_changed.connect(lambda v, f=field: self._on_zone(f, v, False))
            slider.editing_finished.connect(lambda v, f=field: self._on_zone(f, v, True))
        self.feather.value_changed.connect(lambda v: self._on_slider("feather", v, False))
        self.feather.editing_finished.connect(lambda v: self._on_slider("feather", v, True))

        self.zone_card.add(self.zone_width)
        self.zone_card.add(self.zone_height)
        self.zone_card.add(self.zone_tilt)
        self.zone_card.add(self.feather)

        self.overlay_check = QCheckBox(t("region.show"))
        self.overlay_check.setChecked(True)
        self.overlay_check.toggled.connect(self.overlay_toggled.emit)
        self.zone_card.add(self.overlay_check)

        self.autofit_button = QPushButton(t("region.autofit"))
        self.autofit_button.setObjectName("Ghost")
        self.autofit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.autofit_button.clicked.connect(self.autofit_requested.emit)
        self.zone_card.add(self.autofit_button)

        self._set_zone_enabled(False)

    # --------------------------------------------------------------- view card
    def _build_view_card(self) -> None:
        self.view_card = Card(t("card.view"))
        self.layout_.addWidget(self.view_card)

        self.quality_label = QLabel(t("view.quality"))
        self.quality_label.setObjectName("Muted")
        self.view_card.add(self.quality_label)
        self.quality_control = SegmentedControl(
            [
                ("fast", t("view.quality.fast")),
                ("balanced", t("view.quality.balanced")),
                ("high", t("view.quality.high")),
            ],
            "high",
        )
        self.quality_control.changed.connect(self.quality_changed.emit)
        self.view_card.add(self.quality_control)

        self.compare_label = QLabel(t("view.compare"))
        self.compare_label.setObjectName("Muted")
        self.view_card.add(self.compare_label)
        self.compare_control = SegmentedControl(
            [
                ("result", t("view.type.result")),
                ("original", t("view.type.original")),
                ("split", t("view.type.split")),
            ],
            "result",
        )
        self.compare_control.changed.connect(self.compare_changed.emit)
        self.view_card.add(self.compare_control)

        self.theme_label = QLabel(t("view.theme"))
        self.theme_label.setObjectName("Muted")
        self.view_card.add(self.theme_label)
        self.theme_control = SegmentedControl([("dark", "Dark"), ("light", "Light")], "dark")
        self.theme_control.changed.connect(self.theme_changed.emit)
        self.view_card.add(self.theme_control)

        self.language_label = QLabel(t("view.language"))
        self.language_label.setObjectName("Muted")
        self.view_card.add(self.language_label)
        self.language_control = SegmentedControl([("th", "ไทย"), ("en", "English")], "th")
        self.language_control.changed.connect(self.language_changed.emit)
        self.view_card.add(self.language_control)

        self.metadata_check = QCheckBox(t("view.keep_metadata"))
        self.metadata_check.setChecked(True)
        self.metadata_check.toggled.connect(self.metadata_toggled.emit)
        self.view_card.add(self.metadata_check)

    # ------------------------------------------------------------- update card
    def _build_update_card(self) -> None:
        self.update_card = Card(t("card.updates"))
        self.layout_.addWidget(self.update_card)

        self.version_badge = QLabel(t("app.version", version="0.0.0"))
        self.version_badge.setObjectName("Badge")
        self.update_card.add_header_widget(self.version_badge)

        self.update_banner = Banner()
        self.update_banner.action_clicked.connect(self.update_action_requested.emit)
        self.update_card.add(self.update_banner)

        self.auto_update_check = QCheckBox(t("update.auto"))
        self.auto_update_check.setChecked(True)
        self.auto_update_check.toggled.connect(self.auto_update_toggled.emit)
        self.update_card.add(self.auto_update_check)

        self.channel_label = QLabel(t("update.channel"))
        self.channel_label.setObjectName("Muted")
        self.update_card.add(self.channel_label)
        self.channel_control = SegmentedControl(
            [("stable", t("update.channel.stable")), ("beta", t("update.channel.beta"))],
            "stable",
        )
        self.channel_control.changed.connect(self.channel_changed.emit)
        self.update_card.add(self.channel_control)

        self.update_button = QPushButton(t("update.check"))
        self.update_button.setIcon(icons.icon("refresh", self._palette.text, 16))
        self.update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button.clicked.connect(self.update_check_requested.emit)
        self.update_card.add(self.update_button)

        self.repo_row = KeyValueRow(t("update.repo"), "—")
        self.update_card.add(self.repo_row)

    # ----------------------------------------------------------------- state
    def set_image_info(
        self, name: str, width: int, height: int, *, has_image: bool, face_count: int
    ) -> None:
        self._syncing = True
        self.file_name.setText(name if has_image else t("label.no_file"))
        self.info_size.set_value(
            t("label.size", width=width, height=height) if has_image else "—"
        )
        self.info_faces.set_value(str(face_count))
        self.save_button.setEnabled(has_image)
        self.reset_button.setEnabled(has_image)
        self.detect_button.setEnabled(has_image)
        self.add_button.setEnabled(has_image)
        self.zone_width.set_range(10.0, max(60.0, width * 0.8))
        self.zone_height.set_range(10.0, max(60.0, height * 0.8))
        self._syncing = False

    def set_regions(self, regions: Sequence[HeadRegion], selected: int) -> None:
        self._regions = list(regions)
        self._selected = selected
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows = []
        for index, region in enumerate(self._regions):
            row = RegionRow(
                index,
                region.name or t("region.title", index=index + 1),
                region.scale,
                region.enabled,
            )
            row.select_requested.connect(self.region_selected.emit)
            row.toggle_requested.connect(self.region_toggled.emit)
            row.delete_requested.connect(self.region_deleted.emit)
            row.set_selected(index == selected)
            self.region_layout.addWidget(row)
            self._rows.append(row)

        count = len(self._regions)
        self.faces_badge.setText(str(count))
        self.faces_status.setVisible(count == 0)
        self.faces_status.setText(t("faces.none"))
        self.apply_all_button.setEnabled(count > 1)
        self._set_size_enabled(count > 0)
        self._set_zone_enabled(count > 0)
        self._refresh_selected_values()

    def set_faces_message(self, message: str) -> None:
        self.faces_status.setText(message)
        self.faces_status.setVisible(True)

    def set_scale(self, scale: float, *, enabled: bool = True) -> None:
        self._syncing = True
        self.scale_slider.set_value(scale)
        self.scale_input.setValue(scale)
        self.scale_label.setText(t("scale.value", value=scale))
        self.preset_grid.highlight(scale)
        self._syncing = False

    def set_zone(self, region: HeadRegion | None) -> None:
        self._syncing = True
        if region is not None:
            self.zone_width.set_value(region.rx)
            self.zone_height.set_value(region.ry)
            self.zone_tilt.set_value(math.degrees(region.angle))
            self.feather.set_value(region.feather)
        self._syncing = False

    def set_update_status(self, message: str, *, icon: str = "info", action: str = "") -> None:
        self.update_banner.show_message(message, icon=icon, action=action)

    def clear_update_status(self) -> None:
        self.update_banner.clear()

    def set_version(self, version: str) -> None:
        self.version_badge.setText(t("app.version", version=version))

    def set_repo(self, slug: str) -> None:
        self.repo_row.set_value(slug or "—")

    def set_busy(self, busy: bool, *, message: str = "") -> None:
        self.detect_button.setEnabled(not busy)
        self.open_button.setEnabled(not busy)
        if message:
            self.faces_status.setText(message)
            self.faces_status.setVisible(True)

    def set_preferences(
        self,
        *,
        theme: str,
        language: str,
        quality: str,
        channel: str,
        auto_update: bool,
        keep_metadata: bool,
        overlay: bool,
    ) -> None:
        self._syncing = True
        self.theme_control.set_current(theme)
        self.language_control.set_current(language)
        self.quality_control.set_current(quality)
        self.channel_control.set_current(channel)
        self.auto_update_check.setChecked(auto_update)
        self.metadata_check.setChecked(keep_metadata)
        self.overlay_check.setChecked(overlay)
        self._syncing = False

    # ------------------------------------------------------------- internals
    def _refresh_selected_values(self) -> None:
        region = self._regions[self._selected] if 0 <= self._selected < len(self._regions) else None
        if region is not None:
            self.set_scale(region.scale)
            self.set_zone(region)

    def _on_slider(self, field: str, value: float, committed: bool) -> None:
        if self._syncing:
            return
        if field == "scale":
            self._syncing = True
            self.scale_label.setText(t("scale.value", value=value))
            self.scale_input.setValue(value)
            self.preset_grid.highlight(value)
            self._syncing = False
            self.scale_changed.emit(value, committed)
        elif field == "feather":
            self.feather_changed.emit(value, committed)

    def _on_zone(self, field: str, value: float, committed: bool) -> None:
        if self._syncing:
            return
        if field == "angle":
            value = math.radians(value)
        self.zone_changed.emit(field, value, committed)

    def _on_preset(self, scale: float) -> None:
        self._syncing = True
        self.scale_slider.set_value(scale)
        self.scale_input.setValue(scale)
        self.scale_label.setText(t("scale.value", value=scale))
        self.preset_grid.highlight(scale)
        self._syncing = False
        self.scale_changed.emit(scale, True)

    def _on_scale_input(self, value: float) -> None:
        if self._syncing:
            return
        self._syncing = True
        self.scale_slider.set_value(value)
        self.scale_label.setText(t("scale.value", value=value))
        self.preset_grid.highlight(value)
        self._syncing = False
        self.scale_changed.emit(value, True)

    def _set_size_enabled(self, enabled: bool) -> None:
        for widget in (
            self.scale_slider,
            self.scale_input,
            self.scale_reset,
            self.preset_grid,
            self.scale_label,
        ):
            widget.setEnabled(enabled)

    def _set_zone_enabled(self, enabled: bool) -> None:
        for widget in (
            self.zone_width,
            self.zone_height,
            self.zone_tilt,
            self.feather,
            self.autofit_button,
        ):
            widget.setEnabled(enabled)

    # ---------------------------------------------------------- retranslation
    def retranslate(self) -> None:
        self.title_label.setText(t("app.title"))
        self.tagline.setText(t("app.tagline"))
        self.image_card.set_title(t("card.image"))
        self.faces_card.set_title(t("card.faces"))
        self.size_card.set_title(t("card.size"))
        self.zone_card.set_title(t("card.region"))
        self.view_card.set_title(t("card.view"))
        self.update_card.set_title(t("card.updates"))
        self.open_button.setText(t("button.open"))
        self.save_button.setText(t("button.save"))
        self.reset_button.setText(t("button.reset"))
        self.hint.setText(t("hint.drop"))
        self.detect_button.setText(t("button.detect"))
        self.info_size.set_key(t("label.size_key"))
        self.info_faces.set_key(t("label.faces_key"))
        self.add_button.setText(t("button.add_manual"))
        self.apply_all_button.setText(t("button.apply_all"))
        self.scale_reset.setText(t("scale.reset"))
        self.scale_hint.setText(t("scale.hint"))
        self.zone_width.set_label(t("region.width"))
        self.zone_height.set_label(t("region.height"))
        self.zone_tilt.set_label(t("region.rotation"))
        self.feather.set_label(t("region.feather"))
        self.overlay_check.setText(t("region.show"))
        self.autofit_button.setText(t("region.autofit"))
        self.quality_label.setText(t("view.quality"))
        self.quality_control.set_labels(
            [
                ("fast", t("view.quality.fast")),
                ("balanced", t("view.quality.balanced")),
                ("high", t("view.quality.high")),
            ]
        )
        self.compare_label.setText(t("view.compare"))
        self.compare_control.set_labels(
            [
                ("result", t("view.type.result")),
                ("original", t("view.type.original")),
                ("split", t("view.type.split")),
            ]
        )
        self.theme_label.setText(t("view.theme"))
        self.language_label.setText(t("view.language"))
        self.metadata_check.setText(t("view.keep_metadata"))
        self.auto_update_check.setText(t("update.auto"))
        self.channel_label.setText(t("update.channel"))
        self.channel_control.set_labels(
            [("stable", t("update.channel.stable")), ("beta", t("update.channel.beta"))]
        )
        self.update_button.setText(t("update.check"))
        self.repo_row.set_key(t("update.repo"))
        self.set_regions(self._regions, self._selected)


__all__ = ["ControlsPanel"]
