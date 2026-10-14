"""Colour palettes and the stylesheet that gives the app its look.

The stylesheet is a template with ``@token`` placeholders so the palette can be
swapped without fighting Qt's brace-heavy CSS syntax.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

FONT_STACK = '"Segoe UI Variable Display", "Segoe UI", "Leelawadee UI", "Noto Sans Thai", "Inter", sans-serif'
MONO_STACK = '"Cascadia Code", "JetBrains Mono", "Consolas", monospace'


@dataclass(frozen=True)
class Palette:
    name: str
    window: str
    panel: str
    surface: str
    surface_alt: str
    surface_hover: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_faint: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    accent_text: str
    success: str
    warning: str
    danger: str
    groove: str
    handle: str
    canvas: str
    checker_light: str
    checker_dark: str
    shadow: str


DARK = Palette(
    name="dark",
    window="#101319",
    panel="#151922",
    surface="#1b2130",
    surface_alt="#212838",
    surface_hover="#26304a",
    border="#28313f",
    border_strong="#3a475c",
    text="#e9eefb",
    text_muted="#9aa7c2",
    text_faint="#6b7891",
    accent="#6c8cff",
    accent_hover="#829bff",
    accent_pressed="#5a7bf0",
    accent_soft="rgba(108, 140, 255, 34)",
    accent_text="#0d1220",
    success="#48d29a",
    warning="#ffc86b",
    danger="#ff7a7a",
    groove="#2a3346",
    handle="#8fa6ff",
    canvas="#0b0e14",
    checker_light="#2a3040",
    checker_dark="#222836",
    shadow="rgba(0, 0, 0, 120)",
)

LIGHT = Palette(
    name="light",
    window="#eef1f8",
    panel="#f7f9fd",
    surface="#ffffff",
    surface_alt="#f1f4fb",
    surface_hover="#e6ebf7",
    border="#dbe2ef",
    border_strong="#c3ccdd",
    text="#1a2130",
    text_muted="#5d6a83",
    text_faint="#8b97ad",
    accent="#3f63f0",
    accent_hover="#5474f5",
    accent_pressed="#3352d6",
    accent_soft="rgba(63, 99, 240, 26)",
    accent_text="#ffffff",
    success="#0f9d69",
    warning="#b7791f",
    danger="#d64545",
    groove="#e2e7f2",
    handle="#3f63f0",
    canvas="#dfe4ef",
    checker_light="#ccd3e2",
    checker_dark="#c2cadb",
    shadow="rgba(24, 39, 75, 40)",
)

PALETTES = {"dark": DARK, "light": LIGHT}


def palette(name: str) -> Palette:
    return PALETTES.get(name, DARK)


_QSS = """
* {
    font-family: @font_stack;
    font-size: 13px;
    outline: none;
}
QWidget { color: @text; }
QMainWindow, QDialog { background: @window; }
QWidget#Sidebar { background: @panel; border-right: 1px solid @border; }
QWidget#Canvas { background: @canvas; }
QLabel#Title { font-size: 17px; font-weight: 600; letter-spacing: 0.2px; }
QLabel#CardTitle { font-size: 12px; font-weight: 600; color: @text_muted; letter-spacing: 0.6px; text-transform: uppercase; }
QLabel#Muted { color: @text_muted; }
QLabel#Faint { color: @text_faint; font-size: 11px; }
QLabel#Value { font-size: 22px; font-weight: 600; color: @text; }
QLabel#ValueSmall { font-size: 15px; font-weight: 600; }
QLabel#Badge { background: @accent_soft; color: @accent; border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 600; }
QLabel#GoodBadge { background: rgba(72, 210, 154, 40); color: @success; border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 600; }
QLabel#WarnBadge { background: rgba(255, 200, 107, 40); color: @warning; border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 600; }
QLabel#Hint { color: @text_faint; font-size: 11px; }
QLabel#EmptyTitle { font-size: 16px; font-weight: 600; color: @text_muted; }
QLabel#EmptyBody { color: @text_faint; }

QFrame#Card {
    background: @surface;
    border: 1px solid @border;
    border-radius: 12px;
}
QFrame#CardHeaderLine { background: @border; max-height: 1px; border: none; }
QFrame#RegionRow {
    background: @surface_alt;
    border: 1px solid @border;
    border-radius: 9px;
}
QFrame#RegionRow[selected="true"] {
    background: @surface_hover;
    border: 1px solid @accent;
}
QFrame#Banner {
    background: @surface_alt;
    border: 1px solid @border;
    border-radius: 10px;
}
QFrame#Divider { background: @border; border: none; max-height: 1px; }

