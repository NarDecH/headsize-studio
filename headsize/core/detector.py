"""Face detection on top of OpenCV's YuNet DNN detector.

OpenCV 5 removed the Haar cascades, so the detector is the ONNX YuNet model
(MIT licensed, ~225 kB) that ships in ``headsize/assets/models``. The module
degrades gracefully: when the model file is missing the UI offers to download
it, and a head region can always be placed by hand.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable, Iterable

import cv2
import numpy as np

from headsize.core.types import FaceDetection

MODEL_FILENAME = "face_detection_yunet_2026may.onnx"
MODEL_SHA256 = "ebafce4e3c118d6554634be5c27ab333b4c047a9a8c3faf1d7cf93101c22f0f0"
MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2026may.onnx"
)
#: Fallback for OpenCV builds that only accept a static input shape.
LEGACY_MODEL_FILENAME = "face_detection_yunet_2023mar.onnx"
LEGACY_MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
LEGACY_MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)

#: Detection input is limited to this many pixels on the long side. YuNet
#: detects faces of roughly 10-300 px, so huge photos are downscaled first.
DEFAULT_MAX_SIDE = 1600

_ENV_OVERRIDE = "HEADSIZE_FACE_MODEL"


class ModelUnavailableError(RuntimeError):
    """Raised when no usable YuNet model file could be located."""


# --------------------------------------------------------------------- paths
def package_asset_dir() -> Path:
    """Directory that holds bundled package assets (PyInstaller aware)."""
    override = os.environ.get("HEADSIZE_ASSETS_DIR")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):  # pragma: no cover - frozen builds only
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidate = base / "headsize" / "assets"
        if candidate.is_dir():
            return candidate
        return base / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


def bundled_model_path() -> Path | None:
    """Path of the shipped model file, if present."""
    path = package_asset_dir() / "models" / MODEL_FILENAME
    return path if path.is_file() else None


def user_model_dir() -> Path:
    """Per-user cache for a downloaded model (used when assets are missing)."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "HeadSizeStudio" / "models"


def user_model_path() -> Path:
    return user_model_dir() / MODEL_FILENAME


def resolve_model_path() -> Path | None:
    """First usable model path, or ``None``."""
    override = os.environ.get(_ENV_OVERRIDE)
    if override:
        path = Path(override)
        if path.is_file():
            return path
    for candidate in (bundled_model_path(), user_model_path()):
        if candidate is not None and candidate.is_file():
            return candidate
    return None


