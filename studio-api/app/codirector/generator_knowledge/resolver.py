"""Resolve VideoGeneratorKnowledgeProfile by Production Control generator ID.

Dispatch is by profile id / prompt.dialect after lookup. Callers must not
branch on generator-name substrings (no `if "minimax"` dialect switches).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import yaml

from .schemas import VideoGeneratorKnowledgeProfile

PROFILES_DIR = Path(__file__).resolve().parent / "profiles"

# Production Control dock IDs (and live aliases) -> on-disk profile folder.
# Retired generators (wan-local, ltx-local, hunyuan-video-1.5-local) are NOT mapped here.
# Old projects that still reference a retired generator will get GENERATOR_KNOWLEDGE_UNAVAILABLE
# from resolve_profile, which is the honest answer for a retired generator.
PROFILE_KEYS: dict[str, str] = {
    "minimax-h3": "minimax-h3",
    "minimax-h3-local": "minimax-h3",
    "minimax-h3-t2v-local": "minimax-h3",
    "minimax-h3-i2v-local": "minimax-h3",
    "ltx-2.5-full": "ltx-2.5",
    "ltx-2.5-distilled": "ltx-2.5",
    "ltx-2.5-comfy": "ltx-2.5",
    "ltx_2_5_full": "ltx-2.5",
    "ltx_2_5_distilled": "ltx-2.5",
    "ltx_2_5_comfy": "ltx-2.5",
    "ltx-2.5": "ltx-2.5",
    "seedance-2.0": "seedance-api",
    "seedance-2.5": "seedance-api",
    "seedance-api": "seedance-api",
    "seedance-fal": "seedance-api",
    "fal_seedance": "seedance-api",
    "fal_seedance_25": "seedance-api",
    "kling-api": "kling-api",
    "kling-fal": "kling-api",
    "kling-kie": "kling-api",
    "veo-api": "veo-api",
    "veo-kie": "veo-api",
}

LAYER_NAMES = ("capability", "prompt", "workflow")


class ProfileResolveError(ValueError):
    pass


def canonical_profile_id(generator_id: Optional[str]) -> Optional[str]:
    token = str(generator_id or "").strip()
    if not token:
        return None
    return PROFILE_KEYS.get(token) or PROFILE_KEYS.get(token.lower())


def _layer_path(profile_dir: Path, name: str) -> Path:
    json_path = profile_dir / f"{name}.json"
    if json_path.is_file():
        return json_path
    yaml_path = profile_dir / f"{name}.yaml"
    if yaml_path.is_file():
        return yaml_path
    raise ProfileResolveError(
        f"GENERATOR_KNOWLEDGE_UNAVAILABLE: incomplete profile {profile_dir.name} (missing {name}.json)"
    )


def _read_layer(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if "{{" in raw or "{%" in raw or "!!python" in raw.lower():
        raise ProfileResolveError(f"rejected unsafe content in {path.name}")
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
    else:
        data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ProfileResolveError(f"{path} must be a mapping")
    return data


def load_profile_dir(profile_dir: Path) -> VideoGeneratorKnowledgeProfile:
    capability = _read_layer(_layer_path(profile_dir, "capability"))
    prompt = _read_layer(_layer_path(profile_dir, "prompt"))
    workflow = _read_layer(_layer_path(profile_dir, "workflow"))
    meta = {k: v for k, v in capability.items() if k in ("profileId", "displayName", "productionControlIds")}
    cap_body = {k: v for k, v in capability.items() if k not in meta}
    if not meta.get("profileId"):
        meta["profileId"] = profile_dir.name
    if not meta.get("displayName"):
        meta["displayName"] = profile_dir.name
    return VideoGeneratorKnowledgeProfile(
        profileId=str(meta["profileId"]),
        displayName=str(meta["displayName"]),
        productionControlIds=list(meta.get("productionControlIds") or [profile_dir.name]),
        capability=cap_body,
        prompt=prompt,
        workflow=workflow,
    )


def resolve_profile(generator_id: Optional[str]) -> VideoGeneratorKnowledgeProfile:
    profile_id = canonical_profile_id(generator_id)
    if not profile_id:
        raise ProfileResolveError(
            f"GENERATOR_KNOWLEDGE_UNAVAILABLE: no profile mapping for {generator_id!r}"
        )
    profile_dir = PROFILES_DIR / profile_id
    if not profile_dir.is_dir():
        raise ProfileResolveError(
            f"GENERATOR_KNOWLEDGE_UNAVAILABLE: profile dir missing for {profile_id}"
        )
    for name in LAYER_NAMES:
        _layer_path(profile_dir, name)
    return load_profile_dir(profile_dir)


def try_resolve_profile(
    generator_id: Optional[str],
) -> tuple[Optional[VideoGeneratorKnowledgeProfile], Optional[str]]:
    try:
        return resolve_profile(generator_id), None
    except (ProfileResolveError, OSError, yaml.YAMLError, json.JSONDecodeError) as exc:
        return None, str(exc)
