"""Film Timeline Director-native reference package.

Plain dicts / local helpers for MiniMax H3 Director (and other FT generators).
Director-native plain dicts only. W46 r2v.py stays Class C product authority;
Film Timeline must not treat it as FT request-build authority.
"""

from __future__ import annotations

from typing import Any

# Role priority for ranking (character > prior_frame > place > …). Mirrors the
# W46 ranking order so pictureIndex assignment stays stable for @Name ordering.
_ROLE_PRIORITY = {
    "character": 0,
    "prior_frame": 1,
    "place": 2,
    "prop": 3,
    "style": 4,
    "reference": 5,
    "video": 6,
    "audio": 7,
}

_VISUAL_ORDER = ("character", "place", "prop", "prior_frame", "style", "reference")


def make_ref_slot(
    *,
    role: str,
    asset_id: str,
    label: str = "",
    identity_id: str | None = None,
    picture_index: int | None = None,
    audio_index: int | None = None,
    video_index: int | None = None,
) -> dict[str, Any]:
    """One reference slot as a plain dict (Director-native; no Pydantic class)."""
    return {
        "role": str(role or "reference"),
        "assetId": str(asset_id or "").strip(),
        "label": str(label or ""),
        "identityId": identity_id,
        "pictureIndex": picture_index,
        "audioIndex": audio_index,
        "videoIndex": video_index,
        "appearance": "",
        "aliases": [],
    }


def _preferred_slot(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    if existing is None:
        return incoming
    if _ROLE_PRIORITY.get(str(incoming.get("role") or ""), 99) < _ROLE_PRIORITY.get(
        str(existing.get("role") or ""), 99
    ):
        return incoming
    return existing


def assign_picture_indices(
    slots: list[dict[str, Any]],
    *,
    skip_prior_frame: bool = False,
) -> list[dict[str, Any]]:
    """Assign pictureIndex / audioIndex / videoIndex on plain slot dicts.

    Preserves 9/3/3 ref budget ordering: character → place → prop → prior_frame…
    then audio / video extras. Does not import W46 r2v.
    """
    visual = [s for s in slots if str(s.get("role") or "") not in {"video", "audio"}]
    winners: dict[str, dict[str, Any]] = {}
    for slot in visual:
        aid = str(slot.get("assetId") or "").strip()
        if not aid:
            continue
        winners[aid] = _preferred_slot(winners.get(aid), slot)

    ranked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for role in _VISUAL_ORDER:
        for slot in winners.values():
            aid = str(slot.get("assetId") or "").strip()
            if str(slot.get("role") or "") != role or aid in seen:
                continue
            seen.add(aid)
            ranked.append(dict(slot))

    extras = [dict(s) for s in slots if str(s.get("role") or "") in {"video", "audio"}]
    ranked.extend(extras)

    index = 1
    for slot in ranked:
        role = str(slot.get("role") or "")
        if role in {"video", "audio"}:
            slot["pictureIndex"] = None
            continue
        if skip_prior_frame and role == "prior_frame":
            slot["pictureIndex"] = None
            continue
        slot["pictureIndex"] = index
        index += 1

    audio_index = 1
    for slot in ranked:
        if str(slot.get("role") or "") != "audio":
            continue
        slot["audioIndex"] = audio_index
        audio_index += 1

    video_index = 1
    for slot in ranked:
        if str(slot.get("role") or "") != "video":
            continue
        slot["videoIndex"] = video_index
        video_index += 1

    return ranked


def mechanism_token(generator_id: str) -> str:
    """Lightweight mechanism tag for job telemetry — not W46 compile authority."""
    token = (generator_id or "").strip().lower()
    if "minimax-h3" in token:
        return "h3_director"
    if token.startswith("ltx-2.5") or token.startswith("ltx-25"):
        return "ltx25_ref"
    return ""


def build_director_refs(
    slots: list[dict[str, Any]],
    *,
    mapped_start_asset_id: str | None = None,
    generator_id: str = "",
) -> dict[str, Any]:
    """Director-native reference package (plain dict; same slot shape as legacy dump)."""
    assigned = assign_picture_indices(list(slots))
    return {
        "slots": assigned,
        "mappedStartAssetId": mapped_start_asset_id,
        "mechanism": mechanism_token(generator_id),
        "promptPrefix": "",
        "disclosures": [],
        "tensorSlotCount": 0,
        "promptOnlyCount": 0,
    }


def slots_from_params(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Read reference slots from job params.

    Prefers providerOptions-style ``directorRefs``, then plain ``r2v`` dict.
    Never requires CanonicalR2VRequest.
    """
    for key in ("directorRefs", "r2v"):
        blob = params.get(key)
        if isinstance(blob, dict):
            raw = blob.get("slots") or []
            if isinstance(raw, list) and raw:
                return [item for item in raw if isinstance(item, dict)]
    return []
