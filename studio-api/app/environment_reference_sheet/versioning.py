"""ERS version lineage, approval authority, and canonical pointer.

Owns: create_ers_version_from_derivative, approve_ers_version, list/compare/
revert-select, project-level approvedCanonicalSheetId.

Does NOT: mutate approved parent composites; auto-approve; run Comfy inpaint
(Backend owns edit/enqueue -> derivativeOnly).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .contracts import (
    ERSApprovalRequirement,
    EnvironmentReferenceSheet,
    utc_now,
)
from .store import (
    get_canonical_sheet_id,
    list_sheets,
    load_sheet,
    save_sheet,
    set_canonical_sheet_id,
)


def _composite_id(sheet: EnvironmentReferenceSheet | None) -> str:
    if sheet is None:
        return ""
    cid = str(getattr(sheet, "ers_composite_asset_id", "") or "").strip()
    if cid:
        return cid
    rendered = getattr(getattr(sheet, "composition", None), "renderedAssetIds", None) or {}
    if isinstance(rendered, dict):
        for key in ("composite", "png", "sheet"):
            val = str(rendered.get(key) or "").strip()
            if val:
                return val
    return ""


def _root_id(sheet: EnvironmentReferenceSheet) -> str:
    root = str(getattr(sheet, "rootSheetId", None) or "").strip()
    if root:
        return root
    return str(sheet.sheetId)


def _next_version_number(project_id: str, root_sheet_id: str) -> int:
    versions = list_versions(project_id, root_sheet_id)
    nums = [int(getattr(s, "versionNumber", 1) or 1) for s in versions]
    return (max(nums) if nums else 0) + 1


def list_versions(project_id: str, sheet_id: str) -> list[EnvironmentReferenceSheet]:
    """All sheets in the lineage of sheet_id (by rootSheetId), oldest to newest."""
    anchor = load_sheet(project_id, sheet_id)
    if anchor is None:
        return []
    root = _root_id(anchor)
    matched = [
        s
        for s in list_sheets(project_id)
        if _root_id(s) == root or str(s.sheetId) == root
    ]
    matched.sort(key=lambda s: (int(getattr(s, "versionNumber", 1) or 1), str(s.sheetId)))
    return matched


def create_ers_version_from_derivative(
    project_id: str,
    parent_sheet_id: str,
    *,
    derivative_asset_id: str,
    edit_prompt: str | None = None,
    actor: str = "creator",
) -> dict[str, Any]:
    """Create NEW draft ERS vN from a derivative asset. Never mutates parent pixels/id."""
    derivative_asset_id = str(derivative_asset_id or "").strip()
    if not derivative_asset_id:
        raise ValueError("derivativeAssetId is required")

    parent = load_sheet(project_id, parent_sheet_id)
    if parent is None:
        raise FileNotFoundError(f"Environment Reference Sheet not found: {parent_sheet_id}")

    parent_composite_before = _composite_id(parent)
    root = _root_id(parent)
    version_number = _next_version_number(project_id, root)

    payload = parent.model_dump(mode="json")
    new_id = str(uuid4())
    payload["sheetId"] = new_id
    payload["status"] = "draft"
    payload["parentSheetId"] = parent.sheetId
    payload["rootSheetId"] = root
    payload["versionNumber"] = version_number
    payload["createdAt"] = utc_now()
    payload["updatedAt"] = utc_now()
    payload["ers_composite_asset_id"] = derivative_asset_id

    composition = dict(payload.get("composition") or {})
    rendered = dict(composition.get("renderedAssetIds") or {})
    rendered["composite"] = derivative_asset_id
    rendered["png"] = derivative_asset_id
    composition["renderedAssetIds"] = rendered
    composition["lastRenderedAt"] = utc_now()
    if edit_prompt:
        composition["heroSummary"] = f"Edit v{version_number}: {str(edit_prompt).strip()[:240]}"
    payload["composition"] = composition

    provenance = dict(payload.get("provenance") or {})
    provenance.update(
        {
            "createdAt": utc_now(),
            "actor": actor,
            "source": "ers_version_from_derivative",
            "note": "New ERS version from edit derivative; parent frozen",
            "details": {
                "parentSheetId": parent.sheetId,
                "parentCompositeAssetId": parent_composite_before,
                "derivativeAssetId": derivative_asset_id,
                "editPrompt": (str(edit_prompt).strip() if edit_prompt else None),
                "versionNumber": version_number,
            },
        }
    )
    payload["provenance"] = provenance

    creation_plan = dict(payload.get("creationPlan") or {})
    creation_plan["approvalRequirements"] = [
        ERSApprovalRequirement(
            kind="ers-version-approve",
            status="required",
            reason="Creator must Approve this ERS version before it becomes downstream canonical.",
            creatorTip="Review the edit, then Approve to promote this version for Timeline / Image Gen / Storyboard / Co-Director.",
        ).model_dump(mode="json")
    ]
    payload["creationPlan"] = creation_plan

    child = EnvironmentReferenceSheet.model_validate(payload)
    save_sheet(child)

    parent_after = load_sheet(project_id, parent_sheet_id)
    parent_composite_after = _composite_id(parent_after)
    if parent_composite_before != parent_composite_after:
        raise RuntimeError("Invariant violated: parent composite mutated during version create")

    canonical = get_canonical_sheet_id(project_id)
    return {
        "sheet": child.model_dump(mode="json"),
        "summary": version_summary(child, canonical_id=canonical),
        "parentSheetId": parent.sheetId,
        "parentCompositeAssetId": parent_composite_before,
        "versionSheetId": child.sheetId,
        "versionNumber": version_number,
        "derivativeAssetId": derivative_asset_id,
        "status": child.status,
        "approved": False,
        "canonicalSheetId": canonical,
        "autoApproved": False,
    }


def approve_ers_version(
    project_id: str,
    version_sheet_id: str,
    *,
    approved_by: str = "creator",
) -> dict[str, Any]:
    """Sole writer that flips downstream canonical to this sheet."""
    sheet = load_sheet(project_id, version_sheet_id)
    if sheet is None:
        raise FileNotFoundError(f"Environment Reference Sheet not found: {version_sheet_id}")

    composite = _composite_id(sheet)
    if not composite:
        raise ValueError("Cannot approve an ERS version without a composite asset")

    previous_canonical = get_canonical_sheet_id(project_id)

    sheet.status = "approved"
    sheet.updatedAt = utc_now()

    plan = sheet.creationPlan
    reqs = list(getattr(plan, "approvalRequirements", None) or [])
    stamped = False
    for req in reqs:
        if getattr(req, "kind", "") in {"ers-version-approve", "ers-sheet-approve", "ers-create"}:
            req.status = "approved"
            req.approvedBy = approved_by
            req.approvedAt = utc_now()
            stamped = True
    if not stamped:
        reqs.append(
            ERSApprovalRequirement(
                kind="ers-sheet-approve",
                status="approved",
                reason="Creator approved this ERS sheet as downstream canonical.",
                approvedBy=approved_by,
                approvedAt=utc_now(),
            )
        )
    plan.approvalRequirements = reqs
    sheet.creationPlan = plan

    if not str(getattr(sheet, "rootSheetId", None) or "").strip():
        sheet.rootSheetId = sheet.sheetId
    if int(getattr(sheet, "versionNumber", 0) or 0) < 1:
        sheet.versionNumber = 1

    save_sheet(sheet)
    set_canonical_sheet_id(
        project_id,
        sheet.sheetId,
        updated_by=approved_by,
        reason="creator_approve",
    )

    return {
        "sheet": sheet.model_dump(mode="json"),
        "summary": version_summary(sheet, canonical_id=sheet.sheetId),
        "approvedSheetId": sheet.sheetId,
        "previousCanonicalSheetId": previous_canonical,
        "canonicalSheetId": sheet.sheetId,
        "compositeAssetId": composite,
        "autoApproved": False,
    }


def compare_versions(
    project_id: str,
    sheet_id_a: str,
    sheet_id_b: str,
) -> dict[str, Any]:
    a = load_sheet(project_id, sheet_id_a)
    b = load_sheet(project_id, sheet_id_b)
    if a is None or b is None:
        missing = sheet_id_a if a is None else sheet_id_b
        raise FileNotFoundError(f"Environment Reference Sheet not found: {missing}")
    canonical = get_canonical_sheet_id(project_id)
    return {
        "a": version_summary(a, canonical_id=canonical),
        "b": version_summary(b, canonical_id=canonical),
        "sameLineage": _root_id(a) == _root_id(b),
        "canonicalSheetId": canonical,
    }


def revert_select_version(
    project_id: str,
    version_sheet_id: str,
    *,
    approved_by: str = "creator",
) -> dict[str, Any]:
    """Revert-select: promote a prior version via the Approve path (no auto-approve)."""
    sheet = load_sheet(project_id, version_sheet_id)
    if sheet is None:
        raise FileNotFoundError(f"Environment Reference Sheet not found: {version_sheet_id}")
    result = approve_ers_version(
        project_id,
        version_sheet_id,
        approved_by=approved_by,
    )
    result["revertSelected"] = True
    result["action"] = "revert_select"
    return result


def version_summary(
    sheet: EnvironmentReferenceSheet,
    *,
    canonical_id: str | None = None,
) -> dict[str, Any]:
    composite = _composite_id(sheet)
    sid = str(sheet.sheetId)
    is_canonical = bool(canonical_id) and sid == str(canonical_id)
    return {
        "sheetId": sid,
        "versionSheetId": sid,  # FE alias — same as sheetId (select draft without approve)
        "projectId": sheet.projectId,
        "name": sheet.name,
        "status": sheet.status,
        "versionNumber": int(getattr(sheet, "versionNumber", 1) or 1),
        "parentSheetId": getattr(sheet, "parentSheetId", None),
        "rootSheetId": _root_id(sheet),
        "ers_composite_asset_id": composite or None,
        "composite": composite or None,  # FE alias
        "derivativeAssetId": composite or None,  # version composite (= edit derivative on draft vN)
        "has_reference": bool(composite),
        "isCanonical": is_canonical,
        "approved": sheet.status == "approved" or is_canonical,
        "updatedAt": sheet.updatedAt,
        "createdAt": sheet.createdAt,
        "isGlobal": bool(getattr(sheet, "isGlobal", False)),
        "is_global": bool(getattr(sheet, "isGlobal", False)),
        "recordKind": str(getattr(sheet, "recordKind", None) or "original"),
        "isEditableMaster": bool(getattr(sheet, "isEditableMaster", True)),
        "isSnapshot": str(getattr(sheet, "recordKind", "") or "").lower() == "snapshot"
            or bool(getattr(sheet, "snapshotOfSheetId", None)),
        "snapshotNumber": getattr(sheet, "snapshotNumber", None),
        "snapshotOfSheetId": getattr(sheet, "snapshotOfSheetId", None),
        "directionMovement": (str(getattr(sheet, "directionMovement", None) or "").strip() or None),
        "movementSequenceIndex": getattr(sheet, "movementSequenceIndex", None),
        "snapshotSequenceHighWater": int(getattr(sheet, "snapshotSequenceHighWater", 0) or 0),
    }


def resolve_canonical_sheet(project_id: str) -> EnvironmentReferenceSheet | None:
    """Downstream authority: approved canonical pointer only (never draft composite)."""
    canonical_id = get_canonical_sheet_id(project_id)
    if canonical_id:
        sheet = load_sheet(project_id, canonical_id)
        if sheet is not None and sheet.status == "approved":
            return sheet

    approved = [s for s in list_sheets(project_id) if s.status == "approved"]
    if not approved:
        return None
    return approved[0]


def sheet_is_frozen_for_inplace_persist(sheet: EnvironmentReferenceSheet) -> bool:
    """Approved / canonical sheets must not receive in-place composite overwrite."""
    if str(getattr(sheet, "status", "") or "") == "approved":
        return True
    canonical = get_canonical_sheet_id(str(sheet.projectId))
    if canonical and str(sheet.sheetId) == str(canonical):
        return True
    return False
