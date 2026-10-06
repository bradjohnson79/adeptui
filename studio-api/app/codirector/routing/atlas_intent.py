"""Atlas generate vs direct-assign intent — one source for every router.

Generate wins when the turn both mentions a reference and asks to create an
Atlas / Spatial Map. Assign-reference (character or image pipeline) must never
consume a create-atlas request.
"""

from __future__ import annotations

import re

from .v11_spatial_shelf import is_spatial_map_creator_execution_gated

# Create / transform — includes "atlas (top down shot)" and "create a spatial map".
_ATLAS_GENERATE_RE = re.compile(
    r"(?:"
    r"\b(?:create|generate|make|render|build|convert)\b.+\b(?:an?\s+)?atlas\b"
    r"|"
    r"\b(?:create|generate|make|render|build|turn|convert)\b.+\b(?:top[-\s]?down)\b.+\b(?:shot|atlas|reference|view|map)\b"
    r"|"
    r"\b(?:create|generate|make|render|build|turn|convert)\b.+\bspatial\s+map\b"
    r"|"
    r"\bturn\b.+\binto\b.+\b(?:an?\s+)?(?:atlas|spatial\s+map)\b"
    r"|"
    r"\broofless\s+(?:shot|map|view)\b"
    r")",
    re.I,
)

# Direct use of an existing Atlas / Spatial Map background. Must not fire when
# the same sentence asks to create/transform.
_ATLAS_ASSIGN_RE = re.compile(
    r"(?:"
    r"\buse\b.+\bas\s+(?:the\s+)?(?:spatial\s+map|map\s+background|background)\b"
    r"|"
    r"\buse\b.+\bexisting\s+atlas\b"
    r"|"
    r"\buse\b.+\bas\s+(?:the\s+)?(?:atlas(?:\s+shot)?|spatial\s+map)\s+reference\b"
    r"|"
    r"\b(?:set|assign)\b.+\bas\s+(?:the\s+)?(?:spatial\s+map|atlas(?:\s+shot)?)\b"
    r"|"
    r"\bupload\b.+\bas\s+(?:the\s+)?(?:spatial\s+map|atlas(?:\s+shot)?)\b"
    r"|"
    r"\buse\s+this\s+(?:map|atlas|image)\s+for\s+(?:the\s+)?(?:venture|spatial\s+map|map)\b"
    r")",
    re.I,
)

_CREATE_VERB_RE = re.compile(
    r"\b(?:create|generate|make|render|build|turn|convert)\b",
    re.I,
)


def is_atlas_generate_request(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(_ATLAS_GENERATE_RE.search(text))


def is_atlas_assign_request(message: str) -> bool:
    """True only for direct Atlas/Spatial Map use — not create-from-reference."""

    text = (message or "").strip()
    if not text:
        return False
    if is_atlas_generate_request(text):
        return False
    if _CREATE_VERB_RE.search(text) and re.search(r"\batlas\b", text, re.I):
        return False
    return bool(_ATLAS_ASSIGN_RE.search(text))


def atlas_capability_for_message(message: str) -> str:
    # Adept UI v1.1: do not advertise Spatial Map atlas flows while shelved.
    if is_spatial_map_creator_execution_gated():
        return ""
    if is_atlas_generate_request(message):
        return "atlas.generate"
    if is_atlas_assign_request(message):
        return "atlas.assign"
    return ""
