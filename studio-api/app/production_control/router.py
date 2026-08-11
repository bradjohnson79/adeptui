"""Production Control Dock HTTP API."""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .contracts import Modality, UserGlobalPreferences
from .gate import evaluate_production_dock_gate
from .migration import migrate_preferences
from .model_registry import filter_for_action
from .model_inventory import get_models_cached, invalidate_model_cache, warm_model_inventory
from .resolve import get_resolve_cache, invalidate_resolve_cache, resolve_modality, set_resolve_cache
from .status import aggregate_status
from .store import (
    get_project_preferences,
    get_user_preferences,
    patch_user_preferences,
    save_project_preferences,
)

router = APIRouter(prefix="/production-control", tags=["production-control"])

# Pending provider switches — never apply without confirmed=true
_PENDING_SWITCHES: dict[str, dict[str, Any]] = {}


class UserPreferencesPatch(BaseModel):
    model_config = {"extra": "allow"}

    theme: Optional[Literal["aurora-night", "aurora-day", "system"]] = None
    dockCollapsed: Optional[bool] = None
    dockAutoCollapse: Optional[bool] = None
    runtimeSource: Optional[Literal["local", "api", "hybrid"]] = None
    runtimeLocalEnabled: Optional[bool] = None
    runtimeApiEnabled: Optional[bool] = None
    defaultHostedProviderId: Optional[str] = None
    cpuFallbackPolicy: Optional[Literal["disabled", "ask", "lightweight_only"]] = None
    llm: Optional[dict[str, Any]] = None
    video: Optional[dict[str, Any]] = None
    image: Optional[dict[str, Any]] = None
    audio: Optional[dict[str, Any]] = None
    llmRouting: Optional[dict[str, Any]] = None
    videoRouting: Optional[dict[str, Any]] = None
    imageRouting: Optional[dict[str, Any]] = None
    audioRouting: Optional[dict[str, Any]] = None
    defaultVideoQuality: Optional[str] = None
    defaultImageQuality: Optional[str] = None
    defaultAudioQuality: Optional[str] = None


class ProjectPreferencesBody(BaseModel):
    activeVideoModelId: Optional[str] = None
    activeImageModelId: Optional[str] = None
    activeAudioModelId: Optional[str] = None
    codirectorModelId: Optional[str] = None
    resolution: Optional[str] = None
    videoQuality: Optional[str] = None
    imageQuality: Optional[str] = None
    audioQuality: Optional[str] = None
    generatorLocks: Optional[dict[str, bool]] = None


class ProviderSwitchBody(BaseModel):
    providerId: str = Field(..., min_length=1)


class ProviderSwitchConfirmBody(BaseModel):
    providerId: str = Field(..., min_length=1)
    confirmed: bool = False


@router.get("/status")
def get_status():
    return aggregate_status()


@router.get("/gate")
def get_gate():
    return evaluate_production_dock_gate()


@router.get("/preferences")
def get_preferences():
    prefs = get_user_preferences()
    dumped = prefs.model_dump()
    dumped["llmRouting"] = dumped.get("llm")
    dumped["videoRouting"] = dumped.get("video")
    dumped["imageRouting"] = dumped.get("image")
    dumped["audioRouting"] = dumped.get("audio")
    dumped["runtimeLocalEnabled"] = prefs.runtimeSource in ("local", "hybrid")
    dumped["runtimeApiEnabled"] = prefs.runtimeSource in ("api", "hybrid")
    return {"ok": True, "preferences": dumped, "mock": False}


