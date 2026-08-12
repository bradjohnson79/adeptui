"""Provider + model + version Prompt Profile registry."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from .models import CertificationStatus, GenerationDomain, LanguageBalance, PromptLanguageStrategy

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PROFILES_DIR = _REPO_ROOT / "config" / "codirector" / "prompt-profiles"


class PromptProfile(BaseModel):
    profileId: str
    profileVersion: str
    providerId: str
    modelId: str
    modelVersion: Optional[str] = None
    generationDomain: GenerationDomain
    supportedLanguages: list[str] = Field(default_factory=lambda: ["en"])
    defaultStrategy: PromptLanguageStrategy = "english-only"
    bilingualCertified: bool = False
    recommendedLanguageModules: list[str] = Field(default_factory=lambda: ["en"])
    recommendedBalance: Optional[LanguageBalance] = None
    promptOrdering: str = "english-first"
    enabledRefinementModules: list[str] = Field(default_factory=list)
    maxPromptLength: Optional[int] = None
    negativePromptSupport: bool = True
    certificationStatus: CertificationStatus = "not_tested"
    notes: list[str] = Field(default_factory=list)

    @property
    def profileKey(self) -> str:
        return f"{self.profileId}@{self.profileVersion}"


def _default_profile(domain: GenerationDomain = "video") -> PromptProfile:
    return PromptProfile(
        profileId="generic-english",
        profileVersion="1.0",
        providerId="unknown",
        modelId="unknown",
        generationDomain=domain,
        supportedLanguages=["en"],
        defaultStrategy="english-only",
        recommendedLanguageModules=["en"],
        enabledRefinementModules=["production", "provider"],
        maxPromptLength=1800,
        certificationStatus="not_tested",
        notes=["Fallback profile — no matching provider/model profile found."],
    )


@lru_cache(maxsize=1)
def _load_index() -> dict[str, Any]:
    path = _PROFILES_DIR / "index.json"
    if not path.is_file():
        return {"aliases": {}, "profiles": []}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=32)
def _load_profile_file(profile_key: str) -> Optional[PromptProfile]:
    path = _PROFILES_DIR / f"{profile_key}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return PromptProfile.model_validate(data)


def list_profiles() -> list[PromptProfile]:
    index = _load_index()
    out: list[PromptProfile] = []
    for key in index.get("profiles") or []:
        profile = _load_profile_file(str(key))
        if profile:
            out.append(profile)
    return out


def resolve_profile(
    *,
    provider_id: Optional[str] = None,
    model_id: Optional[str] = None,
    model_version: Optional[str] = None,
    engine_id: Optional[str] = None,
    domain: GenerationDomain = "video",
) -> PromptProfile:
    index = _load_index()
    aliases: dict[str, Any] = index.get("aliases") or {}

    for candidate in (engine_id, provider_id, model_id):
        if not candidate:
            continue
        alias = aliases.get(str(candidate).strip())
        if alias and alias.get("profileKey"):
            profile = _load_profile_file(str(alias["profileKey"]))
            if profile:
                return profile

    # Direct profileId@version match attempt
    if model_id and model_version:
        key = f"{model_id}@{model_version}"
        profile = _load_profile_file(key)
        if profile:
            return profile

    # Scan for provider/model match
    for profile in list_profiles():
        if provider_id and profile.providerId == provider_id:
            if not model_id or profile.modelId == model_id:
                return profile
        if model_id and profile.modelId == model_id:
            return profile

    # Domain defaults
    if domain in ("audio", "music", "sfx"):
        audio = _load_profile_file("audio-studio@1.0")
        if audio:
            return audio
    if domain == "image":
        flux = _load_profile_file("flux-image@1.0")
        if flux:
            return flux
    if domain == "voice":
        voice = _load_profile_file("qwen3-tts@1.0")
        if voice:
            return voice

    return _default_profile(domain)


def recommendation_banner(profile: PromptProfile) -> Optional[str]:
    if profile.certificationStatus == "disabled":
        return f"{profile.profileId} @{profile.profileVersion}: profile disabled (Coming Soon)."
    if "zh" in (profile.recommendedLanguageModules or []) and not profile.bilingualCertified:
        balance = profile.recommendedBalance or "balanced"
        return (
            f"{profile.profileId} @{profile.profileVersion}: "
            f"{balance.capitalize()} bilingual prompting recommended (not certified — not auto-enabled)."
        )
    if profile.certificationStatus == "supported":
        return f"{profile.profileId} @{profile.profileVersion}: English production refinement supported."
    return None


def clear_profile_cache() -> None:
    _load_index.cache_clear()
    _load_profile_file.cache_clear()
