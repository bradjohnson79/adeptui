"""Scene Reference Binding domain service."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import repository as repo
from .aliases import display_token, media_kind_for, sanitize_alias, unique_alias
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
    kind = d.get("media_kind") or media_kind_for(str(d.get("reference_type") or ""), asset_kind=None)
    d["media_kind"] = kind
    alias = sanitize_alias(d.get("alias") or d.get("asset_name") or "")
    d["alias"] = alias or d.get("alias")
    d["display_token"] = display_token(alias, kind) if alias else None
    broken = False
    reason = None
    asset_id = d.get("asset_id")
    if asset_id:
        try:
            from app.db import Asset

            asset = db.get(Asset, asset_id)
            if asset is None:
                broken = True
                reason = "missing_asset"
            else:
                d.setdefault("asset_name", getattr(asset, "tag", None) or getattr(asset, "filename", None))
        except Exception:
            broken = True
            reason = "missing_asset"
    if kind == "entity" and d.get("identity_id"):
        try:
            from app.character_identity.models import CharacterProfileRow

            ident = db.get(CharacterProfileRow, d["identity_id"])
            if ident is None:
                broken = True
                reason = reason or "missing_entity"
        except Exception:
            pass
    d["broken"] = broken
    d["broken_reason"] = reason
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

    asset_kind = None
    try:
        from app.db import Asset

        asset_row = db.get(Asset, asset_id)
        asset_kind = getattr(asset_row, "kind", None) if asset_row else None
        if not body.get("alias"):
            body = {**body, "alias": getattr(asset_row, "tag", None) or getattr(asset_row, "filename", None)}
    except Exception:
        pass

    media_kind = body.get("media_kind") or media_kind_for(reference_type, asset_kind=asset_kind)
    if media_kind not in ("entity", "image", "video"):
        raise HTTPException(status_code=400, detail={"code": "INVALID_MEDIA_KIND", "message": str(media_kind)})
    restored = repo.find_soft_deleted_binding(
        db,
        project_id,
        scope_type=scope_type,
        scope_id=scope_id,
        asset_id=asset_id,
        reference_type=reference_type,
    )
    alias, alias_adjusted = unique_alias(
        db,
        project_id,
        body.get("alias"),
        fallback=str(body.get("alias") or reference_type or "Reference"),
        exclude_id=restored.id if restored is not None else None,
    )
    if restored is not None:
        restored = repo.restore_binding(
            db,
            restored,
            {
                "alias": alias,
                "media_kind": media_kind,
                "usage_modes": usage_modes,
                "reference_roles": list(body.get("reference_roles") or []),
                "enabled": bool(body.get("enabled", True)),
            },
            actor=actor,
        )
        db.commit()
        db.refresh(restored)
        out = _enrich(db, repo.binding_to_dict(restored))
        out["alias_adjusted"] = alias_adjusted
        return out

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
            "alias": alias,
            "media_kind": media_kind,
        },
        actor=actor,
    )
    db.commit()
    db.refresh(row)
    out = _enrich(db, repo.binding_to_dict(row))
    out["alias_adjusted"] = alias_adjusted
    return out


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
    if "media_kind" in patch and patch["media_kind"] is not None:
        if patch["media_kind"] not in ("entity", "image", "video"):
            raise HTTPException(status_code=400, detail={"code": "INVALID_MEDIA_KIND", "message": str(patch["media_kind"])})
    alias_adjusted = False
    if "alias" in patch and patch["alias"] is not None:
        desired = sanitize_alias(patch["alias"])
        if not desired:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ALIAS", "message": "Alias cannot be empty."})
        unique, adjusted = unique_alias(db, project_id, desired, exclude_id=binding_id, fallback=desired)
        if adjusted and desired.lower() != unique.lower():
            # Explicit rename to a taken token is refused with a suggestion.
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ALIAS_TAKEN",
                    "message": f"{desired} is already used in this project.",
                    "suggested_alias": unique,
                },
            )
        patch = {**patch, "alias": unique}
        alias_adjusted = adjusted
    row = repo.update_binding(db, row, patch, actor=actor)
    db.commit()
    db.refresh(row)
    out = _enrich(db, repo.binding_to_dict(row))
    out["alias_adjusted"] = alias_adjusted
    return out


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
    entity_refs = _entity_refs_for_asset(db, project_id, asset_id)
    return {
        "assetId": asset_id,
        "activeBindingCount": len(rows),
        "bindings": [_enrich(db, repo.binding_to_dict(r)) for r in rows],
        "entityRefCount": len(entity_refs),
        "entityRefs": entity_refs,
        "deleteBlocked": len(rows) > 0 or len(entity_refs) > 0,
    }


def _entity_refs_for_asset(db: Session, project_id: str, asset_id: str) -> list[dict[str, Any]]:
    """Scan every canonical downstream store for references to asset_id.

    This is the delete-guard scan (CDX-063): scene reference bindings alone are
    not enough. Each entry carries kind/entityType/entityId/entityName/field/
    label so the delete route can name the referencing entity to the creator.
    Every hit blocks a plain delete; force delete detaches every hit explicitly
    (see detach_asset_references). All store scans are defensive (try/except) so
    a store whose tables are not present in a given DB contributes no refs.
    """
    refs: list[dict[str, Any]] = []

    def _add(kind: str, entity_type: str, entity_id: str, entity_name: str, field: str, label: str) -> None:
        refs.append(
            {
                "kind": kind,
                "entityType": entity_type,
                "entityId": entity_id or "",
                "entityName": entity_name or entity_id or "",
                "field": field,
                "label": label,
            }
        )

    # 1) Character identity references (character_reference_assets) — approved
    #    identity images incl. hero_identity.
    try:
        from ..character_identity.models import CharacterProfileRow, CharacterReferenceAssetRow

        for r in db.query(CharacterReferenceAssetRow).filter(CharacterReferenceAssetRow.asset_id == asset_id).all():
            name = ""
            profile = db.get(CharacterProfileRow, r.character_profile_id)
            if profile is not None:
                name = profile.name or ""
            _add(
                "character_identity",
                "character",
                r.character_profile_id,
                name,
                "asset_id",
                "Character identity image (role: " + (r.reference_role or "reference") + ")",
            )
    except Exception:
        pass

    # 2) Character prop library assets (character_props.library_asset_id).
    try:
        from ..character_identity.models import CharacterProfileRow, CharacterPropRow

        for r in db.query(CharacterPropRow).filter(CharacterPropRow.library_asset_id == asset_id).all():
            name = ""
            profile = db.get(CharacterProfileRow, r.character_profile_id)
            if profile is not None:
                name = profile.name or ""
            _add(
                "character_prop",
                "character",
                r.character_profile_id,
                name,
                "library_asset_id",
                "Character prop identity (prop: " + (r.name or r.id) + ")",
            )
    except Exception:
        pass

    # 3) Prop entities (approved_asset_id / library_asset_id mirror).
    try:
        from ..spatial_map.ers_persistence import list_prop_entities

        for prop in list_prop_entities(db, project_id):
            pname = prop.display_label or prop.tag or prop.id
            if (prop.approved_asset_id or "").strip() == asset_id:
                _add("prop_identity", "prop", prop.id, pname, "approved_asset_id", "Approved prop identity (#" + (prop.tag or prop.id) + ")")
            if (prop.library_asset_id or "").strip() == asset_id:
                _add("prop_identity", "prop", prop.id, pname, "library_asset_id", "Prop identity mirror (#" + (prop.tag or prop.id) + ")")
    except Exception:
        pass

    # 4) Spatial map documents (document_json) — background / source /
    #    character+prop placements / collage views. Queried directly on
    #    SpatialMapDocumentRow so spatial_map/service.py stays untouched.
    try:
        import json as _json

        from ..spatial_map.models import SpatialMapDocumentRow

        for row in db.query(SpatialMapDocumentRow).filter(SpatialMapDocumentRow.project_id == project_id).all():
            try:
                data = _json.loads(row.document_json or "{}")
            except Exception:
                data = {}
            if not isinstance(data, dict):
                continue
            dname = data.get("title") or row.title or row.id
            if data.get("backgroundAssetId") == asset_id:
                _add("spatial_map", "spatial_map", row.id, dname, "backgroundAssetId", "Spatial map background asset")
            if (data.get("originalEnvironmentReferenceAssetId") or "") == asset_id:
                _add("spatial_map", "spatial_map", row.id, dname, "originalEnvironmentReferenceAssetId", "Spatial map source reference")
            for c in data.get("characters") or []:
                if isinstance(c, dict) and (c.get("assetId") or "") == asset_id:
                    _add("spatial_map", "spatial_map", row.id, dname, "characters[].assetId", "Spatial map character placement (" + str(c.get("label") or c.get("id")) + ")")
            for p in data.get("props") or []:
                if isinstance(p, dict) and (p.get("assetId") or "") == asset_id:
                    _add("spatial_map", "spatial_map", row.id, dname, "props[].assetId", "Spatial map prop placement (" + str(p.get("label") or p.get("id")) + ")")
            coll = data.get("collage")
            if isinstance(coll, dict):
                for v in coll.get("views") or []:
                    if isinstance(v, dict) and (v.get("assetId") or "") == asset_id:
                        _add("spatial_map", "spatial_map", row.id, dname, "collage.views[].assetId", "Spatial map collage view (" + str(v.get("direction") or v.get("id")) + ")")
    except Exception:
        pass

    # 5) ERS sheets (file-backed environment_reference_sheet store).
    try:
        from ..environment_reference_sheet.store import list_sheets

        for sheet in list_sheets(project_id):
            sname = sheet.name or sheet.sheetId
            for view in sheet.directionalViews or []:
                if (view.approvedAssetId or "") == asset_id:
                    _add("ers_sheet", "ers_sheet", sheet.sheetId, sname, "directionalViews[].approvedAssetId", "ERS approved view (" + str(getattr(view, "direction", "") or view.title) + ")")
            comp = getattr(sheet, "composition", None)
            rendered = getattr(comp, "renderedAssetIds", None) or {}
            for _, aid in (rendered or {}).items():
                if aid == asset_id:
                    _add("ers_sheet", "ers_sheet", sheet.sheetId, sname, "composition.renderedAssetIds", "ERS rendered asset")
            if (getattr(sheet, "ers_composite_asset_id", None) or "") == asset_id:
                _add("ers_sheet", "ers_sheet", sheet.sheetId, sname, "ers_composite_asset_id", "ERS composite asset")
            for ex in getattr(sheet, "exports", None) or []:
                if (getattr(ex, "assetId", None) or "") == asset_id:
                    _add("ers_sheet", "ers_sheet", sheet.sheetId, sname, "exports[].assetId", "ERS export asset")
            threed = getattr(sheet, "optionalThreeD", None)
            if threed is not None and (getattr(threed, "assetId", None) or "") == asset_id:
                _add("ers_sheet", "ers_sheet", sheet.sheetId, sname, "optionalThreeD.assetId", "ERS optional-3D asset")
    except Exception:
        pass

    # 6) ERS packages (trait-backed spatial_ers store).
    try:
        from ..spatial_map.ers_persistence import list_ers_packages

        for pkg in list_ers_packages(db, project_id):
            pname = pkg.id
            if (pkg.atlas_asset_id or "") == asset_id:
                _add("ers_package", "ers_package", pkg.id, pname, "atlas_asset_id", "ERS atlas asset")
            if (pkg.master_environment_asset_id or "") == asset_id:
                _add("ers_package", "ers_package", pkg.id, pname, "master_environment_asset_id", "ERS master environment asset")
            for direction, aid in (pkg.directional_assets or {}).items():
                if (aid or "") == asset_id:
                    _add("ers_package", "ers_package", pkg.id, pname, "directional_assets[" + direction + "]", "ERS directional view (" + direction + ")")
            if (pkg.ers_composite_asset_id or "") == asset_id:
                _add("ers_package", "ers_package", pkg.id, pname, "ers_composite_asset_id", "ERS composite asset")
    except Exception:
        pass

    # 7) Scene shots — Timeline exports only. Approved take state
    #    (takeState.approved_asset_id) is owned by the scene_creator delete
    #    flow, which clears it in the same operation; blocking there would
    #    regress deleting an approved take.
    try:
        from ..spatial_map.ers_persistence import list_scene_shots

        for shot in list_scene_shots(db, project_id):
            ts = dict((shot.take_memory.takeState if shot.take_memory else None) or {})
            if (ts.get("lastTimelineAssetId") or "") == asset_id:
                _add("scene_shot", "scene_shot", shot.id, shot.id, "takeState.lastTimelineAssetId", "Scene shot exported to Timeline")
    except Exception:
        pass

    # 8) Scene rows — storyboard start/middle/end frames (scene visual refs).
    try:
        from ..db import Scene

        for scene in db.query(Scene).filter(Scene.project_id == project_id).all():
            for field, fname in (
                ("start_asset_id", "Start frame"),
                ("middle_asset_id", "Middle frame"),
                ("end_asset_id", "End frame"),
                ("audio_asset_id", "Audio"),
                ("lipsync_audio_asset_id", "Lipsync audio"),
            ):
                if (getattr(scene, field) or "") == asset_id:
                    _add("scene_visual", "scene", scene.id, scene.name, field, "Scene visual reference (" + fname + ")")
    except Exception:
        pass

    # 9) Multi-shot approved shots.
    try:
        from ..image_pipeline.multi_shot.models import MultiShotRow

        for row in (
            db.query(MultiShotRow)
            .filter(MultiShotRow.project_id == project_id, MultiShotRow.approved_asset_id == asset_id)
            .all()
        ):
            _add("multi_shot", "multi_shot", row.id, row.title, "approved_asset_id", "Approved multi-shot image")
    except Exception:
        pass

    # 10) Asset graph edges touching this node.
    try:
        from ..asset_graph import AssetEdge

        for e in db.query(AssetEdge).filter((AssetEdge.from_id == asset_id) | (AssetEdge.to_id == asset_id)).all():
            _add(
                "asset_edge",
                "asset_edge",
                e.id,
                e.id,
                "from_id" if e.from_id == asset_id else "to_id",
                "Asset graph edge (" + e.relation + ")",
            )
    except Exception:
        pass

    return refs


def detach_asset_references(db: Session, project_id: str, asset_id: str) -> list[dict[str, Any]]:
    """Force-delete support: explicitly detach every canonical reference.

    Returns a truthful list of what was detached (each entry mirrors the usage
    ref plus an action). Raises HTTPException(409) if any store cannot be
    cleaned, so the caller aborts the delete instead of leaving a dangling
    reference. The route must call this BEFORE removing the Asset row.
    """
    refs = _entity_refs_for_asset(db, project_id, asset_id)
    detached: list[dict[str, Any]] = []

    def _detach(ref: dict[str, Any], action: str) -> None:
        entry = dict(ref)
        entry["action"] = action
        detached.append(entry)

    # 0) Scene reference bindings — soft-delete so reads never surface them.
    try:
        bindings = [b for b in repo.list_bindings(db, project_id) if b.asset_id == asset_id]
        for b in bindings:
            repo.soft_delete_binding(db, b, actor="system")
        if bindings:
            _detach(
                {
                    "kind": "scene_reference",
                    "entityType": "binding",
                    "entityId": ",".join(b.id for b in bindings),
                    "entityName": ",".join(b.scope_type + ":" + b.scope_id for b in bindings),
                    "field": "asset_id",
                    "label": "Scene reference binding(s) (" + str(len(bindings)) + ")",
                },
                "removed",
            )
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ASSET_DELETE_DETACH_FAILED",
                "message": "Could not detach scene reference bindings before force-delete: " + str(exc),
                "assetId": asset_id,
            },
        ) from exc

    for ref in refs:
        kind = ref["kind"]
        try:
            if kind == "character_identity":
                # character_reference_assets.asset_id is NOT NULL — remove the
                # binding row (explicit detach; approval effectively revoked).
                from ..character_identity.models import CharacterReferenceAssetRow

                db.query(CharacterReferenceAssetRow).filter(CharacterReferenceAssetRow.asset_id == asset_id).delete(
                    synchronize_session=False
                )
                _detach(ref, "removed_binding")
            elif kind == "character_prop":
                from ..character_identity.models import CharacterPropRow

                db.query(CharacterPropRow).filter(CharacterPropRow.library_asset_id == asset_id).update(
                    {"library_asset_id": None}, synchronize_session=False
                )
                _detach(ref, "nulled")
            elif kind == "prop_identity":
                from ..spatial_map.ers_persistence import list_prop_entities, save_prop_entity

                for prop in list_prop_entities(db, project_id):
                    changed = False
                    if (prop.approved_asset_id or "").strip() == asset_id:
                        prop.approved_asset_id = None
                        changed = True
                    if (prop.library_asset_id or "").strip() == asset_id:
                        prop.library_asset_id = ""
                        changed = True
                    if changed:
                        save_prop_entity(db, project_id, prop)
                _detach(ref, "nulled")
            elif kind == "spatial_map":
                import json as _json

                from ..spatial_map.models import SpatialMapDocumentRow

                for row in db.query(SpatialMapDocumentRow).filter(SpatialMapDocumentRow.project_id == project_id).all():
                    try:
                        data = _json.loads(row.document_json or "{}")
                    except Exception:
                        continue
                    if not isinstance(data, dict):
                        continue
                    changed = False
                    for key in ("backgroundAssetId", "originalEnvironmentReferenceAssetId"):
                        if data.get(key) == asset_id:
                            data[key] = None
                            changed = True
                    for grp in ("characters", "props"):
                        for item in data.get(grp) or []:
                            if isinstance(item, dict) and (item.get("assetId") or "") == asset_id:
                                item["assetId"] = None
                                changed = True
                    coll = data.get("collage")
                    if isinstance(coll, dict):
                        for v in coll.get("views") or []:
                            if isinstance(v, dict) and (v.get("assetId") or "") == asset_id:
                                v["assetId"] = None
                                changed = True
                    if changed:
                        row.document_json = _json.dumps(data, ensure_ascii=False)
                _detach(ref, "nulled")
            elif kind == "ers_sheet":
                from ..environment_reference_sheet.store import list_sheets, save_sheet

                for sheet in list_sheets(project_id):
                    changed = False
                    for view in sheet.directionalViews or []:
                        if (view.approvedAssetId or "") == asset_id:
                            view.approvedAssetId = None
                            changed = True
                    comp = getattr(sheet, "composition", None)
                    rendered = getattr(comp, "renderedAssetIds", None) or {}
                    for key in [k for k, v in (rendered or {}).items() if v == asset_id]:
                        rendered.pop(key, None)
                        changed = True
                    if (getattr(sheet, "ers_composite_asset_id", None) or "") == asset_id:
                        sheet.ers_composite_asset_id = None
                        changed = True
                    for ex in getattr(sheet, "exports", None) or []:
                        if (getattr(ex, "assetId", None) or "") == asset_id:
                            ex.assetId = None
                            changed = True
                    threed = getattr(sheet, "optionalThreeD", None)
                    if threed is not None and (getattr(threed, "assetId", None) or "") == asset_id:
                        threed.assetId = None
                        changed = True
                    if changed:
                        save_sheet(sheet)
                _detach(ref, "nulled")
            elif kind == "ers_package":
                from ..spatial_map.ers_persistence import list_ers_packages, save_ers_package

                for pkg in list_ers_packages(db, project_id):
                    changed = False
                    if (pkg.atlas_asset_id or "") == asset_id:
                        pkg.atlas_asset_id = None
                        changed = True
                    if (pkg.master_environment_asset_id or "") == asset_id:
                        pkg.master_environment_asset_id = None
                        changed = True
                    for direction, aid in list((pkg.directional_assets or {}).items()):
                        if (aid or "") == asset_id:
                            pkg.directional_assets[direction] = None
                            changed = True
                    if (pkg.ers_composite_asset_id or "") == asset_id:
                        pkg.ers_composite_asset_id = None
                        changed = True
                    if changed:
                        save_ers_package(db, project_id, pkg)
                _detach(ref, "nulled")
            elif kind == "scene_shot":
                from ..spatial_map.ers_persistence import list_scene_shots, save_scene_shot

                for shot in list_scene_shots(db, project_id):
                    if not shot.take_memory:
                        continue
                    ts = dict(shot.take_memory.takeState or {})
                    if (ts.get("lastTimelineAssetId") or "") == asset_id:
                        ts.pop("lastTimelineAssetId", None)
                        shot.take_memory.takeState = ts
                        save_scene_shot(db, project_id, shot)
                _detach(ref, "removed")
            elif kind == "scene_visual":
                from ..db import Scene

                field = ref["field"]
                db.query(Scene).filter(
                    Scene.project_id == project_id, getattr(Scene, field) == asset_id
                ).update({field: None}, synchronize_session=False)
                _detach(ref, "nulled")
            elif kind == "multi_shot":
                from ..image_pipeline.multi_shot.models import MultiShotRow

                db.query(MultiShotRow).filter(
                    MultiShotRow.project_id == project_id, MultiShotRow.approved_asset_id == asset_id
                ).update({"approved_asset_id": None}, synchronize_session=False)
                _detach(ref, "nulled")
            elif kind == "asset_edge":
                # Edges are lineage, not creator-visible links; they are removed
                # together with AssetVersion rows by cleanup_asset_lineage on the
                # actual delete, and disclosed via the edgesDeleted count.
                continue
            else:
                _detach(ref, "unknown")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ASSET_DELETE_DETACH_FAILED",
                    "message": "Could not detach asset reference (" + kind + ") before force-delete: " + str(exc),
                    "assetId": asset_id,
                    "reference": ref,
                },
            ) from exc

    return detached


def cleanup_asset_lineage(db: Session, asset_id: str) -> dict[str, int]:
    """Remove AssetVersion + AssetEdge rows for a deleted asset (CDX-063)."""
    from ..asset_graph import AssetEdge, AssetVersion

    versions = db.query(AssetVersion).filter(AssetVersion.asset_id == asset_id).delete(synchronize_session=False)
    edges = db.query(AssetEdge).filter((AssetEdge.from_id == asset_id) | (AssetEdge.to_id == asset_id)).delete(
        synchronize_session=False
    )
    return {"versionsDeleted": int(versions or 0), "edgesDeleted": int(edges or 0)}


def capabilities() -> list[dict[str, Any]]:
    return list_capabilities()
