"""Scene Creator candidate routing — User Control Law + hosted honesty."""

from __future__ import annotations

import logging
import random
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

CandidatePlan = dict[str, Any]

# Frozen Scene Creator region-edit capability. Do not infer from txt2img
# roster or edit_compile's silent Z-Image fallback.
REGION_EDIT_UNSUPPORTED_MESSAGE = (
    "This generator cannot edit a region. Choose Z-Image for Native Inpaint."
)
VISUAL_INHERITANCE_BLOCKED_MESSAGE = (
    "This generator cannot keep the painted correction. Choose Z-Image or FLUX for Final Quality Render."
)

# Strategy A I2I paths. qwen.edit is omitted until Certified (it is Draft/stub).
_VISUAL_EDIT_CANDIDATES: dict[str, list[tuple[str, str, int, int]]] = {
    "zimage": [("zimage.ref_edit", "image.edit", 1024, 1024)],
    "flux": [("flux.img2img", "image.edit", 1024, 1024)],
    "qwen": [("qwen.edit", "image.edit", 1024, 1024)],
    "qwen2512": [("qwen.edit", "image.edit", 1024, 1024)],
}

_REGION_EDIT_FAMILY_CAPS: dict[str, dict[str, Any]] = {
    "zimage": {"supportsInpaint": True, "supportsEditing": True, "label": "Native Inpaint"},
    "flux": {"supportsInpaint": False, "supportsEditing": True, "label": "Image Edit"},
    "qwen2512": {"supportsInpaint": False, "supportsEditing": False, "label": "Unsupported"},
    "qwen": {"supportsInpaint": False, "supportsEditing": False, "label": "Unsupported"},
    "illustrious": {"supportsInpaint": False, "supportsEditing": False, "label": "Unsupported"},
}


def _normalize_region_edit_family(family: str) -> str:
    key = (family or "").strip().lower()
    if key in {"qwen-image-2512", "qwen_image_2512", "qwen"}:
        return "qwen2512"
    if key in {"illustrious-xl", "illustrious_xl", "sdxl-illustrious", "sdxl_illustrious"}:
        return "illustrious"
    return key


def certified_visual_edit_path(family: str) -> dict[str, Any] | None:
    """Certified I2I/edit workflow that can consume an approved edited preview.

    Returns None when the family has no Certified visual-conditioning path.
    Draft stubs (including qwen.edit) are not treated as ready.
    """
    key = _normalize_region_edit_family(family)
    try:
        from ..image_runtime.certified_registry import get_workflow
    except Exception:
        return None
    for workflow_key, operation, width, height in _VISUAL_EDIT_CANDIDATES.get(key, ()):
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
    """Honest Native Inpaint | Image Edit | Unsupported for a local family."""
    key = _normalize_region_edit_family(family)
    caps = dict(_REGION_EDIT_FAMILY_CAPS.get(key) or {})
    if not caps:
        caps = {"supportsInpaint": False, "supportsEditing": False, "label": "Unsupported"}
    path = certified_visual_edit_path(key)
    if path and not caps.get("supportsEditing") and not caps.get("supportsInpaint"):
        caps = {"supportsInpaint": False, "supportsEditing": True, "label": "Image Edit"}
    return {"family": key, **caps}


def hosted_image_generation_available() -> bool:
    """True only when a Certified, executable, non-local image workflow exists.

    Hosted image inventory is currently Blocked (imagen.*) and flux-kie maps
    to local flux. Do not pretend API generation is operational.
    """
    try:
        from ..image_runtime.certified_registry import list_workflows
    except Exception:
        return False
    for wf in list_workflows():
        kind = str(getattr(wf, "provider_kind", "") or "local").lower()
        if kind in {"local", "", "comfy", "comfyui"}:
            continue
        if getattr(wf, "status", "") != "Certified":
            continue
        ops = set(getattr(wf, "supported_operations", None) or ())
        op = getattr(wf, "operation", "") or ""
        if op in {"image.generate", "txt2img"} or "txt2img" in ops or "image.generate" in ops:
            return True
    return False


def list_local_generator_families(*, has_reference: bool = False) -> list[dict[str, Any]]:
    from ..imagegen_workflows import build_local_generator_models

    models = build_local_generator_models()
    out: list[dict[str, Any]] = []
    for model in models:
        if model.get("group") == "auto":
            continue
        executable = bool(model.get("executable"))
        if has_reference and not model.get("supportsReferences") and model.get("id") == "illustrious":
            executable = False
        family_id = str(model.get("id") or "")
        region_caps = family_region_edit_capability(family_id)
        out.append(
            {
                "id": family_id,
                "label": model.get("label"),
                "family": family_id,
                "executable": executable,
                "status": model.get("status"),
                "supportsReferences": bool(model.get("supportsReferences")),
                "supportsEditing": bool(region_caps.get("supportsEditing")),
                "supportsInpaint": bool(region_caps.get("supportsInpaint")),
                "regionEditLabel": region_caps.get("label") or "Unsupported",
                "providerKind": "local",
            }
        )
    return out


def build_candidate_plans(
    *,
    local_enabled: bool,
    api_enabled: bool,
    local_family: str = "",
    api_model: str = "",
    has_reference: bool = False,
    candidate_count: int = 4,
    seed: int | None = None,
) -> list[CandidatePlan]:
    """Build up to ``candidate_count`` plans. Unchecked source = zero jobs.

    API ON without a real hosted path raises — never routes API through Comfy.
    """
    count = max(1, min(int(candidate_count or 4), 4))
    if not local_enabled and not api_enabled:
        raise ValueError("Enable a Local or Cloud generator to create scene shots.")

    api_ok = hosted_image_generation_available() or bool((api_model or "").strip())
    if api_enabled and not api_ok:
        raise ValueError("API Generation — Not Available")

    local_families = [
        m for m in list_local_generator_families(has_reference=has_reference) if m.get("executable")
    ]
    if has_reference:
        local_families = [m for m in local_families if m.get("supportsReferences") or m.get("id") != "illustrious"]

    selected_local = (local_family or "").strip()
    if selected_local and local_enabled:
        preferred = [m for m in local_families if m.get("id") == selected_local]
        rest = [m for m in local_families if m.get("id") != selected_local]
        local_families = preferred + rest

    sources: list[CandidatePlan] = []
    if local_enabled:
        if not local_families:
            raise ValueError("No local image generator is ready. Open Source Manager to install a Certified generator.")
        for fam in local_families:
            sources.append(
                {
                    "source": "local",
                    "family": fam["id"],
                    "model": fam["id"],
                    "label": fam.get("label") or fam["id"],
                }
            )
    if api_enabled and api_ok:
        sources.append(
            {
                "source": "api",
                "family": "hosted",
                "model": (api_model or "").strip() or "hosted",
                "label": (api_model or "").strip() or "Cloud generator",
            }
        )

    if not sources:
        raise ValueError("Enable a Local or Cloud generator to create scene shots.")

    rng = random.Random(seed if seed is not None else random.randint(1, 2_147_483_647))
    plans: list[CandidatePlan] = []
    distinct = sources
    for i in range(count):
        src = distinct[i % len(distinct)]
        plans.append(
            {
                **src,
                "index": i,
                "seed": rng.randint(1, 2_147_483_647),
                "provenance_label": (
                    f"LOCAL — {src['label']}" if src["source"] == "local" else f"API — {src['label']}"
                ),
            }
        )
    return plans
