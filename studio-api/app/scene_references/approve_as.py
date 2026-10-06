"""Approve a Library image as Character / Environment / Prop / Scene Frame.

Creator path: Preview Monitor → Approve as → OK.
This is an authorized save. It does not invent a second sheet system.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import Asset, Scene
from app.scene_references import repository as repo
from app.scene_references import service as ref_service
from app.scene_references.sheet_tags import classify_asset, pascal_alias

ApproveKind = Literal["character", "environment", "prop", "scene_frame"]

_KIND_SPEC: dict[str, dict[str, Any]] = {
    "character": {
        "reference_type": "character",
        "media_kind": "entity",
        "usage_modes": ["identity", "appearance"],
        "reference_roles": ["character"],
        "labels": ["character_sheet", "crs", "character_reference_sheet"],
        "meta_role": "character_sheet",
    },
    "environment": {
        "reference_type": "environment",
        "media_kind": "image",
        "usage_modes": ["environment"],
        "reference_roles": ["environment"],
        "labels": ["environment_reference_sheet", "ers_sheet"],
        "meta_role": "environment_reference_sheet",
    },
    "prop": {
        "reference_type": "prop",
        "media_kind": "entity",
        "usage_modes": ["prop"],
        "reference_roles": ["prop"],
        "labels": ["prop_reference_sheet", "prs"],
        "meta_role": "prop_reference_sheet",
    },
    "scene_frame": {
        "reference_type": "image",
        "media_kind": "image",
        "usage_modes": ["appearance"],
        "reference_roles": ["scene_frame"],
        "labels": ["scene_frame"],
        "meta_role": "scene_frame",
    },
}


def _compact(raw: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (raw or "").lower())


def _load_labels(asset: Asset) -> list[str]:
    raw = getattr(asset, "labels_json", None) or "[]"
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = []
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item).strip()]
    if parsed:
        return [str(parsed)]
    return []


def _load_meta(asset: Asset) -> dict[str, Any]:
    raw = getattr(asset, "prompt_meta_json", None) or "{}"
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _stamp_asset(asset: Asset, *, kind: str, spec: dict[str, Any]) -> None:
    labels = _load_labels(asset)
    for token in spec["labels"]:
        if token not in labels:
            labels.append(token)
    asset.labels_json = json.dumps(labels, ensure_ascii=False)
    meta = _load_meta(asset)
    meta["approvedAs"] = kind
    meta["referenceRole"] = spec["meta_role"]
    asset.prompt_meta_json = json.dumps(meta, ensure_ascii=False)


def _display_name(asset: Asset, alias: str | None) -> str:
    raw = (alias or asset.tag or asset.filename or "Reference").strip()
    raw = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", raw)
    return raw or "Reference"


def _match_character(db: Session, project_id: str, needle: str, *, character_id: str | None):
    from app.character_identity.models import CharacterProfileRow
    from app.character_identity.service import resolve_character_by_name

    if character_id:
        row = db.get(CharacterProfileRow, character_id)
        if row and row.project_id == project_id:
            return row
        raise HTTPException(
            status_code=404,
            detail={"code": "CHARACTER_NOT_FOUND", "message": "That character is not in this project."},
        )

    hit = resolve_character_by_name(db, project_id, needle)
    if hit:
        return hit

    compact = _compact(needle)
    if not compact:
        return None
    ranked: list[tuple[int, CharacterProfileRow]] = []
    rows = (
        db.query(CharacterProfileRow)
        .filter(CharacterProfileRow.project_id == project_id)
        .all()
    )
    for profile in rows:
        name_c = _compact(profile.name or "")
        slug_c = _compact(getattr(profile, "slug", "") or "")
        if not name_c:
            continue
        if compact == name_c or compact == slug_c:
            ranked.append((100, profile))
        elif compact.startswith(name_c) and len(name_c) >= 3:
            ranked.append((80 + min(len(name_c), 19), profile))
        elif name_c.startswith(compact) and len(compact) >= 3:
            ranked.append((70 + min(len(compact), 19), profile))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    best = ranked[0][0]
    winners = [row for score, row in ranked if score == best]
    if len(winners) > 1:
        names = ", ".join(row.name for row in winners if row.name)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CHARACTER_AMBIGUOUS",
                "message": f"More than one character matches this picture ({names}). Choose one, then approve.",
                "candidates": [{"id": row.id, "name": row.name} for row in winners],
            },
        )
    return winners[0]


def _ensure_character(db: Session, project_id: str, needle: str, *, character_id: str | None):
    from app.character_identity.schemas import CharacterProfileCreate
    from app.character_identity.service import create_profile

    existing = _match_character(db, project_id, needle, character_id=character_id)
    if existing:
        return existing, False
    created = create_profile(db, project_id, CharacterProfileCreate(name=needle, role="character"))
    from app.character_identity.models import CharacterProfileRow

    row = db.get(CharacterProfileRow, created.id)
    if not row:
        raise HTTPException(status_code=500, detail={"code": "CHARACTER_CREATE_FAILED", "message": "Could not create the character."})
    return row, True


def _upsert_project_binding(
    db: Session,
    project_id: str,
    asset_id: str,
    *,
    spec: dict[str, Any],
    alias: str,
    identity_id: str | None,
) -> dict[str, Any]:
    rows = [row for row in repo.list_bindings(db, project_id, scope_type="project", scope_id=project_id) if row.asset_id == asset_id]
    target_type = spec["reference_type"]
    same_type = next((row for row in rows if row.reference_type == target_type), None)
    other = next((row for row in rows if row.reference_type != target_type), None)
    patch = {
        "reference_type": target_type,
        "media_kind": spec["media_kind"],
        "usage_modes": spec["usage_modes"],
        "reference_roles": spec["reference_roles"],
        "alias": pascal_alias(alias),
        "identity_id": identity_id,
        "notes": "Approved from Preview Monitor",
    }
    if same_type:
        return ref_service.update(db, project_id, same_type.id, patch, actor="user")
    if other:
        return ref_service.update(db, project_id, other.id, patch, actor="user")
    return ref_service.attach(
        db,
        project_id,
        {
            "asset_id": asset_id,
            "scope_type": "project",
            "scope_id": project_id,
            "reference_type": target_type,
            "media_kind": spec["media_kind"],
            "alias": pascal_alias(alias),
            "usage_modes": spec["usage_modes"],
            "reference_roles": spec["reference_roles"],
            "identity_id": identity_id,
            "notes": "Approved from Preview Monitor",
        },
        actor="user",
    )


def _set_scene_frame(db: Session, project_id: str, scene_id: str | None, asset_id: str) -> bool:
    if not scene_id:
        return False
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        return False
    scene.start_asset_id = asset_id
    return True


def approve_library_image_as(
    db: Session,
    project_id: str,
    *,
    asset_id: str,
    kind: str,
    scene_id: str | None = None,
    character_id: str | None = None,
) -> dict[str, Any]:
    if kind not in _KIND_SPEC:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_KIND", "message": "Choose Character, Environment, Prop, or Scene Frame."},
        )
    spec = _KIND_SPEC[kind]
    ref_service.require_project(db, project_id)
    ref_service.require_asset_in_project(db, project_id, asset_id)
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "ASSET_NOT_FOUND", "message": "That Library file is missing."})
    kind_token = str(asset.kind or "").lower()
    if kind_token and kind_token not in {"image", "img", "still"}:
        raise HTTPException(
            status_code=400,
            detail={"code": "NOT_AN_IMAGE", "message": "Approve as works on pictures. Use a Library image."},
        )

    alias = _display_name(asset, None)
    _stamp_asset(asset, kind=kind, spec=spec)
    db.flush()

    character_out: dict[str, Any] | None = None
    created_character = False
    identity_id = None
    if kind == "character":
        from app.character_identity.service import approve_character_candidate

        profile, created_character = _ensure_character(db, project_id, alias, character_id=character_id)
        identity_id = profile.id
        approved = approve_character_candidate(
            db,
            project_id,
            profile.id,
            asset_id=asset_id,
            reference_role="hero_identity",
            source_type="library",
            notes="Approved as Character Reference Sheet from Preview Monitor",
            owner_confirmed=True,
        )
        character_out = {
            "characterId": profile.id,
            "name": profile.name,
            "created": created_character,
            "approvedSheetAssetId": approved.get("approvedSheetAssetId") or asset_id,
            # Canonical tag from the Library asset tag (e.g. @Korri40YearsOld),
            # not the profile name. Character identity is the tag; reference
            # type (CRS) is metadata and never encoded into the @ token.
            "atTag": f"@{pascal_alias(alias)}",
        }

    binding = _upsert_project_binding(
        db,
        project_id,
        asset_id,
        spec=spec,
        alias=alias,
        identity_id=identity_id,
    )
    scene_frame_set = False
    if kind == "scene_frame":
        scene_frame_set = _set_scene_frame(db, project_id, scene_id, asset_id)
        if scene_id:
            existing_frame = next(
                (
                    row
                    for row in repo.list_bindings(db, project_id, scope_type="start_frame", scope_id=scene_id)
                    if row.asset_id == asset_id
                ),
                None,
            )
            if existing_frame is None:
                try:
                    ref_service.attach(
                        db,
                        project_id,
                        {
                            "asset_id": asset_id,
                            "scope_type": "start_frame",
                            "scope_id": scene_id,
                            "reference_type": "image",
                            "media_kind": "image",
                            "alias": pascal_alias(alias),
                            "usage_modes": ["appearance"],
                            "reference_roles": ["scene_frame"],
                            "notes": "Approved as Scene Frame from Preview Monitor",
                        },
                        actor="user",
                    )
                except HTTPException as exc:
                    if getattr(exc, "status_code", None) not in {409, 400}:
                        raise
        if scene_frame_set:
            db.commit()

    classified = classify_asset(asset, preferred_alias=alias)
    label = {
        "character": "Character",
        "environment": "Environment",
        "prop": "Prop",
        "scene_frame": "Scene Frame",
    }[kind]
    token = binding.get("display_token") or f"{'@' if kind == 'character' else '#'}{pascal_alias(alias)}"
    message = f"Approved as {label}."
    if character_out:
        message = f"Approved as Character — {character_out['atTag']}."
    elif kind == "scene_frame":
        message = "Approved as Scene Frame — this picture is the opening frame for the shot."
    return {
        "ok": True,
        "kind": kind,
        "label": label,
        "assetId": asset_id,
        "binding": binding,
        "character": character_out,
        "sceneFrameSet": scene_frame_set,
        "sheetKind": classified.kind,
        "displayToken": token,
        "message": message,
        "mock": False,
    }
