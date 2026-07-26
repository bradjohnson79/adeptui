"""Sandbox promotion proposals - human-gated, no silent prod install."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import ensure_m28_tables
from ..sandbox.service import SandboxService


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class PromoteService:
    @staticmethod
    def create_proposal(db: Session, *, sandbox_id: str) -> dict[str, Any]:
        ensure_m28_tables()
        sb = SandboxService.get(db, sandbox_id)
        if not sb:
            raise LookupError("Sandbox not found")
        mid = str(uuid.uuid4())
        manifest = {
            "version": "m28-fixture-1",
            "commit": "fixture-commit",
            "hashes": {"model.safetensors": "sha256:fixture"},
            "deps": ["comfyui"],
            "workflowAdapter": "fixture-adapter",
            "testEnv": {"fixtureMode": True},
            "approval": None,
            "sandboxId": sandbox_id,
        }
        db.execute(
            text(
                "INSERT INTO m28_promotion_manifests "
                "(id, sandbox_id, manifest_json, status, created_at) "
                "VALUES (:id, :sandbox_id, :manifest_json, :status, :created_at)"
            ),
            {
                "id": mid,
                "sandbox_id": sandbox_id,
                "manifest_json": json.dumps(manifest),
                "status": "pending",
                "created_at": _now(),
            },
        )
        db.commit()
        return {
            "id": mid,
            "sandboxId": sandbox_id,
            "status": "pending",
            "manifest": manifest,
            "productionInstallOccurred": False,
        }

    @staticmethod
    def get(db: Session, manifest_id: str) -> Optional[dict[str, Any]]:
        ensure_m28_tables()
        row = db.execute(
            text(
                "SELECT id, sandbox_id, manifest_json, status, created_at "
                "FROM m28_promotion_manifests WHERE id = :id"
            ),
            {"id": manifest_id},
        ).mappings().first()
        if not row:
            return None
        return {
            "id": row["id"],
            "sandboxId": row["sandbox_id"],
            "status": row["status"],
            "manifest": json.loads(row["manifest_json"] or "{}"),
            "createdAt": str(row["created_at"]),
        }

    @staticmethod
    def reject(db: Session, manifest_id: str) -> dict[str, Any]:
        item = PromoteService.get(db, manifest_id)
        if not item:
            raise LookupError("Promotion proposal not found")
        db.execute(
            text("UPDATE m28_promotion_manifests SET status = 'rejected' WHERE id = :id"),
            {"id": manifest_id},
        )
        db.commit()
        item["status"] = "rejected"
        item["productionInstallOccurred"] = False
        item["mutated"] = False
        return item

    @staticmethod
    def approve(
        db: Session,
        *,
        manifest_id: str,
        project_id: str,
        owner: str = "user",
        actor: str = "user",
    ) -> dict[str, Any]:
        item = PromoteService.get(db, manifest_id)
        if not item:
            raise LookupError("Promotion proposal not found")
        if item["status"] == "rejected":
            raise ValueError("Cannot approve a rejected promotion")

        from ...executive.models import JobType
        from ...executive.schemas import CreateJobRequest
        from ...executive.service import ProductionExecutiveService

        ProductionExecutiveService.ensure_worker()
        manifest = dict(item["manifest"])
        manifest["approval"] = {"approved": True, "actor": actor, "at": _now()}
        db.execute(
            text(
                "UPDATE m28_promotion_manifests SET status = 'approved', "
                "manifest_json = :manifest_json WHERE id = :id"
            ),
            {"id": manifest_id, "manifest_json": json.dumps(manifest)},
        )
        db.commit()
        job = ProductionExecutiveService.create_job(
            db,
            CreateJobRequest(
                type=JobType.SANDBOX_PROMOTE,
                projectId=project_id,
                owner=owner,
                payload={
                    "manifestId": manifest_id,
                    "sandboxId": item["sandboxId"],
                    "approved": True,
                    "manifest": manifest,
                },
            ),
        )
        item["status"] = "approved"
        item["manifest"] = manifest
        item["job"] = job.model_dump()
        item["productionInstallOccurred"] = False
        item["audit"] = {"event": "promotion_approved", "actor": actor}
        return item