@router.put("/preferences")
def put_preferences(body: UserPreferencesPatch):
    patch = body.model_dump(exclude_none=True)
    prefs = patch_user_preferences(patch)
    # Invalidate both caches when user changes preferences
    invalidate_resolve_cache()
    invalidate_model_cache()
    # Sync Co-Director brain when LLM active model changes (preferences → resolver consumers).
    try:
        llm = prefs.llm
        if llm and llm.activeModelId:
            from ..codirector.config_store import load_config, save_config

            cfg = load_config()
            # Map dock model ids to Ollama model names when local; hosted kept as Requires Setup.
            from .runtime_map import llm_ollama_for_dock_model

            model_id = str(llm.activeModelId)
            selected = llm_ollama_for_dock_model(model_id)
            if selected:
                save_config({**cfg, "selectedModel": selected, "primaryModel": selected})
    except Exception:
        pass
    dumped = prefs.model_dump()
    # Frontend aliases
    dumped["llmRouting"] = dumped.get("llm")
    dumped["videoRouting"] = dumped.get("video")
    dumped["imageRouting"] = dumped.get("image")
    dumped["audioRouting"] = dumped.get("audio")
    dumped["runtimeLocalEnabled"] = prefs.runtimeSource in ("local", "hybrid")
    dumped["runtimeApiEnabled"] = prefs.runtimeSource in ("api", "hybrid")
    return {"ok": True, "preferences": dumped, "mock": False}


@router.get("/projects/{project_id}/preferences")
def get_project_prefs(project_id: str):
    prefs = get_project_preferences(project_id)
    return {"ok": True, "preferences": prefs.model_dump(), "mock": False}


@router.put("/projects/{project_id}/preferences")
def put_project_prefs(project_id: str, body: dict[str, Any]):
    # Accept frontend aliases (activeLlmModelId -> codirectorModelId)
    patch = dict(body or {})
    if "activeLlmModelId" in patch and "codirectorModelId" not in patch:
        patch["codirectorModelId"] = patch.pop("activeLlmModelId")
    prefs = save_project_preferences(project_id, {k: v for k, v in patch.items() if v is not None})
    invalidate_resolve_cache(project_id=project_id)
    dumped = prefs.model_dump()
    dumped["activeLlmModelId"] = dumped.get("codirectorModelId")
    return {"ok": True, "preferences": dumped, "mock": False}


@router.get("/resolve")
def get_resolve(projectId: str = "_global", modality: Modality = "audio"):
    pid = projectId.strip() or "_global"
    selection = resolve_modality(pid, modality)
    dumped = selection.model_dump()
    # Ensure nested provenance always present for UI
    if not dumped.get("provenance"):
        dumped["provenance"] = {
            "activeModelId": dumped.get("activeModelId"),
            "activeLabel": dumped.get("activeLabel"),
            "source": dumped.get("source"),
            "fallbackPolicy": dumped.get("fallbackPolicy"),
            "gpu": dumped.get("gpu"),
            "executable": dumped.get("executable"),
            "blockedReason": dumped.get("blockedReason"),
            "runtime": dumped.get("runtime"),
            "providerId": dumped.get("providerId"),
            "cpuFallbackPolicy": dumped.get("cpuFallbackPolicy"),
        }
    return {"ok": True, "selection": dumped, "mock": False}


@router.get("/resolved")
def get_resolved(projectId: str = "_global"):
    """Batch resolve all 4 modalities in a single request.

    Stale-while-revalidate: returns cached data immediately even if stale.
    Background refresh is triggered asynchronously — no user-facing request
    ever waits for the resolver.
    """
    pid = projectId.strip() or "_global"
    modalities: list[Modality] = ["llm", "video", "image", "audio"]
    results: dict[str, dict] = {}
    for mod in modalities:
        # Stale-while-revalidate: read from cache first
        cached = get_resolve_cache(pid, mod)
        if cached is not None:
            selection = cached
        else:
            # Cold cache for this project — fall back to _global cache
            # and trigger background refresh for the project-specific entry.
            global_cached = get_resolve_cache("_global", mod)
            if global_cached is not None:
                selection = global_cached
            else:
                # No cache at all (first request after startup) — must resolve
                selection = resolve_modality(pid, mod)
            # Background refresh for this project so next request is cached
            if pid != "_global":
                import threading as _t
                _t.Thread(
                    target=lambda p=pid, m=mod: _bg_resolve(p, m),
                    daemon=True,
                ).start()
        dumped = selection.model_dump()
        if not dumped.get("provenance"):
            dumped["provenance"] = {
                "activeModelId": dumped.get("activeModelId"),
                "activeLabel": dumped.get("activeLabel"),
                "source": dumped.get("source"),
                "fallbackPolicy": dumped.get("fallbackPolicy"),
                "gpu": dumped.get("gpu"),
                "executable": dumped.get("executable"),
                "blockedReason": dumped.get("blockedReason"),
                "runtime": dumped.get("runtime"),
                "providerId": dumped.get("providerId"),
                "cpuFallbackPolicy": dumped.get("cpuFallbackPolicy"),
            }
        results[mod] = {"ok": True, "selection": dumped, "mock": False}
    return {"ok": True, "resolved": results, "mock": False}


