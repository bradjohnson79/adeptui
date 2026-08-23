"""Unified ImageProviderRegistry — local certified + dock hosted image models (M4.8)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from .contracts import GenerationMode, ImageProviderDescriptor, ProviderReadiness, ResolutionLabel

GenerationModeFilter = Literal["best_match", "choose_model", "all_models"]

_FAMILY_FALLBACK: dict[str, str] = {
    "qwen-image-edit-2509-local": "qwen_edit_2509",
    "qwen-image-2512-local": "qwen2512",
    "flux-local": "flux",
    "zimage-local": "zimage",
    "illustrious-local": "illustrious",
    "krea2-turbo-local": "krea2",
    "krea2-raw-local": "krea2",
    "flux-kie": "flux",
    "flux-fal": "flux",
    "nano-banana-kie": "imagen",
    "gpt-image-2-kie": "imagen",
    "seedream-kie": "imagen",
    "krea2-turbo-fal": "krea2",
    "krea2-medium-fal": "krea2",
    "krea2-large-fal": "krea2",
    "hidream-local": "hidream",
    "flux-schnell-local": "flux",
    "flux-dev-local": "flux",
    "sensenova-u15-local": "sensenova",
}

_HINTS: dict[str, dict[str, Any]] = {
    "qwen-image-edit-2509-local": {
        "nativeResolutions": ["1K", "2K"],
        "upscaleSupported": False,
        "licenseNote": "Apache-2.0 local (Qwen-Image-Edit-2509 I2I)",
        "costHint": "Local GPU",
    },
    "qwen-image-2512-local": {
        "nativeResolutions": ["1K", "2K"],
        "upscaleSupported": True,
        "licenseNote": "Open-weight local (Qwen-Image-2512)",
        "costHint": "Local GPU",
    },
    "flux-local": {
        "nativeResolutions": ["1K"],
        "upscaleSupported": True,
        "licenseNote": "FLUX Dev — check local license terms",
        "costHint": "Local GPU",
    },
    "zimage-local": {
        "nativeResolutions": ["1K"],
        "upscaleSupported": True,
        "licenseNote": "Local certified Z-Image",
        "costHint": "Local GPU",
    },
    "krea2-turbo-local": {
        "nativeResolutions": ["1K", "2K"],
        "nativePixelSizes": ["1024x1024", "1536x1024", "1024x1536", "1920x1080", "2048x2048"],
        "upscaleSupported": True,
        "licenseNote": (
            "Krea 2 Community License — commercial use under $1M annual revenue; "
            "gated HF download, license acceptance required"
        ),
        "costHint": "Local GPU (24 GB-class VRAM)",
    },
    "krea2-raw-local": {
        "nativeResolutions": ["1K", "2K"],
        "nativePixelSizes": ["1024x1024", "1536x1024", "1024x1536", "1920x1080", "2048x2048"],
        "upscaleSupported": False,
        "licenseNote": (
            "Krea 2 Community License — RAW is the LoRA training base "
            "(train on RAW, run on Turbo), not a creator default"
        ),
        "costHint": "Local GPU (24 GB-class VRAM)",
    },
    "flux-fal": {
        "nativeResolutions": ["1K", "2K"],
        "upscaleSupported": True,
        "licenseNote": "Hosted FLUX via fal — provider terms apply",
        "costHint": "Paid hosted API",
    },
    "flux-kie": {
        "nativeResolutions": ["1K", "2K"],
        "upscaleSupported": True,
        "licenseNote": "Hosted FLUX via Kie — provider terms apply",
        "costHint": "Paid hosted API",
    },
    "nano-banana-kie": {
        "nativeResolutions": ["1K", "2K"],
        "upscaleSupported": False,
        "licenseNote": "Hosted Imagen-class via Kie — provider terms apply",
        "costHint": "Paid hosted API",
    },
    "gpt-image-2-kie": {
        "nativeResolutions": ["1K", "2K"],
        "upscaleSupported": False,
        "licenseNote": "Hosted GPT Image 2 via Kie — provider terms apply",
        "costHint": "Paid hosted API",
    },
    "seedream-kie": {
        "nativeResolutions": ["1K", "2K"],
        "upscaleSupported": False,
        "licenseNote": "Hosted Seedream 5 Pro via Kie — provider terms apply",
        "costHint": "Paid hosted API",
    },
    "krea2-turbo-fal": {
        "nativeResolutions": ["1K", "2K"],
        "upscaleSupported": False,
        "licenseNote": "Hosted Krea 2 Turbo via fal — provider terms apply",
        "costHint": "Paid hosted API",
    },
    "krea2-medium-fal": {
        "nativeResolutions": ["1K"],
        "upscaleSupported": False,
        "licenseNote": "Hosted Krea 2 Medium via fal — provider terms apply",
        "costHint": "Paid hosted API",
    },
    "krea2-large-fal": {
        "nativeResolutions": ["1K"],
        "upscaleSupported": False,
        "licenseNote": "Hosted Krea 2 Large via fal — provider terms apply",
        "costHint": "Paid hosted API",
    },
    "hidream-local": {
        "nativeResolutions": ["1K"],
        "upscaleSupported": False,
        "licenseNote": "HiDream — install required; license per vendor",
        "costHint": "Local GPU",
    },
    "flux-schnell-local": {
        "nativeResolutions": ["1K"],
        "upscaleSupported": False,
        "licenseNote": "FLUX Schnell — check license",
        "costHint": "Local GPU",
    },
    "flux-dev-local": {
        "nativeResolutions": ["1K"],
        "upscaleSupported": False,
        "licenseNote": "FLUX Dev — non-commercial / license restricted",
        "costHint": "Local GPU",
    },
    "sensenova-u15-local": {
        "nativeResolutions": ["2K"],
        "nativePixelSizes": ["2720x1536", "2048x2048"],
        "upscaleSupported": False,
        "licenseNote": "Apache-2.0 local (SenseNova U1.5-8B-MoT)",
        "costHint": "Local GPU (24 GB-class VRAM)",
    },
}


def _family_for(model_id: str) -> str:
    try:
        from ..production_control.runtime_map import image_family_for_dock_model

        fam = image_family_for_dock_model(model_id)
        if fam:
            return str(fam)
    except Exception:
        pass
    return _FAMILY_FALLBACK.get(model_id, model_id.split("-")[0] if model_id else "unknown")


def _map_local_readiness(model: Any) -> ProviderReadiness:
    """Map a local dock model's fields to readiness.

    "ready" is asserted only when the model's Setup/Source Manager component
    verifies on disk — callers must pass a disk-verified model (see
    _local_readiness, which consults _COMPONENT_GATE_BY_MODEL). Certified
    registry status alone never implies installed/executable (CDX-075).
    """
    cap = str(getattr(model, "capabilityLabel", "") or "")
    lifecycle = str(getattr(model, "lifecycle", "") or "").lower()
    executable = bool(getattr(model, "executable", False))
    if lifecycle in {"not_installed", "missing"}:
        return "not_installed"
    if cap == "Certified" and executable:
        return "ready"
    if cap in {"Draft", "Testing"}:
        return "draft"
    if not executable:
        return "incompatible"
    return "draft"


#: Local image models whose advertised readiness is gated on a Setup component
#: verification, so weights that are not on disk never present as ready
#: (CDX-075). Mirrors production_control.model_registry._SETUP_COMPONENT_BY_MODEL_ID.
#: A model is "ready" only when its weights verify on disk; Certified metadata
#: alone is never install truth.
_COMPONENT_GATE_BY_MODEL: dict[str, str] = {
    "qwen-image-edit-2509-local": "qwen_image_edit_2509_models",
    "qwen-image-2512-local": "qwen_image_2512_models",
    "zimage-local": "zimage_models",
    "flux-local": "flux1_dev_local",
    "flux-schnell-local": "flux1_schnell_local",
    "flux-kontext-dev-local": "flux1_kontext_dev_local",
    "krea2-turbo-local": "krea2_models",
    "krea2-raw-local": "krea2_models",
    "sana-15-local": "sana_15_local",
    "sdxl-local": "sdxl_local",
    "sd35-large-local": "sd35_large_local",
    "cogview-4-local": "cogview4_local",
    "hidream-local": "hidream_local",
    "lumina-image-2-local": "lumina_image_2_local",
    "pixart-sigma-local": "pixart_sigma_local",
    "kolors-local": "kolors_local",
    "omnigen-local": "omnigen_local",
    "janus-pro-local": "janus_pro_local",
    "hunyuan-image-local": "hunyuan_image_local",
    "sensenova-u15-local": "sensenova_u15_models",
}

#: Dock model → certified-registry workflow whose capability flags the
#: descriptor advertises (single source of truth: the workflow registry).
_CAPABILITY_WORKFLOW_BY_MODEL: dict[str, str] = {
    "krea2-turbo-local": "krea2.turbo_txt2img",
    "krea2-raw-local": "krea2.raw_txt2img",
}

_CAPABILITY_REASON = (
    "Style, moodboard, character, and environment (ERS) reference images plus "
    "LoRA controls are wired into the Krea 2 graph builders. They require the "
    "ComfyUI reference support nodes (CLIPVision + IPAdapter) and LoRA files "
    "installed under the Krea 2 model root — environment references keep their "
    "ERS role in Adept metadata."
)


def _workflow_capabilities(model_id: str) -> dict[str, Any]:
    """Capability flags for a dock model from the certified workflow registry.

    Never invents capability: a registry miss yields an empty dict.
    """
    key = _CAPABILITY_WORKFLOW_BY_MODEL.get(model_id)
    if not key:
        return {}
    try:
        from ..image_runtime.certified_registry import get_workflow

        wf = get_workflow(key)
        if wf is None:
            return {}
        caps = {k: v for k, v in dict(wf.capabilities or {}).items() if isinstance(v, bool)}
        caps["reason"] = _CAPABILITY_REASON
        return caps
    except Exception:  # noqa: BLE001 - a broken registry must not invent capability
        return {}


def _local_readiness(model: Any) -> ProviderReadiness:
    mid = str(getattr(model, "id", "") or "")
    component_id = _COMPONENT_GATE_BY_MODEL.get(mid)
    if component_id:
        try:
            from ..setup.diagnostics import verify_component

            if not verify_component(component_id).healthy:
                return "not_installed"
        except Exception:  # noqa: BLE001 - a broken probe must not invent readiness
            return "not_installed"
    return _map_local_readiness(model)


def _map_hosted_readiness(row: dict[str, Any]) -> ProviderReadiness:
    ready = str(row.get("readiness") or "")
    if ready == "Ready" and row.get("executable") and row.get("selectable"):
        return "ready"
    if ready in {"Requires Setup", "Needs Auth"} or not row.get("accountAccessible", True):
        return "needs_auth"
    if ready in {"Requires Adapter"}:
        return "incompatible"
    if ready in {"Unhealthy", "Failed"}:
        return "unhealthy"
    if not row.get("executable"):
        return "disabled"
    return "draft"


def _from_local_model(model: Any) -> ImageProviderDescriptor:
    mid = str(getattr(model, "id", "") or "")
    hints = _HINTS.get(mid, {})
    exec_class = str(getattr(model, "executionClass", "") or "")
    source: Literal["local", "hosted", "docker"] = (
        "docker" if exec_class == "docker_local" else "local"
    )
    readiness = _local_readiness(model)
    capability_label = getattr(model, "capabilityLabel", None)
    lifecycle = getattr(model, "lifecycle", None)
    # Static catalog may say Certified/Installed; never advertise that while
    # the Setup-gated weights are not on disk.
    if readiness == "not_installed":
        if capability_label in {"Certified", "Installed"}:
            capability_label = "Requires Setup"
        if lifecycle in {"Installed", "Certified"}:
            lifecycle = "Not Installed"
    metadata = {
        "capabilityLabel": capability_label,
        "executionClass": exec_class,
        "supports": list(getattr(model, "supports", None) or []),
        "estimatedVramGb": getattr(model, "estimatedVramGb", None),
        "lifecycle": lifecycle,
        "defaultEligible": bool(getattr(model, "defaultEligible", False)),
    }
    caps = _workflow_capabilities(mid)
    if caps:
        metadata["capabilities"] = caps
    if hints.get("nativePixelSizes"):
        metadata["nativePixelSizes"] = list(hints["nativePixelSizes"])
    return ImageProviderDescriptor(
        id=mid,
        displayName=str(getattr(model, "label", mid) or mid),
        family=_family_for(mid),
        source=source,
        readiness=readiness,
        imageCapable=True,
        licenseNote=hints.get("licenseNote"),
        costHint=hints.get("costHint", "Local GPU"),
        requiresPaidConfirmation=False,
        nativeResolutions=list(hints.get("nativeResolutions") or ["1K"]),
        upscaleSupported=bool(hints.get("upscaleSupported", False)),
        providerPreference=str(getattr(model, "providerId", "") or "comfy") or None,
        modelId=mid,
        metadata=metadata,
    )


def _from_hosted_row(row: dict[str, Any]) -> ImageProviderDescriptor:
    mid = str(row.get("id") or row.get("modelId") or "")
    hints = _HINTS.get(mid, {})
    pricing = row.get("pricingMetadata") if isinstance(row.get("pricingMetadata"), dict) else {}
    cost = hints.get("costHint") or pricing.get("summary") or "Paid hosted API"
    return ImageProviderDescriptor(
        id=mid,
        displayName=str(row.get("label") or row.get("displayName") or mid),
        family=_family_for(mid),
        source="hosted",
        readiness=_map_hosted_readiness(row),
        imageCapable=True,
        licenseNote=hints.get("licenseNote") or "Hosted provider terms apply",
        costHint=str(cost),
        requiresPaidConfirmation=True,
        nativeResolutions=list(hints.get("nativeResolutions") or ["1K", "2K"]),
        upscaleSupported=bool(hints.get("upscaleSupported", False)),
        providerPreference=str(row.get("providerId") or "") or None,
        modelId=mid,
        metadata={
            "providerModelId": row.get("providerModelId"),
            "accountAccessible": row.get("accountAccessible"),
            "liveProbeStatus": row.get("liveProbeStatus"),
            "capabilityLabel": row.get("capabilityLabel"),
            "supports": list(row.get("capabilities") or row.get("supports") or []),
        },
    )


def list_image_providers(*, include_unready: bool = True) -> list[ImageProviderDescriptor]:
    """
    Merge Production Dock local image models + ready hosted discovery rows.
    Does not invent readiness — maps existing dock/registry truth.
    """
    out: list[ImageProviderDescriptor] = []
    seen: set[str] = set()

    try:
        from ..production_control.model_registry import is_ordinary_picker_hidden, list_models

        for model in list_models("image"):
            if is_ordinary_picker_hidden(str(getattr(model, "id", "") or "")):
                continue
            locality = str(getattr(model, "locality", "") or "")
            if locality not in {"local", "docker"} and getattr(model, "executionClass", "") != "docker_local":
                # Hosted static catalog rows are superseded by live discovery when available
                if locality == "hosted":
                    continue
            desc = _from_local_model(model)
            if not include_unready and desc.readiness != "ready":
                continue
            if desc.id and desc.id not in seen:
                seen.add(desc.id)
                out.append(desc)
    except Exception:
        pass

    try:
        from ..hosted_providers.discovery import dock_api_models

        payload = dock_api_models("image") or {}
        for row in payload.get("models") or []:
            if not isinstance(row, dict):
                continue
            desc = _from_hosted_row(row)
            if not include_unready and desc.readiness != "ready":
                continue
            if desc.id and desc.id not in seen:
                seen.add(desc.id)
                out.append(desc)
    except Exception:
        # Fall back to static hosted catalog rows
        try:
            from ..production_control.model_registry import list_models

            for model in list_models("image"):
                if str(getattr(model, "locality", "")) != "hosted":
                    continue
                mid = str(getattr(model, "id", "") or "")
                if mid in seen:
                    continue
                hints = _HINTS.get(mid, {})
                desc = ImageProviderDescriptor(
                    id=mid,
                    displayName=str(getattr(model, "label", mid) or mid),
                    family=_family_for(mid),
                    source="hosted",
                    readiness="ready" if getattr(model, "executable", False) else "needs_auth",
                    imageCapable=True,
                    licenseNote=hints.get("licenseNote"),
                    costHint=hints.get("costHint", "Paid hosted API"),
                    requiresPaidConfirmation=True,
                    nativeResolutions=list(hints.get("nativeResolutions") or ["1K"]),
                    upscaleSupported=bool(hints.get("upscaleSupported", False)),
                    providerPreference=str(getattr(model, "providerId", "") or "") or None,
                    modelId=mid,
                    metadata={"fallback": "static_catalog"},
                )
                if not include_unready and desc.readiness != "ready":
                    continue
                seen.add(mid)
                out.append(desc)
        except Exception:
            pass

    def _sort_key(d: ImageProviderDescriptor) -> tuple:
        src_order = {"local": 0, "docker": 1, "hosted": 2}.get(d.source, 9)
        ready_order = 0 if d.readiness == "ready" else 1
        return (src_order, ready_order, d.displayName.lower())

    return sorted(out, key=_sort_key)


def providers_for_mode(
    mode: GenerationMode | GenerationModeFilter,
    *,
    prompt: str = "",
    purpose: str = "",
    preferred_family: str | None = None,
) -> dict[str, Any]:
    """
    Best Match / Choose Model / All Models eligibility.
    """
    all_providers = list_image_providers(include_unready=True)
    ready = [p for p in all_providers if p.readiness == "ready" and p.imageCapable]

    recommendation: dict[str, Any] = {}
    try:
        from ..image_product.recommend import recommend_image_family

        recommendation = recommend_image_family(
            prompt=prompt,
            purpose=purpose,
            model_family_preference=preferred_family,
        )
    except Exception:
        recommendation = {"recommendedFamily": preferred_family or "qwen2512"}

    fam = str(recommendation.get("recommendedFamily") or preferred_family or "qwen2512")
    best = next((p for p in ready if p.family == fam), None)
    if best is None and ready:
        best = ready[0]

    paid = [p for p in ready if p.requiresPaidConfirmation]

    if mode == "best_match":
        selected = [best] if best else []
    elif mode == "choose_model":
        selected = ready
    else:  # all_models
        selected = all_providers

    return {
        "mode": mode,
        "recommendation": recommendation,
        "bestMatch": best.model_dump() if best else None,
        "providers": [p.model_dump() for p in selected],
        "readyCount": len(ready),
        "paidProvidersRequireConfirmation": [p.id for p in paid],
        "costPreflight": {
            "localReady": [p.id for p in ready if p.source in {"local", "docker"}],
            "hostedReady": [p.id for p in paid],
            "note": "Hosted API models require explicit paid confirmation before enqueue.",
        },
    }


def family_catalog() -> list[dict[str, Any]]:
    """Family readiness including qwen2512 — replaces stale hard-coded families() list."""
    from ..image_product.recommend import _estimates, _executable, _family_status

    labels = {
        "qwen_edit_2509": "Qwen Image Edit 2509",
        "qwen2512": "Qwen-Image-2512",
        "zimage": "ZImage",
        "flux": "FLUX",
        "qwen": "Qwen (legacy)",
        "imagen": "Imagen",
        "hidream": "HiDream",
        "krea2": "Krea 2",
        "sensenova": "SenseNova U1.5",
    }
    families = ("qwen2512", "zimage", "flux", "qwen", "imagen", "hidream", "krea2", "sensenova")
    out = []
    for fam in families:
        status = _family_status(fam)
        out.append(
            {
                "family": fam,
                "status": status,
                "executable": _executable(fam),
                "estimates": _estimates(fam),
                "label": labels.get(fam, fam),
            }
        )
    return out
