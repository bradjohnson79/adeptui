"""Embedding cache for world intelligence.

Cache keys by assetId, contentHash, modelId, modelRevision, and preprocessingVersion.
Stale embeddings are invalidated when source images change.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from .paths import embedding_cache_dir


def _content_hash(file_path: str) -> str:
    """Compute SHA-256 of file contents for cache invalidation."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _cache_key(
    asset_id: str,
    content_hash: str,
    model_id: str,
    model_revision: str,
    preprocess_version: str,
    project_id: str = "",
) -> str:
    """Build a deterministic cache key. Project id prevents cross-project hits."""
    raw = f"{project_id}|{asset_id}|{content_hash}|{model_id}|{model_revision}|{preprocess_version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _cache_path(cache_key: str, project_id: str = "") -> Path:
    """Get filesystem path for a cache entry. Project folders isolate embeddings."""
    d = embedding_cache_dir()
    if project_id:
        d = d / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{cache_key}.json"


def get_cached_embedding(
    asset_id: str,
    content_hash: str,
    model_id: str,
    model_revision: str,
    preprocess_version: str,
    project_id: str = "",
) -> Optional[dict]:
    """Retrieve cached embedding if valid."""
    key = _cache_key(asset_id, content_hash, model_id, model_revision, preprocess_version, project_id)
    path = _cache_path(key, project_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Verify content hash still matches
        if data.get("contentHash") != content_hash:
            path.unlink(missing_ok=True)
            return None
        return data
    except (json.JSONDecodeError, OSError):
        path.unlink(missing_ok=True)
        return None


def set_cached_embedding(
    asset_id: str,
    content_hash: str,
    model_id: str,
    model_revision: str,
    preprocess_version: str,
    embedding: list[float],
    metadata: Optional[dict[str, Any]] = None,
    project_id: str = "",
) -> str:
    """Store embedding in cache. Returns cache key."""
    key = _cache_key(asset_id, content_hash, model_id, model_revision, preprocess_version, project_id)
    path = _cache_path(key, project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "cacheKey": key,
        "assetId": asset_id,
        "projectId": project_id,
        "contentHash": content_hash,
        "modelId": model_id,
        "modelRevision": model_revision,
        "preprocessingVersion": preprocess_version,
        "embedding": embedding,
        "metadata": metadata or {},
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return key


def _iter_cache_files():
    cache_dir = embedding_cache_dir()
    if not cache_dir.is_dir():
        return
    for f in cache_dir.rglob("*.json"):
        if f.is_file():
            yield f


def invalidate_embedding(asset_id: str) -> int:
    """Invalidate all cached embeddings for an asset. Returns count removed."""
    count = 0
    for f in _iter_cache_files():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("assetId") == asset_id:
                f.unlink()
                count += 1
        except (json.JSONDecodeError, OSError):
            continue
    return count


def invalidate_all() -> int:
    """Clear the entire embedding cache. Returns count removed."""
    count = 0
    for f in list(_iter_cache_files()):
        try:
            f.unlink()
            count += 1
        except OSError:
            continue
    return count


def compute_content_hash(file_path: str) -> str:
    """Public wrapper for content hash computation."""
    return _content_hash(file_path)
