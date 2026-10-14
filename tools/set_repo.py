"""Rewrite the baked-in GitHub coordinates for the updater and the docs.

Run:

    python tools/set_repo.py --owner my-github-name --repo headsize-studio
    python tools/set_repo.py --show

It updates:

* ``headsize/update/repo.py`` (the updater's default owner/repo),
* the ``Homepage``/``Documentation``/``Changelog`` URLs in ``pyproject.toml``,
* the repository links inside ``README.md`` and ``docs/*.md``.

The ``HEADSiZE-OWNER`` placeholder means "not published yet"; the updater reports
itself as disabled rather than polling a repository that does not exist. The
placeholder is rewritten too, so a checkout that was already published can still
have a stray placeholder (for example a new changelog section) repaired.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PLACEHOLDER = "HEADSiZE-OWNER"
DEFAULT_REPO = "headsize-studio"

#: Every tracked text file that carries repository coordinates.
REWRITE_TARGETS = (
    "pyproject.toml",
    "README.md",
    "CHANGELOG.md",
    "AGENT.md",
    "docs/readme.md",
    "docs/research.md",
    "docs/changelog.md",
    "docs/index.html",
    "tools/build_docs.py",
)


def current_defaults() -> tuple[str, str]:
    from headsize.update.repo import DEFAULT_OWNER, DEFAULT_REPO

    return DEFAULT_OWNER, DEFAULT_REPO


def rewrite(path: Path, old_owner: str, old_repo: str, owner: str, repo: str) -> bool:
    text = path.read_text(encoding="utf-8")
    updated = text.replace(f"{old_owner}/{old_repo}", f"{owner}/{repo}")
    updated = updated.replace(f"github.com/{old_owner}", f"github.com/{owner}")
    if old_owner != PLACEHOLDER:
        # Repair a stale placeholder left over from before the first publish.
        updated = updated.replace(f"{PLACEHOLDER}/{old_repo}", f"{owner}/{repo}")
        updated = updated.replace(f"github.com/{PLACEHOLDER}", f"github.com/{owner}")
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def update_repo_module(owner: str, repo: str) -> bool:
    path = ROOT / "headsize" / "update" / "repo.py"
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r'^DEFAULT_OWNER = .*$',
        f'DEFAULT_OWNER = "{owner}"',
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(r'^DEFAULT_REPO = .*$', f'DEFAULT_REPO = "{repo}"', text, flags=re.MULTILINE)
    path.write_text(text, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", help="GitHub user or organisation")
    parser.add_argument("--repo", default="", help="repository name")
    parser.add_argument("--show", action="store_true", help="print the current values")
    args = parser.parse_args(argv)

    old_owner, old_repo = current_defaults()
    if args.show or not args.owner:
        print(f"owner: {old_owner}")
        print(f"repo:  {old_repo}")
        return 0

    owner = args.owner.strip()
    repo = (args.repo or old_repo or DEFAULT_REPO).strip()
    if "/" in owner:
        owner, _, embedded = owner.partition("/")
        repo = embedded or repo

    update_repo_module(owner, repo)
    touched: list[str] = ["headsize/update/repo.py"]
    for relative in REWRITE_TARGETS:
        path = ROOT / relative
        if path.is_file() and rewrite(path, old_owner, old_repo, owner, repo):
            touched.append(relative)

    print(f"repository is now {owner}/{repo}")
    for name in touched:
        print(f"  updated {name}")
    print("Rebuild the docs with: python tools/build_docs.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
