"""UnifiedSceneBrief revision sync."""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import UnifiedSceneBrief
from .db import ensure_m214_tables
from .store import M214Store, _jid, _now


def upsert_brief(
    db: Session,
    *,
    project_id: str,
    scene_id: str = "",
    title: str = "",
    logline: str = "",
    emotional_profile_id: Optional[str] = None,
    sonic_concept_id: Optional[str] = None,
    storyteller_handoff_id: Optional[str] = None,
    primary_next_action: str = "",
    departments: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    ensure_m214_tables()
    row = db.execute(
        text("SELECT id, revision, brief_json FROM m214_unified_briefs WHERE project_id = :pid ORDER BY revision DESC"),
        {"pid": project_id},
    ).fetchone()
    revision = (row[1] + 1) if row else 1
    prev = json.loads(row[2]) if row else {}
    brief = UnifiedSceneBrief(
        id=str(__import__("uuid").uuid4()) if not row else str(__import__("uuid").uuid4()),
        project_id=project_id,
        scene_id=scene_id or prev.get("scene_id", ""),
        revision=revision,
        title=title or prev.get("title", "Untitled scene"),
        logline=logline or prev.get("logline", ""),
        emotional_profile_id=emotional_profile_id or prev.get("emotional_profile_id"),
        sonic_concept_id=sonic_concept_id or prev.get("sonic_concept_id"),
        storyteller_handoff_id=storyteller_handoff_id or prev.get("storyteller_handoff_id"),
        departments=departments or prev.get("departments") or {},
        primary_next_action=primary_next_action
        or prev.get("primary_next_action")
        or "Confirm Storyteller direction",
        approved_keys=list(prev.get("approved_keys") or []),
        payload={"extendsM211": True, "forkedRuntime": False},
    )
    ts = _now()
    db.execute(
        text(
            "INSERT INTO m214_unified_briefs "
            "(id, project_id, scene_id, revision, brief_json, created_at, updated_at) "
            "VALUES (:id, :pid, :sid, :rev, :j, :ts, :ts)"
        ),
        {
            "id": brief.id,
            "pid": project_id,
            "sid": brief.scene_id,
            "rev": revision,
            "j": _jid(brief.to_dict()),
            "ts": ts,
        },
    )
    db.commit()
    M214Store.log_capability(
        db,
        capability_id="production_team.brief.update",
        action="upsert",
        project_id=project_id,
        payload={"briefId": brief.id, "revision": revision},
    )
    return brief.to_dict()


def get_latest_brief(db: Session, project_id: str) -> dict[str, Any] | None:
    ensure_m214_tables()
    row = db.execute(
        text(
            "SELECT brief_json FROM m214_unified_briefs WHERE project_id = :pid ORDER BY revision DESC LIMIT 1"
        ),
        {"pid": project_id},
    ).fetchone()
    if not row:
        return None
    return json.loads(row[0] or "{}")
