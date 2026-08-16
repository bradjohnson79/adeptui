"""Scene Intent — compact semantic record snapshotted at Atlas creation.

Product law (Atlas Scene Intent addendum): no Atlas Shot exists without a
minimal environment intent record. Both creation paths converge here:

- CD-assisted: Co-Director summarizes the relevant conversation into the
  same contract before submitting atlas.generate.
- Manual/Express: the creator's short Scene / Location Description becomes
  the primary semantic field (deterministic — no extra LLM call).

The JSON is semantic context. The source image is visual context. The
Spatial Map is spatial context. ERS generation loads all three.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

from pydantic import BaseModel, Field

SCENE_INTENT_VERSION = 1
SCENE_INTENT_PURPOSE = "spatial_environment"

MIN_DESCRIPTION_CHARS = 12

# Exact-match blocklist (normalized). Light validation only — this is not a
# moderation system, just a guard against meaningless entries.
_GENERIC_DESCRIPTIONS = {
    "test",
    "room",
    "scene",
    "image",
    "atlas",
    "place",
    "location",
    "environment",
    "stuff",
    "thing",
    "asdf",
    "n/a",
    "none",
}

# Deterministic keyword → locationType inference. First match wins.
_LOCATION_TYPE_HINTS: tuple[tuple[str, str], ...] = (
    (r"\b(coffee|cafe|café|espresso|barista)\b", "coffee_shop"),
    (r"\b(restaurant|diner|bistro)\b", "restaurant"),
    (r"\b(bar|pub|tavern)\b", "bar"),
    (r"\b(office|workspace|studio)\b", "office"),
    (r"\b(bedroom|dorm)\b", "bedroom"),
    (r"\b(living room|lounge)\b", "living_room"),
    (r"\b(kitchen)\b", "kitchen"),
    (r"\b(street|alley|sidewalk|downtown)\b", "street"),
    (r"\b(forest|woods|park)\b", "outdoor_nature"),
    (r"\b(spaceship|space station|corridor)\b", "sci_fi_interior"),
    (r"\b(warehouse|factory|industrial)\b", "industrial"),
    (r"\b(shop|store|market|boutique)\b", "retail"),
    (r"\b(house|home|apartment)\b", "residential"),
)


class SceneIntent(BaseModel):
    """One contract for CD-assisted and manual Atlas creation."""

    version: int = SCENE_INTENT_VERSION
    purpose: str = SCENE_INTENT_PURPOSE
    sceneTitle: str = ""
    locationType: str = ""
    summary: str = ""
    productionIntent: str = ""
    keySubjects: list[str] = Field(default_factory=list)
    keyProps: list[str] = Field(default_factory=list)
    environmentTraits: list[str] = Field(default_factory=list)
    sourcePromptSummary: str = ""
    sourceReferenceAssetIds: list[str] = Field(default_factory=list)


class SceneDescriptionError(ValueError):
    """Creator-correctable description problem (surfaced as a 422)."""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def validate_scene_description(text: str) -> str:
    """Light validation. Returns the cleaned description or raises."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    normalized = _norm(cleaned)
    if not normalized:
        raise SceneDescriptionError(
            "A short Scene / Location Description is required before generating an Atlas Shot."
        )
    if len(normalized) < MIN_DESCRIPTION_CHARS:
        raise SceneDescriptionError(
            "Describe this location in a few more words — what kind of place is it and what is the scene for?"
        )
    if normalized in _GENERIC_DESCRIPTIONS:
        raise SceneDescriptionError(
            f'"{cleaned}" is too generic. Name the kind of place (e.g. "a warm neighborhood coffee shop for our commercial").'
        )
    return cleaned


def infer_location_type(text: str) -> str:
    """Deterministic keyword inference. Empty string when unknown — never invent."""
    normalized = _norm(text)
    for pattern, location_type in _LOCATION_TYPE_HINTS:
        if re.search(pattern, normalized):
            return location_type
    return ""


def _clean_names(items: Iterable[Any] | None, *, limit: int = 6) -> list[str]:
    out: list[str] = []
    for item in items or []:
        name = str(item).strip() if item is not None else ""
        if name and name not in out:
            out.append(name)
        if len(out) >= limit:
            break
    return out


