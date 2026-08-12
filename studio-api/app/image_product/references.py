"""ReferenceAsset CRUD store + role bridging (M42 W3)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..image_runtime.reference_assets import REFERENCE_TYPES, ReferenceAsset
from .store import read_json, write_json

_ROLE_MAP = {
    "character": "character",
    "face": "character",
    "clothing": "wardrobe",
    "wardrobe": "wardrobe",
    "pose": "pose",
    "env": "environment",
    "environment": "environment",
    "prop": "prop",
    "lighting": "lighting",
    "composition": "composition",
    "style": "style",
    "camera": "composition",
    "vehicle": "vehicle",
    "palette": "palette",
}


def _load(project_id: str) -> list[dict[str, Any]]:
    data = read_json(project_id, "references.json", {"references": []})
    return list(data.get("references") or [])


def _save(project_id: str, refs: list[dict[str, Any]]) -> None:
    write_json(project_id, "references.json", {"references": refs})


def list_references(project_id: str, *, type: str | None = None) -> list[dict[str, Any]]:
    refs = _load(project_id)
    if type:
        refs = [r for r in refs if r.get("type") == type]
    return refs


def get_reference(project_id: str, reference_id: str) -> dict[str, Any] | None:
    for r in _load(project_id):
        if r.get("referenceId") == reference_id:
            return r
    return None


def create_reference(
    project_id: str,
    *,
    type: str,
    display_name: str = "",
    source_images: list[str] | None = None,
    continuity_tags: list[str] | None = None,
    identity_registry_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rtype = type if type in REFERENCE_TYPES else _ROLE_MAP.get(type, "style")
    if rtype not in REFERENCE_TYPES:
        rtype = "style"
    ref = ReferenceAsset(
        type=rtype,  # type: ignore[arg-type]
        displayName=display_name or rtype,
        projectId=project_id,
        sourceImages=list(source_images or []),
        continuityTags=list(continuity_tags or []),
        identityRegistryRef=identity_registry_ref,
        metadata=dict(metadata or {}),
    )
    refs = _load(project_id)
    d = ref.to_dict()
    refs.append(d)
    _save(project_id, refs)
    return d


def attach_asset_as_reference(
    project_id: str,
    *,
    asset_id: str,
    role: str = "character",
    display_name: str = "",
    identity_registry_ref: str | None = None,
) -> dict[str, Any]:
    rtype = _ROLE_MAP.get(role.lower(), "style")
    return create_reference(
        project_id,
        type=rtype,
        display_name=display_name or f"{rtype}:{asset_id[:8]}",
        source_images=[asset_id],
        identity_registry_ref=identity_registry_ref,
        metadata={"role": role, "assetId": asset_id},
    )


def bridge_from_asset(
    project_id: str,
    *,
    asset_id: str,
    role: str = "style",
    display_name: str = "",
    identity_registry_ref: str | None = None,
) -> dict[str, Any]:
    """Bridge library / character_identity asset into ReferenceAsset store."""
    if not asset_id:
        raise ValueError("assetId required")
    for r in _load(project_id):
        meta = r.get("metadata") or {}
        if meta.get("assetId") == asset_id and meta.get("role") == role:
            return r
    return attach_asset_as_reference(
        project_id,
        asset_id=asset_id,
        role=role,
        display_name=display_name,
        identity_registry_ref=identity_registry_ref,
    )


def update_reference(project_id: str, reference_id: str, body: dict[str, Any]) -> dict[str, Any] | None:
    refs = _load(project_id)
    for i, r in enumerate(refs):
        if r.get("referenceId") != reference_id:
            continue
        for key in ("displayName", "type", "sourceImages", "continuityTags", "identityRegistryRef", "metadata"):
            if key in body:
                r[key] = body[key]
        refs[i] = r
        _save(project_id, refs)
        return r
    return None


def normalize_ui_refs(project_id: str, refs: list[dict[str, Any]] | None) -> list[str]:
    """Convert UI refs [{assetId, role}] into ReferenceAsset ids (create if needed)."""
    out: list[str] = []
    for item in refs or []:
        if isinstance(item, str):
            out.append(item)
            continue
        asset_id = str(item.get("assetId") or item.get("asset_id") or "")
        role = str(item.get("role") or "style")
        if not asset_id:
            continue
        # Reuse existing ref for same asset+role
        existing = None
        for r in _load(project_id):
            meta = r.get("metadata") or {}
            if meta.get("assetId") == asset_id and meta.get("role") == role:
                existing = r
                break
        if existing:
            out.append(existing["referenceId"])
        else:
            created = attach_asset_as_reference(project_id, asset_id=asset_id, role=role)
            out.append(created["referenceId"])
    return out


def link_relationship(
    project_id: str,
    reference_id: str,
    *,
    related_id: str,
    relation: str = "derived_from",
) -> dict[str, Any] | None:
    refs = _load(project_id)
    for i, r in enumerate(refs):
        if r.get("referenceId") != reference_id:
            continue
        rels = list(r.get("relationships") or [])
        rels.append({"relatedId": related_id, "relation": relation})
        r["relationships"] = rels
        refs[i] = r
        _save(project_id, refs)
        return r
    return None


def delete_reference(project_id: str, reference_id: str) -> bool:
    refs = _load(project_id)
    before = len(refs)
    refs = [r for r in refs if r.get("referenceId") != reference_id]
    _save(project_id, refs)
    return len(refs) < before
