"""Influence levels for timeline reference bindings."""

from __future__ import annotations

from typing import Literal

InfluenceLevel = Literal["locked", "strong", "moderate", "loose", "inspiration"]

INFLUENCE_LEVELS: tuple[str, ...] = (
    "locked",
    "strong",
    "moderate",
    "loose",
    "inspiration",
)

# Semantic influence -> IC-LoRA strength preset name (only when ic_lora.ready).
INFLUENCE_TO_STRENGTH_PRESET: dict[str, str] = {
    "locked": "strong",
    "strong": "strong",
    "moderate": "balanced",
    "loose": "subtle",
    "inspiration": "subtle",
}


def is_valid_influence(level: str) -> bool:
    return level in INFLUENCE_LEVELS
