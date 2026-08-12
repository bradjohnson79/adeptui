"""Shared, per-run probe context for Production Assurance.

Warms expensive dependencies once (Comfy health, capability snapshot) and shares
them across independent checks so parallel probes do not stampede ComfyUI or
starve the event loop.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Optional

# TTL cache for global (non-project-scoped) checks.
# Success TTL: reuse healthy result for this long.
# Failure TTL: shorter — don't cache failures for long.
_GLOBAL_CACHE_TTL_SUCCESS_SEC = 30.0
_GLOBAL_CACHE_TTL_FAILURE_SEC = 5.0

# Check IDs that are global (not project-scoped) and eligible for TTL caching.
_GLOBAL_CHECK_IDS = {
    "api.health",
    "capabilities.registry",
    "codirector.provider",
    "comfy.health",
    "production_control.status",
    "image_runtime.readiness",
    "video_runtime.readiness",
}

_CACHE_LOCK = RLock()
_CHECK_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}  # check_id -> (cached_at_epoch, result)

def cache_get(check_id: str) -> Optional[dict[str, Any]]:
    """Return cached result for a global check if fresh, else None."""
    entry = _CHECK_CACHE.get(check_id)
    if entry is None:
        return None
    cached_at, result = entry
    age = datetime.now(timezone.utc).timestamp() - cached_at
    is_healthy = result.get("status") in ("healthy", "ready", "connected")
    ttl = _GLOBAL_CACHE_TTL_SUCCESS_SEC if is_healthy else _GLOBAL_CACHE_TTL_FAILURE_SEC
    if age < ttl:
        return dict(result)  # return a shallow copy
    return None

def cache_put(check_id: str, result: dict[str, Any]) -> None:
    """Store a check result in the global cache."""
    if check_id not in _GLOBAL_CHECK_IDS:
        return
    with _CACHE_LOCK:
        _CHECK_CACHE[check_id] = (datetime.now(timezone.utc).timestamp(), dict(result))

def cache_invalidate_global() -> None:
    """Invalidate all cached global results (e.g. on API reconnect)."""
    with _CACHE_LOCK:
        _CHECK_CACHE.clear()

# Per-check timeout budgets (seconds). Standard mode uses these; deep multiplies
# functional/dependency budgets modestly without returning to a flat 1.5s trap.
_TIMEOUT_BY_CHECK: dict[str, float] = {
    # Layer 1–2: process / API
    "api.health": 3.0,
    "session.binding": 2.0,
    "proposal.service": 3.0,
    "production_control.status": 4.0,
    "production_control.queue": 4.0,
    "install_jobs.status": 4.0,
    # Layer 3: registry
    "capabilities.registry": 12.0,
    "tools.registry": 20.0,
    # Layer 4–5: runtime / dependency / smoke
    "codirector.provider": 8.0,
    "comfy.health": 12.0,
    "gpu.stats": 4.0,
    "source_manager.overview": 8.0,
    "image_runtime.readiness": 10.0,
    "video_runtime.readiness": 10.0,
    "voice_runtime.readiness": 8.0,
    "voice_environment.runtime": 6.0,
    "magi.readiness": 6.0,
    "library.preflight": 15.0,
    "bible.versions": 5.0,
    "scriptwriter.documents": 5.0,
    "timeline.preflight": 8.0,
}

_DEFAULT_STANDARD = 5.0
_DEFAULT_DEEP = 15.0

_LAST_HEALTHY_LOCK = RLock()
_LAST_HEALTHY_AT: dict[str, str] = {}
_LAST_HEALTHY_SUMMARY: dict[str, str] = {}


def timeout_for_check(check_id: str, mode: str = "standard") -> float:
    base = _TIMEOUT_BY_CHECK.get(check_id, _DEFAULT_STANDARD if mode == "standard" else _DEFAULT_DEEP)
    if mode == "deep":
        return max(base, _DEFAULT_DEEP) if check_id not in _TIMEOUT_BY_CHECK else min(base * 1.5, 30.0)
    return base


def awaited_dependency_for(check_id: str) -> str:
    mapping = {
        "capabilities.registry": "capability snapshot / Comfy node catalogue",
        "comfy.health": "ComfyUI /system_stats and /object_info",
        "codirector.provider": "Co-Director provider health (Ollama/model)",
        "tools.registry": "tool catalog + project availability",
        "library.preflight": "project library storage preflight",
        "api.health": "Studio API operator health",
        "image_runtime.readiness": "image runtime readiness",
        "video_runtime.readiness": "video runtime diagnostics",
    }
    return mapping.get(check_id, check_id)


def remember_healthy(check_id: str, summary: str = "") -> None:
    stamp = datetime.now(timezone.utc).isoformat()
    with _LAST_HEALTHY_LOCK:
        _LAST_HEALTHY_AT[check_id] = stamp
        if summary:
            _LAST_HEALTHY_SUMMARY[check_id] = summary


def last_healthy_at(check_id: str) -> Optional[str]:
    with _LAST_HEALTHY_LOCK:
        return _LAST_HEALTHY_AT.get(check_id)


def last_healthy_summary(check_id: str) -> Optional[str]:
    with _LAST_HEALTHY_LOCK:
        return _LAST_HEALTHY_SUMMARY.get(check_id)


@dataclass
class SharedProbeBundle:
    """Warm results shared across a single status-check run."""

    comfy_health: Optional[dict[str, Any]] = None
    capabilities: Any = None
    warmed_at: Optional[str] = None
    warm_errors: list[str] = field(default_factory=list)


async def warm_shared_bundle(project_id: Optional[str] = None) -> SharedProbeBundle:
    """Pre-warm Comfy + capability snapshot once before parallel probes."""
    bundle = SharedProbeBundle(warmed_at=datetime.now(timezone.utc).isoformat())

    async def _comfy() -> None:
        try:
            from ...comfy_health import comfy_health

            bundle.comfy_health = await comfy_health(include_nodes=True)
        except Exception as exc:  # noqa: BLE001
            bundle.warm_errors.append(f"comfy_health: {exc}")

    async def _caps() -> None:
        try:
            from ...capabilities import service as capability_service

            if project_id:
                bundle.capabilities = await capability_service.get_project_capabilities(project_id, force=False)
            else:
                bundle.capabilities = await capability_service.get_capabilities(force=False)
        except Exception as exc:  # noqa: BLE001
            bundle.warm_errors.append(f"capabilities: {exc}")

    await asyncio.gather(_comfy(), _caps())
    return bundle
