"""Run one admitted tool through the existing executor and the replay barrier."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy.orm import Session

from ...db import SessionLocal
from .admission import master_hash
from .authority import authorize_tool
from .barrier import apply_with_barrier
from .journal import append_event
from .models import AuthorityEnvelope, FailureState, ToolReceipt, ToolRequest


def _bounded(value: Any) -> Any:
    """Keep the tool payload the model must see, without secret fields or an unbounded blob."""

    from .redact import redact

    cleaned = redact(_dump(value))
    encoded = json.dumps(cleaned, default=str)
    if len(encoded) <= 6000:
        return cleaned
    kept: dict[str, Any] = {"truncated": True, "preview": encoded[:6000]}
    message = _creator_message(cleaned)
    if message:
        kept["message"] = message
    return kept


def _creator_message(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    data = value.get("data") if isinstance(value.get("data"), dict) else {}
    message = str(value.get("message") or data.get("message") or "").strip()
    if message and "character_creator." not in message and "audio.generate_" not in message:
        return message[:500]
    for key in ("read", "result", "evidence", "data"):
        nested = value.get(key)
        if isinstance(nested, dict):
            found = _creator_message(nested)
            if found:
                return found
    return ""


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        data = value.model_dump(mode="json")
        return data if isinstance(data, dict) else {"value": data}
    if isinstance(value, dict):
        return value
    return {"value": str(value)}


def _run_async(coro):
    try:
        asyncio.get_running_loop()
        running = True
    except RuntimeError:
        running = False
    if not running:
        return asyncio.run(coro)

    import concurrent.futures

    def _worker():
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_worker).result()


def run_admitted_tool(
    db: Session,
    envelope: AuthorityEnvelope,
    *,
    tool_id: str,
    arguments: dict[str, Any],
    tool_call_id: str,
) -> ToolReceipt | FailureState:
    from ..tools.exposure import is_shelved_tool
    from ..tools.registry import find

    try:
        definition = find(tool_id)
    except Exception:
        definition = None
    if definition is None:
        return FailureState(
            code="UNKNOWN_TOOL",
            message=f"'{tool_id}' is not in the closed registry.",
            workflow_id=envelope.workflow_id,
            tool_id=tool_id,
        )
    from .bind import bind_request_arguments

    arguments, bind_refusal = bind_request_arguments(
        db,
        tool_id=tool_id,
        arguments=arguments,
        user_text=envelope.user_text,
        project_id=envelope.project_id,
        selected_character_id=envelope.selected_character_id,
        scene_id=envelope.scene_id,
    )
    if bind_refusal:
        _tool_event(envelope, "tool_failed", tool_id, bind_refusal)
        return FailureState(
            code="REQUEST_BIND_REFUSED",
            message=bind_refusal,
            workflow_id=envelope.workflow_id,
            tool_id=tool_id,
        )
    if tool_id == "timeline.propose_add_prompt_segment":
        from ..service import _bind_timed_prompt_tool_arguments

        bound, refusal = _bind_timed_prompt_tool_arguments(
            db,
            project_id=envelope.project_id,
            scene_id=envelope.scene_id or arguments.get("sceneId"),
            arguments=arguments,
            user_message=envelope.user_text,
        )
        if refusal or bound is None:
            message = refusal or "That timed prompt could not be bound."
            _tool_event(envelope, "tool_failed", tool_id, message)
            return FailureState(
                code="TIMED_PROMPT_REFUSED",
                message=message,
                workflow_id=envelope.workflow_id,
                tool_id=tool_id,
            )
        arguments = bound
    decision = authorize_tool(
        envelope,
        tool_id=tool_id,
        arguments=arguments,
        tool_call_id=tool_call_id,
        kind=definition.kind,
        shelved=is_shelved_tool(tool_id),
    )
    if isinstance(decision, FailureState):
        _tool_event(envelope, "tool_failed", tool_id, decision.message)
        return decision

    _tool_event(envelope, "tool_started", tool_id, None)
    if definition.kind == "read":
        receipt = _run_read(decision)
    elif envelope.turn_mode == "PROPOSE":
        receipt = _propose_only(decision)
    else:
        receipt = _mutate(db, decision)
    event_type = "tool_completed" if isinstance(receipt, ToolReceipt) else "tool_failed"
    detail = receipt.error if isinstance(receipt, ToolReceipt) else receipt.message
    _tool_event(envelope, event_type, tool_id, detail, invocation=_invocation_for_receipt(receipt))
    return receipt


def _invocation_for_receipt(receipt: ToolReceipt | FailureState) -> dict[str, Any] | None:
    """Surface a read-tool handoff on the event the browser already navigates from."""

    if not isinstance(receipt, ToolReceipt):
        return None
    evidence = receipt.evidence if isinstance(receipt.evidence, dict) else {}
    read = evidence.get("read")
    if not isinstance(read, dict):
        return None
    result = read.get("result") if isinstance(read.get("result"), dict) else read
    if not isinstance(result, dict):
        return None
    from ..execution.ui_handoff import lift_ui_handoff

    lifted = lift_ui_handoff(result)
    if not lifted.get("uiAction") and not lifted.get("workspaceUrl"):
        return None
    return {"result": lifted, "resultTruncated": bool(read.get("truncated"))}


def _tool_event(
    envelope: AuthorityEnvelope,
    event_type: str,
    tool_id: str,
    error: str | None,
    invocation: dict[str, Any] | None = None,
) -> None:
    event: dict[str, Any] = {
        "type": event_type,
        "requestId": envelope.workflow_id,
        "workflowId": envelope.workflow_id,
        "toolId": tool_id,
        "error": error,
    }
    if invocation:
        event["invocation"] = invocation
    append_event(envelope.workflow_id, event)


def _run_read(request: ToolRequest) -> ToolReceipt | FailureState:
    from ..tools.execution import ToolExecutionService

    def _call(session: Session):
        return _run_async(
            ToolExecutionService.execute_read(
                session,
                project_id=request.project_id,
                tool_id=request.tool_id,
                arguments=request.arguments,
                scene_id=request.scene_id,
                request_id=request.workflow_id,
            )
        )

    try:
        with SessionLocal() as session:
            outcome = _call(session)
    except Exception as exc:
        return FailureState(
            code="READ_FAILED",
            message=str(exc),
            workflow_id=request.workflow_id,
            tool_id=request.tool_id,
        )
    return ToolReceipt(
        requested_action=request.action,
        target=request.scene_id or request.project_id,
        tool_id=request.tool_id,
        execution_status="succeeded",
        mutation_status="none",
        verification_status="not_applicable",
        evidence={"read": _bounded(outcome)},
    )


def _propose_only(request: ToolRequest) -> ToolReceipt | FailureState:
    from .journal import proposal_for_workflow

    existing = proposal_for_workflow(request.workflow_id)
    if existing and existing.get("tool_id") == request.tool_id:
        return ToolReceipt(
            requested_action=request.action,
            target=request.scene_id or request.project_id,
            tool_id=request.tool_id,
            execution_status="succeeded",
            mutation_status="proposed",
            verification_status="not_applicable",
            evidence={"proposalId": existing.get("proposal_id"), "duplicateSuppressed": True},
        )
    from ..tools.execution import ToolExecutionService

    try:
        with SessionLocal() as session:
            outcome = _run_async(
                ToolExecutionService.propose(
                    session,
                    project_id=request.project_id,
                    tool_id=request.tool_id,
                    arguments=request.arguments,
                    scene_id=request.scene_id,
                    request_id=request.workflow_id,
                )
            )
    except Exception as exc:
        return FailureState(
            code="PROPOSE_FAILED",
            message=str(exc),
            workflow_id=request.workflow_id,
            tool_id=request.tool_id,
        )
    proposed = _bounded(outcome)
    proposal_id = ""
    if isinstance(proposed, dict):
        proposal_id = str(proposed.get("id") or proposed.get("proposalId") or "")
    if not proposal_id:
        proposal_id = str(getattr(outcome, "id", "") or "")
    if proposal_id:
        from .bind import ordered_execution_plan
        from .journal import save_proposal_link

        source = str(request.arguments.get("prompt") or request.arguments.get("text") or request.arguments.get("description") or "")
        plan = ordered_execution_plan(source)
        if plan and str(plan[0].get("toolId") or "") != request.tool_id:
            plan = None
        save_proposal_link(
            proposal_id=proposal_id,
            originating_workflow_id=request.workflow_id,
            project_id=request.project_id,
            scene_id=request.scene_id,
            tool_id=request.tool_id,
            intended_text=str(request.arguments.get("text") or ""),
            approval_id=f"approve:{request.workflow_id}:{proposal_id}",
            plan=plan,
        )
    return ToolReceipt(
        requested_action=request.action,
        target=request.scene_id or request.project_id,
        tool_id=request.tool_id,
        execution_status="succeeded",
        mutation_status="proposed",
        verification_status="not_applicable",
        evidence={"proposed": proposed, "proposalId": proposal_id},
    )


_DURABLE_APPROVAL_TOOLS = frozenset(
    {
        "audio.generate_sfx",
        "audio.generate_ambience",
        "audio.generate_music",
    }
)


def durable_approval_required(tool_id: str, *, requires_approval: bool) -> bool:
    """Audio generation stays an audited tool, and Co-Director still asks before starting it."""

    return bool(requires_approval) or tool_id in _DURABLE_APPROVAL_TOOLS


def _mutate(db: Session, request: ToolRequest) -> ToolReceipt | FailureState:
    from ..execution_authority import should_auto_approve
    from ..tools.registry import find

    definition = find(request.tool_id)
    before = master_hash(db, request.project_id, request.scene_id)
    auto_approve = should_auto_approve(db, request.project_id, request.tool_id, request.workflow_id)
    needs_approval = definition is not None and durable_approval_required(
        request.tool_id,
        requires_approval=definition.requires_approval,
    )
    if needs_approval and not auto_approve:
        return _propose_only(request)

    def _read() -> str | None:
        return master_hash(db, request.project_id, request.scene_id)

    def _executor() -> dict[str, Any]:
        with SessionLocal() as session:
            if definition is not None and definition.requires_approval:
                return _apply_approved(session, request)
            from ..tools.execution import ToolExecutionService

            return _dump(
                _run_async(
                    ToolExecutionService.execute_audited(
                        session,
                        project_id=request.project_id,
                        tool_id=request.tool_id,
                        arguments=request.arguments,
                        scene_id=request.scene_id,
                        request_id=request.mutation_id,
                    )
                )
            )

    def _verify(raw: dict[str, Any], after: str | None) -> bool:
        if raw.get("replay") or raw.get("proposedOnly"):
            return False
        if raw.get("verified") is False:
            return False
        if request.tool_id.startswith("timeline."):
            return bool(after) and after != before
        return raw.get("ok", True) is not False

    return apply_with_barrier(
        request,
        before_hash=before,
        read_hash=_read,
        executor=_executor,
        verify=_verify,
    )


def _apply_approved(session: Session, request: ToolRequest) -> dict[str, Any]:
    from ..bible.proposals import ProposalService
    from ..tools.execution import ToolExecutionService

    proposal = _run_async(
        ToolExecutionService.propose(
            session,
            project_id=request.project_id,
            tool_id=request.tool_id,
            arguments=request.arguments,
            scene_id=request.scene_id,
            request_id=request.workflow_id,
        )
    )
    dumped = _dump(proposal)
    proposal_id = dumped.get("id") or dumped.get("proposalId")
    if not proposal_id:
        return {"ok": False, "verified": False, "error": "proposal id missing"}
    approved = ProposalService.approve(
        session,
        request.project_id,
        str(proposal_id),
        note="durable turn",
        decided_by="codirector",
    )
    result = _dump(approved)
    result.setdefault("ok", True)
    if result.get("verified") is None:
        result["verified"] = bool(result.get("ok"))
    return result
