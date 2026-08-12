"""Wave 4 production plan tools — reads + audited create_draft + authoritative apply_*."""

from __future__ import annotations

import json
from typing import Any, Optional

from ....db import Project
from ...errors import (
    PLAN_NOT_FOUND,
    PLAN_VERSION_CONFLICT,
    PROJECT_REQUIRED,
    TOOL_ARGUMENTS_INVALID,
    CoDirectorError,
)
from ...plans.service import PlanService
from ..definitions import ToolContext, ToolPreview


def _parse_steps_json(raw: Optional[str]) -> Optional[list[dict[str, Any]]]:
    if raw is None or raw == "":
        return None
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise CoDirectorError(
            TOOL_ARGUMENTS_INVALID,
            "stepsJson must be a JSON array.",
            recoverable=True,
            recommended_action="revise_arguments",
        ) from exc
    if not isinstance(data, list):
        raise CoDirectorError(
            TOOL_ARGUMENTS_INVALID,
            "stepsJson must be a JSON array.",
            recoverable=True,
            recommended_action="revise_arguments",
        )
    return [x for x in data if isinstance(x, dict)][:50]


def _project(ctx: ToolContext) -> str:
    if not ctx.project_id:
        raise CoDirectorError(
            PROJECT_REQUIRED,
            "No project selected. Open or create a project before using production plan tools.",
            recoverable=True,
            recommended_action="select_project",
        )
    return ctx.project_id


def _require_project_row(ctx: ToolContext) -> Project:
    """Authoritative project read before any plan mutation (D1/D2 invariant).

    `_project` only checks the id is present; this loads the Project row so a
    stale/missing project is caught at the tool boundary instead of inside
    `PlanService`.
    """

    project_id = _project(ctx)
    project = ctx.db.get(Project, project_id)
    if project is None:
        raise CoDirectorError(
            PLAN_NOT_FOUND,
            "Project not found — open or create a project before using production plan tools.",
            details={"projectId": project_id},
            recoverable=False,
            recommended_action="select_project",
        )
    return project


def _require_plan_current(ctx: ToolContext, plan_id: str, expected_version: Optional[int]) -> "Any":
    """Read the plan's current state at the handler before delegating (D3).

    Mirrors `ToolExecutionService.is_stale`'s plan-version comparison at the
    handler boundary: if `expected_version` was captured against an older plan
    version, surface `PLAN_VERSION_CONFLICT` here rather than relying on the
    service to catch it. The service still enforces the transition; this is an
    additive authoritative read, not a replacement.
    """

    if not plan_id:
        raise CoDirectorError(
            TOOL_ARGUMENTS_INVALID,
            "planId is required.",
            recoverable=True,
            recommended_action="revise_arguments",
        )
    try:
        plan = PlanService.get(ctx.db, ctx.project_id, plan_id)
    except CoDirectorError:
        raise
    except Exception as exc:
        raise CoDirectorError(
            PLAN_NOT_FOUND,
            "Production plan not found.",
            details={"planId": plan_id},
            recoverable=False,
            recommended_action="none",
        ) from exc
    if expected_version is not None and int(expected_version) != int(plan.version):
        raise CoDirectorError(
            PLAN_VERSION_CONFLICT,
            "Plan version conflict — the plan changed since this proposal was built.",
            details={
                "planId": plan_id,
                "expectedVersion": int(expected_version),
                "actualVersion": int(plan.version),
                "currentPlanSummary": {"planId": plan.planId, "state": plan.state, "title": plan.title},
                "recommendedAction": "reload_and_retry",
            },
            recoverable=True,
            recommended_action="retry",
        )
    return plan


def _plan_payload(result) -> dict[str, Any]:
    plan = result.plan
    return {
        "plan": plan.model_dump(mode="json"),
        "event": result.event.model_dump(mode="json") if result.event else None,
        "duplicated": result.duplicated,
        "unapproved": plan.unapproved,
        # c2/D9: written justification persisted on the invocation result so the
        # audit trail records WHY this mutating tool was allowed to run without a
        # human proposal gate. A draft is non-authoritative: state=draft,
        # unapproved=True, and the plan state machine forbids draft →
        # approved/ready/in_progress/completed directly (it must go through the
        # proposal path: draft → proposed → approved). So an audited draft can
        # never authorize production.
        "auditedJustification": (
            "Audited write: production_plan.create_draft persists an unapproved draft only. "
            "It does not authorize production; state=draft cannot transition to approved, "
            "ready, in_progress, or completed without the proposal path (draft → proposed → "
            "approved). Recorded here so the audit trail carries the rationale."
        ),
        "_summary": f"Plan {plan.planId} state={plan.state} v{plan.version}.",
        "_evidence": [
            {
                "sourceType": "plan",
                "sourceId": plan.planId,
                "repository": "codirector.plans",
                "version": str(plan.version),
            }
        ],
    }


