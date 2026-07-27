"""M2.9 image production service."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ...executive.models import JobType
from .. import fixture_mode_enabled
from ..fixtures import fixture_image_result
from ..providers import image_provider_available, run_imagegen, wants_fixture
from ..store import create_asset_version, enqueue_executive_job, set_asset_status, _now


class ImageService:
    @staticmethod
    def generate(
        db: Session,
        *,
        project_id: str,
        prompt: str = "M2.9 image",
        operation: str = "generate",
        scene_id: str | None = None,
        owner: str = "user",
        **params: Any,
    ) -> dict[str, Any]:
        payload = {"prompt": prompt, "operation": operation, "m29": True, **params}
        if fixture_mode_enabled():
            result = fixture_image_result(payload)
            ver = create_asset_version(
                db,
                project_id=project_id,
                department="image",
                status="generated",
                asset_id=result["assetId"],
                metadata={"operation": operation, "fixture": True, **params, "prompt": prompt},
            )
            job = enqueue_executive_job(
                db,
                project_id=project_id,
                job_type=JobType.IMAGE_GENERATE,
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

        # Production path: nothing has been generated yet, so no asset id and no version
        # row may be minted here — a client must be able to tell "queued" from "created".
        provider_ready = image_provider_available()
        job = enqueue_executive_job(
            db,
            project_id=project_id,
            job_type=JobType.IMAGE_GENERATE,
            payload=payload,
            scene_id=scene_id,
            owner=owner,
        )
        out: dict[str, Any] = {
            "jobId": job.id,
            "versionId": None,
            "assetId": None,
            "status": "queued",
            "operation": operation,
            "fixture": False,
            "providerMissing": not provider_ready,
            "projectId": project_id,
        }
        if not provider_ready:
            out["awaitingProvider"] = True
            out["message"] = (
                "No image generation provider is available (ComfyUI/Z-Image unreachable). "
                "The job is queued and will report Blocked; no asset was created."
            )
        return out

    @staticmethod
    def execute_job(db: Session, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
        # CI fixture path only — never treat m29=True alone as fixture.
        if wants_fixture(payload):
            if payload.get("assetId") and payload.get("fixtureComplete"):
                result = fixture_image_result(payload)
                if payload.get("versionId"):
                    result["versionId"] = payload["versionId"]
                return result
            result = fixture_image_result(payload)
            if payload.get("versionId"):
                set_asset_status(db, payload["versionId"], "generated")
                result["versionId"] = payload["versionId"]
            else:
                ver = create_asset_version(
                    db,
                    project_id=project_id,
                    department="image",
                    status="generated",
                    asset_id=result["assetId"],
                    metadata={"fixture": True, **payload},
                )
                result["versionId"] = ver["id"]
            return result

        result = run_imagegen(db, project_id=project_id, payload=payload)
        if payload.get("versionId"):
            set_asset_status(db, payload["versionId"], "generated")
            # Bind real asset id onto the version row (no silent overwrite of other versions).
            db.execute(
                text(
                    "UPDATE m29_asset_versions SET asset_id = :aid, updated_at = :u WHERE id = :id"
                ),
                {"aid": result["assetId"], "u": _now(), "id": payload["versionId"]},
            )
            db.commit()
            result["versionId"] = payload["versionId"]
        else:
            ver = create_asset_version(
                db,
                project_id=project_id,
                department="image",
                status="generated",
                asset_id=result["assetId"],
                metadata={"provider": result.get("provider"), **payload},
            )
            result["versionId"] = ver["id"]
        return result

    @staticmethod
    def approve(db: Session, version_id: str, *, actor: str = "user") -> dict[str, Any]:
        out = set_asset_status(db, version_id, "approved")
        out["approvedBy"] = actor
        return out

    @staticmethod
    def reject(db: Session, version_id: str, *, actor: str = "user") -> dict[str, Any]:
        out = set_asset_status(db, version_id, "rejected")
        out["rejectedBy"] = actor
        return out

    @staticmethod
    def publish_reference(db: Session, version_id: str, *, actor: str = "user") -> dict[str, Any]:
        ver = set_asset_status(db, version_id, "approved")
        meta = dict(ver.get("metadata") or {})
        meta["publishedReference"] = True
        meta["publishedBy"] = actor
        db.execute(
            text(
                "UPDATE m29_asset_versions SET metadata_json = :m, updated_at = :u WHERE id = :id"
            ),
            {"m": json.dumps(meta), "u": _now(), "id": version_id},
        )
        db.commit()
        ver["metadata"] = meta
        return ver
