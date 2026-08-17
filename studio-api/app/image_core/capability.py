"""Capability tables lifted out of Scene Creator. Core owns certified edit paths."""

from __future__ import annotations

from typing import Any

# Certified I2I / visual-inheritance paths. qwen.edit is Draft/stub — omitted as ready.
# flux.edit is Draft; flux.img2img is the Certified FLUX image-edit path.
VISUAL_EDIT_CANDIDATES: dict[str, list[tuple[str, str, int, int]]] = {
    "zimage": [("zimage.ref_edit", "image.edit", 1024, 1024)],
    "flux": [("flux.img2img", "image.edit", 1024, 1024)],
    "qwen": [("qwen.edit", "image.edit", 1024, 1024)],
    "qwen2512": [("qwen.edit", "image.edit", 1024, 1024)],
}

REGION_EDIT_FAMILY_CAPS: dict[str, dict[str, Any]] = {
    "zimage": {"supportsInpaint": True, "supportsEditing": True, "label": "Native Inpaint"},
    "flux": {"supportsInpaint": False, "supportsEditing": True, "label": "Image Edit"},
    "nano-banana-fal": {"supportsInpaint": False, "supportsEditing": True, "label": "Image Edit"},
    "qwen2512": {"supportsInpaint": False, "supportsEditing": False, "label": "Unsupported"},
    "qwen": {"supportsInpaint": False, "supportsEditing": False, "label": "Unsupported"},
    "illustrious": {"supportsInpaint": False, "supportsEditing": False, "label": "Unsupported"},
}

# Add-only insert path (Fal instruction edit + existing region composite).
ADD_INSERT_FAMILY = "nano-banana-fal"
ADD_INSERT_FAL_MODEL = "fal-ai/nano-banana-2/edit"
ADD_INSERT_WORKFLOW = "fal:fal-ai/nano-banana-2/edit"
ADD_INSERT_DOCK = "nano-banana-2-fal"
ADD_INSERT_SIZE = (1280, 720)

INPAINT_WORKFLOW: dict[str, tuple[str, str]] = {
    "zimage": ("zimage.inpaint", "image.inpaint"),
}

GENERATE_WORKFLOW: dict[str, str] = {
    "zimage": "zimage.txt2img",
    "flux": "flux.txt2img",
    "qwen2512": "qwen2512.txt2img",
    "qwen": "qwen.txt2img",
    "illustrious": "illustrious.txt2img",
}


def normalize_family(family: str) -> str:
    key = (family or "").strip().lower()
    if key in {"qwen-image-2512", "qwen_image_2512", "qwen"}:
        return "qwen2512"
    if key in {"illustrious-xl", "illustrious_xl", "sdxl-illustrious", "sdxl_illustrious"}:
        return "illustrious"
    return key


def certified_visual_edit_path(family: str) -> dict[str, Any] | None:
    """Certified I2I/edit workflow. Draft stubs (qwen.edit, flux.edit) are not ready."""
    key = normalize_family(family)
    try:
        from ..image_runtime.certified_registry import get_workflow
    except Exception:
        return None
    for workflow_key, operation, width, height in VISUAL_EDIT_CANDIDATES.get(key, ()):
        wf = get_workflow(workflow_key)
        if wf is None:
            continue
        if str(getattr(wf, "status", "") or "") != "Certified":
            continue
        return {
            "family": key,
            "workflowKey": workflow_key,
            "operation": operation,
            "width": width,
            "height": height,
        }
    return None


def family_region_edit_capability(family: str) -> dict[str, Any]:
    key = normalize_family(family)
    caps = dict(REGION_EDIT_FAMILY_CAPS.get(key) or {})
    if not caps:
        caps = {"supportsInpaint": False, "supportsEditing": False, "label": "Unsupported"}
    path = certified_visual_edit_path(key)
    if path and not caps.get("supportsEditing") and not caps.get("supportsInpaint"):
        caps = {"supportsInpaint": False, "supportsEditing": True, "label": "Image Edit"}
    return {"family": key, **caps}


def generate_workflow_key(family: str) -> str | None:
    key = normalize_family(family)
    return GENERATE_WORKFLOW.get(key)


def inpaint_workflow(family: str) -> tuple[str, str] | None:
    key = normalize_family(family)
    return INPAINT_WORKFLOW.get(key)


def is_add_insert_family(family: str) -> bool:
    return normalize_family(family) == ADD_INSERT_FAMILY
