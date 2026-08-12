"""Project-ownership enforcement for service-layer entity lookups.

Centralizes the ``entity.project_id == caller_project_id`` check that closes
cross-project leak paths when the model (or stale client state) emits an
entity ID that belongs to a different project. Every function raises the
project's standard not-found error (HTTP 404) for both missing and foreign
entities, so existence is never leaked across projects.

This module is a deliberate leaf in the import graph: it imports only
``sqlalchemy`` and ``fastapi``. It must not import from the rest of the
Co-Director tool chain (``definitions``, ``registry``, ``execution``) so that
``app.voice_performance.service`` and the ``m29``/``m214`` routers can depend
on it without creating cycles or pulling in the tool registry.

Callers pass an authoritative ``project_id`` (from ``ToolContext.project_id``
on the tool path, or from the request body/query on the REST path). When the
caller has no project scope (legacy REST endpoints that have not yet been
upgraded to carry ``projectId``), pass ``project_id=None`` to retain the
historic bare-lookup behavior; the leak remains open for those callers and
must be closed by adding the project scope at the API boundary.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session


def _not_found(detail: str) -> None:
    raise HTTPException(status_code=404, detail=detail)


def _row_project_id(db: Session, sql: str, params: dict[str, Any]) -> Optional[str]:
    row = db.execute(text(sql), params).mappings().first()
    if not row:
        return None
    return row["project_id"]


def require_owned_performance_plan(db: Session, project_id: str, plan_id: str) -> None:
    """404 if the voice-performance plan is missing or belongs to another project."""
    pid = _row_project_id(
        db,
        "SELECT project_id FROM voice_performance_plans WHERE id = :id",
        {"id": plan_id},
    )
    if not pid or pid != project_id:
        _not_found("Performance plan not found.")


def find_owned_segment_plan(
    db: Session, project_id: str, segment_id: str
) -> tuple[str, dict[str, Any]]:
    """Resolve the (plan_id, segment_dict) that owns ``segment_id`` within ``project_id``.

    Segments are stored as JSON inside ``voice_performance_plans.segments_json``;
    there is no dedicated segment table. We scan the plans of *this* project only
    and locate the segment by id, so a stale segment ID from another project can
    never be retried/approved from a request scoped to this project.
    """
    rows = db.execute(
        text(
            "SELECT id, segments_json FROM voice_performance_plans "
            "WHERE project_id = :pid"
        ),
        {"pid": project_id},
    ).mappings().all()
    for row in rows:
        try:
            segs = json.loads(row["segments_json"] or "[]")
        except (ValueError, TypeError):
            continue
        if not isinstance(segs, list):
            continue
        for s in segs:
            if isinstance(s, dict) and s.get("id") == segment_id:
                return row["id"], s
    _not_found("Segment not found.")


def require_owned_m29_asset_version(
    db: Session, project_id: str, version_id: str
) -> dict[str, Any]:
    """Return the m29 asset version row iff it belongs to ``project_id``; 404 otherwise."""
    row = db.execute(
        text(
            "SELECT id, project_id, asset_id, department, status, parent_version_id, job_id, "
            "metadata_json, created_at, updated_at FROM m29_asset_versions WHERE id = :id"
        ),
        {"id": version_id},
    ).mappings().first()
    if not row or row["project_id"] != project_id:
        _not_found("version not found")
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


def require_owned_m29_timeline_proposal(
    db: Session, project_id: str, proposal_id: str
) -> dict[str, Any]:
    row = db.execute(
        text(
            "SELECT id, project_id, scene_id, status, proposal_json, created_at, updated_at "
            "FROM m29_timeline_proposals WHERE id = :id"
        ),
        {"id": proposal_id},
    ).mappings().first()
    if not row or row["project_id"] != project_id:
        _not_found("proposal not found")
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "sceneId": row["scene_id"],
        "status": row["status"],
        "proposal": json.loads(row["proposal_json"] or "{}"),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "requiresApproval": True,
    }


def require_owned_m29_control_plan(
    db: Session, project_id: str, plan_id: str
) -> dict[str, Any]:
    row = db.execute(
        text(
            "SELECT id, project_id, status, request_text, plan_json, created_at "
            "FROM m29_control_plans WHERE id = :id"
        ),
        {"id": plan_id},
    ).mappings().first()
    if not row or row["project_id"] != project_id:
        _not_found("plan not found")
    plan = json.loads(row["plan_json"] or "{}")
    return {
        "planId": row["id"],
        "projectId": row["project_id"],
        "status": row["status"],
        "requestText": row["request_text"],
        "steps": plan.get("steps") or [],
        "createdAt": row["created_at"],
        "requiresApproval": True,
    }


def require_owned_m29_render_manifest(
    db: Session, project_id: str, manifest_id: str
) -> dict[str, Any]:
    row = db.execute(
        text(
            "SELECT id, project_id, scene_id, kind, status, job_id, asset_id, manifest_json, "
            "created_at, updated_at FROM m29_render_manifests WHERE id = :id"
        ),
        {"id": manifest_id},
    ).mappings().first()
    if not row or row["project_id"] != project_id:
        _not_found("manifest not found")
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


def require_owned_m29_frame_record(
    db: Session, project_id: str, frame_id: str
) -> dict[str, Any]:
    row = db.execute(
        text(
            "SELECT id, project_id, shot_id, frame_type, order_index, asset_id, version_id, "
            "metadata_json, created_at FROM m29_frame_records WHERE id = :id"
        ),
        {"id": frame_id},
    ).mappings().first()
    if not row or row["project_id"] != project_id:
        _not_found("frame not found")
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "shotId": row["shot_id"],
        "frameType": row["frame_type"],
        "order": row["order_index"],
        "assetId": row["asset_id"],
        "versionId": row["version_id"],
        "metadata": json.loads(row["metadata_json"] or "{}"),
        "createdAt": row["created_at"],
    }


def require_owned_m214_storyteller_handoff(
    db: Session, project_id: str, handoff_id: str
) -> dict[str, Any]:
    row = db.execute(
        text(
            "SELECT id, project_id, scene_id, version, handoff_json, approved, created_at, updated_at "
            "FROM m214_storyteller_handoffs WHERE id = :id"
        ),
        {"id": handoff_id},
    ).mappings().first()
    if not row or row["project_id"] != project_id:
        _not_found("handoff not found")
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "sceneId": row["scene_id"],
        "version": row["version"],
        "handoff": json.loads(row["handoff_json"] or "{}"),
        "approved": bool(row["approved"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def require_owned_m214_sonic_concept(
    db: Session, project_id: str, concept_id: str
) -> dict[str, Any]:
    row = db.execute(
        text(
            "SELECT id, project_id, scene_id, version, concept_json, approved, created_at, updated_at "
            "FROM m214_sonic_concepts WHERE id = :id"
        ),
        {"id": concept_id},
    ).mappings().first()
    if not row or row["project_id"] != project_id:
        _not_found("concept not found")
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "sceneId": row["scene_id"],
        "version": row["version"],
        "concept": json.loads(row["concept_json"] or "{}"),
        "approved": bool(row["approved"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def require_owned_m214_attachment_interpretation(
    db: Session, project_id: str, interpretation_id: str
) -> dict[str, Any]:
    row = db.execute(
        text(
            "SELECT id, project_id, attachment_id, classified_kind, confidence, summary, status, "
            "payload_json, created_at, updated_at FROM m214_attachment_interpretations WHERE id = :id"
        ),
        {"id": interpretation_id},
    ).mappings().first()
    if not row or row["project_id"] != project_id:
        _not_found("interpretation not found")
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "attachmentId": row["attachment_id"],
        "classifiedKind": row["classified_kind"],
        "confidence": row["confidence"],
        "summary": row["summary"],
        "status": row["status"],
        "payload": json.loads(row["payload_json"] or "{}"),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }
