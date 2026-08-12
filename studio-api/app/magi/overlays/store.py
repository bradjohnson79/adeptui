"""Overlay composition persistence under data/image_product/{projectId}/overlays/."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ...image_product.store import project_dir, read_json, write_json
from .validate import validate_composition


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _index_name() -> str:
    return "overlays/compositions_index.json"


def list_compositions(project_id: str) -> list[dict[str, Any]]:
    idx = read_json(project_id, _index_name(), {"items": []})
    return list(idx.get("items") or [])


def get_composition(project_id: str, composition_id: str) -> dict[str, Any] | None:
    data = read_json(project_id, f"overlays/{composition_id}.json", None)
    if not isinstance(data, dict):
        return None
    if data.get("projectId") != project_id:
        return None
    return data


def get_or_create_for_asset(
    project_id: str,
    *,
    source_asset_id: str | None,
    canvas_width: int = 1920,
    canvas_height: int = 1080,
) -> dict[str, Any]:
    items = list_compositions(project_id)
    if source_asset_id:
        for it in items:
            if it.get("sourceAssetId") == source_asset_id:
                full = get_composition(project_id, it["compositionId"])
                if full:
                    return full
    return save_composition(
        project_id,
        {
            "schemaVersion": 1,
            "compositionId": str(uuid.uuid4()),
            "projectId": project_id,
            "sourceAssetId": source_asset_id,
            "canvasWidth": canvas_width,
            "canvasHeight": canvas_height,
            "overlays": [],
            "safeAreaEnabled": True,
            "createdAt": _now(),
            "updatedAt": _now(),
        },
    )


def save_composition(project_id: str, composition: dict[str, Any]) -> dict[str, Any]:
    comp = dict(composition)
    comp["projectId"] = project_id
    comp.setdefault("schemaVersion", 1)
    comp.setdefault("compositionId", str(uuid.uuid4()))
    comp.setdefault("overlays", [])
    comp.setdefault("safeAreaEnabled", True)
    comp.setdefault("createdAt", _now())
    comp["updatedAt"] = _now()
    v = validate_composition(comp, project_id=project_id)
    if not v.get("ok"):
        raise ValueError("; ".join(v.get("errors") or ["validation failed"]))
    cid = str(comp["compositionId"])
    overlays_dir = project_dir(project_id) / "overlays"
    overlays_dir.mkdir(parents=True, exist_ok=True)
    write_json(project_id, f"overlays/{cid}.json", comp)
    idx = read_json(project_id, _index_name(), {"items": []})
    items = [i for i in (idx.get("items") or []) if i.get("compositionId") != cid]
    items.insert(
        0,
        {
            "compositionId": cid,
            "sourceAssetId": comp.get("sourceAssetId"),
            "updatedAt": comp["updatedAt"],
            "overlayCount": len(comp.get("overlays") or []),
        },
    )
    write_json(project_id, _index_name(), {"items": items})
    return comp
