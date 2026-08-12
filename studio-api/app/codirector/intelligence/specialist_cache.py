"""Specialist result cache keyed by project + specialist + task + source revisions."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def specialist_cache_key(
    *,
    project_id: str,
    specialist_id: str,
    task: str,
    source_revisions: dict[str, Any] | None,
    request_hash: str,
) -> str:
    payload = {
        "projectId": project_id,
        "specialistId": specialist_id,
        "task": task,
        "revisions": source_revisions or {},
        "requestHash": request_hash,
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached_specialist(key: str) -> Optional[dict[str, Any]]:
    entry = _CACHE.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.time() > expires_at:
        _CACHE.pop(key, None)
        return None
    return value


def put_cached_specialist(key: str, value: dict[str, Any], *, ttl_seconds: int = 600) -> None:
    _CACHE[key] = (time.time() + max(1, ttl_seconds), value)


def invalidate_specialist_cache(*, project_id: str | None = None, specialist_id: str | None = None) -> int:
    """Drop matching in-memory specialist entries. Returns count removed."""
    if project_id is None and specialist_id is None:
        n = len(_CACHE)
        _CACHE.clear()
        return n
    # Keys are hashes — scan values for match markers when present.
    removed = 0
    for key, (_exp, value) in list(_CACHE.items()):
        if project_id and value.get("projectId") != project_id:
            continue
        if specialist_id and value.get("specialistId") != specialist_id:
            continue
        if project_id or specialist_id:
            _CACHE.pop(key, None)
            removed += 1
    return removed
