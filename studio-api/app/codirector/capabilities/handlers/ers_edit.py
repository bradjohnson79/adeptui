"""Capability handler: ers.edit

Open / prepare / execute Environment Reference Sheet edit without auto-approving.
- May enqueue Certified edit (Backend edit/enqueue) or create draft vN from a derivative.
- NEVER calls approve_ers_version / set_canonical_sheet_id.
- New versions remain draft until creator Approve API.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def handle(
    db: Session,
    project_id: str,
    execution_id: str = "",
    *,
    sheet_id: str = "",
    sheetId: str = "",
    prompt: str = "",
    edit_prompt: str = "",
    editPrompt: str = "",
    derivative_asset_id: str = "",
    derivativeAssetId: str = "",
    mask_asset_id: str = "",
    maskAssetId: str = "",
    mask_png: str = "",
    maskPng: str = "",
    source_asset_id: str = "",
    sourceAssetId: str = "",
    prepare_only: bool = False,
    prepareOnly: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    from ....environment_reference_sheet.store import (
        get_canonical_sheet_id,
        list_sheets,
        load_sheet,
    )
    from ....environment_reference_sheet.versioning import (
        create_ers_version_from_derivative,
        resolve_canonical_sheet,
    )

    sid = str(sheet_id or sheetId or "").strip()
    edit_text = str(edit_prompt or editPrompt or prompt or "").strip()
    deriv = str(derivative_asset_id or derivativeAssetId or "").strip()
    mask_id = str(mask_asset_id or maskAssetId or "").strip()
    mask_png_val = str(mask_png or maskPng or "").strip()
    source_id = str(source_asset_id or sourceAssetId or "").strip()
    prepare = bool(prepare_only or prepareOnly or kwargs.get("prepare"))

    sheet = load_sheet(project_id, sid) if sid else None
    if sheet is None:
        sheet = resolve_canonical_sheet(project_id)
    if sheet is None:
        sheets = list_sheets(project_id) or []
        with_comp = [
            s
            for s in sheets
            if str(getattr(s, "ers_composite_asset_id", "") or "").strip()
        ]
        sheet = with_comp[0] if with_comp else (sheets[0] if sheets else None)

    if sheet is None:
        return {
            "status": "failed",
            "error": "No Environment Reference Sheet found to edit.",
            "creatorAck": "I need an existing ERS before I can edit it.",
            "autoApproved": False,
            "child_jobs": [],
            "job_ids": [],
            "surface_type": "ers_edit",
        }

    sid = str(sheet.sheetId)
    canonical = get_canonical_sheet_id(project_id)

    # Path A: derivative already exists → create draft version only (no approve).
    if deriv:
        created = create_ers_version_from_derivative(
            project_id,
            sid,
            derivative_asset_id=deriv,
            edit_prompt=edit_text or None,
            actor="codirector:ers.edit",
        )
        return {
            "status": "draft_version_created",
            "surface_type": "ers_edit",
            "sheetId": sid,
            "versionSheetId": created.get("versionSheetId"),
            "versionNumber": created.get("versionNumber"),
            "derivativeAssetId": deriv,
            "canonicalSheetId": canonical,
            "autoApproved": False,
            "needsCreatorApprove": True,
            "creatorAck": (
                f"Created ERS v{created.get('versionNumber')} as a draft from the edit. "
                "It is NOT canonical yet — Approve in Environment Creator to promote it."
            ),
            "child_jobs": [],
            "job_ids": [],
            "result": created,
        }

    # Path B: mask + prompt → enqueue Certified derivative-only edit (Backend seam).
    if (mask_id or mask_png_val) and edit_text and not prepare:
        from ....environment_reference_sheet.edit import enqueue_ers_edit

        enq = enqueue_ers_edit(
            db,
            project_id,
            sid,
            edit_prompt=edit_text,
            mask_asset_id=mask_id or None,
            mask_png=mask_png_val or None,
            source_asset_id=source_id or None,
        )
        job_id = str(enq.get("jobId") or enq.get("queueJobId") or "")
        return {
            "status": "edit_enqueued",
            "surface_type": "ers_edit",
            "sheetId": sid,
            "jobId": job_id,
            "queueJobId": job_id,
            "derivativeOnly": True,
            "ersCompositeAssetId": enq.get("ersCompositeAssetId"),
            "canonicalSheetId": canonical,
            "autoApproved": False,
            "needsCreatorApprove": True,
            "integrationSeam": (
                "When job completes with derivativeAssetId, POST "
                f"/api/environment-reference-sheets/projects/{project_id}/{sid}/versions "
                "then creator Approve — ers.edit never auto-approves."
            ),
            "creatorAck": (
                "ERS edit is queued (Certified inpaint). When the derivative is ready, "
                "a new draft version can be created — you still need to Approve before it "
                "becomes canonical."
            ),
            "child_jobs": [{"jobId": job_id, "kind": "imagegen_edit"}] if job_id else [],
            "job_ids": [job_id] if job_id else [],
            "enqueue": enq,
        }

    # Path C: prepare / open — return context for UI / creator; no mutation, no approve.
    composite = str(getattr(sheet, "ers_composite_asset_id", "") or "").strip()
    return {
        "status": "prepared",
        "surface_type": "ers_edit",
        "sheetId": sid,
        "sourceAssetId": source_id or composite,
        "editPrompt": edit_text or None,
        "canonicalSheetId": canonical,
        "autoApproved": False,
        "needsCreatorApprove": True,
        "needsMask": True,
        "openEnvironmentCreator": True,
        "creatorAck": (
            "I can edit this environment reference. Provide a mask + edit prompt "
            "(for example: remove the plant beside the couch). I will not auto-approve "
            "the new version — you Approve when ready."
        ),
        "child_jobs": [],
        "job_ids": [],
        "suggestedRoute": (
            f"POST /api/environment-reference-sheets/projects/{project_id}/{sid}/edit/enqueue"
        ),
    }