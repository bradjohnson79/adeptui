"""Adept UI v1.1 Spatial/3D shelf — Co-Director routing / knowledge gate.

Shelve ≠ delete. Spatial Map, PoseCraft, Fire3D, and SceneCraft tools and
project data stay for v1.2 Cloud / SceneCraft. Creator-facing recommendation
and execution are gated here.

Zero creator-facing presence: do not speak the names Spatial Map, PoseCraft,
Fire3D, or SceneCraft. Stale asks navigate silently to the v1.1 authority:

- Spatial Map / aliases → Environment Creator
- PoseCraft / Fire3D / SceneCraft → Image Generator
"""

from __future__ import annotations

import re
from typing import Literal

# Product gates (mirrors Frontend Integrity shelved_v1_1). Flip only when the
# surface returns as an active creator destination.
SPATIAL_MAP_SHELVED_V1_1 = True
POSECRAFT_SHELVED_V1_1 = True
FIRE3D_SHELVED_V1_1 = True
SCENECRAFT_SHELVED_V1_1 = True

SpatialShelfKind = Literal["open_environment_creator", "open_image_generator", ""]

ENVIRONMENT_CREATOR_OPEN_REPLY = "Opening Environment Creator."
IMAGE_GENERATOR_OPEN_REPLY = "Opening Image Generator."

# Kept for import compatibility. Must not name shelved systems.
def spatial_map_shelved_reply(message: str = "") -> str:
    del message
    return ENVIRONMENT_CREATOR_OPEN_REPLY


_SPATIAL_MAP_ASK_RE = re.compile(
    r"(?:"
    r"\b(?:open|show|switch to|take me to|go to|bring up|launch|load|use)\b.+\bspatial\s+map\b"
    r"|"
    r"\bspatial\s+map\b.+\b(?:open|where|available|active|enabled|missing|gone|shelved)\b"
    r"|"
    r"\b(?:where is|what happened to|what is|what does|what's|whats|is there|do we (?:still )?have)\b.+\bspatial\s+map\b"
    r"|"
    r"^\s*spatial\s+map\s*[?.!]?\s*$"
    r"|"
    r"\buse\s+(?:the\s+)?spatial\s+map\b"
    r")",
    re.I,
)

_CREATE_ENVIRONMENT_RE = re.compile(
    r"(?:"
    r"\b(?:create|make|build|design|plan|set\s+up|setup)\b.+\b(?:an?\s+)?(?:new\s+)?environment\b"
    r"(?!\s+reference\s+(?:sheet|package))"
    r"|"
    r"\b(?:create|make|build|design|plan)\b.+\b(?:mess\s+hall|canteen|galley|corridor|set|location|place)\b.+\benvironment\b"
    r"|"
    r"\b(?:mess\s+hall|canteen|galley)\s+environment\b"
    r"|"
    r"\bcreate\b.+\bmess\s+hall\b"
    r"|"
    r"\b(?:open|show|switch to|take me to|go to|bring up|launch)\b.+\benvironment\s+creator\b"
    r"|"
    r"\benvironment\s+creator\b"
    r"|"
    r"\bneed\b.+\b(?:an?\s+)?(?:mess\s+hall\s+)?environment\b"
    r")"
    r"(?!.*\b(?:shots?|images?|stills?|frames?)\b)",
    re.I,
)

_CREATE_SPATIAL_MAP_RE = re.compile(
    r"(?:"
    r"\b(?:create|generate|make|build|turn|convert)\b.+\bspatial\s+map\b"
    r"|"
    r"\b(?:create|generate|make|build)\b.+\b(?:an?\s+)?atlas\b"
    r"|"
    r"\bturn\b.+\binto\b.+\b(?:an?\s+)?(?:atlas|spatial\s+map)\b"
    r")",
    re.I,
)

