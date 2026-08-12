"""Preflight surface: registry + live Comfy inventories + VRAM."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .compatibility_registry import (
    assert_not_deferred,
    get_entry,
    missing_nodes,
    validate_inputs,
)
from .vram_safety import estimate_vram


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_preflight(
    workflow_key: str,
    *,
    width: int | None = None,
    height: int | None = None,
    frames: int | None = None,
    present_inputs: list[str] | None = None,
    apply_safe_config: bool = False,
) -> dict[str, Any]:
    """Return Ready/Blocked preflight payload matching the 4.1A brief."""
    from ..comfy_client import comfy
    from ..comfy_health import comfy_health
    from ..workflows.readiness import ensure_queueable

    entry = get_entry(workflow_key)
    health = await comfy_health()
    connected = bool(health.get("reachable"))

    node_types: set[str] | None = None
    try:
        catalogue = await comfy.get_object_info()
        if isinstance(catalogue, dict) and catalogue:
            node_types = {str(k) for k in catalogue}
    except Exception:  # noqa: BLE001
        node_types = None

    if entry is None:
        return {
            "workflow": workflow_key,
            "runtime": "Connected" if connected else "Unavailable",
            "status": "blocked",
            "statusLabel": "Blocked",
            "message": f"No compatibility registry entry for {workflow_key}.",
            "checkedAt": _now(),
        }

    if entry.capability_state == "deferred":
        return {
            "workflow": entry.model_family + " — " + entry.workflow_version,
            "workflowKey": entry.workflow_key,
            "runtime": "Connected" if connected else "Unavailable",
            "status": "blocked",
            "statusLabel": "Deferred",
            "message": "This capability is deferred and cannot execute.",
            "capabilityState": "deferred",
            "knownLimitations": list(entry.known_limitations),
            "checkedAt": _now(),
        }

    missing_node_list: list[str] = []
    nodes_required = len(entry.required_nodes)
    nodes_available: int | None = None
    if entry.provider_kind.value == "local":
        maybe_missing = missing_nodes(entry, node_types)
        if maybe_missing is None:
            nodes_label = f"?/{nodes_required}"
        else:
            missing_node_list = maybe_missing
            nodes_available = nodes_required - len(missing_node_list)
            nodes_label = f"{nodes_available}/{nodes_required} available"
    else:
        nodes_label = "n/a (cloud)"

    model_missing: list[str] = []
    model_label = "n/a"
    if entry.provider_kind.value == "local" and entry.required_models:
        total = len(entry.required_models)
        try:
            readiness = ensure_queueable(workflow_key, node_types=node_types)
            model_missing = [m["componentId"] for m in readiness.get("missingModels") or []]
            ok = total - len(model_missing)
            model_label = f"{ok}/{total} available"
        except Exception as exc:  # noqa: BLE001
            details = getattr(exc, "details", {}) or {}
            model_missing = list(details.get("missingModels") or [])
            ext = list(details.get("missingExtensions") or [])
            if ext and not missing_node_list:
                missing_node_list = ext
                nodes_available = max(0, nodes_required - len(ext))
                nodes_label = f"{nodes_available}/{nodes_required} available"
            ok = max(0, total - len(model_missing))
            model_label = f"{ok}/{total} available"

    bad_inputs = validate_inputs(entry, present_inputs or [])
    vram = estimate_vram(workflow_key, width=width, height=height, frames=frames, entry=entry)

    risk = {
        "VRAM_INSUFFICIENT": "Critical",
        "VRAM_HIGH_RISK": "High",
        "VRAM_TIGHT": "Medium",
        "VRAM_UNKNOWN": "Unknown",
        "VRAM_SAFE": "Low",
    }.get(vram.state.value, "Unknown")

    blocked_reasons: list[str] = []
    if entry.provider_kind.value == "local" and not connected:
        blocked_reasons.append("ComfyUI runtime is not connected.")
    if missing_node_list:
        blocked_reasons.append("Required nodes missing: " + ", ".join(missing_node_list))
    if model_missing:
        blocked_reasons.append("Required models missing: " + ", ".join(model_missing))
    if bad_inputs:
        blocked_reasons.append("Unsupported inputs: " + ", ".join(bad_inputs))
    if vram.state.value == "VRAM_INSUFFICIENT" and not apply_safe_config:
        blocked_reasons.append(vram.message)

    status = "ready" if not blocked_reasons else "blocked"
    devices = health.get("devices") or []
    available_vram = vram.available_gb
    if available_vram is None and devices:
        free_mb = devices[0].get("vramFreeMb")
        if isinstance(free_mb, (int, float)):
            available_vram = round(float(free_mb) / 1024.0, 2)

    return {
        "workflow": entry.model_family + " — " + entry.workflow_version,
        "workflowKey": entry.workflow_key,
        "runtime": "Connected" if connected else "Unavailable",
        "requiredNodes": nodes_label,
        "requiredModels": model_label,
        "nodesRequired": nodes_required,
        "nodesAvailable": nodes_available,
        "missingNodes": missing_node_list,
        "missingModels": model_missing,
        "unsupportedInputsPresent": bad_inputs,
        "estimatedVramGb": vram.estimated_gb,
        "availableVramGb": available_vram,
        "vramState": vram.state.value,
        "vramRecommendations": vram.recommendations,
        "safeConfig": vram.safe_config,
        "resolution": f"{width or '—'}×{height or '—'}",
        "frames": frames,
        "estimatedRisk": risk,
        "status": status,
        "statusLabel": "Ready" if status == "ready" else "Blocked",
        "message": "; ".join(blocked_reasons) if blocked_reasons else "Ready to queue.",
        "capabilityState": entry.capability_state,
        "knownLimitations": list(entry.known_limitations),
        "checkedAt": _now(),
    }


def ensure_local_queueable(workflow_key: str, *, node_types: set[str] | None) -> dict[str, Any]:
    """Hard stop before model load — deferred / missing nodes / models."""
    from ..workflows.readiness import ensure_queueable

    entry = get_entry(workflow_key)
    if entry is not None:
        assert_not_deferred(entry)
    return ensure_queueable(workflow_key, node_types=node_types)
