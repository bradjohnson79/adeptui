"""Compatibility validation for creative items and provider mappings."""

from __future__ import annotations

from typing import Any

from .kinds import CREATIVE_KINDS
from .schema import CreativeItem


def validate_creative_item_shape(item: CreativeItem | dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    data = item.to_dict() if isinstance(item, CreativeItem) else item
    kind = str(data.get("kind") or "")
    if kind not in CREATIVE_KINDS:
        gaps.append(f"unsupported_kind:{kind or 'missing'}")
    if not str(data.get("name") or "").strip():
        gaps.append("missing_name")
    if not str(data.get("slug") or "").strip():
        gaps.append("missing_slug")
    intent = data.get("intent")
    if not isinstance(intent, dict):
        gaps.append("intent_must_be_object")
    if "providerMappings" in data:
        mappings = data.get("providerMappings")
    elif "provider_mappings" in data:
        mappings = data.get("provider_mappings")
    else:
        mappings = None
    if mappings is None:
        gaps.append("provider_mappings_missing")
    elif not isinstance(mappings, dict):
        gaps.append("provider_mappings_must_be_object")
    return gaps


def validate_provider_mappings(
    provider_mappings: dict[str, Any] | None,
    *,
    available_providers: list[str] | None = None,
) -> dict[str, Any]:
    mappings = provider_mappings if isinstance(provider_mappings, dict) else {}
    available = set(available_providers or ["ltx", "wan", "blender"])
    known = set(mappings.keys())
    missing = sorted(available - known)
    unknown = sorted(known - available)
    return {
        "ok": True,
        "mappedProviders": sorted(known),
        "missingMappings": missing,
        "unknownProviders": unknown,
        "portable": True,  # intent is always portable; mappings may be incomplete
        "notes": (
            ["Intent is portable; incomplete providerMappings are allowed in M3.1a stubs."]
            if missing
            else []
        ),
    }


def compatibility_report(item: CreativeItem | dict[str, Any]) -> dict[str, Any]:
    shape_gaps = validate_creative_item_shape(item)
    data = item.to_dict() if isinstance(item, CreativeItem) else item
    mapping_report = validate_provider_mappings(
        data.get("providerMappings") or data.get("provider_mappings") or {}
    )
    return {
        "ok": not shape_gaps,
        "shapeGaps": shape_gaps,
        "providerMappings": mapping_report,
        "needsClarification": bool(shape_gaps),
    }
