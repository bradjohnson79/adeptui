from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from ..config import settings
from .catalog import REMOVED_UNUSED_SETUP_COMPONENT_IDS

SCHEMA_VERSION = 3
_LOCK = threading.RLock()


def state_path() -> Path:
    return settings.data_dir / "setup_state.json"


def empty_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "components": {},
        "model_locations": {},
        "status": {},
        "operations": {},
        "update_dismissals": {},
        "source_overrides": {},
        "download_sources": {},
        # Source Manager (Phase 1)
        "sources": {},
        "component_sources": {},
        "install_receipts": {},
        "download_queue": {},
        "source_manager": {},
        "model_license_acknowledgements": {},
    }


def normalize_state(raw: Any) -> dict[str, Any]:
    state = dict(raw) if isinstance(raw, dict) else {}
    # Preserve newer schema versions written by Source Manager migration; never downgrade.
    try:
        existing = int(state.get("schema_version") or 0)
    except (TypeError, ValueError):
        existing = 0
    state["schema_version"] = max(existing, SCHEMA_VERSION)
    for key in (
        "components",
        "model_locations",
        "status",
        "operations",
        "update_dismissals",
        "source_overrides",
        "download_sources",
        "sources",
        "component_sources",
        "install_receipts",
        "download_queue",
        "source_manager",
        "model_license_acknowledgements",
    ):
        if not isinstance(state.get(key), dict):
            state[key] = {}
    _drop_removed_components(state)
    # Missing means not yet migrated. Only an explicit true is complete.
    if "first_run_setup_complete" in state:
        state["first_run_setup_complete"] = state.get("first_run_setup_complete") is True
    return state


def _drop_removed_components(state: dict[str, Any]) -> None:
    """Drop Setup records for components Adept UI 1.1 no longer manages.

    Leftover status rows otherwise keep showing Repair Recommended / Not Found
    after the catalog entry is gone.
    """
    # Status rows are what Setup reloads into Repair Recommended / Not Found.
    # Installer fixtures may still record a path while exercising the generic
    # pack engine; those paths are not a public Setup component.
    status = state.get("status")
    if isinstance(status, dict):
        for component_id in REMOVED_UNUSED_SETUP_COMPONENT_IDS:
            status.pop(component_id, None)


def load_state() -> dict[str, Any]:
    with _LOCK:
        path = state_path()
        if not path.exists():
            return empty_state()
        try:
            return normalize_state(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return empty_state()


def save_state(state: dict[str, Any]) -> dict[str, Any]:
    """Atomically persist bounded, secret-free setup state."""
    with _LOCK:
        clean = normalize_state(state)
        operations = clean["operations"]
        if len(operations) > 50:
            ordered = sorted(
                operations.items(),
                key=lambda item: (
                    str(item[1].get("updated_at", ""))
                    if isinstance(item[1], dict) else ""
                ),
                reverse=True,
            )
            clean["operations"] = dict(ordered[:50])
        for summary in clean["operations"].values():
            if isinstance(summary, dict):
                summary.pop("logs", None)
                summary.pop("checkpoint_response", None)

        path = state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(clean, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return clean


def update_state(mutator) -> dict[str, Any]:
    with _LOCK:
        state = load_state()
        mutator(state)
        return save_state(state)
