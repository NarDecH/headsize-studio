"""The main window: menus, toolbar, sidebar, canvas, status bar and updates."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Sequence

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QToolBar,
    QWidget,
)

from headsize.core.config import AppConfig
from headsize.core.detector import FaceDetector, ModelUnavailableError, model_is_available
from headsize.core.document import Document
from headsize.core.io import open_filter, save_filter, save_image
from headsize.core.types import HeadRegion
from headsize.ui import icons
from headsize.ui.canvas import ImageCanvas
from headsize.ui.dialogs import AboutDialog, SettingsDialog, ShortcutsDialog, UpdateDialog
from headsize.ui.i18n import available_languages, set_language, t
from headsize.ui.sidebar import ControlsPanel
from headsize.ui.theme import apply_theme, palette as get_palette
from headsize.ui.widgets import set_active_theme
from headsize.ui.workers import FunctionWorker, WorkerPool
from headsize.update.repo import release_page, repo_is_configured, resolve_repo
from headsize.update.selfupdate import cleanup_leftovers, supports_self_update
from headsize.update.updater import DownloadedUpdate, UpdateCheck, Updater, cleanup_workspace
from headsize.version import APP_NAME, __version__

DOCS_URL = "https://github.com/{slug}/blob/main/docs/readme.md"

COMPARE_CYCLE = ("result", "split", "original")


class MainWindow(QMainWindow):
    """Everything the user sees."""

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.doc = Document()
        self.workers = WorkerPool()
        self.detector: FaceDetector | None = None

        self._interaction: tuple[str, list[HeadRegion]] | None = None
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(24)
        self._render_timer.timeout.connect(self._render_now)
        self._last_save_path: Path | None = None
        self._pending_update: Updater | None = None
        self._pending_check: UpdateCheck | None = None
        self._downloaded: DownloadedUpdate | None = None
        self._installing = False

        self.setWindowTitle(t("app.title"))
        self.setWindowIcon(icons.icon("target", get_palette(config.theme).accent, 64))
        self.resize(1280, 840)
        self.setMinimumSize(920, 620)
        self.setAcceptDrops(True)

        self._build_ui()
        self._restore_geometry()
        self._apply_preferences()
        self._refresh_all()

        cleanup_leftovers()
        cleanup_workspace()

        if config.check_updates_on_start:
            QTimer.singleShot(2000, lambda: self.check_updates(silent=True))

    # ------------------------------------------------------------------- build
    def _build_ui(self) -> None:
        self.palette_tokens = get_palette(self.config.theme)
        set_active_theme(self.config.theme)
        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_central()
        self._create_status_bar()

    def _create_central(self) -> None:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.panel = ControlsPanel(self.palette_tokens)
        self.panel.setMinimumWidth(300)
        self.panel.setMaximumWidth(460)
        self._connect_panel()

        self.canvas = ImageCanvas(self.palette_tokens)
        self._connect_canvas()

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.panel)
        self.splitter.addWidget(self.canvas)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        sizes = self._splitter_sizes()
        self.splitter.setSizes(sizes)
        layout.addWidget(self.splitter)
        self.setCentralWidget(container)

    def _connect_canvas(self) -> None:
        self.canvas.region_changed.connect(self._on_region_changed)
        self.canvas.region_committed.connect(self._on_region_committed)
        self.canvas.selection_changed.connect(self._on_selection_changed)
        self.canvas.region_requested.connect(self._on_region_requested)
        self.canvas.delete_requested.connect(self._on_region_delete)
        self.canvas.zoom_changed.connect(lambda _z: self._update_status())
        self.canvas.cursor_position.connect(self._on_cursor_position)
        self.canvas.file_dropped.connect(self.open_path)

    def _connect_panel(self) -> None:
        panel = self.panel
        panel.open_requested.connect(self.choose_and_open)
        panel.save_requested.connect(lambda: self.save_image(force_as=True))
        panel.reset_requested.connect(self.reset_edits)
        panel.detect_requested.connect(self.detect_faces)
        panel.add_head_requested.connect(self.add_head_centred)
        panel.apply_all_requested.connect(self.apply_scale_to_all)
        panel.autofit_requested.connect(self.refit_zone)
        panel.region_selected.connect(self._on_region_selected)
        panel.region_toggled.connect(self._on_region_toggle)
        panel.region_deleted.connect(self._on_region_delete)
        panel.scale_changed.connect(self._on_scale_changed)
        panel.feather_changed.connect(self._on_feather_changed)
        panel.zone_changed.connect(self._on_zone_changed)
        panel.overlay_toggled.connect(self._on_overlay_toggled)
        panel.compare_changed.connect(self._on_compare_changed)
        panel.quality_changed.connect(self._on_quality_changed)
        panel.theme_changed.connect(self.set_theme)
        panel.language_changed.connect(self.set_language)
        panel.metadata_toggled.connect(self._on_metadata_toggled)
        panel.update_check_requested.connect(lambda: self.check_updates(silent=False))
        panel.update_action_requested.connect(self.on_update_action)
        panel.auto_update_toggled.connect(self._on_auto_update_toggled)
        panel.channel_changed.connect(self._on_channel_changed)

    def _create_actions(self) -> None:
        palette = self.palette_tokens
        muted = palette.text_muted

        def action(key: str, icon: str = "", shortcut: str = "", slot=None, *, checkable=False) -> QAction:
            item = QAction(t(key), self)
            if icon:
                item.setIcon(icons.icon(icon, muted, 18))
            if shortcut:
                item.setShortcut(QKeySequence(shortcut))
            if checkable:
                item.setCheckable(True)
            if slot:
                item.triggered.connect(slot)
            return item

        self.act_open = action("action.open", "open", "Ctrl+O", self.choose_and_open)
        self.act_save = action("action.save", "save", "Ctrl+S", self.save_image)
        self.act_save_as = action("action.save_as", "save", "Ctrl+Shift+S", lambda: self.save_image(force_as=True))
        self.act_quit = action("action.quit", "", "Ctrl+Q", self.close)

        self.act_undo = action("action.undo", "undo", "Ctrl+Z", self.undo)
        self.act_redo = action("action.redo", "redo", "Ctrl+Y", self.redo)
        self.act_add_head = action("action.add_head", "plus", "Ctrl+N", self.add_head_centred)
        self.act_remove_head = action("action.remove_head", "trash", "Del", lambda: self._on_region_delete(self.doc.selected))
        self.act_clear_heads = action("action.clear_regions", "trash", "", self.clear_regions)
        self.act_apply_all = action("action.apply_all", "", "", self.apply_scale_to_all)
        self.act_reset = action("action.reset_edits", "reset", "Ctrl+R", self.reset_edits)

        self.act_zoom_in = action("action.zoom_in", "zoom_in", "Ctrl+=", lambda: self.canvas.zoom_by(1.25))
        self.act_zoom_out = action("action.zoom_out", "zoom_out", "Ctrl+-", lambda: self.canvas.zoom_by(1 / 1.25))
        self.act_zoom_fit = action("action.zoom_fit", "fit", "Ctrl+0", lambda: self.canvas.fit_to_window())
        self.act_zoom_actual = action("action.zoom_reset", "actual", "Ctrl+1", lambda: self.canvas.reset_zoom())
        self.act_overlay = action("action.toggle_overlay", "layers", "H", self._toggle_overlay, checkable=True)
        self.act_overlay.setChecked(self.config.show_region_overlay)
        self.act_compare = action("action.compare", "compare", "C", self.cycle_compare)

        self.act_theme_dark = action("action.theme", "moon", "", lambda: self.set_theme("dark"), checkable=True)
        self.act_theme_light = action("action.theme", "sun", "", lambda: self.set_theme("light"), checkable=True)
        self.theme_group = QActionGroup(self)
        self.theme_group.addAction(self.act_theme_dark)
        self.theme_group.addAction(self.act_theme_light)
        self.act_theme_dark.setChecked(self.config.theme == "dark")
        self.act_theme_light.setChecked(self.config.theme == "light")

        self.language_group = QActionGroup(self)
        self.act_lang_th = action("", "", "", lambda: self.set_language("th"), checkable=True)
        self.act_lang_th.setText("ไทย")
        self.act_lang_en = action("", "", "", lambda: self.set_language("en"), checkable=True)
        self.act_lang_en.setText("English")
        for item in (self.act_lang_th, self.act_lang_en):
            self.language_group.addAction(item)
        self.act_lang_th.setChecked(self.config.language == "th")
        self.act_lang_en.setChecked(self.config.language == "en")

        self.act_detect = action("action.auto_detect", "scan", "Ctrl+D", self.detect_faces)
        self.act_refit = action("region.autofit", "target", "", self.refit_zone)
        self.act_check_updates = action("action.check_updates", "refresh", "Ctrl+U", lambda: self.check_updates(silent=False))
        self.act_settings = action("action.settings", "settings", "", self.open_settings)

        self.act_shortcuts = action("action.shortcuts", "help", "F1", self.show_shortcuts)
        self.act_docs = action("action.docs", "external", "", self.open_docs)
        self.act_about = action("action.about", "info", "", self.show_about)

        self.actions_all = [
            self.act_open, self.act_save, self.act_save_as, self.act_quit,
            self.act_undo, self.act_redo, self.act_add_head, self.act_remove_head,
            self.act_clear_heads, self.act_apply_all, self.act_reset,
            self.act_zoom_in, self.act_zoom_out, self.act_zoom_fit, self.act_zoom_actual,
            self.act_overlay, self.act_compare, self.act_detect, self.act_refit,
            self.act_check_updates, self.act_settings, self.act_shortcuts,
            self.act_docs, self.act_about,
        ]

    def _create_menus(self) -> None:
        bar = self.menuBar()
        bar.clear()

        file_menu = bar.addMenu(t("menu.file"))
        file_menu.addAction(self.act_open)
        self.recent_menu = file_menu.addMenu(t("action.recent"))
        self._rebuild_recent_menu()
        file_menu.addSeparator()
        file_menu.addAction(self.act_save)
        file_menu.addAction(self.act_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)

        edit_menu = bar.addMenu(t("menu.edit"))
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_add_head)
        edit_menu.addAction(self.act_remove_head)
        edit_menu.addAction(self.act_clear_heads)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_apply_all)
        edit_menu.addAction(self.act_reset)

        view_menu = bar.addMenu(t("menu.view"))
        view_menu.addAction(self.act_zoom_in)
        view_menu.addAction(self.act_zoom_out)
        view_menu.addAction(self.act_zoom_fit)
        view_menu.addAction(self.act_zoom_actual)
        view_menu.addSeparator()
        view_menu.addAction(self.act_overlay)
        view_menu.addAction(self.act_compare)
        view_menu.addSeparator()
        theme_menu = view_menu.addMenu(t("view.theme"))
        theme_menu.addAction(self.act_theme_dark)
        theme_menu.addAction(self.act_theme_light)
        language_menu = view_menu.addMenu(t("view.language"))
        language_menu.addAction(self.act_lang_th)
        language_menu.addAction(self.act_lang_en)

        tools_menu = bar.addMenu(t("menu.tools"))
        tools_menu.addAction(self.act_detect)
        tools_menu.addAction(self.act_refit)
        tools_menu.addSeparator()
        tools_menu.addAction(self.act_check_updates)
        tools_menu.addAction(self.act_settings)

        help_menu = bar.addMenu(t("menu.help"))
        help_menu.addAction(self.act_shortcuts)
        help_menu.addAction(self.act_docs)
        help_menu.addSeparator()
        help_menu.addAction(self.act_about)

    def _rebuild_recent_menu(self) -> None:
        menu = getattr(self, "recent_menu", None)
        if menu is None:
            return
        menu.clear()
        entries = [p for p in self.config.recent_files if Path(p).is_file()]
        if not entries:
            placeholder = QAction(t("action.recent"), self)
            placeholder.setEnabled(False)
            menu.addAction(placeholder)
            return
        for path in entries[:8]:
            item = QAction(Path(path).name, self)
            item.setToolTip(path)
            item.triggered.connect(lambda _checked=False, p=path: self.open_path(p))
            menu.addAction(item)

    def _create_toolbar(self) -> None:
        for existing in self.findChildren(QToolBar):
            self.removeToolBar(existing)
            existing.deleteLater()
        bar = QToolBar("main", self)
        bar.setMovable(False)
        bar.setIconSize(bar.iconSize())
        for item in (
            self.act_open,
            self.act_save,
            None,
            self.act_undo,
            self.act_redo,
            None,
            self.act_detect,
            self.act_add_head,
            None,
            self.act_zoom_fit,
            self.act_zoom_actual,
            self.act_zoom_out,
            self.act_zoom_in,
            None,
            self.act_compare,
            self.act_overlay,
        ):
            if item is None:
                bar.addSeparator()
            else:
                bar.addAction(item)
        self._add_spacer(bar)
        bar.addAction(self.act_check_updates)
        bar.addAction(self.act_settings)
        bar.addAction(self.act_shortcuts)
        self.addToolBar(bar)
        self.toolbar = bar

    def _add_spacer(self, bar: QToolBar) -> None:
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.addWidget(spacer)

    def _create_status_bar(self) -> None:
        status = QStatusBar()
        self.setStatusBar(status)

        self.status_label = QLabel(t("status.ready"))
        self.status_label.setObjectName("Muted")
        self.status_regions = QLabel("")
        self.status_regions.setObjectName("Faint")
        self.status_zoom = QLabel("100%")
        self.status_zoom.setObjectName("Faint")
        self.status_cursor = QLabel("")
        self.status_cursor.setObjectName("Faint")
        self.status_version = QLabel(f"v{__version__}")
        self.status_version.setObjectName("Faint")
        self.progress = QProgressBar()
        self.progress.setFixedWidth(160)
        self.progress.setRange(0, 100)
        self.progress.hide()

        status.addWidget(self.status_label, 1)
        status.addPermanentWidget(self.progress)
        status.addPermanentWidget(self.status_regions)
        status.addPermanentWidget(self.status_cursor)
        status.addPermanentWidget(self.status_zoom)
        status.addPermanentWidget(self.status_version)

    # ------------------------------------------------------------ preferences
    def _apply_preferences(self) -> None:
        self.panel.set_preferences(
            theme=self.config.theme,
            language=self.config.language,
            quality=self.config.render_quality,
            channel=self.config.update_channel,
            auto_update=self.config.check_updates_on_start,
            keep_metadata=self.config.keep_metadata,
            overlay=self.config.show_region_overlay,
        )
        owner, repo = resolve_repo(self.config.update_owner, self.config.update_repo)
        self.panel.set_repo(f"{owner}/{repo}" if repo_is_configured(owner, repo) else "")
        self.panel.set_version(__version__)
        self.panel.feather.set_value(self.config.default_feather)
        self.canvas.set_overlay_visible(self.config.show_region_overlay)
        self.canvas.set_split(self.config.compare_position)

    def _load_window_geometry(self) -> None:
        raw = self.config.window_geometry
        if not raw:
            return
        try:
            self.restoreGeometry(base64.b64decode(raw))
        except Exception:
            pass

    def _splitter_sizes(self) -> list[int]:
        raw = getattr(self.config, "splitter_state", "")
        sizes: list[int] = []
        if raw:
            try:
                sizes = [int(part) for part in str(raw).split(",") if part]
            except ValueError:
                sizes = []
        if len(sizes) != 2 or sizes[0] < 240:
            sizes = [352, max(600, self.width() - 352)]
        return sizes

    def _restore_geometry(self) -> None:
        self._load_window_geometry()

    def _save_window_state(self) -> None:
        try:
            self.config.window_geometry = base64.b64encode(
                bytes(self.saveGeometry())
            ).decode("ascii")
        except Exception:
            self.config.window_geometry = ""
        try:
            sizes = self.splitter.sizes()
            if len(sizes) == 2:
                setattr(self.config, "splitter_state", ",".join(str(s) for s in sizes))
        except Exception:
            pass

    # ------------------------------------------------------------------ file
    def choose_and_open(self) -> None:
        directory = self.config.last_directory or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, t("dialog.open_title"), directory, open_filter())
        if path:
            self.open_path(path)

    def open_path(self, path: str) -> None:
        if not path:
            return
        if not self.confirm_discard():
            return
        self.set_status(t("status.loading", name=Path(path).name))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.doc.load(path)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            QApplication.restoreOverrideCursor()
            self.error(t("dialog.open_error", message=exc))
            return
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        self.config.remember_file(path)
        self._last_save_path = None
        self.canvas.request_fit()
        self._refresh_all()
        self.set_status(
            t(
                "status.loaded",
                name=Path(path).name,
                width=self.doc.size[0],
                height=self.doc.size[1],
            )
        )
        if self.config.auto_detect_on_open:
            self.detect_faces()

    def save_image(self, *, force_as: bool = False) -> None:
        if not self.doc.has_image:
            return
        target: Path | None = None
        if not force_as and self._last_save_path is not None:
            target = self._last_save_path
        if target is None:
            target = self._suggested_save_path()
            chosen, _ = QFileDialog.getSaveFileName(
                self, t("dialog.save_title"), str(target), save_filter()
            )
            if not chosen:
                return
            target = Path(chosen)
            if (
                self.config.ask_before_overwrite
                and target.exists()
                and self._last_save_path != target
            ):
                answer = QMessageBox.question(
                    self,
                    t("dialog.overwrite_title"),
                    t("dialog.overwrite_body", name=target.name),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return

        self.set_status(t("status.render"))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = self.doc.render_full(quality=self.config.render_quality)
            source = self.doc.source
            save_image(
                result,
                target,
                quality=self.config.jpeg_quality,
                icc_profile=source.icc_profile if self.config.keep_metadata and source else None,
                dpi=source.dpi if self.config.keep_metadata and source else None,
                exif=source.exif if self.config.keep_metadata and source else None,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            QApplication.restoreOverrideCursor()
            self.error(t("dialog.save_error", message=exc))
            return
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        self._last_save_path = target
        self.doc.dirty = False
        self.set_status(t("status.saved", path=str(target)))
        self._update_status()
        self._update_actions()

    def _suggested_save_path(self) -> Path:
        source = self.doc.source
        if source is None or source.path is None:
            return Path(self.config.last_directory or Path.home()) / "headsize.jpg"
        stem = source.path.stem + "-headsize"
        suffix = source.path.suffix or ".jpg"
        return source.path.with_name(f"{stem}{suffix}")

    def confirm_discard(self) -> bool:
        if not self.doc.dirty or not self.doc.has_image:
            return True
        box = QMessageBox(self)
        box.setWindowTitle(t("dialog.unsaved_title"))
        box.setText(t("dialog.unsaved_body"))
        box.setIcon(QMessageBox.Icon.Question)
        save_button = box.addButton(t("dialog.save_and_close"), QMessageBox.ButtonRole.AcceptRole)
        discard_button = box.addButton(t("dialog.discard"), QMessageBox.ButtonRole.DestructiveRole)
        keep_button = box.addButton(t("dialog.keep"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save_button:
            self.save_image()
            return not self.doc.dirty
        if clicked is discard_button:
            return True
        if clicked is keep_button:
            return False
        return False

    # ------------------------------------------------------------- documents
    def _refresh_all(self, *, render: bool = True) -> None:
        source = self.doc.source
        width, height = self.doc.size
        self.panel.set_image_info(
            source.name if source else "",
            width,
            height,
            has_image=self.doc.has_image,
            face_count=len(self.doc.regions),
        )
        self.panel.set_regions(self.doc.regions, self.doc.selected)
        self._update_actions()
        if render:
            self._render_now()
        self._update_status()

    def _update_actions(self) -> None:
        has_image = self.doc.has_image
        selected = 0 <= self.doc.selected < len(self.doc.regions)
        for item in (self.act_save, self.act_save_as, self.act_reset, self.act_clear_heads,
                     self.act_detect, self.act_add_head, self.act_zoom_in, self.act_zoom_out,
                     self.act_zoom_fit, self.act_zoom_actual, self.act_compare):
            item.setEnabled(has_image)
        self.act_overlay.setEnabled(True)
        self.act_undo.setEnabled(self.doc.can_undo)
        self.act_redo.setEnabled(self.doc.can_redo)
        self.act_remove_head.setEnabled(selected)
        self.act_apply_all.setEnabled(len(self.doc.regions) > 1)
        self.act_refit.setEnabled(selected)
        self.act_overlay.setChecked(self.config.show_region_overlay)

    def _update_status(self) -> None:
        if not self.doc.has_image:
            self.status_regions.setText(t("status.no_image"))
        else:
            self.status_regions.setText(t("status.regions", count=len(self.doc.regions)))
        percent = int(round(self.canvas.zoom * 100))
        self.status_zoom.setText(t("zoom.percent", percent=percent))
        if self.doc.has_image and self.doc.dirty:
            self.status_version.setText(f"v{__version__} · {t('status.edited')}")
        else:
            self.status_version.setText(f"v{__version__}")

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def error(self, message: str) -> None:
        QMessageBox.critical(self, t("dialog.error_title"), message)
        self.set_status(t("status.ready"))

    # --------------------------------------------------------------- editing
    def _begin_interaction(self, label: str) -> None:
        if self._interaction is None:
            self._interaction = (label, [r.copy() for r in self.doc.regions])

    def _end_interaction(self) -> None:
        if self._interaction is None:
            return
        label, before = self._interaction
        self._interaction = None
        self.doc.push_history(before, label)
        self._update_actions()
        self._update_status()

    def _render_now(self) -> None:
        self._render_timer.stop()
        if not self.doc.has_image:
            self.canvas.set_images(None, None, (0, 0))
            return
        source, result, _scale = self.doc.preview_bundle()
        self.canvas.set_images(source, result, self.doc.size)
        self.canvas.set_regions(self.doc.regions, self.doc.selected)

    def _schedule_render(self) -> None:
        self._render_timer.start()

    # ---------------------------------------------------------- panel handlers
    def _on_scale_changed(self, value: float, committed: bool) -> None:
        index = self.doc.selected
        if not (0 <= index < len(self.doc.regions)):
            return
        if committed:
            self._begin_interaction("scale")
        self.doc.apply_live(index, scale=value)
        self.panel.set_scale(value)
        self._schedule_render()
        if committed:
            self._end_interaction()

    def _on_feather_changed(self, value: float, committed: bool) -> None:
        index = self.doc.selected
        if not (0 <= index < len(self.doc.regions)):
            return
        if committed:
            self._begin_interaction("feather")
        self.doc.apply_live(index, feather=value)
        self._schedule_render()
        if committed:
            self._end_interaction()

    def _on_zone_changed(self, field: str, value: float, committed: bool) -> None:
        index = self.doc.selected
        if not (0 <= index < len(self.doc.regions)):
            return
        if committed:
            self._begin_interaction("zone")
        self.doc.apply_live(index, **{field: value})
        self._schedule_render()
        if committed:
            self._end_interaction()

    def _on_region_selected(self, index: int) -> None:
        self.doc.select(index)
        self.canvas.set_regions(self.doc.regions, index)
        self.canvas.update()
        self.panel.set_regions(self.doc.regions, index)
        self._update_actions()
        self._update_status()

    def _on_selection_changed(self, index: int) -> None:
        self.doc.select(index)
        self.panel.set_regions(self.doc.regions, index)
        self._update_actions()

    def _on_region_toggle(self, index: int) -> None:
        if not (0 <= index < len(self.doc.regions)):
            return
        region = self.doc.regions[index]
        self.doc.update_region(index, enabled=not region.enabled, label="toggle")
        self._refresh_all()

    def _on_region_delete(self, index: int) -> None:
        if not (0 <= index < len(self.doc.regions)):
            return
        self.doc.remove_region(index)
        self._refresh_all()

    def _on_region_requested(self, x: float, y: float) -> None:
        if not self.doc.has_image:
            return
        width, height = self.doc.size
        region = HeadRegion(
            cx=x,
            cy=y,
            rx=max(20.0, width * 0.085),
            ry=max(24.0, height * 0.115),
            feather=self.config.default_feather,
            origin="manual",
        )
        index = self.doc.add_region(region, label="add-region")
        self._refresh_all()
        self._on_region_selected(index)

    def _on_region_changed(self, index: int, changes: dict) -> None:
        self._begin_interaction("drag-region")
        self.doc.apply_live(index, **changes)
        self._schedule_render()

    def _on_region_committed(self, index: int, changes: dict) -> None:
        self.doc.apply_live(index, **changes)
        self._end_interaction()
        self.panel.set_regions(self.doc.regions, index)
        self.panel.set_zone(self.doc.regions[index])
        self._update_actions()
        self._update_status()

    def _on_overlay_toggled(self, visible: bool) -> None:
        self.config.show_region_overlay = bool(visible)
        self.canvas.set_overlay_visible(bool(visible))
        self.act_overlay.blockSignals(True)
        self.act_overlay.setChecked(bool(visible))
        self.act_overlay.blockSignals(False)

    def _toggle_overlay(self) -> None:
        self._on_overlay_toggled(self.act_overlay.isChecked())
        self.panel.overlay_check.blockSignals(True)
        self.panel.overlay_check.setChecked(self.act_overlay.isChecked())
        self.panel.overlay_check.blockSignals(False)

    def _on_compare_changed(self, mode: str) -> None:
        self.canvas.set_compare(mode)
        if mode == "split":
            self.canvas.set_split(self.config.compare_position)

    def cycle_compare(self) -> None:
        current = self.panel.compare_control.current()
        try:
            index = (COMPARE_CYCLE.index(current) + 1) % len(COMPARE_CYCLE)
        except ValueError:
            index = 0
        mode = COMPARE_CYCLE[index]
        self.panel.compare_control.set_current(mode)
        self._on_compare_changed(mode)

    def _on_quality_changed(self, quality: str) -> None:
        self.config.render_quality = quality

    def _on_metadata_toggled(self, keep: bool) -> None:
        self.config.keep_metadata = bool(keep)

    def _on_auto_update_toggled(self, enabled: bool) -> None:
        self.config.check_updates_on_start = bool(enabled)

    def _on_channel_changed(self, channel: str) -> None:
        self.config.update_channel = channel

    def _on_cursor_position(self, x: float, y: float) -> None:
        width, height = self.doc.size
        if 0 <= x < width and 0 <= y < height:
            self.status_cursor.setText(t("status.cursor", x=int(x), y=int(y)))
        else:
            self.status_cursor.setText("")

    # ------------------------------------------------------------ head actions
    def add_head_centred(self) -> None:
        if not self.doc.has_image:
            return
        width, height = self.doc.size
        self._on_region_requested(width / 2, height / 2)

    def apply_scale_to_all(self) -> None:
        index = self.doc.selected
        if not (0 <= index < len(self.doc.regions)):
            return
        scale = self.doc.regions[index].scale
        feather = self.doc.regions[index].feather
        self.doc.update_all(label="apply-all", scale=scale, feather=feather)
        self._refresh_all()

    def clear_regions(self) -> None:
        if not self.doc.regions:
            return
        self.doc.clear_regions()
        self._refresh_all()

    def reset_edits(self) -> None:
        if not self.doc.has_image or not self.doc.regions:
            return
        self.doc.update_all(label="reset-scales", scale=1.0)
        self._refresh_all()
        self.set_status(t("action.reset_edits"))

    def undo(self) -> None:
        if self.doc.undo():
            self._refresh_all()

    def redo(self) -> None:
        if self.doc.redo():
            self._refresh_all()

    def refit_zone(self) -> None:
        """Snap the selected region onto the nearest detected face."""
        index = self.doc.selected
        if not (0 <= index < len(self.doc.regions)):
            return
        region = self.doc.regions[index]
        faces = self._detect_sync()
        if not faces:
            self.panel.set_faces_message(t("faces.not_found"))
            return
        nearest = min(
            faces,
            key=lambda r: (r.cx - region.cx) ** 2 + (r.cy - region.cy) ** 2,
        )
        self._begin_interaction("refit")
        self.doc.apply_live(
            index,
            cx=nearest.cx,
            cy=nearest.cy,
            rx=nearest.rx,
            ry=nearest.ry,
            angle=nearest.angle,
        )
        self._end_interaction()
        self._refresh_all()

    # -------------------------------------------------------------- detection
    def _detector(self) -> FaceDetector:
        if self.detector is None:
            self.detector = FaceDetector(score_threshold=self.config.detection_score)
        return self.detector

    def _detect_sync(self) -> list[HeadRegion]:
        if not self.doc.has_image or not model_is_available():
            return []
        try:
            return self._detector().detect_regions(self.doc.array)
        except ModelUnavailableError:
            return []
        except Exception:  # noqa: BLE001 - detection must never crash the UI
            return []

    def detect_faces(self) -> None:
        if not self.doc.has_image:
            return
        if not model_is_available():
            self._offer_model_download()
            return
        self.panel.set_busy(True, message=t("status.detecting"))
        self.set_status(t("status.detecting"))
        image = self.doc.array
        self.workers.submit(
            self._detector().detect_regions,
            image=image,
            on_finished=self._on_detected,
            on_failed=self._on_detect_failed,
        )

    def _on_detected(self, regions: Sequence[HeadRegion]) -> None:
        self.panel.set_busy(False)
        if not regions:
            self.panel.set_faces_message(t("faces.not_found"))
            self.set_status(t("faces.not_found"))
            return
        self.doc.set_regions(regions, select=0, label="detect")
        self._refresh_all()
        self.panel.set_faces_message(t("faces.detected", count=len(regions)))
        self.set_status(t("faces.detected", count=len(regions)))

    def _on_detect_failed(self, message: str) -> None:
        self.panel.set_busy(False)
        if "not found" in message.lower():
            self._offer_model_download()
            return
        self.error(t("dialog.detect_error", message=message.splitlines()[0]))

    def _offer_model_download(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(t("dialog.model_title"))
        box.setText(t("dialog.model_body"))
        box.setIcon(QMessageBox.Icon.Warning)
        download = box.addButton(t("dialog.model_download"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(t("dialog.model_later"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not download:
            return
        from headsize.core.detector import download_model

        self.progress.show()
        self.progress.setRange(0, 0)
        self.set_status(t("update.downloading", percent=0))

        def _progress(done: int, total: int) -> None:
            if total:
                percent = int(done * 100 / total)
                self.status_label.setText(t("update.downloading", percent=percent))

        worker = FunctionWorker(download_model, progress=_progress)
        worker.signals.finished.connect(self._on_model_downloaded)
        worker.signals.failed.connect(self._on_model_failed)
        self.workers.start(worker)

    def _on_model_downloaded(self, path) -> None:
        self.progress.hide()
        self.progress.setRange(0, 100)
        self.detector = None
        self.set_status(t("dialog.model_done"))
        self.detect_faces()

    def _on_model_failed(self, message: str) -> None:
        self.progress.hide()
        self.progress.setRange(0, 100)
        self.error(t("dialog.model_failed", message=message.splitlines()[0]))

    # ------------------------------------------------------------------ theme
    def set_theme(self, name: str) -> None:
        if name not in ("dark", "light"):
            return
        self.config.theme = name
        apply_theme(QApplication.instance(), name)
        self.palette_tokens = get_palette(name)
        set_active_theme(name)
        self._rebuild_ui()
        self._refresh_all()

    def set_language(self, code: str) -> None:
        if code not in dict(available_languages()):
            return
        self.config.language = code
        set_language(code)
        self._rebuild_ui()
        self._refresh_all()
        self._apply_preferences()

    def _rebuild_ui(self) -> None:
        """Rebuild menus, toolbar and panels (theme or language change)."""
        for existing in self.findChildren(QToolBar):
            self.removeToolBar(existing)
            existing.deleteLater()
        central = self.takeCentralWidget()
        if central is not None:
            central.setParent(None)
            central.deleteLater()
        self._build_ui()

    # --------------------------------------------------------------- settings
    def open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            for key, value in dialog.values().items():
                setattr(self.config, key, value)
            self.config.sanitize()
            self.detector = None
            self._apply_preferences()
            self._update_actions()

    def show_about(self) -> None:
        dialog = AboutDialog(__version__, self.palette_tokens, self)
        dialog.docs_requested.connect(self.open_docs)
        dialog.exec()

    def show_shortcuts(self) -> None:
        ShortcutsDialog(self).exec()

    def open_docs(self) -> None:
        owner, repo = resolve_repo(self.config.update_owner, self.config.update_repo)
        QDesktopServices.openUrl(QUrl(DOCS_URL.format(slug=f"{owner}/{repo}")))

    # ---------------------------------------------------------------- updates
    def _updater(self) -> Updater | None:
        owner, repo = resolve_repo(self.config.update_owner, self.config.update_repo)
        if not repo_is_configured(owner, repo):
            return None
        return Updater(owner, repo, __version__, channel=self.config.update_channel)

    def check_updates(self, *, silent: bool = False) -> None:
        updater = self._updater()
        if updater is None:
            self.panel.set_update_status(t("update.disabled"), icon="alert")
            if not silent:
                self.set_status(t("update.disabled"))
            return
        self.panel.clear_update_status()
        if not silent:
            self.set_status(t("update.checking"))
            self.panel.set_update_status(t("update.checking"), icon="info")
        self.workers.submit(
            updater.check,
            on_finished=lambda check: self._on_update_checked(updater, check, silent),
            on_failed=lambda message: self._on_update_failed(message, silent),
        )

    def _on_update_checked(self, updater: Updater, check: UpdateCheck, silent: bool) -> None:
        self._pending_update = updater
        self._pending_check = check
        if check.status == "available":
            self.panel.set_update_status(
                t("update.available", version=check.latest), icon="download", action=t("update.now")
            )
            self.set_status(t("update.available", version=check.latest))
        elif check.status == "up-to-date":
            self.panel.set_update_status(
                t("update.up_to_date", version=check.current), icon="check"
            )
            if not silent:
                self.set_status(t("update.up_to_date", version=check.current))
        else:
            self.panel.set_update_status(check.message or t("update.disabled"), icon="alert")
            if not silent:
                self.set_status(check.message or t("update.disabled"))

    def _on_update_failed(self, message: str, silent: bool) -> None:
        text = t("update.failed", message=message.splitlines()[0])
        self.panel.set_update_status(text, icon="alert")
        if not silent:
            self.set_status(text)

    def on_update_action(self) -> None:
        """The sidebar banner button: open the update dialog (or re-check)."""
        check = self._pending_check
        if check is None or not check.available or check.release is None:
            self.check_updates(silent=False)
            return
        self.show_update_dialog(check)

    def show_update_dialog(self, check: UpdateCheck) -> None:
        release = check.release
        if release is None:
            return
        dialog = UpdateDialog(
            check.latest, check.current, release.notes, release.html_url, self.palette_tokens, self
        )
        dialog.download_requested.connect(lambda: self._start_update_download(dialog, release))
        if dialog.exec() == QDialog.DialogCode.Accepted and self._downloaded is not None:
            self.close()

    def _start_update_download(self, dialog: UpdateDialog, release) -> None:
        updater = self._pending_update or self._updater()
        if updater is None:
            dialog.set_error(t("update.disabled"))
            return
        dialog.set_downloading(0)

        def _progress(done: int, total: int) -> None:
            if total:
                dialog.set_downloading(int(done * 100 / total))

        def _download() -> DownloadedUpdate:
            return updater.download(release, progress=_progress)

        worker = FunctionWorker(_download)
        worker.signals.progress.connect(lambda done, total: dialog.set_downloading(int(done * 100 / total) if total else 0))
        worker.signals.finished.connect(lambda payload: self._on_update_downloaded(dialog, payload))
        worker.signals.failed.connect(lambda message: dialog.set_error(message.splitlines()[0]))
        self.workers.start(worker)

    def _on_update_downloaded(self, dialog: UpdateDialog, payload: DownloadedUpdate) -> None:
        from headsize.update.selfupdate import apply_update

        if payload.warning:
            self.set_status(payload.warning)
        if not supports_self_update():
            dialog.set_error(
                "This copy runs from source; install the new build from the release page."
            )
            QDesktopServices.openUrl(QUrl(payload.release_url or release_page(
                *resolve_repo(self.config.update_owner, self.config.update_repo)
            )))
            return
        dialog.set_installing()
        try:
            apply_update(payload.path)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            dialog.set_error(str(exc))
            return
        self._downloaded = payload
        self._installing = True
        dialog.accept()
        self.set_status(t("update.installing"))
        QTimer.singleShot(400, QApplication.instance().quit)

    # ------------------------------------------------------------------ misc
    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt naming
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.open_path(url.toLocalFile())
                event.acceptProposedAction()
                return

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if not getattr(self, "_installing", False) and not self.confirm_discard():
            event.ignore()
            return
        self._save_window_state()
        try:
            self.config.save()
        except OSError:
            pass
        self.workers.wait(1500)
        event.accept()


__all__ = ["DOCS_URL", "MainWindow"]
