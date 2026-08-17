"""Prompt intelligence — expand with camera/lighting/composition; user may accept/edit."""

from __future__ import annotations

from typing import Any


def expand_prompt(
    prompt: str,
    *,
    purpose: str = "",
    style_hints: dict[str, Any] | None = None,
    continuity_constraints: list[str] | None = None,
    cinematography: dict[str, Any] | None = None,
    lighting: dict[str, Any] | None = None,
    spatial_hints: list[str] | None = None,
    visual_language: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = (prompt or "").strip()
    parts: list[str] = [base] if base else []
    style_hints = style_hints or {}
    cinematography = cinematography or {}
    lighting = lighting or {}
    visual_language = visual_language or {}

    cam = cinematography.get("camera") or cinematography.get("lens") or style_hints.get("camera")
    if cam:
        parts.append(f"Camera: {cam}")
    light = lighting.get("mood") or lighting.get("setup") or style_hints.get("lighting")
    if light:
        parts.append(f"Lighting: {light}")
    comp = cinematography.get("composition") or style_hints.get("composition")
    if comp:
        parts.append(f"Composition: {comp}")
    art = style_hints.get("artDirection") or style_hints.get("style")
    if art:
        parts.append(f"Art direction: {art}")
    color_clause = ""
    try:
        from ..image_studio.color_grades import color_grade_prompt_clause

        color_clause = color_grade_prompt_clause(
            visual_language.get("colorGradePreset") or style_hints.get("colorGradePreset"),
            visual_language.get("colorTreatment") or style_hints.get("colorTreatment"),
        )
    except Exception:
        color_clause = ""
    if color_clause:
        parts.append(color_clause)
    if purpose:
        parts.append(f"Purpose: {purpose.replace('_', ' ')}")
    for c in continuity_constraints or []:
        if c:
            parts.append(f"Continuity: {c}")
    for hint in spatial_hints or []:
        if hint:
            parts.append(f"Spatial: {hint}")

    expanded = ". ".join(p for p in parts if p).strip()
    if not expanded.endswith("."):
        expanded = expanded + "." if expanded else base
    return {
        "originalPrompt": base,
        "expandedPrompt": expanded,
        "acceptedPrompt": expanded,  # caller may overwrite with user edit
        "improvements": [
            k
            for k, v in {
                "camera": bool(cam),
                "lighting": bool(light),
                "composition": bool(comp),
                "artDirection": bool(art),
                "colorGrade": bool(color_clause),
                "continuity": bool(continuity_constraints),
                "spatial": bool(spatial_hints),
            }.items()
            if v
        ],
    }
