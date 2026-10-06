"""Display pointer selection for Environment Reference Sheets.

Leftover restitch collages (`restitchCompositeAssetId`) are forensic history.
Full Size / Library / display must prefer the live full-sheet visual
(`visualSheetAssetId` / `ers_composite_asset_id`) when one exists.
"""

from __future__ import annotations

from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            data = dump()
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def _sheet_details(sheet: Any) -> dict[str, Any]:
    if sheet is None:
        return {}
    provenance = sheet.get("provenance") if isinstance(sheet, dict) else getattr(sheet, "provenance", None)
    if isinstance(provenance, dict):
        details = provenance.get("details")
    else:
        details = getattr(provenance, "details", None) if provenance is not None else None
    return _as_dict(details)


def _package_meta(package: Any) -> dict[str, Any]:
    if package is None:
        return {}
    if isinstance(package, dict):
        return _as_dict(package.get("metadata"))
    return _as_dict(getattr(package, "metadata", None))


def _attr(obj: Any, name: str) -> str:
    if obj is None:
        return ""
    if isinstance(obj, dict):
        return str(obj.get(name) or "").strip()
    return str(getattr(obj, name, "") or "").strip()


def _first(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def restitch_composite_asset_id(*, sheet: Any = None, package: Any = None) -> str:
    details = _sheet_details(sheet)
    meta = _package_meta(package)
    return _first(details.get("restitchCompositeAssetId"), meta.get("restitchCompositeAssetId"))


def select_ers_display_asset_id(
    *,
    sheet: Any = None,
    package: Any = None,
    claimed_asset_id: str = "",
    resolved_composite_asset_id: str = "",
) -> str:
    """Return the asset id Full Size / Library / display should open.

    Never selects `restitchCompositeAssetId` when a newer full-sheet visual
    exists. The leftover restitch id is kept as forensic history only.
    """
    details = _sheet_details(sheet)
    meta = _package_meta(package)
    restitch = _first(
        details.get("restitchCompositeAssetId"),
        meta.get("restitchCompositeAssetId"),
    )
    visuals = [
        _first(details.get("visualSheetAssetId")),
        _first(_attr(sheet, "ers_composite_asset_id")),
        _first(_attr(package, "ers_composite_asset_id")),
        _first(resolved_composite_asset_id),
        _first(meta.get("visualSheetAssetId")),
        _first(meta.get("collageAssetId")),
    ]
    for visual in visuals:
        if visual and visual != restitch:
            return visual
    claimed = _first(claimed_asset_id)
    if claimed and claimed != restitch:
        return claimed
    for visual in visuals:
        if visual:
            return visual
    return claimed or restitch
