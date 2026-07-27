"""Read handlers for local-system readiness: provider, ComfyUI, sources, references, engines.

Each of these reads from the capability snapshot the adapter already built for this turn rather
than re-probing, so a single chat turn never hits ComfyUI or Ollama twice for the same answer.
"""

from __future__ import annotations

from typing import Any

from ....db import Project
from ..definitions import ToolContext


def _detail(ctx: ToolContext, key: str) -> dict[str, Any]:
    state = ctx.capabilities.get(key)
    detail = getattr(state, "detail", None)
    return detail if isinstance(detail, dict) else {}


async def get_provider_health(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ... import service as codirector_service

    health = await codirector_service.get_health()
    payload = health.to_dict()
    # Endpoint is an operator-side deployment detail with no value to the model, and it can
    # carry a host/port an untrusted reply shouldn't be able to echo back.
    payload.pop("endpoint", None)
    payload.pop("models", None)
    payload["modelCount"] = len(health.models)
    return payload


async def get_selected_model(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ... import service as codirector_service

    health = await codirector_service.get_health()
    return {
        "providerId": health.provider_id,
        "selectedModel": health.selected_model,
        "modelAvailable": health.model_available,
        "status": health.status,
        "availableModels": [m.id for m in health.models][:25],
    }


async def get_comfyui_health(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    stats = _detail(ctx, "comfyui").get("systemStats") or {}
    devices = stats.get("devices") if isinstance(stats, dict) else None
    device = devices[0] if isinstance(devices, list) and devices else {}
    return {
        "reachable": True,
        "deviceName": device.get("name") if isinstance(device, dict) else None,
        "vramTotalBytes": device.get("vram_total") if isinstance(device, dict) else None,
        "vramFreeBytes": device.get("vram_free") if isinstance(device, dict) else None,
    }


async def get_source_manager_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    overview = _detail(ctx, "source_manager")
    sources = overview.get("sources")
    assignments = overview.get("assignments")
    providers = overview.get("providers")
    return {
        "sourceCount": len(sources) if isinstance(sources, (list, dict)) else 0,
        "assignmentCount": len(assignments) if isinstance(assignments, (list, dict)) else 0,
        "providerIds": [
            p.get("id") for p in providers if isinstance(p, dict)
        ] if isinstance(providers, list) else [],
    }


async def get_reference_capabilities(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    caps = _detail(ctx, "references")
    return {
        "modelId": caps.get("model_id"),
        "modelReady": bool(caps.get("model_ready")),
        "nodesAvailable": bool(caps.get("nodes_available")),
        "icLoraOptionEnabled": bool(caps.get("ic_lora_option_enabled")),
        "workflowKey": caps.get("workflow_key"),
        "workflowVersion": caps.get("workflow_version"),
        "blockers": list(caps.get("blockers") or [])[:10],
        "vramWarning": caps.get("vram_warning"),
    }


async def get_cloud_render_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """fal.ai connection state + the engines it unlocks.

    Deliberately returns no credential material: not the key, not the masked hint, not the
    fingerprint. The model only needs to know whether cloud rendering will work and what to
    tell the user if it will not.
    """
    from ....fal_catalog import list_fal_models
    from ....secrets_store import secret_status

    status = secret_status("fal_api_key")
    state = str(status.get("state") or "missing")
    usable = state == "verified"
    engines = [
        {
            "engine": m["engine"],
            "label": m["label"],
            "mediaType": m.get("media_type", "video"),
            "mode": m["mode"],
            "durations": m["durations"],
        }
        for m in list_fal_models()
    ]
    guidance = {
        "missing": "No fal.ai key is saved. The user can add one in Project Settings → Integrations.",
        "invalid": "fal.ai rejected the saved key. The user needs to replace it before cloud renders will run.",
        "unverified": "A fal.ai key is saved but has not been confirmed with fal.ai; cloud renders may fail.",
        "verified": "fal.ai accepted the saved key; cloud engines are available.",
    }
    return {
        "provider": "fal.ai",
        "credentialState": state,
        "cloudRenderUsable": usable,
        "verifiedAt": status.get("verifiedAt"),
        "guidance": guidance.get(state, ""),
        "engines": engines,
        "imageEnginesAvailable": [e for e in engines if e["mediaType"] == "image"],
    }


async def get_engine_capabilities(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....preview_bus import preview_bus

    engine = args.get("engine")
    if not engine:
        project = ctx.db.get(Project, ctx.project_id) if ctx.project_id else None
        engine = getattr(project, "engine_default", None) or "ltx"
    return {"engine": engine, "capabilities": preview_bus.capabilities_for(str(engine))}
