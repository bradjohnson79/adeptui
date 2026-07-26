"""Sandbox directory + install-manifest helpers (no weight download)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...config import settings
from .adapters.base import sandbox_providers_root
from .execution_lock import is_execution_authorized, list_authorized_candidates


def sandbox_root() -> Path:
    return Path(settings.data_dir) / "m210b-sandbox"


def ensure_sandbox_tree() -> Path:
    root = sandbox_root()
    providers = sandbox_providers_root()
    for path in (root, providers, root / "exports", root / "logs"):
        path.mkdir(parents=True, exist_ok=True)
    return root


def provider_sandbox_dir(registry_id: str) -> Path:
    return sandbox_providers_root() / registry_id


def create_provider_dirs(registry_id: str) -> Path:
    """Create isolated provider sandbox dirs. Does not download weights."""
    if not is_execution_authorized(registry_id):
        raise PermissionError(
            f"Cannot create sandbox dirs for unauthorized candidate {registry_id!r}"
        )
    root = provider_sandbox_dir(registry_id)
    for sub in ("venv", "models", "output", "cache", "logs"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def write_install_manifest(
    registry_id: str,
    *,
    installed: bool,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write install-manifest.json under the provider sandbox root."""
    if not is_execution_authorized(registry_id):
        raise PermissionError(
            f"Cannot write install manifest for unauthorized candidate {registry_id!r}"
        )
    root = create_provider_dirs(registry_id)
    payload: dict[str, Any] = {
        "registryId": registry_id,
        "installed": bool(installed),
        "sandboxOnly": True,
        "productionApproved": False,
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "allowAutomaticModelDownload": False,
    }
    if extra:
        payload.update(extra)
    path = root / "install-manifest.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def read_install_manifest(registry_id: str) -> dict[str, Any] | None:
    path = provider_sandbox_dir(registry_id) / "install-manifest.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def bootstrap_authorized_provider_dirs() -> list[str]:
    """Ensure sandbox dirs exist for every execution-authorized candidate."""
    ensure_sandbox_tree()
    created: list[str] = []
    for c in list_authorized_candidates():
        rid = str(c.get("registryId") or "")
        if not rid:
            continue
        create_provider_dirs(rid)
        created.append(rid)
    return created
