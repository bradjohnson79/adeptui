"""Load and resolve creator-facing domain profiles."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from app.codirector.foundation.contracts import DomainProfile

_REPO_ROOT = Path(__file__).resolve().parents[5]
_PROFILES_DIR = _REPO_ROOT / "config" / "codirector" / "domain-profiles"


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    for token in (" ", "-", "/"):
        normalized = normalized.replace(token, "_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def _trait_tokens(traits: Any) -> set[str]:
    tokens: set[str] = set()
    if traits is None:
        return tokens
    if isinstance(traits, str):
        tokens.add(_normalize(traits))
        return tokens
    if isinstance(traits, dict):
        for key, value in traits.items():
            if value:
                tokens.add(_normalize(str(key)))
                if isinstance(value, str):
                    tokens.add(_normalize(value))
        return tokens
    if isinstance(traits, (list, tuple, set)):
        for item in traits:
            if isinstance(item, str):
                tokens.add(_normalize(item))
            elif isinstance(item, dict):
                tokens |= _trait_tokens(item)
    return {token for token in tokens if token}


@lru_cache(maxsize=1)
def _index() -> dict[str, Any]:
    path = _PROFILES_DIR / "index.json"
    if not path.is_file():
        return {"profiles": []}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=32)
def _load_profile_file(file_key: str) -> Optional[DomainProfile]:
    path = _PROFILES_DIR / f"{file_key}.json"
    if not path.is_file():
        return None
    return DomainProfile.model_validate(json.loads(path.read_text(encoding="utf-8")))


def list_profiles() -> list[DomainProfile]:
    profiles: list[DomainProfile] = []
    for file_key in _index().get("profiles", []):
        profile = _load_profile_file(str(file_key))
        if profile is not None:
            profiles.append(profile)
    return profiles


def get_profile(profile_id: str) -> Optional[DomainProfile]:
    wanted = _normalize(profile_id)
    for profile in list_profiles():
        if _normalize(profile.profileId) == wanted:
            return profile
    return None


def _profile_tokens(profile: DomainProfile) -> set[str]:
    tokens = {_normalize(profile.profileId)}
    tokens.update(_normalize(slug) for slug in profile.projectTypeSlugs)
    return {token for token in tokens if token}


def resolve_profiles(primary_slug: str, subtype_slug: str | None = None, traits: Any = None) -> list[DomainProfile]:
    """Resolve a primary creative domain plus optional subtype/traits into profiles."""

    primary = _normalize(primary_slug)
    subtype = _normalize(subtype_slug)
    trait_tokens = _trait_tokens(traits)
    exact_tokens = [token for token in (primary, subtype) if token]
    all_tokens = set(exact_tokens) | trait_tokens

    ranked: list[tuple[int, str, DomainProfile]] = []
    for profile in list_profiles():
        tokens = _profile_tokens(profile)
        score = 0
        if primary and primary in tokens:
            score += 100
        if subtype and subtype in tokens:
            score += 80
        score += sum(20 for token in trait_tokens if token in tokens)
        if score == 0:
            continue
        if exact_tokens and _normalize(profile.profileId) == exact_tokens[0]:
            score += 5
        ranked.append((score, _normalize(profile.profileId), profile))

    ranked.sort(key=lambda item: (-item[0], item[1]))

    chosen: list[DomainProfile] = []
    seen_ids: set[str] = set()
    for _score, normalized_id, profile in ranked:
        if normalized_id in seen_ids:
            continue
        seen_ids.add(normalized_id)
        chosen.append(profile)

    if not chosen:
        custom = get_profile("custom")
        return [custom] if custom is not None else []

    return chosen


def clear_profile_cache() -> None:
    _index.cache_clear()
    _load_profile_file.cache_clear()
