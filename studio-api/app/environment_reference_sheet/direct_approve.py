"""Direct approval: creator approves an attached reference image as the
official environment visual for an existing environment identity (Path A).

Path B (generated ERS) reaches the same end state through generation +
``approve_ers_version``. Both paths converge on ONE contract:

- ``sheet.ers_composite_asset_id``  — official environment visual asset
- ``sheet.status == "approved"``    — approval state (sole writer:
  ``versioning.approve_ers_version``)
- ``canonical.json`` pointer        — downstream canonical authority
- ``sync_environment_scope``        — creator-scope identity asset
- plan ``referenceImageAssetId``    — the creator-attached reference image
  (kept equal to the approved asset on this path; never carries approval
  state itself)

No second schema. No duplicate environment. Library bytes are never deleted.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .contracts import ERSApprovalRequirement, EnvironmentReferenceSheet, utc_now
from .store import (
    clear_canonical_sheet_id,
    get_canonical_sheet_id,
    load_visible_sheet,
    save_sheet,
    sync_environment_scope,
)
from .versioning import approve_ers_version, version_summary

_APPROVE_REQUIREMENT_KINDS = {"ers-version-approve", "ers-sheet-approve", "ers-create"}


def _load_owned_sheet(db: Session, project_id: str, sheet_id: str) -> EnvironmentReferenceSheet:
    sheet = load_visible_sheet(db, project_id, sheet_id)
    if sheet is None:
        raise FileNotFoundError("Environment Reference Sheet not found")
    if sheet.projectId != project_id:
        raise PermissionError("Global environments can only be edited from the project that created them.")
    return sheet


def _require_project_image_asset(db: Session, project_id: str, asset_id: str):
    from ..scene_references.permissions import require_asset_in_project

    asset = require_asset_in_project(db, project_id, asset_id)
    kind_token = str(getattr(asset, "kind", "") or "").lower()
    if kind_token and kind_token not in {"image", "img", "still"}:
        raise ValueError("NOT_AN_IMAGE: Approve as Environment works on pictures. Use a Library image.")
    return asset


def _stamp_asset_as_environment(asset: Any) -> None:
    """Classify the Library asset as an environment reference (same stamp as
    Preview Monitor → Approve as Environment). Never deletes bytes.

    An explicit Timeline override (approvedAs is a different image role) is
    left in place. Clearing that override returns this saved environment.
    """
    from ..scene_references.approve_as import _KIND_SPEC, _stamp_asset
    from ..scene_references.reference_eligibility import explicit_image_role

    current = explicit_image_role(getattr(asset, "prompt_meta_json", None))
    if current and current != "environment":
        return
    _stamp_asset(asset, kind="environment", spec=_KIND_SPEC["environment"])


def _set_official_visual(sheet: EnvironmentReferenceSheet, asset_id: str) -> None:
    sheet.ers_composite_asset_id = asset_id
    composition = getattr(sheet, "composition", None)
    if composition is not None:
        rendered = dict(getattr(composition, "renderedAssetIds", None) or {})
        rendered["composite"] = asset_id
        rendered.setdefault("png", asset_id)
        composition.renderedAssetIds = rendered
        composition.lastRenderedAt = utc_now()


def _keep_plan_reference_consistent(sheet: EnvironmentReferenceSheet, asset_id: str) -> None:
    """The approved image IS the attached reference on this path — keep the
    saved plan's referenceImageAssetId pointing at it so reload shows the same
    attached image. Approval state itself never lives in the plan."""
    provenance = getattr(sheet, "provenance", None)
    if provenance is None:
        return
    details = dict(getattr(provenance, "details", None) or {})
    plan = dict(details.get("environmentCreatorPlan") or {})
    if plan:
        plan["referenceImageAssetId"] = asset_id
        details["environmentCreatorPlan"] = plan
    details["directApproval"] = {
        "assetId": asset_id,
        "path": "direct_reference_approval",
        "at": utc_now(),
    }
    provenance.details = details
    provenance.actor = "creator"
    provenance.note = "Creator approved the attached reference image as the official environment visual."


def approve_reference_as_environment(
    db: Session,
    project_id: str,
    sheet_id: str,
    *,
    asset_id: str,
    approved_by: str = "creator",
) -> dict[str, Any]:
    """Approve the attached reference image as the sheet's official environment
    visual. Same identity, same canonical tag — no duplicate environment."""
    asset_id = str(asset_id or "").strip()
    if not asset_id:
        raise ValueError("assetId is required")
    sheet = _load_owned_sheet(db, project_id, sheet_id)
    asset = _require_project_image_asset(db, project_id, asset_id)

    _set_official_visual(sheet, asset_id)
    _keep_plan_reference_consistent(sheet, asset_id)
    sheet.updatedAt = utc_now()
    save_sheet(sheet)

    _stamp_asset_as_environment(asset)

    # Sole canonical approval writer: status=approved, stamped requirements,
    # canonical pointer. Requires the composite we just persisted.
    approved = approve_ers_version(project_id, sheet.sheetId, approved_by=approved_by)

    approved_sheet = load_visible_sheet(db, project_id, sheet.sheetId) or sheet
    sync_environment_scope(db, approved_sheet)

    return {
        "ok": True,
        "sheet": approved["sheet"],
        "summary": approved["summary"],
        "approved": True,
        "assetId": asset_id,
        "canonicalSheetId": approved.get("canonicalSheetId"),
        "path": "direct_reference_approval",
        "mock": False,
    }


def clear_reference_environment_approval(
    db: Session,
    project_id: str,
    sheet_id: str,
    *,
    cleared_by: str = "creator",
) -> dict[str, Any]:
    """Clear a direct/generated approval: official visual detached, status back
    to draft, canonical pointer released. Library bytes are never deleted."""
    sheet = _load_owned_sheet(db, project_id, sheet_id)
    previous_composite = str(getattr(sheet, "ers_composite_asset_id", "") or "").strip()

    sheet.ers_composite_asset_id = None
    composition = getattr(sheet, "composition", None)
    if composition is not None and previous_composite:
        rendered = dict(getattr(composition, "renderedAssetIds", None) or {})
        for key in [k for k, v in rendered.items() if v == previous_composite]:
            rendered.pop(key, None)
        composition.renderedAssetIds = rendered

    sheet.status = "draft"
    sheet.updatedAt = utc_now()

    plan = getattr(sheet, "creationPlan", None)
    if plan is not None:
        reqs = list(getattr(plan, "approvalRequirements", None) or [])
        restamped = False
        for req in reqs:
            if getattr(req, "kind", "") in _APPROVE_REQUIREMENT_KINDS:
                req.status = "required"
                req.approvedBy = None
                req.approvedAt = None
                restamped = True
        if not restamped:
            reqs.append(
                ERSApprovalRequirement(
                    kind="ers-sheet-approve",
                    status="required",
                    reason="Creator must Approve this ERS sheet before it becomes downstream canonical.",
                )
            )
        plan.approvalRequirements = reqs
        sheet.creationPlan = plan

    provenance = getattr(sheet, "provenance", None)
    if provenance is not None:
        details = dict(getattr(provenance, "details", None) or {})
        details.pop("directApproval", None)
        provenance.details = details
        provenance.actor = cleared_by
        provenance.note = "Creator removed the approved environment reference; approval cleared."

    save_sheet(sheet)

    canonical = get_canonical_sheet_id(project_id)
    canonical_cleared = False
    if canonical and str(canonical) == str(sheet.sheetId):
        clear_canonical_sheet_id(project_id)
        canonical_cleared = True

    sync_environment_scope(db, sheet)

    return {
        "ok": True,
        "sheet": sheet.model_dump(mode="json"),
        "summary": version_summary(sheet, canonical_id=get_canonical_sheet_id(project_id)),
        "approved": False,
        "clearedAssetId": previous_composite or None,
        "canonicalCleared": canonical_cleared,
        "mock": False,
    }
