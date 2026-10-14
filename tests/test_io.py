"""Image IO: formats, metadata and EXIF orientation."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from headsize.core.io import load_image, save_image


def test_round_trip_png(tmp_path, portrait_image) -> None:
    target = tmp_path / "out.png"
    save_image(portrait_image, target)
    loaded = load_image(target)
    assert loaded.size == (portrait_image.shape[1], portrait_image.shape[0])
    assert np.array_equal(loaded.array, portrait_image)
    assert loaded.source_format == "PNG"


def test_round_trip_jpeg_is_close(tmp_path, portrait_image) -> None:
    target = tmp_path / "out.jpg"
    save_image(portrait_image, target, quality=100)
    loaded = load_image(target)
    assert loaded.array.shape == portrait_image.shape
    difference = np.abs(loaded.array.astype(int) - portrait_image.astype(int)).mean()
    assert difference < 4.0


def test_save_respects_extension(tmp_path, portrait_image) -> None:
    webp = save_image(portrait_image, tmp_path / "a.webp", quality=90)
    assert webp.suffix == ".webp"
    with Image.open(webp) as handle:
        assert handle.format == "WEBP"
    tiff = save_image(portrait_image, tmp_path / "a.tiff")
    with Image.open(tiff) as handle:
        assert handle.format == "TIFF"


def test_rgba_and_grayscale_inputs(tmp_path, portrait_image) -> None:
    rgba = np.dstack([portrait_image, np.full(portrait_image.shape[:2], 255, np.uint8)])
    target = tmp_path / "rgba.png"
    save_image(rgba, target)
    assert load_image(target).array.shape == portrait_image.shape

    gray = np.full((40, 30), 128, np.uint8)
    gray_target = tmp_path / "gray.png"
    save_image(gray, gray_target)
    loaded = load_image(gray_target)
    assert loaded.array.shape == (40, 30, 3)
    assert loaded.array.mean() == pytest.approx(128, abs=1)


def test_sixteen_bit_grayscale_is_normalised(tmp_path) -> None:
    data = np.full((20, 20), 65535, np.uint16)
    target = tmp_path / "deep.png"
    Image.fromarray(data).save(target)
    loaded = load_image(target)
    assert loaded.array.dtype == np.uint8
    assert loaded.array.max() == 255


def test_exif_orientation_is_applied(tmp_path, portrait_image) -> None:
    """A portrait JPEG tagged 'rotate 90' must come back upright."""
    source = tmp_path / "rotated.jpg"
    rotated = np.rot90(portrait_image)
    Image.fromarray(rotated).save(source, exif=_exif_orientation(6))
    loaded = load_image(source)
    assert loaded.array.shape[0] > loaded.array.shape[1]


def _exif_orientation(value: int) -> bytes:
    exif = Image.Exif()
    exif[274] = value  # Orientation tag
    return exif.tobytes()


def test_alpha_input_is_flattened(tmp_path, portrait_image) -> None:
    source = tmp_path / "alpha.png"
    Image.fromarray(portrait_image).convert("RGBA").save(source)
    loaded = load_image(source)
    assert loaded.array.shape[2] == 3
    assert loaded.meta["has_alpha"] is True


def test_dpi_and_icc_survive(tmp_path, portrait_image) -> None:
    target = tmp_path / "meta.jpg"
    save_image(portrait_image, target, dpi=(300.0, 300.0))
    loaded = load_image(target)
    assert loaded.dpi is not None
    assert loaded.dpi[0] == pytest.approx(300.0, abs=1.0)
