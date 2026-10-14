"""Turn the changelog into release notes whose links work on a Release page.

The links inside ``docs/`` are written for someone browsing the repository, so
they are relative to that folder. A GitHub Release body is rendered against the
repository root instead, which turns ``assets/hero.png`` into a request for
``/<owner>/<repo>/raw/<tag>/assets/hero.png`` — a file that does not exist, and a
broken image in the notes.

This rewrites every relative target to an absolute URL on the tag being
released: images point at the raw file, other links at the blob page, and
``#fragments`` are kept.

Run:

    python tools/make_release_notes.py --out release-notes.md --ref v1.0.0
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_SOURCE = ROOT / "docs" / "changelog.md"

#: ``![alt](target)`` or ``[text](target "title")``.
LINK = re.compile(r"(!?\[[^\]]*\]\()([^)\s]+)((?:\s+\"[^\"]*\")?\))")

ABSOLUTE_PREFIXES = ("http://", "https://", "//", "mailto:", "data:", "#")


def current_slug() -> str:
    from headsize.update.repo import resolve_repo

    owner, repo = resolve_repo()
    return f"{owner}/{repo}"


def rewrite_target(
    target: str, *, base_dir: str, slug: str, ref: str, is_image: bool
) -> str:
    """Absolute URL for one relative markdown target, or the target unchanged."""
    if not target or target.startswith(ABSOLUTE_PREFIXES) or "://" in target:
        return target
    path, _, fragment = target.partition("#")
    if not path:
        return target
    resolved = posixpath.normpath(posixpath.join(base_dir, path))
    if resolved.startswith(".."):
        return target
    if is_image:
        url = f"https://raw.githubusercontent.com/{slug}/{ref}/{resolved}"
    else:
        url = f"https://github.com/{slug}/blob/{ref}/{resolved}"
    return f"{url}#{fragment}" if fragment else url


def build_notes(
    text: str, *, slug: str, ref: str, base_dir: str = "docs"
) -> str:
    """Release notes: ``text`` with every relative link made absolute."""

    def replace(match: re.Match[str]) -> str:
        prefix, target, suffix = match.groups()
        return (
            prefix
            + rewrite_target(
                target,
                base_dir=base_dir,
                slug=slug,
                ref=ref,
                is_image=prefix.startswith("!"),
            )
            + suffix
        )

    return LINK.sub(replace, text)


def version_tag() -> str:
    from headsize.version import __version__

    return f"v{__version__}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="changelog to convert")
    parser.add_argument("--out", help="where to write the notes (default: stdout)")
    parser.add_argument("--ref", default="", help="tag or branch the links point at")
    parser.add_argument("--slug", default="", help="owner/repo, defaults to the baked-in one")
    parser.add_argument(
        "--base-dir", default="docs", help="folder the relative links are written from"
    )
    args = parser.parse_args(argv)

    source = Path(args.source)
    if not source.is_file():
        parser.error(f"{source} not found")

    notes = build_notes(
        source.read_text(encoding="utf-8"),
        slug=args.slug or current_slug(),
        ref=args.ref or version_tag(),
        base_dir=args.base_dir,
    )
    if args.out:
        Path(args.out).write_text(notes, encoding="utf-8")
        print(f"wrote {args.out} ({len(notes)} chars)")
    else:
        print(notes, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
