"""Co-Director Project Library awareness — folder map, resolve, retrieval, preflight."""

from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..asset_graph import search_assets
from ..db import Asset
from .schema import LIBRARY_SCHEMA_VERSION
from .service import (
    build_folder_map,
    ensure_entity_folder,
    enrich_library_item,
    get_tree,
    resolve_path,
)
from .taxonomy import (
    ENTITY_ROOTS,
    display_path_for_system_key,
    get_system_node,
    system_folder_id,
)

_PATH_SEP = re.compile(r"[/\\]")
_NL_PATH = re.compile(
    r"(?:put (?:this|it) in|store (?:this|it) in|save (?:this|it) (?:to|in)|move (?:this|it) to)\s+(.+?)(?:\.|$)",
    re.IGNORECASE,
)
_ENTITY_QUERY = re.compile(
    r"(?:find|search|locate|get)\s+(?:(character|prop|scene|audio|video|3d)\s+)?(.+)",
    re.IGNORECASE,
)


def _normalize_path(value: str) -> str:
    parts = [p.strip() for p in _PATH_SEP.split(value.strip()) if p.strip()]
    return "/".join(parts)


def get_folder_map_for_codirector(db: Session, project_id: str) -> dict[str, Any]:
    """Compact folder map + schema version for Co-Director session context."""
    tree = get_tree(db, project_id)
    folder_map = build_folder_map(tree["folders"])
    return {
        "projectId": project_id,
        "librarySchemaVersion": tree["librarySchemaVersion"],
        "systemFolderCount": tree["systemFolderCount"],
        "entityFolderCount": tree["entityFolderCount"],
        "folderMap": folder_map,
    }


def _match_folders(folder_map: dict[str, dict[str, Any]], *, path: str = "", query: str = "") -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    norm_path = _normalize_path(path) if path else ""
    norm_query = query.strip().lower()

    for entry in folder_map.values():
        display_path = str(entry.get("displayPath") or "")
        norm_display = _normalize_path(display_path)
        system_key = str(entry.get("systemKey") or "")
        display_name = str(entry.get("displayName") or "")
        entity_name = str(entry.get("entityName") or "")

        if norm_path:
            if norm_display.lower() == norm_path.lower() or norm_display.lower().endswith("/" + norm_path.lower()):
                candidates.append(entry)
            continue

        if not norm_query:
            continue

        haystacks = [
            norm_display.lower(),
            display_name.lower(),
            system_key.lower().replace(".", "/"),
            entity_name.lower(),
        ]
        if any(norm_query in h or h.endswith("/" + norm_query) for h in haystacks if h):
            candidates.append(entry)
        elif norm_query.replace(" ", "/") in norm_display.lower():
            candidates.append(entry)

    # De-dupe by folderId preserving order
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for entry in candidates:
        fid = str(entry.get("folderId") or "")
        if fid and fid not in seen:
            seen.add(fid)
            unique.append(entry)
    return unique