def _bg_resolve(project_id: str, modality: str) -> None:
    """Background resolve for a project-specific cache entry."""
    try:
        result = resolve_modality(project_id, modality)  # type: ignore[arg-type]
        set_resolve_cache(project_id, modality, result)  # type: ignore[arg-type]
    except Exception:
        pass


@router.get("/models")
def get_models(modality: Modality, action: str = "generate"):
    """Return Local + API (discovered) sections — served from cached model inventory.

    Stale-while-revalidate: returns cached data immediately even if stale.
    Background refresh runs at most once per TTL across all 4 modalities.
    No creator-facing request ever waits for model discovery.
    """
    return get_models_cached(modality, action)


@router.get("/queue")
def get_queue():
    from .status import _queue_counts

    return {"ok": True, "queue": _queue_counts(), "mock": False}


@router.post("/migrate")
def post_migrate():
    return migrate_preferences()


@router.post("/providers/switch")
def post_provider_switch(body: ProviderSwitchBody):
    """Stage a provider switch — does not apply until confirmed=true."""
    from ..hosted_providers.registry import PROVIDERS

    provider_id = body.providerId.lower()
    if provider_id not in PROVIDERS and provider_id not in ("kie", "wavespeed", "fal"):
        raise HTTPException(404, f"Unknown provider: {body.providerId}")

    payload = {
        "providerId": provider_id,
        "confirmed": False,
        "applied": False,
        "message": (
            f"Switch to {provider_id} staged. POST /providers/switch/confirm with "
            "confirmed=true to apply. No silent provider switch."
        ),
        "requiresConfirmation": True,
    }
    _PENDING_SWITCHES[provider_id] = payload
    return {"ok": True, **payload, "mock": False}


@router.post("/providers/switch/confirm")
def post_provider_switch_confirm(body: ProviderSwitchConfirmBody):
    provider_id = body.providerId.lower()
    if not body.confirmed:
        raise HTTPException(
            400,
            "Provider switch not applied. Set confirmed=true after explicit user approval.",
        )

    pending = _PENDING_SWITCHES.get(provider_id)
    if not pending:
        raise HTTPException(
            400,
            f"No pending switch for {provider_id}. POST /providers/switch first.",
        )

    from ..hosted_providers.preferences import save_preferences

    prefs = save_preferences(preferred_provider=provider_id)  # type: ignore[arg-type]
    user_patch = patch_user_preferences({"defaultHostedProviderId": provider_id})
    _PENDING_SWITCHES.pop(provider_id, None)

    return {
        "ok": True,
        "providerId": provider_id,
        "confirmed": True,
        "applied": True,
        "hostedPreferences": {
            "preferredProvider": prefs.get("preferredProvider"),
            "budgetPreference": prefs.get("budgetPreference"),
        },
        "userPreferences": {"defaultHostedProviderId": user_patch.defaultHostedProviderId},
        "message": f"Provider switch to {provider_id} applied with explicit confirmation.",
        "mock": False,
    }


def ensure_production_control() -> None:
    """Create preference directories on startup and pre-warm resolve + model caches."""
    from ..config import settings

    (settings.data_dir / "production_control" / "projects").mkdir(parents=True, exist_ok=True)
    try:
        from .resolve import warm_resolve_cache
        warm_resolve_cache()
    except Exception:
        import logging
        logging.getLogger(__name__).debug("Resolve cache warm skipped (test/import env)")
    try:
        from .model_inventory import warm_model_inventory
        warm_model_inventory()
    except Exception:
        import logging
        logging.getLogger(__name__).debug("Model inventory warm skipped (test/import env)")
