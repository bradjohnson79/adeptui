"""Workflow execution helpers with strict safety and idempotency rules."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from uuid import uuid4

from app.codirector.foundation.contracts import (
    ActivityEvent,
    AutonomousWorkflow,
    StopCondition,
    ToolReceipt,
    WorkflowStep,
)

ToolExecutor = Callable[[str, dict[str, object], str], ToolReceipt | Mapping[str, object]]

_COSTLY_GENERATION_PREFIXES = (
    "propose_image_generate",
    "propose_video_generate",
    "propose_shot_generate",
    "propose_scene_generate",
    "propose_three_frame_generate",
    "propose_timeline_render",
    "propose_batch_timeline",
    "propose_music_generate",
    "propose_sfx_generate",
    "audio.generate_",
    "propose_voice_generate",
    "propose_subtitle_generate",
    "timeline.propose_generate_",
)
_DESTRUCTIVE_TOKENS = ("delete", "remove", "publish", "marketplace", "canon.overwrite", "overwrite_canon")
_MUTATING_PREFIXES = (
    "create_",
    "update_",
    "set_",
    "record_",
    "propose_",
    "approve_",
    "apply_",
    "attach",
    "copy",
    "move",
    "retry",
    "cancel",
    "start",
    "stop",
    "render",
    "generate",
)


class WorkflowExecutionError(RuntimeError):
    """Structured execution failure surfaced to the workflow runner."""

    def __init__(self, message: str, *, recoverable: bool = False) -> None:
        super().__init__(message)
        self.recoverable = recoverable


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(
    workflow: AutonomousWorkflow,
    step: WorkflowStep | None,
    *,
    state: str,
    title: str,
    detail: str = "",
    event_type: str = "workflow",
) -> ActivityEvent:
    return ActivityEvent(
        eventId=f"evt-{uuid4().hex}",
        projectId=workflow.projectId,
        type=event_type,
        state=state,  # type: ignore[arg-type]
        title=title,
        detail=detail,
        timestamp=_timestamp(),
        toolId=step.toolId if step else None,
        workflowId=workflow.workflowId,
        metadata={"stepId": step.stepId} if step else {},
    )


def _normalize_receipt(
    raw: ToolReceipt | Mapping[str, object],
    *,
    project_id: str,
    tool_id: str,
    idempotency_key: str,
) -> ToolReceipt:
    if isinstance(raw, ToolReceipt):
        data = raw.model_dump()
        data.setdefault("projectId", project_id)
        data.setdefault("toolId", tool_id)
        data.setdefault("idempotencyKey", idempotency_key)
        return ToolReceipt.model_validate(data)

    payload = dict(raw)
    return ToolReceipt(
        receiptId=str(payload.get("receiptId") or f"receipt-{uuid4().hex}"),
        projectId=str(payload.get("projectId") or project_id),
        toolId=str(payload.get("toolId") or tool_id),
        status=str(payload.get("status") or "executed"),  # type: ignore[arg-type]
        idempotencyKey=str(payload.get("idempotencyKey") or idempotency_key),
        summary=str(payload.get("summary") or ""),
        error=str(payload.get("error")) if payload.get("error") is not None else None,
        payload=dict(payload.get("payload") or {}),
    )


def _stop(workflow: AutonomousWorkflow, kind: str, detail: str) -> None:
    workflow.stopConditions.append(StopCondition(kind=kind, detail=detail))  # type: ignore[arg-type]


def _existing_receipt(workflow: AutonomousWorkflow, idempotency_key: str) -> ToolReceipt | None:
    for receipt in workflow.receipts:
        if receipt.idempotencyKey == idempotency_key and receipt.status in {"executed", "failed", "rejected"}:
            return receipt
    return None


def _classify_mutation(tool_id: str | None) -> bool:
    if not tool_id:
        return False
    lowered = tool_id.lower()
    if lowered.startswith("get_") or lowered.startswith("list_"):
        return False
    if any(token in lowered for token in (".get", ".list", ".inspect", ".search", ".validate", ".preflight", ".status")):
        return False
    return any(prefix in lowered for prefix in _MUTATING_PREFIXES)


def _needs_hard_approval(tool_id: str | None) -> bool:
    if not tool_id:
        return False
    lowered = tool_id.lower()
    return lowered.startswith(_COSTLY_GENERATION_PREFIXES) or any(token in lowered for token in _DESTRUCTIVE_TOKENS)


def _approval_token_matches(step: WorkflowStep, tool_id: str | None, approvals: set[str]) -> bool:
    if not approvals:
        return False
    return any(
        token in approvals
        for token in (
            step.stepId,
            step.idempotencyKey,
            tool_id,
            f"{step.stepId}:{tool_id}",
        )
        if token
    )


def _dependencies_satisfied(step: WorkflowStep, completed_steps: set[str]) -> bool:
    return all(dep in completed_steps for dep in step.dependsOn)


def run_workflow(
    workflow: AutonomousWorkflow,
    tool_executor: ToolExecutor,
    *,
    step_arguments: Mapping[str, Mapping[str, object]] | None = None,
    approval_grants: Sequence[str] | None = None,
) -> tuple[AutonomousWorkflow, list[ActivityEvent]]:
    """Run a safe workflow against a caller-provided tool executor."""

    events: list[ActivityEvent] = []
    args_by_step = step_arguments or {}
    approvals = set(approval_grants or [])
    completed_steps = {step.stepId for step in workflow.steps if step.state == "complete"}

    workflow.currentState = "running"
    events.append(_event(workflow, None, state="running", title="Workflow started", detail=workflow.objective))

    for index, step in enumerate(workflow.steps):
        if index >= workflow.budget.maxSteps:
            step.state = "blocked"
            workflow.currentState = "stopped"
            _stop(workflow, "max_steps", "Workflow stopped at its step budget.")
            events.append(_event(workflow, step, state="failed", title="Workflow budget reached"))
            break

        if not step.toolId:
            step.state = "failed"
            workflow.currentState = "failed"
            _stop(workflow, "failure", f"Step '{step.stepId}' has no toolId.")
            events.append(_event(workflow, step, state="failed", title="Step missing tool", detail=step.title))
            break

        step.idempotencyKey = step.idempotencyKey or f"{workflow.workflowId}:{step.stepId}"

        if not _dependencies_satisfied(step, completed_steps):
            step.state = "blocked"
            workflow.currentState = "stopped"
            missing = [dep for dep in step.dependsOn if dep not in completed_steps]
            _stop(workflow, "failure", f"Step '{step.stepId}' is blocked by unresolved dependencies: {missing}.")
            events.append(_event(workflow, step, state="failed", title="Step blocked", detail=", ".join(missing)))
            break

        prior = _existing_receipt(workflow, step.idempotencyKey)
        if prior:
            step.state = "complete" if prior.status == "executed" else "failed"
            if prior.status == "executed":
                completed_steps.add(step.stepId)
                events.append(
                    _event(
                        workflow,
                        step,
                        state="succeeded",
                        title="Step reused prior receipt",
                        detail=prior.summary or step.title,
                    )
                )
                continue
            workflow.currentState = "failed"
            _stop(workflow, "failure", prior.error or f"Prior receipt for '{step.stepId}' already failed.")
            events.append(_event(workflow, step, state="failed", title="Step reused failed receipt", detail=prior.error or ""))
            break

        if step.toolId not in workflow.allowedTools:
            step.state = "failed"
            workflow.currentState = "failed"
            receipt = ToolReceipt(
                receiptId=f"receipt-{uuid4().hex}",
                projectId=workflow.projectId,
                toolId=step.toolId,
                status="failed",
                idempotencyKey=step.idempotencyKey,
                summary=f"Tool '{step.toolId}' is not allowed for this workflow.",
                error="allowedTools enforcement blocked execution.",
                payload={"recoverable": False},
            )
            workflow.receipts.append(receipt)
            _stop(workflow, "failure", receipt.summary)
            events.append(_event(workflow, step, state="failed", title="Tool blocked", detail=receipt.summary))
            break

        requires_approval = step.requiresApproval or (
            _classify_mutation(step.toolId) and workflow.approvalPolicy == "creator_required_for_mutations"
        )
        hard_excluded = _needs_hard_approval(step.toolId)
        approved = _approval_token_matches(step, step.toolId, approvals)

        if hard_excluded and not approved:
            step.state = "awaiting_approval"
            workflow.currentState = "awaiting_approval"
            _stop(
                workflow,
                "approval_required",
                f"Tool '{step.toolId}' needs explicit approval because it may be costly, destructive, or publish-facing.",
            )
            events.append(_event(workflow, step, state="queued", title="Approval required", detail=step.toolId))
            break

        if requires_approval and not approved:
            step.state = "awaiting_approval"
            workflow.currentState = "awaiting_approval"
            _stop(workflow, "approval_required", f"Step '{step.stepId}' requires creator approval.")
            events.append(_event(workflow, step, state="queued", title="Approval required", detail=step.title))
            break

        if _needs_hard_approval(step.toolId) and "generate" in step.toolId.lower() and not workflow.budget.allowCostlyGeneration:
            step.state = "failed"
            workflow.currentState = "failed"
            _stop(workflow, "budget", f"Workflow budget disallows costly generation for '{step.toolId}'.")
            events.append(_event(workflow, step, state="failed", title="Budget blocked generation", detail=step.toolId))
            break

        if any(token in step.toolId.lower() for token in ("delete", "remove")) and not workflow.budget.allowDestructive:
            step.state = "failed"
            workflow.currentState = "failed"
            _stop(workflow, "budget", f"Workflow budget disallows destructive operation '{step.toolId}'.")
            events.append(_event(workflow, step, state="failed", title="Budget blocked destructive tool", detail=step.toolId))
            break

        attempts = 0
        while attempts <= workflow.budget.maxRetries:
            attempts += 1
            step.state = "in_progress"
            events.append(_event(workflow, step, state="running", title="Step running", detail=f"Attempt {attempts}"))
            raw_args = dict(args_by_step.get(step.stepId, {}))
            raw_args.setdefault("projectId", workflow.projectId)
            try:
                receipt = _normalize_receipt(
                    tool_executor(step.toolId, raw_args, step.idempotencyKey),
                    project_id=workflow.projectId,
                    tool_id=step.toolId,
                    idempotency_key=step.idempotencyKey,
                )
            except WorkflowExecutionError as exc:
                receipt = ToolReceipt(
                    receiptId=f"receipt-{uuid4().hex}",
                    projectId=workflow.projectId,
                    toolId=step.toolId,
                    status="failed",
                    idempotencyKey=step.idempotencyKey,
                    summary=f"Step '{step.stepId}' failed.",
                    error=str(exc),
                    payload={"recoverable": exc.recoverable},
                )
            except Exception as exc:  # pragma: no cover - defensive normalization
                receipt = ToolReceipt(
                    receiptId=f"receipt-{uuid4().hex}",
                    projectId=workflow.projectId,
                    toolId=step.toolId,
                    status="failed",
                    idempotencyKey=step.idempotencyKey,
                    summary=f"Step '{step.stepId}' failed.",
                    error=str(exc),
                    payload={"recoverable": False},
                )

            workflow.receipts.append(receipt)
            recoverable = bool(receipt.payload.get("recoverable"))
            succeeded = receipt.status == "executed"
            if succeeded:
                step.state = "complete"
                completed_steps.add(step.stepId)
                events.append(
                    _event(
                        workflow,
                        step,
                        state="succeeded",
                        title="Step complete",
                        detail=receipt.summary or step.title,
                    )
                )
                break

            if recoverable and attempts <= workflow.budget.maxRetries:
                events.append(
                    _event(
                        workflow,
                        step,
                        state="queued",
                        title="Retry scheduled",
                        detail=receipt.error or receipt.summary or "Recoverable failure.",
                    )
                )
                continue

            step.state = "failed"
            workflow.currentState = "failed"
            _stop(
                workflow,
                "failure",
                receipt.error or receipt.summary or f"Step '{step.stepId}' failed without recovery.",
            )
            events.append(
                _event(
                    workflow,
                    step,
                    state="failed",
                    title="Step failed",
                    detail=receipt.error or receipt.summary,
                )
            )
            break

        if step.state != "complete":
            break

    else:
        workflow.currentState = "complete"

    if workflow.currentState == "running":
        workflow.currentState = "complete"

    final_state = "succeeded" if workflow.currentState == "complete" else "info"
    events.append(
        _event(
            workflow,
            None,
            state=final_state,
            title="Workflow finished",
            detail=workflow.currentState,
            event_type="workflow.completed",
        )
    )
    return workflow, events
