"""Aspect-preserving MAGI upscale targets.

A target is a resolution class. It sets the shorter output edge only.
The other edge comes from the source pixel aspect. MAGI upscale never
selects a 16:9 or 9:16 canvas, and it never crops, pads, or stretches.

2K is its own class: shorter edge 2048. It sits above 1440p (shorter edge
1440) and below 4K (shorter edge 2160). It is not Timeline's "2K" alias
of a 2560×1440 frame.
"""

from __future__ import annotations

import math
from typing import Any

# (class id, shorter output edge in pixels). Order is the creator selector order.
CLASS_SHORT_EDGE: tuple[tuple[str, int], ...] = (
    ("1080p", 1080),
    ("1440p", 1440),
    ("2K", 2048),
    ("4K", 2160),
    ("8K", 4320),
)

# Accepted on old clients and Preview Render strings. Not shown in the selector.
_EXTRA_SHORT_EDGE = {
    "720P": 720,
    "480P": 480,
}

_CLASS_BY_KEY = {label.upper(): (label, edge) for label, edge in CLASS_SHORT_EDGE}
_CLASS_BY_KEY.update({key: (key.lower() if key != "720P" else "720p", edge) for key, edge in _EXTRA_SHORT_EDGE.items()})
_CLASS_BY_KEY["720P"] = ("720p", 720)
_CLASS_BY_KEY["480P"] = ("480p", 480)

# Relative aspect error allowed after even-pixel normalization.
ASPECT_TOLERANCE = 0.005

TARGET_NOT_ABOVE = "TARGET_NOT_ABOVE_SOURCE"
SOURCE_UNKNOWN = "SOURCE_RESOLUTION_UNKNOWN"
NO_HIGHER_TARGET = "NO_HIGHER_TARGET"
TARGET_UNKNOWN = "TARGET_UNKNOWN"

CREATOR_TARGET_NOT_ABOVE = (
    "MAGI only upscales to a size above the current master. "
    "Choose a higher target — same or lower resolution is not an upscale."
)
CREATOR_SOURCE_UNKNOWN = "Adept could not read the master resolution, so MAGI cannot upscale yet."
CREATOR_NO_HIGHER = (
    "This master is already at or above the highest MAGI target. "
    "There is nothing higher to upscale to."
)
CREATOR_TARGET_UNKNOWN = "Choose an upscale target such as 1080p, 1440p, 2K, or 4K."

# Known display names. Used only to label real pixels, never to choose them.
_KNOWN_ASPECTS: tuple[tuple[float, str], ...] = (
    (1 / 1, "1:1"),
    (4 / 3, "4:3"),
    (3 / 4, "3:4"),
    (16 / 9, "16:9"),
    (9 / 16, "9:16"),
    (21 / 9, "21:9"),
    (2.39, "2.39:1"),
)


class UpscaleTargetError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.creator_message = message


def is_portrait(src_w: int, src_h: int) -> bool:
    return int(src_h or 0) > int(src_w or 0)


def even_dim(value: float) -> int:
    return max(2, int(round(float(value) / 2.0)) * 2)


def aspects_match(src_w: int, src_h: int, dst_w: int, dst_h: int, *, tolerance: float = ASPECT_TOLERANCE) -> bool:
    if min(int(src_w), int(src_h), int(dst_w), int(dst_h)) <= 0:
        return False
    source = int(src_w) / int(src_h)
    output = int(dst_w) / int(dst_h)
    return abs(source - output) / source <= tolerance


def aspect_label(width: int, height: int) -> str:
    """Label the actual pixel ratio. Never invent 16:9 for a different frame."""
    if width <= 0 or height <= 0:
        return ""
    ratio = width / height
    for known, name in _KNOWN_ASPECTS:
        if abs(ratio - known) / known <= 0.004:
            return name
    divisor = math.gcd(int(width), int(height)) or 1
    return f"{int(width) // divisor}:{int(height) // divisor}"


def dimensions_for_short_edge(src_w: int, src_h: int, short_edge: int) -> tuple[int, int]:
    """Shorter side is the class. The longer side follows the source ratio, even pixels only."""
    if src_w <= 0 or src_h <= 0 or short_edge <= 0:
        raise UpscaleTargetError(SOURCE_UNKNOWN, CREATOR_SOURCE_UNKNOWN)
    short = even_dim(short_edge)
    aspect = src_w / src_h
    if src_w >= src_h:
        height = short
        width = _best_even(height * aspect, fixed=height, aspect=aspect, free_is_width=True)
        return width, height
    width = short
    height = _best_even(width / aspect, fixed=width, aspect=aspect, free_is_width=False)
    return width, height


