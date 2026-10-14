"""Command line interface: batch head resizing without a GUI.

Examples
--------
Detect every face and grow all heads by 30 %::

    headsize-cli photo.jpg --scale 1.3

Shrink the head by hand without a photo of a face::

    headsize-cli photo.jpg --scale 0.85 --region 640,420,180,240 -o small.jpg

List what the detector found::

    headsize-cli photo.jpg --list-faces
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from headsize.core.detector import FaceDetector, ModelUnavailableError, model_is_available
from headsize.core.geometry import estimate_head_region
from headsize.core.io import load_image, save_image
from headsize.core.types import MAX_SCALE, MIN_SCALE, HeadRegion
from headsize.core.warp import affected_bounds, apply_head_regions
from headsize.version import APP_NAME, __version__


def _parse_region(text: str) -> HeadRegion:
    parts = [piece for piece in text.replace(" ", "").split(",") if piece]
    if len(parts) not in (4, 5):
        raise argparse.ArgumentTypeError(
            "--region needs cx,cy,rx,ry or cx,cy,rx,ry,scale"
        )
    try:
        values = [float(piece) for piece in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"--region values must be numbers: {exc}") from exc
    cx, cy, rx, ry = values[:4]
    scale = values[4] if len(values) == 5 else 1.0
    return HeadRegion(cx=cx, cy=cy, rx=rx, ry=ry, scale=scale)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="headsize-cli",
        description="Resize the head of people in a photo (batch mode).",
    )
    parser.add_argument("input", nargs="?", help="input image")
    parser.add_argument("-o", "--output", help="output image (default: <input>-headsize.<ext>)")
    parser.add_argument(
        "--scale",
        type=float,
        default=1.3,
        help=f"head scale factor, {MIN_SCALE}-{MAX_SCALE} (default: 1.3)",
    )
    parser.add_argument("--feather", type=float, default=0.55, help="edge softness 0-0.9")
    parser.add_argument(
        "--index",
        type=int,
        default=-1,
        help="only change this detected face (-1 = every face)",
    )
    parser.add_argument(
        "--region",
        type=_parse_region,
        action="append",
        help="manual zone cx,cy,rx,ry[,scale]; repeatable, skips detection",
    )
    parser.add_argument(
        "--list-faces", action="store_true", help="print the detected faces and exit"
    )
    parser.add_argument("--json", action="store_true", help="JSON output for --list-faces")
    parser.add_argument(
        "--quality",
        choices=("fast", "balanced", "high"),
        default="high",
        help="resampling quality",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    parser.add_argument(
        "--check-update", action="store_true", help="check GitHub for a newer release"
    )
    return parser


def _resolve_regions(args, image) -> list[HeadRegion]:
    if args.region:
        regions = list(args.region)
        if any(abs(r.scale - 1.0) < 1e-9 for r in regions):
            for region in regions:
                region.scale = args.scale
                region.feather = args.feather
        return regions

    if not model_is_available():
        raise ModelUnavailableError(
            "Face model not found. Run `tools/fetch_model.py`, or pass --region."
        )
    faces = FaceDetector().detect(image)
    if not faces:
        raise ModelUnavailableError(
            "No face detected. Pass a manual --region cx,cy,rx,ry instead."
        )
    regions = [estimate_head_region(face, feather=args.feather) for face in faces]
    if args.index >= 0:
        if args.index >= len(regions):
            raise SystemExit(f"error: --index {args.index} but only {len(regions)} face(s) found")
        chosen = regions[args.index]
        chosen.scale = args.scale
        return [chosen]
    for region in regions:
        region.scale = args.scale
    return regions


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.check_update:
        from headsize.update.repo import resolve_repo
        from headsize.update.updater import Updater

        owner, repo = resolve_repo()
        check = Updater(owner, repo, __version__).check()
        print(f"current: {check.current}")
        if check.status == "available":
            print(f"available: {check.latest}\n{check.url}")
            return 0
        print(f"status: {check.status} {check.message}".strip())
        return 0

    if not args.input:
        parser.print_help()
        return 2

    source = Path(args.input)
    if not source.is_file():
        print(f"error: {source} not found", file=sys.stderr)
        return 2

    image = load_image(source)
    array = image.array

    if args.list_faces:
        if not model_is_available():
            print("error: face model not found", file=sys.stderr)
            return 3
        faces = FaceDetector().detect(array)
        if args.json:
            print(json.dumps([face.as_dict() for face in faces], indent=2))
        else:
            print(f"{image.width}x{image.height} px — {len(faces)} face(s)")
            for index, face in enumerate(faces):
                print(
                    f"  #{index} box=({face.x:.0f},{face.y:.0f},{face.w:.0f},{face.h:.0f}) "
                    f"score={face.score:.3f}"
                )
        return 0

    try:
        regions = _resolve_regions(args, array)
    except ModelUnavailableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    scale = max(MIN_SCALE, min(MAX_SCALE, args.scale))
    for region in regions:
        region.scale = max(MIN_SCALE, min(MAX_SCALE, region.scale))

    output = Path(args.output) if args.output else source.with_name(
        f"{source.stem}-headsize{source.suffix or '.jpg'}"
    )
    result = apply_head_regions(array, regions, quality=args.quality)
    save_image(
        result,
        output,
        quality=95,
        icc_profile=image.icc_profile,
        dpi=image.dpi,
    )

    bounds = affected_bounds(regions, *image.size)
    print(
        f"{source.name} -> {output.name}: {len(regions)} zone(s), scale {scale:.2f}x"
        + (f", touched {bounds}" if bounds else "")
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
