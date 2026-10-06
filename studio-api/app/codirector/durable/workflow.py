"""One DBOS workflow per Co-Director turn."""

from __future__ import annotations

from typing import Any

from dbos import DBOS

from ...db import SessionLocal
from .agent import build_agent, set_turn_deps
from .deps import TurnDeps
from .journal import append_event, receipts_for, set_status
from .models import AuthorityEnvelope, ToolReceipt
from .tracing import emit_trace
from .wording import project_creator_reply, scrub_unverified_success

agent = build_agent()


@DBOS.step()
def _remember_assistant(project_id: str, workflow_id: str, reply: str, provider_id: str, model_id: str) -> None:
    from ..conversation_events import EventInput, append_events

    with SessionLocal() as db:
        append_events(
            db,
            project_id,
            [
                EventInput(
                    role="assistant",
                    content=reply,
                    request_id=workflow_id,
                    client_request_id=f"{workflow_id}:assistant",
                    message_id=f"{workflow_id}:assistant",
                    actor="assistant",
                )
            ],
            model=model_id or None,
            provider_id=provider_id or None,
        )
        db.commit()


def _remember_user(project_id: str, workflow_id: str, text: str) -> None:
    """Store the current line once. A retry with the same request id does not duplicate it."""

    if not project_id or not (text or "").strip():
        return
    from ..conversation_events import EventInput, append_events

    with SessionLocal() as db:
        try:
            append_events(
                db,
                project_id,
                [
                    EventInput(
                        role="user",
                        content=text,
                        request_id=workflow_id,
                        client_request_id=f"{workflow_id}:user",
                        message_id=f"{workflow_id}:user",
                        actor="user",
                    )
                ],
            )
            db.commit()
        except Exception:
            db.rollback()


@DBOS.workflow()
async def codirector_turn(payload: dict[str, Any]) -> dict[str, Any]:
    envelope = AuthorityEnvelope.model_validate(payload["envelope"])
    from .crash import maybe_crash

    maybe_crash("conversation", envelope.workflow_id, None)
    _remember_user(envelope.project_id, envelope.workflow_id, envelope.user_text)
    history: list[dict[str, Any]] = []
    try:
        from ..conversation_events import fold_events_for_llm

        with SessionLocal() as db:
            history = fold_events_for_llm(db, envelope.project_id)
    except Exception:
        history = []
    deps = TurnDeps(
        envelope={**envelope.model_dump(), "conversation_for_model": history},
        exposed_tool_ids=tuple(envelope.exposed_tool_ids),
    )
    set_turn_deps(deps)
    append_event(
        envelope.workflow_id,
        {
            "type": "request_started",
            "requestId": envelope.workflow_id,
            "workflowId": envelope.workflow_id,
            "traceId": envelope.workflow_id,
        },
    )
    failure = None
    try:
        result = await agent.run(envelope.user_text, deps=deps)
        reply = str(result.output or "")
    except Exception as exc:
        failure = str(exc)
        reply = "I couldn't finish that turn. No project change was confirmed."
    parsed: list[ToolReceipt] = []
    for item in receipts_for(envelope.workflow_id):
        if "verification_status" in item:
            parsed.append(ToolReceipt.model_validate(item))
    from .journal import events_from

    failed = [
        item["event"].get("error")
        for item in events_from(envelope.workflow_id, 0)
        if item["event"].get("type") == "tool_failed" and item["event"].get("error")
    ]
    if failed and not any(item.verification_status == "verified" for item in parsed):
        reply = str(failed[-1])
    reply = project_creator_reply(reply)
    reply = scrub_unverified_success(reply, parsed)
    try:
        _remember_assistant(
            envelope.project_id,
            envelope.workflow_id,
            reply,
            envelope.provider_id,
            envelope.model_id,
        )
    except Exception:
        failure = failure or "conversation append failed"
    trace_id = emit_trace(
        workflow_id=envelope.workflow_id,
        project_id=envelope.project_id,
        scene_id=envelope.scene_id,
        model=envelope.model_id,
        prompt_version=envelope.system_prompt_version,
        user_text=envelope.user_text,
        tool_ids=envelope.exposed_tool_ids,
        receipts=[item.model_dump() for item in parsed],
        reply=reply,
        failure=failure,
    )
    append_event(
        envelope.workflow_id,
        {"type": "token", "requestId": envelope.workflow_id, "content": reply},
    )
    append_event(
        envelope.workflow_id,
        {
            "type": "completed",
            "requestId": envelope.workflow_id,
            "workflowId": envelope.workflow_id,
            "traceId": trace_id,
            "content": reply,
            "messageId": f"{envelope.workflow_id}:assistant",
            "modelId": envelope.model_id,
            "providerId": envelope.provider_id,
        },
    )
    body = {
        "requestId": envelope.workflow_id,
        "workflowId": envelope.workflow_id,
        "traceId": trace_id,
        "reply": reply,
        "model": envelope.model_id,
        "providerId": envelope.provider_id,
        "fallbackUsed": False,
    }
    set_status(envelope.workflow_id, "ERROR" if failure else "SUCCESS", body)
    return body
