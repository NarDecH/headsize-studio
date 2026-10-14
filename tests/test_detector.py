"""Face detector: model resolution, graceful degradation, download path."""

from __future__ import annotations

import numpy as np
import pytest

from headsize.core import detector as detector_module
from headsize.core.detector import (
    MODEL_SHA256,
    FaceDetector,
    ModelUnavailableError,
    dedupe_detections,
    download_model,
    model_is_available,
    resolve_model_path,
    sha256_file,
)
from headsize.core.types import FaceDetection


def test_bundled_model_is_present_and_intact() -> None:
    path = detector_module.bundled_model_path()
    assert path is not None, "the YuNet model must ship with the app"
    assert path.stat().st_size > 100_000
    assert sha256_file(path) == MODEL_SHA256


def test_model_is_available() -> None:
    assert model_is_available() is True
    assert resolve_model_path() is not None


def test_missing_model_raises_a_helpful_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HEADSIZE_FACE_MODEL", str(tmp_path / "missing.onnx"))
    monkeypatch.setattr(detector_module, "bundled_model_path", lambda: None)
    monkeypatch.setattr(
        detector_module, "user_model_path", lambda: tmp_path / "also-missing.onnx"
    )
    assert resolve_model_path() is None
    with pytest.raises(ModelUnavailableError) as info:
        FaceDetector().load()
    assert "not found" in str(info.value).lower()


def test_detect_returns_detection_objects(portrait_image) -> None:
    faces = FaceDetector().detect(portrait_image)
    assert isinstance(faces, list)  # a cartoon face may or may not be found
    for face in faces:
        assert isinstance(face, FaceDetection)
        assert face.w > 0 and face.h > 0
        assert len(face.landmarks) == 5


def test_detect_accepts_bgr_and_grayscale(portrait_image) -> None:
    import cv2

    bgr = cv2.cvtColor(portrait_image, cv2.COLOR_RGB2BGR)
    assert isinstance(FaceDetector().detect(bgr, rgb=False), list)
    gray = cv2.cvtColor(portrait_image, cv2.COLOR_RGB2GRAY)
    assert isinstance(FaceDetector().detect(gray), list)


def test_tiny_and_empty_images_are_safe() -> None:
    assert FaceDetector().detect(np.zeros((4, 4, 3), np.uint8)) == []
    assert FaceDetector().detect(np.zeros((0, 0, 3), np.uint8)) == []


def test_detect_scales_coordinates_back_to_full_size(portrait_image) -> None:
    import cv2

    big = cv2.resize(portrait_image, (2400, 3200), interpolation=cv2.INTER_CUBIC)
    faces = FaceDetector(max_side=800).detect(big)
    for face in faces:
        assert face.x + face.w <= big.shape[1] + 1
        assert face.y + face.h <= big.shape[0] + 1


def test_detect_regions_uses_head_geometry(portrait_image) -> None:
    regions = FaceDetector().detect_regions(portrait_image)
    for region in regions:
        assert region.origin == "auto"
        assert region.ry > region.rx
        assert region.scale == 1.0


def test_iou_dedupe_keeps_the_best_box() -> None:
    strong = FaceDetection(x=10, y=10, w=100, h=100, score=0.9)
    weak = FaceDetection(x=12, y=12, w=100, h=100, score=0.4)
    far = FaceDetection(x=400, y=400, w=100, h=100, score=0.8)
    kept = dedupe_detections([weak, strong, far])
    assert len(kept) == 2
    assert kept[0] is strong


def test_download_model_verifies_checksum(tmp_path, monkeypatch) -> None:
    """The download path works offline against a file:// URL."""
    source = detector_module.bundled_model_path()
    assert source is not None
    target = tmp_path / "downloaded.onnx"
    result = download_model(
        target,
        url=source.resolve().as_uri(),
        sha256=MODEL_SHA256,
    )
    assert result == target
    assert sha256_file(target) == MODEL_SHA256


def test_download_model_rejects_a_bad_checksum(tmp_path) -> None:
    source = detector_module.bundled_model_path()
    assert source is not None
    with pytest.raises(ModelUnavailableError):
        download_model(
            tmp_path / "bad.onnx",
            url=source.resolve().as_uri(),
            sha256="0" * 64,
        )
    assert not (tmp_path / "bad.onnx").exists()
    assert list(tmp_path.glob("*.part")) == []


@pytest.mark.integration
def test_real_photo_detects_exactly_one_face(real_photo) -> None:
    faces = FaceDetector().detect(real_photo)
    assert faces, "expected at least one face in the reference photo"
    assert faces[0].score > 0.6
    assert len(faces[0].landmarks) == 5


@pytest.mark.integration
def test_real_photo_head_really_grows(real_photo) -> None:
    """End-to-end on a photograph: detect, warp, re-detect and measure.

    The measured growth is slightly below the requested factor because the face
    box reaches into the blending band — that relationship is documented in
    docs/research.md and is why the default feather is 0.35.
    """
    from headsize.core.geometry import estimate_head_region
    from headsize.core.types import DEFAULT_FEATHER
    from headsize.core.warp import apply_head_regions

    detector = FaceDetector()
    before = detector.detect(real_photo)[0]
    region = estimate_head_region(before, feather=DEFAULT_FEATHER)

    bigger = apply_head_regions(real_photo, [region.copy(scale=1.30)])
    after = detector.detect(bigger)[0]
    assert after.w / before.w > 1.15
    assert after.h / before.h > 1.15
    assert after.w / before.w < 1.45  # not overshooting either

    smaller = apply_head_regions(real_photo, [region.copy(scale=0.80)])
    shrunk = detector.detect(smaller)[0]
    assert shrunk.w / before.w < 0.90
