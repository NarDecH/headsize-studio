"""Download (or verify) the YuNet face detection model.

Run:

    python tools/fetch_model.py            # download into headsize/assets/models
    python tools/fetch_model.py --verify   # only check the bundled file

The model is MIT licensed (© Shiqi Yu) and is committed to the repository, so
this is only needed for a slim clone or after a corrupted checkout.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from headsize.core.detector import (  # noqa: E402
    LEGACY_MODEL_FILENAME,
    LEGACY_MODEL_SHA256,
    LEGACY_MODEL_URL,
    MODEL_FILENAME,
    MODEL_SHA256,
    MODEL_URL,
    download_model,
    package_asset_dir,
    sha256_file,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch the YuNet model")
    parser.add_argument("--verify", action="store_true", help="only verify what is present")
    parser.add_argument("--legacy", action="store_true", help="also fetch the OpenCV 4 fallback")
    args = parser.parse_args(argv)

    target_dir = package_asset_dir() / "models"
    target = target_dir / MODEL_FILENAME

    if target.is_file():
        digest = sha256_file(target)
        state = "ok" if digest == MODEL_SHA256 else "MISMATCH"
        print(f"{target} ({target.stat().st_size} bytes) sha256 {state}")
        if digest != MODEL_SHA256:
            print(f"  expected {MODEL_SHA256}")
            if args.verify:
                return 1

    if args.verify:
        return 0 if target.is_file() else 1

    if not target.is_file() or sha256_file(target) != MODEL_SHA256:
        def progress(done: int, total: int) -> None:
            percent = int(done * 100 / total) if total else 0
            print(f"\r  downloading… {percent}%", end="", flush=True)

        print(f"downloading {MODEL_URL}")
        download_model(target, progress=progress, url=MODEL_URL, sha256=MODEL_SHA256)
        print(f"\n  wrote {target} ({target.stat().st_size} bytes)")

    if args.legacy:
        legacy = target_dir / LEGACY_MODEL_FILENAME
        if not legacy.is_file() or sha256_file(legacy) != LEGACY_MODEL_SHA256:
            download_model(
                legacy, url=LEGACY_MODEL_URL, sha256=LEGACY_MODEL_SHA256
            )
            print(f"  wrote {legacy} ({legacy.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
