"""User settings persistence."""

from __future__ import annotations

import json

from headsize.core.config import AppConfig, config_path


def test_defaults_are_sane() -> None:
    config = AppConfig()
    assert config.theme == "dark"
    assert config.language == "th"
    assert config.update_channel == "stable"
    config.sanitize()
    assert config.render_quality == "high"


def test_round_trip(tmp_path) -> None:
    path = tmp_path / "config.json"
    config = AppConfig(theme="light", language="en", default_feather=0.4)
    config.save(path)
    loaded = AppConfig.load(path)
    assert loaded.theme == "light"
    assert loaded.language == "en"
    assert loaded.default_feather == 0.4


def test_missing_file_yields_defaults(tmp_path) -> None:
    loaded = AppConfig.load(tmp_path / "nope.json")
    assert loaded == AppConfig()


def test_corrupt_file_is_ignored(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{ this is not json", encoding="utf-8")
    assert AppConfig.load(path) == AppConfig()


def test_unknown_and_invalid_values_are_dropped(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"theme": "neon", "language": "kr", "bogus": 1, "default_feather": 9}),
        encoding="utf-8",
    )
    loaded = AppConfig.load(path)
    assert loaded.theme == "dark"
    assert loaded.language == "th"
    assert loaded.default_feather == 0.95
    assert not hasattr(loaded, "bogus")


def test_remember_file_moves_to_front_and_caps() -> None:
    config = AppConfig()
    for index in range(15):
        config.remember_file(f"C:/photos/{index}.jpg")
    config.remember_file("C:/photos/3.jpg")
    assert config.recent_files[0] == "C:/photos/3.jpg"
    assert len(config.recent_files) == 12
    assert config.recent_files.count("C:/photos/3.jpg") == 1


def test_config_path_uses_env_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HEADSIZE_CONFIG_DIR", str(tmp_path))
    assert config_path() == tmp_path / "config.json"
