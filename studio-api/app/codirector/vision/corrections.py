"""Build M2.2 tool_call proposals for vision corrections - never auto-execute."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..bible.proposals import ProposalService
from ..tools.definitions import TOOL_SCHEMA_VERSION, ToolCallPayload, ToolPreview
from .schemas import ValidationReport
from .store import VisionStore


def build_correction_preview(report: ValidationReport, *, notes: str = "") -> ToolPreview:
    lines = [
        f"Session {report.sessionId}",
        f"Overall score {report.overallScore} ({report.band})",
    ]
    for rec in report.recommendations[:8]:
        lines.append(rec)
    if notes:
        lines.append(f"Reviewer notes: {notes}")
    warnings = list(report.blockingFailures)
    if report.blockingFailures:
        warnings.append("Blocking failures present - do not treat as validated.")
    return ToolPreview(
        summary="Propose prompt/package corrections from vision validation findings (no auto-regenerate).",
        lines=lines,
        resourceKind="project",
        resourceId=report.projectId,
        warnings=warnings,
    )


def create_correction_proposal(
    db: Session,
    *,
    project_id: str,
    report: ValidationReport,
    finding_validator_ids: list[str] | None = None,
    notes: str = "",
    created_by: str = "user",
) -> dict[str, Any]:
    selected = set(finding_validator_ids or [])
    findings = [
        f.model_dump(mode="json")
        for f in report.findings
        if not selected or f.validatorId in selected
    ]
    preview = build_correction_preview(report, notes=notes)
    payload = ToolCallPayload(
        toolId="propose_vision_correction",
        toolSchemaVersion=TOOL_SCHEMA_VERSION,
        arguments={
            "sessionId": report.sessionId,
            "reportId": report.reportId,
            "findingValidatorIds": list(selected) if selected else [f["validatorId"] for f in findings],
            "notes": notes,
            "recommendations": report.recommendations[:12],
        },
        capabilitySnapshot={"visionValidation": True},
        preview=preview,
        inputHash=f"vision-correction:{report.reportId}",
        baseResourceVersions={},
    )
    proposal = ProposalService.create_tool_proposal(
        db,
        project_id=project_id,
        payload=payload,
        title="Vision validation correction",
        summary=preview.summary,
        created_by=created_by,
    )
    link = VisionStore.link_correction_proposal(
        db,
        session_id=report.sessionId,
        report_id=report.reportId,
        project_id=project_id,
        proposal_id=proposal.id,
        kind="vision_correction",
    )
    return {
        "proposalId": proposal.id,
        "linkId": link.linkId,
        "proposal": proposal.model_dump(mode="json") if hasattr(proposal, "model_dump") else proposal,
    }


def create_bible_link_proposal(
    db: Session,
    *,
    project_id: str,
    session_id: str,
    asset_id: Optional[str],
    report_id: Optional[str] = None,
    created_by: str = "user",
) -> dict[str, Any]:
    preview = ToolPreview(
        summary="Link validated asset into Production Bible as a reference (approval required).",
        lines=[
            f"Session {session_id}",
            f"Asset {asset_id or '(none)'}",
            "Does not mutate Bible until you approve this proposal.",
        ],
        resourceKind="bible",
        resourceId=project_id,
        warnings=[],
    )
    payload = ToolCallPayload(
        toolId="propose_asset_bible_link",
        toolSchemaVersion=TOOL_SCHEMA_VERSION,
        arguments={
            "sessionId": session_id,
            "assetId": asset_id,
            "reportId": report_id,
            "polarity": "positive",
            "primary": True,
        },
        capabilitySnapshot={"visionValidation": True},
        preview=preview,
        inputHash=f"vision-bible-link:{session_id}:{asset_id}",
        baseResourceVersions={},
    )
    proposal = ProposalService.create_tool_proposal(
        db,
        project_id=project_id,
        payload=payload,
        title="Link validated asset to Bible",
        summary=preview.summary,
        created_by=created_by,
    )
    link = VisionStore.link_correction_proposal(
        db,
        session_id=session_id,
        report_id=report_id,
        project_id=project_id,
        proposal_id=proposal.id,
        kind="asset_bible_link",
    )
    return {
        "proposalId": proposal.id,
        "linkId": link.linkId,
        "proposal": proposal.model_dump(mode="json") if hasattr(proposal, "model_dump") else proposal,
    }
