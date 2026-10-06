"""Chat entry. SSE reads persisted events. It does not own the workflow."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.orm import Session

from .admission import build_envelope
from .journal import events_from, get_status, load_admission, save_admission
from .runtime import ensure_started


def _user_text(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user" and (message.get("content") or "").strip():
            return str(message["content"])
    return ""


def _provider_and_model(provider_id: str | None, model: str | None) -> tuple[str, str]:
    from ..service import active_provider_id, get_provider

    selected = provider_id or active_provider_id()
    provider = get_provider(selected)
    model_id = model or ""
    if not model_id:
        try:
            from .. import config_store

            model_id = str(config_store.load_config().get("selectedModel") or "")
        except Exception:
            model_id = ""
    _ = provider
    return selected, model_id


async def begin_turn(
    db: Session,
    *,
    messages: list[dict[str, str]],
    project_id: str | None,
    scene_id: str | None,
    model: str | None,
    provider_id: str | None,
    request_id: str,
    surface: str | None,
    selected_character_id: str | None = None,
) -> str:
    """Start the admitted workflow once. The same request id only attaches."""

    if not project_id:
        raise ValueError("A project is required.")
    ensure_started()
    if load_admission(request_id) is not None or get_status(request_id) is not None:
        return request_id
    user_text = _user_text(messages)
    selected_provider, model_id = _provider_and_model(provider_id, model)
    envelope = build_envelope(
        db,
        workflow_id=request_id,
        project_id=project_id,
        scene_id=scene_id,
        user_text=user_text,
        surface=surface,
        provider_id=selected_provider,
        model_id=model_id,
        selected_character_id=selected_character_id,
    )
    save_admission(request_id, envelope.model_dump())
    await _start_workflow(envelope.model_dump())
    return request_id


async def _start_workflow(envelope: dict[str, Any]) -> None:
    from dbos import DBOS, SetEnqueueOptions, SetWorkflowID

    from .workflow import codirector_turn

    payload = {"envelope": envelope}
    workflow_id = str(envelope["workflow_id"])
    with SetWorkflowID(workflow_id):
        if envelope.get("turn_mode") == "MUTATE":
            partition = f"{envelope.get('project_id')}:{envelope.get('scene_id') or '*'}"
            with SetEnqueueOptions(queue_partition_key=partition):
                await DBOS.enqueue_workflow_async("adept_cd_mutations", codirector_turn, payload)
        else:
            await DBOS.start_workflow_async(codirector_turn, payload)


async def iter_projection(workflow_id: str) -> AsyncIterator[dict[str, Any]]:
    """Project already stored events. Disconnecting this generator does not cancel the workflow."""

    seen = 0
    idle = 0
    while idle < 12000:
        rows = events_from(workflow_id, seen)
        if not rows:
            status = get_status(workflow_id)
            if status in {"SUCCESS", "ERROR", "CANCELLED"}:
                return
            idle += 1
            await asyncio.sleep(0.05)
            continue
        idle = 0
        for row in rows:
            seen = int(row["seq"])
            event = row["event"]
            yield event
            if event.get("type") in {"completed", "error", "cancelled"}:
                return


async def wait_for_result(workflow_id: str) -> dict[str, Any]:
    completed: dict[str, Any] | None = None
    async for event in iter_projection(workflow_id):
        if event.get("type") == "completed":
            completed = event
    if completed is None:
        return {
            "requestId": workflow_id,
            "workflowId": workflow_id,
            "reply": "I couldn't finish that turn. No project change was confirmed.",
            "fallbackUsed": False,
        }
    return {
        "requestId": workflow_id,
        "workflowId": workflow_id,
        "traceId": completed.get("traceId") or workflow_id,
        "reply": completed.get("content") or "",
        "model": completed.get("modelId") or "",
        "providerId": completed.get("providerId") or "",
        "fallbackUsed": False,
    }


def cancel_turn(workflow_id: str) -> dict[str, Any]:
    """Explicit stop. A dropped browser connection must not call this."""

    from .journal import append_event, receipts_for

    verified = any(
        item.get("verification_status") == "verified" for item in receipts_for(workflow_id)
    )
    if verified:
        append_event(
            workflow_id,
            {
                "type": "cancelled",
                "requestId": workflow_id,
                "workflowId": workflow_id,
                "content": "The verified change was kept.",
            },
        )
        return {"ok": True, "cancelled": False, "reason": "verified mutation kept"}
    try:
        from dbos import DBOS

        DBOS.cancel_workflow(workflow_id)
    except Exception:
        pass
    append_event(
        workflow_id,
        {"type": "cancelled", "requestId": workflow_id, "workflowId": workflow_id},
    )
    return {"ok": True, "cancelled": True}
