"""Capability probe for Director Visual References / IC-LoRA."""

from __future__ import annotations

from typing import Any

import httpx

from ..config import settings
from .ic_lora_status import ingredients_status, public_resource_card
from .models import STRENGTH_PRESETS, WORKFLOW_KEY, WORKFLOW_VERSION


def fetch_object_info(comfy_url: str | None = None) -> dict[str, Any]:
    base = (comfy_url or settings.comfy_url).rstrip("/")
    try:
        response = httpx.get(f"{base}/object_info", timeout=12.0)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def reference_capabilities(
    *,
    configured_model_path: str | None = None,
    object_info: dict[str, Any] | None = None,
    vram_gb: float | None = None,
) -> dict[str, Any]:
    # Lazy import avoids circular import through workflows.registry.
    from ..workflows.ltx_ingredients_compiler import probe_ic_lora_nodes

    status = ingredients_status(configured_model_path)
    info = object_info if object_info is not None else fetch_object_info()
    probe = probe_ic_lora_nodes(info)
    blockers: list[str] = []
    if status.get("status") != "ready":
        blockers.append(status.get("message") or "Ingredients IC-LoRA is not ready.")
    if not probe.get("available"):
        blockers.append("Required ComfyUI IC-LoRA nodes are missing.")
    vram_warning = None
    if vram_gb is not None and vram_gb < 24:
        vram_warning = (
            f"Detected ~{vram_gb:.0f} GB VRAM. Ingredients IC-LoRA with LTX 2.3 may exceed available memory. "
            "Consider a lower resolution/frame count or unloading other models."
        )
        if vram_gb < 16:
            blockers.append(vram_warning)
    return {
        "model_id": status.get("model_id"),
        "model_ready": status.get("status") == "ready",
        "model_status": status.get("status"),
        "model_issue_code": status.get("issue_code"),
        "model_message": status.get("message"),
        "installed_filename": status.get("filename"),
        "nodes_available": bool(probe.get("available")),
        "strategy": probe.get("strategy"),
        "workflow_key": WORKFLOW_KEY,
        "workflow_version": WORKFLOW_VERSION,
        "blockers": blockers,
        "ic_lora_option_enabled": status.get("status") == "ready" and bool(probe.get("available")),
        "identity_option_enabled": False,
        "strength_presets": dict(STRENGTH_PRESETS),
        "vram_warning": vram_warning,
        "resource_card": public_resource_card(configured_model_path),
    }
