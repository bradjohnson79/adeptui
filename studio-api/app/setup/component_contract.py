"""Catalog sidecar. IDs, verifiers, and installers stay on ComponentDefinition."""

from __future__ import annotations

from typing import Any

from .catalog import get_component
from .lifecycle.service import recipe_for_component

# Extra floors and source hints. Missing ids inherit catalog sizes and installer owners.
_EXTRAS: dict[str, dict[str, Any]] = {
    "python": {
        "vramFloorGb": 0,
        "ramFloorGb": 1,
        "source": {"kind": "existing_install", "componentId": "python", "owner": "detect_only"},
        "storageClass": "runtime",
        "restart": False,
    },
    "ffmpeg": {
        "vramFloorGb": 0,
        "ramFloorGb": 1,
        "source": {"kind": "existing_install", "componentId": "ffmpeg", "owner": "manual"},
        "storageClass": "runtime",
        "restart": False,
    },
    "comfyui": {
        "vramFloorGb": 0,
        "ramFloorGb": 4,
        "source": {"kind": "existing_install", "componentId": "comfyui", "owner": "manual"},
        "storageClass": "runtime",
        "restart": False,
    },
    "minimax_h3_base_optimized": {
        "vramFloorGb": 16,
        "ramFloorGb": 16,
        "source": {
            "kind": "existing_install",
            "componentId": "minimax_h3_base_optimized",
            "owner": "detect_only",
        },
        "storageClass": "model",
        "restart": False,
    },
}

_REQUIRED_KEYS = (
    "id",
    "vramFloorGb",
    "ramFloorGb",
    "diskFloorBytes",
    "sourcePriority",
    "source",
    "installOwner",
    "validationOwner",
    "restart",
    "storageClass",
    "channel",
)


def contract_for(component_id: str) -> dict[str, Any]:
    """Structured metadata for one catalog id. Does not invent a second component list."""
    component = get_component(component_id)
    extra = dict(_EXTRAS.get(component_id) or {})
    recipe = recipe_for_component(component_id)
    recipe_source = dict(recipe.source) if recipe and recipe.source else None
    source = extra.get("source") or recipe_source
    if not source:
        source = {
            "kind": "existing_install" if component.installer in {"detect_only", "manual", "path_link"} else "certified_recipe",
            "componentId": component.id,
            "owner": component.installer,
        }
    payload = {
        "id": component.id,
        "vramFloorGb": extra.get("vramFloorGb", 0),
        "ramFloorGb": extra.get("ramFloorGb", 0),
        "diskFloorBytes": int(extra.get("diskFloorBytes", component.installed_bytes or 0)),
        "sourcePriority": ["existing_valid_local", "certified_recipe", "registered_provider"],
        "source": source,
        "installOwner": component.installer,
        "validationOwner": component.verifier,
        "restart": bool(extra.get("restart", False)),
        "storageClass": extra.get("storageClass") or component.category or "core",
        "channel": "certified",
    }
    missing = [key for key in _REQUIRED_KEYS if payload.get(key) is None or payload.get(key) == ""]
    payload["complete"] = not missing
    payload["missing"] = missing
    return payload
