"""M2.9 video production service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ...executive.models import JobType
from .. import fixture_mode_enabled
from ..fixtures import fixture_video_result
from ..providers import run_video, video_provider_available, wants_fixture
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
                payload={
                    **payload,
                    "assetId": result["assetId"],
                    "versionId": ver["id"],
                    "fixtureComplete": True,
                },
                scene_id=scene_id,
                owner=owner,
            )
            result.update({"jobId": job.id, "versionId": ver["id"], "projectId": project_id})
            return result
        # Production path: no provider has run, so no asset id and no version row may be
        # minted here — a client must be able to tell "queued" from "created".
        provider_ready = video_provider_available(db)
        job = enqueue_executive_job(
            db,
            project_id=project_id,
            job_type=JobType.VIDEO_GENERATE,
            payload=payload,
            scene_id=scene_id,
            owner=owner,
        )
        out: dict[str, Any] = {
            "jobId": job.id,
            "versionId": None,
            "assetId": None,
            "mode": mode,
            "status": "queued",
            "fixture": False,
            "providerMissing": not provider_ready,
            "projectId": project_id,
        }
        if not provider_ready:
            out["awaitingProvider"] = True
            out["message"] = (
                "No video generation provider is available (neither ComfyUI nor a fal key). "
                "The job is queued and will report Blocked; no asset was created."
            )
        return out

    @staticmethod
    def execute_job(db: Session, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
        if wants_fixture(payload):
            result = fixture_video_result(payload)
            if payload.get("versionId"):
                try:
                    set_asset_status(db, payload["versionId"], "generated")
                except Exception:  # noqa: BLE001
                    pass
                result["versionId"] = payload["versionId"]
            return result

        result = run_video(db, project_id=project_id, payload=payload)
        if payload.get("versionId"):
            set_asset_status(db, payload["versionId"], "generated")
            result["versionId"] = payload["versionId"]
        else:
            ver = create_asset_version(
                db,
                project_id=project_id,
                department="video",
                status="generated",
                asset_id=result["assetId"],
                metadata={"provider": result.get("provider"), **payload},
            )
            result["versionId"] = ver["id"]
        return result
