"""Pixel-review dimensions for Sanitation Phase 1.

Existing vision validation is the reviewer. This module only states the
required dimensions so metadata-only reviews cannot claim PASS.
"""

from __future__ import annotations

from typing import Any

PIXEL_REVIEW_DIMENSIONS = (
    "IDENTITY",
    "PLACEMENT",
    "ENVIRONMENT",
    "PERFORMANCE",
    "CAMERA",
)


def pixel_review_instructions(
    *,
    character_name: str = "the character",
    scene_name: str = "the established scene",
    placement: str = "behind the barista counter",
    performance: str = "standing, relaxed, facing the customer side",
    camera: str = "preserve the established scene relationship",
) -> str:
    return (
        "Visually inspect the generated image. Metadata is not evidence.\n"
        f"IDENTITY: Does the generated character match approved {character_name}?\n"
        f"PLACEMENT: Is {character_name} {placement}?\n"
        f"ENVIRONMENT: Is this {scene_name}?\n"
        f"PERFORMANCE: Is the pose consistent with '{performance}' "
        "(semantic intent, not pixel-perfect mannequin angles)? "
        "Fail if sitting, in front of the counter, back turned, or unrelated action.\n"
        f"CAMERA: Does the requested camera {camera}?\n"
        "Respond with JSON: "
        '{"identity":"pass|fail","placement":"pass|fail","environment":"pass|fail",'
        '"performance":"pass|fail","camera":"pass|fail","notes":"..."}'
    )


def all_dimensions_present(review: dict[str, Any]) -> bool:
    return all(str(review.get(k.lower()) or review.get(k) or "").strip() for k in PIXEL_REVIEW_DIMENSIONS)
