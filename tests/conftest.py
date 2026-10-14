"""Shared test fixtures.

The suite is fully self-contained: every test image is generated procedurally so
no third-party photo is redistributed. A real photo can be pointed at with
``HEADSIZE_TEST_IMAGE`` to run the optional detector integration test.
"""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from headsize.core.types import FaceDetection, HeadRegion


@pytest.fixture
def disk_image() -> tuple[np.ndarray, tuple[int, int, int]]:
    """500x500 black image with a white disk of radius 40 at the centre."""
    image = np.zeros((500, 500, 3), dtype=np.uint8)
    cv2.circle(image, (250, 250), 40, (255, 255, 255), -1)
    return image, (250, 250, 40)


@pytest.fixture
def portrait_image() -> np.ndarray:
    """A simple procedural portrait: background, shoulders and a head."""
    height, width = 480, 360
    image = np.full((height, width, 3), 232, dtype=np.uint8)
    # background gradient
    for y in range(height):
        image[y, :, :] = np.array([224 - y // 8, 214 - y // 10, 206 - y // 12], dtype=np.uint8)
    # shoulders
    cv2.ellipse(image, (180, 520), (150, 120), 0, 180, 360, (78, 96, 140), -1)
    # neck
    cv2.rectangle(image, (160, 300), (200, 360), (196, 158, 132), -1)
    # head
    cv2.ellipse(image, (180, 210), (62, 82), 0, 0, 360, (198, 162, 138), -1)
    # hair
    cv2.ellipse(image, (180, 176), (66, 62), 0, 180, 360, (58, 44, 38), -1)
    # eyes, nose, mouth
    cv2.circle(image, (158, 200), 6, (250, 250, 250), -1)
    cv2.circle(image, (202, 200), 6, (250, 250, 250), -1)
    cv2.circle(image, (158, 200), 3, (44, 36, 30), -1)
    cv2.circle(image, (202, 200), 3, (44, 36, 30), -1)
    cv2.ellipse(image, (180, 228), (7, 10), 0, 0, 360, (176, 134, 112), -1)
    cv2.ellipse(image, (180, 252), (14, 5), 0, 0, 180, (150, 84, 84), -1)
    return np.ascontiguousarray(image)


@pytest.fixture
def face_detection() -> FaceDetection:
    """A synthetic detector result with landmarks (100x140 box at 50,60)."""
    return FaceDetection(
        x=50.0,
        y=60.0,
        w=100.0,
        h=140.0,
        score=0.97,
        landmarks=(
            (80.0, 120.0),
            (130.0, 121.0),
            (105.0, 150.0),
            (85.0, 175.0),
            (128.0, 176.0),
        ),
    )


@pytest.fixture
def region() -> HeadRegion:
    return HeadRegion(cx=250.0, cy=250.0, rx=200.0, ry=200.0, feather=0.5, scale=1.5)


@pytest.fixture(scope="session")
def real_photo() -> np.ndarray:
    """A real photo for the optional detector test (``HEADSIZE_TEST_IMAGE``)."""
    path = os.environ.get("HEADSIZE_TEST_IMAGE")
    if not path or not Path(path).is_file():
        pytest.skip("set HEADSIZE_TEST_IMAGE to a photo containing a face")
    return cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2RGB)
