"""Local cache for verified pack release metadata (no URLs or tokens)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from .pack_settings import pack_settings


def _cache_path() -> Path:
    root = settings.data_dir / "pack_release_cache"
    root.mkdir(parents=True, exist_ok=True)
    return root / "releases.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def load_cache() -> dict[str, Any]:
    path = _cache_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(data: dict[str, Any]) -> None:
    path = _cache_path()
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def get_cached_release(pack_id: str) -> dict[str, Any] | None:
    entry = load_cache().get(pack_id)
    if not isinstance(entry, dict):
        return None
    retrieved = entry.get("retrieved_at")
    if not retrieved:
        return None
    try:
        when = datetime.fromisoformat(str(retrieved).replace("Z", "+00:00"))
    except ValueError:
        return None
    ttl = pack_settings().cache_ttl_seconds
    if (_now() - when).total_seconds() > ttl:
        return None
    return entry


def put_cached_release(pack_id: str, payload: dict[str, Any]) -> None:
    data = load_cache()
    # Never persist download URLs or tokens.
    safe = {
        "pack_id": pack_id,
        "provider_id": payload.get("provider_id"),
        "repository": payload.get("repository"),
        "release_id": payload.get("release_id"),
        "tag_name": payload.get("tag_name"),
        "version": payload.get("version"),
        "channel": payload.get("channel"),
        "archive_asset_id": payload.get("archive_asset_id"),
        "archive_asset_name": payload.get("archive_asset_name"),
        "expected_bytes": payload.get("expected_bytes"),
        "checksum": payload.get("checksum"),
        "checksum_algorithm": payload.get("checksum_algorithm"),
        "required_files": payload.get("required_files"),
        "archive_format": payload.get("archive_format"),
        "minimum_studio_version": payload.get("minimum_studio_version"),
        "retrieved_at": payload.get("retrieved_at") or _now().isoformat(),
    }
    data[pack_id] = safe
    save_cache(data)


def clear_cached_release(pack_id: str | None = None) -> None:
    if pack_id is None:
        path = _cache_path()
        if path.exists():
            path.unlink()
        return
    data = load_cache()
    data.pop(pack_id, None)
    save_cache(data)
