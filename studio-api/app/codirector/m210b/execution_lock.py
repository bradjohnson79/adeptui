"""Load and guard M2.10b execution lock vs Gate 6 product lock."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[4]
EXECUTION_LOCK_PATH = (
    _REPO_ROOT / "config/capabilities/adept-ui-v1.1-m2.10b-execution-lock.json"
)
PRODUCT_LOCK_PATH = (
    _REPO_ROOT / "config/capabilities/adept-ui-v1.1-product-approved-sandbox-lock.json"
)

_AUDIO_CAPS = (
    "audio.dialogue.generate",
    "audio.sfx.generate",
    "audio.music.generate",
    "audio.character_voice.design",
    "audio.character_voice.clone",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_execution_lock() -> dict[str, Any]:
    if not EXECUTION_LOCK_PATH.is_file():
        raise FileNotFoundError(f"M2.10b execution lock missing: {EXECUTION_LOCK_PATH}")
    return _load_json(EXECUTION_LOCK_PATH)


@lru_cache(maxsize=1)
def load_product_lock() -> dict[str, Any]:
    if not PRODUCT_LOCK_PATH.is_file():
        raise FileNotFoundError(f"Product-approved sandbox lock missing: {PRODUCT_LOCK_PATH}")
    return _load_json(PRODUCT_LOCK_PATH)


def _iter_candidates(lock: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_cap = lock.get("candidatesByCapability") or {}
    for cap in _AUDIO_CAPS:
        out.extend(list(by_cap.get(cap) or []))
    return out


def _find_candidate(lock: dict[str, Any], key: str) -> dict[str, Any] | None:
    needle = (key or "").strip()
    if not needle:
        return None
    for c in _iter_candidates(lock):
        if c.get("registryId") == needle or c.get("sourceKey") == needle:
            return c
    return None


def is_execution_authorized(registry_id_or_source_key: str) -> bool:
    """True when the candidate is execution+install authorized and not production-authorized.

    Requires both candidate-level ``executionAuthorized`` and ``installationAuthorized``.
    ``productionAuthorized`` must remain false (sandbox-only).
    """
    try:
        lock = load_execution_lock()
    except FileNotFoundError:
        return False
    if not lock.get("executionAuthorized"):
        return False
    if not lock.get("installationAuthorized"):
        return False
    if lock.get("productionAuthorized") is True:
        return False
    cand = _find_candidate(lock, registry_id_or_source_key)
    if not cand:
        return False
    if cand.get("productionAuthorized") is True or cand.get("productionApproved") is True:
        return False
    if not cand.get("executionAuthorized"):
        return False
    if not cand.get("installationAuthorized"):
        return False
    if cand.get("sandboxOnly") is False:
        return False
    return True


def assert_subset_of_product_lock() -> None:
    """Raise if any execution-lock candidate is outside the Gate 6 product lock."""
    exe = load_execution_lock()
    product = load_product_lock()
    product_keys = {
        (c.get("registryId"), c.get("sourceKey")) for c in _iter_candidates(product)
    }
    product_ids = {c.get("registryId") for c in _iter_candidates(product)}
    product_sources = {c.get("sourceKey") for c in _iter_candidates(product)}
    for c in _iter_candidates(exe):
        rid = c.get("registryId")
        sk = c.get("sourceKey")
        if (rid, sk) in product_keys:
            continue
        if rid in product_ids and sk in product_sources:
            continue
        raise AssertionError(
            f"execution lock candidate outside product lock: registryId={rid!r} sourceKey={sk!r}"
        )


def list_authorized_candidates() -> list[dict[str, Any]]:
    """Return execution-lock candidates that pass ``is_execution_authorized``."""
    lock = load_execution_lock()
    out: list[dict[str, Any]] = []
    for c in _iter_candidates(lock):
        key = c.get("registryId") or c.get("sourceKey") or ""
        if key and is_execution_authorized(str(key)):
            out.append(dict(c))
    return out


def clear_lock_caches() -> None:
    """Test helper to reload locks after file changes."""
    load_execution_lock.cache_clear()
    load_product_lock.cache_clear()
