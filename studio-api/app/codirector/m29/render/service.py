"""M2.9 render manifests + scene/timeline render jobs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ...executive.models import JobType
from .. import fixture_mode_enabled
from ..db import ensure_m29_tables
from ..fixtures import fixture_render_result
from ..store import create_asset_version, enqueue_executive_job


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


class RenderService:
    @staticmethod
    def create_manifest(
        db: Session,
        *,
        project_id: str,
        kind: str = "timeline_render",
        scene_id: str | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ensure_m29_tables()
        mid = uuid.uuid4().hex
        now = _now()
        body = manifest or {"outputs": ["mp4"], "quality": "draft"}
        db.execute(
            text(
                "INSERT INTO m29_render_manifests "
                "(id, project_id, scene_id, kind, status, job_id, asset_id, manifest_json, "
                "created_at, updated_at) "
                "VALUES (:id, :pid, :sid, :kind, :status, NULL, NULL, :mj, :c, :u)"
            ),
            {
                "id": mid,
                "pid": project_id,
                "sid": scene_id,
                "kind": kind,
                "status": "draft",
                "mj": json.dumps(body),
                "c": now,
                "u": now,
            },
        )
        db.commit()
        return {
            "id": mid,
            "projectId": project_id,
            "sceneId": scene_id,
            "kind": kind,
            "status": "draft",
            "manifest": body,
        }

    @staticmethod
    def render(
        db: Session,
        *,
        project_id: str,
        kind: str = "timeline_render",
        manifest_id: str | None = None,
        scene_id: str | None = None,
        owner: str = "user",
        **params: Any,
    ) -> dict[str, Any]:
        ensure_m29_tables()
        if not manifest_id:
            man = RenderService.create_manifest(
                db, project_id=project_id, kind=kind, scene_id=scene_id, manifest=params.get("manifest")
            )
            manifest_id = man["id"]
        job_type = JobType.SCENE_RENDER if kind == "scene_render" else JobType.TIMELINE_RENDER
        payload = {"manifestId": manifest_id, "kind": kind, "m29": True, **params}
        if fixture_mode_enabled():
            result = fixture_render_result(payload)
            ver = create_asset_version(
                db,
                project_id=project_id,
                department="render",
                status="generated",
                asset_id=result["assetId"],
                metadata={"kind": kind, "fixture": True},
            )
            job = enqueue_executive_job(
                db,
                project_id=project_id,
                job_type=job_type,
                payload={**payload, **result, "versionId": ver["id"], "fixtureComplete": True},
                scene_id=scene_id,
                owner=owner,
            )
            db.execute(
                text(
                    "UPDATE m29_render_manifests SET status = :s, job_id = :j, asset_id = :a, "
                    "updated_at = :u WHERE id = :id"
                ),
                {
                    "s": "generated",
                    "j": job.id,
                    "a": result["assetId"],
                    "u": _now(),
                    "id": manifest_id,
                },
            )
            db.commit()
            result.update({"jobId": job.id, "manifestId": manifest_id, "versionId": ver["id"], "projectId": project_id})
            return result
        job = enqueue_executive_job(
            db,
            project_id=project_id,
            job_type=job_type,
            payload=payload,
            scene_id=scene_id,
            owner=owner,
        )
        db.execute(
            text(
                "UPDATE m29_render_manifests SET status = :s, job_id = :j, updated_at = :u WHERE id = :id"
            ),
            {"s": "queued", "j": job.id, "u": _now(), "id": manifest_id},
        )
        db.commit()
        return {
            "jobId": job.id,
            "manifestId": manifest_id,
            "kind": kind,
            "status": "queued",
            "fixture": False,
            "projectId": project_id,
        }

    @staticmethod
    def execute_job(db: Session, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
        return fixture_render_result(payload)

    @staticmethod
    def get_manifest(db: Session, manifest_id: str) -> dict[str, Any] | None:
        ensure_m29_tables()
        row = db.execute(
            text(
                "SELECT id, project_id, scene_id, kind, status, job_id, asset_id, manifest_json, "
                "created_at, updated_at FROM m29_render_manifests WHERE id = :id"
            ),
            {"id": manifest_id},
        ).mappings().first()
        if not row:
            return None
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "sceneId": row["scene_id"],
            "kind": row["kind"],
            "status": row["status"],
            "jobId": row["job_id"],
            "assetId": row["asset_id"],
            "manifest": json.loads(row["manifest_json"] or "{}"),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
