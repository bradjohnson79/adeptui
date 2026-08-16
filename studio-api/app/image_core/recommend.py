"""Operation recommendations. Recommended ≠ routed. Never silent-swap models."""

from __future__ import annotations

from typing import Any

from .capability import family_region_edit_capability, normalize_family

# Product recommendation registry — UI only.
_RECOMMENDED_FAMILY: dict[str, str] = {
    "remove": "flux",
    "add": "flux",
    "modify": "flux",
    "replace": "flux",
}

_RECOMMENDED_LABEL: dict[str, str] = {
    "zimage": "Z-Image",
    "flux": "FLUX",
}


def recommend(operation: str, family: str) -> dict[str, Any]:
    op = (operation or "").strip().lower()
    current = normalize_family(family)
    recommended = _RECOMMENDED_FAMILY.get(op, "")
    caps = family_region_edit_capability(current)
    supported = bool(caps.get("supportsInpaint") or caps.get("supportsEditing"))
    rec_caps = family_region_edit_capability(recommended) if recommended else {}
    rec_supported = bool(rec_caps.get("supportsInpaint") or rec_caps.get("supportsEditing"))
    same = bool(recommended) and recommended == current
    message = ""
    if recommended and not same and rec_supported:
        label = _RECOMMENDED_LABEL.get(recommended, recommended)
        op_label = op.capitalize() if op else "this edit"
        message = f"{label} is recommended for {op_label}"
    return {
        "operation": op,
        "family": current,
        "recommendedFamily": recommended,
        "recommended": same or not recommended,
        "supported": supported,
        "message": message,
        "keepCurrentAllowed": True,
    }
