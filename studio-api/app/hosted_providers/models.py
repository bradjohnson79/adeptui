"""Canonical model registry — users see FLUX, not FLUX (Kie) / FLUX (fal)."""

from __future__ import annotations

from typing import Any


# Canonical model id → provider-specific implementation ids (opaque to UI).
CANONICAL_MODELS: dict[str, dict[str, Any]] = {
    "FLUX": {
        "displayName": "FLUX",
        "modality": "image",
        "mappings": {
            "kie": {"providerModelId": "flux", "status": "Testing"},
            "wavespeed": {"providerModelId": "wavespeed-ai/flux-dev", "status": "Testing"},
            "fal": {"providerModelId": "fal-ai/flux/dev", "status": "Available but Uncertified"},
        },
    },
    "Seedance": {
        "displayName": "Seedance",
        "modality": "video",
        "mappings": {
            "kie": {"providerModelId": "seedance", "status": "Testing"},
            "wavespeed": {"providerModelId": "seedance", "status": "Testing"},
            "fal": {"providerModelId": "fal-ai/bytedance/seedance", "status": "Certified", "engine": "fal_seedance"},
        },
    },
    "Kling": {
        "displayName": "Kling",
        "modality": "video",
        "mappings": {
            "kie": {"providerModelId": "kling", "status": "Testing"},
            "wavespeed": {"providerModelId": "kling", "status": "Available but Uncertified"},
            "fal": {"providerModelId": "fal-ai/kling-video", "status": "Certified", "engine": "fal_kling"},
        },
    },
    "Veo": {
        "displayName": "Veo",
        "modality": "video",
        "mappings": {
            "kie": {"providerModelId": "veo", "status": "Available but Uncertified"},
            "fal": {"providerModelId": "fal-ai/veo", "status": "Certified", "engine": "fal_veo"},
        },
    },
    "Runway": {
        "displayName": "Runway",
        "modality": "video",
        "mappings": {
            "fal": {"providerModelId": "fal-ai/runway", "status": "Certified", "engine": "fal_runway"},
        },
    },
}


def list_canonical_models(*, include_mappings: bool = False) -> list[dict[str, Any]]:
    out = []
    for mid, meta in CANONICAL_MODELS.items():
        item: dict[str, Any] = {
            "modelId": mid,
            "displayName": meta["displayName"],
            "modality": meta["modality"],
            "providerCount": len(meta.get("mappings") or {}),
        }
        if include_mappings:
            item["mappings"] = meta["mappings"]
        out.append(item)
    return out


def resolve_model_mapping(canonical_model: str, provider_id: str) -> dict[str, Any] | None:
    meta = CANONICAL_MODELS.get(canonical_model)
    if not meta:
        return None
    m = (meta.get("mappings") or {}).get(provider_id)
    if not m:
        return None
    return {"canonicalModel": canonical_model, "providerId": provider_id, **m}


def providers_for_model(canonical_model: str) -> list[str]:
    meta = CANONICAL_MODELS.get(canonical_model) or {}
    return list((meta.get("mappings") or {}).keys())
