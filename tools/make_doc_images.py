"""Generate every image used by the documentation.

Run:  python tools/make_doc_images.py

Produces, in ``docs/assets``:

* ``hero-before-after.png``  three-panel demo (smaller / original / bigger)
* ``detail-before.png`` / ``detail-after.png``  2x crop of the head region
* ``shot-main-dark.png`` / ``shot-main-light.png``  offscreen UI screenshots
* ``shot-controls.png``  the sidebar alone
* ``portrait-source.png``  the procedural source illustration
* ``benchmark.png``  the timing chart

Everything is generated so the repository ships no third-party photograph.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

from headsize.core.io import save_image  # noqa: E402
from headsize.core.types import DEFAULT_FEATHER, HeadRegion  # noqa: E402
from headsize.core.warp import apply_head_regions  # noqa: E402

ASSETS = ROOT / "docs" / "assets"

# The illustration is drawn from a fixed layout, so its head geometry is known
# exactly and can be handed to the engine without running a detector.
PORTRAIT_SIZE = (760, 980)
HEAD_CENTRE = (380.0, 372.0)
HEAD_RADII = (152.0, 190.0)
# The influence zone is deliberately ~1.3x the drawn head, exactly like the
# automatic region a detector would produce (hair and margin included).
ZONE_RADII = (236.0, 292.0)
ZONE_FEATHER = 0.22


# --------------------------------------------------------------------- drawing
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in ("segoeuib.ttf", "segoeui.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_portrait() -> Image.Image:
    """A studio-style illustrated portrait (procedural, no photo licences)."""
    width, height = PORTRAIT_SIZE

    # backdrop: vertical gradient plus a soft floor shadow
    backdrop = Image.new("RGB", (width, height), (38, 46, 74))
    draw = ImageDraw.Draw(backdrop)
    for y in range(height):
        t = y / height
        colour = (
            int(40 + 46 * t),
            int(50 + 44 * t),
            int(84 + 40 * t),
        )
        draw.line([(0, y), (width, y)], fill=colour)
    glow = Image.new("L", (width, height), 0)
    ImageDraw.Draw(glow).ellipse([40, -160, width - 40, 620], fill=90)
    backdrop = Image.composite(Image.new("RGB", (width, height), (96, 116, 178)), backdrop, glow.filter(ImageFilter.GaussianBlur(120)))

    layer = backdrop.convert("RGBA")
    draw = ImageDraw.Draw(layer, "RGBA")

    cx, cy = HEAD_CENTRE
    hx, hy = HEAD_RADII

    # shoulders / torso
    draw.rounded_rectangle(
        [cx - 300, cy + 250, cx + 300, height + 120],
        radius=170,
        fill=(28, 34, 58, 255),
    )
    # neck
    draw.rounded_rectangle(
        [cx - 52, cy + 90, cx + 52, cy + 300], radius=40, fill=(198, 152, 126, 255)
    )
    neck_shade = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(neck_shade).ellipse(
        [cx - 70, cy + 60, cx + 70, cy + 220], fill=(150, 100, 84, 120)
    )
    layer = Image.alpha_composite(layer, neck_shade)
    draw = ImageDraw.Draw(layer, "RGBA")

    # ears
    draw.ellipse([cx - hx - 14, cy - 24, cx - hx + 22, cy + 60], fill=(206, 160, 134, 255))
    draw.ellipse([cx + hx - 22, cy - 24, cx + hx + 14, cy + 60], fill=(206, 160, 134, 255))

    # head + hair mass
    draw.ellipse(
        [cx - hx - 16, cy - hy - 26, cx + hx + 16, cy + hy + 18],
        fill=(56, 40, 36, 255),
    )
    draw.ellipse([cx - hx, cy - hy, cx + hx, cy + hy], fill=(224, 176, 148, 255))

    # cheek shading and highlights
    shade = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shade, "RGBA")
    sdraw.ellipse([cx + 40, cy - 70, cx + hx + 20, cy + 120], fill=(176, 116, 96, 90))
    sdraw.ellipse([cx - hx - 10, cy - 90, cx - 30, cy + 90], fill=(255, 236, 220, 70))
    sdraw.ellipse([cx - 110, cy + 30, cx - 40, cy + 90], fill=(214, 122, 122, 60))
    sdraw.ellipse([cx + 40, cy + 30, cx + 110, cy + 90], fill=(214, 122, 122, 60))
    layer = Image.alpha_composite(layer, shade.filter(ImageFilter.GaussianBlur(26)))
    draw = ImageDraw.Draw(layer, "RGBA")

    # hair on top of the skull
    draw.pieslice(
        [cx - hx - 18, cy - hy - 30, cx + hx + 18, cy + hy - 40],
        start=178,
        end=362,
        fill=(46, 32, 30, 255),
    )
    draw.ellipse([cx - hx + 20, cy - hy - 4, cx + hx - 20, cy - hy + 74], fill=(40, 28, 26, 255))

    # brows, eyes, nose, mouth
    draw.rounded_rectangle([cx - 78, cy - 32, cx - 26, cy - 22], radius=6, fill=(58, 42, 38, 255))
    draw.rounded_rectangle([cx + 26, cy - 32, cx + 78, cy - 22], radius=6, fill=(58, 42, 38, 255))
    for sx in (-50, 50):
        draw.ellipse([cx + sx - 27, cy - 12, cx + sx + 27, cy + 26], fill=(252, 250, 250, 255))
        draw.ellipse([cx + sx - 15, cy - 6, cx + sx + 15, cy + 22], fill=(74, 116, 96, 255))
        draw.ellipse([cx + sx - 8, cy - 1, cx + sx + 8, cy + 16], fill=(22, 20, 22, 255))
        draw.ellipse([cx + sx - 12, cy - 4, cx + sx - 3, cy + 5], fill=(255, 255, 255, 220))
        draw.arc([cx + sx - 29, cy - 16, cx + sx + 29, cy + 30], start=200, end=340, fill=(50, 36, 32, 255), width=5)

    nose = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ndraw = ImageDraw.Draw(nose, "RGBA")
    ndraw.ellipse([cx - 22, cy + 34, cx + 22, cy + 76], fill=(176, 118, 96, 110))
    ndraw.ellipse([cx - 20, cy + 62, cx + 20, cy + 80], fill=(150, 92, 78, 120))
    layer = Image.alpha_composite(layer, nose.filter(ImageFilter.GaussianBlur(9)))
    draw = ImageDraw.Draw(layer, "RGBA")

    draw.ellipse([cx - 52, cy + 100, cx + 52, cy + 132], fill=(176, 74, 84, 235))
    draw.line([(cx - 50, cy + 116), (cx + 50, cy + 116)], fill=(140, 52, 62, 200), width=3)
    draw.arc([cx - 40, cy + 96, cx + 40, cy + 140], start=20, end=160, fill=(130, 46, 56, 200), width=3)

    # a soft shadow behind the head to lift it off the backdrop
    shadow = Image.new("L", (width, height), 0)
    ImageDraw.Draw(shadow).ellipse(
        [cx - hx - 60, cy - hy - 40, cx + hx + 60, cy + hy + 120], fill=120
    )
    backdrop = Image.composite(
        Image.new("RGB", (width, height), (18, 22, 40)),
        backdrop,
        shadow.filter(ImageFilter.GaussianBlur(60)),
    )
    return Image.alpha_composite(backdrop.convert("RGBA"), layer).convert("RGB")


# ------------------------------------------------------------------ compositing
def _label(image: Image.Image, text: str, colour: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    band = Image.new("RGB", (image.width, 54), (16, 19, 30))
    draw = ImageDraw.Draw(band)
    font = _font(24)
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(
        ((image.width - (box[2] - box[0])) / 2, 14), text, font=font, fill=colour
    )
    combined = Image.new("RGB", (image.width, image.height + band.height), (16, 19, 30))
    combined.paste(band, (0, 0))
    combined.paste(image, (0, band.height))
    return combined


def _rounded(image: Image.Image, radius: int = 18) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, image.width, image.height], radius=radius, fill=255)
    out = image.convert("RGBA")
    out.putalpha(mask)
    return out


def head_region(scale: float, feather: float = ZONE_FEATHER) -> HeadRegion:
    return HeadRegion(
        cx=HEAD_CENTRE[0],
        cy=HEAD_CENTRE[1],
        rx=ZONE_RADII[0],
        ry=ZONE_RADII[1],
        scale=scale,
        feather=feather,
    )


def write_hero(portrait: Image.Image) -> None:
    array = np.asarray(portrait)
    panels = []
    for scale, label in ((0.78, "smaller  0.78x"), (1.0, "original  1.00x"), (1.36, "bigger  1.36x")):
        rendered = portrait if scale == 1.0 else Image.fromarray(
            apply_head_regions(array, [head_region(scale)])
        )
        crop = rendered.crop((60, 60, 700, 900)).resize((420, 550), Image.LANCZOS)
        panels.append(_label(crop, label, (200, 214, 255) if scale != 1.0 else (255, 255, 255)))

    gap = 18
    total_w = sum(p.width for p in panels) + gap * (len(panels) + 1)
    height = max(p.height for p in panels) + gap * 2
    canvas = Image.new("RGB", (total_w, height), (10, 12, 20))
    x = gap
    for panel in panels:
        canvas.paste(panel, (x, gap))
        x += panel.width + gap
    canvas.save(ASSETS / "hero-before-after.png", optimize=True)

    # zoomed detail pair
    detail_box = (170, 120, 600, 620)
    before = portrait.crop(detail_box).resize((516, 600), Image.LANCZOS)
    after = Image.fromarray(
        apply_head_regions(array, [head_region(1.36)])
    ).crop(detail_box).resize((516, 600), Image.LANCZOS)
    _label(before, "original 1.00x").save(ASSETS / "detail-before.png", optimize=True)
    _label(after, "warped 1.36x").save(ASSETS / "detail-after.png", optimize=True)


def write_benchmark() -> None:
    """Measure warp timings so the research doc quotes real numbers."""
    from headsize.core.warp import apply_head_regions as warp

    rows = []
    for label, (width, height) in (
        ("1 MP", (1200, 830)),
        ("4 MP", (2000, 1500)),
        ("12 MP", (4000, 3000)),
        ("24 MP", (6000, 4000)),
    ):
        rng = np.random.default_rng(7)
        image = rng.integers(40, 210, (height, width, 3), dtype=np.uint8)
        region = HeadRegion(
            cx=width * 0.5, cy=height * 0.35, rx=width * 0.11, ry=height * 0.16, scale=1.3
        )
        timings = {}
        for quality in ("fast", "high"):
            start = time.perf_counter()
            warp(image, [region], quality=quality)
            timings[quality] = (time.perf_counter() - start) * 1000
        rows.append({"size": label, "pixels": width * height, **{k: round(v, 1) for k, v in timings.items()}})

    (ASSETS / "benchmark.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

    # simple bar chart
    width, height = 720, 340
    chart = Image.new("RGB", (width, height), (16, 19, 30))
    draw = ImageDraw.Draw(chart)
    font = _font(18)
    small = _font(15)
    max_ms = max(r["high"] for r in rows) * 1.15
    bar_w = 70
    for index, row in enumerate(rows):
        x = 90 + index * 150
        for offset, key, colour in ((0, "fast", (108, 140, 255)), (bar_w + 12, "high", (69, 215, 176))):
            h = int(row[key] / max_ms * 230)
            draw.rounded_rectangle(
                [x + offset, 280 - h, x + offset + bar_w, 280], radius=8, fill=colour
            )
            draw.text((x + offset + 6, 286 - h - 22), f"{row[key]:.0f} ms", font=small, fill=(220, 228, 255))
        draw.text((x + 34, 292), row["size"], font=font, fill=(200, 210, 240))
    draw.text((24, 24), "Head warp time (one head, high vs fast resampling)", font=font, fill=(232, 238, 255))
    draw.rectangle([90, 280, width - 40, 281], fill=(60, 70, 96))
    chart.save(ASSETS / "benchmark.png", optimize=True)
    print("benchmark:", rows)


# ---------------------------------------------------------------------- UI shots
def write_screenshots(portrait: Image.Image) -> None:
    from PyQt6.QtWidgets import QApplication

    from headsize.core.config import AppConfig
    from headsize.core.io import load_image
    from headsize.ui.i18n import set_language
    from headsize.ui.main_window import MainWindow
    from headsize.ui.theme import apply_theme

    app = QApplication.instance() or QApplication([])
    portrait_path = ASSETS / "portrait-source.png"
    portrait.save(portrait_path, optimize=True)

    config = AppConfig(check_updates_on_start=False, auto_detect_on_open=False)
    config.theme = "dark"
    config.language = "th"
    apply_theme(app, config.theme)
    set_language(config.language)
    window = MainWindow(config)
    window.resize(1440, 920)
    window.open_path(str(portrait_path))
    window.add_head_centred()
    index = window.doc.selected
    window.doc.apply_live(
        index,
        cx=HEAD_CENTRE[0],
        cy=HEAD_CENTRE[1],
        rx=ZONE_RADII[0],
        ry=ZONE_RADII[1],
        feather=ZONE_FEATHER,
    )
    window._on_scale_changed(1.36, True)
    window.canvas.fit_to_window()
    window.show()
    QApplication.processEvents()
    window.grab().save(str(ASSETS / "shot-main-dark.png"), "PNG")
    window.panel.grab().save(str(ASSETS / "shot-controls.png"), "PNG")

    window.set_theme("light")
    window.set_language("en")
    window._on_compare_changed("split")
    window.canvas.set_split(0.5)
    QApplication.processEvents()
    window.grab().save(str(ASSETS / "shot-main-light.png"), "PNG")

    window.doc.dirty = False
    window.close()
    _ = load_image
    print("screenshots written")


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    portrait = make_portrait()
    write_hero(portrait)
    write_benchmark()
    write_screenshots(portrait)
    for path in sorted(ASSETS.glob("*.png")):
        print(f"{path.name:28s} {path.stat().st_size / 1024:8.1f} KiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
