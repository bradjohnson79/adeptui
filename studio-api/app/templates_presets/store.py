"""SQLite persistence helpers for creative items, bindings, and production units."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dumps(data: Any) -> str:
    return json.dumps(data if data is not None else {}, ensure_ascii=False)


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def row_to_item(row: Any, version: int | None = None) -> dict[str, Any]:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "category": row["category"] or "",
        "subcategory": row["subcategory"] or "",
        "scope": row["scope"],
        "name": row["name"],
        "slug": row["slug"],
        "description": row["description"] or "",
        "intent": _loads(row["intent_json"], {}),
        "providerMappings": _loads(row["provider_mappings_json"], {}),
        "compatibility": _loads(row["compatibility_json"], {}),
        "lifecycle": row["lifecycle"],
        "approvalState": row["approval_state"],
        "activeVersionId": row["active_version_id"],
        "version": version if version is not None else 1,
        "ownerUserId": row["owner_user_id"],
        "projectId": row["project_id"],
        "sceneId": row["scene_id"],
        "shotRef": row["shot_ref"],
        "parentItemId": row["parent_item_id"],
        "origin": row["origin"],
        "visibility": row["visibility"],
        "shareSlug": row["share_slug"],
        "librarySystemKey": row["library_system_key"] or "",
        "tags": _loads(row["tags_json"], []),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def get_active_version_number(db: Session, item_id: str) -> int:
    row = db.execute(
        text(
            "SELECT v.version FROM creative_item_versions v "
            "JOIN creative_items i ON i.active_version_id = v.id "
            "WHERE i.id = :id"
        ),
        {"id": item_id},
    ).mappings().first()
    return int(row["version"]) if row else 1


def insert_item(
    db: Session,
    *,
    kind: str,
    name: str,
    slug: str,
    scope: str,
    intent: dict[str, Any],
    provider_mappings: dict[str, Any] | None = None,
    compatibility: dict[str, Any] | None = None,
    category: str = "",
    subcategory: str = "",
    description: str = "",
    project_id: str | None = None,
    scene_id: str | None = None,
    shot_ref: str | None = None,
    owner_user_id: str | None = None,
    parent_item_id: str | None = None,
    origin: str = "local",
    visibility: str = "private",
    library_system_key: str = "",
    tags: list[str] | None = None,
    lifecycle: str = "draft",
    approval_state: str = "draft",
) -> dict[str, Any]:
    item_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    now = _now()
    db.execute(
        text(
            "INSERT INTO creative_items ("
            "id, kind, category, subcategory, scope, owner_user_id, project_id, scene_id, shot_ref, "
            "name, slug, description, intent_json, provider_mappings_json, compatibility_json, "
            "lifecycle, approval_state, active_version_id, parent_item_id, origin, visibility, "
            "share_slug, library_system_key, tags_json, created_at, updated_at"
            ") VALUES ("
            ":id, :kind, :category, :subcategory, :scope, :owner_user_id, :project_id, :scene_id, :shot_ref, "
            ":name, :slug, :description, :intent_json, :provider_mappings_json, :compatibility_json, "
            ":lifecycle, :approval_state, :active_version_id, :parent_item_id, :origin, :visibility, "
            ":share_slug, :library_system_key, :tags_json, :created_at, :updated_at)"
        ),
        {
            "id": item_id,
            "kind": kind,
            "category": category,
            "subcategory": subcategory,
            "scope": scope,
            "owner_user_id": owner_user_id,
            "project_id": project_id,
            "scene_id": scene_id,
            "shot_ref": shot_ref,
            "name": name,
            "slug": slug,
            "description": description,
            "intent_json": _dumps(intent),
            "provider_mappings_json": _dumps(provider_mappings or {}),
            "compatibility_json": _dumps(compatibility or {}),
            "lifecycle": lifecycle,
            "approval_state": approval_state,
            "active_version_id": version_id,
            "parent_item_id": parent_item_id,
            "origin": origin,
            "visibility": visibility,
            "share_slug": None,
            "library_system_key": library_system_key,
            "tags_json": _dumps(tags or []),
            "created_at": now,
            "updated_at": now,
        },
    )
    db.execute(
        text(
            "INSERT INTO creative_item_versions ("
            "id, item_id, version, intent_json, provider_mappings_json, compatibility_json, "
            "changelog, created_at, created_by"
            ") VALUES ("
            ":id, :item_id, 1, :intent_json, :provider_mappings_json, :compatibility_json, "
            ":changelog, :created_at, :created_by)"
        ),
        {
            "id": version_id,
            "item_id": item_id,
            "intent_json": _dumps(intent),
            "provider_mappings_json": _dumps(provider_mappings or {}),
            "compatibility_json": _dumps(compatibility or {}),
            "changelog": "initial",
            "created_at": now,
            "created_by": owner_user_id,
        },
    )
    db.commit()
    return get_item(db, item_id)  # type: ignore[return-value]


def get_item(db: Session, item_id: str) -> Optional[dict[str, Any]]:
    row = db.execute(
        text("SELECT * FROM creative_items WHERE id = :id"),
        {"id": item_id},
    ).mappings().first()
    if not row:
        return None
    version = get_active_version_number(db, item_id)
    return row_to_item(row, version)


def list_items(
    db: Session,
    *,
    project_id: str | None = None,
    kind: str | None = None,
    scope: str | None = None,
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: dict[str, Any] = {}
    if project_id:
        clauses.append("project_id = :project_id")
        params["project_id"] = project_id
    if kind:
        clauses.append("kind = :kind")
        params["kind"] = kind
    if scope:
        clauses.append("scope = :scope")
        params["scope"] = scope
    rows = db.execute(
        text(f"SELECT * FROM creative_items WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC"),
        params,
    ).mappings().all()
    return [row_to_item(r, get_active_version_number(db, r["id"])) for r in rows]


def create_version(
    db: Session,
    item_id: str,
    *,
    intent: dict[str, Any],
    provider_mappings: dict[str, Any] | None = None,
    compatibility: dict[str, Any] | None = None,
    changelog: str = "",
    created_by: str | None = None,
    lifecycle: str | None = None,
    approval_state: str | None = None,
) -> dict[str, Any]:
    row = db.execute(
        text("SELECT * FROM creative_items WHERE id = :id"),
        {"id": item_id},
    ).mappings().first()
    if not row:
        raise KeyError(item_id)
    max_v = db.execute(
        text("SELECT COALESCE(MAX(version), 0) AS m FROM creative_item_versions WHERE item_id = :id"),
        {"id": item_id},
    ).mappings().first()
    next_v = int(max_v["m"] if max_v else 0) + 1
    version_id = str(uuid.uuid4())
    now = _now()
    db.execute(
        text(
            "INSERT INTO creative_item_versions ("
            "id, item_id, version, intent_json, provider_mappings_json, compatibility_json, "
            "changelog, created_at, created_by"
            ") VALUES ("
            ":id, :item_id, :version, :intent_json, :provider_mappings_json, :compatibility_json, "
            ":changelog, :created_at, :created_by)"
        ),
        {
            "id": version_id,
            "item_id": item_id,
            "version": next_v,
            "intent_json": _dumps(intent),
            "provider_mappings_json": _dumps(provider_mappings or {}),
            "compatibility_json": _dumps(compatibility or {}),
            "changelog": changelog,
            "created_at": now,
            "created_by": created_by,
        },
    )
    db.execute(
        text(
            "UPDATE creative_items SET intent_json = :intent_json, "
            "provider_mappings_json = :provider_mappings_json, compatibility_json = :compatibility_json, "
            "active_version_id = :active_version_id, lifecycle = :lifecycle, "
            "approval_state = :approval_state, updated_at = :updated_at WHERE id = :id"
        ),
        {
            "intent_json": _dumps(intent),
            "provider_mappings_json": _dumps(provider_mappings or {}),
            "compatibility_json": _dumps(compatibility or {}),
            "active_version_id": version_id,
            "lifecycle": lifecycle or row["lifecycle"],
            "approval_state": approval_state or row["approval_state"],
            "updated_at": now,
            "id": item_id,
        },
    )
    db.commit()
    return get_item(db, item_id)  # type: ignore[return-value]


def fork_item(
    db: Session,
    item_id: str,
    *,
    name: str | None = None,
    scope: str = "project",
    project_id: str | None = None,
) -> dict[str, Any]:
    src = get_item(db, item_id)
    if not src:
        raise KeyError(item_id)
    return insert_item(
        db,
        kind=src["kind"],
        name=name or f"{src['name']} (copy)",
        slug=f"{src['slug']}_fork_{uuid.uuid4().hex[:8]}",
        scope=scope,
        intent=dict(src["intent"]),
        provider_mappings=dict(src["providerMappings"]),
        compatibility=dict(src["compatibility"]),
        category=src["category"],
        subcategory=src["subcategory"],
        description=src["description"],
        project_id=project_id or src.get("projectId"),
        parent_item_id=item_id,
        origin="local",
        library_system_key=src.get("librarySystemKey") or "",
        tags=list(src.get("tags") or []),
        lifecycle="draft",
        approval_state="draft",
    )


def upsert_binding(
    db: Session,
    *,
    project_id: str,
    scope_level: str,
    slot: str,
    item_id: str,
    scene_id: str | None = None,
    shot_ref: str | None = None,
    mode: str = "override",
    version_pin: int | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    now = _now()
    binding_id = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO creative_bindings ("
            "id, project_id, scope_level, scene_id, shot_ref, slot, item_id, version_pin, mode, "
            "expected_version, created_at, updated_at"
            ") VALUES ("
            ":id, :project_id, :scope_level, :scene_id, :shot_ref, :slot, :item_id, :version_pin, :mode, "
            ":expected_version, :created_at, :updated_at)"
        ),
        {
            "id": binding_id,
            "project_id": project_id,
            "scope_level": scope_level,
            "scene_id": scene_id,
            "shot_ref": shot_ref,
            "slot": slot,
            "item_id": item_id,
            "version_pin": version_pin,
            "mode": mode,
            "expected_version": expected_version,
            "created_at": now,
            "updated_at": now,
        },
    )
    db.commit()
    return {
        "id": binding_id,
        "projectId": project_id,
        "scopeLevel": scope_level,
        "sceneId": scene_id,
        "shotRef": shot_ref,
        "slot": slot,
        "itemId": item_id,
        "versionPin": version_pin,
        "mode": mode,
        "expectedVersion": expected_version,
    }


def list_bindings(db: Session, project_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        text("SELECT * FROM creative_bindings WHERE project_id = :pid ORDER BY created_at"),
        {"pid": project_id},
    ).mappings().all()
    return [
        {
            "id": r["id"],
            "projectId": r["project_id"],
            "scopeLevel": r["scope_level"],
            "sceneId": r["scene_id"],
            "shotRef": r["shot_ref"],
            "slot": r["slot"],
            "itemId": r["item_id"],
            "versionPin": r["version_pin"],
            "mode": r["mode"],
            "expectedVersion": r["expected_version"],
        }
        for r in rows
    ]


def insert_production_unit(
    db: Session,
    *,
    project_id: str,
    kind: str,
    name: str,
    parent_id: str | None = None,
    unit_index: int = 0,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    unit_id = str(uuid.uuid4())
    now = _now()
    db.execute(
        text(
            "INSERT INTO production_units ("
            "id, project_id, kind, parent_id, name, unit_index, meta_json, created_at"
            ") VALUES ("
            ":id, :project_id, :kind, :parent_id, :name, :unit_index, :meta_json, :created_at)"
        ),
        {
            "id": unit_id,
            "project_id": project_id,
            "kind": kind,
            "parent_id": parent_id,
            "name": name,
            "unit_index": unit_index,
            "meta_json": _dumps(meta or {}),
            "created_at": now,
        },
    )
    return {
        "id": unit_id,
        "projectId": project_id,
        "kind": kind,
        "parentId": parent_id,
        "name": name,
        "index": unit_index,
        "meta": meta or {},
        "createdAt": now,
    }


def list_production_units(db: Session, project_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            "SELECT * FROM production_units WHERE project_id = :pid "
            "ORDER BY kind, unit_index, created_at"
        ),
        {"pid": project_id},
    ).mappings().all()
    return [
        {
            "id": r["id"],
            "projectId": r["project_id"],
            "kind": r["kind"],
            "parentId": r["parent_id"],
            "name": r["name"],
            "index": r["unit_index"],
            "meta": _loads(r["meta_json"], {}),
            "createdAt": r["created_at"],
        }
        for r in rows
    ]


def save_custom_project_type(
    db: Session,
    *,
    slug: str,
    display_name: str,
    profile: dict[str, Any],
    parent_selector: str | None = None,
    group: str = "custom",
) -> dict[str, Any]:
    now = _now()
    type_id = str(uuid.uuid4())
    existing = db.execute(
        text("SELECT id, version FROM project_type_definitions WHERE slug = :slug"),
        {"slug": slug},
    ).mappings().first()
    if existing:
        version = int(existing["version"] or 1) + 1
        db.execute(
            text(
                "UPDATE project_type_definitions SET display_name = :display_name, "
                "group_name = :group_name, parent_selector = :parent_selector, "
                "profile_json = :profile_json, version = :version, updated_at = :updated_at "
                "WHERE id = :id"
            ),
            {
                "display_name": display_name,
                "group_name": group,
                "parent_selector": parent_selector,
                "profile_json": _dumps(profile),
                "version": version,
                "updated_at": now,
                "id": existing["id"],
            },
        )
        db.commit()
        type_id = existing["id"]
    else:
        version = 1
        db.execute(
            text(
                "INSERT INTO project_type_definitions ("
                "id, slug, display_name, group_name, is_builtin, parent_selector, profile_json, "
                "version, lifecycle, origin, created_at, updated_at"
                ") VALUES ("
                ":id, :slug, :display_name, :group_name, 0, :parent_selector, :profile_json, "
                ":version, 'approved', 'local', :created_at, :updated_at)"
            ),
            {
                "id": type_id,
                "slug": slug,
                "display_name": display_name,
                "group_name": group,
                "parent_selector": parent_selector,
                "profile_json": _dumps(profile),
                "version": version,
                "created_at": now,
                "updated_at": now,
            },
        )
        db.commit()
    return {
        "id": type_id,
        "slug": slug,
        "displayName": display_name,
        "group": group,
        "isBuiltin": False,
        "parentSelector": parent_selector,
        "profile": profile,
        "version": version,
        "lifecycle": "approved",
        "origin": "local",
        "primarySelector": False,
    }


def get_custom_project_type(db: Session, slug: str) -> Optional[dict[str, Any]]:
    row = db.execute(
        text("SELECT * FROM project_type_definitions WHERE slug = :slug"),
        {"slug": slug},
    ).mappings().first()
    if not row:
        return None
    return {
        "id": row["id"],
        "slug": row["slug"],
        "displayName": row["display_name"],
        "group": row["group_name"],
        "isBuiltin": bool(row["is_builtin"]),
        "parentSelector": row["parent_selector"],
        "profile": _loads(row["profile_json"], {}),
        "version": row["version"],
        "lifecycle": row["lifecycle"],
        "origin": row["origin"],
        "primarySelector": False,
    }


def list_custom_project_types(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        text("SELECT * FROM project_type_definitions WHERE is_builtin = 0 ORDER BY display_name")
    ).mappings().all()
    return [
        {
            "id": r["id"],
            "slug": r["slug"],
            "displayName": r["display_name"],
            "group": r["group_name"],
            "isBuiltin": False,
            "parentSelector": r["parent_selector"],
            "profile": _loads(r["profile_json"], {}),
            "version": r["version"],
            "lifecycle": r["lifecycle"],
            "origin": r["origin"],
            "primarySelector": False,
        }
        for r in rows
    ]
