"""Inline SVG icons.

Keeping the icons as SVG strings means no binary assets to ship, no Qt resource
compilation, and instant recolouring per theme. ``{c}`` is the stroke colour.
"""

from __future__ import annotations

from functools import lru_cache

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

_SVG = {
    "open": '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h3l2 2.5h6.5A2.5 2.5 0 0 1 19.5 10v6.5'
    'A2.5 2.5 0 0 1 17 19H5.5A2.5 2.5 0 0 1 3 16.5z"/>',
    "save": '<path d="M5 4h11l3 3v13H5z"/><path d="M9 4v5h6V4"/><path d="M8 20v-6h8v6"/>',
    "undo": '<path d="M9 7H15a5 5 0 0 1 0 10H8"/><path d="M12 4 9 7l3 3"/>',
    "redo": '<path d="M15 7H9a5 5 0 0 0 0 10h7"/><path d="M12 4l3 3-3 3"/>',
    "reset": '<path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v5h-5"/>',
    "scan": '<path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8"/><path d="M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8"/>'
    '<path d="M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16"/><path d="M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16"/>'
    '<circle cx="12" cy="11" r="3.2"/><path d="M8.6 16.6c.9-1.4 2-2.1 3.4-2.1s2.5.7 3.4 2.1"/>',
    "plus": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "trash": '<path d="M5 7h14"/><path d="M10 7V5h4v2"/><path d="M6.5 7l.8 12h9.4l.8-12"/>'
    '<path d="M10.5 11v5"/><path d="M13.5 11v5"/>',
    "zoom_in": '<circle cx="11" cy="11" r="6"/><path d="M15.5 15.5 20 20"/><path d="M11 8.8v4.4"/><path d="M8.8 11h4.4"/>',
    "zoom_out": '<circle cx="11" cy="11" r="6"/><path d="M15.5 15.5 20 20"/><path d="M8.8 11h4.4"/>',
    "fit": '<path d="M4 9V5h4"/><path d="M20 9V5h-4"/><path d="M4 15v4h4"/><path d="M20 15v4h-4"/>'
    '<rect x="9" y="9" width="6" height="6" rx="1"/>',
    "actual": '<rect x="4" y="6" width="16" height="12" rx="2"/><path d="M8 12h2"/><path d="M14 12h2"/>',
    "compare": '<rect x="4" y="5" width="7" height="14" rx="1.6"/><rect x="13" y="5" width="7" height="14" rx="1.6"/>'
    '<path d="M12 3v18"/>',
    "eye": '<path d="M2.5 12S6 6.5 12 6.5 21.5 12 21.5 12S18 17.5 12 17.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    "eye_off": '<path d="M4 4l16 16"/><path d="M9.5 5.9A9.5 9.5 0 0 1 12 6.5c6 0 9.5 5.5 9.5 5.5a17 17 0 0 1-3.4 3.9"/>'
    '<path d="M6.4 8.1A16.6 16.6 0 0 0 2.5 12S6 17.5 12 17.5c1 0 1.9-.2 2.7-.4"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2.5"/><path d="M12 19.5V22"/><path d="M2 12h2.5"/>'
    '<path d="M19.5 12H22"/><path d="M4.9 4.9l1.8 1.8"/><path d="M17.3 17.3l1.8 1.8"/>'
    '<path d="M4.9 19.1l1.8-1.8"/><path d="M17.3 6.7l1.8-1.8"/>',
    "moon": '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-13.7-4.3"/><path d="M4 13a8 8 0 0 0 13.7 4.3"/>'
    '<path d="M4 5v5h5"/><path d="M20 19v-5h-5"/>',
    "download": '<path d="M12 4v11"/><path d="M7.5 10.5 12 15l4.5-4.5"/><path d="M5 19h14"/>',
    "help": '<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.4a2.5 2.5 0 1 1 3.3 2.4c-.6.3-.9.7-.9 1.4v.4"/>'
    '<path d="M12 17.2h.01"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v6"/><path d="M12 7.6h.01"/>',
    "settings": '<circle cx="12" cy="12" r="3"/>'
    '<path d="M12 3v2.2"/><path d="M12 18.8V21"/><path d="M3 12h2.2"/><path d="M18.8 12H21"/>'
    '<path d="M5.6 5.6l1.6 1.6"/><path d="M16.8 16.8l1.6 1.6"/><path d="M5.6 18.4l1.6-1.6"/><path d="M16.8 7.2l1.6-1.6"/>',
    "external": '<path d="M14 5h5v5"/><path d="M19 5l-7 7"/><path d="M17 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h4"/>',
    "check": '<path d="M5 12.5 10 17.5 19 7"/>',
    "alert": '<path d="M12 4.5 21 19.5H3z"/><path d="M12 10v4.2"/><path d="M12 17.2h.01"/>',
    "close": '<path d="M6 6l12 12"/><path d="M18 6 6 18"/>',
    "chevron_down": '<path d="M6 9.5 12 15.5 18 9.5"/>',
    "move": '<path d="M12 3v18"/><path d="M3 12h18"/><path d="M12 3 9.5 5.5"/><path d="M12 3l2.5 2.5"/>'
    '<path d="M12 21l-2.5-2.5"/><path d="M12 21l2.5-2.5"/><path d="M3 12l2.5-2.5"/><path d="M3 12l2.5 2.5"/>'
    '<path d="M21 12l-2.5-2.5"/><path d="M21 12l-2.5 2.5"/>',
    "rotate": '<path d="M19.5 12a7.5 7.5 0 1 1-2.6-5.7"/><path d="M19.5 4.5V9H15"/><circle cx="12" cy="12" r="1.6"/>',
    "wand": '<path d="M6 18 18 6"/><path d="M15 4.5 15.8 6l1.7.8-1.7.8L15 9l-.8-1.4L12.5 6.8l1.7-.8z"/>'
    '<path d="M6.5 5.5 7 6.6l1.1.5-1.1.5-.5 1.1-.5-1.1L5 7.1l1.1-.5z"/><path d="M4.5 14.5l.5 1.1 1.1.5-1.1.5-.5 1.1-.5-1.1-1.1-.5 1.1-.5z"/>',
    "target": '<circle cx="12" cy="12" r="7.5"/><circle cx="12" cy="12" r="2.5"/>'
    '<path d="M12 2.5V5"/><path d="M12 19v2.5"/><path d="M2.5 12H5"/><path d="M19 12h2.5"/>',
    "layers": '<path d="M12 3 20 7.5 12 12 4 7.5z"/><path d="M4 12.5 12 17l8-4.5"/><path d="M4 17 12 21.5 20 17"/>',
    "copy": '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M15 6.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h.5"/>',
    "grid": '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/>'
    '<rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
}

_HEADER = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" ' \
          'stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'

#: Icons that read better filled (used for the small centre dot of the target).
_EMPTY = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"/>'


def svg_markup(name: str, color: str) -> str:
    body = _SVG.get(name, "")
    return _HEADER.format(c=color, body=body)


def available_icons() -> tuple[str, ...]:
    return tuple(sorted(_SVG))


@lru_cache(maxsize=256)
def _render(name: str, color: str, size: int, ratio: float) -> QPixmap:
    pixels = max(1, int(round(size * ratio)))
    pixmap = QPixmap(pixels, pixels)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(svg_markup(name, color).encode("utf-8")))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def pixmap(name: str, color: str = "#e9eefb", size: int = 20, ratio: float = 2.0) -> QPixmap:
    return _render(name, color, size, ratio)


def icon(name: str, color: str = "#e9eefb", size: int = 20) -> QIcon:
    return QIcon(pixmap(name, color, size))


__all__ = ["available_icons", "icon", "pixmap", "svg_markup"]
