"""Shot Profile CRUD with guided/professional shared payload."""

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


DEFAULT_PAYLOAD = {
    "mode": "guided",
    "camera": {"lensMm": 35, "distance": 2.0, "elevation": 0.0, "tilt": 0.0, "roll": 0.0},
    "lighting": {
        "template": "soft_key",
        "key": 0.7,
        "fill": 0.3,
        "rim": 0.2,
        "intensity": 0.8,
        "temperature": 5600,
        "softness": 0.6,
    },
    "atmosphere": {"blueHaze": 0.1},
    "grade": {"template": "neutral", "contrast": 0.1, "saturation": 0.0},
    "aiRelighting": False,
    "associations": {"storyboardShotId": None, "timelineItemId": None},
    "cinematicDepth": {"suggestions": [], "accepted": [], "rejected": []},
}


class ShotProfileService:
    @staticmethod
    def create(db: Session, *, project_id: str, name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        ensure_m28_tables()
        pid = str(uuid.uuid4())
        vid = str(uuid.uuid4())
        body = {**DEFAULT_PAYLOAD, **(payload or {})}
        db.execute(
            text(
                "INSERT INTO m28_shot_profiles (id, project_id, name, active_version_id, created_at) "
                "VALUES (:id, :project_id, :name, :active_version_id, :created_at)"
            ),
            {
                "id": pid,
                "project_id": project_id,
                "name": name,
                "active_version_id": vid,
                "created_at": _now(),
            },
        )
        db.execute(
            text(
                "INSERT INTO m28_shot_profile_versions "
                "(id, profile_id, version, payload_json, created_at) "
                "VALUES (:id, :profile_id, 1, :payload_json, :created_at)"
            ),
            {
                "id": vid,
                "profile_id": pid,
                "payload_json": json.dumps(body),
                "created_at": _now(),
            },
        )
        db.commit()
        return ShotProfileService.get(db, pid)  # type: ignore[return-value]

    @staticmethod
    def get(db: Session, profile_id: str) -> Optional[dict[str, Any]]:
        ensure_m28_tables()
        row = db.execute(
            text(
                "SELECT id, project_id, name, active_version_id, created_at "
                "FROM m28_shot_profiles WHERE id = :id"
            ),
            {"id": profile_id},
        ).mappings().first()
        if not row:
            return None
        versions = db.execute(
            text(
                "SELECT id, version, payload_json, created_at FROM m28_shot_profile_versions "
                "WHERE profile_id = :pid ORDER BY version"
            ),
            {"pid": profile_id},
        ).mappings().all()
        active = next((v for v in versions if v["id"] == row["active_version_id"]), None)
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "name": row["name"],
            "activeVersionId": row["active_version_id"],
            "createdAt": str(row["created_at"]),
            "payload": json.loads(active["payload_json"]) if active else {},
            "versions": [
                {
                    "id": v["id"],
                    "version": v["version"],
                    "payload": json.loads(v["payload_json"] or "{}"),
                    "createdAt": str(v["created_at"]),
                }
                for v in versions
            ],
        }

    @staticmethod
    def save_version(
        db: Session,
        *,
        profile_id: str,
        payload: dict[str, Any],
        mode: str | None = None,
    ) -> dict[str, Any]:
        profile = ShotProfileService.get(db, profile_id)
        if not profile:
            raise LookupError("Shot profile not found")
        body = {**(profile.get("payload") or {}), **payload}
        if mode:
            body["mode"] = mode
        next_ver = max((v["version"] for v in profile["versions"]), default=0) + 1
        vid = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO m28_shot_profile_versions "
                "(id, profile_id, version, payload_json, created_at) "
                "VALUES (:id, :profile_id, :version, :payload_json, :created_at)"
            ),
            {
                "id": vid,
                "profile_id": profile_id,
                "version": next_ver,
                "payload_json": json.dumps(body),
                "created_at": _now(),
            },
        )
        db.execute(
            text("UPDATE m28_shot_profiles SET active_version_id = :vid WHERE id = :id"),
            {"vid": vid, "id": profile_id},
        )
        db.commit()
        return ShotProfileService.get(db, profile_id)  # type: ignore[return-value]

    @staticmethod
    def apply_cinematic_depth(
        db: Session,
        *,
        profile_id: str,
        suggestions: list[dict[str, Any]],
        accept_ids: list[str],
    ) -> dict[str, Any]:
        profile = ShotProfileService.get(db, profile_id)
        if not profile:
            raise LookupError("Shot profile not found")
        accepted = [s for s in suggestions if s.get("id") in accept_ids]
        rejected = [s for s in suggestions if s.get("id") not in accept_ids]
        payload = dict(profile["payload"])
        payload["cinematicDepth"] = {
            "suggestions": suggestions,
            "accepted": accepted,
            "rejected": rejected,
        }
        # Apply accepted camera/composition keys only
        for s in accepted:
            if "camera" in s:
                payload["camera"] = {**payload.get("camera", {}), **s["camera"]}
        return ShotProfileService.save_version(db, profile_id=profile_id, payload=payload)

    @staticmethod
    def associate(
        db: Session,
        *,
        profile_id: str,
        storyboard_shot_id: str | None = None,
        timeline_item_id: str | None = None,
    ) -> dict[str, Any]:
        profile = ShotProfileService.get(db, profile_id)
        if not profile:
            raise LookupError("Shot profile not found")
        payload = dict(profile["payload"])
        assoc = dict(payload.get("associations") or {})
        if storyboard_shot_id is not None:
            assoc["storyboardShotId"] = storyboard_shot_id
        if timeline_item_id is not None:
            assoc["timelineItemId"] = timeline_item_id
        payload["associations"] = assoc
        return ShotProfileService.save_version(db, profile_id=profile_id, payload=payload)

    @staticmethod
    def export(db: Session, profile_id: str) -> dict[str, Any]:
        profile = ShotProfileService.get(db, profile_id)
        if not profile:
            raise LookupError("Shot profile not found")
        return {
            "format": "adept.shot_profile.v1",
            "name": profile["name"],
            "payload": profile["payload"],
            "versions": profile["versions"],
        }

    @staticmethod
    def import_profile(
        db: Session, *, project_id: str, name: str, blob: dict[str, Any]
    ) -> dict[str, Any]:
        return ShotProfileService.create(
            db,
            project_id=project_id,
            name=name or blob.get("name") or "Imported Profile",
            payload=blob.get("payload") or {},
        )
