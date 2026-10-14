"""Head-size presets shared by the UI and the CLI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    key: str
    label_en: str
    label_th: str
    scale: float
    hint: str = ""


PRESETS: tuple[Preset, ...] = (
    Preset("tiny", "Tiny", "เล็กมาก", 0.75, "0.75x"),
    Preset("small", "Small", "เล็ก", 0.88, "0.88x"),
    Preset("normal", "Normal", "ปกติ", 1.00, "1.00x"),
    Preset("big", "Big", "ใหญ่", 1.18, "1.18x"),
    Preset("huge", "Huge", "ใหญ่มาก", 1.38, "1.38x"),
    Preset("meme", "Meme", "มีม", 1.75, "1.75x"),
)

PRESET_BY_KEY = {preset.key: preset for preset in PRESETS}


def preset_for_scale(scale: float, tolerance: float = 0.01) -> Preset | None:
    for preset in PRESETS:
        if abs(preset.scale - scale) <= tolerance:
            return preset
    return None


__all__ = ["PRESETS", "PRESET_BY_KEY", "Preset", "preset_for_scale"]
