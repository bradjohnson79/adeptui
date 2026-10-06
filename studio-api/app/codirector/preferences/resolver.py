"""Resolve the generator for one job. Named unavailable providers fail honestly."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from .store import load_generator_preferences, save_generator_preference


# Canonical provider ids used on GenerationJob / enginePreference.
CREATOR_PROVIDER_LABELS: dict[str, str] = {
    "fal_seedance": "Seedance 2.0",
    "seedance-fal": "Seedance 2.0",
    "seedance-2.0": "Seedance 2.0",
    "seedance-2.0-mini": "Seedance 2.0 Mini",
    "fal_seedance_mini": "Seedance 2.0 Mini",
    "seedance-mini": "Seedance 2.0 Mini",
    "seedance-2.5": "Seedance 2.5",
    "fal_seedance_25": "Seedance 2.5",
    "fal_kling": "Kling",
    "kling-fal": "Kling",
    "kling-kie": "Kling",
    "minimax-h3": "MiniMax H3",
    "minimax-h3-i2v-local": "MiniMax H3 Image-to-Video",
    "ltx-2.5": "LTX 2.5",
    "ltx-2.5-full": "LTX 2.5 Full",
    "ltx-2.5-distilled": "LTX 2.5 Distilled",
    "ltx-2.5-comfy": "LTX 2.5 Comfy",
}


def creator_provider_label(provider: str) -> str:
    pid = normalize_provider(provider)
    return CREATOR_PROVIDER_LABELS.get(pid, pid.replace("_", " ").replace("-", " ").title())


PROVIDER_ALIASES: dict[str, str] = {
    "ltx-2.5": "ltx-2.5",
    "ltx-2.5-distilled": "ltx-2.5-distilled",
    "ltx-2.5-full": "ltx-2.5-full",
    "ltx-2.5-comfy": "ltx-2.5-comfy",
    "minimax": "minimax-h3",
    "minimax h3": "minimax-h3",
    "minimax-h3": "minimax-h3",
    "minimax-h3-i2v-local": "minimax-h3-i2v-local",
    "kling": "fal_kling",
    "fal_kling": "fal_kling",
    "kling-fal": "kling-fal",
    "kling-kie": "kling-kie",
    "seedance": "seedance-2.0",
    "see dance": "seedance-2.0",
    "seedance 2.0": "seedance-2.0",
    "seedance-2.0": "seedance-2.0",
    "seedance mini": "seedance-2.0-mini",
    "seedance-mini": "seedance-2.0-mini",
    "seedance-2.0-mini": "seedance-2.0-mini",
    "fal_seedance_mini": "seedance-2.0-mini",
    "fal_seedance": "seedance-2.0",
    "seedance-fal": "seedance-2.0",
    "seedance 2.5": "seedance-2.5",
    "seedance-2.5": "seedance-2.5",
    "fal_seedance_25": "seedance-2.5",
    "seedance-kie": "seedance-kie",
    "qwen": "qwen2512",
    "qwen2512": "qwen2512",
    "flux": "flux",
    "z-image": "zimage",
    "zimage": "zimage",
}

_EXPLICIT_RE = re.compile(
    r"\b(?:use|with|via|in)\s+(ltx(?:\s*2\.5)?|kling|seedance|see\s*dance|minimax(?:\s*h3)?|qwen|flux|z-?image)\b",
    re.I,
)
_CHANGE_DEFAULT_RE = re.compile(
    r"\b(?:make (?:this|that|it) (?:my |the )?(?:default|preferred)|always use|set (?:my |the )?preferred|from now on)\b",
    re.I,
)
_THIS_ONE_RE = re.compile(r"\b(?:for this (?:one|job|shot|clip|image|video)|just this|this time only)\b", re.I)

# Hosted video providers that require credentials. Local Comfy engines do not.
_HOSTED_SECRET_ENV: dict[str, tuple[str, ...]] = {
    "fal_seedance": ("FAL_KEY", "FAL_API_KEY"),
    "seedance-fal": ("FAL_KEY", "FAL_API_KEY"),
    "seedance-2.0": ("FAL_KEY", "FAL_API_KEY"),
    "seedance-2.0-mini": ("FAL_KEY", "FAL_API_KEY"),
    "fal_seedance_mini": ("FAL_KEY", "FAL_API_KEY"),
    "seedance-2.5": ("FAL_KEY", "FAL_API_KEY"),
    "fal_seedance_25": ("FAL_KEY", "FAL_API_KEY"),
    "seedance-kie": ("KIE_API_KEY", "KIE_KEY"),
    "fal_kling": ("FAL_KEY", "FAL_API_KEY"),
    "kling-fal": ("FAL_KEY", "FAL_API_KEY"),
    "kling-kie": ("KIE_API_KEY", "KIE_KEY"),
}

_HOSTED_SECRET_NAMES: dict[str, tuple[str, ...]] = {
    "fal_seedance": ("fal_api_key",),
    "seedance-fal": ("fal_api_key",),
    "seedance-2.0": ("fal_api_key",),
    "seedance-2.0-mini": ("fal_api_key",),
    "fal_seedance_mini": ("fal_api_key",),
    "seedance-2.5": ("fal_api_key",),
    "fal_seedance_25": ("fal_api_key",),
    "seedance-kie": ("kie_api_key",),
    "fal_kling": ("fal_api_key",),
    "kling-fal": ("fal_api_key",),
    "kling-kie": ("kie_api_key",),
}

ADEPT_DEFAULTS: dict[str, str] = {
    "video": "minimax-h3",
    "image": "zimage",
    "voice": "voice",
    "music": "music",
    "sfx": "sfx",
}


@dataclass
class PreferenceResolution:
    provider: str
    source: str
    modality: str
    explicit: bool = False
    job_scoped: bool = True
    persist_default: bool = False
    configured: bool = True
    error: Optional[str] = None
    aliases: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.configured and not self.error


def normalize_provider(name: str) -> str:
    key = re.sub(r"\s+", " ", (name or "").strip().lower())
    return PROVIDER_ALIASES.get(key, key.replace(" ", "-"))


def extract_explicit_provider(message: str) -> Optional[str]:
    match = _EXPLICIT_RE.search(message or "")
    if not match:
        return None
    return normalize_provider(match.group(1))


def wants_persist_default(message: str) -> bool:
    text = message or ""
    if _THIS_ONE_RE.search(text):
        return False
    return bool(_CHANGE_DEFAULT_RE.search(text))


def _env_configured(keys: tuple[str, ...]) -> bool:
    return any(bool(os.environ.get(key, "").strip()) for key in keys)


def _secret_configured(names: tuple[str, ...]) -> bool:
    try:
        from ...secrets_store import get_secret
    except Exception:
        return False
    for name in names:
        try:
            if get_secret(name):
                return True
        except Exception:
            continue
    return False


def is_provider_configured(provider: str) -> bool:
    """Local engines are configured when Comfy/Studio can run them. Hosted APIs need keys."""

    pid = normalize_provider(provider)
    if pid in {
        "minimax-h3",
        "minimax-h3-i2v-local",
        "qwen2512",
        "flux",
        "zimage",
        "ltx-2.5",
        "ltx-2.5-distilled",
        "ltx-2.5-full",
        "ltx-2.5-comfy",
    }:
        return True
    env_keys = _HOSTED_SECRET_ENV.get(pid)
    secret_names = _HOSTED_SECRET_NAMES.get(pid)
    if env_keys or secret_names:
        return _env_configured(env_keys or ()) or _secret_configured(secret_names or ())
    return True


def _project_video_default(project_id: str) -> Optional[str]:
    try:
        from ...production_control.resolve import resolve_modality

        selection = resolve_modality(project_id or "_global", "video")
        engine = getattr(selection, "runtime", None) or getattr(selection, "activeModelId", None)
        if engine:
            return normalize_provider(str(engine))
        model_id = getattr(selection, "activeModelId", None)
        if model_id:
            return normalize_provider(str(model_id))
    except Exception:
        return None
    return None


def resolve_generator_preference(
    db: Optional[Session],
    project_id: str,
    *,
    modality: str,
    message: str = "",
    persist_if_requested: bool = True,
) -> PreferenceResolution:
    """Order: explicit request → user preferred → project → Adept default.

    Explicit provider is job-scoped unless the user asks to change the default.
    Named unavailable providers fail honestly — never silent substitute.
    """

    modality_key = (modality or "image").split(".")[0]
    stored = load_generator_preferences(db, project_id) if db is not None else {}
    explicit = extract_explicit_provider(message)
    persist = wants_persist_default(message) if explicit else False

    if explicit:
        configured = is_provider_configured(explicit)
        if persist and persist_if_requested and configured and db is not None:
            save_generator_preference(db, project_id, modality_key, explicit)
        if not configured:
            from ..image_route.lock import parse_route_lock

            lock = parse_route_lock(message)
            label = creator_provider_label(explicit)
            if lock.level == "STRICT":
                return PreferenceResolution(
                    provider=explicit,
                    source="explicit",
                    modality=modality_key,
                    explicit=True,
                    job_scoped=not persist,
                    persist_default=False,
                    configured=False,
                    error=f"{label} is not configured. I will not switch to another generator.",
                )
            return PreferenceResolution(
                provider=explicit,
                source="explicit",
                modality=modality_key,
                explicit=True,
                job_scoped=not persist,
                persist_default=False,
                configured=False,
            )
        return PreferenceResolution(
            provider=explicit,
            source="explicit",
            modality=modality_key,
            explicit=True,
            job_scoped=not persist,
            persist_default=persist,
            configured=True,
        )

    user_pref = stored.get(modality_key)
    if user_pref:
        provider = normalize_provider(str(user_pref))
        if not is_provider_configured(provider):
            return PreferenceResolution(
                provider=provider,
                source="user",
                modality=modality_key,
                configured=False,
                error=f"{provider} is saved as your preferred {modality_key} generator but is not configured.",
            )
        return PreferenceResolution(
            provider=provider,
            source="user",
            modality=modality_key,
            job_scoped=False,
            configured=True,
        )

    if modality_key == "video":
        project_pref = _project_video_default(project_id)
        if project_pref:
            return PreferenceResolution(
                provider=project_pref,
                source="project",
                modality=modality_key,
                job_scoped=False,
                configured=is_provider_configured(project_pref),
            )

    default = ADEPT_DEFAULTS.get(modality_key, ADEPT_DEFAULTS["image"])
    return PreferenceResolution(
        provider=default,
        source="adept_default",
        modality=modality_key,
        job_scoped=False,
        configured=is_provider_configured(default),
    )
