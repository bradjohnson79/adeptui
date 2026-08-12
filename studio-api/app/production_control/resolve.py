"""Resolve active model selection with registry + runtime probes."""

from __future__ import annotations

import logging
import threading
import time
from threading import RLock
from typing import Any

logger = logging.getLogger(__name__)


def warm_resolve_cache() -> None:
    """Pre-warm the resolve cache for all 4 modalities on startup.

    This ensures the first UI request finds cached results instead of
    triggering a slow cold-start resolve that can exceed the proxy timeout.
    """
    import os
    if not os.environ.get("STUDIO_API_PORT"):
        logger.debug("Skipping resolve cache warm — no API configured (test environment).")
        return

    from .contracts import Modality

    logger.info("Warming Production Control resolve cache...")
    modalities: list[Modality] = ["llm", "video", "image", "audio"]
    for mod in modalities:
        try:
            result = resolve_modality("_global", mod)
            logger.info("  %s: %s (%s)", mod, result.activeModelId or "none", "cached" if is_cache_fresh("_global", mod) else "skip")
        except Exception as exc:
            logger.warning("  %s: warm failed (%s)", mod, exc)
    logger.info("Production Control resolve cache warm complete.")


def _background_refresh(modality: str) -> None:
    """Refresh a single modality's resolve result in the background.
    Logs errors but never raises — designed for timer-driven refresh.
    """
    try:
        result = resolve_modality("_global", modality)
        logger.debug("Background refresh of %s: %s", modality, result.activeModelId or "none")
    except Exception as exc:
        logger.warning("Background refresh of %s failed: %s", modality, exc)

from ..hosted_providers.preferences import load_preferences as load_hosted_prefs
from ..hosted_providers.registry import list_providers
from .contracts import GpuStatus, Modality, PreferenceProvenance, ResolvedSelection
from .model_registry import get_model, list_models
from .store import get_user_preferences, resolve_with_precedence

# Phase CK — stale-while-revalidate resolve cache.
# User-facing requests ALWAYS return cached data immediately (even if stale).
# Background refresh runs on-demand when stale is detected, or on a timer.
# No user-facing request EVER waits for a slow resolver.
_RESOLVE_CACHE: dict[tuple[str, str], tuple[float, ResolvedSelection]] = {}
_RESOLVE_CACHE_STALE_AFTER = 30.0  # Serve stale after this many seconds
_RESOLVE_CACHE_LOCK = RLock()
_RESOLVE_REFRESH_IN_FLIGHT: set[tuple[str, str]] = set()  # Prevent concurrent background refreshes
_WARM_ATTEMPTED = False  # Prevent warm from blocking during imports in tests


def is_cache_fresh(project_id: str, modality: str) -> bool:
    """Check if cache entry exists and is fresh (not stale)."""
    key = (project_id, modality)
    with _RESOLVE_CACHE_LOCK:
        entry = _RESOLVE_CACHE.get(key)
        if entry is None:
            return False
        cached_at = entry[0]
        return time.monotonic() - cached_at < _RESOLVE_CACHE_STALE_AFTER


def get_resolve_cache(project_id: str, modality: str) -> ResolvedSelection | None:
    """Return cached resolve result. May return STALE data — never blocks.

    If the cache entry is stale, a background refresh is scheduled.
    The caller receives the stale value immediately.
    """
    key = (project_id, modality)
    with _RESOLVE_CACHE_LOCK:
        entry = _RESOLVE_CACHE.get(key)
        if entry is None:
            return None
        cached_at, result = entry
        # Stale-while-revalidate: if expired, trigger background refresh
        if time.monotonic() - cached_at >= _RESOLVE_CACHE_STALE_AFTER:
            if key not in _RESOLVE_REFRESH_IN_FLIGHT:
                _RESOLVE_REFRESH_IN_FLIGHT.add(key)
                threading.Thread(target=_background_refresh, args=(modality,), daemon=True).start()
        return result  # Always return stale value if we have one


def set_resolve_cache(project_id: str, modality: str, result: ResolvedSelection) -> None:
    key = (project_id, modality)
    with _RESOLVE_CACHE_LOCK:
        _RESOLVE_CACHE[key] = (time.monotonic(), result)
        _RESOLVE_REFRESH_IN_FLIGHT.discard(key)


def invalidate_resolve_cache(*, project_id: str | None = None, modality: str | None = None) -> None:
    """Invalidate resolve cache entries. If both None, clears all."""
    with _RESOLVE_CACHE_LOCK:
        if project_id is None and modality is None:
            _RESOLVE_CACHE.clear()
            return
        to_delete = [k for k in _RESOLVE_CACHE if (project_id is None or k[0] == project_id) and (modality is None or k[1] == modality)]
        for k in to_delete:
            del _RESOLVE_CACHE[k]
            _RESOLVE_REFRESH_IN_FLIGHT.discard(k)


def _gpu_from_audio(local_key: str, local_status: dict[str, Any]) -> GpuStatus:
    row = local_status.get(local_key) or {}
    if row.get("ready") and row.get("cuda"):
        return "Ready"
    if row.get("ready"):
        return "Unavailable"
    return "Unknown"


