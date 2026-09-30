"""Meaningful MAGI upscale targets — never same-or-lower than the source.

Production targets are 1080p / 1440p / 4K / 8K. A source already at 1080p
cannot "upscale" to 1080p. Compare edges so neither shrinks, then pixel count.

Portrait (tall) sources get portrait targets so MAGI preserves 9:16 framing.
Never scale a tall master to 1920x1080.
"""

from __future__ import annotations

from typing import Any

# Landscape short-edge tiers (width x height).
TARGET_PRESETS_LANDSCAPE: tuple[tuple[str, int, int], ...] = (
    ("1080p", 1920, 1080),
    ("1440p", 2560, 1440),
    ("4K", 3840, 2160),
    ("8K", 7680, 4320),
)

# Portrait short-edge tiers (width x height) — same tier names, swapped framing.
TARGET_PRESETS_PORTRAIT: tuple[tuple[str, int, int], ...] = (
    ("1080p", 1080, 1920),
    ("1440p", 1440, 2560),
    ("4K", 2160, 3840),
    ("8K", 4320, 7680),
)

# Back-compat alias used by older imports/tests.
TARGET_PRESETS = TARGET_PRESETS_LANDSCAPE

_ALIAS_LANDSCAPE = {
    "480P": (854, 480),
    "720P": (1280, 720),
    "1080P": (1920, 1080),
    "1440P": (2560, 1440),
    "4K": (3840, 2160),
    "8K": (7680, 4320),
}

_ALIAS_PORTRAIT = {
    "480P": (480, 854),
    "720P": (720, 1280),
    "1080P": (1080, 1920),
    "1440P": (1440, 2560),
    "4K": (2160, 3840),
    "8K": (4320, 7680),
}

_ALIAS = _ALIAS_LANDSCAPE

TARGET_NOT_ABOVE = "TARGET_NOT_ABOVE_SOURCE"
SOURCE_UNKNOWN = "SOURCE_RESOLUTION_UNKNOWN"
NO_HIGHER_TARGET = "NO_HIGHER_TARGET"

CREATOR_TARGET_NOT_ABOVE = (
    "MAGI only upscales to a size above the current master. "
    "Choose a higher target — same or lower resolution is not an upscale."
)
CREATOR_SOURCE_UNKNOWN = "Adept could not read the master resolution, so MAGI cannot upscale yet."
CREATOR_NO_HIGHER = (
    "This master is already at or above the highest MAGI target. "
    "There is nothing higher to upscale to."
)


class UpscaleTargetError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.creator_message = message


def is_portrait(src_w: int, src_h: int) -> bool:
    return int(src_h or 0) > int(src_w or 0)


def oriented_presets(src_w: int, src_h: int) -> tuple[tuple[str, int, int], ...]:
    return TARGET_PRESETS_PORTRAIT if is_portrait(src_w, src_h) else TARGET_PRESETS_LANDSCAPE


def parse_resolution(resolution_str: str, *, src_w: int = 0, src_h: int = 0) -> tuple[int, int]:
    text = (resolution_str or "").strip().upper()
    alias = _ALIAS_PORTRAIT if is_portrait(src_w, src_h) else _ALIAS_LANDSCAPE
    if text in alias:
        return alias[text]
    if "X" in text:
        parts = text.split("X")
        try:
            width = int(parts[0])
            height = int(parts[1])
            if width > 0 and height > 0:
                return width, height
        except (ValueError, IndexError):
            pass
    # Unknown label with known source orientation → first oriented preset dims as last resort parse
    if is_portrait(src_w, src_h):
        return (1080, 1920)
    return (1920, 1080)


def is_above_source(src_w: int, src_h: int, target_w: int, target_h: int) -> bool:
    if src_w <= 0 or src_h <= 0 or target_w <= 0 or target_h <= 0:
        return False
    # Never shrink either edge; require strictly more pixels.
    if target_w < src_w or target_h < src_h:
        return False
    return (target_w * target_h) > (src_w * src_h)


def meaningful_targets(src_w: int, src_h: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for label, width, height in oriented_presets(src_w, src_h):
        if is_above_source(src_w, src_h, width, height):
            out.append({"id": label, "label": label, "width": width, "height": height})
    return out


def default_target(src_w: int, src_h: int) -> dict[str, Any] | None:
    legal = meaningful_targets(src_w, src_h)
    return legal[0] if legal else None


def assert_meaningful_target(src_w: int, src_h: int, target_w: int, target_h: int) -> None:
    if src_w <= 0 or src_h <= 0:
        raise UpscaleTargetError(SOURCE_UNKNOWN, CREATOR_SOURCE_UNKNOWN)
    if not meaningful_targets(src_w, src_h):
        raise UpscaleTargetError(NO_HIGHER_TARGET, CREATOR_NO_HIGHER)
    if not is_above_source(src_w, src_h, target_w, target_h):
        raise UpscaleTargetError(TARGET_NOT_ABOVE, CREATOR_TARGET_NOT_ABOVE)


def resolve_apply_target(src_w: int, src_h: int, requested: str) -> tuple[int, int, str]:
    """Return (width, height, preset_or_wxh) after the source gate."""
    text = (requested or "").strip()
    if not text:
        first = default_target(src_w, src_h)
        if first is None:
            raise UpscaleTargetError(NO_HIGHER_TARGET, CREATOR_NO_HIGHER)
        return int(first["width"]), int(first["height"]), str(first["id"])
    # Tier labels resolve to orientation-matched presets.
    presets = {row[0].upper(): row for row in oriented_presets(src_w, src_h)}
    key = text.upper()
    if key in presets:
        label, width, height = presets[key]
        assert_meaningful_target(src_w, src_h, width, height)
        return width, height, label
    width, height = parse_resolution(text, src_w=src_w, src_h=src_h)
    assert_meaningful_target(src_w, src_h, width, height)
    return width, height, text
