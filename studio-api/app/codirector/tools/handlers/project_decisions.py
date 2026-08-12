"""Project-scoped production decision handlers.

These tools write to the existing M2.11 decision-record substrate and may also update the
project title when the user explicitly confirms a new name.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ....db import Project
from ...errors import TOOL_TARGET_NOT_FOUND, VALIDATION_ERROR, CoDirectorError
from ...m211.decisions import DecisionRecordStore
from ..definitions import ToolContext, ToolPreview


def _require_project(ctx: ToolContext) -> Project:
    project = ctx.db.get(Project, ctx.project_id)
    if not project:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "Project not found.",
            details={"projectId": ctx.project_id},
            recoverable=False,
            recommended_action="none",
        )
    return project


def _clean_required_text(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if text:
        return text
    raise CoDirectorError(
        VALIDATION_ERROR,
        f"{field_name} is required.",
        details={"field": field_name},
        recoverable=True,
        recommended_action="none",
    )


def _clean_optional_text(value: Any) -> str:
    return str(value or "").strip()


def preview_record_production_decision(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    project = _require_project(ctx)
    decision = _clean_required_text(args.get("decision"), field_name="decision")
    rationale = _clean_optional_text(args.get("rationale"))
    requested_title = _clean_optional_text(args.get("projectTitle"))
    lines = [decision]
    warnings: list[str] = []
    if rationale:
        lines.append(f"Why: {rationale}")
    if requested_title:
        lines.append(f"Project title: {project.name} -> {requested_title}")
        if requested_title == (project.name or "").strip():
            warnings.append("The requested project title matches the current title.")
    return ToolPreview(
        summary=(
            f"Save this production decision for “{project.name}”"
            + (f" and rename the project to “{requested_title}”." if requested_title else ".")
        ),
        lines=lines,
        resourceKind="project",
        resourceId=project.id,
        warnings=warnings,
    )


def apply_record_production_decision(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project = _require_project(ctx)
    decision = _clean_required_text(args.get("decision"), field_name="decision")
    rationale = _clean_optional_text(args.get("rationale"))
    project_title = _clean_optional_text(args.get("projectTitle"))
    previous_title = (project.name or "").strip()
    project_title_updated = False

    if project_title and project_title != previous_title:
        project.name = project_title
        project.updated_at = datetime.utcnow()
        project_title_updated = True

    scene_id = _clean_optional_text(args.get("sceneId")) or None
    evidence = [
        {
            "sourceType": "project",
            "sourceId": project.id,
            "sourceName": project.name,
            "repository": "projects",
        }
    ]
    if ctx.request_id:
        evidence.append(
            {
                "sourceType": "conversation",
                "sourceId": ctx.request_id,
                "repository": "codirector_conversations",
            }
        )

    explainability = {
        "summary": rationale or decision,
        "decision": decision,
        "projectTitle": project.name,
        "previousProjectTitle": previous_title if project_title_updated else None,
        "source": "record_production_decision",
    }

    record = DecisionRecordStore.create(
        ctx.db,
        project_id=project.id,
        category="production_decision",
        rationale=rationale or decision,
        confidence=float(args.get("confidence") or 1.0),
        evidence=evidence,
        bible_refs=[],
        specialist_id="codirector",
        approval_required=False,
        approval_status="approved",
        recommendation=decision,
        scene_id=scene_id,
        explainability=explainability,
    )

    confirmation = (
        f"Saved the production decision for “{project.name}”."
        if not project_title_updated
        else f"Saved the production decision and renamed the project to “{project.name}”."
    )
    return {
        "ok": True,
        "saved": "production_decision",
        "confirmation": confirmation,
        "decision": record,
        "project": {"id": project.id, "name": project.name},
        "projectTitleUpdated": project_title_updated,
        "previousProjectTitle": previous_title if project_title_updated else None,
        "_evidence": evidence,
    }

