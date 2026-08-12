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

    if not wants_sheet:
        return "Single approved image output; do not convert this into a multi-panel character sheet unless explicitly requested."

    requested_views = sheet_request.get("views") or list(CHARACTER_SHEET_ROLE_MAP)
    compiled_views: list[str] = []
    for view in requested_views:
        key = _text(view)
        if not key:
            continue
        compiled_views.append(f"{key}->{CHARACTER_SHEET_ROLE_MAP.get(key, key)}")

    reference_roles = [
        _text(item.get("reference_role"))
        for item in references
        if isinstance(item, Mapping) and _text(item.get("reference_role"))
    ]
    ref_text = ", ".join(reference_roles[:8]) if reference_roles else "no attached reference roles"
    return (
        "Character sheet mode with stable view naming; "
        f"views: {', '.join(compiled_views)}; "
        f"reference roles considered: {ref_text}."
    )
