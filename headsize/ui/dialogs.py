"""Secondary windows: about, updates, shortcuts, settings."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from headsize.ui import icons
from headsize.ui.i18n import t
from headsize.ui.theme import Palette

SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("Ctrl+O", "action.open"),
    ("Ctrl+S", "action.save"),
    ("Ctrl+Shift+S", "action.save_as"),
    ("Ctrl+D", "action.auto_detect"),
    ("Ctrl+N", "action.add_head"),
    ("Del", "action.remove_head"),
    ("Ctrl+Z", "action.undo"),
    ("Ctrl+Y", "action.redo"),
    ("Ctrl+R", "action.reset_edits"),
    ("Ctrl+=", "action.zoom_in"),
    ("Ctrl+-", "action.zoom_out"),
    ("Ctrl+0", "action.zoom_fit"),
    ("Ctrl+1", "action.zoom_reset"),
    ("H", "action.toggle_overlay"),
    ("C", "action.compare"),
    ("Ctrl+U", "action.check_updates"),
    ("F1", "action.shortcuts"),
    ("Ctrl+Q", "action.quit"),
)


class AboutDialog(QDialog):
    """Product information."""

    docs_requested = pyqtSignal()

    def __init__(self, version: str, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("action.about"))
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(14)
        logo = QLabel()
        logo.setPixmap(icons.pixmap("target", palette.accent, 52))
        header.addWidget(logo)
        body = QLabel(
            t("about.body", version=version, tagline=t("app.tagline"))
        )
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setOpenExternalLinks(True)
        header.addWidget(body, 1)
        layout.addLayout(header)

        credits = QLabel(
            "YuNet — Shiqi Yu, <i>YuNet: A Tiny Millisecond-level Face Detector</i>, "
            "MIT licence · PyQt6 · OpenCV · NumPy · Pillow"
        )
        credits.setObjectName("Hint")
        credits.setWordWrap(True)
        layout.addWidget(credits)

        buttons = QDialogButtonBox()
        docs_button = buttons.addButton(t("action.docs"), QDialogButtonBox.ButtonRole.ActionRole)
        docs_button.clicked.connect(self.docs_requested.emit)
        close_button = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        close_button.setText(t("action.about") and "OK")
        close_button.clicked.connect(self.accept)
        layout.addWidget(buttons)


class ShortcutsDialog(QDialog):
    """A two-column cheat sheet."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("shortcuts.title"))
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        for row, (keys, action_key) in enumerate(SHORTCUTS):
            key_label = QLabel(keys)
            key_label.setFont(mono)
            key_label.setObjectName("Badge")
            action_label = QLabel(t(action_key))
            action_label.setObjectName("Muted")
            grid.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(action_label, row, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class UpdateDialog(QDialog):
    """Shows the release notes and drives the download."""

    download_requested = pyqtSignal()
    page_requested = pyqtSignal()

    def __init__(
        self,
        version: str,
        current: str,
        notes: str,
        url: str,
        palette: Palette,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("action.check_updates"))
        self.setMinimumSize(560, 460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(icons.pixmap("download", palette.accent, 40))
        header.addWidget(logo)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel(t("update.available", version=version))
        title.setObjectName("Title")
        subtitle = QLabel(t("app.version", version=current))
        subtitle.setObjectName("Hint")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch(1)
        layout.addLayout(header)

        self.notes = QTextBrowser()
        self.notes.setOpenExternalLinks(True)
        try:
            self.notes.setMarkdown(notes or "_No release notes._")
        except Exception:  # pragma: no cover - very old Qt
            self.notes.setPlainText(notes or "")
        layout.addWidget(self.notes, 1)

        self.status = QLabel("")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.page_button = QPushButton(t("update.open_page"))
        self.page_button.setObjectName("Ghost")
        self.page_button.clicked.connect(lambda: self._open(url))
        self.later_button = QPushButton(t("update.later"))
        self.later_button.clicked.connect(self.reject)
        self.update_button = QPushButton(t("update.now"))
        self.update_button.setObjectName("Primary")
        self.update_button.clicked.connect(self.download_requested.emit)
        buttons.addWidget(self.page_button)
        buttons.addStretch(1)
        buttons.addWidget(self.later_button)
        buttons.addWidget(self.update_button)
        layout.addLayout(buttons)

    def _open(self, url: str) -> None:
        if url:
            QDesktopServices.openUrl(QUrl(url))

    # ------------------------------------------------------------------ states
    def set_downloading(self, percent: int) -> None:
        self.progress.show()
        self.progress.setValue(max(0, min(100, percent)))
        self.status.setText(t("update.downloading", percent=percent))
        self.update_button.setEnabled(False)

    def set_installing(self) -> None:
        self.progress.setRange(0, 0)
        self.status.setText(t("update.installing"))
        self.update_button.setEnabled(False)

    def set_error(self, message: str) -> None:
        self.progress.hide()
        self.status.setText(t("update.failed", message=message))
        self.update_button.setEnabled(True)


class SettingsDialog(QDialog):
    """Advanced preferences that do not deserve a permanent sidebar slot."""

    def __init__(self, config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("action.settings"))
        self.setMinimumWidth(460)
        self._config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)

        self.owner = QLineEdit(config.update_owner)
        self.owner.setPlaceholderText("github-owner")
        self.repo = QLineEdit(config.update_repo)
        self.repo.setPlaceholderText("repository-name")
        form.addRow(t("update.repo") + " (owner)", self.owner)
        form.addRow(t("update.repo") + " (name)", self.repo)

        self.quality = QSpinBox()
        self.quality.setRange(50, 100)
        self.quality.setValue(int(config.jpeg_quality))
        self.quality.setSuffix(" %")
        form.addRow("JPEG / WebP quality", self.quality)

        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.1, 0.99)
        self.threshold.setSingleStep(0.05)
        self.threshold.setDecimals(2)
        self.threshold.setValue(float(config.detection_score))
        form.addRow("Face detection threshold", self.threshold)

        self.feather = QDoubleSpinBox()
        self.feather.setRange(0.0, 0.90)
        self.feather.setSingleStep(0.05)
        self.feather.setDecimals(2)
        self.feather.setValue(float(config.default_feather))
        form.addRow(t("region.feather") + " (default)", self.feather)

        self.ask_overwrite = QCheckBox(t("dialog.overwrite_title"))
        self.ask_overwrite.setChecked(bool(config.ask_before_overwrite))
        form.addRow(self.ask_overwrite)

        layout.addLayout(form)

        note = QLabel(
            "The update repository is baked into release builds; change it here only "
            "for forks or a private mirror."
        )
        note.setObjectName("Hint")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, Any]:
        return {
            "update_owner": self.owner.text().strip(),
            "update_repo": self.repo.text().strip(),
            "jpeg_quality": int(self.quality.value()),
            "detection_score": float(self.threshold.value()),
            "default_feather": float(self.feather.value()),
            "ask_before_overwrite": bool(self.ask_overwrite.isChecked()),
        }


__all__ = [
    "AboutDialog",
    "SHORTCUTS",
    "SettingsDialog",
    "ShortcutsDialog",
    "UpdateDialog",
]
