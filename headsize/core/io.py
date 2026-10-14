"""Image loading and saving (Pillow keeps EXIF orientation, ICC and DPI)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

#: Extensions offered in the open/save dialogs.
READ_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".jfif",
    ".ppm",
    ".pgm",
)
WRITE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")

_FORMAT_BY_EXT = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".jfif": "JPEG",
    ".webp": "WEBP",
    ".bmp": "BMP",
    ".tif": "TIFF",
    ".tiff": "TIFF",
}


@dataclass
class ImageData:
    """An in-memory RGB image plus the metadata needed to save it faithfully."""

    array: np.ndarray
    path: Path | None = None
    source_format: str | None = None
    icc_profile: bytes | None = None
    dpi: tuple[float, float] | None = None
    exif: bytes | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def height(self) -> int:
        return int(self.array.shape[0])

    @property
    def width(self) -> int:
        return int(self.array.shape[1])

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)

    @property
    def name(self) -> str:
        return self.path.name if self.path else "untitled"


def load_image(path: str | Path) -> ImageData:
    """Load an image as an RGB ``uint8`` array with EXIF rotation applied."""
    source = Path(path)
    with Image.open(source) as handle:
        handle.load()
        info = dict(handle.info)
        source_format = handle.format
        icc = info.get("icc_profile")
        dpi = info.get("dpi")
        exif = info.get("exif")
        frame = ImageOps.exif_transpose(handle)

    array = _to_rgb8(frame)
    meta = {
        "mode": frame.mode,
        "has_alpha": "A" in getattr(handle, "mode", ""),
    }
    return ImageData(
        array=array,
        path=source,
        source_format=source_format,
        icc_profile=icc,
        dpi=(float(dpi[0]), float(dpi[1])) if dpi else None,
        exif=exif,
        meta=meta,
    )


def _to_rgb8(frame: Image.Image) -> np.ndarray:
    """Convert any Pillow mode to a contiguous RGB uint8 array."""
    if frame.mode in ("I;16", "I;16B", "I;16L", "I", "F"):
        # 16/32-bit grayscale or float: normalise to 8-bit.
        raw = np.asarray(frame).astype(np.float64)
        peak = float(np.nanmax(raw)) if raw.size else 1.0
        if peak <= 0:
            peak = 1.0
        scale = 255.0 / peak if peak > 255 else 1.0
        return np.repeat(
            np.clip(raw * scale, 0, 255).astype(np.uint8)[..., None], 3, axis=2
        )
    if frame.mode != "RGB":
        frame = frame.convert("RGB")
    return np.ascontiguousarray(np.asarray(frame)[..., :3], dtype=np.uint8)


def save_image(
    image: np.ndarray,
    path: str | Path,
    *,
    format: str | None = None,
    quality: int = 95,
    icc_profile: bytes | None = None,
    dpi: tuple[float, float] | None = None,
    exif: bytes | None = None,
    png_compress_level: int = 6,
) -> Path:
    """Write an RGB array to ``path``.

    ``quality`` (1-100) applies to the lossy formats (JPEG/WebP). The extension
    wins over ``format`` unless ``format`` is given explicitly.
    """
    target = Path(path)
    fmt = (format or _FORMAT_BY_EXT.get(target.suffix.lower()) or "PNG").upper()
    if fmt == "JPG":
        fmt = "JPEG"

    array = np.asarray(image)
    if array.ndim == 2:
        array = np.repeat(array[..., None], 3, axis=2)
    if array.shape[2] == 4:
        array = array[..., :3]
    array = np.ascontiguousarray(np.clip(array, 0, 255).astype(np.uint8))

    frame = Image.fromarray(array, mode="RGB")
    params: dict[str, Any] = {}
    if icc_profile:
        params["icc_profile"] = icc_profile
    if dpi:
        params["dpi"] = dpi
    if fmt in ("JPEG", "WEBP"):
        params["quality"] = int(max(1, min(100, quality)))
        if fmt == "JPEG":
            params["optimize"] = True
            params["progressive"] = False
            if exif:
                params["exif"] = exif
    elif fmt == "PNG":
        params["compress_level"] = int(max(0, min(9, png_compress_level)))
        params["optimize"] = False

    target.parent.mkdir(parents=True, exist_ok=True)
    frame.save(target, format=fmt, **params)
    return target


def supported_extensions() -> tuple[str, ...]:
    return READ_EXTENSIONS


def open_filter() -> str:
    patterns = " ".join(f"*{ext}" for ext in READ_EXTENSIONS)
    return f"Images ({patterns});;All files (*)"


def save_filter() -> str:
    return (
        "PNG image (*.png);;JPEG image (*.jpg *.jpeg);;WebP image (*.webp);;"
        "BMP image (*.bmp);;TIFF image (*.tif *.tiff)"
    )


__all__ = [
    "ImageData",
    "READ_EXTENSIONS",
    "WRITE_EXTENSIONS",
    "load_image",
    "open_filter",
    "save_filter",
    "save_image",
    "supported_extensions",
]
