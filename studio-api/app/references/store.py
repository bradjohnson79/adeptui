"""Project-scoped persistence for reference ingredients, sheets, and presets."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def project_refs_root(project_id: str) -> Path:
    root = settings.data_dir / "projects" / project_id / "references"
    root.mkdir(parents=True, exist_ok=True)
    (root / "sheets").mkdir(exist_ok=True)
    return root


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_ingredients(project_id: str) -> list[dict[str, Any]]:
    data = _read_json(project_refs_root(project_id) / "ingredients.json", {"items": []})
    return list(data.get("items") or [])


def save_ingredients(project_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    path = project_refs_root(project_id) / "ingredients.json"
    _write_json(path, {"items": items, "updated_at": _now()})
    return items


def upsert_ingredient(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    items = list_ingredients(project_id)
    ing_id = str(payload.get("id") or uuid.uuid4())
    row = {
        "id": ing_id,
        "asset_id": str(payload.get("asset_id") or ""),
        "role": str(payload.get("role") or "other"),
        "subject_name": str(payload.get("subject_name") or payload.get("label") or ""),
        "description": str(payload.get("description") or ""),
        "priority": str(payload.get("priority") or "primary"),
        "include": bool(payload.get("include", True)),
        "crop_preference": str(payload.get("crop_preference") or "contain"),
        "label": str(payload.get("label") or payload.get("subject_name") or ""),
        "updated_at": _now(),
    }
    out = []
    replaced = False
    for item in items:
        if item.get("id") == ing_id:
            out.append({**item, **row})
            replaced = True
        else:
            out.append(item)
    if not replaced:
        row["created_at"] = _now()
        out.append(row)
    save_ingredients(project_id, out)
    return row if not replaced else next(i for i in out if i["id"] == ing_id)


def get_sheet(project_id: str, sheet_id: str) -> dict[str, Any] | None:
    path = project_refs_root(project_id) / "sheets" / f"{sheet_id}.json"
    if not path.is_file():
        return None
    return _read_json(path, None)


def save_sheet(project_id: str, sheet: dict[str, Any]) -> dict[str, Any]:
    sheet_id = str(sheet.get("id") or uuid.uuid4())
    sheet = {**sheet, "id": sheet_id, "updated_at": _now()}
    if "created_at" not in sheet:
        sheet["created_at"] = _now()
    path = project_refs_root(project_id) / "sheets" / f"{sheet_id}.json"
    _write_json(path, sheet)
    index_path = project_refs_root(project_id) / "sheets_index.json"
    index = _read_json(index_path, {"items": []})
    items = [i for i in (index.get("items") or []) if i.get("id") != sheet_id]
    items.insert(
        0,
        {
            "id": sheet_id,
            "version": sheet.get("version"),
            "layout": sheet.get("layout"),
            "updated_at": sheet["updated_at"],
        },
    )
    _write_json(index_path, {"items": items})
    return sheet


def list_presets(project_id: str) -> list[dict[str, Any]]:
    data = _read_json(project_refs_root(project_id) / "presets.json", {"items": []})
    return list(data.get("items") or [])


def save_preset(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    items = list_presets(project_id)
    preset_id = str(payload.get("id") or uuid.uuid4())
    now = _now()
    row = {
        "id": preset_id,
        "project_id": project_id,
        "name": str(payload.get("name") or "Untitled continuity"),
        "model_family": "ltx-2.3",
        "reference_method": "ingredients_ic_lora",
        "reference_sheet_asset_id": payload.get("reference_sheet_asset_id"),
        "sheet_id": payload.get("sheet_id"),
        "source_reference_ids": list(payload.get("source_reference_ids") or []),
        "subjects": list(payload.get("subjects") or []),
        "strength_preset": str(payload.get("strength_preset") or "balanced"),
        "strength_value": float(payload.get("strength_value") or 1.4),
        "created_at": next((i.get("created_at") for i in items if i.get("id") == preset_id), now),
        "updated_at": now,
    }
    if payload.get("reused_from"):
        row["reused_from"] = payload["reused_from"]
    out = [i for i in items if i.get("id") != preset_id]
    out.insert(0, row)
    _write_json(project_refs_root(project_id) / "presets.json", {"items": out})
    return row


def get_preset(project_id: str, preset_id: str) -> dict[str, Any] | None:
    for item in list_presets(project_id):
        if item.get("id") == preset_id:
            return item
    return None


def reuse_preset(project_id: str, preset_id: str) -> dict[str, Any]:
    preset = get_preset(project_id, preset_id)
    if not preset:
        raise KeyError(preset_id)
    clone = {
        **preset,
        "id": str(uuid.uuid4()),
        "name": f"{preset.get('name') or 'Preset'} (reuse)",
        "reused_from": preset_id,
        "created_at": _now(),
        "updated_at": _now(),
    }
    return save_preset(project_id, clone)
