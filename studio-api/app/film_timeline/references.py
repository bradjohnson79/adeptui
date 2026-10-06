"""Film Timeline reference tags. Same Adept grammar as Timed Prompt sheets.

@ character, # environment, % prop, * video, & audio.
"""

from __future__ import annotations

import re

from .contracts import ReferenceAsset

_PREFIX = {
    "character": "@",
    "environment": "#",
    "prop": "%",
    "video": "*",
    "audio": "&",
}
_ALLOWED = frozenset(_PREFIX)


def normalize_reference_type(raw: str | None) -> str:
    token = str(raw or "").strip().lower()
    if token in {"location", "place", "scene"}:
        return "environment"
    if token in {"vehicle"}:
        return "prop"
    if token in {"voice", "music"}:
        return "audio"
    if token in {"motion"}:
        return "video"
    if token in _ALLOWED:
        return token
    return "image"


def canonical_tag(ref_type: str, raw: str) -> str:
    kind = normalize_reference_type(ref_type)
    prefix = _PREFIX.get(kind)
    if not prefix:
        raise ValueError("TAG_TYPE")
    stripped = re.sub(r"^[@#%*&~]+", "", str(raw or "").strip())
    words = re.sub(r"[^A-Za-z0-9]+", " ", stripped).split()
    if not words:
        raise ValueError("TAG_REQUIRED")
    alias = "".join(part[:1].upper() + part[1:] for part in words)
    alias = re.sub(r"[^A-Za-z0-9]", "", alias)
    if not alias:
        raise ValueError("TAG_REQUIRED")
    return f"{prefix}{alias}"


def duplicate_tag(references: list[ReferenceAsset], tag: str, *, except_id: str = "") -> ReferenceAsset | None:
    needle = tag.strip().lower()
    for item in references:
        if except_id and item.id == except_id:
            continue
        if (item.tag or "").strip().lower() == needle:
            return item
    return None


def generation_role(ref_type: str) -> str:
    """How a stored Timeline reference reaches MiniMax H3 picture slots."""

    return {
        "character": "character",
        "environment": "place",
        "prop": "prop",
        "video": "video",
        "audio": "audio",
        "first_frame": "prior_frame",
        "storyboard": "reference",
        "image": "reference",
    }.get(str(ref_type or ""), "reference")


def provider_reference_slots(references: list[ReferenceAsset], capabilities) -> list[ReferenceAsset]:
    """Stored references the selected model is allowed to receive."""

    video_ok = bool(getattr(capabilities, "supportsVideoReferences", False))
    audio_ok = bool(getattr(capabilities, "supportsAudioReferences", False))
    kept: list[ReferenceAsset] = []
    for item in references:
        if not item.assetId:
            continue
        if item.type == "video" and not video_ok:
            continue
        if item.type == "audio" and not audio_ok:
            continue
        kept.append(item)
    return kept


def apply_cancelled_segment(segment) -> None:
    """A cancelled render is not finished media and has no continuity packet."""

    segment.status = "cancelled"
    segment.assetId = None
    segment.lastFrameAssetId = None
    segment.firstFrameAssetId = None
    meta = segment.generationMetadata
    meta.pop("continuity", None)
    meta.pop("submission", None)
    meta.pop("requestKey", None)
    meta.pop("retakePreviousContinuity", None)
