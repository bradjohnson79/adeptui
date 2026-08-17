"""Environment Visual Canon — Co-Director vision analysis (ERS image-to-image).

The authoritative environment image is inspected once by the hosted vision
transport (chat_kie — the same provider the ERS semantic gate uses; no second
vision architecture) and reduced to structured, uncertainty-marked continuity
data that every ERS panel shares.

Persistence reuses the canonical ProjectTraitRow store (spatial_map
ers_persistence) — no second environment database. Creator-authored
corrections outrank inferred vision output (merge_visual_canon). Staleness
reuses the Scene Intent grounding fingerprint (lineage_fingerprint).

Honesty contract: when no vision provider is configured or the analysis
fails, availability="unavailable" with a reason — nothing is invented and the
canon never pretends to have seen the image.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CANON_CATEGORY = "environment_visual_canon"
CANON_VERSION = 1

ENVIRONMENT_VISUAL_CANON_PROMPT = (
    "Inspect the authoritative environment image as a production designer and continuity "
    "supervisor. Extract the physical characteristics that must remain invariant across future "
    "camera views. Focus on architecture, geometry, doors, windows, counters, fixed furniture, "
    "fixtures, materials, lighting, and spatial relationships. Distinguish persistent environment "
    "elements from people and temporary action. Do not redesign or embellish the environment. "
    "Mark uncertain observations explicitly. Return structured environment continuity data "
    "suitable for generating multiple views of the exact same physical location. "
    'Respond with ONLY a JSON object shaped like: {"identity": {"environmentType": "...", '
    '"architecturalStyle": "...", "dominantMaterials": ["..."], "colorPalette": ["..."], '
    '"lightingCharacter": "..."}, "geometry": {"roomShape": "...", "wallRelationships": "...", '
    '"windowLocations": ["..."], "doorOrEntranceLocations": ["..."], "circulation": "..."}, '
    '"fixedArchitecture": {"serviceCounterOrBar": {"location": "...", "shape": "...", '
    '"orientation": "..."}, "shelving": "...", "cabinetry": "...", "builtIns": "...", '
    '"permanentFixtures": ["..."]}, "furniture": {"couch": {"present": true, "location": "..."}, '
    '"tables": ["..."], "chairs": ["..."], "stools": ["..."], "displayCases": ["..."], '
    '"plants": ["..."], "majorLamps": ["..."], "majorDecor": ["..."]}, '
    '"spatialRelationships": ["..."], "hardInvariants": ["..."], "uncertainty": ["..."]}. '
    "For anything not confidently visible, put it in \"uncertainty\" instead of guessing."
)


class EnvironmentVisualCanon(BaseModel):
    """Structured, uncertainty-marked visual continuity data for one environment."""

    version: int = CANON_VERSION
    availability: str = "unavailable"  # available | unavailable
    unavailableReason: str = ""
    sourceAssetId: str = ""
    mapId: str = ""
    sceneIntentVersion: Optional[int] = None
    groundingFingerprint: str = ""
    fingerprint: str = ""
    analyzedAt: str = ""
    provenance: str = ""  # co_director_vision | creator_corrected
    identity: dict[str, Any] = Field(default_factory=dict)
    geometry: dict[str, Any] = Field(default_factory=dict)
    fixedArchitecture: dict[str, Any] = Field(default_factory=dict)
    furniture: dict[str, Any] = Field(default_factory=dict)
    materials: dict[str, Any] = Field(default_factory=dict)
    lighting: dict[str, Any] = Field(default_factory=dict)
    spatialRelationships: list[str] = Field(default_factory=list)
    hardInvariants: list[str] = Field(default_factory=list)
    forbiddenChanges: list[str] = Field(default_factory=list)
    sourceAuthority: dict[str, Any] = Field(default_factory=dict)
    factStatus: dict[str, str] = Field(default_factory=dict)
    uncertainty: list[str] = Field(default_factory=list)


def canon_fingerprint(canon: EnvironmentVisualCanon) -> str:
    """Stable fingerprint of the canon CONTENT (excludes analysis provenance)."""
    payload = {
        "identity": canon.identity,
        "geometry": canon.geometry,
        "fixedArchitecture": canon.fixedArchitecture,
        "furniture": canon.furniture,
        "spatialRelationships": canon.spatialRelationships,
        "hardInvariants": canon.hardInvariants,
        "uncertainty": canon.uncertainty,
    }
    if canon.materials:
        payload["materials"] = canon.materials
    if canon.lighting:
        payload["lighting"] = canon.lighting
    if canon.forbiddenChanges:
        payload["forbiddenChanges"] = canon.forbiddenChanges
    if canon.factStatus:
        payload["factStatus"] = canon.factStatus
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def canon_is_stale(canon: EnvironmentVisualCanon | None, current_grounding_fingerprint: str) -> bool:
    """True when the source lineage moved since the canon was analyzed."""
    if canon is None:
        return True
    if not current_grounding_fingerprint:
        return False
    return str(canon.groundingFingerprint or "") != str(current_grounding_fingerprint)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort JSON object extraction from a VLM response."""
    raw = (text or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_visual_canon_output(text: str) -> EnvironmentVisualCanon | None:
    """Parse a structured canon from the VLM response. None when unparseable."""
    data = _extract_json_object(text)
    if not data:
        return None
    try:
        return EnvironmentVisualCanon.model_validate(data)
    except Exception as exc:
        logger.warning("Visual canon parse failed: %s", exc)
        return None


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


async def analyze_environment_visual_canon(
    *,
    project_id: str,
    source_asset_id: str,
    asset_path: str | Path,
    map_id: str = "",
    scene_intent_version: Optional[int] = None,
    grounding_fingerprint: str = "",
    model_id: str = "gemini-3-pro",
) -> EnvironmentVisualCanon:
    """One hosted vision call: authoritative environment image -> structured canon.

    Honest degrade: no vision provider / unreadable image / provider error all
    yield availability="unavailable" with the reason. Never invents content.
    """
    from ...secrets_store import get_secret
    from .ers_gate import _data_url

    base = EnvironmentVisualCanon(
        sourceAssetId=source_asset_id,
        mapId=map_id,
        sceneIntentVersion=scene_intent_version,
        groundingFingerprint=grounding_fingerprint,
        analyzedAt=_now(),
    )

    api_key = get_secret("kie_api_key")
    if not api_key:
        base.unavailableReason = "No vision-capable provider is configured."
        return base

    image_url = _data_url(Path(asset_path))
    if not image_url:
        base.unavailableReason = "The authoritative environment image could not be read."
        return base

    content: list[dict[str, Any]] = [
        {"type": "text", "text": ENVIRONMENT_VISUAL_CANON_PROMPT},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]
    try:
        from ...hosted_providers.adapters.kie_adapter import chat_kie

        response = await chat_kie(
            api_key,
            model_id=model_id,
            messages=[{"role": "user", "content": content}],
            temperature=0.0,
            timeout_sec=120.0,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Visual canon analysis call failed: %s", exc)
        base.unavailableReason = "The vision provider could not be reached."
        return base

    if not response.get("ok"):
        detail = str(
            response.get("message")
            or response.get("error")
            or (f"HTTP {response.get('httpStatus')}" if response.get("httpStatus") else "")
            or "The vision provider did not complete the analysis."
        )
        base.unavailableReason = detail[:300]
        return base

    parsed = parse_visual_canon_output(str(response.get("output") or ""))
    if parsed is None:
        base.unavailableReason = "The vision provider returned no parseable environment canon."
        return base

    parsed.version = CANON_VERSION
    parsed.availability = "available"
    parsed.sourceAssetId = source_asset_id
    parsed.mapId = map_id
    parsed.sceneIntentVersion = scene_intent_version
    parsed.groundingFingerprint = grounding_fingerprint
    parsed.analyzedAt = _now()
    parsed.provenance = "co_director_vision"
    parsed.fingerprint = canon_fingerprint(parsed)
    return parsed


def merge_visual_canon(
    base: EnvironmentVisualCanon | None,
    corrections: dict[str, Any] | None,
) -> EnvironmentVisualCanon | None:
    """Creator-authored corrections outrank inferred vision output.

    Corrections merge over the canon fields; the fingerprint is recomputed so a
    corrected canon is a new version. Returns None when there is nothing to
    merge onto.
    """
    if base is None and not corrections:
        return None
    merged = (
        base.model_copy(deep=True)
        if base is not None
        else EnvironmentVisualCanon(availability="unavailable", unavailableReason="No vision canon yet.")
    )
    if corrections:
        data = merged.model_dump(exclude={"fingerprint", "version", "provenance"})
        for key, value in corrections.items():
            if key in data and isinstance(value, (dict, list, str, int, float, bool)) and value not in (None, "", [], {}):
                data[key] = value
        merged = EnvironmentVisualCanon.model_validate(data)
        merged.version = CANON_VERSION + 1
        merged.provenance = "creator_corrected"
        merged.fingerprint = canon_fingerprint(merged)
    return merged


# ---------------------------------------------------------------------------
# Persistence — canonical ProjectTraitRow store (no second environment database)
# ---------------------------------------------------------------------------


def save_visual_canon(db, project_id: str, map_id: str, canon: EnvironmentVisualCanon) -> EnvironmentVisualCanon:
    from ...spatial_map.ers_persistence import _upsert_trait

    if not canon.fingerprint:
        canon.fingerprint = canon_fingerprint(canon)
    canon.mapId = map_id
    _upsert_trait(
        db,
        project_id=project_id,
        category=CANON_CATEGORY,
        key=map_id or canon.sourceAssetId,
        value=canon.model_dump_json(),
        provenance="co_director_vision",
    )
    return canon


def load_visual_canon(db, project_id: str, map_id: str) -> EnvironmentVisualCanon | None:
    from ...spatial_map.ers_persistence import _load_trait_value

    raw = _load_trait_value(db, project_id=project_id, category=CANON_CATEGORY, key=map_id)
    if not raw:
        return None
    try:
        return EnvironmentVisualCanon.model_validate_json(raw)
    except Exception as exc:
        logger.warning("Failed to load visual canon %s: %s", map_id, exc)
        return None
