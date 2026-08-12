"""Certified continuity corrections via ImageEditIntent only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..image_product.edit_intent import ImageEditIntent, validate_basic
from .models import ContinuityCorrectionRow, ContinuityHistoryRow
from .permissions import assert_same_project, require_project, require_project_asset
from . import service as continuity_service
from .validation import sanitize_user_text


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _j(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


CERTIFIED_WORKFLOWS = frozenset({"image.inpaint", "image.edit", "image.refine"})


def propose_correction(db: Session, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    require_project(db, project_id)
    source = str(body.get("sourceAssetId") or "")
    require_project_asset(db, project_id, source)
    dimensions = list(body.get("dimensions") or [])
    prompt = sanitize_user_text(
        body.get("prompt")
        or (
            "Restore approved visual identity for dimensions: "
            + (", ".join(dimensions) if dimensions else "overall identity")
            + ". Preserve locked traits from the continuity packet."
        )
    )
    ref_ids: list[str] = []
    packet_id = body.get("packetId")
    if packet_id:
        packet = continuity_service.get_packet(db, project_id, packet_id)
        for b in packet.get("bindings") or []:
            for r in b.get("references_frozen") or []:
                aid = r.get("asset_id")
                if aid and aid not in ref_ids:
                    ref_ids.append(aid)

    workflow = "image.inpaint"
    certified = workflow in CERTIFIED_WORKFLOWS and bool(source)
    intent = ImageEditIntent(
        projectId=project_id,
        sourceAssetIds=[source],
        operation=workflow,
        prompt=prompt,
        referenceAssetIds=ref_ids,
        continuity={
            "packetId": packet_id,
            "evaluationId": body.get("evaluationId"),
            "issueIds": list(body.get("issueIds") or []),
            "dimensions": dimensions,
        },
        metadata={"source": "continuity.correction", "phase": "M42-W5"},
    )
    errors = validate_basic(intent)
    status = "proposed" if certified and not errors else "blocked"
    if not certified:
        status = "deferred"
    if errors and status == "proposed":
        status = "blocked"

    row = ContinuityCorrectionRow(
        id=str(uuid4()),
        project_id=project_id,
        source_asset_id=source,
        packet_id=packet_id,
        evaluation_id=body.get("evaluationId"),
        issue_ids_json=_j(list(body.get("issueIds") or [])),
        status=status,
        certified=certified and status == "proposed",
        workflow_key=workflow,
        image_edit_intent_json=_j(intent.to_dict()),
        created_by=str(body.get("createdBy") or "user"),
        created_at=_now(),
    )
    db.add(row)
    db.add(
        ContinuityHistoryRow(
            id=str(uuid4()),
            project_id=project_id,
            event_type="correction_proposed",
            entity_type="correction",
            entity_id=row.id,
            payload_json=_j({"certified": row.certified, "status": status}),
            actor=row.created_by,
            created_at=_now(),
        )
    )
    db.commit()
    return get_correction(db, project_id, row.id)


def get_correction(db: Session, project_id: str, correction_id: str) -> dict[str, Any]:
    row = db.get(ContinuityCorrectionRow, correction_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Correction not found."})
    assert_same_project(row.project_id, project_id, what="correction")
    return {
        "id": row.id,
        "projectId": row.project_id,
        "sourceAssetId": row.source_asset_id,
        "packetId": row.packet_id,
        "evaluationId": row.evaluation_id,
        "issueIds": json.loads(row.issue_ids_json or "[]"),
        "status": row.status,
        "certified": bool(row.certified),
        "certificationLabel": "Certified" if row.certified else ("Deferred" if row.status == "deferred" else "Blocked"),
        "workflowKey": row.workflow_key,
        "imageEditIntent": json.loads(row.image_edit_intent_json or "{}"),
        "jobId": row.job_id,
        "derivedAssetId": row.derived_asset_id,
        "createdBy": row.created_by,
        "createdAt": row.created_at,
        "enqueuedAt": row.enqueued_at,
        "sourcePreserved": True,
        "disclosure": "Corrections enqueue only via ImageEditIntent → editEnqueue. No second runtime.",
    }


def compile_correction(db: Session, project_id: str, correction_id: str) -> dict[str, Any]:
    row = get_correction(db, project_id, correction_id)
    if row["status"] in ("deferred", "blocked"):
        return {
            **row,
            "compiled": False,
            "message": f"Correction is {row['certificationLabel']} — cannot compile for enqueue.",
        }
    intent = ImageEditIntent.from_dict(row["imageEditIntent"])
    errors = validate_basic(intent)
    return {
        **row,
        "compiled": len(errors) == 0,
        "validation": {"ok": len(errors) == 0, "errors": errors},
        "path": "ImageEditIntent → compile_edit_request → editEnqueue",
    }


def enqueue_correction(db: Session, project_id: str, correction_id: str, approved_by: str = "user") -> dict[str, Any]:
    """User-approved enqueue through canonical image product edit path only."""
    crow = db.get(ContinuityCorrectionRow, correction_id)
    if not crow:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Correction not found."})
    assert_same_project(crow.project_id, project_id, what="correction")
    if not crow.certified or crow.status not in ("proposed", "compiled"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "NOT_CERTIFIED",
                "message": "Deferred or Blocked corrections cannot enqueue.",
                "status": crow.status,
                "certified": crow.certified,
            },
        )
    intent_dict = json.loads(crow.image_edit_intent_json or "{}")
    errors = validate_basic(intent_dict)
    if errors:
        raise HTTPException(
            status_code=400,
            detail={"code": "INTENT_INVALID", "message": "ImageEditIntent failed validation.", "errors": errors},
        )
    from ..image_product.edit_service import enqueue_edit

    result = enqueue_edit(db, project_id, intent_dict)
    job_id = None
    if isinstance(result, dict):
        job_id = result.get("jobId") or result.get("job_id") or (result.get("job") or {}).get("id")
    crow.status = "enqueued"
    crow.job_id = str(job_id) if job_id else None
    crow.enqueued_at = _now()
    # Never set derived_asset_id until real job completes — source preserved
    db.add(
        ContinuityHistoryRow(
            id=str(uuid4()),
            project_id=project_id,
            event_type="correction_enqueued",
            entity_type="correction",
            entity_id=correction_id,
            payload_json=_j({"jobId": crow.job_id, "approvedBy": approved_by}),
            actor=approved_by,
            created_at=_now(),
        )
    )
    db.commit()
    return {
        **get_correction(db, project_id, correction_id),
        "enqueueResult": result if isinstance(result, dict) else {"ok": True},
        "sourcePreserved": True,
    }
