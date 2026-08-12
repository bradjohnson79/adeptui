"""Activity event helpers for foundation workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .contracts import ActivityEvent, AutonomousWorkflow


def workflow_activity_events(workflow: AutonomousWorkflow) -> list[ActivityEvent]:
    """Emit low-noise activity events for workflow state transitions."""

    now = datetime.now(timezone.utc).isoformat()
    events = [
        ActivityEvent(
            eventId=str(uuid4()),
            projectId=workflow.projectId,
            type="workflow",
            stage=workflow.currentState,
            state="info" if workflow.currentState in {"draft", "ready"} else "running",
            title=workflow.objective,
            detail=f"Workflow {workflow.workflowId} is {workflow.currentState}.",
            timestamp=now,
            workflowId=workflow.workflowId,
        )
    ]
    if workflow.currentState == "complete":
        events[-1].state = "succeeded"
    elif workflow.currentState == "failed":
        events[-1].state = "failed"
    elif workflow.currentState == "awaiting_approval":
        events[-1].state = "info"
        events[-1].detail = "Waiting for creator approval before continuing."
    return events
