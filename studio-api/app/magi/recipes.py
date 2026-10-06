"""MAGI edit recipes.

Same track-default and snap rules as the MAGI recipe drawer. Recipes never
replace clips, timing, or media.
"""

from __future__ import annotations

from typing import Any

RECIPE_IDS = (
    "music-video",
    "commercial",
    "interview",
    "podcast",
    "narrative",
    "trailer",
    "documentary",
    "anime",
    "cinematic",
    "social",
)

RECIPE_NAMES = {
    "music video": "music-video",
    "music-video": "music-video",
    "commercial": "commercial",
    "interview": "interview",
    "podcast": "podcast",
    "narrative": "narrative",
    "trailer": "trailer",
    "documentary": "documentary",
    "anime": "anime",
    "cinematic": "cinematic",
    "social": "social",
}


def canonical_recipe_id(value: str) -> str:
    key = " ".join(str(value or "").strip().lower().replace("_", " ").replace("-", " ").split())
    if key in RECIPE_NAMES:
        return RECIPE_NAMES[key]
    hyphen = key.replace(" ", "-")
    if hyphen in RECIPE_IDS:
        return hyphen
    return ""


def recipe_snap_enabled(recipe_id: str) -> bool:
    return recipe_id not in {"podcast", "documentary"}


def recipe_tracks(tracks: list[dict[str, Any]], recipe_id: str) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for track in tracks:
        row = dict(track)
        kind = str(row.get("kind") or "")
        if recipe_id == "podcast":
            row["muted"] = kind == "video"
            row["solo"] = kind == "audio"
            row["locked"] = False
        elif recipe_id in {"trailer", "anime", "music-video"}:
            row["muted"] = False
            row["solo"] = False
            row["locked"] = False
        elif recipe_id in {"interview", "documentary"}:
            row["muted"] = kind == "sfx"
            row["solo"] = False
            row["locked"] = False
        else:
            row["muted"] = False
            row["solo"] = False
            row["locked"] = False
        updated.append(row)
    return updated


def apply_recipe(sequence: dict[str, Any], recipe_id: str) -> dict[str, Any]:
    """Return a new sequence with recipe posture applied. Clips are copied unchanged."""
    canonical = canonical_recipe_id(recipe_id)
    if not canonical:
        raise ValueError(f"Unknown MAGI recipe '{recipe_id}'.")
    clips = [dict(clip) for clip in (sequence.get("clips") or [])]
    return {
        **sequence,
        "recipeId": canonical,
        "snapEnabled": recipe_snap_enabled(canonical),
        "tracks": recipe_tracks(list(sequence.get("tracks") or []), canonical),
        "clips": clips,
    }
