"""HTTP API for Wave 5 continuity domain."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from . import correction_service, service
from .production_gate import evaluate_m42_wave5_gate
from .schemas import (
    ConstraintCreate,
    ContinuityPolicyUpdate,
    CorrectionEnqueueRequest,
    CorrectionProposeRequest,
    EvaluateRequest,
    IdentityVariantCreate,
    IdentityVersionCreate,
    IdentityVersionUpdate,
    PreflightRequest,
    ReferenceCreate,
    ReferenceUpdate,
    ReviewRequest,
    VisualIdentityCreate,
    VisualIdentityUpdate,
)

router = APIRouter(prefix="/continuity", tags=["continuity"])


@router.get("/gate/wave5")
def gate_wave5() -> dict[str, Any]:
    g = evaluate_m42_wave5_gate()
    return {**g, "ok": bool(g.get("wave5Go")), "passed": bool(g.get("wave5Go"))}


@router.get("/projects/{project_id}/policy")
def get_policy(project_id: str, db: Session = Depends(get_db)):
    return service.get_policy(db, project_id)


@router.patch("/projects/{project_id}/policy")
def patch_policy(project_id: str, body: ContinuityPolicyUpdate, db: Session = Depends(get_db)):
    return service.update_policy(db, project_id, body.model_dump(exclude_none=True))


@router.get("/projects/{project_id}/summary")
def summary(project_id: str, db: Session = Depends(get_db)):
    return service.project_summary(db, project_id)


@router.get("/projects/{project_id}/issues")
def issues(project_id: str, db: Session = Depends(get_db)):
    return {"items": service.list_issues(db, project_id)}


@router.get("/identities")
def list_identities(projectId: str, db: Session = Depends(get_db)):
    return {"items": service.list_identities(db, projectId)}


@router.post("/identities")
def create_identity(projectId: str, body: VisualIdentityCreate, db: Session = Depends(get_db)):
    return service.create_identity(db, projectId, body.model_dump())


@router.get("/identities/{identity_id}")
def get_identity(identity_id: str, projectId: str, db: Session = Depends(get_db)):
    return service.get_identity(db, projectId, identity_id)


@router.patch("/identities/{identity_id}")
def patch_identity(
    identity_id: str, projectId: str, body: VisualIdentityUpdate, db: Session = Depends(get_db)
):
    return service.update_identity(db, projectId, identity_id, body.model_dump(exclude_none=True))


@router.delete("/identities/{identity_id}")
def delete_identity(identity_id: str, projectId: str, db: Session = Depends(get_db)):
    return service.delete_or_archive_identity(db, projectId, identity_id)


@router.get("/identities/{identity_id}/readiness")
def readiness(identity_id: str, projectId: str, db: Session = Depends(get_db)):
    return service.identity_readiness(db, projectId, identity_id)


@router.get("/identities/{identity_id}/versions")
def versions(identity_id: str, projectId: str, db: Session = Depends(get_db)):
    return {"items": service.list_versions(db, projectId, identity_id)}


@router.post("/identities/{identity_id}/versions")
def create_version(
    identity_id: str, projectId: str, body: IdentityVersionCreate, db: Session = Depends(get_db)
):
    return service.create_version(db, projectId, identity_id, body.model_dump())


@router.patch("/versions/{version_id}")
def patch_version(version_id: str, projectId: str, body: IdentityVersionUpdate, db: Session = Depends(get_db)):
    return service.update_version_or_spawn_draft(db, projectId, version_id, body.model_dump(exclude_none=True))


@router.post("/versions/{version_id}/approve")
def approve_version(version_id: str, projectId: str, db: Session = Depends(get_db)):
    return service.approve_version(db, projectId, version_id)


@router.post("/versions/{version_id}/deprecate")
def deprecate_version(version_id: str, projectId: str, db: Session = Depends(get_db)):
    return service.deprecate_version(db, projectId, version_id)


@router.post("/versions/{version_id}/variants")
def create_variant(
    version_id: str, projectId: str, body: IdentityVariantCreate, db: Session = Depends(get_db)
):
    return service.create_variant(db, projectId, version_id, body.model_dump())


@router.get("/versions/{version_id}/variants")
def list_variants(version_id: str, projectId: str, db: Session = Depends(get_db)):
    return {"items": service.list_variants(db, projectId, version_id)}


@router.post("/references")
def create_reference(projectId: str, body: ReferenceCreate, db: Session = Depends(get_db)):
    return service.create_reference(db, projectId, body.model_dump())


@router.get("/references")
def list_references(projectId: str, identityId: str | None = None, db: Session = Depends(get_db)):
    return {"items": service.list_references(db, projectId, identityId)}


@router.patch("/references/{reference_id}")
def patch_reference(
    reference_id: str, projectId: str, body: ReferenceUpdate, db: Session = Depends(get_db)
):
    from .models import ApprovedReferenceRow
    from .permissions import assert_same_project
    from .validation import require_roles, sanitize_user_text

    row = db.get(ApprovedReferenceRow, reference_id)
    if not row:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Reference not found."})
    assert_same_project(row.project_id, projectId, what="reference")
    data = body.model_dump(exclude_none=True)
    if "roles" in data:
        import json

        row.roles_json = json.dumps(require_roles(data["roles"]))
    if "notes" in data:
        row.notes = sanitize_user_text(data["notes"])
    if "qualityStatus" in data:
        row.quality_status = str(data["qualityStatus"])
    db.commit()
    return service._ref_out(row)


@router.post("/references/{reference_id}/approve")
def approve_reference(reference_id: str, projectId: str, db: Session = Depends(get_db)):
    return service.approve_reference(db, projectId, reference_id)


@router.post("/references/{reference_id}/reject")
def reject_reference(reference_id: str, projectId: str, db: Session = Depends(get_db)):
    return service.reject_reference(db, projectId, reference_id)


@router.post("/references/{reference_id}/revoke")
def revoke_reference(reference_id: str, projectId: str, reason: str = "", db: Session = Depends(get_db)):
    return service.revoke_reference(db, projectId, reference_id, reason=reason)


@router.post("/constraints")
def create_constraint(projectId: str, body: ConstraintCreate, db: Session = Depends(get_db)):
    return service.create_constraint(db, projectId, body.model_dump())


@router.get("/versions/{version_id}/constraints")
def list_constraints(version_id: str, projectId: str, db: Session = Depends(get_db)):
    return {"items": service.list_constraints(db, projectId, version_id)}


@router.post("/preflight")
def preflight(projectId: str, body: PreflightRequest, db: Session = Depends(get_db)):
    return service.preflight(db, projectId, body.model_dump())


@router.get("/packets/{packet_id}")
def get_packet(packet_id: str, projectId: str, db: Session = Depends(get_db)):
    return service.get_packet(db, projectId, packet_id)


@router.post("/evaluate")
def evaluate(projectId: str, body: EvaluateRequest, db: Session = Depends(get_db)):
    return service.evaluate(db, projectId, body.assetId, body.packetId)


@router.get("/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str, projectId: str, db: Session = Depends(get_db)):
    return service.get_evaluation(db, projectId, evaluation_id)


@router.post("/evaluations/{evaluation_id}/review")
def review(evaluation_id: str, projectId: str, body: ReviewRequest, db: Session = Depends(get_db)):
    return service.add_review(db, projectId, evaluation_id, body.model_dump())


@router.post("/corrections/propose")
def propose_correction(projectId: str, body: CorrectionProposeRequest, db: Session = Depends(get_db)):
    return correction_service.propose_correction(db, projectId, body.model_dump())


@router.post("/corrections/{correction_id}/compile")
def compile_correction(correction_id: str, projectId: str, db: Session = Depends(get_db)):
    return correction_service.compile_correction(db, projectId, correction_id)


@router.post("/corrections/{correction_id}/enqueue")
def enqueue_correction(
    correction_id: str,
    projectId: str,
    body: CorrectionEnqueueRequest | None = None,
    db: Session = Depends(get_db),
):
    approved_by = (body.approvedBy if body else None) or "user"
    return correction_service.enqueue_correction(db, projectId, correction_id, approved_by=approved_by)
