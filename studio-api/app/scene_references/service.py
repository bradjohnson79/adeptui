"""Scene Reference Binding domain service."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import repository as repo
from .capability import get_capability, list_capabilities, support_status_for
from .constants import REFERENCE_TYPES, SCOPE_TYPES, USAGE_MODES
from .inheritance import ancestor_chain, merge_inherited
from .permissions import require_asset_in_project, require_project


def _validate_enums(scope_type: str, reference_type: str, usage_modes: list[str]) -> None:
    if scope_type not in SCOPE_TYPES:
        raise HTTPException(status_code=400, detail={"code": "INVALID_SCOPE", "message": scope_type})
    if reference_type not in REFERENCE_TYPES:
        raise HTTPException(status_code=400, detail={"code": "INVALID_TYPE", "message": reference_type})
    for m in usage_modes:
        if m not in USAGE_MODES:
            raise HTTPException(status_code=400, detail={"code": "INVALID_USAGE_MODE", "message": m})


def _identity_approval(db: Session, identity_id: str | None, identity_version_id: str | None) -> str | None:
    if not identity_id:
        return None
    try:
        from app.continuity.models import ApprovedReferenceRow

        q = select(ApprovedReferenceRow).where(ApprovedReferenceRow.identity_id == identity_id)
        rows = list(db.scalars(q).all())
        if not rows:
            return "unlinked"
        # Prefer matching version if provided
        for r in rows:
            if identity_version_id and getattr(r, "identity_version_id", None) == identity_version_id:
                return r.approval_status
        return rows[0].approval_status
    except Exception:
        return None


def _enrich(db: Session, d: dict[str, Any]) -> dict[str, Any]:
    status = _identity_approval(db, d.get("identity_id"), d.get("identity_version_id"))
    if status:
        d["approval_status"] = status
    return d


def list_for_scope(
    db: Session,
    project_id: str,
    scope_type: str,
    scope_id: str,
    *,
    include_inherited: bool = False,
    sequence_id: str | None = None,
    scene_id: str | None = None,
    shot_id: str | None = None,
) -> list[dict[str, Any]]:
    require_project(db, project_id)
    if not include_inherited:
        rows = repo.list_bindings(db, project_id, scope_type=scope_type, scope_id=scope_id)
        return [_enrich(db, repo.binding_to_dict(r)) for r in rows]

    chain = ancestor_chain(
        scope_type,
        scope_id,
        project_id=project_id,
        sequence_id=sequence_id,
        scene_id=scene_id or (scope_id if scope_type == "scene" else None),
        shot_id=shot_id or (scope_id if scope_type == "shot" else None),
    )
    by_scope: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for st, sid in chain:
        rows = repo.list_bindings(db, project_id, scope_type=st, scope_id=sid)
        by_scope[(st, sid)] = [_enrich(db, repo.binding_to_dict(r)) for r in rows]
    return merge_inherited(by_scope, chain)


def attach(db: Session, project_id: str, body: dict[str, Any], *, actor: str = "user") -> dict[str, Any]:
    require_project(db, project_id)
    asset_id = body["asset_id"]
    require_asset_in_project(db, project_id, asset_id)
    scope_type = body["scope_type"]
    scope_id = body["scope_id"]
    reference_type = body["reference_type"]
    usage_modes = list(body.get("usage_modes") or [])
    _validate_enums(scope_type, reference_type, usage_modes)

    # Reject attaching revoked/rejected identity refs as new selection
    approval = _identity_approval(db, body.get("identity_id"), body.get("identity_version_id"))
    if approval in ("revoked", "rejected"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "REVOKED_OR_REJECTED",
                "message": "Revoked/rejected identity references cannot be attached for new selection.",
            },
        )

    order = body.get("order_index")
    if order is None:
        order = repo.next_order_index(db, project_id, scope_type, scope_id)

    row = repo.create_binding(
        db,
        {
            "project_id": project_id,
            "asset_id": asset_id,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "reference_type": reference_type,
            "usage_modes": usage_modes,
            "reference_roles": list(body.get("reference_roles") or []),
            "identity_id": body.get("identity_id"),
            "identity_version_id": body.get("identity_version_id"),
            "variant_ids": list(body.get("variant_ids") or []),
            "enabled": bool(body.get("enabled", True)),
            "order_index": order,
            "requested_weight": body.get("requested_weight"),
            "notes": body.get("notes"),
        },
        actor=actor,
    )
    db.commit()
    db.refresh(row)
    return _enrich(db, repo.binding_to_dict(row))


def update(
    db: Session, project_id: str, binding_id: str, patch: dict[str, Any], *, actor: str = "user"
) -> dict[str, Any]:
    require_project(db, project_id)
    row = repo.get_binding(db, project_id, binding_id)
    if not row:
        raise HTTPException(status_code=404, detail="Binding not found")
    if "reference_type" in patch and patch["reference_type"]:
        _validate_enums(row.scope_type, patch["reference_type"], patch.get("usage_modes") or [])
    if "usage_modes" in patch and patch["usage_modes"] is not None:
        _validate_enums(row.scope_type, patch.get("reference_type") or row.reference_type, patch["usage_modes"])
    row = repo.update_binding(db, row, patch, actor=actor)
    db.commit()
    db.refresh(row)
    return _enrich(db, repo.binding_to_dict(row))


def remove(db: Session, project_id: str, binding_id: str, *, actor: str = "user") -> dict[str, Any]:
    require_project(db, project_id)
    row = repo.get_binding(db, project_id, binding_id)
    if not row:
        raise HTTPException(status_code=404, detail="Binding not found")
    repo.soft_delete_binding(db, row, actor=actor)
    db.commit()
    return {"ok": True, "id": binding_id, "assetDeleted": False}


def reorder(db: Session, project_id: str, binding_ids: list[str], *, actor: str = "user") -> list[dict[str, Any]]:
    require_project(db, project_id)
    rows = repo.reorder_bindings(db, project_id, binding_ids, actor=actor)
    db.commit()
    return [_enrich(db, repo.binding_to_dict(r)) for r in rows]


def copy_scope(
    db: Session,
    project_id: str,
    *,
    source_scope_type: str,
    source_scope_id: str,
    target_scope_type: str,
    target_scope_id: str,
    actor: str = "user",
) -> list[dict[str, Any]]:
    require_project(db, project_id)
    source = repo.list_bindings(db, project_id, scope_type=source_scope_type, scope_id=source_scope_id)
    created = []
    for s in source:
        if not s.enabled:
            continue
        d = repo.binding_to_dict(s)
        created.append(
            attach(
                db,
                project_id,
                {
                    "asset_id": d["asset_id"],
                    "scope_type": target_scope_type,
                    "scope_id": target_scope_id,
                    "reference_type": d["reference_type"],
                    "usage_modes": d["usage_modes"],
                    "reference_roles": d["reference_roles"],
                    "identity_id": d.get("identity_id"),
                    "identity_version_id": d.get("identity_version_id"),
                    "variant_ids": d.get("variant_ids") or [],
                    "enabled": True,
                    "notes": d.get("notes"),
                },
                actor=actor,
            )
        )
    return created


def apply_to_scopes(
    db: Session,
    project_id: str,
    binding_ids: list[str],
    target_scopes: list[dict[str, str]],
    *,
    mode: str = "copy",
    actor: str = "user",
) -> dict[str, Any]:
    require_project(db, project_id)
    results: list[dict[str, Any]] = []
    for bid in binding_ids:
        row = repo.get_binding(db, project_id, bid)
        if not row:
            continue
        src = repo.binding_to_dict(row)
        for t in target_scopes:
            if mode == "replace":
                existing = repo.list_bindings(
                    db, project_id, scope_type=t["scope_type"], scope_id=t["scope_id"]
                )
                for e in existing:
                    if e.asset_id == src["asset_id"] and e.reference_type == src["reference_type"]:
                        repo.soft_delete_binding(db, e, actor=actor)
            results.append(
                attach(
                    db,
                    project_id,
                    {
                        "asset_id": src["asset_id"],
                        "scope_type": t["scope_type"],
                        "scope_id": t["scope_id"],
                        "reference_type": src["reference_type"],
                        "usage_modes": src["usage_modes"],
                        "reference_roles": src["reference_roles"],
                        "identity_id": src.get("identity_id"),
                        "identity_version_id": src.get("identity_version_id"),
                        "variant_ids": src.get("variant_ids") or [],
                    },
                    actor=actor,
                )
            )
    return {"ok": True, "created": results}


def readiness(db: Session, project_id: str, scope_type: str, scope_id: str, workflow_key: str) -> dict[str, Any]:
    """Reference Readiness — distinct from Continuity Score."""
    require_project(db, project_id)
    cap = get_capability(workflow_key)
    bindings = list_for_scope(db, project_id, scope_type, scope_id, include_inherited=True)
    enabled = [b for b in bindings if b.get("enabled")]
    support = support_status_for(workflow_key)
    missing_roles: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    if not cap:
        blockers.append(f"Workflow {workflow_key} has no certified ReferenceCapability.")
        support = "unsupported"
    else:
        if len(enabled) > cap.max_count:
            warnings.append(
                f"{len(enabled)} bindings exceed max_count={cap.max_count}; selection will exclude extras with reasons."
            )
        revoked = [b for b in enabled if b.get("approval_status") in ("revoked", "rejected")]
        if revoked:
            warnings.append(f"{len(revoked)} revoked/rejected identity refs will be excluded from new packets.")
        if support == "prompt_guided" and cap and not cap.image_conditioning:
            warnings.append("Workflow is prompt-guided only — do not claim image conditioning.")

    status = "ready"
    if blockers:
        status = "blocked"
    elif warnings or not enabled:
        status = "partial" if enabled else "empty"

    return {
        "referenceReadiness": status,
        "notContinuityScore": True,
        "workflowKey": workflow_key,
        "supportClass": support,
        "bindingCount": len(enabled),
        "maxCount": cap.max_count if cap else 0,
        "missingRoles": missing_roles,
        "blockers": blockers,
        "warnings": warnings,
        "capability": cap.to_public() if cap else None,
    }


def preflight(
    db: Session,
    project_id: str,
    *,
    scope_type: str,
    scope_id: str,
    workflow_key: str,
    override_binding_ids: list[str] | None = None,
    sequence_id: str | None = None,
    scene_id: str | None = None,
) -> dict[str, Any]:
    """Deterministic role-aware selection; never silent drop."""
    require_project(db, project_id)
    cap = get_capability(workflow_key)
    if not cap:
        return {
            "ok": False,
            "supportClass": "unsupported",
            "selected": [],
            "excluded": [],
            "selectionReasons": {},
            "exclusionReasons": {"*": "unsupported_workflow"},
            "continuityPacketId": None,
            "referenceReadiness": readiness(db, project_id, scope_type, scope_id, workflow_key),
        }

    bindings = list_for_scope(
        db,
        project_id,
        scope_type,
        scope_id,
        include_inherited=True,
        sequence_id=sequence_id,
        scene_id=scene_id,
    )
    candidates = [b for b in bindings if b.get("enabled")]
    if override_binding_ids:
        override_set = set(override_binding_ids)
        candidates = [b for b in candidates if b["id"] in override_set] or candidates

    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    selection_reasons: dict[str, str] = {}
    exclusion_reasons: dict[str, str] = {}

    for b in candidates:
        if b.get("approval_status") in ("revoked", "rejected"):
            excluded.append(b)
            exclusion_reasons[b["id"]] = f"excluded_status:{b.get('approval_status')}"
            continue
        if b.get("reference_type") not in cap.supported_types:
            excluded.append(b)
            exclusion_reasons[b["id"]] = "unsupported_type"
            continue
        modes = set(b.get("usage_modes") or [])
        if modes and not (modes & cap.supported_modes):
            excluded.append(b)
            exclusion_reasons[b["id"]] = "unsupported_usage_mode"
            continue
        if len(selected) >= cap.max_count:
            excluded.append(b)
            exclusion_reasons[b["id"]] = "excluded_by_limit"
            continue
        selected.append(b)
        selection_reasons[b["id"]] = "selected_by_order_and_role"

    # Continuity preflight when identity bindings present (packet freeze ownership = Continuity)
    continuity_packet_id = None
    identity_bindings = [
        {
            "identityId": b["identity_id"],
            "identityVersionId": b.get("identity_version_id"),
            "variantIds": b.get("variant_ids") or [],
        }
        for b in selected
        if b.get("identity_id")
    ]
    if identity_bindings:
        try:
            from app.continuity import service as continuity_service

            cont = continuity_service.preflight(
                db,
                project_id,
                {
                    "bindings": identity_bindings,
                    "workflowKey": workflow_key,
                    "scopeType": scope_type,
                    "scopeId": scope_id,
                },
            )
            continuity_packet_id = cont.get("packetId")
        except Exception:
            continuity_packet_id = None

    provenance = {
        "bindingIds": [b["id"] for b in selected],
        "selectedAssetIds": [b["asset_id"] for b in selected],
        "selectedIdentityVersionIds": [b["identity_version_id"] for b in selected if b.get("identity_version_id")],
        "continuityPacketId": continuity_packet_id,
        "workflowCapabilityKey": workflow_key,
        "selectionReasons": selection_reasons,
        "excludedReferenceIds": [b["id"] for b in excluded],
        "exclusionReasons": exclusion_reasons,
    }

    return {
        "ok": True,
        "supportClass": cap.support_class,
        "imageConditioning": cap.image_conditioning,
        "selected": selected,
        "excluded": excluded,
        "selectionReasons": selection_reasons,
        "exclusionReasons": exclusion_reasons,
        "continuityPacketId": continuity_packet_id,
        "provenance": provenance,
        "referenceReadiness": readiness(db, project_id, scope_type, scope_id, workflow_key),
        "capability": cap.to_public(),
    }


def asset_usage(db: Session, project_id: str, asset_id: str) -> dict[str, Any]:
    require_project(db, project_id)
    require_asset_in_project(db, project_id, asset_id)
    rows = [r for r in repo.list_bindings(db, project_id) if r.asset_id == asset_id]
    return {
        "assetId": asset_id,
        "activeBindingCount": len(rows),
        "bindings": [_enrich(db, repo.binding_to_dict(r)) for r in rows],
        "deleteBlocked": len(rows) > 0,
    }


def capabilities() -> list[dict[str, Any]]:
    return list_capabilities()
