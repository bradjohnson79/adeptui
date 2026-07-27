"""VisualThemeProfile persist + recommend + preview compare."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m213_tables
from .store import M213Store


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


DEFAULT_THEMES = (
    {
        "name": "Natural Photoreal",
        "palette": ["#c4b7a6", "#6b7c5a", "#2f3a3a"],
        "mood": "natural",
        "conditioningPasses": ["color_match", "grain_light"],
    },
    {
        "name": "Noir Night",
        "palette": ["#0d0d12", "#3a3a48", "#c9b896"],
        "mood": "noir",
        "conditioningPasses": ["contrast", "rim_light", "desaturate"],
    },
    {
        "name": "Anime Cel",
        "palette": ["#f2e9e4", "#5b8def", "#ef5b7a"],
        "mood": "stylized",
        "conditioningPasses": ["line_art", "flat_shade"],
    },
)


def recommend_themes(project_style: str | None = None) -> list[dict[str, Any]]:
    style = (project_style or "").lower()
    ranked = list(DEFAULT_THEMES)
    if "noir" in style or "night" in style:
        ranked = [DEFAULT_THEMES[1], DEFAULT_THEMES[0], DEFAULT_THEMES[2]]
    elif "anime" in style or "cel" in style:
        ranked = [DEFAULT_THEMES[2], DEFAULT_THEMES[0], DEFAULT_THEMES[1]]
    return [{**t, "recommended": i == 0} for i, t in enumerate(ranked)]


def persist_theme(
    db: Session,
    *,
    project_id: str,
    name: str,
    profile: dict[str, Any],
    environment_id: str | None = None,
    recommended: bool = False,
) -> dict[str, Any]:
    ensure_m213_tables()
    tid = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO m213_theme_profiles "
            "(id, project_id, environment_id, name, profile_json, recommended, approved, created_at, updated_at) "
            "VALUES (:id, :project_id, :environment_id, :name, :profile_json, :recommended, 0, :ts, :ts)"
        ),
        {
            "id": tid,
            "project_id": project_id,
            "environment_id": environment_id,
            "name": name,
            "profile_json": json.dumps(profile),
            "recommended": 1 if recommended else 0,
            "ts": _now(),
        },
    )
    db.commit()
    M213Store.log_capability(
        db,
        capability_id="ve.theme.translate",
        action="persist",
        project_id=project_id,
        payload={"themeId": tid},
    )
    return {"id": tid, "name": name, "profile": profile, "approved": False}


def preview_compare(theme_a: dict[str, Any], theme_b: dict[str, Any]) -> dict[str, Any]:
    passes_a = theme_a.get("conditioningPasses") or theme_a.get("profile", {}).get("conditioningPasses", [])
    passes_b = theme_b.get("conditioningPasses") or theme_b.get("profile", {}).get("conditioningPasses", [])
    return {
        "a": theme_a,
        "b": theme_b,
        "passDelta": {
            "onlyA": [p for p in passes_a if p not in passes_b],
            "onlyB": [p for p in passes_b if p not in passes_a],
            "shared": [p for p in passes_a if p in passes_b],
        },
        "note": "Conditioning pass sets prepared per theme; not all passes emit always.",
    }


def approve_theme(db: Session, *, theme_id: str, actor: str = "user", note: str = "") -> dict[str, Any]:
    ensure_m213_tables()
    row = db.execute(
        text("SELECT id, project_id FROM m213_theme_profiles WHERE id = :id"),
        {"id": theme_id},
    ).mappings().first()
    if not row:
        raise LookupError("theme not found")
    db.execute(
        text("UPDATE m213_theme_profiles SET approved = 1, updated_at = :ts WHERE id = :id"),
        {"id": theme_id, "ts": _now()},
    )
    db.commit()
    approval = M213Store.record_approval(
        db, project_id=row["project_id"], gate="theme", subject_id=theme_id, approved=True, actor=actor, note=note
    )
    return {"ok": True, "themeId": theme_id, "approved": True, "approval": approval}


def get_theme(db: Session, theme_id: str) -> Optional[dict[str, Any]]:
    ensure_m213_tables()
    row = db.execute(
        text(
            "SELECT id, project_id, environment_id, name, profile_json, recommended, approved, created_at "
            "FROM m213_theme_profiles WHERE id = :id"
        ),
        {"id": theme_id},
    ).mappings().first()
    if not row:
        return None
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "environmentId": row["environment_id"],
        "name": row["name"],
        "profile": json.loads(row["profile_json"] or "{}"),
        "recommended": bool(row["recommended"]),
        "approved": bool(row["approved"]),
        "createdAt": str(row["created_at"]),
    }
