"""M2.9 video production service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...executive.models import JobType
from .. import fixture_mode_enabled
from ..fixtures import fixture_video_result
from ..store import create_asset_version, enqueue_executive_job, set_asset_status


class VideoService:
    @staticmethod
    def generate(
        db: Session,
        *,
        project_id: str,
        prompt: str = "M2.9 video",
        mode: str = "text_to_video",
        scene_id: str | None = None,
        owner: str = "user",
        **params: Any,
    ) -> dict[str, Any]:
        payload = {"prompt": prompt, "mode": mode, "m29": True, **params}
        if fixture_mode_enabled():
            result = fixture_video_result(payload)
            ver = create_asset_version(
                db,
                project_id=project_id,
                department="video",
                status="generated",
                asset_id=result["assetId"],
                metadata={"mode": mode, "fixture": True, "prompt": prompt},
            )
            job = enqueue_executive_job(
                db,
                project_id=project_id,
                job_type=JobType.VIDEO_GENERATE,
                payload={**payload, "assetId": result["assetId"], "versionId": ver["id"], "fixtureComplete": True},
                scene_id=scene_id,
                owner=owner,
            )
            result.update({"jobId": job.id, "versionId": ver["id"], "projectId": project_id})
            return result
        job = enqueue_executive_job(
            db,
            project_id=project_id,
            job_type=JobType.VIDEO_GENERATE,
            payload=payload,
            scene_id=scene_id,
            owner=owner,
        )
        ver = create_asset_version(
            db,
            project_id=project_id,
            department="video",
            status="draft",
            job_id=job.id,
            metadata={"mode": mode, "prompt": prompt, **params},
        )
        return {
            "jobId": job.id,
            "versionId": ver["id"],
            "assetId": ver["assetId"],
            "mode": mode,
            "status": "draft",
            "fixture": False,
            "projectId": project_id,
        }

    @staticmethod
    def execute_job(db: Session, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
        result = fixture_video_result(payload)
        if payload.get("versionId"):
            try:
                set_asset_status(db, payload["versionId"], "generated")
            except Exception:
                pass
            result["versionId"] = payload["versionId"]
        return result
