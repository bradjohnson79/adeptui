"""Shared persistence helpers for M2.9 tables."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m29_tables

ASSET_STATUSES = frozenset(
    {
        "draft",
        "generated",
        "validation_pending",
        "needs_review",
        "approved",
        "rejected",
        "superseded",
        "archived",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _jid() -> str:
    return uuid.uuid4().hex


def create_asset_version(
    db: Session,
    *,
    project_id: str,
    department: str,
    status: str = "generated",
    asset_id: str | None = None,
    job_id: str | None = None,
    parent_version_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_m29_tables()
    if status not in ASSET_STATUSES:
        raise ValueError(f"invalid asset status: {status}")
    vid = _jid()
    aid = asset_id or f"{department}-{vid[:12]}"
    now = _now()
    meta = metadata or {}
    db.execute(
        text(
            "INSERT INTO m29_asset_versions "
            "(id, project_id, asset_id, department, status, parent_version_id, job_id, "
            "metadata_json, created_at, updated_at) "
            "VALUES (:id, :pid, :aid, :dept, :status, :parent, :job, :meta, :c, :u)"
        ),
        {
            "id": vid,
            "pid": project_id,
            "aid": aid,
            "dept": department,
            "status": status,
            "parent": parent_version_id,
            "job": job_id,
            "meta": json.dumps(meta),
            "c": now,
            "u": now,
        },
    )
    db.commit()
    return {
        "id": vid,
        "projectId": project_id,
        "assetId": aid,
        "department": department,
        "status": status,
        "jobId": job_id,
        "metadata": meta,
        "createdAt": now,
    }


def get_asset_version(db: Session, version_id: str) -> dict[str, Any] | None:
    ensure_m29_tables()
    row = db.execute(
        text(
            "SELECT id, project_id, asset_id, department, status, parent_version_id, job_id, "
            "metadata_json, created_at, updated_at FROM m29_asset_versions WHERE id = :id"
        ),
        {"id": version_id},
    ).mappings().first()
    if not row:
        return None
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "assetId": row["asset_id"],
        "department": row["department"],
        "status": row["status"],
        "parentVersionId": row["parent_version_id"],
        "jobId": row["job_id"],
        "metadata": json.loads(row["metadata_json"] or "{}"),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def set_asset_status(db: Session, version_id: str, status: str) -> dict[str, Any]:
    ensure_m29_tables()
    if status not in ASSET_STATUSES:
        raise ValueError(f"invalid asset status: {status}")
    db.execute(
        text(
            "UPDATE m29_asset_versions SET status = :status, updated_at = :u WHERE id = :id"
        ),
        {"status": status, "u": _now(), "id": version_id},
    )
    db.commit()
    out = get_asset_version(db, version_id)
    if not out:
        raise KeyError(version_id)
    return out


def enqueue_executive_job(
    db: Session,
    *,
    project_id: str,
    job_type: Any,
    payload: dict[str, Any],
    scene_id: str | None = None,
    owner: str = "user",
) -> Any:
    from ..executive.schemas import CreateJobRequest
    from ..executive.service import ProductionExecutiveService

    ProductionExecutiveService.ensure_worker()
    return ProductionExecutiveService.create_job(
        db,
        CreateJobRequest(
            type=job_type,
            projectId=project_id,
            owner=owner,
            sceneId=scene_id,
            payload=payload,
        ),
    )
