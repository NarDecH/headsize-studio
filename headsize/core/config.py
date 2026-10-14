"""User settings persisted as JSON in the platform config directory."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from headsize.core.types import DEFAULT_FEATHER


def config_dir() -> Path:
    """Per-user configuration directory."""
    override = os.environ.get("HEADSIZE_CONFIG_DIR")
    if override:
        return Path(override)
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "HeadSizeStudio"


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class AppConfig:
    """Everything the app remembers between runs."""

    version_seen: str = ""
    theme: str = "dark"  # "dark" | "light"
    language: str = "th"  # "th" | "en"
    auto_detect_on_open: bool = True
    show_region_overlay: bool = True
    show_compare_split: bool = False
    compare_position: float = 0.5
    default_feather: float = DEFAULT_FEATHER
    render_quality: str = "high"  # "fast" | "balanced" | "high"
    check_updates_on_start: bool = True
    update_channel: str = "stable"  # "stable" | "beta"
    update_owner: str = ""
    update_repo: str = ""
    last_directory: str = ""
    jpeg_quality: int = 95
    window_geometry: str = ""
    window_state: str = ""
    splitter_state: str = ""
    recent_files: list[str] = field(default_factory=list)
    ask_before_overwrite: bool = True
    detection_score: float = 0.6
    keep_metadata: bool = True

    # ------------------------------------------------------------ persistence
    @classmethod
    def load(cls, path: str | Path | None = None) -> AppConfig:
        target = Path(path) if path else config_path()
        config = cls()
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return config
        if not isinstance(raw, dict):
            return config
        known = {f.name for f in fields(cls)}
        for key, value in raw.items():
            if key in known:
                setattr(config, key, value)
        config.sanitize()
        return config

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path else config_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, target)
        return target

    def sanitize(self) -> None:
        """Drop values that would break the UI if hand-edited."""
        if self.theme not in ("dark", "light"):
            self.theme = "dark"
        if self.language not in ("th", "en"):
            self.language = "th"
        if self.render_quality not in ("fast", "balanced", "high"):
            self.render_quality = "high"
        if self.update_channel not in ("stable", "beta"):
            self.update_channel = "stable"
        self.compare_position = min(max(float(self.compare_position), 0.0), 1.0)
        self.default_feather = min(max(float(self.default_feather), 0.0), 0.95)
        self.detection_score = min(max(float(self.detection_score), 0.1), 0.99)
        self.jpeg_quality = min(max(int(self.jpeg_quality), 50), 100)
        if not isinstance(self.recent_files, list):
            self.recent_files = []
        self.recent_files = [str(p) for p in self.recent_files][:12]

    # ----------------------------------------------------------------- recent
    def remember_file(self, path: str | Path) -> None:
        text = str(path)
        self.recent_files = [text] + [p for p in self.recent_files if p != text]
        self.recent_files = self.recent_files[:12]
        self.last_directory = str(Path(text).parent)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = ["AppConfig", "config_dir", "config_path"]
