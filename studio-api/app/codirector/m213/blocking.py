"""Blocking Canvas: 4 channels, tools, layers, CharacterBlockingState, approve."""
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


CHANNELS = (
    {"index": 0, "color": "#E4572E", "shape": "circle", "initials": "A"},
    {"index": 1, "color": "#29335C", "shape": "square", "initials": "B"},
    {"index": 2, "color": "#F3A712", "shape": "triangle", "initials": "C"},
    {"index": 3, "color": "#A8C256", "shape": "diamond", "initials": "D"},
)

TOOLS = ("marker", "facing", "path", "notes")
SURFACES = ("collage", "panorama", "viewport_snapshot", "floor_plan")


def empty_blocking_state(*, surface: str = "floor_plan") -> dict[str, Any]:
    return {
        "surface": surface if surface in SURFACES else "floor_plan",
        "channels": [dict(c) for c in CHANNELS],
        "layers": [
            {"id": "markers", "visible": True, "items": []},
            {"id": "facing", "visible": True, "items": []},
            {"id": "paths", "visible": True, "items": []},
            {"id": "notes", "visible": True, "items": []},
        ],
        "characters": [],
        "tools": list(TOOLS),
        "presets": [
            {"id": "two_shot", "label": "Two-shot facing"},
            {"id": "over_shoulder", "label": "Over-shoulder"},
            {"id": "wide_ensemble", "label": "Wide ensemble"},
        ],
    }


def apply_preset(state: dict[str, Any], preset_id: str) -> dict[str, Any]:
    state = json.loads(json.dumps(state))
    chars = []
    if preset_id == "two_shot":
        chars = [
            {"channel": 0, "x": 0.35, "y": 0.55, "facing": 90, "initials": "A"},
            {"channel": 1, "x": 0.65, "y": 0.55, "facing": 270, "initials": "B"},
        ]
    elif preset_id == "over_shoulder":
        chars = [
            {"channel": 0, "x": 0.3, "y": 0.6, "facing": 45, "initials": "A"},
            {"channel": 1, "x": 0.55, "y": 0.45, "facing": 225, "initials": "B"},
        ]
    else:
        chars = [
            {"channel": i, "x": 0.2 + i * 0.2, "y": 0.5, "facing": 0, "initials": CHANNELS[i]["initials"]}
            for i in range(4)
        ]
    state["characters"] = chars
    state["appliedPreset"] = preset_id
    return state


def save_blocking(
    db: Session,
    *,
    project_id: str,
    environment_id: str,
    state: dict[str, Any],
    version: int | None = None,
) -> dict[str, Any]:
    ensure_m213_tables()
    if version is None:
        row = db.execute(
            text(
                "SELECT COALESCE(MAX(version), 0) AS v FROM m213_blocking_states "
                "WHERE environment_id = :eid"
            ),
            {"eid": environment_id},
        ).mappings().first()
        version = int(row["v"] if row else 0) + 1
    bid = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO m213_blocking_states "
            "(id, project_id, environment_id, version, state_json, approved, approved_at, created_at, updated_at) "
            "VALUES (:id, :project_id, :environment_id, :version, :state_json, 0, NULL, :ts, :ts)"
        ),
        {
            "id": bid,
            "project_id": project_id,
            "environment_id": environment_id,
            "version": version,
            "state_json": json.dumps(state),
            "ts": _now(),
        },
    )
    db.commit()
    M213Store.save_version(
        db,
        project_id=project_id,
        subject_kind="blocking",
        subject_id=environment_id,
        version=version,
        snapshot=state,
    )
    M213Store.log_capability(
        db,
        capability_id="ve.blocking.canvas",
        action="save",
        project_id=project_id,
        payload={"blockingId": bid, "version": version},
    )
    return {
        "id": bid,
        "environmentId": environment_id,
        "version": version,
        "state": state,
        "approved": False,
        "approvalGate": "blocking",
    }


def approve_blocking(
    db: Session, *, blocking_id: str, actor: str = "user", note: str = ""
) -> dict[str, Any]:
    ensure_m213_tables()
    row = db.execute(
        text("SELECT id, project_id FROM m213_blocking_states WHERE id = :id"),
        {"id": blocking_id},
    ).mappings().first()
    if not row:
        raise LookupError("blocking not found")
    db.execute(
        text(
            "UPDATE m213_blocking_states SET approved = 1, approved_at = :ts, updated_at = :ts WHERE id = :id"
        ),
        {"id": blocking_id, "ts": _now()},
    )
    db.commit()
    approval = M213Store.record_approval(
        db,
        project_id=row["project_id"],
        gate="blocking",
        subject_id=blocking_id,
        approved=True,
        actor=actor,
        note=note,
    )
    return {"ok": True, "blockingId": blocking_id, "approved": True, "approval": approval}


def get_blocking(db: Session, blocking_id: str) -> Optional[dict[str, Any]]:
    ensure_m213_tables()
    row = db.execute(
        text(
            "SELECT id, project_id, environment_id, version, state_json, approved, created_at "
            "FROM m213_blocking_states WHERE id = :id"
        ),
        {"id": blocking_id},
    ).mappings().first()
    if not row:
        return None
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "environmentId": row["environment_id"],
        "version": int(row["version"]),
        "state": json.loads(row["state_json"] or "{}"),
        "approved": bool(row["approved"]),
        "createdAt": str(row["created_at"]),
    }


def merge_multiview_prompt(states: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "prompt": "Merge blocking annotations across surfaces; preserve channel color/shape/initials.",
        "surfaces": [s.get("surface") for s in states],
        "characterCount": max((len(s.get("characters") or []) for s in states), default=0),
        "advisory": True,
    }
