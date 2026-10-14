"""Repository coordinates: the rewrite helper and the shipped-file invariant."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SET_REPO = ROOT / "tools" / "set_repo.py"


def _load():
    spec = importlib.util.spec_from_file_location("set_repo", SET_REPO)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


set_repo = _load()
PLACEHOLDER = set_repo.PLACEHOLDER


def _real_coordinates() -> tuple[str, str]:
    from headsize.update.repo import DEFAULT_OWNER, DEFAULT_REPO

    return DEFAULT_OWNER, DEFAULT_REPO


def test_rewrite_targets_cover_every_shipped_file() -> None:
    """Every checked-in file that carries a repository link must be rewritten."""
    assert "CHANGELOG.md" in set_repo.REWRITE_TARGETS
    for relative in set_repo.REWRITE_TARGETS:
        assert (ROOT / relative).is_file(), f"{relative} is gone from the tree"


def test_rewrite_replaces_coordinates(tmp_path: Path) -> None:
    target = tmp_path / "note.md"
    target.write_text("see https://github.com/old-user/old-repo\n", encoding="utf-8")

    assert set_repo.rewrite(target, "old-user", "old-repo", "new-user", "new-repo")
    assert target.read_text(encoding="utf-8") == "see https://github.com/new-user/new-repo\n"
    assert not set_repo.rewrite(target, "old-user", "old-repo", "new-user", "new-repo")


def test_rewrite_repairs_a_stale_placeholder(tmp_path: Path) -> None:
    """A file added after the first publish can still carry the placeholder."""
    target = tmp_path / "CHANGELOG.md"
    target.write_text(
        f"[1.0.0]: https://github.com/{PLACEHOLDER}/old-repo/releases/tag/v1.0.0\n",
        encoding="utf-8",
    )

    assert set_repo.rewrite(target, "old-user", "old-repo", "new-user", "new-repo")
    assert target.read_text(encoding="utf-8") == (
        "[1.0.0]: https://github.com/new-user/new-repo/releases/tag/v1.0.0\n"
    )


@pytest.mark.parametrize(
    "relative", ["README.md", "CHANGELOG.md", "AGENT.md", "pyproject.toml"]
)
def test_published_tree_has_no_placeholder(relative: str) -> None:
    """Once the updater has real coordinates, no shipped file may keep the placeholder.

    Before the first publish the placeholder is the correct value everywhere, so
    the check is one of consistency rather than an absolute ban.
    """
    owner, repo = _real_coordinates()
    if owner == PLACEHOLDER:
        pytest.skip("repository is not published yet")

    text = (ROOT / relative).read_text(encoding="utf-8")
    assert PLACEHOLDER not in text, f"{relative} still points at {PLACEHOLDER}"
