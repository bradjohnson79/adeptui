"""Resolve creator-facing ERS sheetId to an EnvironmentReferencePackage.

Binding: Scene Creator UI never requires package UUIDs.
Never regenerate ERS because package lookup failed.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ..spatial_map.ers_contracts import DirectionLabel, EnvironmentReferencePackage

logger = logging.getLogger(__name__)

_DIRECTIONS: tuple[DirectionLabel, ...] = ("north", "east", "south", "west")


class ErsResolveError(ValueError):
    """Creator-facing ERS resolution failure."""


def resolve_ers_for_sheet(
    db: Session,
    project_id: str,
    sheet_id: str,
    *,
    persist_runtime: bool = True,
) -> tuple[EnvironmentReferencePackage, bool]:
    """Resolve ``sheetId`` → existing package or a non-destructive runtime package.

    Returns ``(package, runtime)`` where ``runtime`` is True when no persisted
    generation package existed and a read-only package was constructed from the
    canonical sheet + Spatial Map. Never enqueues ERS view jobs.
    """
    sheet_id = (sheet_id or "").strip()
    if not sheet_id:
        raise ErsResolveError("Select an Environment Reference Sheet first.")

    from ..environment_reference_sheet.store import load_sheet

    sheet = load_sheet(project_id, sheet_id)
    if sheet is None:
        raise ErsResolveError("Environment Reference Sheet not found in this project.")

    existing = _find_existing_package(db, project_id, sheet)
    if existing is not None:
        hydrated = _hydrate_directional_assets(existing, sheet)
        cameras = _spatial_cameras(db, project_id, sheet)
        if cameras:
            hydrated.metadata = dict(hydrated.metadata or {})
            hydrated.metadata.setdefault("cameras", cameras)
            hydrated.metadata["sheet_id"] = sheet.sheetId
        return hydrated, False

    runtime = _build_runtime_package(db, project_id, sheet)
    if persist_runtime:
        from ..spatial_map.ers_persistence import save_ers_package

        save_ers_package(db, project_id, runtime, provenance="scene_creator_runtime")
    return runtime, True


def _find_existing_package(db: Session, project_id: str, sheet: Any) -> EnvironmentReferencePackage | None:
    from ..spatial_map.ers_persistence import list_ers_packages

    packages = list_ers_packages(db, project_id)
    map_id = ""
    if getattr(sheet, "spatialMap", None) is not None:
        map_id = str(sheet.spatialMap.mapId or "")

    by_sheet = [
        p
        for p in packages
        if str((p.metadata or {}).get("sheet_id") or "") == sheet.sheetId
        and not str(p.id).startswith("runtime-")
    ]
    if by_sheet:
        return sorted(by_sheet, key=lambda p: p.updated_at or p.created_at or "", reverse=True)[0]

    if map_id:
        by_layout = [
            p
            for p in packages
            if p.scene_layout_id == map_id and not str(p.id).startswith("runtime-")
        ]
        if by_layout:
            return sorted(by_layout, key=lambda p: p.updated_at or p.created_at or "", reverse=True)[0]

    runtime_id = f"runtime-{sheet.sheetId}"
    for p in packages:
        if p.id == runtime_id:
            return p
    return None


def _hydrate_directional_assets(
    package: EnvironmentReferencePackage,
    sheet: Any,
) -> EnvironmentReferencePackage:
    """Fill empty directional slots from the canonical sheet. Never regenerates."""
    filled = dict(package.directional_assets or {})
    changed = False
    for view in getattr(sheet, "directionalViews", None) or []:
        direction = getattr(view, "direction", None)
        asset_id = getattr(view, "approvedAssetId", None)
        if direction in _DIRECTIONS and asset_id and not filled.get(direction):
            filled[direction] = asset_id
            changed = True
    composite = getattr(getattr(sheet, "composition", None), "renderedAssetIds", None) or {}
    composite_id = None
    if isinstance(composite, dict):
        composite_id = composite.get("png") or composite.get("sheet") or composite.get("composite")
    if changed or (composite_id and not package.ers_composite_asset_id):
        return package.model_copy(
            update={
                "directional_assets": filled,
                "ers_composite_asset_id": package.ers_composite_asset_id or composite_id,
                "metadata": {**(package.metadata or {}), "sheet_id": sheet.sheetId},
            }
        )
    return package


def _spatial_cameras(db: Session, project_id: str, sheet: Any) -> list[dict[str, Any]]:
    map_id = ""
    if getattr(sheet, "spatialMap", None) is not None:
        map_id = str(sheet.spatialMap.mapId or "")
    if not map_id:
        return []
    try:
        from ..spatial_map.service import get_document

        document = get_document(db, project_id, map_id)
    except Exception:
        return []
    cameras: list[dict[str, Any]] = []
    for index, camera in enumerate(getattr(document, "cameras", None) or []):
        slot = getattr(camera, "cameraSlot", None)
        if slot is None or slot < 0:
            slot = index
        cameras.append(
            {
                "id": camera.id,
                "label": camera.label or f"C{slot + 1}",
                "cameraSlot": int(slot),
                "orientation": getattr(camera, "orientation", "") or "",
                "fovPreset": getattr(camera, "fovPreset", "") or "",
                "yawDegrees": getattr(camera, "yawDegrees", None),
                "lensMm": getattr(camera, "lensMm", None),
                "hero": bool(getattr(camera, "hero", False)),
            }
        )
    return cameras


def _build_runtime_package(db: Session, project_id: str, sheet: Any) -> EnvironmentReferencePackage:
    """Construct a read-only package from sheet + Spatial Map. No generation."""
    map_id = ""
    if getattr(sheet, "spatialMap", None) is not None:
        map_id = str(sheet.spatialMap.mapId or "")

    placements: list[dict[str, Any]] = []
    atlas_asset_id = None
    master_env = None
    if map_id:
        try:
            from ..spatial_map.service import get_document

            document = get_document(db, project_id, map_id)
            placements = [
                placement.model_dump() for placement in (document.characters or [])
            ] + [placement.model_dump() for placement in (document.props or [])]
            atlas_asset_id = getattr(document, "backgroundAssetId", None)
        except Exception as exc:
            logger.info("Runtime ERS package: spatial map %s unread (%s)", map_id, exc)

    directional: dict[DirectionLabel, str | None] = {d: None for d in _DIRECTIONS}
    for view in getattr(sheet, "directionalViews", None) or []:
        direction = getattr(view, "direction", None)
        asset_id = getattr(view, "approvedAssetId", None)
        if direction in _DIRECTIONS and asset_id:
            directional[direction] = asset_id

    profile = getattr(sheet, "profile", None)
    style_context: dict[str, Any] = {
        "visual_style": "",
        "materials": list(getattr(profile, "materials", None) or []),
        "lighting": list(getattr(profile, "lightingNotes", None) or []),
        "atmosphere": list(getattr(profile, "atmosphere", None) or []),
        "time_of_day": getattr(profile, "timeOfDay", "") or "",
        "color_palette": list(getattr(profile, "colorPalette", None) or []),
        "environment_name": getattr(profile, "environmentName", "") or sheet.name,
    }
    continuity = getattr(sheet, "continuity", None)
    composition = getattr(sheet, "composition", None)
    rendered = getattr(composition, "renderedAssetIds", None) or {}
    composite_id = None
    if isinstance(rendered, dict):
        composite_id = rendered.get("png") or rendered.get("sheet") or rendered.get("composite")

    return EnvironmentReferencePackage(
        id=f"runtime-{sheet.sheetId}",
        project_id=project_id,
        scene_layout_id=map_id or sheet.sheetId,
        atlas_asset_id=atlas_asset_id,
        master_environment_asset_id=master_env,
        placements=placements,
        style_context=style_context,
        orientation="atlas-north-up",
        directional_assets=directional,
        ers_composite_asset_id=composite_id,
        metadata={
            "sheet_id": sheet.sheetId,
            "runtime": True,
            "cameras": _spatial_cameras(db, project_id, sheet),
            "continuity_summary": getattr(continuity, "summary", "") or "",
            "provenance": "scene_creator_runtime",
        },
    )
