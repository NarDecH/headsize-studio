"""Semantic version handling used by the updater."""

from __future__ import annotations

import pytest

from headsize.update.version import (
    Version,
    compare_versions,
    is_newer,
    normalize_tag,
    parse_version,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.2.3", (1, 2, 3)),
        ("v1.2.3", (1, 2, 3)),
        ("1.2", (1, 2, 0)),
        ("1", (1, 0, 0)),
        ("1_2_3", (1, 2, 3)),
        ("  2.10.4  ", (2, 10, 4)),
    ],
)
def test_parse_and_pad(raw, expected) -> None:
    assert Version(raw).tuple() == expected


def test_prerelease_is_below_release() -> None:
    assert Version("1.0.0-beta1") < Version("1.0.0")
    assert Version("1.0.0-alpha1") < Version("1.0.0-beta1")
    assert Version("1.0.0-rc1") > Version("1.0.0-beta9")
    assert Version("1.0.0-dev") < Version("1.0.0-alpha1")


def test_numeric_comparison_is_not_lexicographic() -> None:
    assert Version("1.10.0") > Version("1.9.9")
    assert Version("2.0.0") > Version("1.99.99")


def test_equal_versions() -> None:
    assert Version("1.2.0") == Version("1.2")
    assert Version("v1.2.0") == "1.2.0"
    assert compare_versions("1.2.0", "1.2") == 0
    assert hash(Version("1.2.0")) == hash(Version("1.2"))


def test_build_metadata_is_ignored() -> None:
    assert Version("1.2.3+win64") == Version("1.2.3")


def test_compare_versions_direction() -> None:
    assert compare_versions("1.0.0", "1.1.0") == -1
    assert compare_versions("1.1.0", "1.0.0") == 1
    assert is_newer("1.1.0", "1.0.0")
    assert not is_newer("1.0.0", "1.0.0")
    assert not is_newer("0.9.0", "1.0.0")


def test_normalize_tag() -> None:
    assert normalize_tag("v1.2.3") == "1.2.3"
    assert normalize_tag("v1.2.3-beta.4") == "1.2.3-beta4"
    assert normalize_tag("") == "0.0.0"


def test_garbage_does_not_explode() -> None:
    version = parse_version("not-a-version")
    assert version.tuple() == (0, 0, 0)
    assert not version.valid
    assert version < Version("0.0.1")
    assert parse_version(None).raw == "0.0.0"


def test_sorting_a_release_list() -> None:
    tags = ["v1.0.0", "v1.2.0-rc1", "v1.2.0", "v1.10.0", "v1.3.0"]
    ordered = [v.raw for v in sorted(Version(t) for t in tags)]
    assert ordered == ["v1.0.0", "v1.2.0-rc1", "v1.2.0", "v1.3.0", "v1.10.0"]
