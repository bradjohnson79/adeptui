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
    """Hosted AI Providers status (Kie.ai / WaveSpeed.ai / fal.ai) — no credential material."""
    from ....fal_catalog import list_fal_models
    from ....hosted_providers import service as hosted
    from ....hosted_providers.resolver import describe_for_codirector

    catalog = hosted.catalog()
    capability = str(args.get("capability") or "text_to_video")
    canonical_model = str(args.get("canonicalModel") or args.get("model") or "") or None
    resolution = hosted.resolve(capability=capability, canonical_model=canonical_model)
    engines = [
        {
            "engine": m["engine"],
            "label": m["label"],
            "mediaType": m.get("media_type", "video"),
            "mode": m["mode"],
            "durations": m["durations"],
            "hostedProvider": "fal",
        }
        for m in list_fal_models()
    ]
    providers = [
        {
            "providerId": p["providerId"],
            "displayName": p["displayName"],
            "role": p["role"],
            "recommended": p["recommended"],
            "connectionStatus": p["connectionStatus"],
            "healthStatus": p["healthStatus"],
            "certifiedModels": p["certifiedModels"],
        }
        for p in catalog.get("providers") or []
    ]
    any_usable = any(p.get("connectionStatus") == "verified" for p in providers)
    return {
        "hostedProviders": providers,
        "recommendationOrder": ["kie", "wavespeed", "fal"],
        "preferences": catalog.get("preferences"),
        "resolution": resolution,
        "codirector": describe_for_codirector(resolution),
        "cloudRenderUsable": any_usable or bool(resolution.get("ok")),
        "engines": engines,
        "imageEnginesAvailable": [e for e in engines if e["mediaType"] == "image"],
        "setupPath": "Setup → AI Providers (Project Settings → Integrations)",
        "silentSwitchForbidden": True,
        "guidance": resolution.get("explanation")
        or "Configure Hosted AI Providers under Setup → AI Providers: Kie.ai (recommended), WaveSpeed.ai, fal.ai.",
        "mock": False,
        # Legacy fields for existing clients
        "provider": "Hosted AI Providers",
        "credentialState": next(
            (p["connectionStatus"] for p in providers if p["providerId"] == "fal"),
            "missing",
        ),
    }


async def recommend_hosted_provider(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Provider-aware recommendation for Co-Director — never invents support."""
    from ....hosted_providers import service as hosted
    from ....hosted_providers.resolver import describe_for_codirector

    capability = str(args.get("capability") or "").strip() or None
    canonical_model = str(args.get("canonicalModel") or args.get("model") or "").strip() or None
    resolution = hosted.resolve(capability=capability, canonical_model=canonical_model)
    return {
        **describe_for_codirector(resolution),
        "resolution": resolution,
        "_evidence": {"source": "hosted_providers.resolver"},
    }


async def get_engine_capabilities(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....preview_bus import preview_bus

    engine = args.get("engine")
    if not engine:
        project = ctx.db.get(Project, ctx.project_id) if ctx.project_id else None
        engine = getattr(project, "engine_default", None) or "ltx"
    return {"engine": engine, "capabilities": preview_bus.capabilities_for(str(engine))}
