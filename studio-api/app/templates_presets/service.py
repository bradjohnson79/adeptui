"""High-level Templates & Presets service facade."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from .catalog.seed_placeholders import list_system_items, system_items_by_slug
from .compatibility import compatibility_report
from .import_export import export_creative_item, import_creative_item
from .resolve import resolve_creative_plan
from .schema import CreativeBinding, CreativeItem
from . import store


def catalog(
    db: Session,
    *,
    kind: str | None = None,
    category: str | None = None,
    scope: str | None = None,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if scope in (None, "system"):
        for item in list_system_items(kind=kind, category=category):
            items.append(item.to_dict())
    if scope != "system":
        persisted = store.list_items(db, project_id=project_id, kind=kind, scope=scope)
        if category:
            persisted = [p for p in persisted if p.get("category") == category]
        items.extend(persisted)
    return items


def create_item(db: Session, body: dict[str, Any]) -> dict[str, Any]:
    item = store.insert_item(
        db,
        kind=str(body["kind"]),
        name=str(body["name"]),
        slug=str(body.get("slug") or body["name"]).lower().replace(" ", "_"),
        scope=str(body.get("scope") or "project"),
        intent=dict(body.get("intent") or {}),
        provider_mappings=dict(body.get("providerMappings") or body.get("provider_mappings") or {}),
        compatibility=dict(body.get("compatibility") or {}),
        category=str(body.get("category") or ""),
        subcategory=str(body.get("subcategory") or ""),
        description=str(body.get("description") or ""),
        project_id=body.get("projectId") or body.get("project_id"),
        scene_id=body.get("sceneId") or body.get("scene_id"),
        shot_ref=body.get("shotRef") or body.get("shot_ref"),
        owner_user_id=body.get("ownerUserId") or body.get("owner_user_id"),
        library_system_key=str(body.get("librarySystemKey") or body.get("library_system_key") or ""),
        tags=list(body.get("tags") or []),
        lifecycle=str(body.get("lifecycle") or "draft"),
        approval_state=str(body.get("approvalState") or body.get("approval_state") or "draft"),
    )
    item["compatibilityReport"] = compatibility_report(CreativeItem.from_dict(item))
    return item


def get_item(db: Session, item_id: str) -> Optional[dict[str, Any]]:
    if item_id.startswith("sys:") or item_id in system_items_by_slug():
        slug = item_id[4:] if item_id.startswith("sys:") else item_id
        item = system_items_by_slug().get(slug)
        return item.to_dict() if item else None
    return store.get_item(db, item_id)


def add_version(db: Session, item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    return store.create_version(
        db,
        item_id,
        intent=dict(body.get("intent") or {}),
        provider_mappings=dict(body.get("providerMappings") or {}),
        compatibility=dict(body.get("compatibility") or {}),
        changelog=str(body.get("changelog") or ""),
        lifecycle=body.get("lifecycle"),
        approval_state=body.get("approvalState") or body.get("approval_state"),
    )


def fork(db: Session, item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    # Allow forking system items into project scope without mutating system catalog.
    if item_id.startswith("sys:") or item_id in system_items_by_slug():
        slug = item_id[4:] if item_id.startswith("sys:") else item_id
        src = system_items_by_slug().get(slug)
        if not src:
            raise KeyError(item_id)
        return store.insert_item(
            db,
            kind=src.kind,
            name=str(body.get("name") or f"{src.name} (copy)"),
            slug=f"{src.slug}_fork",
            scope=str(body.get("scope") or "project"),
            intent=dict(src.intent),
            provider_mappings=dict(src.provider_mappings),
            compatibility=dict(src.compatibility),
            category=src.category,
            subcategory=src.subcategory,
            description=src.description,
            project_id=body.get("projectId") or body.get("project_id"),
            parent_item_id=src.id,
            library_system_key=src.library_system_key,
            tags=list(src.tags),
        )
    return store.fork_item(
        db,
        item_id,
        name=body.get("name"),
        scope=str(body.get("scope") or "project"),
        project_id=body.get("projectId") or body.get("project_id"),
    )


def approve_item(db: Session, item_id: str) -> dict[str, Any]:
    item = store.get_item(db, item_id)
    if not item:
        raise KeyError(item_id)
    return store.create_version(
        db,
        item_id,
        intent=item["intent"],
        provider_mappings=item["providerMappings"],
        compatibility=item["compatibility"],
        changelog="approved",
        lifecycle="approved",
        approval_state="approved",
    )


def export_item(db: Session, item_id: str) -> dict[str, Any]:
    data = get_item(db, item_id)
    if not data:
        raise KeyError(item_id)
    return export_creative_item(CreativeItem.from_dict(data))


def import_item(db: Session, package: dict[str, Any], *, project_id: str | None = None) -> dict[str, Any]:
    item, report = import_creative_item(package)
    created = store.insert_item(
        db,
        kind=item.kind,
        name=item.name,
        slug=item.slug,
        scope="project" if project_id else item.scope if item.scope != "system" else "user",
        intent=item.intent,
        provider_mappings=item.provider_mappings,
        compatibility=item.compatibility,
        category=item.category,
        subcategory=item.subcategory,
        description=item.description,
        project_id=project_id or item.project_id,
        origin="imported",
        library_system_key=item.library_system_key,
        tags=item.tags,
        lifecycle=item.lifecycle if item.lifecycle != "locked" else "approved",
        approval_state=item.approval_state,
    )
    created["compatibilityReport"] = report
    return created


def bind(db: Session, body: dict[str, Any]) -> dict[str, Any]:
    return store.upsert_binding(
        db,
        project_id=str(body["projectId"]),
        scope_level=str(body.get("scopeLevel") or "project"),
        slot=str(body["slot"]),
        item_id=str(body["itemId"]),
        scene_id=body.get("sceneId"),
        shot_ref=body.get("shotRef"),
        mode=str(body.get("mode") or "override"),
        version_pin=body.get("versionPin"),
        expected_version=body.get("expectedVersion"),
    )


def resolve(db: Session, body: dict[str, Any]) -> dict[str, Any]:
    project_id = str(body["projectId"])
    scene_id = body.get("sceneId")
    shot_ref = body.get("shotRef")
    bindings_raw = store.list_bindings(db, project_id)
    bindings = [
        CreativeBinding(
            id=b["id"],
            project_id=b["projectId"],
            scope_level=b["scopeLevel"],
            slot=b["slot"],
            item_id=b["itemId"],
            scene_id=b.get("sceneId"),
            shot_ref=b.get("shotRef"),
            version_pin=b.get("versionPin"),
            mode=b.get("mode") or "override",
            expected_version=b.get("expectedVersion"),
        )
        for b in bindings_raw
    ]
    project_items = {
        i["id"]: CreativeItem.from_dict(i)
        for i in store.list_items(db, project_id=project_id)
    }
    for i in list(project_items.values()):
        project_items[i.slug] = i
    plan = resolve_creative_plan(
        project_id=project_id,
        scene_id=scene_id,
        shot_ref=shot_ref,
        bindings=bindings,
        project_items=project_items,
        selections=dict(body.get("selections") or {}),
    )
    return plan.to_dict()
