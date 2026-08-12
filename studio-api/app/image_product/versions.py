"""Non-destructive edit version graph (M42 W4)."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .store import read_json, write_json

_VERSIONS_FILE = "edit_versions.json"

_VALID_STATES = {
    "Draft",
    "PendingReview",
    "Approved",
    "Rejected",
    "ProductionMaster",
    "Archived",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(project_id: str) -> dict[str, Any]:
    return read_json(project_id, _VERSIONS_FILE, {"versions": [], "roots": []})


def _save(project_id: str, data: dict[str, Any]) -> None:
    write_json(project_id, _VERSIONS_FILE, data)


def create_version(
    project_id: str,
    *,
    source_asset_id: str,
    parent_version_id: str | None = None,
    image_edit_intent_id: str | None = None,
    output_asset_id: str | None = None,
    name: str = "Edit",
    state: str = "Draft",
) -> dict[str, Any]:
    if state not in _VALID_STATES:
        raise ValueError(f"Invalid state: {state}")
    data = _load(project_id)
    version_id = f"ver-{uuid4().hex[:12]}"
    node = {
        "versionId": version_id,
        "projectId": project_id,
        "sourceAssetId": source_asset_id,
        "parentVersionId": parent_version_id,
        "imageEditIntentId": image_edit_intent_id,
        "outputAssetId": output_asset_id,
        "name": name,
        "state": state,
        "reviewNotes": [],
        "createdAt": _now(),
        "modifiedAt": _now(),
        "children": [],
    }
    data.setdefault("versions", []).append(node)
    if parent_version_id:
        for v in data["versions"]:
            if v.get("versionId") == parent_version_id:
                v.setdefault("children", []).append(version_id)
                v["modifiedAt"] = _now()
                break
    else:
        data.setdefault("roots", []).append(version_id)
    _save(project_id, data)
    return node


def branch(
    project_id: str,
    version_id: str,
    *,
    name: str = "Branch",
    state: str = "Draft",
) -> dict[str, Any]:
    data = _load(project_id)
    parent = next((v for v in data.get("versions") or [] if v.get("versionId") == version_id), None)
    if not parent:
        raise ValueError(f"Version not found: {version_id}")
    return create_version(
        project_id,
        source_asset_id=str(parent.get("sourceAssetId") or ""),
        parent_version_id=version_id,
        image_edit_intent_id=parent.get("imageEditIntentId"),
        name=name,
        state=state,
    )


def set_state(project_id: str, version_id: str, state: str) -> dict[str, Any] | None:
    if state not in _VALID_STATES:
        raise ValueError(f"Invalid state: {state}")
    data = _load(project_id)
    for v in data.get("versions") or []:
        if v.get("versionId") == version_id:
            v["state"] = state
            v["modifiedAt"] = _now()
            _save(project_id, data)
            return deepcopy(v)
    return None


def add_review_note(
    project_id: str,
    version_id: str,
    *,
    author: str,
    text: str,
) -> dict[str, Any] | None:
    data = _load(project_id)
    for v in data.get("versions") or []:
        if v.get("versionId") == version_id:
            note = {"author": author, "text": text, "createdAt": _now()}
            v.setdefault("reviewNotes", []).append(note)
            v["modifiedAt"] = _now()
            _save(project_id, data)
            return deepcopy(v)
    return None


def mark_master(project_id: str, version_id: str) -> dict[str, Any] | None:
    """Promote version to ProductionMaster without erasing prior masters."""
    data = _load(project_id)
    target = None
    for v in data.get("versions") or []:
        if v.get("versionId") == version_id:
            target = v
            break
    if not target:
        return None
    target["state"] = "ProductionMaster"
    target["modifiedAt"] = _now()
    target["promotedAt"] = _now()
    _save(project_id, data)
    return deepcopy(target)


def get_tree(project_id: str) -> dict[str, Any]:
    data = _load(project_id)
    versions = {v["versionId"]: deepcopy(v) for v in (data.get("versions") or [])}
    roots = list(data.get("roots") or [])

    def _build(vid: str) -> dict[str, Any]:
        node = versions.get(vid, {"versionId": vid})
        child_ids = node.get("children") or []
        node["childrenNodes"] = [_build(cid) for cid in child_ids]
        return node

    return {
        "projectId": project_id,
        "roots": [_build(r) for r in roots],
        "versions": list(versions.values()),
        "versionCount": len(versions),
    }


def get_version(project_id: str, version_id: str) -> dict[str, Any] | None:
    for v in _load(project_id).get("versions") or []:
        if v.get("versionId") == version_id:
            return deepcopy(v)
    return None
