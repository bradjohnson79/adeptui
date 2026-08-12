"""Read-only adapter: global profile_items camera/motion → unified intent preview."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session


def _parse(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def preview_profile_item(db: Session, profile_id: str) -> dict[str, Any]:
    item = None
    try:
        from ...profiles import ProfileItem

        row = db.get(ProfileItem, profile_id)
        if row:
            item = {
                "id": row.id,
                "kind": row.kind,
                "name": row.name,
                "data": _parse(row.data_json),
            }
    except Exception:
        try:
            from sqlalchemy import text

            row = db.execute(
                text("SELECT id, kind, name, data_json FROM profile_items WHERE id = :id"),
                {"id": profile_id},
            ).mappings().first()
            if row:
                item = {
                    "id": row["id"],
                    "kind": row["kind"],
                    "name": row["name"],
                    "data": _parse(row["data_json"]),
                }
        except Exception:
            item = None

    if not item:
        return {
            "intent": {},
            "providerMappings": {},
            "source": {"system": "profile_items", "id": profile_id, "version": None},
            "gaps": ["not_found"],
            "needsClarification": True,
        }

    data = item.get("data") if isinstance(item.get("data"), dict) else _parse(item.get("data_json"))
    gaps: list[str] = []
    if not data:
        gaps.append("empty_data_json")
    kind = str(item.get("kind") or "")
    intent: dict[str, Any] = {"kind": kind, "raw": data}
    if kind == "camera_preset":
        intent["camera"] = data
    elif kind == "motion_preset":
        intent["motion"] = data
    return {
        "intent": intent,
        "providerMappings": {},
        "source": {
            "system": "profile_items",
            "id": profile_id,
            "version": item.get("version"),
            "name": item.get("name"),
            "kind": kind,
        },
        "gaps": gaps,
        "needsClarification": bool(gaps),
        "note": "Read-only preview. Not a native creative_item.",
    }