def resolve_library_location(
    db: Session,
    project_id: str,
    *,
    path: Optional[str] = None,
    system_key: Optional[str] = None,
    query: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve a display path, systemKey, or NL phrase to canonical folder metadata."""
    folder_ctx = get_folder_map_for_codirector(db, project_id)
    folder_map: dict[str, dict[str, Any]] = folder_ctx["folderMap"]

    extracted_path = path
    if query and not extracted_path and not system_key:
        m = _NL_PATH.search(query)
        if m:
            extracted_path = m.group(1).strip()

    if system_key:
        node = get_system_node(system_key)
        if not node:
            return {
                "resolved": False,
                "ambiguous": False,
                "reason": f"Unknown systemKey: {system_key}",
                "librarySchemaVersion": folder_ctx["librarySchemaVersion"],
            }
        fid = system_folder_id(system_key)
        entry = folder_map.get(fid) or {
            "folderId": fid,
            "displayName": node.display_name,
            "displayPath": display_path_for_system_key(system_key),
            "systemKey": system_key,
            "isSystem": True,
        }
        library_path = resolve_path(db, project_id, folder_id=fid, system_key=system_key)
        return {
            "resolved": True,
            "ambiguous": False,
            "match": {**entry, "libraryPath": library_path or entry.get("displayPath")},
            "librarySchemaVersion": folder_ctx["librarySchemaVersion"],
        }

    candidates = _match_folders(folder_map, path=extracted_path or "", query=query or "")
    if len(candidates) == 1:
        entry = candidates[0]
        fid = str(entry.get("folderId") or "")
        sk = entry.get("systemKey")
        library_path = resolve_path(db, project_id, folder_id=fid or None, system_key=str(sk) if sk else None)
        return {
            "resolved": True,
            "ambiguous": False,
            "match": {**entry, "libraryPath": library_path or entry.get("displayPath")},
            "librarySchemaVersion": folder_ctx["librarySchemaVersion"],
        }

    if len(candidates) > 1:
        enriched = []
        for entry in candidates[:12]:
            fid = str(entry.get("folderId") or "")
            sk = entry.get("systemKey")
            library_path = resolve_path(db, project_id, folder_id=fid or None, system_key=str(sk) if sk else None)
            enriched.append({**entry, "libraryPath": library_path or entry.get("displayPath")})
        return {
            "resolved": False,
            "ambiguous": True,
            "candidates": enriched,
            "reason": "Multiple folders match — filmmaker must choose.",
            "librarySchemaVersion": folder_ctx["librarySchemaVersion"],
        }

    return {
        "resolved": False,
        "ambiguous": False,
        "reason": "No matching folder found.",
        "librarySchemaVersion": folder_ctx["librarySchemaVersion"],
    }


def _parse_entity_query(query: str) -> tuple[Optional[str], str]:
    m = _ENTITY_QUERY.match(query.strip())
    if not m:
        return None, query.strip()
    entity_type = m.group(1).lower() if m.group(1) else None
    if entity_type == "3d":
        entity_type = None
    term = (m.group(2) or "").strip()
    return entity_type, term


def _asset_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    approval = str(item.get("approvalState") or "draft")
    approved_rank = 0 if approval == "approved" else 1
    canonical_rank = 0 if item.get("isCanonical") else 1
    version = int(item.get("version") or 1)
    created = str(item.get("created_at") or "")
    return (approved_rank, canonical_rank, -version, created)


def search_library_assets(
    db: Session,
    project_id: str,
    *,
    query: str,
    entity_type: Optional[str] = None,
    folder_id: Optional[str] = None,
    system_key: Optional[str] = None,
    limit: int = 12,
) -> dict[str, Any]:
    """Indexed retrieval with version/approval metadata and ambiguity reporting.

    - Approval truth comes from Asset.production_approval (see enrich_library_item /
      read_asset_library_meta) - approved assets rank first (CDX-064).
    - Global-scope assets promoted via promote_asset_global are discoverable from
      any project (CDX-065).
    - Retrieval pages through search_assets so older assets stay reachable instead of
      being cut off by the most-recent scan window (CDX-067).
    """
    parsed_type, term = _parse_entity_query(query)
    entity_type = entity_type or parsed_type
    search_q = term or query

    rows: list[Asset] = []
    page_size = 100
    max_scanned = 2000  # bounded pages; anything beyond is reachable via the paged API
    offset = 0
    while offset < max_scanned:
        page = search_assets(db, project_id, search_q, global_only=False, limit=page_size, offset=offset)
        if not page:
            break
        rows.extend(page)
        offset += page_size
        if len(page) < page_size:
            break

    items = [
        enrich_library_item(a)
        for a in rows
        if a.project_id == project_id or getattr(a, "scope", "project") == "global"
    ]

    if folder_id:
        items = [i for i in items if i.get("canonicalFolderId") == folder_id]
    if system_key:
        items = [i for i in items if i.get("folderSystemKey") == system_key]
    if entity_type:
        field = {"character": "characterId", "prop": "propId", "scene": "sceneId"}.get(entity_type)
        if field:
            items = [i for i in items if i.get(field) or entity_type in str(i.get("libraryPath") or "").lower()]

    items.sort(key=_asset_sort_key)
    limited = items[: max(1, min(limit, 50))]

    ambiguous = len(items) > 1 and len({i["id"] for i in items[:3]}) > 1
    choices: list[dict[str, Any]] = []
    if ambiguous:
        for item in items[:8]:
            choices.append(
                {
                    "assetId": item["id"],
                    "tag": item.get("tag"),
                    "kind": item.get("kind"),
                    "libraryPath": item.get("libraryPath"),
                    "approvalState": item.get("approvalState"),
                    "version": item.get("version"),
                    "isCanonical": item.get("isCanonical"),
                    "createdAt": item.get("created_at"),
                }
            )

    return {
        "projectId": project_id,
        "query": query,
        "totalMatches": len(items),
        "ambiguous": ambiguous,
        "choices": choices if ambiguous else [],
        "items": limited,
        "preferred": limited[0] if limited else None,
    }


def storage_preflight(
    db: Session,
    project_id: str,
    *,
    task: str,
    system_key: Optional[str] = None,
    path: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_name: Optional[str] = None,
    entity_id: Optional[str] = None,
    filename_hint: Optional[str] = None,
    classified_by: str = "codirector",
) -> dict[str, Any]:
    """Plan canonical storage location before generation (folderId/systemKey authority)."""
    from .classify import ClassifyInput, classify_asset

    resolved_key = system_key
    resolved_path = path
    canonical_folder_id: Optional[str] = None
    library_path = ""

    if path and not system_key:
        loc = resolve_library_location(db, project_id, path=path)
        if loc.get("resolved") and loc.get("match"):
            match = loc["match"]
            resolved_key = match.get("systemKey")
            canonical_folder_id = match.get("folderId")
            library_path = match.get("libraryPath") or match.get("displayPath") or ""
        elif loc.get("ambiguous"):
            return {
                "ready": False,
                "ambiguous": True,
                "candidates": loc.get("candidates") or [],
                "reason": loc.get("reason"),
            }

    if entity_type and entity_name:
        if entity_type not in ENTITY_ROOTS:
            return {"ready": False, "reason": f"Unsupported entityType: {entity_type}"}
        sub_key = resolved_key or None
        if sub_key:
            node = get_system_node(sub_key)
            if not node or not node.entity_subfolder:
                sub_key = None
        folder = ensure_entity_folder(
            db,
            project_id,
            entity_type=entity_type,
            entity_name=entity_name,
            entity_id=entity_id,
            subfolder_system_key=sub_key,
        )
        canonical_folder_id = folder.folder_id
        resolved_key = folder.system_key or resolved_key
        library_path = folder.display_path

    if not canonical_folder_id:
        if resolved_key:
            canonical_folder_id = system_folder_id(resolved_key)
            library_path = library_path or resolve_path(
                db, project_id, folder_id=canonical_folder_id, system_key=resolved_key
            )
        else:
            classification = classify_asset(
                ClassifyInput(kind="", tag=task, filename=filename_hint or "", hints={"task": task}),
                classified_by=classified_by,
            )
            resolved_key = classification.target_folder
            canonical_folder_id = system_folder_id(resolved_key)
            library_path = display_path_for_system_key(resolved_key)

    classification = classify_asset(
        ClassifyInput(
            kind="",
            tag=task,
            filename=filename_hint or "",
            hints={"systemKey": resolved_key, "reason": f"Co-Director preflight for {task}"},
        ),
        classified_by=classified_by,
    )

    expected_name = filename_hint or f"{task.replace(' ', '-').lower()}-v01"
    return {
        "ready": True,
        "ambiguous": False,
        "task": task,
        "canonicalFolderId": canonical_folder_id,
        "folderSystemKey": resolved_key,
        "targetPath": library_path,
        "expectedName": expected_name,
        "approvalState": "draft",
        "classification": classification.to_dict(),
        "entityType": entity_type,
        "entityName": entity_name,
        "entityId": entity_id,
        "librarySchemaVersion": get_folder_map_for_codirector(db, project_id)["librarySchemaVersion"],
    }


def link_bible_entity_folder(
    db: Session,
    project_id: str,
    *,
    entity_type: str,
    entity_name: str,
    entity_id: Optional[str] = None,
    subfolder_system_key: Optional[str] = None,
) -> dict[str, Any]:
    """Ensure a Bible entity has a lazy-created library folder."""
    folder = ensure_entity_folder(
        db,
        project_id,
        entity_type=entity_type,
        entity_name=entity_name,
        entity_id=entity_id,
        subfolder_system_key=subfolder_system_key,
    )
    return {
        "folderId": folder.folder_id,
        "displayPath": folder.display_path,
        "systemKey": folder.system_key,
        "entityType": entity_type,
        "entityName": entity_name,
        "entityId": folder.entity_id,
    }


def get_library_context(db: Session, project_id: str, *, recent_limit: int = 8) -> dict[str, Any]:
    """Compact session bundle: folder map, recent assets, schema version."""
    folder_ctx = get_folder_map_for_codirector(db, project_id)
    rows = (
        db.query(Asset)
        .filter(Asset.project_id == project_id)
        .order_by(Asset.created_at.desc())
        .limit(recent_limit)
        .all()
    )
    recent = [enrich_library_item(a) for a in rows]
    return {
        **folder_ctx,
        "recentAssets": recent,
    }