def _refresh_audio_executable(
    selection: ResolvedSelection, local_status: dict[str, Any]
) -> ResolvedSelection:
    from ..audio_studio.provider_resolver import local_runtime_status

    local = local_status or local_runtime_status()
    model_id = selection.activeModelId or ""

    if model_id == "ace-step-local":
        ace = local.get("ACE-Step") or {}
        gpu = _gpu_from_audio("ACE-Step", local)
        executable = bool(ace.get("ready") and ace.get("cuda"))
        blocked = None
        if not ace.get("ready"):
            blocked = "ACE-Step local runtime not ready"
        elif not ace.get("cuda"):
            user = get_user_preferences()
            if user.cpuFallbackPolicy == "disabled":
                blocked = "GPU acceleration required; CPU fallback disabled (Law 26)"
            else:
                executable = True
        selection.executable = executable
        selection.gpu = gpu
        selection.blockedReason = blocked
        selection.runtime = "ACE-Step"
        selection.providerId = "ace-step"
    elif model_id == "mmaudio-local":
        mm = local.get("MMAudio") or {}
        gpu = _gpu_from_audio("MMAudio", local)
        executable = bool(mm.get("ready") and mm.get("cuda"))
        blocked = None
        if not mm.get("ready"):
            blocked = "MMAudio local runtime not ready"
        elif not mm.get("cuda"):
            user = get_user_preferences()
            if user.cpuFallbackPolicy == "disabled":
                blocked = "GPU acceleration required; CPU fallback disabled (Law 26)"
            else:
                executable = True
        selection.executable = executable
        selection.gpu = gpu
        selection.blockedReason = blocked
        selection.runtime = "MMAudio"
        selection.providerId = "mmaudio"
    elif selection.modality == "audio" and not selection.executable:
        selection.blockedReason = selection.blockedReason or "No executable audio route"

    selection.provenance = PreferenceProvenance(
        activeModelId=selection.activeModelId,
        activeLabel=selection.activeLabel,
        source=selection.source,
        fallbackPolicy=selection.fallbackPolicy,
        gpu=selection.gpu,
        executable=selection.executable,
        blockedReason=selection.blockedReason,
        runtime=selection.runtime,
        providerId=selection.providerId,
        cpuFallbackPolicy=selection.cpuFallbackPolicy,
    )
    return selection


def _refresh_docker_executable(selection: ResolvedSelection, descriptor: Any) -> ResolvedSelection:
    """Law 27: Docker runtime must be ready; never fall back to another model."""
    runtime_id = getattr(descriptor, "runtimeId", None) or str(selection.activeModelId or "").removeprefix(
        "docker-runtime:"
    )
    try:
        from ..docker_runtime.gpu_preflight import check_gpu
        from ..docker_runtime.health import check_health
        from ..docker_runtime.registry import get_runtime

        desc = get_runtime(runtime_id)
        if not desc:
            selection.executable = False
            selection.blockedReason = "Docker runtime not registered"
            selection.runtime = runtime_id
            return selection
        if desc.disabled:
            selection.executable = False
            selection.blockedReason = "Docker runtime disabled — enable in Runtime Manager"
            selection.runtime = runtime_id
            return selection
        if desc.lifecycle != "running":
            selection.executable = False
            selection.blockedReason = "Container Stopped — Start Runtime"
            selection.gpu = "Unknown"
            selection.runtime = runtime_id
            return selection
        health = check_health(runtime_id)
        gpu = check_gpu(runtime_id)
        ok = health.ok and (gpu.frameworkAccelerator or gpu.cudaAvailable)
        selection.executable = ok
        selection.gpu = "Ready" if gpu.frameworkAccelerator or gpu.cudaAvailable else "Unavailable"
        selection.runtime = runtime_id
        selection.providerId = "docker-runtime"
        if not ok:
            selection.blockedReason = "Requires Repair — Docker health/GPU preflight failed"
        # Provenance fields for job metadata consumers
        selection.provenance = PreferenceProvenance(
            activeModelId=selection.activeModelId,
            activeLabel=selection.activeLabel,
            source=selection.source,
            fallbackPolicy="disabled",
            gpu=selection.gpu,
            executable=selection.executable,
            blockedReason=selection.blockedReason,
            runtime=runtime_id,
            providerId="docker-runtime",
            cpuFallbackPolicy="disabled",
        )
    except Exception as exc:
        selection.executable = False
        selection.blockedReason = f"Docker runtime probe failed: {exc}"[:200]
        selection.runtime = runtime_id
    return selection


