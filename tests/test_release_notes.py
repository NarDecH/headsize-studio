"""Release notes: every relative link must survive GitHub's rendering rules."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "make_release_notes.py"
CHANGELOG = ROOT / "docs" / "changelog.md"

SLUG = "someone/headsize-studio"
REF = "v9.9.9"


def _load():
    spec = importlib.util.spec_from_file_location("make_release_notes", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


notes = _load()


def test_images_become_raw_urls_on_the_tag() -> None:
    text = "![hero](assets/hero.png)\n"
    out = notes.build_notes(text, slug=SLUG, ref=REF)
    assert out == f"![hero](https://raw.githubusercontent.com/{SLUG}/{REF}/docs/assets/hero.png)\n"


def test_links_become_blob_urls_and_keep_their_fragment() -> None:
    text = "see [research §5](research.md#5-the-rim-is-a-fixed-point)\n"
    out = notes.build_notes(text, slug=SLUG, ref=REF)
    assert out == (
        f"see [research §5](https://github.com/{SLUG}/blob/{REF}/docs/research.md"
        "#5-the-rim-is-a-fixed-point)\n"
    )


def test_parent_relative_links_resolve_against_the_repository_root() -> None:
    out = notes.build_notes("[root](../CHANGELOG.md)\n", slug=SLUG, ref=REF)
    assert out == f"[root](https://github.com/{SLUG}/blob/{REF}/CHANGELOG.md)\n"


@pytest.mark.parametrize(
    "target",
    [
        "https://example.com/x.png",
        "http://example.com/page",
        "#section",
        "mailto:dev@example.com",
    ],
)
def test_absolute_and_internal_targets_are_left_alone(target: str) -> None:
    text = f"[x]({target})\n"
    assert notes.build_notes(text, slug=SLUG, ref=REF) == text


def test_a_titled_link_keeps_its_title() -> None:
    text = '![hero](assets/hero.png "the hero")\n'
    expected = (
        f"![hero](https://raw.githubusercontent.com/{SLUG}/{REF}/docs/assets/hero.png"
        ' "the hero")\n'
    )
    assert notes.build_notes(text, slug=SLUG, ref=REF) == expected


def test_the_real_changelog_has_no_relative_links_left() -> None:
    out = notes.build_notes(CHANGELOG.read_text(encoding="utf-8"), slug=SLUG, ref=REF)
    for line in out.splitlines():
        for chunk in line.split("](")[1:]:
            target = chunk.split(")")[0]
            assert target.startswith(("http://", "https://", "#")), target


def test_version_tag_matches_the_shipped_version() -> None:
    from headsize.version import __version__

    assert notes.version_tag() == f"v{__version__}"
