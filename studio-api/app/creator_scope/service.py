"""Query index + helpers for creator-asset visibility.

The canonical entity stays in Character / Prop / Environment stores.
This table is a direct query index so globals do not require N-project fan-out.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, String, Text, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..db import Base
from .contract import (
    ENTITY_CHARACTER,
    ENTITY_ENVIRONMENT,
    ENTITY_PROP,
    OWNER_REQUIRED,
    PROFILE_NAME_ALREADY_EXISTS,
    CreatorScopeError,
    canonical_tag,
    display_profile_name,
    normalize_is_global,
    ENVIRONMENT_NAME_ALREADY_EXISTS_MESSAGE,
    normalize_profile_name,
    owner_required_message,
    profile_name_conflict_message,
)

SCOPE_TYPES = (ENTITY_CHARACTER, ENTITY_PROP, ENTITY_ENVIRONMENT)


class CreatorAssetScopeRow(Base):
    __tablename__ = "creator_asset_scope"

    entity_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owning_project_id: Mapped[str] = mapped_column(String(36), index=True)
    is_global: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    tag: Mapped[str] = mapped_column(String(200), default="", index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    name_normalized: Mapped[str] = mapped_column(String(200), default="", index=True)
    identity_asset_id: Mapped[str] = mapped_column(String(36), default="", index=True)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class CreatorEntityTombstoneRow(Base):
    """Intentional delete marker so heal/reconnect cannot resurrect a removed identity."""

    __tablename__ = "creator_entity_tombstone"

    entity_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owning_project_id: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


def ensure_creator_scope_tables() -> None:
    from sqlalchemy import text

    from ..db import engine

    Base.metadata.create_all(
        bind=engine,
        tables=[CreatorAssetScopeRow.__table__, CreatorEntityTombstoneRow.__table__],
    )
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(character_profiles)")).fetchall()
        if rows and not any(r[1] == "is_global" for r in rows):
            conn.execute(
                text(
                    "ALTER TABLE character_profiles "
                    "ADD COLUMN is_global BOOLEAN NOT NULL DEFAULT 0"
                )
            )
            conn.commit()
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_creator_asset_scope_global "
                "ON creator_asset_scope (entity_type, is_global)"
            )
        )
        cols = conn.execute(text("PRAGMA table_info(creator_asset_scope)")).fetchall()
        if cols and not any(r[1] == "name_normalized" for r in cols):
            conn.execute(
                text(
                    "ALTER TABLE creator_asset_scope "
                    "ADD COLUMN name_normalized VARCHAR(200) NOT NULL DEFAULT ''"
                )
            )
        conn.execute(
            text(
                "UPDATE creator_asset_scope SET name_normalized = lower(trim(name)) "
                "WHERE name_normalized = '' AND trim(name) != ''"
            )
        )
        try:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_creator_scope_local_name "
                    "ON creator_asset_scope (entity_type, owning_project_id, name_normalized) "
                    "WHERE name_normalized != ''"
                )
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_creator_scope_global_name "
                    "ON creator_asset_scope (entity_type, name_normalized) "
                    "WHERE is_global = 1 AND name_normalized != ''"
                )
            )
        except Exception:
            # Existing duplicates must be merged before the unique index can apply.
            pass
        conn.commit()


def mark_entity_deleted(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    owning_project_id: str = "",
) -> None:
    et = str(entity_type or "").strip()
    eid = str(entity_id or "").strip()
    if not et or not eid:
        return
    existing = (
        db.query(CreatorEntityTombstoneRow)
        .filter(
            CreatorEntityTombstoneRow.entity_type == et,
            CreatorEntityTombstoneRow.entity_id == eid,
        )
        .first()
    )
    if existing is not None:
        return
    db.add(
        CreatorEntityTombstoneRow(
            entity_type=et,
            entity_id=eid,
            owning_project_id=str(owning_project_id or "").strip(),
            created_at=_now(),
        )
    )


def is_entity_deleted(db: Session, *, entity_type: str, entity_id: str) -> bool:
    et = str(entity_type or "").strip()
    eid = str(entity_id or "").strip()
    if not et or not eid:
        return False
    return (
        db.query(CreatorEntityTombstoneRow)
        .filter(
            CreatorEntityTombstoneRow.entity_type == et,
            CreatorEntityTombstoneRow.entity_id == eid,
        )
        .first()
        is not None
    )


def sync_scope(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    owning_project_id: str,
    is_global: bool = False,
    tag: str = "",
    name: str = "",
    identity_asset_id: str = "",
) -> CreatorAssetScopeRow:
    ensure_creator_scope_tables()
    et = str(entity_type or "").strip()
    eid = str(entity_id or "").strip()
    owner = str(owning_project_id or "").strip()
    if et not in SCOPE_TYPES or not eid or not owner:
        raise CreatorScopeError("INVALID_SCOPE", "Creator scope needs type, id, and owning project.")
    now = _now()
    row = (
        db.query(CreatorAssetScopeRow)
        .filter(
            CreatorAssetScopeRow.entity_type == et,
            CreatorAssetScopeRow.entity_id == eid,
        )
        .first()
    )
    if row is None:
        row = CreatorAssetScopeRow(
            entity_type=et,
            entity_id=eid,
            owning_project_id=owner,
            created_at=now,
        )
        db.add(row)
    row.owning_project_id = owner
    row.is_global = bool(is_global)
    row.tag = canonical_tag(tag or name)
    row.name = display_profile_name(name)
    row.name_normalized = normalize_profile_name(name)
    row.identity_asset_id = str(identity_asset_id or "").strip()
    row.updated_at = now
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise CreatorScopeError(
            PROFILE_NAME_ALREADY_EXISTS,
            profile_name_conflict_message(
                entity_type=et,
                existing_name=display_profile_name(name),
                is_global=bool(is_global),
            ),
            status=409,
            extra=_name_conflict_extra(
                entity_type=et,
                name=display_profile_name(name),
                is_global=bool(is_global),
            ),
        ) from exc
    db.refresh(row)
    return row


def delete_scope(db: Session, *, entity_type: str, entity_id: str) -> None:
    row = (
        db.query(CreatorAssetScopeRow)
        .filter(
            CreatorAssetScopeRow.entity_type == str(entity_type),
            CreatorAssetScopeRow.entity_id == str(entity_id),
        )
        .first()
    )
    if row is None:
        return
    db.delete(row)
    db.commit()


def visible_to_project(row: CreatorAssetScopeRow, project_id: str) -> bool:
    pid = str(project_id or "").strip()
    return bool(pid) and (row.owning_project_id == pid or bool(row.is_global))


def list_visible_scope(
    db: Session,
    project_id: str,
    *,
    entity_type: str | None = None,
) -> list[CreatorAssetScopeRow]:
    """One query: owning project OR is_global. Deduped by primary key."""
    ensure_creator_scope_tables()
    pid = str(project_id or "").strip()
    q = db.query(CreatorAssetScopeRow).filter(
        or_(
            CreatorAssetScopeRow.owning_project_id == pid,
            CreatorAssetScopeRow.is_global.is_(True),
        )
    )
    if entity_type:
        q = q.filter(CreatorAssetScopeRow.entity_type == entity_type)
    rows = q.all()
    seen: set[tuple[str, str]] = set()
    out: list[CreatorAssetScopeRow] = []
    for row in rows:
        key = (row.entity_type, row.entity_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def find_tag_collision(
    db: Session,
    *,
    entity_type: str,
    tag: str,
    exclude_id: str = "",
    owning_project_id: str = "",
    making_global: bool = False,
) -> CreatorAssetScopeRow | None:
    """Prevent two selectable assets from sharing a tag in the visible scope."""
    ensure_creator_scope_tables()
    token = canonical_tag(tag).lower()
    if not token:
        return None
    rows = (
        db.query(CreatorAssetScopeRow)
        .filter(CreatorAssetScopeRow.entity_type == entity_type)
        .all()
    )
    for row in rows:
        if exclude_id and row.entity_id == exclude_id:
            continue
        if canonical_tag(row.tag).lower() != token:
            continue
        # Local vs local in the same project
        if owning_project_id and row.owning_project_id == owning_project_id:
            return row
        # Any global collides with a new visible item of the same tag
        if row.is_global or making_global:
            return row
    return None


def _name_conflict_extra(
    *,
    entity_type: str,
    name: str,
    is_global: bool,
    existing: CreatorAssetScopeRow | None = None,
) -> dict[str, Any]:
    row = existing
    return {
        "existingId": row.entity_id if row is not None else "",
        "existingName": display_profile_name(row.name if row is not None else name),
        "scope": "global" if (row.is_global if row is not None else is_global) else "local",
        "type": entity_type,
        "isGlobal": bool(row.is_global if row is not None else is_global),
    }


def find_name_collision(
    db: Session,
    *,
    entity_type: str,
    name: str,
    exclude_id: str = "",
    owning_project_id: str = "",
    making_global: bool = False,
) -> CreatorAssetScopeRow | None:
    """Visible-scope display-name uniqueness (normalized)."""
    ensure_creator_scope_tables()
    key = normalize_profile_name(name)
    if not key:
        return None
    owner = str(owning_project_id or "").strip()
    rows = (
        db.query(CreatorAssetScopeRow)
        .filter(CreatorAssetScopeRow.entity_type == entity_type)
        .all()
    )
    for row in rows:
        if exclude_id and row.entity_id == exclude_id:
            continue
        other = row.name_normalized or normalize_profile_name(row.name)
        if other != key:
            continue
        if owner and row.owning_project_id == owner:
            return row
        if row.is_global or making_global:
            return row
    return None


def require_unique_profile_name(
    db: Session,
    *,
    entity_type: str,
    name: str,
    owning_project_id: str,
    exclude_id: str = "",
    making_global: bool = False,
) -> None:
    hit = find_name_collision(
        db,
        entity_type=entity_type,
        name=name,
        exclude_id=exclude_id,
        owning_project_id=owning_project_id,
        making_global=making_global,
    )
    if hit is None:
        return
    message = profile_name_conflict_message(
        entity_type=entity_type,
        existing_name=hit.name,
        is_global=bool(hit.is_global),
    )
    if entity_type == ENTITY_ENVIRONMENT and not hit.is_global:
        message = ENVIRONMENT_NAME_ALREADY_EXISTS_MESSAGE
    raise CreatorScopeError(
        PROFILE_NAME_ALREADY_EXISTS,
        message,
        status=409,
        extra=_name_conflict_extra(
            entity_type=entity_type,
            name=hit.name,
            is_global=bool(hit.is_global),
            existing=hit,
        ),
    )


def resolve_visible_profile(
    db: Session,
    *,
    entity_type: str,
    project_id: str,
    name: str,
) -> CreatorAssetScopeRow | None:
    key = normalize_profile_name(name)
    if not key:
        return None
    for row in list_visible_scope(db, project_id, entity_type=entity_type):
        other = row.name_normalized or normalize_profile_name(row.name)
        if other == key:
            return row
    return None


def reuse_existing_profile(
    db: Session,
    *,
    entity_type: str,
    project_id: str,
    name: str,
) -> dict[str, Any] | None:
    """Co-Director must reuse a visible canonical profile instead of creating a duplicate."""
    row = resolve_visible_profile(db, entity_type=entity_type, project_id=project_id, name=name)
    if row is None:
        return None
    from .contract import TYPE_LABELS

    label = TYPE_LABELS.get(entity_type, "profile")
    shown = display_profile_name(row.name) or name
    return {
        "ok": True,
        "reused": True,
        "created": False,
        "entityType": entity_type,
        "entityId": row.entity_id,
        "existingId": row.entity_id,
        "existingName": shown,
        "isGlobal": bool(row.is_global),
        "scope": "global" if row.is_global else "local",
        "owningProjectId": row.owning_project_id,
        "message": f"{shown} already exists. I'll use the existing {label} profile.",
    }


def list_normalized_name_duplicates(
    db: Session,
    *,
    entity_type: str | None = None,
) -> list[dict[str, Any]]:
    """Audit helper: groups that share a normalized name inside a colliding scope."""
    ensure_creator_scope_tables()
    q = db.query(CreatorAssetScopeRow)
    if entity_type:
        q = q.filter(CreatorAssetScopeRow.entity_type == entity_type)
    groups: dict[tuple[str, str, str], list[CreatorAssetScopeRow]] = {}
    for row in q.all():
        key = row.name_normalized or normalize_profile_name(row.name)
        if not key:
            continue
        scope_key = "global" if row.is_global else row.owning_project_id
        bucket = (row.entity_type, scope_key, key)
        groups.setdefault(bucket, []).append(row)
    out: list[dict[str, Any]] = []
    for (et, scope_key, key), rows in groups.items():
        if len(rows) < 2:
            continue
        out.append(
            {
                "entityType": et,
                "scope": "global" if scope_key == "global" else "local",
                "scopeKey": scope_key,
                "nameNormalized": key,
                "profiles": [
                    {
                        "id": r.entity_id,
                        "name": r.name,
                        "isGlobal": bool(r.is_global),
                        "owningProjectId": r.owning_project_id,
                        "tag": r.tag,
                    }
                    for r in rows
                ],
            }
        )
    return out


def list_cross_project_usage(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    owning_project_id: str,
) -> list[dict[str, Any]]:
    """Bindings in other projects that still point at this canonical entity."""
    usage: list[dict[str, Any]] = []
    owner = str(owning_project_id or "").strip()
    eid = str(entity_id or "").strip()
    try:
        from ..scene_references.models import SceneReferenceBinding

        q = db.query(SceneReferenceBinding).filter(
            SceneReferenceBinding.identity_id == eid,
            SceneReferenceBinding.deleted_at.is_(None),
        )
        if owner:
            q = q.filter(SceneReferenceBinding.project_id != owner)
        for binding in q.all():
            usage.append(
                {
                    "kind": "scene_reference",
                    "projectId": binding.project_id,
                    "bindingId": binding.id,
                    "alias": binding.alias,
                }
            )
    except Exception:
        pass
    try:
        from ..db import Project

        for item in usage:
            proj = db.get(Project, item.get("projectId"))
            if proj is not None:
                item["projectName"] = getattr(proj, "name", "") or item["projectId"]
    except Exception:
        pass
    return usage


def list_entity_usage(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    owning_project_id: str,
) -> list[dict[str, Any]]:
    """Return all canonical-entity usage visible to the deleting project.

    For global entities, usage across every project is returned; for local
    entities, only the owning project is searched. Each dict carries a human
    ``kind`` label and a resolved ``projectName``. Additional best-effort
    checks are wrapped in try/except so missing tables/models never break the
    preview.
    """
    usage: list[dict[str, Any]] = []
    owner = str(owning_project_id or "").strip()
    eid = str(entity_id or "").strip()
    is_global = False
    try:
        scope = (
            db.query(CreatorAssetScopeRow)
            .filter(
                CreatorAssetScopeRow.entity_type == str(entity_type),
                CreatorAssetScopeRow.entity_id == eid,
            )
            .first()
        )
        if scope is not None:
            is_global = bool(scope.is_global)
    except Exception:
        pass

    seen: set[tuple[str, str, str]] = set()

    def _add(kind: str, project_id: str, binding_id: str = "", alias: str = "", **extra: Any) -> None:
        key = (str(kind), str(project_id), str(binding_id or alias or extra.get("id", "")))
        if key in seen:
            return
        seen.add(key)
        item: dict[str, Any] = {
            "kind": str(kind),
            "projectId": str(project_id),
            "bindingId": str(binding_id) if binding_id else "",
            "alias": str(alias) if alias else "",
        }
        item.update(extra)
        usage.append(item)

    # SceneReferenceBinding rows pointing at this canonical entity.
    try:
        from ..scene_references.models import SceneReferenceBinding

        q = db.query(SceneReferenceBinding).filter(
            SceneReferenceBinding.identity_id == eid,
            SceneReferenceBinding.deleted_at.is_(None),
        )
        if not is_global and owner:
            q = q.filter(SceneReferenceBinding.project_id == owner)
        for binding in q.all():
            _add(
                "Scene reference",
                binding.project_id,
                binding_id=binding.id,
                alias=binding.alias or "",
            )
    except Exception:
        pass

    # Entity-specific best-effort checks.
    if str(entity_type) == ENTITY_CHARACTER:
        try:
            from ..character_identity.models import (
                CharacterPropRow,
                CharacterReferenceAssetRow,
                CharacterTraitRow,
                VoiceProfileRow,
            )

            for row in (
                db.query(CharacterPropRow)
                .filter(CharacterPropRow.character_profile_id == eid)
                .all()
            ):
                _add("Character prop", owner, binding_id=row.id, alias=row.name)
            for row in (
                db.query(CharacterReferenceAssetRow)
                .filter(CharacterReferenceAssetRow.character_profile_id == eid)
                .all()
            ):
                _add(
                    "Character reference asset",
                    owner,
                    binding_id=row.id,
                    alias=row.reference_role,
                )
            for row in (
                db.query(VoiceProfileRow)
                .filter(VoiceProfileRow.character_profile_id == eid)
                .all()
            ):
                _add("Voice profile", row.project_id or owner, binding_id=row.id, alias=row.name)
            for row in (
                db.query(CharacterTraitRow)
                .filter(CharacterTraitRow.character_profile_id == eid)
                .all()
            ):
                _add("Character trait", owner, binding_id=row.id, alias=row.key)
        except Exception:
            pass
        try:
            from ..continuity.models import VisualIdentityRow

            for row in (
                db.query(VisualIdentityRow)
                .filter(VisualIdentityRow.character_profile_id == eid)
                .all()
            ):
                _add("Visual identity", row.project_id or owner, binding_id=row.id, alias=row.display_name)
        except Exception:
            pass
        try:
            from ..db import Job

            job_q = db.query(Job).filter(Job.params_json.contains(eid))
            if not is_global and owner:
                job_q = job_q.filter(Job.project_id == owner)
            for job in job_q.all():
                _add("Image generation job", job.project_id or owner, binding_id=job.id, alias=job.kind)
        except Exception:
            pass

    if str(entity_type) == ENTITY_PROP:
        try:
            from ..spatial_map.ers_persistence import list_scene_shots

            projects_to_scan = [owner] if not is_global else None
            if projects_to_scan is None:
                try:
                    from ..db import Project

                    projects_to_scan = [p.id for p in db.query(Project).all()]
                except Exception:
                    projects_to_scan = [owner]
            for pid in projects_to_scan:
                try:
                    for shot in list_scene_shots(db, pid):
                        if eid in (getattr(shot, "prop_entity_ids", None) or []):
                            _add("Shot prop", pid, binding_id=shot.shot_id or shot.id or "", alias=shot.name or "")
                except Exception:
                    pass
        except Exception:
            pass
        try:
            from ..spatial_map.models import SpatialMapDocumentRow

            doc_q = db.query(SpatialMapDocumentRow)
            if not is_global and owner:
                doc_q = doc_q.filter(SpatialMapDocumentRow.project_id == owner)
            for doc in doc_q.all():
                raw = str(getattr(doc, "document_json", "") or "")
                if eid in raw:
                    _add("Spatial map", doc.project_id or owner, binding_id=doc.id, alias=doc.title or "")
        except Exception:
            pass
        try:
            from ..db import Job

            job_q = db.query(Job).filter(Job.params_json.contains(eid))
            if not is_global and owner:
                job_q = job_q.filter(Job.project_id == owner)
            for job in job_q.all():
                _add("Image generation job", job.project_id or owner, binding_id=job.id, alias=job.kind)
        except Exception:
            pass

    if str(entity_type) == ENTITY_ENVIRONMENT:
        try:
            from ..environment_reference_sheet.store import list_sheets

            for sheet in list_sheets(owner):
                if str(getattr(sheet, "sceneId", "") or "").strip() == eid:
                    _add(
                        "Environment Reference Sheet",
                        owner,
                        binding_id=sheet.sheetId,
                        alias=sheet.name or "",
                    )
        except Exception:
            pass
        try:
            from ..db import Job

            job_q = db.query(Job).filter(Job.params_json.contains(eid))
            if not is_global and owner:
                job_q = job_q.filter(Job.project_id == owner)
            for job in job_q.all():
                _add("Image generation job", job.project_id or owner, binding_id=job.id, alias=job.kind)
        except Exception:
            pass
        try:
            from ..scene_references.models import SceneReferenceBinding

            alias_q = db.query(SceneReferenceBinding).filter(
                SceneReferenceBinding.deleted_at.is_(None),
                or_(
                    SceneReferenceBinding.identity_id == eid,
                    SceneReferenceBinding.alias.contains(eid),
                ),
            )
            if not is_global and owner:
                alias_q = alias_q.filter(SceneReferenceBinding.project_id == owner)
            for binding in alias_q.all():
                _add(
                    "ERS scene binding",
                    binding.project_id,
                    binding_id=binding.id,
                    alias=binding.alias or "",
                )
        except Exception:
            pass

    # Resolve project names for every usage item.
    try:
        from ..db import Project

        pids = {str(u.get("projectId") or "").strip() for u in usage}
        pids.discard("")
        names = {}
        if pids:
            for proj in db.query(Project).filter(Project.id.in_(list(pids))).all():
                names[str(proj.id)] = str(getattr(proj, "name", "") or proj.id)
        for item in usage:
            pid = str(item.get("projectId") or "").strip()
            item["projectName"] = names.get(pid) or pid
    except Exception:
        for item in usage:
            item.setdefault("projectName", item.get("projectId") or "")

    return usage


def delete_preview_payload(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    name: str,
    is_global: bool,
    owning_project_id: str,
    can_delete: bool = True,
    block_reason: str | None = None,
    library_assets_kept: bool = True,
) -> dict[str, Any]:
    """Build the canonical delete-preview payload for any creator entity."""
    usage_list = list_entity_usage(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        owning_project_id=owning_project_id,
    )
    return {
        "entityType": str(entity_type),
        "entityId": str(entity_id),
        "name": str(name or ""),
        "isGlobal": bool(is_global),
        "owningProjectId": str(owning_project_id or ""),
        "usage": usage_list,
        "usageCount": len(usage_list),
        "projectCount": len({str(u.get("projectId") or "").strip() for u in usage_list if str(u.get("projectId") or "").strip()}),
        "libraryAssetsKept": bool(library_assets_kept),
        "canDelete": bool(can_delete),
        "blockReason": block_reason or None,
    }


def require_delete_safety(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    owning_project_id: str,
    is_global: bool,
    confirm_cross_project: bool = False,
) -> list[dict[str, Any]]:
    usage = list_cross_project_usage(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        owning_project_id=owning_project_id,
    )
    if is_global and usage and not confirm_cross_project:
        names = sorted({str(u.get("projectName") or u.get("projectId") or "") for u in usage})
        raise CreatorScopeError(
            "GLOBAL_IN_USE",
            "This Global asset is used in other projects: "
            + ", ".join(n for n in names if n)
            + ". Confirm delete to remove it everywhere.",
            status=409,
            extra={"usage": usage, "confirmRequired": True},
        )
    return usage


def load_entity_for_reference(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
) -> CreatorAssetScopeRow | None:
    """Resolve a stored reference by canonical id even after Global is turned off."""
    ensure_creator_scope_tables()
    return (
        db.query(CreatorAssetScopeRow)
        .filter(
            CreatorAssetScopeRow.entity_type == entity_type,
            CreatorAssetScopeRow.entity_id == entity_id,
        )
        .first()
    )


def load_visible_entity(
    db: Session,
    *,
    project_id: str,
    entity_type: str,
    entity_id: str,
) -> CreatorAssetScopeRow | None:
    row = load_entity_for_reference(db, entity_type=entity_type, entity_id=entity_id)
    if row is None or not visible_to_project(row, project_id):
        return None
    return row


def require_owner_for_mutate(
    *,
    entity_type: str,
    owner_project_id: str,
    viewing_project_id: str,
) -> None:
    owner = str(owner_project_id or "").strip()
    viewer = str(viewing_project_id or "").strip()
    if owner and viewer and owner == viewer:
        return
    raise CreatorScopeError(
        OWNER_REQUIRED,
        owner_required_message(entity_type),
        status=403,
    )


_META_ENTITY_KEYS = (
    ("characterId", ENTITY_CHARACTER),
    ("character_id", ENTITY_CHARACTER),
    ("propId", ENTITY_PROP),
    ("prop_id", ENTITY_PROP),
    ("environmentId", ENTITY_ENVIRONMENT),
    ("environment_id", ENTITY_ENVIRONMENT),
    ("sheetId", ENTITY_ENVIRONMENT),
    ("ersSheetId", ENTITY_ENVIRONMENT),
)


def _scope_for(db: Session, entity_type: str, entity_id: str) -> CreatorAssetScopeRow | None:
    eid = str(entity_id or "").strip()
    if not eid:
        return None
    return (
        db.query(CreatorAssetScopeRow)
        .filter(
            CreatorAssetScopeRow.entity_type == entity_type,
            CreatorAssetScopeRow.entity_id == eid,
        )
        .first()
    )


def _visible_global_entity(db: Session, viewing_project_id: str, entity_type: str, entity_id: str) -> bool:
    scope = _scope_for(db, entity_type, entity_id)
    return scope is not None and visible_to_project(scope, viewing_project_id)


def resolve_readable_asset(db: Session, viewing_project_id: str, asset_id: str):
    """Allow a viewing project to read only Global-linked canonical backing files."""
    from ..db import Asset

    aid = str(asset_id or "").strip()
    pid = str(viewing_project_id or "").strip()
    asset = db.get(Asset, aid) if aid else None
    if asset is None:
        return None
    if str(getattr(asset, "project_id", "") or "") == pid:
        return asset
    scope = (
        db.query(CreatorAssetScopeRow)
        .filter(CreatorAssetScopeRow.identity_asset_id == aid)
        .first()
    )
    if scope is not None and visible_to_project(scope, pid):
        return asset
    try:
        meta_raw = getattr(asset, "prompt_meta_json", None) or "{}"
        meta = json.loads(meta_raw) if isinstance(meta_raw, str) else (meta_raw or {})
        for key, entity_type in _META_ENTITY_KEYS:
            entity_id = str((meta or {}).get(key) or "").strip()
            if entity_id and _visible_global_entity(db, pid, entity_type, entity_id):
                return asset
    except Exception:
        pass
    try:
        from ..character_identity.models import CharacterReferenceAssetRow

        ref = (
            db.query(CharacterReferenceAssetRow)
            .filter(CharacterReferenceAssetRow.asset_id == aid)
            .first()
        )
        if ref is not None and _visible_global_entity(
            db, pid, ENTITY_CHARACTER, str(ref.character_profile_id or "")
        ):
            return asset
    except Exception:
        pass
    try:
        from ..character_identity.models import CharacterTraitRow

        trait = (
            db.query(CharacterTraitRow)
            .filter(
                CharacterTraitRow.key == "cc_v2",
                CharacterTraitRow.value.contains(aid),
            )
            .first()
        )
        if trait is not None and _visible_global_entity(
            db, pid, ENTITY_CHARACTER, str(trait.character_profile_id or "")
        ):
            return asset
    except Exception:
        pass
    try:
        from ..character_identity.models import VoiceProfileRow

        voice = (
            db.query(VoiceProfileRow)
            .filter(
                or_(
                    VoiceProfileRow.approved_preview_asset_id == aid,
                    VoiceProfileRow.reference_asset_id == aid,
                    VoiceProfileRow.candidate_asset_ids_json.contains(aid),
                )
            )
            .first()
        )
        if voice is not None and _visible_global_entity(
            db, pid, ENTITY_CHARACTER, str(voice.character_profile_id or "")
        ):
            return asset
    except Exception:
        pass
    try:
        from ..scene_references.models import SceneReferenceBinding

        bound = (
            db.query(SceneReferenceBinding)
            .filter(
                SceneReferenceBinding.project_id == pid,
                SceneReferenceBinding.deleted_at.is_(None),
                or_(
                    SceneReferenceBinding.asset_id == aid,
                    SceneReferenceBinding.identity_id == (scope.entity_id if scope else ""),
                ),
            )
            .first()
        )
        if bound is not None:
            return asset
    except Exception:
        pass
    if _visible_global_prop_owns_asset(db, pid, aid):
        return asset
    if _visible_global_environment_owns_asset(db, pid, aid):
        return asset
    return None


def _prop_visual_asset_ids(prop: Any) -> set[str]:
    ids: set[str] = set()
    for key in (
        "reference_asset_id",
        "approved_asset_id",
        "library_asset_id",
        "advanced_sheet_asset_id",
        "primary_approved_asset_id",
    ):
        value = str(getattr(prop, key, "") or "").strip()
        if value:
            ids.add(value)
    angles = getattr(prop, "angles", None) or {}
    if isinstance(angles, dict):
        for slot in angles.values():
            if isinstance(slot, dict):
                value = str(slot.get("asset_id") or slot.get("approved_asset_id") or "").strip()
            else:
                value = str(getattr(slot, "asset_id", "") or getattr(slot, "approved_asset_id", "") or "").strip()
            if value:
                ids.add(value)
    return ids


def _visible_global_prop_owns_asset(db: Session, viewing_project_id: str, asset_id: str) -> bool:
    from ..db import ProjectTraitRow
    from ..spatial_map.ers_persistence import PROP_CATEGORY

    aid = str(asset_id or "").strip()
    if not aid:
        return False
    rows = (
        db.query(ProjectTraitRow)
        .filter(
            ProjectTraitRow.category == PROP_CATEGORY,
            ProjectTraitRow.value.contains(aid),
        )
        .all()
    )
    for row in rows:
        try:
            from ..spatial_map.ers_contracts import PropEntity

            prop = PropEntity.model_validate_json(row.value)
        except Exception:
            continue
        if aid not in _prop_visual_asset_ids(prop):
            continue
        if _visible_global_entity(db, viewing_project_id, ENTITY_PROP, prop.id):
            return True
        if bool(getattr(prop, "is_global", False) or getattr(prop, "isGlobal", False)):
            if visible_to_project(
                CreatorAssetScopeRow(
                    entity_type=ENTITY_PROP,
                    entity_id=prop.id,
                    owning_project_id=prop.project_id,
                    is_global=True,
                ),
                viewing_project_id,
            ):
                return True
    return False


def _visible_global_environment_owns_asset(db: Session, viewing_project_id: str, asset_id: str) -> bool:
    aid = str(asset_id or "").strip()
    if not aid:
        return False
    for row in list_visible_scope(db, viewing_project_id, entity_type=ENTITY_ENVIRONMENT):
        if not visible_to_project(row, viewing_project_id):
            continue
        if str(row.identity_asset_id or "").strip() == aid:
            return True
        try:
            from ..environment_reference_sheet.store import load_sheet

            sheet = load_sheet(row.owning_project_id, row.entity_id)
        except Exception:
            continue
        if sheet is None:
            continue
        for key in ("ers_composite_asset_id", "atlas_asset_id", "master_environment_asset_id"):
            if str(getattr(sheet, key, "") or "").strip() == aid:
                return True
    return False


def asset_file_path(db: Session, viewing_project_id: str, asset_id: str) -> Path | None:
    from ..config import settings

    asset = resolve_readable_asset(db, viewing_project_id, asset_id)
    if asset is None:
        return None
    raw = str(getattr(asset, "path", "") or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_file():
        return path
    alt = Path(settings.data_dir) / raw
    return alt if alt.is_file() else None
