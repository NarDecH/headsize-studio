"""HeadSize Studio image engine (NumPy + OpenCV only, no Qt)."""

from headsize.core.detector import FaceDetector, ModelUnavailableError
from headsize.core.geometry import estimate_head_region
from headsize.core.io import ImageData, load_image, save_image, supported_extensions
from headsize.core.pipeline import render_regions
from headsize.core.types import FaceDetection, HeadRegion
from headsize.core.warp import apply_head_regions

__all__ = [
    "FaceDetection",
    "FaceDetector",
    "HeadRegion",
    "ImageData",
    "ModelUnavailableError",
    "apply_head_regions",
    "estimate_head_region",
    "load_image",
    "render_regions",
    "save_image",
    "supported_extensions",
]
