from __future__ import annotations

from app.codirector.foundation.contracts import AutonomousWorkflow, ToolReceipt, WorkflowBudget, WorkflowStep
from app.codirector.foundation.operations.engine import WorkflowExecutionError, run_workflow
from app.codirector.foundation.operations.supervisor import collect_notifications
from app.codirector.foundation.operations.workflows import generation_preflight, project_readiness_audit


def test_safe_workflow_factories_stay_read_only() -> None:
    workflow = project_readiness_audit("proj-1")

    assert workflow.workflowId == "project_readiness_audit"
    assert workflow.currentState == "ready"
    assert workflow.budget.allowCostlyGeneration is False
    assert workflow.budget.allowDestructive is False
    assert workflow.allowedTools == ["project.get_summary", "project.list_blockers", "system.status_summary"]
    assert all(step.requiresApproval is False for step in workflow.steps)


def test_generation_preflight_uses_safe_preflight_tools() -> None:
    workflow = generation_preflight("proj-2")

    assert workflow.workflowId == "generation_preflight"
    assert workflow.allowedTools == ["timeline.preflight", "references.preflight", "continuity.preflight"]
    assert workflow.budget.maxRetries == 2


def test_run_workflow_blocks_tools_outside_allowed_set() -> None:
    workflow = AutonomousWorkflow(
        workflowId="unsafe",
        projectId="proj-1",
        objective="Try a disallowed tool.",
        steps=[WorkflowStep(stepId="step-1", title="Unsafe step", toolId="create_scene", state="ready")],
        allowedTools=["project.get_summary"],
        budget=WorkflowBudget(maxSteps=1, maxRetries=0),
        currentState="ready",
    )

    called = 0

    def executor(_tool_id: str, _arguments: dict[str, object], _idempotency_key: str):
        nonlocal called
        called += 1
        return {"status": "executed", "summary": "should never run"}

    updated, _events = run_workflow(workflow, executor)

    assert called == 0
    assert updated.currentState == "failed"
    assert updated.steps[0].state == "failed"
    assert updated.receipts[0].status == "failed"
    assert updated.stopConditions[-1].kind == "failure"


def test_run_workflow_requires_approval_for_mutation_tools() -> None:
    workflow = AutonomousWorkflow(
        workflowId="approval",
        projectId="proj-1",
        objective="Try a mutation.",
        steps=[WorkflowStep(stepId="step-1", title="Create scene", toolId="create_scene", state="ready")],
        allowedTools=["create_scene"],
        budget=WorkflowBudget(maxSteps=1, maxRetries=0),
        currentState="ready",
    )

    called = 0

    def executor(_tool_id: str, _arguments: dict[str, object], _idempotency_key: str):
        nonlocal called
        called += 1
        return {"status": "executed", "summary": "should never run"}

    updated, events = run_workflow(workflow, executor)

    assert called == 0
    assert updated.currentState == "awaiting_approval"
    assert updated.steps[0].state == "awaiting_approval"
    assert updated.stopConditions[-1].kind == "approval_required"
    assert any(event.title == "Approval required" for event in events)


def test_run_workflow_retries_recoverable_failure_and_appends_receipts() -> None:
    workflow = AutonomousWorkflow(
        workflowId="retry",
        projectId="proj-1",
        objective="Recover from a transient read failure.",
        steps=[WorkflowStep(stepId="step-1", title="Read summary", toolId="project.get_summary", state="ready")],
        allowedTools=["project.get_summary"],
        budget=WorkflowBudget(maxSteps=1, maxRetries=1),
        currentState="ready",
    )

    calls = 0

    def executor(tool_id: str, _arguments: dict[str, object], idempotency_key: str) -> ToolReceipt:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ToolReceipt(
                receiptId="r1",
                projectId="proj-1",
                toolId=tool_id,
                status="failed",
                idempotencyKey=idempotency_key,
                summary="Temporary outage",
                error="Temporary outage",
                payload={"recoverable": True},
            )
        return ToolReceipt(
            receiptId="r2",
            projectId="proj-1",
            toolId=tool_id,
            status="executed",
            idempotencyKey=idempotency_key,
            summary="Recovered",
            payload={},
        )

    updated, events = run_workflow(workflow, executor)

    assert calls == 2
    assert updated.currentState == "complete"
    assert updated.steps[0].state == "complete"
    assert [receipt.status for receipt in updated.receipts] == ["failed", "executed"]
    assert any(event.title == "Retry scheduled" for event in events)


def test_run_workflow_reuses_existing_receipt_for_same_idempotency_key() -> None:
    workflow = AutonomousWorkflow(
        workflowId="reuse",
        projectId="proj-1",
        objective="Avoid duplicate execution.",
        steps=[
            WorkflowStep(
                stepId="step-1",
                title="Read summary",
                toolId="project.get_summary",
                state="ready",
                idempotencyKey="dup-key",
            )
        ],
        allowedTools=["project.get_summary"],
        budget=WorkflowBudget(maxSteps=1, maxRetries=0),
        currentState="ready",
        receipts=[
            ToolReceipt(
                receiptId="existing",
                projectId="proj-1",
                toolId="project.get_summary",
                status="executed",
                idempotencyKey="dup-key",
                summary="Already done",
                payload={},
            )
        ],
    )

    called = 0

    def executor(_tool_id: str, _arguments: dict[str, object], _idempotency_key: str):
        nonlocal called
        called += 1
        return {"status": "executed", "summary": "should never run"}

    updated, _events = run_workflow(workflow, executor)

    assert called == 0
    assert updated.currentState == "complete"
    assert updated.steps[0].state == "complete"
    assert len(updated.receipts) == 1


def test_run_workflow_stops_on_nonrecoverable_failure() -> None:
    workflow = AutonomousWorkflow(
        workflowId="fail",
        projectId="proj-1",
        objective="Surface a hard failure.",
        steps=[WorkflowStep(stepId="step-1", title="Read summary", toolId="project.get_summary", state="ready")],
        allowedTools=["project.get_summary"],
        budget=WorkflowBudget(maxSteps=1, maxRetries=2),
        currentState="ready",
    )

    def executor(_tool_id: str, _arguments: dict[str, object], _idempotency_key: str):
        raise WorkflowExecutionError("Permanent failure", recoverable=False)

    updated, _events = run_workflow(workflow, executor)

    assert updated.currentState == "failed"
    assert updated.steps[0].state == "failed"
    assert updated.receipts[0].error == "Permanent failure"
    assert updated.stopConditions[-1].kind == "failure"


def test_collect_notifications_collapses_project_health_without_spam() -> None:
    notifications = collect_notifications(
        "proj-1",
        {
            "failedJobs": [{"title": "Render batch 12"}, {"title": "Render batch 12"}, {"jobId": "job-3"}],
            "blockers": [{"title": "Missing timeline audio"}],
            "missingAssets": [{"title": "Hero costume plate"}, {"assetId": "asset-2"}],
            "stalePlans": [{"title": "Season launch plan"}],
        },
    )

    assert len(notifications) == 4
    assert notifications[0].type == "project_health.failed_jobs"
    assert notifications[0].metadata["count"] == 3
    assert "Render batch 12" in notifications[0].detail
    assert notifications[1].type == "project_health.blockers"
