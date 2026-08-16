"""Resolution from certified registry fingerprints — not Scene constants."""

from __future__ import annotations

from typing import Any

from .capability import certified_visual_edit_path, generate_workflow_key, inpaint_workflow, normalize_family

_PREVIEW_SIZE = (512, 288)
_DEFAULT = (1024, 1024)


def _registry_size(workflow_key: str) -> tuple[int, int] | None:
    try:
        from ..image_runtime.certified_registry import get_workflow
    except Exception:
        return None
    wf = get_workflow(workflow_key)
    if wf is None:
        return None
    fps = dict(getattr(wf, "fingerprints", None) or {})
    live = str(fps.get("liveTestResolution") or "").lower().replace(" ", "")
    if "x" in live:
        parts = live.split("x", 1)
        try:
            return max(64, int(parts[0])), max(64, int(parts[1]))
        except ValueError:
            return None
    width = getattr(wf, "width", None) or (getattr(wf, "output_contract", None) or {}).get("width")
    height = getattr(wf, "height", None) or (getattr(wf, "output_contract", None) or {}).get("height")
    if width and height:
        try:
            return int(width), int(height)
        except (TypeError, ValueError):
            return None
    return None


def resolve_resolution(
    model: str,
    operation: str,
    purpose: str,
    *,
    workflow_key: str = "",
    aspect_ratio: str | None = None,
) -> tuple[int, int]:
    purpose_n = (purpose or "").strip().lower()
    if purpose_n in {"scene_shot_preview"}:
        from ..aspect_fps import production_pixels

        return production_pixels(aspect_ratio, "draft")
    if purpose_n in {"scene_shot_final"}:
        from ..aspect_fps import production_pixels

        return production_pixels(aspect_ratio, "final")
    if workflow_key:
        sized = _registry_size(workflow_key)
        if sized:
            return sized
    op = (operation or "").strip().lower()
    family = normalize_family(model)
    if op in {"image.inpaint", "image.object_remove", "image.object_replace", "native_inpaint"}:
        pair = inpaint_workflow(family)
        if pair:
            sized = _registry_size(pair[0])
            if sized:
                return sized
        path = certified_visual_edit_path(family)
        if path:
            return int(path["width"]), int(path["height"])
        return _DEFAULT
    if op in {"image.edit", "image.reference", "reference_edit"}:
        path = certified_visual_edit_path(family)
        if path:
            return int(path["width"]), int(path["height"])
        return _DEFAULT
    key = workflow_key or generate_workflow_key(family) or ""
    sized = _registry_size(key) if key else None
    if sized:
        return sized
    return _DEFAULT
