"""Single source of truth for the application version.

Bump ``__version__`` here and mirror it in ``pyproject.toml`` when releasing.
The release workflow refuses to build if the two disagree.
"""

__version__ = "1.0.0"

APP_NAME = "HeadSize Studio"
APP_ID = "headsize-studio"
ORG_NAME = "HeadSize Studio"

__all__ = ["APP_NAME", "APP_ID", "ORG_NAME", "__version__"]