def _refresh_hosted_executable(selection: ResolvedSelection) -> ResolvedSelection:
    descriptor = get_model(selection.activeModelId)
    if not descriptor or descriptor.locality != "hosted":
        return selection

    provider_id = descriptor.providerId
    if not provider_id:
        selection.executable = False
        selection.blockedReason = "Hosted model missing provider"
        return selection

    try:
        providers = {p["provider_id"]: p for p in list_providers()}
        card = providers.get(provider_id) or {}
        configured = card.get("credentialState") in ("verified", "connected")
        selection.executable = configured and descriptor.executable
        if not configured:
            selection.blockedReason = f"Hosted provider {provider_id} requires setup"
        elif not descriptor.executable:
            selection.blockedReason = f"{descriptor.label} is not executable yet"
        selection.providerId = provider_id
    except Exception:
        selection.executable = False
        selection.blockedReason = "Hosted provider status unavailable"

    selection.provenance = PreferenceProvenance(
        activeModelId=selection.activeModelId,
        activeLabel=selection.activeLabel,
        source=selection.source,
        fallbackPolicy=selection.fallbackPolicy,
        gpu=selection.gpu,
        executable=selection.executable,
        blockedReason=selection.blockedReason,
        runtime=selection.runtime,
        providerId=selection.providerId,
        cpuFallbackPolicy=selection.cpuFallbackPolicy,
    )
    return selection


def _apply_system_default(selection: ResolvedSelection) -> ResolvedSelection:
    if selection.activeModelId:
        return selection

    defaults: dict[Modality, str] = {
        "llm": "ollama-gemma4-31b",
        "video": "minimax-h3",
        "image": "qwen-image-2512-local",
        "audio": "ace-step-local",
    }
    default_id = defaults.get(selection.modality)
    descriptor = get_model(default_id)
    if descriptor:
        selection.activeModelId = default_id
        selection.activeLabel = descriptor.label
        selection.source = "system"
        selection.executable = descriptor.executable
        selection.providerId = descriptor.providerId
        selection.runtime = descriptor.providerId
        selection.availableModelIds = [m.id for m in list_models(selection.modality)]
    return selection


def resolve_modality(project_id: str, modality: Modality) -> ResolvedSelection:
    """Combine user+project prefs, registry, and runtime probes.

    Uses a 30s TTL cache — repeated calls within the TTL window
    return the cached result without recomputation.
    """
    # Stale-while-revalidate: skip recompute only if cache is FRESH
    if is_cache_fresh(project_id, modality):
        return get_resolve_cache(project_id, modality)
    selection = resolve_with_precedence(project_id, modality)
    selection = _apply_system_default(selection)

    user = get_user_preferences()
    selection.cpuFallbackPolicy = user.cpuFallbackPolicy
    selection.fallbackPolicy = user.cpuFallbackPolicy

    descriptor = get_model(selection.activeModelId)
    if descriptor:
        selection.activeLabel = descriptor.label
        selection.executable = descriptor.executable
        selection.providerId = descriptor.providerId
        if descriptor.locality == "local" and descriptor.gpuCompatible:
            selection.gpu = "Ready" if descriptor.executable else "Unknown"

    if modality == "audio":
        from ..audio_studio.provider_resolver import local_runtime_status

        selection = _refresh_audio_executable(selection, local_runtime_status())
    elif descriptor and descriptor.locality == "hosted":
        selection = _refresh_hosted_executable(selection)
    elif descriptor and getattr(descriptor, "executionClass", None) == "docker_local":
        # W47: Docker Local — no silent substitute; start/repair required
        selection = _refresh_docker_executable(selection, descriptor)
    elif modality == "video" and selection.activeModelId in (
        "hunyuan-video-1.5-local",
        "hunyuan-video-13b-local",
    ):
        from ..video_runtime.hunyuan_providers import describe_provider

        hy = describe_provider(selection.activeModelId)
        selection.executable = hy.executable
        selection.gpu = "Ready" if hy.executable else "Unknown"
        selection.blockedReason = None if hy.executable else "Hunyuan provider requires Setup install/verify"
        selection.runtime = hy.engine

    if not selection.executable and not selection.blockedReason:
        if modality == "audio":
            selection.blockedReason = "No executable audio route"
        elif modality == "video" and selection.activeModelId == "minimax-h3":
            selection.blockedReason = (
                "MiniMax H3 unavailable. Choose another generator — Adept UI will not silently switch to LTX."
            )
        else:
            selection.blockedReason = f"No executable {modality} route"

    # Sync hosted provider preference without silent switch
    hosted = load_hosted_prefs()
    if selection.providerId and hosted.get("preferredProvider") not in (None, "automatic"):
        if hosted.get("preferredProvider") != selection.providerId:
            selection.blockedReason = (
                selection.blockedReason
                or f"Preferred provider {hosted.get('preferredProvider')} differs; explicit confirmation required"
            )

    selection.provenance = PreferenceProvenance(
        activeModelId=selection.activeModelId,
        activeLabel=selection.activeLabel,
        source=selection.source,
        fallbackPolicy=selection.fallbackPolicy,
        gpu=selection.gpu,
        executable=selection.executable,
        blockedReason=selection.blockedReason,
        runtime=selection.runtime,
        providerId=selection.providerId,
        cpuFallbackPolicy=selection.cpuFallbackPolicy,
    )
    set_resolve_cache(project_id, modality, selection)
    return selection
