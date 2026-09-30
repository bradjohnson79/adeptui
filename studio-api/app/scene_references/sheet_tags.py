"""Frozen Timeline R2V sheet-tag contract (Law #16).

Prefix IS the type. One PascalCase token. No spaces.

  @  CRS  Character Reference Sheet
  #  ERS  Environment Reference Sheet
  %  PRS  Prop Reference Sheet
  *  video / motion (unchanged)
  &  audio / voice reference (conditioning; not Timeline Audio clip)
  ~  Generic Image (Image Generator "Other Image References" authority)

Front stills / hero_identity are Image-to-Video only.
Last-frame continuity is not a subject and not a place.

The ~ generic-image sigil is an Image Generator provenance/authority tag.
It is NOT a Timeline R2V binding prefix: r2v_role stays "reference" and the
Timeline reference grammar (@ # % *) is unchanged.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

PREFIX_CRS = "@"
PREFIX_ERS = "#"
PREFIX_PRS = "%"
PREFIX_VIDEO = "*"
PREFIX_AUDIO = "&"
PREFIX_GENERIC_IMAGE = "~"
ALL_PREFIXES = frozenset({PREFIX_CRS, PREFIX_ERS, PREFIX_PRS, PREFIX_VIDEO, PREFIX_AUDIO, PREFIX_GENERIC_IMAGE})
# Binding prefixes accepted by the Timeline R2V grammar (one architecture).
R2V_BINDING_PREFIXES = frozenset({PREFIX_CRS, PREFIX_ERS, PREFIX_PRS, PREFIX_VIDEO, PREFIX_AUDIO})
GENERIC_IMAGE_REFERENCE_TYPE = "generic_image"

# Live MiniMaxH3ReferenceToVideo: LoadImage → ref_image_0..ref_image_8 (max 9).
# Timeline H3 owner dialect binds characters with lowercase <subject N> is Name.
# N is 1-based and matches ref_image_(N-1). Picture tokens may annotate places /
# continuity when present; orphan trailing <Picture N> lists are not the binding.
H3_LIVE_SUBJECT_TOKEN = "subject"
H3_LIVE_PICTURE_TOKEN = "Picture"
H3_LIVE_AUDIO_TOKEN = "Audio"
H3_LIVE_VIDEO_TOKEN = "Video"

CRS_MARKERS = (
    "character_sheet",
    "crs",
    "composed_sheet",
    "character_reference_sheet",
)
ERS_MARKERS = (
    "environment_reference_sheet",
    "production_ers",
    "ers_composite",
    "ers_sheet",
    "environment-reference",
    "codirectorers",
)
PRS_MARKERS = (
    "prop_reference_sheet",
    "prs",
)
PLACE_FALLBACK_MARKERS = (
    "venture-corridor",
    "venture_corridor",
    "venture corridor",
    "environment",
    "location",
)
FRONT_STILL_MARKERS = (
    "hero_identity",
    "character_reference",
    "front.png",
    " front ",
)

# Spatial Map / Scene Creator still mention #prop-tag (kebab). Timeline R2V
# uses %PascalCase. Do not rewrite those surfaces in this journey.
LEFTOVER_HASH_PROP_TAG_CALLERS = (
    "studio-api/app/codirector/entity_resolver.py (_PROP_TAG_RE, leftover #kebab)",
    "studio-api/app/spatial_map/ers_contracts.py (normalize_prop_tag)",
    "studio-web/src/components/CoDirector/SpatialMap/EntityPicker.tsx",
)

_NON_TOKEN = re.compile(r"[^A-Za-z0-9]")


@dataclass(frozen=True)
class SheetClassification:
    kind: str  # crs | ers | prs | video | front_still | unknown
    prefix: str
    reference_type: str
    media_kind: str
    r2v_role: str
    alias: str


def pascal_alias(raw: str | None, fallback: str = "Reference") -> str:
    token = (raw or "").strip()
    if token[:1] in ALL_PREFIXES:
        token = token[1:]
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", token) if p]
    if not parts:
        return fallback
    out = "".join(p[:1].upper() + p[1:] for p in parts)
    return _NON_TOKEN.sub("", out) or fallback


def strip_sheet_prefix(raw: str) -> str:
    token = (raw or "").strip()
    if token[:1] in ALL_PREFIXES:
        return token[1:].strip()
    return token


def prefix_for_reference(reference_type: str | None, media_kind: str | None = None) -> str:
    blob = f"{reference_type or ''} {media_kind or ''}".strip().lower()
    if "audio" in blob or "voice" in blob:
        return PREFIX_AUDIO
    if "video" in blob or blob.strip() == "motion":
        return PREFIX_VIDEO
    if (reference_type or "") in {"character", "wardrobe", "creature"}:
        return PREFIX_CRS
    if (reference_type or "") in {"environment", "location"}:
        return PREFIX_ERS
    if (reference_type or "") in {"prop", "vehicle"}:
        return PREFIX_PRS
    if (reference_type or "") == GENERIC_IMAGE_REFERENCE_TYPE:
        return PREFIX_GENERIC_IMAGE
    if media_kind == "entity":
        return PREFIX_CRS
    if media_kind == "video":
        return PREFIX_VIDEO
    return PREFIX_ERS


def display_sheet_token(alias: str, reference_type: str | None, media_kind: str | None = None) -> str:
    token = pascal_alias(alias)
    if not token:
        return ""
    return f"{prefix_for_reference(reference_type, media_kind)}{token}"


def _labels_text(asset: Any) -> str:
    raw_labels = getattr(asset, "labels_json", None)
    if isinstance(raw_labels, list):
        return " ".join(str(item) for item in raw_labels)
    if isinstance(raw_labels, str) and raw_labels.strip():
        try:
            parsed = json.loads(raw_labels)
            if isinstance(parsed, list):
                return " ".join(str(item) for item in parsed)
            return str(parsed)
        except Exception:
            return raw_labels
    return ""


def _blob_for_asset(asset: Any) -> str:
    meta = str(getattr(asset, "prompt_meta_json", "") or "")
    return " ".join(
        (
            str(getattr(asset, "tag", "") or ""),
            str(getattr(asset, "filename", "") or ""),
            str(getattr(asset, "kind", "") or ""),
            _labels_text(asset),
            meta,
        )
    ).lower()


def _sheet_identity(asset: Any) -> str:
    """Tag, filename, and labels only.

    Generation prompt prose is not a sheet type. A prop prompt that says
    "no environment scene" must not become an environment reference.
    """
    return " ".join(
        (
            str(getattr(asset, "tag", "") or ""),
            str(getattr(asset, "filename", "") or ""),
            _labels_text(asset),
        )
    ).lower()


def classify_asset(asset: Any, *, preferred_alias: str | None = None) -> SheetClassification:
    kind = str(getattr(asset, "kind", "") or "").lower()
    filename = str(getattr(asset, "filename", "") or "")
    tag = str(getattr(asset, "tag", "") or "")
    blob = _blob_for_asset(asset)
    identity = _sheet_identity(asset)
    tag_key = tag.lower().strip()
    prop_sheet = (
        tag_key.startswith("prop_")
        or tag_key.startswith("prop-")
        or "approved_prop" in identity
        or "project_prop" in identity
        or "prop_view" in identity
        or "prop_reference_sheet" in identity
    )
    alias_src = preferred_alias or tag or filename or "Reference"

    if kind == "audio":
        return SheetClassification(
            kind="audio",
            prefix=PREFIX_AUDIO,
            reference_type="audio",
            media_kind="audio",
            r2v_role="audio",
            alias=pascal_alias(alias_src, "Audio"),
        )

    if kind == "video":
        return SheetClassification(
            kind="video",
            prefix=PREFIX_VIDEO,
            reference_type="video",
            media_kind="video",
            r2v_role="video",
            alias=pascal_alias(alias_src, "Video"),
        )

    if any(marker in blob for marker in CRS_MARKERS):
        return SheetClassification(
            kind="crs",
            prefix=PREFIX_CRS,
            reference_type="character",
            media_kind="entity",
            r2v_role="character",
            alias=pascal_alias(alias_src, "Character"),
        )
    if prop_sheet or any(marker in blob for marker in PRS_MARKERS) or "project_prop" in blob:
        return SheetClassification(
            kind="prs",
            prefix=PREFIX_PRS,
            reference_type="prop",
            media_kind="entity",
            r2v_role="prop",
            alias=pascal_alias(alias_src, "Prop"),
        )
    if any(marker in blob for marker in FRONT_STILL_MARKERS):
        return SheetClassification(
            kind="front_still",
            prefix="",
            reference_type="character",
            media_kind="image",
            r2v_role="character",
            alias=pascal_alias(alias_src, "Front"),
        )
    if any(marker in blob for marker in ERS_MARKERS) or any(
        marker in identity for marker in PLACE_FALLBACK_MARKERS
    ):
        return SheetClassification(
            kind="ers",
            prefix=PREFIX_ERS,
            reference_type="environment",
            media_kind="image",
            r2v_role="place",
            alias=pascal_alias(alias_src, "Place"),
        )
    if kind == "image":
        return SheetClassification(
            kind="unknown",
            prefix=PREFIX_ERS,
            reference_type="image",
            media_kind="image",
            r2v_role="reference",
            alias=pascal_alias(alias_src, "Image"),
        )
    return SheetClassification(
        kind="unknown",
        prefix="",
        reference_type="other",
        media_kind="image",
        r2v_role="reference",
        alias=pascal_alias(alias_src, "Reference"),
    )


def r2v_role_for_reference(reference_type: str | None, role: str | None = None, kind: str | None = None) -> str:
    blob = f"{reference_type or ''} {role or ''} {kind or ''}".lower()
    if "voice" in blob or blob.strip() == "audio":
        return "audio"
    if "video" in blob or "motion" in blob:
        return "video"
    if any(part in blob for part in ("character", "crs", "hero", "identity")):
        return "character"
    if any(part in blob for part in ("environment", "location", "ers", "place", "scene")):
        return "place"
    if "prop" in blob or "prs" in blob:
        return "prop"
    if any(part in blob for part in ("prior", "last_frame", "continuity", "previous")):
        return "prior_frame"
    return "reference"
