"""Classify Spatial Map environment-creation intent.

These routes solve different problems and must not be conflated:

- design: create a new environment (GPT Image 2 Atlas)
- designed_with_reference: design, using a photo only for look
- reconstruct: reconstruct an observed location (MoGe-2 / VGGT)
- supplied: use an existing Atlas as-is
"""

from __future__ import annotations

import re
from typing import Literal

SpatialEnvironmentRoute = Literal[
    "design",
    "designed_with_reference",
    "reconstruct",
    "supplied",
]

_SUPPLIED_RE = re.compile(
    r"("
    r"\buse\s+this\s+atlas\s+as[- ]is\b"
    r"|"
    r"\buse\s+(?:this|the|an|my)\s+existing\s+atlas\b"
    r"|"
    r"\buse\s+this\s+atlas\s+as[- ]?(?:the\s+)?(?:spatial\s+map|background)\b"
    r"|"
    r"\balready\s+have\s+(?:an?\s+)?(?:atlas|spatial\s+map)\b"
    r")",
    re.I,
)

_RECONSTRUCT_RE = re.compile(
    r"("
    r"\breconstruct\b"
    r"|"
    r"\bfrom\s+(?:this|the|my)\s+(?:location\s+)?image\b"
    r"|"
    r"\bfrom\s+(?:this|the)\s+(?:corridor|room|photo|photograph|master)\b"
    r"|"
    r"\bpreserve\s+this\s+exact\s+visible\s+layout\b"
    r"|"
    r"\bfree\s+local\b"
    r")",
    re.I,
)

_DESIGN_RE = re.compile(
    r"("
    r"\bcreate\s+a\s+new\b"
    r"|"
    r"\bdesign\b"
    r"|"
    r"\bfrom\s+(?:a\s+)?(?:written\s+)?description\b"
    r"|"
    r"\blook\s+like\s+this\s+reference\b"
    r"|"
    r"\bmake\s+(?:the\s+)?(?:new\s+)?atlas\s+look\s+like\b"
    r")",
    re.I,
)

_STYLE_REF_RE = re.compile(
    r"("
    r"\blook\s+like\s+this\s+reference\b"
    r"|"
    r"\bmake\s+(?:the\s+)?(?:new\s+)?atlas\s+look\s+like\b"
    r"|"
    r"\bstyle\s+reference\b"
    r"|"
    r"\bvisual\s+reference\b"
    r")",
    re.I,
)

_LAYOUT_LOCK_RE = re.compile(
    r"\bpreserve\s+this\s+exact\s+visible\s+layout\b",
    re.I,
)


def classify_spatial_environment_route(
    message: str,
    *,
    has_observed_image: bool = False,
    has_style_reference: bool = False,
    explicit_route: str = "",
) -> SpatialEnvironmentRoute:
    """Return one of the four product routes. Explicit user choice wins."""
    forced = (explicit_route or "").strip().lower()
    aliases = {
        "designed": "design",
        "design": "design",
        "designed_with_reference": "designed_with_reference",
        "reconstruct": "reconstruct",
        "reconstructed": "reconstruct",
        "supplied": "supplied",
        "assign": "supplied",
        "local": "reconstruct",
        "api": "design",
    }
    if forced in aliases:
        route = aliases[forced]
        if route == "design" and has_style_reference:
            return "designed_with_reference"
        return route  # type: ignore[return-value]

    text = (message or "").strip()
    if _LAYOUT_LOCK_RE.search(text):
        return "reconstruct"
    if _SUPPLIED_RE.search(text) and not _DESIGN_RE.search(text) and not _RECONSTRUCT_RE.search(text):
        return "supplied"
    if _RECONSTRUCT_RE.search(text) and not _STYLE_REF_RE.search(text):
        return "reconstruct"
    if _STYLE_REF_RE.search(text) or (has_style_reference and _DESIGN_RE.search(text)):
        return "designed_with_reference"
    if has_observed_image and not has_style_reference:
        return "reconstruct"
    if _DESIGN_RE.search(text):
        return "designed_with_reference" if has_style_reference else "design"
    if has_style_reference:
        return "designed_with_reference"
    return "design"


def geometry_source_for_route(route: str) -> str:
    if route in {"design", "designed", "designed_with_reference"}:
        return "designed"
    if route in {"reconstruct", "reconstructed"}:
        return "reconstructed"
    return "supplied"
