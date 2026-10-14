"""HeadSize Studio — resize the head of people in a photo.

The package is split into three layers:

* :mod:`headsize.core`   — pure NumPy/OpenCV image engine (no Qt import).
* :mod:`headsize.ui`     — PyQt6 user interface.
* :mod:`headsize.update` — auto-update through GitHub Releases.

``headsize.core`` must stay importable without a display and without Qt so the
engine can be unit-tested and scripted from the command line.
"""

from headsize.version import APP_ID, APP_NAME, ORG_NAME, __version__

__all__ = ["APP_ID", "APP_NAME", "ORG_NAME", "__version__"]
