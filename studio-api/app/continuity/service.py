"""Continuity domain service — identities, packets, evaluation, review, corrections."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import SCHEMA_VERSIONS
from .constants import EVALUATOR_KEY
from .evaluator import evaluate_packet, evaluator_capability
from .models import (
    ApprovedReferenceRow,
    ContinuityConstraintRow,
    ContinuityCorrectionRow,
    ContinuityEvaluationRow,
    ContinuityHistoryRow,
    ContinuityIssueRow,
    ContinuityPacketRow,
    ContinuityPolicyRow,
    ContinuityReviewRow,
    IdentityVariantRow,
    IdentityVersionRow,
    VisualIdentityRow,
)
from .packet_compiler import assemble_packet, build_binding_snapshot, select_references, _role_priority_for_shot
from .permissions import assert_same_project, require_project, require_project_asset
from .validation import (
    assert_reference_status_transition,
    reject_external_url,
    require_identity_type,
    require_roles,
    require_variant_type,
    sanitize_user_text,
    traits_are_dicts,
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _j(obj: Any) -> str:
    return json.dumps(obj if obj is not None else None, ensure_ascii=False)


def _l(raw: str | None, default: Any = None) -> Any:
    if not raw:
        return default if default is not None else {}
    try:
        return json.loads(raw)
    except Exception:
        return default if default is not None else {}


def _history(db: Session, project_id: str, event_type: str, entity_type: str, entity_id: str, payload: dict, actor: str = "user") -> None:
    db.add(
        ContinuityHistoryRow(
            id=str(uuid4()),
            project_id=project_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_json=_j(payload),
            actor=actor,
            created_at=_now(),
        )
    )


# ── Policy ──────────────────────────────────────────────────────────────────

def default_policy(project_id: str) -> dict[str, Any]:
    return {
        "continuityPolicySchemaVersion": SCHEMA_VERSIONS["continuityPolicySchemaVersion"],
        "projectId": project_id,
        "enabled": False,
        "preflightMode": "off",
        "evaluationMode": "manual",
        "productionMasterRequiresDecision": False,
        "criticalSeverityBehavior": "warn",
        "defaultEvaluatorKey": EVALUATOR_KEY,
    }


def get_policy(db: Session, project_id: str) -> dict[str, Any]:
    require_project(db, project_id)
    row = db.get(ContinuityPolicyRow, project_id)
    if not row:
        return default_policy(project_id)
    return {
        "continuityPolicySchemaVersion": row.continuity_policy_schema_version,
        "projectId": project_id,
        "enabled": bool(row.enabled),
        "preflightMode": row.preflight_mode,
        "evaluationMode": row.evaluation_mode,
        "productionMasterRequiresDecision": bool(row.production_master_requires_decision),
        "criticalSeverityBehavior": row.critical_severity_behavior,
        "defaultEvaluatorKey": row.default_evaluator_key,
    }


def update_policy(db: Session, project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    require_project(db, project_id)
    row = db.get(ContinuityPolicyRow, project_id)
    if not row:
        row = ContinuityPolicyRow(project_id=project_id, updated_at=_now())
        db.add(row)
    mapping = {
        "enabled": "enabled",
        "preflightMode": "preflight_mode",
        "evaluationMode": "evaluation_mode",
        "productionMasterRequiresDecision": "production_master_requires_decision",
        "criticalSeverityBehavior": "critical_severity_behavior",
        "defaultEvaluatorKey": "default_evaluator_key",
    }
    for src, dst in mapping.items():
        if src in patch and patch[src] is not None:
            setattr(row, dst, patch[src])
    row.continuity_policy_schema_version = SCHEMA_VERSIONS["continuityPolicySchemaVersion"]
    row.updated_at = _now()
    db.commit()
    _history(db, project_id, "policy_updated", "policy", project_id, patch)
    db.commit()
    return get_policy(db, project_id)


# ── Identity serialization ───────────────────────────────────────────────────

def _identity_out(row: VisualIdentityRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "projectId": row.project_id,
        "visualIdentitySchemaVersion": row.visual_identity_schema_version,
        "identityType": row.identity_type,
        "canonicalName": row.canonical_name,
        "displayName": row.display_name,
        "description": row.description,
        "status": row.status,
        "activeVersionId": row.active_version_id,
        "productionVersionId": row.production_version_id,
        "characterProfileId": row.character_profile_id,
        "bibleEntityStableId": row.bible_entity_stable_id,
        "archived": bool(row.archived),
        "createdBy": row.created_by,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


def _version_out(row: IdentityVersionRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "identityId": row.identity_id,
        "projectId": row.project_id,
        "versionNumber": row.version_number,
        "parentVersionId": row.parent_version_id,
        "label": row.label,
        "summary": row.summary,
        "identityTraitSchemaVersion": row.identity_trait_schema_version,
        "traits": _l(row.traits_json, {}),
        "constraintIds": _l(row.constraint_ids_json, []),
        "referenceSetId": row.reference_set_id,
        "status": row.status,
        "archived": bool(row.archived),
        "createdBy": row.created_by,
        "createdAt": row.created_at,
        "approvedBy": row.approved_by,
        "approvedAt": row.approved_at,
    }


def _variant_out(row: IdentityVariantRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "identityId": row.identity_id,
        "identityVersionId": row.identity_version_id,
        "projectId": row.project_id,
        "variantType": row.variant_type,
        "name": row.name,
        "description": row.description,
        "traitOverrides": _l(row.trait_overrides_json, {}),
        "lockedTraits": _l(row.locked_traits_json, []),
        "referenceSetId": row.reference_set_id,
        "status": row.status,
        "archived": bool(row.archived),
        "createdBy": row.created_by,
        "createdAt": row.created_at,
    }


def _ref_out(row: ApprovedReferenceRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "projectId": row.project_id,
        "identityId": row.identity_id,
        "identityVersionId": row.identity_version_id,
        "variantId": row.variant_id,
        "assetId": row.asset_id,
        "referenceRoleSchemaVersion": row.reference_role_schema_version,
        "roles": _l(row.roles_json, []),
        "approvalStatus": row.approval_status,
        "qualityStatus": row.quality_status,
        "notes": row.notes,
        "archived": bool(row.archived),
        "createdBy": row.created_by,
        "approvedBy": row.approved_by,
        "createdAt": row.created_at,
        "approvedAt": row.approved_at,
        "revokedAt": row.revoked_at,
        "revokedBy": row.revoked_by,
        "revokeReason": row.revoke_reason,
    }


def _get_identity(db: Session, project_id: str, identity_id: str) -> VisualIdentityRow:
    row = db.get(VisualIdentityRow, identity_id)
    if not row or row.archived:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Identity not found."})
    assert_same_project(row.project_id, project_id, what="identity")
    return row


# ── CRUD ─────────────────────────────────────────────────────────────────────

def list_identities(db: Session, project_id: str) -> list[dict[str, Any]]:
    require_project(db, project_id)
    rows = (
        db.query(VisualIdentityRow)
        .filter(VisualIdentityRow.project_id == project_id, VisualIdentityRow.archived.is_(False))
        .order_by(VisualIdentityRow.updated_at.desc())
        .all()
    )
    return [_identity_out(r) for r in rows]


def create_identity(db: Session, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    require_project(db, project_id)
    itype = require_identity_type(body.get("identityType") or "character")
    name = sanitize_user_text(body.get("canonicalName") or "", max_len=200)
    if not name:
        raise HTTPException(status_code=400, detail={"code": "NAME_REQUIRED", "message": "canonicalName is required."})
    now = _now()
    identity_id = str(uuid4())
    version_id = str(uuid4())
    ident = VisualIdentityRow(
        id=identity_id,
        project_id=project_id,
        visual_identity_schema_version=SCHEMA_VERSIONS["visualIdentitySchemaVersion"],
        identity_type=itype,
        canonical_name=name,
        display_name=sanitize_user_text(body.get("displayName") or name, max_len=200),
        description=sanitize_user_text(body.get("description")),
        status="draft",
        active_version_id=version_id,
        character_profile_id=body.get("characterProfileId"),
        bible_entity_stable_id=body.get("bibleEntityStableId"),
        created_by=str(body.get("createdBy") or "user"),
        created_at=now,
        updated_at=now,
    )
    ver = IdentityVersionRow(
        id=version_id,
        identity_id=identity_id,
        project_id=project_id,
        version_number=1,
        label="Version 1",
        summary="Initial draft",
        identity_trait_schema_version=SCHEMA_VERSIONS["identityTraitSchemaVersion"],
        traits_json="{}",
        constraint_ids_json="[]",
        status="draft",
        created_by=str(body.get("createdBy") or "user"),
        created_at=now,
    )
    db.add(ident)
    db.add(ver)
    _history(db, project_id, "identity_created", "identity", identity_id, {"name": name})
    db.commit()
    return _identity_out(ident)


def get_identity(db: Session, project_id: str, identity_id: str) -> dict[str, Any]:
    require_project(db, project_id)
    return _identity_out(_get_identity(db, project_id, identity_id))


def update_identity(db: Session, project_id: str, identity_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    require_project(db, project_id)
    row = _get_identity(db, project_id, identity_id)
    if patch.get("displayName") is not None:
        row.display_name = sanitize_user_text(patch["displayName"], max_len=200)
    if patch.get("description") is not None:
        row.description = sanitize_user_text(patch["description"])
    if patch.get("status") is not None:
        row.status = str(patch["status"])
    if patch.get("activeVersionId") is not None:
        row.active_version_id = patch["activeVersionId"]
    if patch.get("productionVersionId") is not None:
        row.production_version_id = patch["productionVersionId"]
    if "characterProfileId" in patch:
        row.character_profile_id = patch.get("characterProfileId")
    if "bibleEntityStableId" in patch:
        row.bible_entity_stable_id = patch.get("bibleEntityStableId")
    row.updated_at = _now()
    db.commit()
    return _identity_out(row)


def list_versions(db: Session, project_id: str, identity_id: str) -> list[dict[str, Any]]:
    _get_identity(db, project_id, identity_id)
    rows = (
        db.query(IdentityVersionRow)
        .filter(IdentityVersionRow.identity_id == identity_id, IdentityVersionRow.project_id == project_id)
        .order_by(IdentityVersionRow.version_number.asc())
        .all()
    )
    return [_version_out(r) for r in rows]


def create_version(db: Session, project_id: str, identity_id: str, body: dict[str, Any]) -> dict[str, Any]:
    ident = _get_identity(db, project_id, identity_id)
    existing = (
        db.query(IdentityVersionRow)
        .filter(IdentityVersionRow.identity_id == identity_id)
        .order_by(IdentityVersionRow.version_number.desc())
        .first()
    )
    num = (existing.version_number + 1) if existing else 1
    row = IdentityVersionRow(
        id=str(uuid4()),
        identity_id=identity_id,
        project_id=project_id,
        version_number=num,
        parent_version_id=existing.id if existing else None,
        label=sanitize_user_text(body.get("label") or f"Version {num}", max_len=200),
        summary=sanitize_user_text(body.get("summary")),
        identity_trait_schema_version=SCHEMA_VERSIONS["identityTraitSchemaVersion"],
        traits_json=_j(traits_are_dicts(body.get("traits"))),
        constraint_ids_json="[]",
        status="draft",
        created_by=str(body.get("createdBy") or "user"),
        created_at=_now(),
    )
    db.add(row)
    ident.active_version_id = row.id
    ident.updated_at = _now()
    _history(db, project_id, "identity_version_created", "version", row.id, {"versionNumber": num})
    db.commit()
    return _version_out(row)


def update_version_or_spawn_draft(
    db: Session, project_id: str, version_id: str, body: dict[str, Any]
) -> dict[str, Any]:
    """Approved versions are immutable — edits spawn a draft child."""
    row = db.get(IdentityVersionRow, version_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Version not found."})
    assert_same_project(row.project_id, project_id, what="version")
    if row.status == "approved":
        traits = traits_are_dicts(body.get("traits")) if body.get("traits") is not None else _l(row.traits_json, {})
        return create_version(
            db,
            project_id,
            row.identity_id,
            {
                "label": body.get("label") or f"{row.label} (draft)",
                "summary": body.get("summary") or f"Draft child of approved version {row.version_number}",
                "traits": traits,
                "createdBy": body.get("createdBy") or "user",
            },
        )
    if body.get("label") is not None:
        row.label = sanitize_user_text(body["label"], max_len=200)
    if body.get("summary") is not None:
        row.summary = sanitize_user_text(body["summary"])
    if body.get("traits") is not None:
        row.traits_json = _j(traits_are_dicts(body["traits"]))
    db.commit()
    return _version_out(row)


def approve_version(db: Session, project_id: str, version_id: str, approved_by: str = "user") -> dict[str, Any]:
    row = db.get(IdentityVersionRow, version_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Version not found."})
    assert_same_project(row.project_id, project_id, what="version")
    if row.archived:
        raise HTTPException(status_code=400, detail={"code": "ARCHIVED", "message": "Archived version cannot be approved."})
    row.status = "approved"
    row.approved_by = approved_by
    row.approved_at = _now()
    ident = _get_identity(db, project_id, row.identity_id)
    ident.status = "approved"
    ident.active_version_id = row.id
    ident.updated_at = _now()
    _history(db, project_id, "identity_version_approved", "version", version_id, {}, actor=approved_by)
    db.commit()
    return _version_out(row)


def deprecate_version(db: Session, project_id: str, version_id: str) -> dict[str, Any]:
    row = db.get(IdentityVersionRow, version_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Version not found."})
    assert_same_project(row.project_id, project_id, what="version")
    row.status = "deprecated"
    db.commit()
    return _version_out(row)


def create_variant(db: Session, project_id: str, version_id: str, body: dict[str, Any]) -> dict[str, Any]:
    ver = db.get(IdentityVersionRow, version_id)
    if not ver:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Version not found."})
    assert_same_project(ver.project_id, project_id, what="version")
    row = IdentityVariantRow(
        id=str(uuid4()),
        identity_id=ver.identity_id,
        identity_version_id=version_id,
        project_id=project_id,
        variant_type=require_variant_type(body.get("variantType") or "custom"),
        name=sanitize_user_text(body.get("name") or "Variant", max_len=200),
        description=sanitize_user_text(body.get("description")),
        trait_overrides_json=_j(traits_are_dicts(body.get("traitOverrides"))),
        locked_traits_json=_j(list(body.get("lockedTraits") or [])),
        status="approved" if ver.status == "approved" else "draft",
        created_by=str(body.get("createdBy") or "user"),
        created_at=_now(),
    )
    db.add(row)
    _history(db, project_id, "variant_created", "variant", row.id, {"name": row.name})
    db.commit()
    return _variant_out(row)


def list_variants(db: Session, project_id: str, version_id: str) -> list[dict[str, Any]]:
    ver = db.get(IdentityVersionRow, version_id)
    if not ver:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Version not found."})
    assert_same_project(ver.project_id, project_id, what="version")
    rows = db.query(IdentityVariantRow).filter(IdentityVariantRow.identity_version_id == version_id).all()
    return [_variant_out(r) for r in rows]


# ── References ───────────────────────────────────────────────────────────────

def _detect_collisions(db: Session, project_id: str, asset_id: str, identity_id: str) -> None:
    others = (
        db.query(ApprovedReferenceRow)
        .filter(
            ApprovedReferenceRow.project_id == project_id,
            ApprovedReferenceRow.asset_id == asset_id,
            ApprovedReferenceRow.identity_id != identity_id,
            ApprovedReferenceRow.archived.is_(False),
            ApprovedReferenceRow.approval_status.in_(["approved", "candidate", "in_review"]),
        )
        .all()
    )
    if not others:
        return
    identity_ids = sorted({identity_id, *[o.identity_id for o in others]})
    db.add(
        ContinuityIssueRow(
            id=str(uuid4()),
            project_id=project_id,
            issue_type="identity_collision",
            severity="major",
            status="open",
            title="Reference asset associated with multiple identities",
            detail_json=_j({"assetId": asset_id, "identityIds": identity_ids}),
            identity_ids_json=_j(identity_ids),
            asset_ids_json=_j([asset_id]),
            packet_ids_json="[]",
            evaluation_ids_json="[]",
            created_at=_now(),
        )
    )


def create_reference(db: Session, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    require_project(db, project_id)
    asset_id = str(body.get("assetId") or "")
    reject_external_url(asset_id)
    require_project_asset(db, project_id, asset_id)
    identity_id = str(body.get("identityId") or "")
    version_id = str(body.get("identityVersionId") or "")
    _get_identity(db, project_id, identity_id)
    ver = db.get(IdentityVersionRow, version_id)
    if not ver or ver.project_id != project_id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Version not found."})
    roles = require_roles(list(body.get("roles") or []))
    row = ApprovedReferenceRow(
        id=str(uuid4()),
        project_id=project_id,
        identity_id=identity_id,
        identity_version_id=version_id,
        variant_id=body.get("variantId"),
        asset_id=asset_id,
        reference_role_schema_version=SCHEMA_VERSIONS["referenceRoleSchemaVersion"],
        roles_json=_j(roles),
        approval_status="candidate",
        notes=sanitize_user_text(body.get("notes")),
        created_by=str(body.get("createdBy") or "user"),
        created_at=_now(),
    )
    db.add(row)
    _detect_collisions(db, project_id, asset_id, identity_id)
    _history(db, project_id, "reference_added", "reference", row.id, {"assetId": asset_id, "roles": roles})
    db.commit()
    return _ref_out(row)


def list_references(db: Session, project_id: str, identity_id: str | None = None) -> list[dict[str, Any]]:
    require_project(db, project_id)
    q = db.query(ApprovedReferenceRow).filter(
        ApprovedReferenceRow.project_id == project_id,
        ApprovedReferenceRow.archived.is_(False),
    )
    if identity_id:
        q = q.filter(ApprovedReferenceRow.identity_id == identity_id)
    return [_ref_out(r) for r in q.all()]


def approve_reference(db: Session, project_id: str, reference_id: str, approved_by: str = "user") -> dict[str, Any]:
    row = db.get(ApprovedReferenceRow, reference_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Reference not found."})
    assert_same_project(row.project_id, project_id, what="reference")
    assert_reference_status_transition(row.approval_status, "approved")
    row.approval_status = "approved"
    row.approved_by = approved_by
    row.approved_at = _now()
    _history(db, project_id, "reference_approved", "reference", reference_id, {}, actor=approved_by)
    db.commit()
    return _ref_out(row)


def reject_reference(db: Session, project_id: str, reference_id: str) -> dict[str, Any]:
    row = db.get(ApprovedReferenceRow, reference_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Reference not found."})
    assert_same_project(row.project_id, project_id, what="reference")
    row.approval_status = "rejected"
    _history(db, project_id, "reference_rejected", "reference", reference_id, {})
    db.commit()
    return _ref_out(row)


def revoke_reference(db: Session, project_id: str, reference_id: str, reason: str = "", revoked_by: str = "user") -> dict[str, Any]:
    """Revoke without mutating historical packets; mark affected evaluations for review."""
    row = db.get(ApprovedReferenceRow, reference_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Reference not found."})
    assert_same_project(row.project_id, project_id, what="reference")
    row.approval_status = "revoked"
    row.revoked_at = _now()
    row.revoked_by = revoked_by
    row.revoke_reason = sanitize_user_text(reason)
    # Find historical packets that used this reference (do not mutate them)
    packets = db.query(ContinuityPacketRow).filter(ContinuityPacketRow.project_id == project_id).all()
    affected_packet_ids: list[str] = []
    for p in packets:
        bindings = _l(p.bindings_json, [])
        for b in bindings:
            if reference_id in (b.get("selected_reference_ids") or []):
                affected_packet_ids.append(p.id)
                break
    evals = (
        db.query(ContinuityEvaluationRow)
        .filter(
            ContinuityEvaluationRow.project_id == project_id,
            ContinuityEvaluationRow.packet_id.in_(affected_packet_ids or ["__none__"]),
        )
        .all()
    )
    eval_ids = []
    for ev in evals:
        ev.marked_for_review = True
        ev.mark_reason = f"Reference {reference_id} revoked; historical packet unchanged."
        eval_ids.append(ev.id)
    db.add(
        ContinuityIssueRow(
            id=str(uuid4()),
            project_id=project_id,
            issue_type="reference_revoked",
            severity="major",
            status="open",
            title="Approved reference revoked — review historical evaluations",
            detail_json=_j(
                {
                    "referenceId": reference_id,
                    "affectedPacketIds": affected_packet_ids,
                    "note": "Historical packets preserve frozen approval states; outputs not silently invalidated.",
                }
            ),
            identity_ids_json=_j([row.identity_id]),
            asset_ids_json=_j([row.asset_id]),
            packet_ids_json=_j(affected_packet_ids),
            evaluation_ids_json=_j(eval_ids),
            created_at=_now(),
        )
    )
    _history(db, project_id, "reference_revoked", "reference", reference_id, {"packets": affected_packet_ids}, actor=revoked_by)
    db.commit()
    return _ref_out(row)


# ── Constraints ──────────────────────────────────────────────────────────────

def create_constraint(db: Session, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    _get_identity(db, project_id, str(body.get("identityId")))
    row = ContinuityConstraintRow(
        id=str(uuid4()),
        identity_id=str(body["identityId"]),
        identity_version_id=str(body["identityVersionId"]),
        project_id=project_id,
        variant_id=body.get("variantId"),
        continuity_constraint_schema_version=SCHEMA_VERSIONS["continuityConstraintSchemaVersion"],
        dimension=str(body.get("dimension") or ""),
        policy=str(body.get("policy") or "prefer"),
        severity=str(body.get("severity") or "minor"),
        expected_value_json=_j(body.get("expectedValue")),
        tolerance_json=_j(body.get("tolerance")),
        user_description=sanitize_user_text(body.get("userDescription")),
        enabled=bool(body.get("enabled", True)),
        created_at=_now(),
    )
    db.add(row)
    db.commit()
    return {
        "id": row.id,
        "identityId": row.identity_id,
        "identityVersionId": row.identity_version_id,
        "dimension": row.dimension,
        "policy": row.policy,
        "severity": row.severity,
        "expectedValue": _l(row.expected_value_json, None),
        "enabled": row.enabled,
        "userDescription": row.user_description,
        "continuityConstraintSchemaVersion": row.continuity_constraint_schema_version,
    }


def list_constraints(db: Session, project_id: str, version_id: str) -> list[dict[str, Any]]:
    rows = (
        db.query(ContinuityConstraintRow)
        .filter(
            ContinuityConstraintRow.project_id == project_id,
            ContinuityConstraintRow.identity_version_id == version_id,
        )
        .all()
    )
    return [
        {
            "id": r.id,
            "dimension": r.dimension,
            "policy": r.policy,
            "severity": r.severity,
            "expected_value": _l(r.expected_value_json, None),
            "enabled": r.enabled,
            "user_description": r.user_description,
        }
        for r in rows
    ]


# ── Archival / deletion ──────────────────────────────────────────────────────

def _usage_count(db: Session, project_id: str, identity_id: str) -> int:
    packets = db.query(ContinuityPacketRow).filter(ContinuityPacketRow.project_id == project_id).all()
    n = 0
    for p in packets:
        for b in _l(p.bindings_json, []):
            if b.get("identity_id") == identity_id:
                n += 1
                break
    n += db.query(ContinuityEvaluationRow).filter(ContinuityEvaluationRow.project_id == project_id).count()  # coarse
    return n


def delete_or_archive_identity(db: Session, project_id: str, identity_id: str) -> dict[str, Any]:
    row = _get_identity(db, project_id, identity_id)
    versions = db.query(IdentityVersionRow).filter(IdentityVersionRow.identity_id == identity_id).all()
    if any(v.status == "approved" for v in versions):
        row.archived = True
        row.status = "archived"
        row.updated_at = _now()
        db.commit()
        return {"action": "archived", "reason": "Approved versions cannot be hard-deleted.", "identity": _identity_out(row)}
    # Check packet usage
    used = False
    for p in db.query(ContinuityPacketRow).filter(ContinuityPacketRow.project_id == project_id).all():
        for b in _l(p.bindings_json, []):
            if b.get("identity_id") == identity_id:
                used = True
                break
        if used:
            break
    if used:
        row.archived = True
        row.status = "archived"
        row.updated_at = _now()
        db.commit()
        return {"action": "archived", "reason": "Identity used in packet provenance.", "identity": _identity_out(row)}
    db.delete(row)
    for v in versions:
        db.delete(v)
    db.commit()
    return {"action": "deleted", "identityId": identity_id}


# ── Readiness (NOT continuity score) ─────────────────────────────────────────

def identity_readiness(db: Session, project_id: str, identity_id: str) -> dict[str, Any]:
    ident = _get_identity(db, project_id, identity_id)
    versions = list_versions(db, project_id, identity_id)
    approved_version = next((v for v in versions if v["status"] == "approved"), None)
    refs = list_references(db, project_id, identity_id)
    approved_refs = [r for r in refs if r["approvalStatus"] == "approved"]
    role_set: set[str] = set()
    for r in approved_refs:
        role_set.update(r.get("roles") or [])
    constraints = []
    if approved_version:
        constraints = list_constraints(db, project_id, approved_version["id"])
    coverage = {
        "front": "canonical_front" in role_set,
        "profile": "canonical_profile" in role_set,
        "back": "canonical_back" in role_set,
        "fullBody": "full_body" in role_set,
        "wardrobe": any(x.startswith("wardrobe_") for x in role_set),
    }
    return {
        "identityReadinessSchemaVersion": SCHEMA_VERSIONS["identityReadinessSchemaVersion"],
        "kind": "identity_readiness",
        "label": "Identity Readiness",
        "notContinuityScore": True,
        "identityId": identity_id,
        "approvedVersionPresent": approved_version is not None,
        "activeVersionId": ident.active_version_id,
        "referenceCoverage": coverage,
        "approvedReferenceCount": len(approved_refs),
        "criticalConstraintsConfigured": any(c.get("severity") == "critical" for c in constraints),
        "missingRoles": [k for k, ok in coverage.items() if not ok],
        "summary": "Reference / identity readiness — not an output continuity quality score.",
    }


# ── Preflight + packets ──────────────────────────────────────────────────────

def preflight(db: Session, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    require_project(db, project_id)
    policy = get_policy(db, project_id)
    bindings_req = list(body.get("bindings") or [])
    if not bindings_req or not policy.get("enabled"):
        if not bindings_req:
            return {
                "status": "not_applicable",
                "packetId": None,
                "blockers": [],
                "warnings": [],
                "missingRoles": [],
                "selectedReferences": [],
                "requiresUserConfirmation": False,
                "policy": policy,
            }

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    compiled_bindings: list[dict[str, Any]] = []
    all_selected: list[str] = []
    missing_roles: list[str] = []

    for br in bindings_req:
        identity_id = str(br.get("identityId") or "")
        try:
            ident_row = _get_identity(db, project_id, identity_id)
        except HTTPException as e:
            blockers.append({"code": "IDENTITY_NOT_FOUND", "message": str(e.detail), "identityId": identity_id})
            continue
        if ident_row.status == "archived":
            blockers.append({"code": "IDENTITY_ARCHIVED", "identityId": identity_id})
            continue
        version_id = br.get("identityVersionId") or ident_row.active_version_id or ident_row.production_version_id
        ver = db.get(IdentityVersionRow, version_id) if version_id else None
        if not ver or ver.project_id != project_id:
            blockers.append({"code": "NO_VERSION", "identityId": identity_id})
            continue
        if ver.status != "approved" and (body.get("requireContinuity") or policy.get("preflightMode") == "required"):
            blockers.append({"code": "NO_APPROVED_VERSION", "identityId": identity_id, "versionId": ver.id})
        elif ver.status != "approved":
            warnings.append({"code": "DRAFT_VERSION", "identityId": identity_id, "versionId": ver.id})

        variant_ids = list(br.get("variantIds") or [])
        variants = []
        for vid in variant_ids:
            vrow = db.get(IdentityVariantRow, vid)
            if not vrow or vrow.project_id != project_id:
                blockers.append({"code": "VARIANT_NOT_FOUND", "variantId": vid})
            else:
                variants.append(
                    {
                        "id": vrow.id,
                        "name": vrow.name,
                        "variant_type": vrow.variant_type,
                        "trait_overrides": _l(vrow.trait_overrides_json, {}),
                        "locked_traits": _l(vrow.locked_traits_json, []),
                    }
                )

        refs = list_references(db, project_id, identity_id)
        candidates = [
            {
                "id": r["id"],
                "asset_id": r["assetId"],
                "roles": r["roles"],
                "approval_status": r["approvalStatus"],
                "archived": r["archived"],
            }
            for r in refs
        ]
        preferred = _role_priority_for_shot(br.get("shotType"), list(br.get("requiredRoles") or []))
        selection = select_references(
            candidates=candidates,
            preferred_roles=preferred,
            max_references=int(body.get("maxReferences") or 6),
        )
        missing_roles.extend(selection.get("missing_preferred_roles") or [])
        if selection.get("missing_preferred_roles") and policy.get("preflightMode") == "required":
            if policy.get("criticalSeverityBehavior") == "block":
                blockers.append(
                    {
                        "code": "MISSING_REQUIRED_ROLES",
                        "roles": selection["missing_preferred_roles"],
                        "identityId": identity_id,
                    }
                )
            else:
                warnings.append(
                    {
                        "code": "MISSING_PREFERRED_ROLES",
                        "roles": selection["missing_preferred_roles"],
                        "identityId": identity_id,
                    }
                )
        elif selection.get("missing_preferred_roles"):
            warnings.append(
                {
                    "code": "MISSING_PREFERRED_ROLES",
                    "roles": selection["missing_preferred_roles"],
                    "identityId": identity_id,
                }
            )

        constraints = list_constraints(db, project_id, ver.id)
        identity_dict = {
            "id": ident_row.id,
            "identity_type": ident_row.identity_type,
            "display_name": ident_row.display_name,
            "canonical_name": ident_row.canonical_name,
        }
        version_dict = {
            "id": ver.id,
            "version_number": ver.version_number,
            "traits": _l(ver.traits_json, {}),
        }
        binding = build_binding_snapshot(
            identity=identity_dict,
            version=version_dict,
            variants=variants,
            selection=selection,
            constraints=constraints,
            expected_screen_role=br.get("expectedScreenRole"),
            expected_visibility=br.get("expectedVisibility") or "fully_visible",
            expected_view=br.get("expectedView"),
        )
        compiled_bindings.append(binding)
        all_selected.extend(binding["selected_reference_ids"])

    status = "ready"
    if blockers:
        status = "blocked"
    elif warnings:
        status = "ready_with_warnings" if policy.get("preflightMode") != "required" else "needs_review"

    packet_id = None
    if status in ("ready", "ready_with_warnings", "needs_review") and compiled_bindings:
        packet = assemble_packet(
            project_id=project_id,
            request_id=str(body.get("requestId") or uuid4()),
            bindings=compiled_bindings,
            workflow_capability_statement={
                "workflowKey": body.get("workflowKey"),
                "supportsReferences": bool(body.get("workflowSupportsReferences", True)),
                "promptGuidedOnly": not bool(body.get("workflowSupportsReferences", True)),
            },
        )
        prow = ContinuityPacketRow(
            id=packet["id"],
            project_id=project_id,
            request_id=packet["request_id"],
            continuity_packet_schema_version=packet["continuityPacketSchemaVersion"],
            bindings_json=_j(packet["bindings"]),
            workflow_capability_statement_json=_j(packet["workflow_capability_statement"]),
            resolver_version=packet["resolver_version"],
            compiler_version=packet["compiler_version"],
            frozen=True,
            created_at=_now(),
        )
        db.add(prow)
        _history(db, project_id, "continuity_packet_compiled", "packet", packet["id"], {"bindings": len(compiled_bindings)})
        db.commit()
        packet_id = packet["id"]

    return {
        "status": status,
        "packetId": packet_id,
        "blockers": blockers,
        "warnings": warnings,
        "missingRoles": missing_roles,
        "selectedReferences": all_selected,
        "selectedIdentityVersions": [b.get("identity_version_id") for b in compiled_bindings],
        "selectedVariants": [vid for b in compiled_bindings for vid in b.get("variant_ids") or []],
        "requiresUserConfirmation": status in ("needs_review", "ready_with_warnings"),
        "policy": policy,
        "bindingCount": len(compiled_bindings),
    }


def get_packet(db: Session, project_id: str, packet_id: str) -> dict[str, Any]:
    require_project(db, project_id)
    row = db.get(ContinuityPacketRow, packet_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Packet not found."})
    assert_same_project(row.project_id, project_id, what="packet")
    return {
        "id": row.id,
        "projectId": row.project_id,
        "requestId": row.request_id,
        "continuityPacketSchemaVersion": row.continuity_packet_schema_version,
        "bindings": _l(row.bindings_json, []),
        "workflowCapabilityStatement": _l(row.workflow_capability_statement_json, {}),
        "resolverVersion": row.resolver_version,
        "compilerVersion": row.compiler_version,
        "frozen": bool(row.frozen),
        "createdAt": row.created_at,
    }


def evaluate(db: Session, project_id: str, asset_id: str, packet_id: str) -> dict[str, Any]:
    require_project(db, project_id)
    require_project_asset(db, project_id, asset_id)
    packet = get_packet(db, project_id, packet_id)
    # Evaluate ONLY against frozen packet — do not re-resolve live identity records
    result = evaluate_packet(
        packet={"id": packet["id"], "bindings": packet["bindings"]},
        asset_id=asset_id,
        project_id=project_id,
    )
    row = ContinuityEvaluationRow(
        id=result["id"],
        project_id=project_id,
        asset_id=asset_id,
        packet_id=packet_id,
        continuity_evaluation_schema_version=result["continuityEvaluationSchemaVersion"],
        evaluator_key=result["evaluator_key"],
        evaluator_version=result["evaluator_version"],
        overall_score=result.get("overall_score"),
        overall_status=result["overall_status"],
        dimensions_json=_j(result["dimensions"]),
        requires_human_review=bool(result["requires_human_review"]),
        created_at=_now(),
    )
    db.add(row)
    _history(db, project_id, "evaluation_completed", "evaluation", row.id, {"status": row.overall_status})
    db.commit()
    return get_evaluation(db, project_id, row.id)


def get_evaluation(db: Session, project_id: str, evaluation_id: str) -> dict[str, Any]:
    row = db.get(ContinuityEvaluationRow, evaluation_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Evaluation not found."})
    assert_same_project(row.project_id, project_id, what="evaluation")
    return {
        "id": row.id,
        "projectId": row.project_id,
        "assetId": row.asset_id,
        "packetId": row.packet_id,
        "continuityEvaluationSchemaVersion": row.continuity_evaluation_schema_version,
        "evaluatorKey": row.evaluator_key,
        "evaluatorVersion": row.evaluator_version,
        "evaluatorCapability": evaluator_capability(row.evaluator_key),
        "overallScore": row.overall_score,
        "overallStatus": row.overall_status,
        "dimensions": _l(row.dimensions_json, []),
        "requiresHumanReview": bool(row.requires_human_review),
        "markedForReview": bool(row.marked_for_review),
        "markReason": row.mark_reason,
        "createdAt": row.created_at,
        "reviews": list_reviews(db, project_id, evaluation_id),
    }


def list_reviews(db: Session, project_id: str, evaluation_id: str) -> list[dict[str, Any]]:
    rows = (
        db.query(ContinuityReviewRow)
        .filter(
            ContinuityReviewRow.project_id == project_id,
            ContinuityReviewRow.evaluation_id == evaluation_id,
        )
        .order_by(ContinuityReviewRow.created_at.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "decision": r.decision,
            "reason": r.reason,
            "notes": r.notes,
            "previousDecision": r.previous_decision,
            "reviewer": r.reviewer,
            "createdAt": r.created_at,
            "reviewDecisionSchemaVersion": r.review_decision_schema_version,
        }
        for r in rows
    ]


def add_review(db: Session, project_id: str, evaluation_id: str, body: dict[str, Any]) -> dict[str, Any]:
    ev = get_evaluation(db, project_id, evaluation_id)
    prev = ev["reviews"][-1]["decision"] if ev["reviews"] else None
    row = ContinuityReviewRow(
        id=str(uuid4()),
        project_id=project_id,
        evaluation_id=evaluation_id,
        asset_id=ev["assetId"],
        review_decision_schema_version=SCHEMA_VERSIONS["reviewDecisionSchemaVersion"],
        decision=str(body.get("decision") or ""),
        reason=sanitize_user_text(body.get("reason")),
        notes=sanitize_user_text(body.get("notes")),
        previous_decision=prev,
        reviewer=str(body.get("reviewer") or "user"),
        correction_id=body.get("correctionId"),
        created_at=_now(),
    )
    db.add(row)
    _history(db, project_id, "human_review_recorded", "review", row.id, {"decision": row.decision}, actor=row.reviewer)
    db.commit()
    return get_evaluation(db, project_id, evaluation_id)


def list_issues(db: Session, project_id: str) -> list[dict[str, Any]]:
    require_project(db, project_id)
    rows = (
        db.query(ContinuityIssueRow)
        .filter(ContinuityIssueRow.project_id == project_id)
        .order_by(ContinuityIssueRow.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "issueType": r.issue_type,
            "severity": r.severity,
            "status": r.status,
            "title": r.title,
            "detail": _l(r.detail_json, {}),
            "identityIds": _l(r.identity_ids_json, []),
            "assetIds": _l(r.asset_ids_json, []),
            "packetIds": _l(r.packet_ids_json, []),
            "evaluationIds": _l(r.evaluation_ids_json, []),
            "createdAt": r.created_at,
        }
        for r in rows
    ]


def project_summary(db: Session, project_id: str) -> dict[str, Any]:
    require_project(db, project_id)
    return {
        "projectId": project_id,
        "policy": get_policy(db, project_id),
        "identityCount": len(list_identities(db, project_id)),
        "openIssues": len([i for i in list_issues(db, project_id) if i["status"] == "open"]),
        "evaluatorCapability": evaluator_capability(),
    }
