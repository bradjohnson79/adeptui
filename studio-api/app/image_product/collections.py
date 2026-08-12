"""Production Collections — named groups of assets per project (M42 W3)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .store import read_json, write_json

SEED_NAMES = [
    "Episode 1 Concepts",
    "Bridge References",
    "Costume Designs",
    "Approved Characters",
    "Marketing Artwork",
]


def list_collections(project_id: str) -> list[dict[str, Any]]:
    data = read_json(project_id, "collections.json", None)
    if data is None:
        # Seed empty named collections once
        seeded = [
            {"collectionId": f"col-{uuid4().hex[:8]}", "name": n, "assetIds": [], "metadata": {}}
            for n in SEED_NAMES
        ]
        write_json(project_id, "collections.json", {"collections": seeded})
        return seeded
    return list(data.get("collections") or [])


def get_collection(project_id: str, collection_id: str) -> dict[str, Any] | None:
    for c in list_collections(project_id):
        if c.get("collectionId") == collection_id:
            return c
    return None


def create_collection(project_id: str, name: str, asset_ids: list[str] | None = None) -> dict[str, Any]:
    data = {"collections": list_collections(project_id)}
    col = {
        "collectionId": f"col-{uuid4().hex[:10]}",
        "name": name or "Untitled Collection",
        "assetIds": list(asset_ids or []),
        "metadata": {},
    }
    data["collections"].append(col)
    write_json(project_id, "collections.json", data)
    return col


def update_collection(project_id: str, collection_id: str, body: dict[str, Any]) -> dict[str, Any] | None:
    data = {"collections": list_collections(project_id)}
    for i, c in enumerate(data["collections"]):
        if c.get("collectionId") != collection_id:
            continue
        if "name" in body:
            c["name"] = body["name"]
        if "assetIds" in body:
            c["assetIds"] = list(body["assetIds"] or [])
        if "metadata" in body and isinstance(body["metadata"], dict):
            c.setdefault("metadata", {}).update(body["metadata"])
        data["collections"][i] = c
        write_json(project_id, "collections.json", data)
        return c
    return None


def delete_collection(project_id: str, collection_id: str) -> bool:
    data = {"collections": list_collections(project_id)}
    before = len(data["collections"])
    data["collections"] = [c for c in data["collections"] if c.get("collectionId") != collection_id]
    write_json(project_id, "collections.json", data)
    return len(data["collections"]) < before


def add_assets(project_id: str, collection_id: str, asset_ids: list[str]) -> dict[str, Any] | None:
    col = get_collection(project_id, collection_id)
    if not col:
        return None
    ids = list(dict.fromkeys(list(col.get("assetIds") or []) + list(asset_ids)))
    return update_collection(project_id, collection_id, {"assetIds": ids})


def remove_assets(project_id: str, collection_id: str, asset_ids: list[str]) -> dict[str, Any] | None:
    col = get_collection(project_id, collection_id)
    if not col:
        return None
    drop = set(asset_ids)
    ids = [a for a in (col.get("assetIds") or []) if a not in drop]
    return update_collection(project_id, collection_id, {"assetIds": ids})
