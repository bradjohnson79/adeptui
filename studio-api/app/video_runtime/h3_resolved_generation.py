"""Helpers: one resolvedGeneration for MiniMax H3 Film Timeline / render_scene."""

from __future__ import annotations

from typing import Any


def stamp_resolved_generation(params: dict[str, Any], dims: dict[str, Any]) -> dict[str, Any]:
    """Write the single authoritative generation size onto job params."""
    width = int(dims["width"])
    height = int(dims["height"])
    resolved = {
        "productId": dims.get("productId") or "minimax-h3",
        "width": width,
        "height": height,
        "megapixels": dims.get("megapixels"),
        "source": dims.get("source"),
        "label": dims.get("label"),
        "aspect": dims.get("aspect") or "16:9",
        "projectCanvasIgnored": dims.get("projectCanvasIgnored"),
    }
    params["width"] = width
    params["height"] = height
    params["resolution"] = f"{width}x{height}"
    params["resolvedGeneration"] = resolved
    return resolved


def resolve_h3_job_dimensions(params: dict[str, Any], *, resolved_engine: str = "minimax-h3") -> dict[str, Any]:
    """Scene canvas is DISPLAY only. H3 generation size comes from the megapixel table.

    Never validate Scene WxH through the generic /32 gate. Resolve first, then
    assert_h3_legal_resolution on the table entry only.
    """
    from .legal_canvas import (
        assert_h3_legal_resolution,
        is_h3_legal_pixels,
        resolve_generation_dimensions,
    )

    existing = params.get("resolvedGeneration")
    if isinstance(existing, dict) and existing.get("width") and existing.get("height"):
        w, h = int(existing["width"]), int(existing["height"])
        assert_h3_legal_resolution(w, h)
        return stamp_resolved_generation(params, existing)

    width = int(params.get("width") or 0)
    height = int(params.get("height") or 0)
    scene_like = (width, height) if width > 0 and height > 0 else None

    if width > 0 and height > 0 and is_h3_legal_pixels(width, height):
        return stamp_resolved_generation(
            params,
            {
                "productId": "minimax-h3",
                "width": width,
                "height": height,
                "megapixels": None,
                "label": f"{width}x{height}",
                "aspect": "16:9",
                "source": "job_params",
                "projectCanvasIgnored": None,
            },
        )

    res = str(params.get("resolution") or "").strip()
    requested_quality: str | float | None = None
    if res and "x" in res.lower():
        try:
            w_s, h_s = res.lower().split("x", 1)
            rw, rh = int(w_s), int(h_s)
        except ValueError:
            rw, rh = 0, 0
        if rw > 0 and rh > 0 and is_h3_legal_pixels(rw, rh):
            requested_quality = res
        # Illegal WxH (e.g. Scene 1920x824) is ignored — auto H3 policy applies.
    elif res:
        requested_quality = res

    dims = resolve_generation_dimensions(
        model=str(params.get("generatorId") or params.get("adapterId") or resolved_engine or "minimax-h3"),
        requested_quality=requested_quality,
        draft_mode=bool(params.get("draftMode") or params.get("fast_generation")),
        project_canvas=scene_like,
    )
    assert_h3_legal_resolution(int(dims["width"]), int(dims["height"]))
    if scene_like and scene_like != (int(dims["width"]), int(dims["height"])):
        dims = {**dims, "projectCanvasIgnored": list(scene_like)}
    return stamp_resolved_generation(params, dims)
