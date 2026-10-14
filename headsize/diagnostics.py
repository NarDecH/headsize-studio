"""Self-test that proves a build is functional (used by CI and the executable).

``python -m headsize --self-test`` builds the window offscreen, runs the whole
pipeline on a generated image and prints one line per check. It exits non-zero
if anything fails, which makes it a real smoke test for the PyInstaller bundle
(assets present, Qt plugins loadable, OpenCV usable, model loadable).
"""

from __future__ import annotations

import os
import platform
import sys
import tempfile
from pathlib import Path

import numpy as np

from headsize.core.detector import FaceDetector, model_is_available, resolve_model_path
from headsize.core.io import load_image, save_image
from headsize.core.types import DEFAULT_FEATHER, HeadRegion
from headsize.core.warp import apply_head_regions
from headsize.version import APP_NAME, __version__

CHECKS: list[tuple[str, bool, str]] = []
_LINES: list[str] = []


def emit(line: str = "") -> None:
    """Print when there is a console, and always keep the line for the report.

    A ``--windowed`` PyInstaller build has ``sys.stdout is None``, so the report
    file is the only reliable channel there.
    """
    _LINES.append(line)
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        try:
            stream.write(line + "\n")
            stream.flush()
        except Exception:
            pass


def check(name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append((name, bool(ok), detail))
    marker = "ok  " if ok else "FAIL"
    line = f"[{marker}] {name}"
    if detail:
        line += f" — {detail}"
    emit(line)
    return bool(ok)


def report_path() -> Path:
    from headsize.core.config import config_dir

    folder = config_dir() / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "self-test.txt"


def write_report(code: int) -> Path:
    path = report_path()
    try:
        path.write_text(
            "\n".join(_LINES) + f"\nexit-code: {code}\n", encoding="utf-8"
        )
    except OSError:
        pass
    return path


def make_test_image(width: int = 640, height: int = 800) -> np.ndarray:
    """A small synthetic portrait, so the self-test needs no assets."""
    import cv2

    image = np.full((height, width, 3), 220, dtype=np.uint8)
    cv2.ellipse(image, (width // 2, height + 40), (220, 180), 0, 180, 360, (70, 90, 130), -1)
    cv2.ellipse(image, (width // 2, 300), (110, 140), 0, 0, 360, (206, 168, 142), -1)
    cv2.ellipse(image, (width // 2, 250), (118, 100), 0, 180, 360, (52, 40, 36), -1)
    cv2.circle(image, (width // 2 - 40, 290), 8, (250, 250, 250), -1)
    cv2.circle(image, (width // 2 + 40, 290), 8, (250, 250, 250), -1)
    cv2.circle(image, (width // 2 - 40, 290), 4, (30, 30, 30), -1)
    cv2.circle(image, (width // 2 + 40, 290), 4, (30, 30, 30), -1)
    return image


def run_render_pipeline() -> int:
    image = make_test_image()
    region = HeadRegion(
        cx=image.shape[1] / 2,
        cy=310,
        rx=150,
        ry=190,
        scale=1.35,
        feather=DEFAULT_FEATHER,
    )
    warped = apply_head_regions(image, [region], quality="high")
    changed = int(np.count_nonzero(np.any(warped != image, axis=2)))
    check("warp changes pixels", changed > 1000, f"{changed} pixels")
    outside = np.any(warped != image, axis=2)
    ys, xs = np.mgrid[0 : image.shape[0], 0 : image.shape[1]]
    d = np.hypot((xs - region.cx) / region.rx, (ys - region.cy) / region.ry)
    check(
        "nothing outside the ellipse moved",
        not outside[d >= 1.0].any(),
        f"{int(changed)} changed pixels",
    )
    check(
        "scale 1.0 is the identity",
        np.array_equal(apply_head_regions(image, [region.copy(scale=1.0)]), image),
    )
    return 0 if all(ok for _, ok, _ in CHECKS) else 1


def run_io_round_trip() -> int:
    image = make_test_image(320, 400)
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "roundtrip.png"
        save_image(image, target)
        loaded = load_image(target)
        check(
            "PNG round trip",
            loaded.array.shape == image.shape and np.array_equal(loaded.array, image),
            str(target.name),
        )
    return 0


def run_ui_smoke() -> int:
    from PyQt6.QtWidgets import QApplication

    from headsize.core.config import AppConfig
    from headsize.ui.main_window import MainWindow
    from headsize.ui.theme import apply_theme

    app = QApplication.instance() or QApplication([sys.argv[0]])
    config = AppConfig(check_updates_on_start=False, auto_detect_on_open=False)
    apply_theme(app, config.theme)
    window = MainWindow(config)
    window.resize(1100, 760)
    window.show()
    app.processEvents()

    image = make_test_image()
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "selftest.png"
        save_image(image, path)
        window.open_path(str(path))
        window.add_head_centred()
        window._on_scale_changed(1.3, True)
        app.processEvents()
        check("window opened an image", window.doc.has_image, f"{window.doc.size[0]}x{window.doc.size[1]}")
        check("head region created", len(window.doc.regions) == 1)
        result = window.doc.render_full(quality="balanced")
        check(
            "full-resolution render differs from the source",
            not np.array_equal(result, window.doc.array),
        )
        shot = Path(folder) / "window.png"
        check("window can be rendered", window.grab().save(str(shot)), f"{shot.stat().st_size} bytes")
        window.doc.dirty = False
    window.close()
    app.processEvents()
    return 0


def run_detector_check() -> int:
    if not model_is_available():
        check("face model present", False, "model file not found")
        return 1
    path = resolve_model_path()
    check("face model present", True, f"{path} ({path.stat().st_size} bytes)")
    detector = FaceDetector()
    faces = detector.detect(make_test_image())
    check("detector runs", True, f"{len(faces)} face(s) in the synthetic portrait")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run every check. Returns 0 when all of them pass."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    emit(f"{APP_NAME} {__version__} self-test")
    emit(f"  python   {sys.version.split()[0]}")
    emit(f"  platform {platform.platform()}")
    emit(f"  frozen   {getattr(sys, 'frozen', False)}")
    emit(f"  exe      {sys.executable}")

    try:
        import cv2

        check("OpenCV import", True, cv2.__version__)
    except Exception as exc:  # pragma: no cover - broken bundle
        check("OpenCV import", False, str(exc))
    check("NumPy import", True, np.__version__)
    run_detector_check()
    run_render_pipeline()
    run_io_round_trip()
    run_ui_smoke()

    failed = [name for name, ok, _ in CHECKS if not ok]
    emit()
    if failed:
        emit(f"FAILED ({len(failed)}): " + ", ".join(failed))
        code = 1
    else:
        emit(f"all {len(CHECKS)} checks passed")
        code = 0
    emit(f"report: {write_report(code)}")
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