QPushButton {
    background: @surface_alt;
    color: @text;
    border: 1px solid @border;
    border-radius: 9px;
    padding: 7px 12px;
    font-weight: 500;
}
QPushButton:hover { background: @surface_hover; border-color: @border_strong; }
QPushButton:pressed { background: @surface; }
QPushButton:disabled { color: @text_faint; background: @surface; border-color: @border; }
QPushButton#Primary {
    background: @accent;
    color: @accent_text;
    border: 1px solid @accent;
    font-weight: 600;
}
QPushButton#Primary:hover { background: @accent_hover; border-color: @accent_hover; }
QPushButton#Primary:pressed { background: @accent_pressed; }
QPushButton#Primary:disabled { background: @surface_alt; color: @text_faint; border-color: @border; }
QPushButton#Ghost { background: transparent; border: 1px solid transparent; color: @text_muted; }
QPushButton#Ghost:hover { background: @surface_alt; color: @text; }
QPushButton#Chip {
    padding: 5px 9px;
    border-radius: 8px;
    background: @surface_alt;
    color: @text_muted;
    font-size: 12px;
}
QPushButton#Chip:hover { color: @text; background: @surface_hover; }
QPushButton#Chip:checked { background: @accent; color: @accent_text; border-color: @accent; font-weight: 600; }
QPushButton#Tiny {
    padding: 2px 6px;
    font-size: 11px;
    border-radius: 7px;
    color: @text_muted;
    background: transparent;
    border: 1px solid transparent;
}
QPushButton#Tiny:hover { background: @surface_hover; color: @text; }
QPushButton#Danger:hover { background: rgba(255, 122, 122, 30); color: @danger; border-color: rgba(255,122,122,80); }

QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 7px;
    color: @text_muted;
}
QToolButton:hover { background: @surface_alt; color: @text; }
QToolButton:pressed, QToolButton:checked { background: @surface_hover; color: @accent; }
QToolButton:disabled { color: @text_faint; }
QToolBar {
    background: @panel;
    border-bottom: 1px solid @border;
    padding: 4px 6px;
    spacing: 4px;
}
QToolBar::separator { background: @border; width: 1px; margin: 6px 4px; }

QMenuBar { background: @panel; border-bottom: 1px solid @border; padding: 2px 4px; }
QMenuBar::item { padding: 5px 10px; border-radius: 7px; background: transparent; }
QMenuBar::item:selected { background: @surface_alt; }
QMenu { background: @surface; border: 1px solid @border; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 6px 26px 6px 12px; border-radius: 7px; }
QMenu::item:selected { background: @accent_soft; color: @text; }
QMenu::item:disabled { color: @text_faint; }
QMenu::separator { height: 1px; background: @border; margin: 5px 8px; }

QSlider::groove:horizontal {
    height: 6px;
    border-radius: 3px;
    background: @groove;
}
QSlider::sub-page:horizontal { background: @accent; border-radius: 3px; }
QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: @handle;
    border: 2px solid @surface;
}
QSlider::handle:horizontal:hover { background: @accent_hover; }
QSlider::handle:horizontal:disabled { background: @border_strong; }
QSlider::groove:vertical { width: 6px; border-radius: 3px; background: @groove; }
QSlider::handle:vertical { height: 16px; margin: 0 -6px; border-radius: 8px; background: @handle; }

QCheckBox { spacing: 8px; color: @text; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 5px;
    border: 1px solid @border_strong;
    background: @surface_alt;
}
QCheckBox::indicator:checked { background: @accent; border-color: @accent; image: none; }
QCheckBox::indicator:hover { border-color: @accent; }

QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background: @surface_alt;
    border: 1px solid @border;
    border-radius: 8px;
    padding: 6px 9px;
    min-height: 18px;
    color: @text;
    selection-background-color: @accent;
    selection-color: @accent_text;
}
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover { border-color: @border_strong; }
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus { border-color: @accent; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox::down-arrow { image: none; }
QComboBox QAbstractItemView {
    background: @surface;
    border: 1px solid @border;
    border-radius: 9px;
    padding: 4px;
    selection-background-color: @accent_soft;
    selection-color: @text;
    outline: none;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 16px; background: transparent; border: none; }

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: @border_strong; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: @accent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: @border_strong; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QStatusBar { background: @panel; border-top: 1px solid @border; color: @text_muted; }
QStatusBar::item { border: none; }
QProgressBar {
    background: @groove;
    border: none;
    border-radius: 5px;
    height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk { background: @accent; border-radius: 5px; }

QSplitter::handle { background: @border; width: 1px; }
QSplitter::handle:hover { background: @accent; }

QToolTip {
    background: @surface;
    color: @text;
    border: 1px solid @border;
    border-radius: 8px;
    padding: 6px 9px;
}

QTextBrowser, QTextEdit {
    background: @surface_alt;
    border: 1px solid @border;
    border-radius: 10px;
    padding: 10px;
}
QScrollArea#SidebarScroll, QScrollArea#SidebarScroll > QWidget#qt_scrollarea_viewport {
    background: @panel;
    border: none;
}
QWidget#SidebarInner { background: @panel; }
"""


def build_qss(palette_: Palette) -> str:
    """Substitute palette tokens into the stylesheet template."""
    tokens = asdict(palette_)
    qss = _QSS
    # Longer names first so @accent_soft is not clobbered by @accent.
    for key in sorted(tokens, key=len, reverse=True):
        qss = qss.replace("@" + key, str(tokens[key]))
    qss = qss.replace("@font_stack", FONT_STACK).replace("@mono_stack", MONO_STACK)
    return qss


def apply_theme(app, name: str = "dark") -> Palette:
    """Apply a palette to a ``QApplication`` and return it."""
    chosen = palette(name)
    font = app.font()
    font.setPointSize(10 if chosen.name == "dark" else 10)
    app.setFont(font)
    app.setStyleSheet(build_qss(chosen))
    return chosen


__all__ = [
    "DARK",
    "FONT_STACK",
    "LIGHT",
    "MONO_STACK",
    "PALETTES",
    "Palette",
    "apply_theme",
    "build_qss",
    "palette",
]
