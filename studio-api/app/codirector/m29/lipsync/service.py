"""M2.9 lip sync and mouth tracking service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...executive.models import JobType
from .. import fixture_mode_enabled
from ..fixtures import fixture_lipsync_result, fixture_mouth_track_result
from ..providers import run_lipsync, run_mouth_track, wants_fixture
from ..store import create_asset_version, enqueue_executive_job, set_asset_status


class LipsyncService:
    @staticmethod
    def generate(
        db: Session,
        *,
        project_id: str,
        audio_asset_id: str | None = None,
        video_asset_id: str | None = None,
        scene_id: str | None = None,
        owner: str = "user",
        **params: Any,
    ) -> dict[str, Any]:
        payload = {
            "audioAssetId": audio_asset_id,
            "videoAssetId": video_asset_id,
            "m29": True,
            **params,
        }
        if fixture_mode_enabled():
            result = fixture_lipsync_result(payload)
            ver = create_asset_version(
                db,
                project_id=project_id,
                department="lipsync",
                status="generated",
                asset_id=result["assetId"],
                metadata={"fixture": True},
            )
            job = enqueue_executive_job(
                db,
                project_id=project_id,
                job_type=JobType.LIPSYNC_GENERATE,
                payload={**payload, **result, "versionId": ver["id"], "fixtureComplete": True},
                scene_id=scene_id,
                owner=owner,
            )
            result.update({"jobId": job.id, "versionId": ver["id"], "projectId": project_id})
            return result
        job = enqueue_executive_job(
            db,
            project_id=project_id,
            job_type=JobType.LIPSYNC_GENERATE,
            payload=payload,
            scene_id=scene_id,
            owner=owner,
        )
        ver = create_asset_version(
            db,
            project_id=project_id,
            department="lipsync",
            status="draft",
            job_id=job.id,
            metadata={"audioAssetId": audio_asset_id, "videoAssetId": video_asset_id},
        )
        return {
            "jobId": job.id,
            "versionId": ver["id"],
            "fixture": False,
            "projectId": project_id,
            "status": "queued",
        }

    @staticmethod
    def mouth_track(
        db: Session,
        *,
        project_id: str,
        video_asset_id: str | None = None,
        scene_id: str | None = None,
        owner: str = "user",
        **params: Any,
    ) -> dict[str, Any]:
        payload = {"videoAssetId": video_asset_id, "m29": True, **params}
        if fixture_mode_enabled():
            result = fixture_mouth_track_result(payload)
            job = enqueue_executive_job(
                db,
                project_id=project_id,
                job_type=JobType.MOUTH_TRACK_GENERATE,
                payload={**payload, **result, "fixtureComplete": True},
                scene_id=scene_id,
                owner=owner,
            )
            result.update({"jobId": job.id, "projectId": project_id})
            return result
        job = enqueue_executive_job(
            db,
            project_id=project_id,
            job_type=JobType.MOUTH_TRACK_GENERATE,
            payload=payload,
            scene_id=scene_id,
            owner=owner,
        )
        return {"jobId": job.id, "fixture": False, "projectId": project_id, "status": "queued"}

    @staticmethod
    def mouth_rectangle(db: Session, *, project_id: str, **params: Any) -> dict[str, Any]:
        if fixture_mode_enabled():
            result = fixture_lipsync_result(params)
            result["projectId"] = project_id
            result["capability"] = "mouth.rectangle.generate"
            return result
        # Deterministic local edit/persist of rectangles (no generative provider required).
        rects = params.get("rectangles") or [{"t": 0.0, "x": 0.4, "y": 0.55, "w": 0.2, "h": 0.12}]
        ver = create_asset_version(
            db,
            project_id=project_id,
            department="mouth",
            status="generated",
            metadata={"rectangles": rects, "provider": "m29_local"},
        )
        return {
            "rectangles": rects,
            "provider": "m29_local",
            "fixture": False,
            "status": "generated",
            "projectId": project_id,
            "versionId": ver["id"],
            "capability": "mouth.rectangle.generate",
        }

    @staticmethod
    def execute_lipsync_job(db: Session, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
        if wants_fixture(payload):
            return fixture_lipsync_result(payload)
        result = run_lipsync(db, project_id=project_id, payload=payload)
        if payload.get("versionId"):
            set_asset_status(db, payload["versionId"], "generated")
            result["versionId"] = payload["versionId"]
        return result

    @staticmethod
    def execute_mouth_track_job(db: Session, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
        if wants_fixture(payload):
            return fixture_mouth_track_result(payload)
        return run_mouth_track(db, project_id=project_id, payload=payload)
