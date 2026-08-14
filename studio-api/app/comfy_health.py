"""Structured ComfyUI health.

Replaces the previous all-or-nothing check (a raw exception string plus three hardcoded
model-path probes against one developer's `%LOCALAPPDATA%`) with a payload that separates
three independent questions:

1. Is the ComfyUI service reachable at the configured URL?
2. Can we read its node catalogue (`/object_info`) so extension gaps are knowable?
3. Which catalogued model components are verified on disk?

Model presence is answered by the Setup component verifiers — the same source the Setup
Wizard and Source Manager use — so the answer stays consistent and points at real
component ids instead of prose labels.

Reason codes are duplicated as literals here (rather than imported from
`app.capabilities.errors`) to keep this module importable from the capability probes without
an import cycle.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from .config import settings

DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
DEPENDENCY_DEGRADED = "DEPENDENCY_DEGRADED"
MODEL_MISSING = "MODEL_MISSING"

#: Catalogued components that carry local generation weights, in priority order.
MODEL_COMPONENT_IDS: tuple[str, ...] = (
    "ltx_checkpoint",
    "ltx_2_5_checkpoint",
    "ltx_2_5_text_encoder",
    "ltx_2_5_video_vae",
    "ltx_2_5_audio_vae",
    "wan_models",
    "ltx23_ic_lora_ingredients",
    "zimage_models",
    "krea2_models",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _devices(stats: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for device in stats.get("devices") or []:
        if not isinstance(device, dict):
            continue
        total = device.get("vram_total")
        free = device.get("vram_free")
        out.append(
            {
                "name": str(device.get("name") or "")[:120],
                "type": str(device.get("type") or ""),
                "vramTotalMb": round(float(total) / (1024 * 1024)) if isinstance(total, (int, float)) else None,
                "vramFreeMb": round(float(free) / (1024 * 1024)) if isinstance(free, (int, float)) else None,
            }
        )
    return out


def _version(stats: dict[str, Any]) -> str | None:
    system = stats.get("system")
    if isinstance(system, dict):
        for key in ("comfyui_version", "comfy_version", "version"):
            value = system.get(key)
            if value:
                return str(value)[:64]
    return None


def model_component_states() -> list[dict[str, Any]]:
    """Verified state of each catalogued model component (no absolute paths for missing ones)."""
    from .setup.catalog import get_component, dependency_type_for
    from .setup.diagnostics import verify_component

    states: list[dict[str, Any]] = []
    for component_id in MODEL_COMPONENT_IDS:
        try:
            definition = get_component(component_id)
            verification = verify_component(component_id)
        except Exception:  # noqa: BLE001 - a broken probe must not break health
            states.append(
                {
                    "componentId": component_id,
                    "name": component_id,
                    "required": False,
                    "present": False,
                    "issueCode": "verification_failed",
                    "summary": "Component verification could not be completed.",
                    "dependencyType": "UNKNOWN",
                    "filename": None,
                    "expectedPath": None,
                }
            )
            continue
        meta = _component_filename_and_path(component_id, definition)
        states.append(
            {
                "componentId": component_id,
                "name": definition.name,
                "required": bool(definition.required),
                "present": bool(verification.healthy),
                "issueCode": verification.issue_code,
                "summary": verification.summary,
                "version": verification.version,
                "dependencyType": dependency_type_for(component_id),
                "filename": meta["filename"],
                "expectedPath": meta["expectedPath"],
            }
        )
    return states


def _component_filename_and_path(component_id: str, definition: Any) -> dict[str, Any]:
    """Best-effort mapping of a catalogued component to its expected filename + subpath.

    Used so the readiness contract can surface the exact missing dependency file
    (e.g. `gemma4-12b-...safetensors` under `models/text_encoders/`) without the
    frontend inferring from counts. Returns None when no static mapping is known
    (e.g. composite components like `wan_models`).
    """
    from .config import settings

    mapping = {
        "ltx_checkpoint": (settings.ltx_checkpoint, ("checkpoints", "diffusion_models")),
        "ltx_2_5_checkpoint": (settings.ltx_2_5_checkpoint, ("diffusion_models", "checkpoints")),
        "ltx_2_5_text_encoder": (settings.ltx_2_5_text_encoder, ("text_encoders",)),
        "ltx_2_5_video_vae": (settings.ltx_2_5_video_vae, ("vae",)),
        "ltx_2_5_audio_vae": (settings.ltx_2_5_audio_vae, ("vae",)),
        "ltx_2_5_spatial_upscaler": (settings.ltx_2_5_spatial_upscaler, ("upscale_models",)),
        "ltx_text_encoder": (settings.ltx_text_encoder, ("text_encoders",)),
    }
    spec = mapping.get(component_id)
    if not spec:
        return {"filename": None, "expectedPath": None}
    filename, extra_dirs = spec
    expected_path = "models/" + "/".join(extra_dirs) + "/"
    return {"filename": filename, "expectedPath": expected_path}


async def comfy_health(*, include_nodes: bool = True) -> dict[str, Any]:
    """Probe ComfyUI and return a structured, secret-free health payload."""
    from .comfy_client import comfy

    payload: dict[str, Any] = {
        "reachable": False,
        "status": "unreachable",
        "baseUrl": settings.comfy_url,
        "version": None,
        "devices": [],
        "nodeCatalogAvailable": False,
        "nodeTypeCount": 0,
        "reasonCode": DEPENDENCY_UNAVAILABLE,
        "message": "",
        "recommendedAction": "start_comfyui",
        "models": [],
        "missingModelComponentIds": [],
        "missingRequiredModelComponentIds": [],
        "missingOptionalModelComponentIds": [],
        "checkedAt": _now(),
    }

    try:
        stats = await comfy.health()
    except Exception:  # noqa: BLE001 - the reason is reported, never the stack trace
        payload["message"] = (
            f"ComfyUI is not reachable at {settings.comfy_url}. Start ComfyUI, then refresh."
        )
        payload["models"] = await asyncio.to_thread(model_component_states)
        payload["missingModelComponentIds"] = [
            item["componentId"] for item in payload["models"] if not item["present"]
        ]
        payload["missingRequiredModelComponentIds"] = [
            item["componentId"] for item in payload["models"] if item["required"] and not item["present"]
        ]
        payload["missingOptionalModelComponentIds"] = [
            item["componentId"]
            for item in payload["models"]
            if (not item["required"]) and not item["present"]
        ]
        return payload

    stats = stats if isinstance(stats, dict) else {}
    payload["reachable"] = True
    payload["version"] = _version(stats)
    payload["devices"] = _devices(stats)
    payload["reasonCode"] = None
    payload["recommendedAction"] = None
    payload["status"] = "ready"
    payload["message"] = "ComfyUI is reachable."

    if include_nodes:
        try:
            catalogue = await comfy.get_object_info()
        except Exception:  # noqa: BLE001
            catalogue = None
        if isinstance(catalogue, dict) and catalogue:
            payload["nodeCatalogAvailable"] = True
            payload["nodeTypeCount"] = len(catalogue)
        else:
            payload["status"] = "degraded"
            payload["reasonCode"] = DEPENDENCY_DEGRADED
            payload["recommendedAction"] = "review_comfyui_logs"
            payload["message"] = (
                "ComfyUI is reachable but its node catalogue could not be read, so extension "
                "gaps cannot be detected."
            )

    # Model disk verification is sync filesystem work — keep it off the event loop.
    payload["models"] = await asyncio.to_thread(model_component_states)
    missing = [item["componentId"] for item in payload["models"] if not item["present"]]
    payload["missingModelComponentIds"] = missing
    missing_required = [
        item["componentId"] for item in payload["models"] if item["required"] and not item["present"]
    ]
    missing_optional = [
        item["componentId"]
        for item in payload["models"]
        if (not item["required"]) and not item["present"]
    ]
    # Expose the required-only subset explicitly so downstream consumers (status probe,
    # capability layer, UI) can distinguish "a required model is missing" (runtime-relevant)
    # from "an optional/generator-specific component is missing" (generator-relevant only).
    payload["missingRequiredModelComponentIds"] = missing_required
    payload["missingOptionalModelComponentIds"] = missing_optional
    if missing_required:
        payload["status"] = "degraded"
        payload["reasonCode"] = MODEL_MISSING
        payload["recommendedAction"] = "open_source_manager"
        payload["message"] = (
            "ComfyUI is reachable but required local model components are missing: "
            + ", ".join(missing_required)
            + "."
        )
    payload["checkedAt"] = _now()
    return payload


async def node_types(*, timeout_sec: float = 30.0) -> set[str] | None:
    """Return the live ComfyUI node type names, or None when the catalogue is unavailable."""
    from .comfy_client import comfy

    try:
        catalogue = await asyncio.wait_for(comfy.get_object_info(), timeout=timeout_sec)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(catalogue, dict) or not catalogue:
        return None
    return {str(key) for key in catalogue.keys()}
