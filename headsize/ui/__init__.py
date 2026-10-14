"""PyQt6 user interface for HeadSize Studio.

Importing this package pulls in Qt, which is why the engine lives in
:mod:`headsize.core` and stays Qt-free.
"""

from headsize.ui.i18n import set_language, t
from headsize.ui.main_window import MainWindow
from headsize.ui.theme import apply_theme, palette

__all__ = ["MainWindow", "apply_theme", "palette", "set_language", "t"]
