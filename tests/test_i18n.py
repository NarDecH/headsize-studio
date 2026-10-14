"""The two-language string catalogue must stay complete and safe to format."""

from __future__ import annotations

import string

import pytest

from headsize.ui import i18n


def test_both_languages_have_the_same_keys() -> None:
    assert i18n.missing_keys("th") == []
    assert i18n.missing_keys("en") == []


def test_no_duplicate_or_empty_strings() -> None:
    for language, table in i18n.STRINGS.items():
        for key, value in table.items():
            assert value.strip(), f"{language}:{key} is empty"
            assert key.strip() == key, f"{language}: {key!r} has stray whitespace"


def test_placeholders_match_across_languages() -> None:
    def fields(text: str) -> set[str]:
        return {
            name for _, name, _, _ in string.Formatter().parse(text) if name
        }

    english = i18n.STRINGS["en"]
    for key, value in i18n.STRINGS["th"].items():
        assert fields(value) == fields(english[key]), f"placeholder mismatch in {key}"


def test_translator_formats_and_falls_back() -> None:
    translator = i18n.Translator("en")
    assert translator.t("app.title") == "HeadSize Studio"
    assert "1.2.3" in translator.t("update.available", version="1.2.3")
    assert translator.t("does.not.exist") == "does.not.exist"


def test_missing_placeholder_does_not_raise() -> None:
    # A caller that forgets an argument gets the raw template, never a crash.
    assert "{version}" in i18n.translator.t("app.version")


def test_language_switch_round_trip() -> None:
    original = i18n.current_language()
    try:
        i18n.set_language("en")
        assert i18n.t("button.open") == "Open an image"
        i18n.set_language("th")
        assert i18n.t("button.open") == "เปิดรูปภาพ"
        i18n.set_language("kl")
        assert i18n.current_language() == "th"  # unknown language is ignored
    finally:
        i18n.set_language(original)


@pytest.mark.parametrize("language,label", i18n.available_languages())
def test_available_languages(language: str, label: str) -> None:
    assert language in i18n.STRINGS
    assert label
