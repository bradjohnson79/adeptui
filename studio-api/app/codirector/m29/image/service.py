"""M2.9 image production service."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ...executive.models import JobType
from .. import fixture_mode_enabled
from ..fixtures import fixture_image_result
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
                payload={**payload, "assetId": result["assetId"], "versionId": ver["id"], "fixtureComplete": True},
                scene_id=scene_id,
                owner=owner,
            )
            result.update({"jobId": job.id, "versionId": ver["id"], "projectId": project_id})
            return result

        job = enqueue_executive_job(
            db,
            project_id=project_id,
            job_type=JobType.IMAGE_GENERATE,
            payload=payload,
            scene_id=scene_id,
            owner=owner,
        )
        ver = create_asset_version(
            db,
            project_id=project_id,
            department="image",
            status="draft",
            job_id=job.id,
            metadata={"operation": operation, "prompt": prompt, **params},
        )
        return {
            "jobId": job.id,
            "versionId": ver["id"],
            "assetId": ver["assetId"],
            "status": "draft",
            "operation": operation,
            "fixture": False,
            "projectId": project_id,
        }

    @staticmethod
    def execute_job(db: Session, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
        if payload.get("fixtureComplete") or fixture_mode_enabled() or payload.get("m29"):
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
        return {
            "assetId": payload.get("assetId"),
            "operation": payload.get("operation") or "generate",
            "provider": payload.get("provider") or "comfy",
            "fixture": False,
            "status": "generated" if payload.get("assetId") else "draft",
            "delegated": True,
        }

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