def _best_even(raw: float, *, fixed: int, aspect: float, free_is_width: bool) -> int:
    base = even_dim(raw)
    best = base
    best_err = float("inf")
    for candidate in (base - 2, base, base + 2):
        if candidate < 2:
            continue
        ratio = (candidate / fixed) if free_is_width else (fixed / candidate)
        err = abs(ratio - aspect)
        if err < best_err:
            best_err = err
            best = candidate
    return best


def _explicit_wxh(text: str) -> tuple[int, int] | None:
    cleaned = (text or "").strip().lower().replace("×", "x").replace(" ", "")
    if "x" not in cleaned:
        return None
    left, right = cleaned.split("x", 1)
    try:
        width = int(left)
        height = int(right)
    except ValueError:
        return None
    if width > 0 and height > 0:
        return width, height
    return None


def _class_for_text(text: str) -> tuple[str, int] | None:
    key = (text or "").strip().upper().replace(" ", "")
    found = _CLASS_BY_KEY.get(key)
    if found:
        return found
    wh = _explicit_wxh(text)
    if not wh:
        return None
    short = min(wh)
    for label, edge in CLASS_SHORT_EDGE:
        if abs(edge - short) <= 1:
            return label, edge
    for label, edge in (("720p", 720), ("480p", 480)):
        if abs(edge - short) <= 1:
            return label, edge
    return "", short


def oriented_presets(src_w: int, src_h: int) -> tuple[tuple[str, int, int], ...]:
    """Class id plus the aspect-correct size for this source. Not a 16:9 table."""
    rows: list[tuple[str, int, int]] = []
    for label, edge in CLASS_SHORT_EDGE:
        width, height = dimensions_for_short_edge(src_w, src_h, edge)
        rows.append((label, width, height))
    return tuple(rows)


def parse_resolution(resolution_str: str, *, src_w: int = 0, src_h: int = 0) -> tuple[int, int]:
    """Parse a request. Class names require source dimensions so they cannot become 16:9."""
    wh = _explicit_wxh(resolution_str)
    if src_w > 0 and src_h > 0:
        width, height, _label = resolve_apply_target(src_w, src_h, resolution_str, require_upscale=False)
        return width, height
    if wh:
        return wh
    raise ValueError(CREATOR_TARGET_UNKNOWN)


def is_above_source(src_w: int, src_h: int, target_w: int, target_h: int) -> bool:
    if src_w <= 0 or src_h <= 0 or target_w <= 0 or target_h <= 0:
        return False
    if target_w < src_w or target_h < src_h:
        return False
    return (target_w * target_h) > (src_w * src_h)


def meaningful_targets(src_w: int, src_h: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for label, edge in CLASS_SHORT_EDGE:
        width, height = dimensions_for_short_edge(src_w, src_h, edge)
        if is_above_source(src_w, src_h, width, height):
            out.append(
                {
                    "id": label,
                    "label": label,
                    "width": width,
                    "height": height,
                    "aspect": aspect_label(width, height),
                }
            )
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


def resolve_apply_target(
    src_w: int,
    src_h: int,
    requested: str,
    *,
    require_upscale: bool = True,
) -> tuple[int, int, str]:
    """Return (width, height, class id). Preview and Apply both call this."""
    if src_w <= 0 or src_h <= 0:
        raise UpscaleTargetError(SOURCE_UNKNOWN, CREATOR_SOURCE_UNKNOWN)
    text = (requested or "").strip()
    if not text:
        first = default_target(src_w, src_h)
        if first is None:
            raise UpscaleTargetError(NO_HIGHER_TARGET, CREATOR_NO_HIGHER)
        return int(first["width"]), int(first["height"]), str(first["id"])

    parsed = _class_for_text(text)
    if parsed is None:
        raise UpscaleTargetError(TARGET_UNKNOWN, CREATOR_TARGET_UNKNOWN)
    label, short_edge = parsed
    explicit = _explicit_wxh(text)
    if explicit and aspects_match(src_w, src_h, explicit[0], explicit[1]):
        width, height = even_dim(explicit[0]), even_dim(explicit[1])
        if not aspects_match(src_w, src_h, width, height):
            width, height = dimensions_for_short_edge(src_w, src_h, min(explicit))
    else:
        width, height = dimensions_for_short_edge(src_w, src_h, short_edge)
    if not aspects_match(src_w, src_h, width, height):
        raise UpscaleTargetError(TARGET_UNKNOWN, CREATOR_TARGET_UNKNOWN)
    if require_upscale:
        assert_meaningful_target(src_w, src_h, width, height)
    resolved = label or f"{width}x{height}"
    return width, height, resolved
