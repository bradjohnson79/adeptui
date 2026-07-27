"""Camera + lighting scene states integrated with director/virtual stage patterns."""
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


LIGHT_PRESETS = {
    "three_point": {
        "key": {"intensity": 1.0, "azimuth": 45, "elevation": 35},
        "fill": {"intensity": 0.45, "azimuth": -40, "elevation": 20},
        "back": {"intensity": 0.7, "azimuth": 180, "elevation": 50},
    },
    "soft_overcast": {
        "key": {"intensity": 0.7, "azimuth": 0, "elevation": 80},
        "fill": {"intensity": 0.6, "azimuth": 90, "elevation": 40},
        "back": {"intensity": 0.2, "azimuth": 180, "elevation": 30},
    },
    "noir_rim": {
        "key": {"intensity": 0.55, "azimuth": 60, "elevation": 25},
        "fill": {"intensity": 0.1, "azimuth": -20, "elevation": 10},
        "back": {"intensity": 1.1, "azimuth": 200, "elevation": 35},
    },
}


def default_camera_state() -> dict[str, Any]:
    return {
        "position": {"x": 0, "y": 1.6, "z": 4},
        "target": {"x": 0, "y": 1.4, "z": 0},
        "fov": 35,
        "bookmark": "hero",
        "promptHint": "medium lens, eye-level, subtle dolly-in",
        "respectsM210bLocks": True,
        "executionLocked": True,
        "metadataOnlyUnlessApproved": True,
    }


def default_lighting_state(preset: str = "three_point") -> dict[str, Any]:
    rig = LIGHT_PRESETS.get(preset, LIGHT_PRESETS["three_point"])
    return {
        "preset": preset if preset in LIGHT_PRESETS else "three_point",
        "rig": rig,
        "promptLayers": {
            "key": "motivated key",
            "fill": "soft fill",
            "back": "separation rim",
        },
        "viewportPreview": True,
    }


def save_scene_state(
    db: Session,
    *,
    project_id: str,
    environment_id: str,
    kind: str,
    state: dict[str, Any],
    version: int | None = None,
) -> dict[str, Any]:
    if kind not in {"camera", "lighting"}:
        raise ValueError("kind must be camera or lighting")
    ensure_m213_tables()
    if version is None:
        row = db.execute(
            text(
                "SELECT COALESCE(MAX(version), 0) AS v FROM m213_scene_states "
                "WHERE environment_id = :eid AND kind = :kind"
            ),
            {"eid": environment_id, "kind": kind},
        ).mappings().first()
        version = int(row["v"] if row else 0) + 1
    sid = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO m213_scene_states "
            "(id, project_id, environment_id, kind, version, state_json, approved, created_at, updated_at) "
            "VALUES (:id, :project_id, :environment_id, :kind, :version, :state_json, 0, :ts, :ts)"
        ),
        {
            "id": sid,
            "project_id": project_id,
            "environment_id": environment_id,
            "kind": kind,
            "version": version,
            "state_json": json.dumps(state),
            "ts": _now(),
        },
    )
    db.commit()
    M213Store.save_version(
        db,
        project_id=project_id,
        subject_kind=f"scene_{kind}",
        subject_id=environment_id,
        version=version,
        snapshot=state,
    )
    cap = "ve.camera.state" if kind == "camera" else "ve.lighting.state"
    M213Store.log_capability(
        db, capability_id=cap, action="save", project_id=project_id, payload={"stateId": sid, "version": version}
    )
    return {
        "id": sid,
        "kind": kind,
        "version": version,
        "state": state,
        "approved": False,
        "approvalGate": f"{kind}_state",
    }


def approve_scene_state(
    db: Session, *, state_id: str, actor: str = "user", note: str = ""
) -> dict[str, Any]:
    ensure_m213_tables()
    row = db.execute(
        text("SELECT id, project_id, kind FROM m213_scene_states WHERE id = :id"),
        {"id": state_id},
    ).mappings().first()
    if not row:
        raise LookupError("scene state not found")
    db.execute(
        text("UPDATE m213_scene_states SET approved = 1, updated_at = :ts WHERE id = :id"),
        {"id": state_id, "ts": _now()},
    )
    db.commit()
    gate = f"{row['kind']}_state"
    approval = M213Store.record_approval(
        db, project_id=row["project_id"], gate=gate, subject_id=state_id, approved=True, actor=actor, note=note
    )
    return {"ok": True, "stateId": state_id, "kind": row["kind"], "approved": True, "approval": approval}


def get_scene_state(db: Session, state_id: str) -> Optional[dict[str, Any]]:
    ensure_m213_tables()
    row = db.execute(
        text(
            "SELECT id, project_id, environment_id, kind, version, state_json, approved, created_at "
            "FROM m213_scene_states WHERE id = :id"
        ),
        {"id": state_id},
    ).mappings().first()
    if not row:
        return None
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "environmentId": row["environment_id"],
        "kind": row["kind"],
        "version": int(row["version"]),
        "state": json.loads(row["state_json"] or "{}"),
        "approved": bool(row["approved"]),
        "createdAt": str(row["created_at"]),
    }
