"""Studio Project Library service — virtual taxonomy, lazy entity folders, asset assignment."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..db import Asset, Project
from .classify import ClassifyInput, classification_display_path, classify_asset
from .schema import AssetLibraryMeta, FolderNode, LIBRARY_SCHEMA_VERSION, LibraryState
from .taxonomy import (
    ENTITY_ID_FIELDS,
    ENTITY_ROOTS,
    SYSTEM_FOLDER_PREFIX,
    TAXONOMY_ROOT,
    TaxonomyNode,
    display_path_for_system_key,
    get_system_node,
    is_system_folder_id,
    system_folder_id,
    system_key_from_folder_id,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_settings(project: Project) -> dict[str, Any]:
    try:
        return json.loads(project.settings_json or "{}")
    except Exception:
        return {}


def _save_settings(db: Session, project: Project, settings: dict[str, Any]) -> None:
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    db.add(project)


def _library_state(settings: dict[str, Any]) -> LibraryState:
    return LibraryState.from_dict(settings.get("library"))


def _set_library_state(settings: dict[str, Any], state: LibraryState) -> None:
    settings["library"] = state.to_dict()


def init_project_library(db: Session, project: Project) -> LibraryState:
    """Record librarySchemaVersion on project create — no empty system folder rows."""
    settings = _load_settings(project)
    state = _library_state(settings)
    if "library" not in settings or state.schema_version < LIBRARY_SCHEMA_VERSION:
        state.schema_version = LIBRARY_SCHEMA_VERSION
        _set_library_state(settings, state)
        _save_settings(db, project, settings)
    return state


def migrate_project_library(db: Session, project_id: str) -> dict[str, Any]:
    """Non-destructive migration to current librarySchemaVersion."""
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("PROJECT_NOT_FOUND")

    settings = _load_settings(project)
    state = _library_state(settings)
    from_version = state.schema_version
    repairs: list[str] = []

    if from_version == 0:
        state.schema_version = LIBRARY_SCHEMA_VERSION
        repairs.append("initialized library schema")
    elif from_version < LIBRARY_SCHEMA_VERSION:
        # Future versions: add stepwise migrations here without deleting custom folders.
        state.schema_version = LIBRARY_SCHEMA_VERSION
        repairs.append(f"bumped schema {from_version} → {LIBRARY_SCHEMA_VERSION}")

    if from_version != state.schema_version:
        state.migration_log.append(
            {
                "from": from_version,
                "to": state.schema_version,
                "at": _now_iso(),
                "note": "; ".join(repairs) or "no-op",
            }
        )

    _set_library_state(settings, state)
    _save_settings(db, project, settings)
    db.commit()

    return {
        "projectId": project_id,
        "fromVersion": from_version,
        "toVersion": state.schema_version,
        "repairs": repairs,
        "folderCount": len(state.folders),
    }


def _build_system_tree(node: TaxonomyNode, parent_id: Optional[str] = None) -> Optional[FolderNode]:
    if node.system_key == "root":
        return FolderNode(
            folder_id="root",
            display_name=node.display_name,
            display_path="Project",
            is_system=True,
            is_renamable=False,
            is_deletable=False,
            children=[c for c in (_build_system_tree(ch, None) for ch in node.children) if c],
        )

    folder_id = system_folder_id(node.system_key)
    child_nodes: list[FolderNode] = []
    for child in node.children:
        if node.entity_container and child.entity_subfolder:
            continue
        built = _build_system_tree(child, folder_id)
        if built:
            child_nodes.append(built)

    return FolderNode(
        folder_id=folder_id,
        display_name=node.display_name,
        system_key=node.system_key,
        parent_folder_id=parent_id,
        display_path=display_path_for_system_key(node.system_key),
        is_system=True,
        is_renamable=node.renamable,
        is_deletable=node.deletable,
        entity_type=_entity_type_for_container(node),
        children=child_nodes,
    )


def _index_tree(node: FolderNode, out: dict[str, FolderNode]) -> None:
    out[node.folder_id] = node
    for child in node.children:
        _index_tree(child, out)


def _entity_type_for_container(node: TaxonomyNode) -> Optional[str]:
    for etype, root_key in ENTITY_ROOTS.items():
        if node.system_key == root_key:
            return etype
    return None


def _persisted_entity_folders(state: LibraryState) -> list[FolderNode]:
    return [FolderNode.from_dict(row) for row in state.folders.values()]


def get_tree(db: Session, project_id: str) -> dict[str, Any]:
    """Return virtual system taxonomy merged with persisted entity/custom folders."""
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("PROJECT_NOT_FOUND")

    migrate_project_library(db, project_id)
    settings = _load_settings(project)
    state = _library_state(settings)

    root = _build_system_tree(TAXONOMY_ROOT)
    if not root:
        root = FolderNode(folder_id="root", display_name="Project", is_system=True)

    by_id: dict[str, FolderNode] = {}
    _index_tree(root, by_id)
    entity_nodes = _persisted_entity_folders(state)

    for entity in entity_nodes:
        by_id[entity.folder_id] = entity
        parent_id = entity.parent_folder_id
        if parent_id and parent_id in by_id:
            by_id[parent_id].children.append(entity)

    return {
        "projectId": project_id,
        "librarySchemaVersion": state.schema_version,
        "folders": [c.to_dict() for c in root.children],
        "entityFolderCount": len(entity_nodes),
        "systemFolderCount": len(by_id) - len(entity_nodes),
    }


def ensure_entity_folder(
    db: Session,
    project_id: str,
    *,
    entity_type: str,
    entity_name: str,
    entity_id: Optional[str] = None,
    subfolder_system_key: Optional[str] = None,
) -> FolderNode:
    """Lazy-create an entity folder (e.g. Characters/Anadriya/Identity References)."""
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("PROJECT_NOT_FOUND")

    root_key = ENTITY_ROOTS.get(entity_type)
    if not root_key:
        raise ValueError(f"UNSUPPORTED_ENTITY_TYPE:{entity_type}")

    sub_key = subfolder_system_key or _default_subfolder(entity_type)
    if not get_system_node(sub_key):
        raise ValueError(f"UNKNOWN_SUBFOLDER:{sub_key}")

    settings = _load_settings(project)
    state = _library_state(settings)
    eid = entity_id or str(uuid.uuid4())

    entity_folder = _find_entity_folder(state, entity_type, eid, entity_name)
    if not entity_folder:
        container_id = system_folder_id(root_key)
        entity_folder_id = str(uuid.uuid4())
        entity_path = f"{display_path_for_system_key(root_key)}/{entity_name}"
        entity_folder = FolderNode(
            folder_id=entity_folder_id,
            display_name=entity_name,
            parent_folder_id=container_id,
            display_path=entity_path,
            is_system=False,
            is_renamable=True,
            is_deletable=False,
            entity_type=entity_type,
            entity_id=eid,
            entity_name=entity_name,
        )
        state.folders[entity_folder_id] = entity_folder.to_dict()

    subfolder = _find_entity_subfolder(state, entity_folder.folder_id, sub_key)
    if not subfolder:
        subfolder_id = str(uuid.uuid4())
        sub_name = get_system_node(sub_key).display_name if get_system_node(sub_key) else sub_key
        sub_path = f"{entity_folder.display_path}/{sub_name}"
        subfolder = FolderNode(
            folder_id=subfolder_id,
            display_name=sub_name,
            system_key=sub_key,
            parent_folder_id=entity_folder.folder_id,
            display_path=sub_path,
            is_system=False,
            is_renamable=False,
            is_deletable=False,
            entity_type=entity_type,
            entity_id=eid,
            entity_name=entity_name,
        )
        state.folders[subfolder_id] = subfolder.to_dict()

    _set_library_state(settings, state)
    _save_settings(db, project, settings)
    db.commit()
    return subfolder


def _default_subfolder(entity_type: str) -> str:
    defaults = {
        "character": "characters.identity_references",
        "prop": "props.references",
        "scene": "scenes.backgrounds",
    }
    return defaults[entity_type]


def _find_entity_folder(state: LibraryState, entity_type: str, entity_id: str, entity_name: str) -> Optional[FolderNode]:
    for row in state.folders.values():
        if row.get("entityType") == entity_type and (
            row.get("entityId") == entity_id or row.get("entityName") == entity_name
        ):
            if not row.get("systemKey"):
                return FolderNode.from_dict(row)
    return None


def _find_entity_subfolder(state: LibraryState, parent_id: str, system_key: str) -> Optional[FolderNode]:
    for row in state.folders.values():
        if row.get("parentFolderId") == parent_id and row.get("systemKey") == system_key:
            return FolderNode.from_dict(row)
    return None


def resolve_path(
    db: Session,
    project_id: str,
    *,
    folder_id: Optional[str] = None,
    system_key: Optional[str] = None,
) -> str:
    """Recalculate display libraryPath from authoritative folderId / systemKey."""
    if folder_id:
        if is_system_folder_id(folder_id):
            key = system_key_from_folder_id(folder_id)
            return display_path_for_system_key(key or "")
        project = db.get(Project, project_id)
        if project:
            state = _library_state(_load_settings(project))
            row = state.folders.get(folder_id)
            if row:
                return str(row.get("displayPath") or "")
    if system_key:
        project = db.get(Project, project_id)
        if project:
            state = _library_state(_load_settings(project))
            for row in state.folders.values():
                if row.get("systemKey") == system_key and row.get("entityName"):
                    return str(row.get("displayPath") or "")
        return display_path_for_system_key(system_key)
    return ""


def read_asset_library_meta(asset: Asset) -> AssetLibraryMeta:
    try:
        prompt_meta = json.loads(asset.prompt_meta_json or "{}")
    except Exception:
        prompt_meta = {}
    return AssetLibraryMeta.from_dict(prompt_meta.get("library"))


def write_asset_library_meta(asset: Asset, meta: AssetLibraryMeta) -> None:
    try:
        prompt_meta = json.loads(asset.prompt_meta_json or "{}")
    except Exception:
        prompt_meta = {}
    prompt_meta["library"] = meta.to_dict()
    asset.prompt_meta_json = json.dumps(prompt_meta, ensure_ascii=False)


def compute_content_hash(path: str | Path) -> Optional[str]:
    p = Path(path)
    if not p.is_file():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def find_duplicates_by_hash(db: Session, project_id: str, content_hash: str) -> list[Asset]:
    if not content_hash:
        return []
    matches: list[Asset] = []
    for asset in db.query(Asset).filter(Asset.project_id == project_id).all():
        meta = read_asset_library_meta(asset)
        if meta.content_hash == content_hash:
            matches.append(asset)
    return matches


def assign_asset(
    db: Session,
    asset: Asset,
    *,
    system_key: Optional[str] = None,
    folder_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_name: Optional[str] = None,
    entity_id: Optional[str] = None,
    classified_by: str = "auto",
    override: bool = False,
    hints: Optional[dict[str, Any]] = None,
) -> AssetLibraryMeta:
    """Classify and persist library metadata on an asset."""
    existing = read_asset_library_meta(asset)
    if existing.override and not override:
        return existing

    classify_hints = dict(hints or {})
    if system_key:
        classify_hints["systemKey"] = system_key

    classification = classify_asset(
        ClassifyInput(
            kind=asset.kind,
            tag=asset.tag,
            filename=asset.filename,
            hints=classify_hints,
        ),
        classified_by=classified_by,
    )

    target_key = system_key or classification.target_folder
    canonical_id = folder_id or system_folder_id(target_key)
    library_path = resolve_path(db, asset.project_id, folder_id=canonical_id, system_key=target_key)

    if entity_type and entity_name:
        sub_key = target_key
        sub_node = get_system_node(target_key)
        if not sub_node or not sub_node.entity_subfolder:
            sub_key = _default_subfolder(entity_type)
        folder = ensure_entity_folder(
            db,
            asset.project_id,
            entity_type=entity_type,
            entity_name=entity_name,
            entity_id=entity_id,
            subfolder_system_key=sub_key,
        )
        canonical_id = folder.folder_id
        library_path = folder.display_path
        target_key = folder.system_key or target_key

    content_hash = compute_content_hash(asset.path)

    entity_links: dict[str, Optional[str]] = {
        "character_id": entity_id if entity_type == "character" else None,
        "prop_id": entity_id if entity_type == "prop" else None,
        "scene_id": entity_id if entity_type == "scene" else None,
    }

    meta = AssetLibraryMeta(
        canonical_folder_id=canonical_id,
        folder_system_key=target_key,
        library_path=library_path or classification_display_path(classification),
        classification=classification,
        content_hash=content_hash,
        override=override,
        **entity_links,
    )
    write_asset_library_meta(asset, meta)
    db.add(asset)
    db.commit()
    return meta


def repair_library(db: Session, project_id: str) -> dict[str, Any]:
    """Non-destructive repair: refresh paths, reindex classifications, detect gaps."""
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("PROJECT_NOT_FOUND")

    migrate_project_library(db, project_id)
    settings = _load_settings(project)
    state = _library_state(settings)

    repaired_paths = 0
    reclassified = 0
    missing_refs = 0
    unclassified = 0
    broken_links = 0

    # Refresh persisted folder display paths
    for fid, row in list(state.folders.items()):
        parent_id = row.get("parentFolderId")
        name = row.get("displayName") or ""
        if parent_id and is_system_folder_id(parent_id):
            parent_key = system_key_from_folder_id(parent_id)
            base = display_path_for_system_key(parent_key or "")
            new_path = f"{base}/{name}" if base else name
        elif parent_id and parent_id in state.folders:
            parent_path = state.folders[parent_id].get("displayPath") or ""
            new_path = f"{parent_path}/{name}" if parent_path else name
        else:
            new_path = row.get("displayPath") or name
        if row.get("displayPath") != new_path:
            row["displayPath"] = new_path
            repaired_paths += 1

    assets = db.query(Asset).filter(Asset.project_id == project_id).all()
    for asset in assets:
        meta = read_asset_library_meta(asset)
        if not meta.folder_system_key and not meta.canonical_folder_id:
            unclassified += 1
            assign_asset(db, asset, classified_by="repair")
            reclassified += 1
            meta = read_asset_library_meta(asset)

        new_path = resolve_path(
            db,
            project_id,
            folder_id=meta.canonical_folder_id or None,
            system_key=meta.folder_system_key or None,
        )
        if new_path and meta.library_path != new_path:
            meta.library_path = new_path
            write_asset_library_meta(asset, meta)
            repaired_paths += 1

        if meta.canonical_folder_id and not is_system_folder_id(meta.canonical_folder_id):
            if meta.canonical_folder_id not in state.folders:
                missing_refs += 1

        for field_name, etype in (("character_id", "character"), ("prop_id", "prop"), ("scene_id", "scene")):
            eid = getattr(meta, field_name)
            if eid and not _find_entity_folder(state, etype, eid, ""):
                broken_links += 1

        if not meta.content_hash and asset.path:
            meta.content_hash = compute_content_hash(asset.path)
            write_asset_library_meta(asset, meta)

        db.add(asset)

    _set_library_state(settings, state)
    _save_settings(db, project, settings)
    db.commit()

    return {
        "projectId": project_id,
        "repairedPaths": repaired_paths,
        "reclassified": reclassified,
        "missingFolderRefs": missing_refs,
        "unclassifiedAssetCount": unclassified,
        "brokenEntityLinkCount": broken_links,
        "librarySchemaVersion": state.schema_version,
    }


def enrich_library_item(asset: Asset) -> dict[str, Any]:
    """Shape a library list row with authoritative + display fields."""
    meta = read_asset_library_meta(asset)
    return {
        "id": asset.id,
        "project_id": asset.project_id,
        "tag": asset.tag,
        "kind": asset.kind,
        "filename": asset.filename,
        "path": asset.path,
        "scope": getattr(asset, "scope", "project"),
        "labels_json": getattr(asset, "labels_json", "[]"),
        "prompt_meta_json": getattr(asset, "prompt_meta_json", "{}"),
        "parent_asset_id": getattr(asset, "parent_asset_id", None),
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "canonicalFolderId": meta.canonical_folder_id or None,
        "folderSystemKey": meta.folder_system_key or None,
        "libraryPath": meta.library_path or None,
        "classification": meta.classification.to_dict() if meta.folder_system_key or meta.canonical_folder_id else None,
        "characterId": meta.character_id,
        "propId": meta.prop_id,
        "sceneId": meta.scene_id,
        "contentHash": meta.content_hash,
    }


def filter_library_items(
    items: list[dict[str, Any]],
    *,
    folder_id: Optional[str] = None,
    system_key: Optional[str] = None,
) -> list[dict[str, Any]]:
    if folder_id:
        return [i for i in items if i.get("canonicalFolderId") == folder_id]
    if system_key:
        return [i for i in items if i.get("folderSystemKey") == system_key]
    return items


def build_folder_map(folders: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Flatten nested folder tree into folderId → display metadata map."""
    out: dict[str, dict[str, Any]] = {}

    def walk(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            fid = node.get("folderId")
            if fid:
                entry: dict[str, Any] = {
                    "folderId": fid,
                    "displayName": node.get("displayName"),
                    "displayPath": node.get("displayPath"),
                    "isSystem": node.get("isSystem"),
                }
                if node.get("systemKey"):
                    entry["systemKey"] = node["systemKey"]
                if node.get("entityType"):
                    entry["entityType"] = node["entityType"]
                if node.get("entityName"):
                    entry["entityName"] = node["entityName"]
                out[str(fid)] = entry
            walk(node.get("children") or [])

    walk(folders)
    return out


def get_library_response(
    db: Session,
    project_id: str,
    items: list[dict[str, Any]],
    *,
    folder_id: Optional[str] = None,
    system_key: Optional[str] = None,
) -> dict[str, Any]:
    """Shape full library payload: filtered items + virtual tree + folder map."""
    tree = get_tree(db, project_id)
    filtered = filter_library_items(items, folder_id=folder_id, system_key=system_key)
    return {
        "items": filtered,
        "tree": tree,
        "librarySchemaVersion": tree["librarySchemaVersion"],
        "folderMap": build_folder_map(tree["folders"]),
    }
