"""Character sheet prompt helpers for Qwen-Image-2512."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

CHARACTER_SHEET_ROLE_MAP: dict[str, str] = {
    "front": "full_body_front",
    "side_left": "full_body_side_left",
    "back": "full_body_back",
    "front_closeup": "closeup_front",
    "side_closeup": "closeup_side_left",
    "back_closeup": "closeup_back",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def compile_character_sheet_block(
    sheet_request: Mapping[str, Any] | None = None,
    references: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    sheet_request = sheet_request or {}
    references = references or []
    wants_sheet = bool(sheet_request.get("enabled") or sheet_request.get("views"))
    if str(sheet_request.get("layout") or "").strip().lower() == "four_view":
        return (
            "FOUR-VIEW CHARACTER SHEET (layout=four_view). "
            "Exactly four distinct views of the same character: "
            "full_body_front, full_body_side, full_body_back, head_shoulders_closeup. "
            "The supplied reference is identity preservation only and must not change layout. "
            "Do not generate a single standalone character image. Do not crop or omit any required view."
        )

    if not wants_sheet:
        return "Single approved image output; do not convert this into a multi-panel character sheet unless explicitly requested."

    from app.character_identity.four_view_sheet import (
        FOUR_VIEW_SHEET_PROMPT,
        REQUIRED_VIEWS,
    )

    requested_views = sheet_request.get("views") or list(CHARACTER_SHEET_ROLE_MAP)
    compiled_views: list[str] = []
    for view in requested_views:
        key = _text(view)
        if not key:
            continue
        compiled_views.append(f"{key}->{CHARACTER_SHEET_ROLE_MAP.get(key, key)}")
    required = list(sheet_request.get("requiredViews") or REQUIRED_VIEWS)

    reference_roles = [
        _text(item.get("reference_role"))
        for item in references
        if isinstance(item, Mapping) and _text(item.get("reference_role"))
    ]
    ref_text = ", ".join(reference_roles[:8]) if reference_roles else "identity_preservation only"
    layout = _text(sheet_request.get("layout")) or "four_view"
    return (
        f"{FOUR_VIEW_SHEET_PROMPT} "
        f"layout={layout}; requiredViews={','.join(required)}; "
        f"views: {', '.join(compiled_views)}; "
        f"referenceMode=identity_preservation; reference roles considered: {ref_text}."
    )
