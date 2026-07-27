"""Session restore: project, scene, media, stage, approvals, blockers, next action."""
from __future__ import annotations

import json
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from .brief import get_latest_brief
from .db import ensure_m214_tables
from .media import list_media
from .store import M214Store, _jid, _now


def save_snapshot(db: Session, project_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    ensure_m214_tables()
    row = db.execute(
        text("SELECT id FROM m214_session_snapshots WHERE project_id = :pid"),
        {"pid": project_id},
    ).fetchone()
    ts = _now()
    payload = {**snapshot, "projectId": project_id, "updatedAt": ts}
    if row:
        db.execute(
            text(
                "UPDATE m214_session_snapshots SET snapshot_json = :j, updated_at = :ts WHERE project_id = :pid"
            ),
            {"j": _jid(payload), "ts": ts, "pid": project_id},
        )
        row_id = row[0]
    else:
        row_id = str(uuid4())
        db.execute(
            text(
                "INSERT INTO m214_session_snapshots (id, project_id, snapshot_json, created_at, updated_at) "
                "VALUES (:id, :pid, :j, :ts, :ts)"
            ),
            {"id": row_id, "pid": project_id, "j": _jid(payload), "ts": ts},
        )
    db.commit()
    return {"id": row_id, "projectId": project_id}


def restore_session(db: Session, project_id: str) -> dict[str, Any]:
    ensure_m214_tables()
    stage = M214Store.get_stage(db, project_id)
    brief = get_latest_brief(db, project_id)
    media = list_media(db, project_id)
    row = db.execute(
        text("SELECT snapshot_json FROM m214_session_snapshots WHERE project_id = :pid"),
        {"pid": project_id},
    ).fetchone()
    snap = json.loads(row[0]) if row else {}
    M214Store.log_capability(
        db, capability_id="codirector.project.resume", action="restore", project_id=project_id
    )
    return {
        "projectId": project_id,
        "stage": stage,
        "brief": brief,
        "media": media,
        "approvals": snap.get("approvals") or {},
        "blockers": snap.get("blockers") or [],
        "primaryNextAction": (brief or {}).get("primary_next_action")
        or snap.get("primaryNextAction")
        or "Start idea-first discovery",
        "snapshot": snap,
        "m212FeedbackHooks": {
            "emitOnPreference": True,
            "autoSystemPromote": False,
        },
    }
