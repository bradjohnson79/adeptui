"""Persistence for Scene Reference Bindings."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import SceneReferenceAuditEvent, SceneReferenceBinding


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dumps(v: Any) -> str:
    return json.dumps(v if v is not None else [], ensure_ascii=False)


def _loads(raw: str | None, default: Any = None) -> Any:
    if not raw:
        return default if default is not None else []
    try:
        return json.loads(raw)
    except Exception:
        return default if default is not None else []


def binding_to_dict(row: SceneReferenceBinding) -> dict[str, Any]:
    asset = getattr(row, "asset", None)
    return {
        "id": row.id,
        "schema_version": row.schema_version,
        "project_id": row.project_id,
        "asset_id": row.asset_id,
        "scope_type": row.scope_type,
        "scope_id": row.scope_id,
        "reference_type": row.reference_type,
        "usage_modes": _loads(row.usage_modes_json, []),
        "reference_roles": _loads(row.reference_roles_json, []),
        "identity_id": row.identity_id,
        "identity_version_id": row.identity_version_id,
        "variant_ids": _loads(row.variant_ids_json, []),
        "enabled": bool(row.enabled),
        "order_index": int(row.order_index or 0),
        "requested_weight": row.requested_weight,
        "notes": row.notes,
        "alias": getattr(row, "alias", None),
        "media_kind": getattr(row, "media_kind", None),
        "asset_name": getattr(asset, "tag", None) or getattr(asset, "filename", None),
        "thumbnail_url": f"/api/assets/{row.asset_id}/file" if row.asset_id else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "inherited_from": None,
        "is_override": False,
        "approval_status": None,
    }


def list_bindings(
    db: Session,
    project_id: str,
    *,
    scope_type: str | None = None,
    scope_id: str | None = None,
    include_deleted: bool = False,
) -> list[SceneReferenceBinding]:
    q = select(SceneReferenceBinding).where(SceneReferenceBinding.project_id == project_id)
    if not include_deleted:
        q = q.where(SceneReferenceBinding.deleted_at.is_(None))
    if scope_type:
        q = q.where(SceneReferenceBinding.scope_type == scope_type)
    if scope_id:
        q = q.where(SceneReferenceBinding.scope_id == scope_id)
    q = q.order_by(SceneReferenceBinding.order_index.asc(), SceneReferenceBinding.id.asc())
    return list(db.scalars(q).all())


def get_binding(db: Session, project_id: str, binding_id: str) -> SceneReferenceBinding | None:
    row = db.get(SceneReferenceBinding, binding_id)
    if not row or row.project_id != project_id or row.deleted_at is not None:
        return None
    return row


def find_soft_deleted_binding(
    db: Session,
    project_id: str,
    *,
    scope_type: str,
    scope_id: str,
    asset_id: str,
    reference_type: str,
) -> SceneReferenceBinding | None:
    q = select(SceneReferenceBinding).where(
        SceneReferenceBinding.project_id == project_id,
        SceneReferenceBinding.scope_type == scope_type,
        SceneReferenceBinding.scope_id == scope_id,
        SceneReferenceBinding.asset_id == asset_id,
        SceneReferenceBinding.reference_type == reference_type,
        SceneReferenceBinding.deleted_at.is_not(None),
    )
    return db.scalars(q).first()


def restore_binding(
    db: Session,
    row: SceneReferenceBinding,
    data: dict[str, Any],
    *,
    actor: str = "user",
) -> SceneReferenceBinding:
    row.deleted_at = None
    row.alias = data.get("alias")
    row.media_kind = data.get("media_kind")
    if data.get("usage_modes") is not None:
        row.usage_modes_json = _dumps(data.get("usage_modes") or [])
    if data.get("reference_roles") is not None:
        row.reference_roles_json = _dumps(data.get("reference_roles") or [])
    row.enabled = bool(data.get("enabled", True))
    row.updated_by = actor
    row.updated_at = _now()
    db.flush()
    return row


def next_order_index(db: Session, project_id: str, scope_type: str, scope_id: str) -> int:
    rows = list_bindings(db, project_id, scope_type=scope_type, scope_id=scope_id)
    if not rows:
        return 0
    return max(int(r.order_index or 0) for r in rows) + 1


def create_binding(db: Session, data: dict[str, Any], *, actor: str = "user") -> SceneReferenceBinding:
    row = SceneReferenceBinding(
        id=str(uuid.uuid4()),
        schema_version=int(data.get("schema_version") or 1),
        project_id=data["project_id"],
        asset_id=data["asset_id"],
        scope_type=data["scope_type"],
        scope_id=data["scope_id"],
        reference_type=data["reference_type"],
        usage_modes_json=_dumps(data.get("usage_modes") or []),
        reference_roles_json=_dumps(data.get("reference_roles") or []),
        identity_id=data.get("identity_id"),
        identity_version_id=data.get("identity_version_id"),
        variant_ids_json=_dumps(data.get("variant_ids") or []),
        enabled=bool(data.get("enabled", True)),
        order_index=int(data.get("order_index") if data.get("order_index") is not None else 0),
        requested_weight=data.get("requested_weight"),
        notes=data.get("notes"),
        alias=data.get("alias"),
        media_kind=data.get("media_kind"),
        created_by=actor,
        updated_by=actor,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.flush()
    audit(
        db,
        project_id=row.project_id,
        binding_id=row.id,
        event_type="binding_created",
        actor=actor,
        payload={"asset_id": row.asset_id, "scope_type": row.scope_type, "scope_id": row.scope_id},
    )
    return row


def update_binding(
    db: Session, row: SceneReferenceBinding, patch: dict[str, Any], *, actor: str = "user"
) -> SceneReferenceBinding:
    mapping = {
        "reference_type": "reference_type",
        "enabled": "enabled",
        "order_index": "order_index",
        "requested_weight": "requested_weight",
        "notes": "notes",
        "identity_id": "identity_id",
        "identity_version_id": "identity_version_id",
        "alias": "alias",
        "media_kind": "media_kind",
    }
    for src, dest in mapping.items():
        if src in patch and patch[src] is not None:
            setattr(row, dest, patch[src])
    if "usage_modes" in patch and patch["usage_modes"] is not None:
        row.usage_modes_json = _dumps(patch["usage_modes"])
    if "reference_roles" in patch and patch["reference_roles"] is not None:
        row.reference_roles_json = _dumps(patch["reference_roles"])
    if "variant_ids" in patch and patch["variant_ids"] is not None:
        row.variant_ids_json = _dumps(patch["variant_ids"])
    row.updated_by = actor
    row.updated_at = _now()
    audit(
        db,
        project_id=row.project_id,
        binding_id=row.id,
        event_type="binding_updated",
        actor=actor,
        payload=patch,
    )
    db.flush()
    return row


def soft_delete_binding(db: Session, row: SceneReferenceBinding, *, actor: str = "user") -> None:
    row.deleted_at = _now()
    row.alias = None
    row.updated_by = actor
    row.updated_at = _now()
    audit(
        db,
        project_id=row.project_id,
        binding_id=row.id,
        event_type="binding_removed",
        actor=actor,
        payload={"asset_id": row.asset_id},
    )
    db.flush()


def reorder_bindings(
    db: Session, project_id: str, binding_ids: list[str], *, actor: str = "user"
) -> list[SceneReferenceBinding]:
    rows = []
    for idx, bid in enumerate(binding_ids):
        row = get_binding(db, project_id, bid)
        if not row:
            continue
        row.order_index = idx
        row.updated_by = actor
        row.updated_at = _now()
        rows.append(row)
    audit(
        db,
        project_id=project_id,
        binding_id=None,
        event_type="bindings_reordered",
        actor=actor,
        payload={"binding_ids": binding_ids},
    )
    db.flush()
    return rows


def audit(
    db: Session,
    *,
    project_id: str,
    binding_id: Optional[str],
    event_type: str,
    actor: str,
    payload: dict[str, Any],
) -> None:
    db.add(
        SceneReferenceAuditEvent(
            id=str(uuid.uuid4()),
            project_id=project_id,
            binding_id=binding_id,
            event_type=event_type,
            actor=actor,
            payload_json=_dumps(payload),
            created_at=_now(),
        )
    )


def count_active_bindings_for_asset(db: Session, project_id: str, asset_id: str) -> int:
    rows = list_bindings(db, project_id)
    return sum(1 for r in rows if r.asset_id == asset_id and r.enabled)
