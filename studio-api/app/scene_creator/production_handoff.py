"""Pointer-only Scene Spatial Profile / production handoff.

One object: the creator-facing Spatial Profile IS the scene_production_handoff
trait. Pointers to canonical ERS, Spatial Map, cameras, characters, props, and
shots — never a duplicated snapshot blob.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import Asset

HANDOFF_CATEGORY = "scene_production_handoff"
SELECTION_CATEGORY = "scene_spatial_profile_selection"
SELECTION_KEY = "selected"


class SceneCreatorHandoffError(ValueError):
    """Creator-correctable Continue / profile failure."""


class SpatialProfilePointers(BaseModel):
    handoffId: str = ""
    name: str = ""
    displayName: str = ""
    revision: int = 1
    updatedAt: str = ""
    projectId: str = ""
    sceneId: str = ""
    sheetId: str = ""
    spatialMapId: str = ""
    # Version of the Spatial Map document consumed at handoff time.
    mapVersion: str = ""
    ersPackageId: str = ""
    ersLibraryAssetId: str = ""
    aspectRatio: str = "16:9"
    characterIds: list[str] = Field(default_factory=list)
    propIds: list[str] = Field(default_factory=list)
    shotIds: list[str] = Field(default_factory=list)
    cameras: list[dict[str, str]] = Field(default_factory=list)
    fingerprint: str = ""


class ProfileSelection(BaseModel):
    selectedProfileId: str | None = None
    workspaceReset: bool = False
    updatedAt: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s or "scene"


def _display_name(slug: str) -> str:
    parts = [p for p in (slug or "").split("-") if p]
    return " ".join(p[:1].upper() + p[1:] for p in parts) or "Spatial Profile"


def stable_handoff_id(project_id: str, spatial_map_id: str, scene_id: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"adept.spatial-profile:{project_id}:{spatial_map_id}:{scene_id}",
        )
    )


def pointer_fingerprint(profile: SpatialProfilePointers) -> str:
    payload = {
        "sceneId": profile.sceneId,
        "sheetId": profile.sheetId,
        "spatialMapId": profile.spatialMapId,
        "mapVersion": profile.mapVersion,
        "ersPackageId": profile.ersPackageId,
        "ersLibraryAssetId": profile.ersLibraryAssetId,
        "aspectRatio": profile.aspectRatio,
        "characterIds": sorted(profile.characterIds),
        "propIds": sorted(profile.propIds),
        "shotIds": sorted(profile.shotIds),
        "cameras": sorted(
            [
                {"cameraId": str(c.get("cameraId") or ""), "cameraStateHash": str(c.get("cameraStateHash") or "")}
                for c in profile.cameras
                if isinstance(c, dict)
            ],
            key=lambda row: row["cameraId"],
        ),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _load_json_trait(db: Session, *, project_id: str, category: str, key: str) -> dict[str, Any] | None:
    from ..spatial_map.ers_persistence import _load_trait_value

    raw = _load_trait_value(db, project_id=project_id, category=category, key=key)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def load_profile(db: Session, project_id: str, handoff_id: str) -> SpatialProfilePointers | None:
    data = _load_json_trait(db, project_id=project_id, category=HANDOFF_CATEGORY, key=handoff_id)
    if not data:
        return None
    try:
        return SpatialProfilePointers.model_validate(data)
    except Exception:
        return None


def list_profiles(db: Session, project_id: str) -> list[SpatialProfilePointers]:
    from ..spatial_map.ers_persistence import _list_trait_values

    out: list[SpatialProfilePointers] = []
    for raw in _list_trait_values(db, project_id=project_id, category=HANDOFF_CATEGORY):
        try:
            item = SpatialProfilePointers.model_validate_json(raw)
        except Exception:
            continue
        if item.projectId == project_id:
            out.append(item)
    out.sort(key=lambda p: p.updatedAt or "", reverse=True)
    return out


def load_selection(db: Session, project_id: str) -> ProfileSelection:
    data = _load_json_trait(db, project_id=project_id, category=SELECTION_CATEGORY, key=SELECTION_KEY)
    if not data:
        return ProfileSelection()
    try:
        return ProfileSelection.model_validate(data)
    except Exception:
        return ProfileSelection()


def save_selection(db: Session, project_id: str, selection: ProfileSelection) -> ProfileSelection:
    from ..spatial_map.ers_persistence import _upsert_trait

    selection.updatedAt = _now()
    _upsert_trait(
        db,
        project_id=project_id,
        category=SELECTION_CATEGORY,
        key=SELECTION_KEY,
        value=selection.model_dump_json(),
        provenance="scene_creator",
    )
    return selection


def save_profile(db: Session, project_id: str, profile: SpatialProfilePointers) -> SpatialProfilePointers:
    from ..spatial_map.ers_persistence import _upsert_trait

    profile.projectId = project_id
    profile.updatedAt = _now()
    profile.fingerprint = pointer_fingerprint(profile)
    _upsert_trait(
        db,
        project_id=project_id,
        category=HANDOFF_CATEGORY,
        key=profile.handoffId,
        value=profile.model_dump_json(),
        provenance="scene_creator",
    )
    return profile


def _pick_sheet(
    project_id: str, *, scene_id: str = "", sheet_id: str = "", map_id: str = ""
) -> Any:
    from ..environment_reference_sheet.store import list_sheets, load_sheet

    wanted = (sheet_id or "").strip()
    if wanted:
        sheet = load_sheet(project_id, wanted)
        if sheet is None:
            raise SceneCreatorHandoffError("Environment Reference Sheet not found in this project.")
        return sheet
    sheets = list_sheets(project_id)
    if not sheets:
        raise SceneCreatorHandoffError(
            "Scene Creator needs an Environment Reference Sheet. Create one in Spatial Map first."
        )
    # CDX-037: prefer the sheet bound to the ACTIVE spatial map. The map is the
    # canonical spatial truth; a sceneId match or the newest-with-composite
    # fallback can otherwise pick a sibling sheet from a different map that
    # happens to be newer or share the scene id.
    wanted_map = (map_id or "").strip()
    if wanted_map:
        for sheet in sheets:
            spatial = getattr(sheet, "spatialMap", None)
            if spatial is not None and str(getattr(spatial, "mapId", "") or "") == wanted_map:
                return sheet
    if scene_id:
        for sheet in sheets:
            if str(getattr(sheet, "sceneId", "") or "") == scene_id:
                return sheet
    with_composite = [
        s
        for s in sheets
        if str(getattr(s, "ers_composite_asset_id", "") or "").strip()
        or getattr(s, "status", "") in {"complete", "registered", "approved"}
    ]
    return with_composite[0] if with_composite else sheets[0]


def _character_ids_from_map(document: Any) -> list[str]:
    ids: list[str] = []
    for row in list(getattr(document, "characters", None) or []):
        cid = str(getattr(row, "characterId", "") or "")
        if cid and cid not in ids:
            ids.append(cid)
    return ids


def _prop_ids_from_map(db: Session, project_id: str, document: Any) -> list[str]:
    """CDX-015: apply the same approved-entity rule as _placed_project_prop_ids.

    Draft/deleted PropEntities must never be written into shot.prop_entity_ids.
    Only placements whose propId resolves to a project-owned PropEntity with an
    approved_asset_id propagate to the shot/profiles.
    """
    from ..spatial_map.ers_persistence import load_prop_entity_by_id

    ids: list[str] = []
    for row in list(getattr(document, "props", None) or []):
        pid = str(getattr(row, "propId", "") or getattr(row, "prop_id", "") or "").strip()
        if not pid or pid in ids:
            continue
        entity = load_prop_entity_by_id(db, project_id, pid)
        if entity is None:
            continue
        approved_asset_id = (entity.approved_asset_id or "").strip()
        if not approved_asset_id:
            continue
        # CDX-015 hardening: the approved asset row must still exist. A prop
        # whose approved asset was deleted (stale/deleted prop ID) is not
        # production-truth and must not propagate a dangling reference.
        if db.get(Asset, approved_asset_id) is None:
            continue
        ids.append(entity.id)
    return ids


def _camera_pointers(pack: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for rec in list(getattr(pack, "cameras", None) or []):
        cam_id = str(getattr(rec, "cameraId", "") or "")
        if not cam_id:
            continue
        out.append(
            {
                "cameraId": cam_id,
                "cameraStateHash": str(getattr(rec, "cameraStateHash", "") or ""),
            }
        )
    return out


def _unique_name(existing: list[SpatialProfilePointers], title: str) -> str:
    taken = {p.name for p in existing}
    base = f"{_slugify(title)}-spatial"
    n = 1
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def synchronize_production_handoff(
    db: Session,
    project_id: str,
    *,
    scene_id: str = "",
    sheet_id: str = "",
    spatial_map_id: str = "",
) -> dict[str, Any]:
    """Sync canonical upstream intelligence onto the existing Scene Creator scene.

    Does not create projects, duplicate ERS, rewrite Timeline, or create shots
    when the scene already has shots.
    """
    from ..aspect_fps import normalize_production_aspect
    from ..spatial_map.ers_persistence import list_scene_shots, save_scene_shot
    from ..spatial_map.service import list_documents
    from .cinematographer_service import hydrate_cinematographer
    from .ers_resolver import resolve_ers_for_sheet
    from .service import SceneCreatorError, create_or_update_shot, ensure_scene_id

    maps = list_documents(db, project_id)
    wanted_map = (spatial_map_id or "").strip()
    document = next((m for m in maps if m.id == wanted_map), None) if wanted_map else (maps[0] if maps else None)
    map_id = str(getattr(document, "id", "") or "") if document else ""
    map_scene = str(getattr(document, "sceneId", "") or "") if document else ""

    scene = ensure_scene_id(db, project_id, (scene_id or "").strip() or map_scene)
    sheet = _pick_sheet(project_id, scene_id=scene.id, sheet_id=sheet_id, map_id=map_id)
    sheet_id_resolved = str(getattr(sheet, "sheetId", "") or "")
    try:
        package, _runtime = resolve_ers_for_sheet(db, project_id, sheet_id_resolved)
    except Exception as exc:
        raise SceneCreatorHandoffError(str(exc) or "Environment Reference Sheet could not be resolved.") from exc

    ers_library = str(
        getattr(package, "ers_composite_asset_id", "")
        or getattr(sheet, "ers_composite_asset_id", "")
        or ""
    )
    character_ids = _character_ids_from_map(document) if document else []
    prop_ids = _prop_ids_from_map(db, project_id, document) if document else []
    pack = hydrate_cinematographer(db, project_id, scene_id=scene.id)
    cameras = _camera_pointers(pack)

    shots = list_scene_shots(db, project_id, scene_id=scene.id)
    if shots:
        for shot in shots:
            shot.sheet_id = sheet_id_resolved
            shot.ers_package_id = package.id
            if character_ids:
                shot.character_ids = list(dict.fromkeys([*(shot.character_ids or []), *character_ids]))
            if prop_ids:
                shot.prop_entity_ids = list(dict.fromkeys([*(shot.prop_entity_ids or []), *prop_ids]))
            save_scene_shot(db, project_id, shot)
    else:
        created = []
        sources = list(getattr(pack, "cameras", None) or []) or [None]
        for rec in sources:
            camera_body = None
            if rec is not None:
                pose = getattr(rec, "current", None)
                shot_type = str(getattr(pose, "shotType", "") or "medium") if pose is not None else "medium"
                size = "close_up" if "close" in shot_type else "wide" if "wide" in shot_type else "medium_wide"
                camera_body = {
                    "camera_id": str(getattr(rec, "cameraId", "") or ""),
                    "camera_slot": getattr(rec, "cameraSlot", None),
                    "label": str(getattr(rec, "label", "") or "Camera"),
                    "orientation": str(getattr(pose, "orientation", "") or "") if pose is not None else "",
                    "fov_preset": str(getattr(pose, "fovPreset", "") or "") if pose is not None else "",
                    "cinematic": {"shot_size": size, "motion": "static", "framing": "single"},
                }
            try:
                created.append(
                    create_or_update_shot(
                        db,
                        project_id,
                        scene_id=scene.id,
                        sheet_id=sheet_id_resolved,
                        character_ids=character_ids or None,
                        prop_entity_ids=prop_ids or None,
                        camera=camera_body,
                    )
                )
            except SceneCreatorError as exc:
                raise SceneCreatorHandoffError(str(exc)) from exc
        shots = created

    shot_ids = [s.id for s in shots]
    aspect = normalize_production_aspect(getattr(scene, "aspect_ratio", None))
    handoff_id = stable_handoff_id(project_id, map_id, scene.id)
    existing_profiles = list_profiles(db, project_id)
    previous = load_profile(db, project_id, handoff_id)
    title = (
        str(getattr(document, "title", "") or "")
        or str(getattr(scene, "name", "") or "")
        or "scene"
    )
    name = previous.name if previous else _unique_name(existing_profiles, title)
    next_profile = SpatialProfilePointers(
        handoffId=handoff_id,
        name=name,
        displayName=previous.displayName if previous else _display_name(name),
        revision=(previous.revision if previous else 0) + 1,
        projectId=project_id,
        sceneId=scene.id,
        sheetId=sheet_id_resolved,
        spatialMapId=map_id,
        mapVersion=str(getattr(document, "version", "") or ""),
        ersPackageId=str(package.id or ""),
        ersLibraryAssetId=ers_library,
        aspectRatio=aspect,
        characterIds=character_ids,
        propIds=prop_ids,
        shotIds=shot_ids,
        cameras=cameras,
    )
    fingerprint = pointer_fingerprint(next_profile)
    unchanged = bool(previous and previous.fingerprint == fingerprint)
    if unchanged and previous:
        previous.updatedAt = _now()
        previous.revision = previous.revision + 1
        previous.fingerprint = fingerprint
        saved = save_profile(db, project_id, previous)
        noop = True
    else:
        saved = save_profile(db, project_id, next_profile)
        noop = False
    save_selection(
        db,
        project_id,
        ProfileSelection(selectedProfileId=saved.handoffId, workspaceReset=False),
    )
    return {
        "sceneId": saved.sceneId,
        "sheetId": saved.sheetId,
        "handoffId": saved.handoffId,
        "revision": saved.revision,
        "selectedProfileId": saved.handoffId,
        "ersPackageId": saved.ersPackageId,
        "ersLibraryAssetId": saved.ersLibraryAssetId,
        "spatialMapId": saved.spatialMapId,
        "name": saved.name,
        "displayName": saved.displayName,
        "noop": noop,
        "profile": saved.model_dump(),
    }


def select_profile(db: Session, project_id: str, handoff_id: str) -> dict[str, Any]:
    wanted = (handoff_id or "").strip()
    if not wanted or wanted == "none":
        save_selection(db, project_id, ProfileSelection(selectedProfileId=None, workspaceReset=False))
        return {
            "sceneId": "",
            "sheetId": "",
            "handoffId": "",
            "revision": 0,
            "selectedProfileId": None,
            "ersPackageId": "",
            "ersLibraryAssetId": "",
            "spatialMapId": "",
            "mapVersion": "",
            "profile": None,
        }
    profile = load_profile(db, project_id, wanted)
    if profile is None or profile.projectId != project_id:
        raise SceneCreatorHandoffError("Spatial Profile could not be loaded.")
    save_selection(
        db,
        project_id,
        ProfileSelection(selectedProfileId=profile.handoffId, workspaceReset=False),
    )
    return {
        "sceneId": profile.sceneId,
        "sheetId": profile.sheetId,
        "handoffId": profile.handoffId,
        "revision": profile.revision,
        "selectedProfileId": profile.handoffId,
        "ersPackageId": profile.ersPackageId,
        "ersLibraryAssetId": profile.ersLibraryAssetId,
        "spatialMapId": profile.spatialMapId,
        "mapVersion": profile.mapVersion,
        "profile": profile.model_dump(),
    }


def reset_workspace(db: Session, project_id: str) -> dict[str, Any]:
    save_selection(db, project_id, ProfileSelection(selectedProfileId=None, workspaceReset=True))
    return {"ok": True, "selectedProfileId": None, "workspaceReset": True}
