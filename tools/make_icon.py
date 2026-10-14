"""Generate the application icon (PNG + multi-size ICO) from the SVG mark.

Run:  python tools/make_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QByteArray, Qt  # noqa: E402
from PyQt6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PyQt6.QtSvg import QSvgRenderer  # noqa: E402

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#4f6bff"/>
      <stop offset="1" stop-color="#8f5cff"/>
    </linearGradient>
    <linearGradient id="face" x1="0.2" y1="0" x2="0.8" y2="1">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="1" stop-color="#d9e2ff"/>
    </linearGradient>
  </defs>
  <rect x="8" y="8" width="240" height="240" rx="58" fill="url(#bg)"/>
  <path d="M96 196c0-22 14-36 32-36s32 14 32 36z" fill="url(#face)" opacity="0.92"/>
  <ellipse cx="128" cy="112" rx="46" ry="54" fill="url(#face)"/>
  <path d="M82 104c0-30 20-48 46-48s46 18 46 48c0-8-8-20-20-24-12 8-30 10-44 6-14-4-24-10-28-18-6 8-8 20-8 36z" fill="#1b2340" opacity="0.85"/>
  <circle cx="111" cy="112" r="6" fill="#1b2340"/>
  <circle cx="145" cy="112" r="6" fill="#1b2340"/>
  <path d="M116 140c8 6 16 6 24 0" stroke="#1b2340" stroke-width="5" fill="none" stroke-linecap="round"/>
  <path d="M40 52V36h16M200 52V36h16M40 204v16h16M200 204v16h16" stroke="#ffffff" stroke-width="9" fill="none" stroke-linecap="round" opacity="0.85"/>
</svg>
"""


def render(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(ICON_SVG.encode("utf-8")))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return image


def main() -> int:
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841
    out_dir = ROOT / "headsize" / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    png = out_dir / "headsize.png"
    render(512).save(str(png), "PNG")

    from PIL import Image

    source = Image.open(png).convert("RGBA")
    ico = out_dir / "headsize.ico"
    source.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"wrote {png} and {ico}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