_POSECRAFT_ASK_RE = re.compile(
    r"(?:"
    r"\b(?:open|show|switch to|take me to|go to|bring up|launch|load|use)\b.+\bpose\s*craft\b"
    r"|"
    r"\bpose\s*craft\b.+\b(?:open|where|available|active|enabled|missing|gone|shelved)\b"
    r"|"
    r"\b(?:where is|what happened to|is there|do we (?:still )?have|what is)\b.+\bpose\s*craft\b"
    r"|"
    r"^\s*pose\s*craft\s*[?.!]?\s*$"
    r"|"
    r"\bopen\s+[A-Za-z][\w'-]*\s+in\s+pose\s*craft\b"
    r")",
    re.I,
)

_FIRE3D_ASK_RE = re.compile(
    r"(?:"
    r"\bfire\s*3d\b"
    r"|"
    r"\bwsl2\b.+\bfire\b"
    r")",
    re.I,
)

_SCENECRAFT_ASK_RE = re.compile(
    r"\bscene\s*craft\b",
    re.I,
)


def classify_v11_spatial_shelf_intent(message: str) -> SpatialShelfKind:
    """Return shelf routing kind for Adept UI v1.1 Co-Director.

    Order:
    1) create-environment / Environment Creator → open Express
    2) Spatial Map ask / create-spatial-map → Environment Creator (silent)
    3) PoseCraft / Fire3D / SceneCraft ask → Image Generator (silent)
    """
    text = (message or "").strip()
    if not text:
        return ""
    # A Timeline scene-production request is never an environment-creation
    # navigation — even when it names an environment reference sheet as the
    # setting ("create a Timeline prompt ... using the Venture Corridor Scene
    # environment reference sheet"). The create-environment patterns exist for
    # creators asking to BUILD an environment asset, not to shoot a scene in one.
    try:
        from .generation_authority import classify_generation_authority

        authority = classify_generation_authority(text)
        if authority is not None and str(getattr(authority, "owner", "") or "") == "timeline":
            return ""
    except Exception:
        pass
    if SPATIAL_MAP_SHELVED_V1_1 and _CREATE_ENVIRONMENT_RE.search(text):
        return "open_environment_creator"
    if SPATIAL_MAP_SHELVED_V1_1 and (
        _SPATIAL_MAP_ASK_RE.search(text) or _CREATE_SPATIAL_MAP_RE.search(text)
    ):
        return "open_environment_creator"
    if POSECRAFT_SHELVED_V1_1 and _POSECRAFT_ASK_RE.search(text):
        return "open_image_generator"
    if FIRE3D_SHELVED_V1_1 and _FIRE3D_ASK_RE.search(text):
        return "open_image_generator"
    if SCENECRAFT_SHELVED_V1_1 and _SCENECRAFT_ASK_RE.search(text):
        return "open_image_generator"
    return ""


def is_spatial_map_creator_execution_gated() -> bool:
    """True when Co-Director must not recommend/execute Spatial Map for creators."""
    return SPATIAL_MAP_SHELVED_V1_1


def is_posecraft_creator_execution_gated() -> bool:
    """True when Co-Director must not recommend/execute PoseCraft for creators."""
    return POSECRAFT_SHELVED_V1_1


def is_fire3d_creator_execution_gated() -> bool:
    return FIRE3D_SHELVED_V1_1


def is_scenecraft_creator_execution_gated() -> bool:
    return SCENECRAFT_SHELVED_V1_1


def environment_creator_content_tab() -> str:
    """Canonical Express content tab id (Scene Creator UX rename → Environment Creator)."""
    return "scene_creator"


def image_generator_workspace_id() -> str:
    """FE workspaces.imagegen id (ProjectEditor tab). Not a Co-Director contentTab."""
    return "imagegen"


def shelf_open_reply(kind: SpatialShelfKind) -> str:
    if kind == "open_image_generator":
        return IMAGE_GENERATOR_OPEN_REPLY
    if kind == "open_environment_creator":
        return ENVIRONMENT_CREATOR_OPEN_REPLY
    return ""
