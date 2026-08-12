"""Factory functions for safe Co-Director autonomous workflows."""

from __future__ import annotations

from app.codirector.foundation.contracts import (
    AutonomousWorkflow,
    StopCondition,
    WorkflowBudget,
    WorkflowStep,
)


def _read_step(step_id: str, title: str, tool_id: str, *, depends_on: list[str] | None = None) -> WorkflowStep:
    return WorkflowStep(
        stepId=step_id,
        title=title,
        toolId=tool_id,
        state="ready",
        requiresApproval=False,
        idempotencyKey=step_id,
        dependsOn=list(depends_on or []),
    )


def _workflow(
    workflow_id: str,
    project_id: str,
    objective: str,
    steps: list[WorkflowStep],
    *,
    budget: WorkflowBudget | None = None,
) -> AutonomousWorkflow:
    allowed_tools = [step.toolId for step in steps if step.toolId]
    return AutonomousWorkflow(
        workflowId=workflow_id,
        projectId=project_id,
        objective=objective,
        steps=steps,
        allowedTools=allowed_tools,
        approvalPolicy="creator_required_for_mutations",
        budget=budget or WorkflowBudget(maxSteps=len(steps), maxRetries=1, maxDurationSeconds=60),
        stopConditions=[
            StopCondition(kind="approval_required", detail="Creator approval gates any project mutation."),
            StopCondition(kind="budget", detail="Safe audits stay read-only and avoid costly generation."),
        ],
        currentState="ready",
    )


def project_readiness_audit(project_id: str) -> AutonomousWorkflow:
    return _workflow(
        "project_readiness_audit",
        project_id,
        "Check project health, blockers, and system readiness before deeper work.",
        [
            _read_step("summary", "Refresh project summary", "project.get_summary"),
            _read_step("blockers", "List open blockers", "project.list_blockers", depends_on=["summary"]),
            _read_step("status", "Capture system health snapshot", "system.status_summary", depends_on=["summary"]),
        ],
    )


def continuity_scan(project_id: str) -> AutonomousWorkflow:
    return _workflow(
        "continuity_scan",
        project_id,
        "Scan continuity findings and highlight anything likely to break story consistency.",
        [
            _read_step("findings", "List continuity findings", "continuity.list_findings"),
            _read_step("issues", "Inspect active issues", "continuity.list_issues", depends_on=["findings"]),
            _read_step("script", "Review script continuity", "script.analyze_continuity", depends_on=["findings"]),
        ],
    )


def missing_asset_audit(project_id: str) -> AutonomousWorkflow:
    return _workflow(
        "missing_asset_audit",
        project_id,
        "Find missing or weakly covered creative assets before production work advances.",
        [
            _read_step("assets", "List known assets", "asset.list"),
            _read_step("scene-assets", "Inspect scene asset coverage", "scene.list_assets", depends_on=["assets"]),
            _read_step("library-search", "Search the project library", "search_library_assets", depends_on=["assets"]),
        ],
    )


def plan_validation(project_id: str) -> AutonomousWorkflow:
    return _workflow(
        "plan_validation",
        project_id,
        "Validate the current production plan and identify anything stale or blocked.",
        [
            _read_step("plans", "List production plans", "production_plan.list"),
            _read_step("validate", "Validate selected plan", "production_plan.validate", depends_on=["plans"]),
            _read_step("readiness", "Check plan readiness", "production_plan.get_readiness", depends_on=["validate"]),
        ],
    )


def failed_job_review(project_id: str) -> AutonomousWorkflow:
    return _workflow(
        "failed_job_review",
        project_id,
        "Review failed jobs and collect enough evidence to decide the next repair step.",
        [
            _read_step("jobs", "List recent jobs", "job.list"),
            _read_step("job-detail", "Inspect failed job detail", "job.get", depends_on=["jobs"]),
            _read_step("blockers", "Cross-check system blockers", "system.status_list_blockers", depends_on=["jobs"]),
        ],
    )


def generation_preflight(project_id: str) -> AutonomousWorkflow:
    return _workflow(
        "generation_preflight",
        project_id,
        "Run safe preflight checks before any creator-approved generation begins.",
        [
            _read_step("timeline", "Check timeline readiness", "timeline.preflight"),
            _read_step("references", "Check reference readiness", "references.preflight", depends_on=["timeline"]),
            _read_step("continuity", "Check continuity readiness", "continuity.preflight", depends_on=["timeline"]),
        ],
        budget=WorkflowBudget(maxSteps=3, maxRetries=2, maxDurationSeconds=90),
    )


def project_summary_refresh(project_id: str) -> AutonomousWorkflow:
    return _workflow(
        "project_summary_refresh",
        project_id,
        "Refresh the project's creator-facing summary without changing stored project data.",
        [
            _read_step("summary", "Refresh project summary", "project.get_summary"),
            _read_step("status", "Refresh project status", "get_project_status", depends_on=["summary"]),
            _read_step("bible", "Refresh bible summary", "production_bible.get_summary", depends_on=["summary"]),
        ],
    )


def export_readiness_check(project_id: str) -> AutonomousWorkflow:
    return _workflow(
        "export_readiness_check",
        project_id,
        "Check whether the project is ready for creator-led export or delivery review.",
        [
            _read_step("timeline", "Inspect timeline preflight", "timeline.preflight"),
            _read_step("references", "Inspect reference readiness", "references.get_readiness", depends_on=["timeline"]),
            _read_step(
                "continuity",
                "Inspect continuity reference readiness",
                "continuity.get_reference_readiness",
                depends_on=["timeline"],
            ),
        ],
    )
