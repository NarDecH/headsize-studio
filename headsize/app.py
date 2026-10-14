"""Application entry point: logging, theming, main window."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from headsize.core.config import AppConfig, config_dir
from headsize.ui.i18n import set_language
from headsize.ui.main_window import MainWindow
from headsize.ui.theme import apply_theme
from headsize.version import APP_ID, APP_NAME, ORG_NAME, __version__

LOGGER = logging.getLogger("headsize")


def setup_logging(verbose: bool = False) -> Path:
    """Log to the user config directory, plus stderr when it is a terminal."""
    log_dir = config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "headsize.log"

    handlers: list[logging.Handler] = []
    try:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    except OSError:  # pragma: no cover - read-only config dir
        pass
    if sys.stderr is not None and (verbose or sys.stderr.isatty()):
        stream = sys.stderr
        try:  # Thai/emoji text must never crash logging on a cp437 console.
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
        handlers.append(logging.StreamHandler(stream))

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    return log_file


def build_application(argv: list[str] | None = None) -> tuple[QApplication, MainWindow]:
    """Create the QApplication and the main window (without showing it)."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(ORG_NAME)
    app.setDesktopFileName(APP_ID)

    config = AppConfig.load()
    set_language(config.language)
    apply_theme(app, config.theme)
    window = MainWindow(config)
    return app, window


def run(argv: list[str] | None = None) -> int:
    """Run the GUI. Returns the process exit code."""
    arguments = list(argv if argv is not None else sys.argv[1:])
    verbose = "--verbose" in arguments or "-v" in arguments
    setup_logging(verbose)

    if "--version" in arguments:
        print(f"{APP_NAME} {__version__}")
        return 0
    if "--self-test" in arguments:
        from headsize.diagnostics import main as self_test

        return self_test()

    LOGGER.info("Starting %s %s (python %s)", APP_NAME, __version__, sys.version.split()[0])
    if os.name == "nt":
        # A stable AppUserModelID gives the taskbar its own icon and grouping.
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(  # type: ignore[attr-defined]
                f"{ORG_NAME}.{APP_ID}.{__version__}"
            )
        except Exception:  # pragma: no cover - cosmetic only
            pass

    app, window = build_application([sys.argv[0], *arguments])
    window.show()

    images = [a for a in arguments if not a.startswith("-") and Path(a).suffix]
    if images and Path(images[0]).is_file():
        window.open_path(images[0])

    return app.exec()


__all__ = ["build_application", "run", "setup_logging", "Qt"]
