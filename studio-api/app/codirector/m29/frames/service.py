"""M2.9 frame production service."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ...executive.models import JobType
from .. import fixture_mode_enabled
from ..db import ensure_m29_tables
from ..fixtures import fixture_frame_result
from ..store import create_asset_version, enqueue_executive_job


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


class FramesService:
    @staticmethod
    def generate(
        db: Session,
        *,
        project_id: str,
        frame_type: str = "production_frame",
        shot_id: str | None = None,
        count: int = 1,
        scene_id: str | None = None,
        owner: str = "user",
        sequence: bool = False,
        **params: Any,
    ) -> dict[str, Any]:
        ensure_m29_tables()
        job_type = JobType.FRAME_SEQUENCE if sequence else JobType.FRAME_GENERATE
        payload = {
            "frameType": frame_type,
            "shotId": shot_id,
            "count": count,
            "sequence": sequence,
            "m29": True,
            **params,
        }
        if fixture_mode_enabled():
            result = fixture_frame_result(payload)
            records = []
            for fr in result["frames"]:
                ver = create_asset_version(
                    db,
                    project_id=project_id,
                    department="frame",
                    status="generated",
                    asset_id=fr["assetId"],
                    metadata={"frameType": frame_type, "fixture": True},
                )
                fid = fr["frameId"]
                db.execute(
                    text(
                        "INSERT INTO m29_frame_records "
                        "(id, project_id, shot_id, frame_type, order_index, asset_id, version_id, "
                        "metadata_json, created_at) "
                        "VALUES (:id, :pid, :sid, :ft, :ord, :aid, :vid, :meta, :c)"
                    ),
                    {
                        "id": fid,
                        "pid": project_id,
                        "sid": shot_id,
                        "ft": frame_type,
                        "ord": fr["order"],
                        "aid": fr["assetId"],
                        "vid": ver["id"],
                        "meta": json.dumps({"fixture": True}),
                        "c": _now(),
                    },
                )
                records.append({**fr, "versionId": ver["id"]})
            db.commit()
            job = enqueue_executive_job(
                db,
                project_id=project_id,
                job_type=job_type,
                payload={**payload, "fixtureComplete": True, "frames": records},
                scene_id=scene_id,
                owner=owner,
            )
            return {"jobId": job.id, "frames": records, "fixture": True, "projectId": project_id}

        job = enqueue_executive_job(
            db,
            project_id=project_id,
            job_type=job_type,
            payload=payload,
            scene_id=scene_id,
            owner=owner,
        )
        return {"jobId": job.id, "fixture": False, "projectId": project_id, "status": "queued"}

    @staticmethod
    def execute_job(db: Session, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
        if payload.get("frames"):
            return {"frames": payload["frames"], "fixture": True, "status": "generated"}
        return fixture_frame_result(payload)

    @staticmethod
    def list_frames(db: Session, project_id: str, shot_id: str | None = None) -> list[dict[str, Any]]:
        ensure_m29_tables()
        if shot_id:
            rows = db.execute(
                text(
                    "SELECT id, project_id, shot_id, frame_type, order_index, asset_id, version_id, "
                    "metadata_json, created_at FROM m29_frame_records "
                    "WHERE project_id = :pid AND shot_id = :sid ORDER BY order_index"
                ),
                {"pid": project_id, "sid": shot_id},
            ).mappings().all()
        else:
            rows = db.execute(
                text(
                    "SELECT id, project_id, shot_id, frame_type, order_index, asset_id, version_id, "
                    "metadata_json, created_at FROM m29_frame_records "
                    "WHERE project_id = :pid ORDER BY created_at"
                ),
                {"pid": project_id},
            ).mappings().all()
        return [
            {
                "id": r["id"],
                "projectId": r["project_id"],
                "shotId": r["shot_id"],
                "frameType": r["frame_type"],
                "order": r["order_index"],
                "assetId": r["asset_id"],
                "versionId": r["version_id"],
                "metadata": json.loads(r["metadata_json"] or "{}"),
                "createdAt": r["created_at"],
            }
            for r in rows
        ]

    @staticmethod
    def bind_to_shot(db: Session, frame_id: str, shot_id: str) -> dict[str, Any]:
        ensure_m29_tables()
        db.execute(
            text("UPDATE m29_frame_records SET shot_id = :sid WHERE id = :id"),
            {"sid": shot_id, "id": frame_id},
        )
        db.commit()
        row = db.execute(
            text(
                "SELECT id, project_id, shot_id, frame_type, order_index, asset_id FROM m29_frame_records "
                "WHERE id = :id"
            ),
            {"id": frame_id},
        ).mappings().first()
        if not row:
            raise KeyError(frame_id)
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "shotId": row["shot_id"],
            "frameType": row["frame_type"],
            "order": row["order_index"],
            "assetId": row["asset_id"],
        }
