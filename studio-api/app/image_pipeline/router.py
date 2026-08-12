"""Capability-aware model routing for the image pipeline foundation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import DeploymentPreference, ImageModelRoute, QualityProfile


def _normalize_family(value: str | None) -> str:
    family = (value or "").strip().lower()
    if family in {"qwen-image-2512", "qwen_image_2512"}:
        return "qwen2512"
    if family.startswith("qwen2512"):
        return "qwen2512"
    if family.startswith("zimage"):
        return "zimage"
    if family.startswith("imagen"):
        return "imagen"
    return family or "zimage"


def _registry_entries() -> list[dict[str, Any]]:
    try:
        from ..image_runtime.certified_registry import list_workflows

        return [item.to_dict() for item in list_workflows()]
    except Exception:
        path = Path(__file__).resolve().parents[3] / "config" / "image-workflows" / "certified-registry.json"
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        entries = data.get("entries")
        return list(entries) if isinstance(entries, list) else []


def _safe_local_defaults() -> list[dict[str, Any]]:
    return [
        {
            "workflowKey": "zimage.txt2img",
            "modelFamily": "zimage",
            "status": "Certified",
            "providerKind": "local",
            "provider": "comfyui",
        },
        {
            "workflowKey": "qwen2512.txt2img",
            "modelFamily": "qwen2512",
            "status": "Certified",
            "providerKind": "local",
            "provider": "comfyui",
        },
    ]


def _local_certified_entries() -> list[dict[str, Any]]:
    entries = _registry_entries() or _safe_local_defaults()
    local_entries = []
    for entry in entries:
        family = _normalize_family(str(entry.get("modelFamily") or entry.get("engine") or ""))
        provider_kind = str(entry.get("providerKind") or "local")
        if provider_kind != "local":
            continue
        if str(entry.get("status") or "") != "Certified":
            continue
        if not str(entry.get("workflowKey") or "").endswith("txt2img"):
            continue
        local_entries.append({**entry, "modelFamily": family})
    return local_entries or _safe_local_defaults()


def choose_model_route(
    *,
    quality_profile: QualityProfile,
    deployment_preference: DeploymentPreference,
    allow_api_deployment: bool = False,
) -> ImageModelRoute:
    if deployment_preference == "api" and not allow_api_deployment:
        return ImageModelRoute(
            workflowKey="approval-required",
            modelFamily="api",
            providerKind="api",
            provider="approval_required",
            deploymentTarget="api",
            certified=False,
            requiresApproval=True,
            approvedForUse=False,
            approvalReason="API deployment was requested but not explicitly approved.",
            readiness="blocked",
            honestyNote="The pipeline will not auto-select a paid API route without creator approval.",
            provenance={"policy": "no-silent-api-spend"},
        )

    preferred_family = "zimage" if quality_profile == "quick" else "qwen2512"
    local_entries = _local_certified_entries()
    selected = None
    for entry in local_entries:
        if _normalize_family(str(entry.get("modelFamily"))) == preferred_family:
            selected = entry
            break
    if selected is None:
        selected = local_entries[0]

    return ImageModelRoute(
        workflowKey=str(selected.get("workflowKey") or f"{preferred_family}.txt2img"),
        modelFamily=_normalize_family(str(selected.get("modelFamily") or preferred_family)),
        providerKind=str(selected.get("providerKind") or "local"),
        provider=str(selected.get("provider") or "comfyui"),
        deploymentTarget="local",
        certified=str(selected.get("status") or "") == "Certified",
        requiresApproval=False,
        approvedForUse=True,
        readiness="ready",
        honestyNote="Using a local certified route chosen for creator safety and predictable cost.",
        provenance={"deploymentPreference": deployment_preference, "qualityProfile": quality_profile},
    )