def build_scene_intent(
    description: str,
    *,
    project_name: str = "",
    scene_title: str = "",
    location_type: str = "",
    production_intent: str = "",
    key_subjects: Iterable[Any] | None = None,
    key_props: Iterable[Any] | None = None,
    environment_traits: Iterable[Any] | None = None,
    source_reference_asset_ids: Iterable[Any] | None = None,
    originating_prompt: str = "",
) -> SceneIntent:
    """Deterministic builder. The creator's description is the semantic anchor.

    User words have priority: ``summary``/``sourcePromptSummary`` carry the
    creator's text verbatim; inference only fills ``locationType`` when the
    caller did not supply one.
    """
    cleaned = validate_scene_description(description)
    intent = SceneIntent(
        sceneTitle=(scene_title or "").strip() or (project_name or "").strip(),
        locationType=(location_type or "").strip() or infer_location_type(cleaned),
        summary=cleaned,
        productionIntent=(production_intent or "").strip()
        or "Spatial planning, environment continuity, ERS generation, and Scene Creator.",
        keySubjects=_clean_names(key_subjects),
        keyProps=_clean_names(key_props),
        environmentTraits=_clean_names(environment_traits),
        sourcePromptSummary=(originating_prompt or "").strip()[:600] or cleaned,
        sourceReferenceAssetIds=_clean_names(source_reference_asset_ids, limit=8),
    )
    return intent


def merge_scene_description_edit(
    existing: SceneIntent | None,
    new_description: str,
    *,
    project_name: str = "",
    fallback_source_reference_asset_ids: Iterable[Any] | None = None,
    originating_prompt: str = "",
) -> SceneIntent:
    """Edit Scene Description: update the description-derived fields while
    preserving the curated snapshot (subjects, props, traits, production
    intent, originating request). Without the merge, a typo fix would silently
    orphan the grounding lineage and permanently shift the staleness
    fingerprint even after restoring the original text."""
    cleaned = validate_scene_description(new_description)
    if existing is None:
        return build_scene_intent(
            cleaned,
            project_name=project_name,
            source_reference_asset_ids=fallback_source_reference_asset_ids,
            originating_prompt=originating_prompt,
        )
    return existing.model_copy(
        update={
            "summary": cleaned,
            "locationType": infer_location_type(cleaned) or existing.locationType,
            "sceneTitle": existing.sceneTitle or (project_name or "").strip(),
            "sourcePromptSummary": existing.sourcePromptSummary or (originating_prompt or "").strip()[:600],
        }
    )


def coerce_scene_intent(value: Any) -> SceneIntent | None:
    """Parse a stored/passed value into SceneIntent. None when absent or invalid."""
    if value is None:
        return None
    if isinstance(value, SceneIntent):
        return value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return None
    if not isinstance(value, dict):
        return None
    try:
        return SceneIntent.model_validate(value)
    except Exception:
        return None


def environment_intent_summary(intent: SceneIntent | None) -> str:
    """Concise multi-line summary for ERS prompts and the semantic verifier."""
    if intent is None:
        return ""
    parts: list[str] = []
    if intent.sceneTitle:
        parts.append(f"Scene: {intent.sceneTitle}")
    if intent.locationType:
        parts.append(f"Location type: {intent.locationType.replace('_', ' ')}")
    if intent.summary:
        parts.append(f"Environment intent: {intent.summary}")
    if intent.keySubjects:
        parts.append("Featured: " + ", ".join(intent.keySubjects))
    if intent.keyProps:
        parts.append("Key props: " + ", ".join(intent.keyProps))
    if intent.environmentTraits:
        parts.append("Environment traits: " + ", ".join(intent.environmentTraits))
    if intent.sourcePromptSummary and intent.sourcePromptSummary != intent.summary:
        parts.append(f"Originating request: {intent.sourcePromptSummary}")
    return "\n".join(parts)


def lineage_fingerprint(
    intent: SceneIntent | None,
    *,
    background_asset_id: str | None = None,
    original_reference_asset_id: str | None = None,
) -> str:
    """Stable fingerprint of the ERS grounding lineage. Used for staleness."""
    payload = {
        "intent": intent.model_dump() if intent is not None else None,
        "backgroundAssetId": background_asset_id or "",
        "originalEnvironmentReferenceAssetId": original_reference_asset_id or "",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def scene_intent_from_atlas_meta(prompt_meta: Any) -> SceneIntent | None:
    """Recover a SceneIntent stamped onto an Atlas asset's prompt_meta."""
    if isinstance(prompt_meta, str):
        try:
            prompt_meta = json.loads(prompt_meta)
        except (TypeError, json.JSONDecodeError):
            return None
    if not isinstance(prompt_meta, dict):
        return None
    return coerce_scene_intent(prompt_meta.get("sceneIntent"))