def model_is_available() -> bool:
    return resolve_model_path() is not None


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def download_model(
    destination: str | Path | None = None,
    *,
    url: str = MODEL_URL,
    sha256: str = MODEL_SHA256,
    progress: Callable[[int, int], None] | None = None,
    timeout: float = 60.0,
) -> Path:
    """Download and verify the YuNet model. Returns the written path."""
    target = Path(destination) if destination else user_model_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "HeadSizeStudio"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        fd, tmp_name = tempfile.mkstemp(suffix=".part", dir=str(target.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
            digest = sha256_file(tmp_name)
            if sha256 and digest != sha256:
                raise ModelUnavailableError(
                    f"Model checksum mismatch: expected {sha256}, got {digest}"
                )
            os.replace(tmp_name, target)
        except BaseException:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise
    return target


# ------------------------------------------------------------------- detector
class FaceDetector:
    """Thin, reusable wrapper around :class:`cv2.FaceDetectorYN`."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        *,
        score_threshold: float = 0.6,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
        max_side: int = DEFAULT_MAX_SIDE,
        allow_legacy: bool = True,
    ) -> None:
        self.score_threshold = float(score_threshold)
        self.nms_threshold = float(nms_threshold)
        self.top_k = int(top_k)
        self.max_side = int(max_side)
        self._allow_legacy = allow_legacy
        self._model_path = Path(model_path) if model_path else None
        self._net = None
        self._input_size: tuple[int, int] | None = None

    # -- lifecycle ---------------------------------------------------------
    @property
    def model_path(self) -> Path:
        if self._model_path is None:
            resolved = resolve_model_path()
            if resolved is None:
                raise ModelUnavailableError(
                    "Face detection model not found. Download it or place a head "
                    "region manually."
                )
            self._model_path = resolved
        return self._model_path

    @property
    def loaded(self) -> bool:
        return self._net is not None

    def load(self):
        """Create the underlying network (idempotent). Raises on failure."""
        if self._net is not None:
            return self._net
        path = self.model_path
        try:
            self._net = cv2.FaceDetectorYN_create(
                str(path),
                "",
                (320, 320),
                self.score_threshold,
                self.nms_threshold,
                self.top_k,
            )
        except Exception as exc:  # pragma: no cover - depends on OpenCV build
            legacy = package_asset_dir() / "models" / LEGACY_MODEL_FILENAME
            if self._allow_legacy and legacy.is_file() and legacy != path:
                self._net = cv2.FaceDetectorYN_create(
                    str(legacy),
                    "",
                    (320, 320),
                    self.score_threshold,
                    self.nms_threshold,
                    self.top_k,
                )
                self._model_path = legacy
            else:
                raise ModelUnavailableError(str(exc)) from exc
        return self._net

    def warmup(self) -> None:
        """Run one dummy inference so the first real detection is fast."""
        try:
            self.load().setInputSize((64, 64))
            self.load().detect(np.zeros((64, 64, 3), dtype=np.uint8))
            self._input_size = (64, 64)
        except Exception:  # pragma: no cover - warmup must never break startup
            pass

    # -- detection ---------------------------------------------------------
    def detect(
        self,
        image: np.ndarray,
        *,
        rgb: bool = True,
        max_side: int | None = None,
    ) -> list[FaceDetection]:
        """Detect faces; returns them sorted by descending box area."""
        if image is None or image.size == 0:
            return []
        if image.ndim == 2:
            frame = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.shape[2] == 4:
            frame = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
        else:
            frame = cv2.cvtColor(image, cv2.COLOR_RGB2BGR) if rgb else image

        limit = int(max_side if max_side is not None else self.max_side)
        height, width = frame.shape[:2]
        scale = 1.0
        if limit > 0 and max(height, width) > limit:
            scale = limit / float(max(height, width))
            frame = cv2.resize(
                frame,
                (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
                interpolation=cv2.INTER_AREA,
            )

        net = self.load()
        h, w = frame.shape[:2]
        if self._input_size != (w, h):
            net.setInputSize((w, h))
            self._input_size = (w, h)
        _, raw = net.detect(frame)
        if raw is None:
            return []

        inv = 1.0 / scale if scale != 1.0 else 1.0
        faces: list[FaceDetection] = []
        for row in np.asarray(raw).reshape(-1, 15):
            x, y, bw, bh = (float(row[i]) * inv for i in range(4))
            landmarks = tuple(
                (float(row[i]) * inv, float(row[i + 1]) * inv)
                for i in range(4, 14, 2)
            )
            faces.append(
                FaceDetection(
                    x=x,
                    y=y,
                    w=bw,
                    h=bh,
                    score=float(row[14]),
                    landmarks=landmarks,
                )
            )
        faces.sort(key=lambda f: f.w * f.h, reverse=True)
        return faces

    def detect_regions(self, image: np.ndarray, **kwargs):
        """Detect faces and convert them straight to head regions."""
        from headsize.core.geometry import estimate_head_region

        return [estimate_head_region(face) for face in self.detect(image, **kwargs)]


def detect_faces(image: np.ndarray, **kwargs) -> list[FaceDetection]:
    """One-shot helper that owns a throwaway detector."""
    return FaceDetector().detect(image, **kwargs)


def dedupe_detections(
    detections: Iterable[FaceDetection], iou_threshold: float = 0.5
) -> list[FaceDetection]:
    """Drop detections that overlap a higher scored one (safety net)."""
    ordered = sorted(detections, key=lambda d: d.score, reverse=True)
    kept: list[FaceDetection] = []
    for candidate in ordered:
        if any(_iou(candidate, other) > iou_threshold for other in kept):
            continue
        kept.append(candidate)
    return kept


def _iou(a: FaceDetection, b: FaceDetection) -> float:
    ax0, ay0, ax1, ay1 = a.x, a.y, a.x + a.w, a.y + a.h
    bx0, by0, bx1, by1 = b.x, b.y, b.x + b.w, b.y + b.h
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


__all__ = [
    "FaceDetector",
    "LEGACY_MODEL_FILENAME",
    "LEGACY_MODEL_URL",
    "MODEL_FILENAME",
    "MODEL_SHA256",
    "MODEL_URL",
    "ModelUnavailableError",
    "bundled_model_path",
    "dedupe_detections",
    "detect_faces",
    "download_model",
    "model_is_available",
    "resolve_model_path",
    "sha256_file",
    "user_model_path",
]