# ---- reads ----


async def production_plan_list(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _project(ctx)
    limit = int(args.get("limit") or 25)
    plans = PlanService.list(ctx.db, project_id, limit=min(limit, 100))
    items = [
        {
            "planId": p.planId,
            "title": p.title,
            "state": p.state,
            "version": p.version,
            "unapproved": p.unapproved,
            "readiness": p.capabilitySnapshot.readiness if p.capabilitySnapshot else None,
            "updatedAt": p.updatedAt,
            "source": "plans",
        }
        for p in plans
    ]
    warnings = []
    try:
        from ...m214.plan_view import production_plan_view

        view = production_plan_view(ctx.db, project_id)
        if view:
            items.append(
                {
                    "planId": f"m214:{project_id}",
                    "title": "M214 production stages",
                    "state": "scaffolded",
                    "source": "m214",
                    "honesty": "scaffolded",
                }
            )
            warnings.append(
                {
                    "code": "M214_SCAFFOLDED",
                    "message": "M214 plan view is scaffolded and must not be treated as completed step truth.",
                    "section": "plans",
                }
            )
    except Exception:
        pass
    return {
        "plans": items[:limit],
        "_summary": f"{len(items[:limit])} plan record(s).",
        "_warnings": warnings,
        "_evidence": [
            {"sourceType": "plan", "sourceId": p["planId"], "repository": p.get("source") or "plans"} for p in items[:limit]
        ],
    }


async def production_plan_get(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _project(ctx)
    plan_id = str(args.get("planId") or "")
    if plan_id.startswith("m214:"):
        from ...m214.plan_view import production_plan_view

        view = production_plan_view(ctx.db, project_id)
        return {
            "plan": view,
            "source": "m214",
            "honesty": "scaffolded",
            "_warnings": [
                {
                    "code": "M214_SCAFFOLDED",
                    "message": "Scaffolded plan — steps are not inferred as complete.",
                    "section": "plans",
                }
            ],
            "_summary": "M214 scaffolded production plan view.",
            "_evidence": [{"sourceType": "plan", "sourceId": plan_id, "repository": "m214.plan_view"}],
        }
    try:
        plan = PlanService.get(ctx.db, project_id, plan_id)
    except CoDirectorError:
        raise
    except Exception as exc:
        raise CoDirectorError(
            PLAN_NOT_FOUND,
            "Production plan not found.",
            details={"planId": plan_id},
            recoverable=False,
            recommended_action="none",
        ) from exc
    return {
        "plan": plan.model_dump(mode="json"),
        "source": "plans",
        "unapproved": plan.unapproved,
        "_summary": f"Plan '{plan.title}' state={plan.state} v{plan.version}.",
        "_evidence": [
            {
                "sourceType": "plan",
                "sourceId": plan.planId,
                "repository": "codirector.plans",
                "version": str(plan.version),
            }
        ],
    }


async def production_plan_get_version(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _project(ctx)
    plan_id = str(args.get("planId") or "")
    version = int(args.get("version") or 0)
    plan = PlanService.get_version(ctx.db, project_id, plan_id, version)
    return {
        "plan": plan.model_dump(mode="json"),
        "_summary": f"Plan version {version}.",
        "_evidence": [
            {"sourceType": "plan", "sourceId": plan_id, "repository": "codirector.plans.versions", "version": str(version)}
        ],
    }


async def production_plan_list_versions(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _project(ctx)
    plan_id = str(args.get("planId") or "")
    versions = PlanService.list_versions(ctx.db, project_id, plan_id)
    return {
        "versions": versions,
        "_summary": f"{len(versions)} version(s).",
        "_evidence": [{"sourceType": "plan", "sourceId": plan_id, "repository": "codirector.plans.versions"}],
    }


async def production_plan_list_events(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _project(ctx)
    plan_id = str(args.get("planId") or "")
    events = PlanService.list_events(ctx.db, project_id, plan_id, limit=int(args.get("limit") or 100))
    return {
        "events": events,
        "_summary": f"{len(events)} event(s).",
        "_evidence": [{"sourceType": "plan", "sourceId": plan_id, "repository": "codirector.plans.events"}],
    }


async def production_plan_validate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _project(ctx)
    plan_id = str(args.get("planId") or "")
    result = PlanService.validate(ctx.db, project_id, plan_id)
    return {
        "validation": result.model_dump(mode="json"),
        "_summary": f"Validation status={result.status}.",
        "_evidence": [{"sourceType": "plan", "sourceId": plan_id, "repository": "codirector.plans"}],
    }


async def production_plan_get_readiness(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _project(ctx)
    plan_id = str(args.get("planId") or "")
    report = PlanService.get_readiness(ctx.db, project_id, plan_id)
    return {
        "readiness": report.model_dump(mode="json"),
        "snapshotReadiness": report.snapshotReadiness,
        "currentReadiness": report.currentReadiness,
        "changedCapabilities": report.changedCapabilities,
        "requiresRefresh": report.requiresRefresh,
        "_summary": (
            f"snapshot={report.snapshotReadiness} current={report.currentReadiness}"
            + ("; refresh required" if report.requiresRefresh else "")
        ),
        "_evidence": [{"sourceType": "plan", "sourceId": plan_id, "repository": "codirector.plans.readiness"}],
    }


# ---- audited create_draft (no plan-approval gate) ----


def preview_create_draft(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    title = str(args.get("title") or "Untitled plan")
    steps = args.get("steps") or []
    return ToolPreview(
        summary=f"Persist unapproved draft plan '{title}' (does not authorize production).",
        lines=[
            "State will be draft / unapproved.",
            f"Steps: {len(steps) if isinstance(steps, list) else 0}",
            "No production actions will run.",
        ],
        resourceKind="plan",
        warnings=["Draft is audited but not approved."],
    )


def apply_create_draft(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _project(ctx)
    # D1/D2: authoritative read-before-write. Load the project row and check for
    # an existing unapproved draft with the same title+objective so a repeated
    # draft proposal does not silently create duplicates. PlanService's own
    # idempotency (requestId) covers retries of the same request; this guards a
    # second, distinct request that re-asks for the same draft.
    _require_project_row(ctx)
    title = str(args.get("title") or "Untitled plan").strip()
    objective = str(args.get("objective") or "").strip()
    existing_drafts = PlanService.list(ctx.db, project_id, limit=100)
    duplicate = next(
        (
            p
            for p in existing_drafts
            if p.state == "draft"
            and p.unapproved
            and (p.title or "").strip() == title
            and (p.objective or "").strip() == objective
        ),
        None,
    )
    if duplicate is not None:
        # Surface the duplicate as an explicit proposal outcome rather than
        # silently creating a second draft. The caller (preview/apply pipeline)
        # persists this on the invocation result.
        return {
            "plan": duplicate.model_dump(mode="json"),
            "event": None,
            "duplicated": True,
            "unapproved": True,
            "duplicateDraft": True,
            "auditedJustification": (
                "Audited write: production_plan.create_draft persists an unapproved draft only. "
                "It does not authorize production; state=draft cannot transition to approved, "
                "ready, in_progress, or completed without the proposal path (draft → proposed → "
                "approved). Recorded here so the audit trail carries the rationale."
            ),
            "_summary": (
                f"Draft '{title}' already exists as {duplicate.planId} (state=draft, unapproved). "
                "No new draft created."
            ),
            "_evidence": [
                {
                    "sourceType": "plan",
                    "sourceId": duplicate.planId,
                    "repository": "codirector.plans",
                    "version": str(duplicate.version),
                }
            ],
        }
    steps = _parse_steps_json(args.get("stepsJson")) or []
    result = PlanService.create_draft(
        ctx.db,
        project_id=project_id,
        request_id=str(args.get("requestId") or ctx.request_id or ""),
        title=title,
        objective=objective,
        description=str(args.get("description") or ""),
        steps=steps,
        conversation_id=args.get("conversationId"),
        source_type="conversation",
    )
    return _plan_payload(result)


# ---- authoritative mutations (preview + apply after human approve) ----


def _preview_cmd(summary: str, plan_id: str, extra: list[str] | None = None) -> ToolPreview:
    return ToolPreview(
        summary=summary,
        lines=[f"planId={plan_id}", *(extra or [])],
        resourceKind="plan",
        resourceId=plan_id,
        warnings=["Plan-management only — does not execute production steps."],
    )


def preview_propose(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_cmd("Propose plan for acceptance approval.", str(args.get("planId") or ""))


def apply_propose(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # D3: authoritative read-before-write — verify the plan exists and the
    # expected version is current before delegating to PlanService.
    _require_plan_current(ctx, str(args.get("planId") or ""), args.get("expectedVersion"))
    result = PlanService.propose(
        ctx.db,
        project_id=_project(ctx),
        plan_id=str(args.get("planId") or ""),
        request_id=str(args.get("requestId") or ctx.request_id or ""),
        expected_version=int(args.get("expectedVersion")),
    )
    return _plan_payload(result)


def preview_approve(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_cmd(
        "Approve plan acceptance (not a production-action approval).",
        str(args.get("planId") or ""),
        ["Does not start generation or execute steps."],
    )


def apply_approve(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # D3: authoritative read-before-write.
    _require_plan_current(ctx, str(args.get("planId") or ""), args.get("expectedVersion"))
    result = PlanService.approve(
        ctx.db,
        project_id=_project(ctx),
        plan_id=str(args.get("planId") or ""),
        request_id=str(args.get("requestId") or ctx.request_id or ""),
        expected_version=int(args.get("expectedVersion")),
    )
    return _plan_payload(result)


def preview_reject(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_cmd("Reject plan and return to draft.", str(args.get("planId") or ""))


def apply_reject(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # D3: authoritative read-before-write.
    _require_plan_current(ctx, str(args.get("planId") or ""), args.get("expectedVersion"))
    result = PlanService.reject(
        ctx.db,
        project_id=_project(ctx),
        plan_id=str(args.get("planId") or ""),
        request_id=str(args.get("requestId") or ctx.request_id or ""),
        expected_version=int(args.get("expectedVersion")),
        reason=str(args.get("reason") or ""),
    )
    return _plan_payload(result)


def preview_revise(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_cmd(
        "Revise plan (new version after approval).",
        str(args.get("planId") or ""),
        [str(args.get("revisionReason") or "revision")],
    )


def apply_revise(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    result = PlanService.revise(
        ctx.db,
        project_id=_project(ctx),
        plan_id=str(args.get("planId") or ""),
        request_id=str(args.get("requestId") or ctx.request_id or ""),
        expected_version=int(args.get("expectedVersion")),
        title=args.get("title"),
        objective=args.get("objective"),
        steps=_parse_steps_json(args.get("stepsJson")),
        revision_reason=str(args.get("revisionReason") or ""),
    )
    return _plan_payload(result)


def preview_pause(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_cmd("Pause plan.", str(args.get("planId") or ""))


def apply_pause(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    result = PlanService.pause(
        ctx.db,
        project_id=_project(ctx),
        plan_id=str(args.get("planId") or ""),
        request_id=str(args.get("requestId") or ctx.request_id or ""),
        expected_version=int(args.get("expectedVersion")),
    )
    return _plan_payload(result)


def preview_resume(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_cmd("Resume paused plan.", str(args.get("planId") or ""))


def apply_resume(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    result = PlanService.resume(
        ctx.db,
        project_id=_project(ctx),
        plan_id=str(args.get("planId") or ""),
        request_id=str(args.get("requestId") or ctx.request_id or ""),
        expected_version=int(args.get("expectedVersion")),
    )
    return _plan_payload(result)


def preview_cancel(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_cmd("Cancel plan.", str(args.get("planId") or ""))


def apply_cancel(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    result = PlanService.cancel(
        ctx.db,
        project_id=_project(ctx),
        plan_id=str(args.get("planId") or ""),
        request_id=str(args.get("requestId") or ctx.request_id or ""),
        expected_version=int(args.get("expectedVersion")),
    )
    return _plan_payload(result)


def preview_archive(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_cmd("Archive plan.", str(args.get("planId") or ""))


def apply_archive(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    result = PlanService.archive(
        ctx.db,
        project_id=_project(ctx),
        plan_id=str(args.get("planId") or ""),
        request_id=str(args.get("requestId") or ctx.request_id or ""),
        expected_version=int(args.get("expectedVersion")),
    )
    return _plan_payload(result)


def preview_resolve_blocker(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_cmd(
        "Resolve plan blocker.",
        str(args.get("planId") or ""),
        [f"blockerId={args.get('blockerId')}"],
    )


def apply_resolve_blocker(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    result = PlanService.resolve_blocker(
        ctx.db,
        project_id=_project(ctx),
        plan_id=str(args.get("planId") or ""),
        request_id=str(args.get("requestId") or ctx.request_id or ""),
        expected_version=int(args.get("expectedVersion")),
        blocker_id=str(args.get("blockerId") or ""),
    )
    return _plan_payload(result)
