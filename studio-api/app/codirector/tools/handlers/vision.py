"""Co-Director M2.5 vision validation tool handlers."""

from __future__ import annotations

from typing import Any

from ...errors import TOOL_ARGUMENTS_INVALID, CoDirectorError
from ...vision.approval import record_decision
from ...vision.corrections import create_bible_link_proposal, create_correction_proposal
from ...vision.store import VisionStore
from ..definitions import ToolContext, ToolPreview


async def vision_validation_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    session_id = str(args.get("sessionId") or "")
    if session_id:
        session = VisionStore.get_session(ctx.db, session_id, project_id=ctx.project_id)
        if not session:
            return {"found": False, "sessionId": session_id}
        return {"found": True, "session": session.model_dump(mode="json")}
    sessions = VisionStore.list_sessions_for_project(ctx.db, ctx.project_id, limit=int(args.get("limit") or 20))
    return {
        "found": True,
        "sessions": [s.model_dump(mode="json") for s in sessions],
        "count": len(sessions),
    }


async def vision_validation_report(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    report_id = str(args.get("reportId") or "")
    session_id = str(args.get("sessionId") or "")
    if not report_id and session_id:
        session = VisionStore.get_session(ctx.db, session_id, project_id=ctx.project_id)
        report_id = (session.reportId if session else "") or ""
    if not report_id:
        raise CoDirectorError(
            TOOL_ARGUMENTS_INVALID,
            "reportId or sessionId is required.",
            recoverable=True,
        )
    report = VisionStore.get_report(ctx.db, report_id, project_id=ctx.project_id)
    if not report:
        return {"found": False, "reportId": report_id}
    return {"found": True, "report": report.model_dump(mode="json")}


def preview_propose_vision_correction(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    session_id = str(args.get("sessionId") or "")
    return ToolPreview(
        summary="Propose vision validation corrections (no auto-regenerate).",
        lines=[
            f"Session: {session_id or '(required)'}",
            "Creates a durable tool_call proposal from validation findings.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=["Does not regenerate assets or mutate the Bible."],
    )


def apply_propose_vision_correction(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    session_id = str(args.get("sessionId") or "")
    session = VisionStore.get_session(ctx.db, session_id, project_id=ctx.project_id)
    if not session or not session.reportId:
        raise CoDirectorError(TOOL_ARGUMENTS_INVALID, "Valid sessionId with a report is required.", recoverable=True)
    report = VisionStore.get_report(ctx.db, session.reportId, project_id=ctx.project_id)
    if not report:
        raise CoDirectorError(TOOL_ARGUMENTS_INVALID, "Validation report not found.", recoverable=True)
    ids = args.get("findingValidatorIds") or []
    if isinstance(ids, str):
        ids = [ids]
    return create_correction_proposal(
        ctx.db,
        project_id=ctx.project_id,
        report=report,
        finding_validator_ids=list(ids),
        notes=str(args.get("notes") or ""),
        created_by="assistant",
    )


def preview_propose_asset_bible_link(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Propose linking a validated asset into the Production Bible.",
        lines=[
            f"Session: {args.get('sessionId') or '(required)'}",
            f"Asset: {args.get('assetId') or '(none)'}",
            "Bible is not mutated until this proposal is approved.",
        ],
        resourceKind="bible",
        resourceId=ctx.project_id,
        warnings=[],
    )


def apply_propose_asset_bible_link(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    session_id = str(args.get("sessionId") or "")
    asset_id = args.get("assetId")
    report_id = args.get("reportId")
    return create_bible_link_proposal(
        ctx.db,
        project_id=ctx.project_id,
        session_id=session_id,
        asset_id=str(asset_id) if asset_id else None,
        report_id=str(report_id) if report_id else None,
        created_by="assistant",
    )


def preview_record_vision_review(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    decision = str(args.get("decision") or "approved")
    return ToolPreview(
        summary=f"Record human vision review decision: {decision}.",
        lines=[
            f"Session: {args.get('sessionId') or '(required)'}",
            f"Decision: {decision}",
            "Stores an approval record; does not auto-regenerate.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=[],
    )


def apply_record_vision_review(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    session_id = str(args.get("sessionId") or "")
    decision = str(args.get("decision") or "approved")
    if decision not in {"approved", "rejected", "override_approve", "override_reject"}:
        raise CoDirectorError(TOOL_ARGUMENTS_INVALID, "Invalid decision.", recoverable=True)
    return record_decision(
        ctx.db,
        project_id=ctx.project_id,
        session_id=session_id,
        decision=decision,
        reviewer=str(args.get("reviewer") or "user"),
        notes=str(args.get("notes") or ""),
        override=decision.startswith("override_"),
        link_to_bible=bool(args.get("linkToBible")),
    )
