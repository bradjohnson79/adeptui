"""Short-lived project-keyed cache for stable Wave 3 reads.

Jobs and proposals intentionally bypass this cache (always fresh).
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any, Optional

_DEFAULT_TTL_SEC = 8.0
_FRESH_TOOLS = {
    "job.list",
    "job.get",
    "proposal.list",
    "proposal.get",
    "project.list_blockers",
    "continuity.list_findings",
    "continuity.get_finding",
    # Wave 4 plan reads must not serve stale head/version after commands
    "production_plan.list",
    "production_plan.get",
    "production_plan.get_version",
    "production_plan.list_versions",
    "production_plan.list_events",
    "production_plan.validate",
    "production_plan.get_readiness",
    "workspace.get_active_context",
    # Spatial Map reads should reflect newly approved staging changes immediately.
    "spatial.list_maps",
    "spatial.get_map",
    "spatial.inspect_scene",
    "spatial.list_cameras",
    "spatial.get_camera_view",
    "spatial.check_visibility",
    "spatial.check_consistency",
    "spatial.build_reference_bundle",
}

_lock = Lock()
_store: dict[str, tuple[float, Any]] = {}


def cache_key(project_id: str, tool_id: str, arguments: dict[str, Any]) -> str:
    # Stable enough for list/summary tools; argument order normalized via sorted items.
    args = ",".join(f"{k}={arguments.get(k)}" for k in sorted(arguments.keys()))
    return f"{project_id}|{tool_id}|{args}"


def get_cached(project_id: str, tool_id: str, arguments: dict[str, Any]) -> Optional[Any]:
    if tool_id in _FRESH_TOOLS:
        return None
    key = cache_key(project_id, tool_id, arguments)
    now = time.monotonic()
    with _lock:
        hit = _store.get(key)
        if not hit:
            return None
        expires, value = hit
        if expires <= now:
            _store.pop(key, None)
            return None
        return value


def put_cached(project_id: str, tool_id: str, arguments: dict[str, Any], value: Any, *, ttl: float = _DEFAULT_TTL_SEC) -> None:
    if tool_id in _FRESH_TOOLS:
        return
    key = cache_key(project_id, tool_id, arguments)
    with _lock:
        _store[key] = (time.monotonic() + ttl, value)


def clear_project(project_id: str) -> None:
    prefix = f"{project_id}|"
    with _lock:
        for key in list(_store.keys()):
            if key.startswith(prefix):
                _store.pop(key, None)
