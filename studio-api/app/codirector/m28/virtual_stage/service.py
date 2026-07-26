"""Adept Virtual Stage - structured camera as source of truth."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import ensure_m28_tables


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


DEFAULT_CAMERA = {
    "orbit": 0.0,
    "pivot": {"x": 0.0, "y": 0.0, "z": 0.0},
    "elevation": 0.0,
    "tilt": 0.0,
    "roll": 0.0,
    "distance": 3.0,
    "lensMm": 35,
}


def prompt_from_camera(camera: dict[str, Any]) -> str:
    """Derive prompt instructions from structured camera - prompt text is not SoT."""
    pivot = camera.get("pivot") or {}
    return (
        f"camera orbit={camera.get('orbit')} elevation={camera.get('elevation')} "
        f"tilt={camera.get('tilt')} roll={camera.get('roll')} "
        f"distance={camera.get('distance')} lens={camera.get('lensMm')}mm "
        f"pivot=({pivot.get('x')},{pivot.get('y')},{pivot.get('z')})"
    )


class VirtualStageService:
    @staticmethod
    def create(
        db: Session,
        *,
        project_id: str,
        scene_id: str | None = None,
        name: str = "Stage",
        camera: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ensure_m28_tables()
        sid = str(uuid.uuid4())
        cam = {**DEFAULT_CAMERA, **(camera or {})}
        now = _now()
        db.execute(
            text(
                "INSERT INTO m28_virtual_stages "
                "(id, project_id, scene_id, name, camera_json, created_at, updated_at) "
                "VALUES (:id, :project_id, :scene_id, :name, :camera_json, :created_at, :updated_at)"
            ),
            {
                "id": sid,
                "project_id": project_id,
                "scene_id": scene_id,
                "name": name,
                "camera_json": json.dumps(cam),
                "created_at": now,
                "updated_at": now,
            },
        )
        db.commit()
        return VirtualStageService.get(db, sid)  # type: ignore[return-value]

    @staticmethod
    def get(db: Session, stage_id: str) -> Optional[dict[str, Any]]:
        ensure_m28_tables()
        row = db.execute(
            text(
                "SELECT id, project_id, scene_id, name, camera_json, created_at, updated_at "
                "FROM m28_virtual_stages WHERE id = :id"
            ),
            {"id": stage_id},
        ).mappings().first()
        if not row:
            return None
        camera = json.loads(row["camera_json"] or "{}")
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "sceneId": row["scene_id"],
            "name": row["name"],
            "camera": camera,
            "promptDerived": prompt_from_camera(camera),
            "promptIsSourceOfTruth": False,
            "createdAt": str(row["created_at"]),
            "updatedAt": str(row["updated_at"]),
        }

    @staticmethod
    def update_camera(
        db: Session, *, stage_id: str, camera: dict[str, Any]
    ) -> dict[str, Any]:
        stage = VirtualStageService.get(db, stage_id)
        if not stage:
            raise LookupError("Virtual stage not found")
        merged = {**stage["camera"], **camera}
        if "pivot" in camera and isinstance(camera["pivot"], dict):
            merged["pivot"] = {**(stage["camera"].get("pivot") or {}), **camera["pivot"]}
        db.execute(
            text(
                "UPDATE m28_virtual_stages SET camera_json = :camera_json, updated_at = :updated_at "
                "WHERE id = :id"
            ),
            {"id": stage_id, "camera_json": json.dumps(merged), "updated_at": _now()},
        )
        db.commit()
        return VirtualStageService.get(db, stage_id)  # type: ignore[return-value]

    @staticmethod
    def list_for_project(db: Session, project_id: str) -> list[dict[str, Any]]:
        ensure_m28_tables()
        rows = db.execute(
            text(
                "SELECT id FROM m28_virtual_stages WHERE project_id = :pid "
                "ORDER BY created_at DESC"
            ),
            {"pid": project_id},
        ).fetchall()
        out = []
        for (sid,) in rows:
            item = VirtualStageService.get(db, sid)
            if item:
                out.append(item)
        return out
