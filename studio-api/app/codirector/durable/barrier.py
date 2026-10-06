"""Mutation replay barrier.

Survives: Master save succeeded, then the process died before the DBOS step
was marked complete. A retry must not call save again.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .journal import begin_mutation, get_mutation, mark_executing, save_receipt
from .models import FailureState, ToolReceipt, ToolRequest


def apply_with_barrier(
    request: ToolRequest,
    *,
    before_hash: str | None,
    read_hash: Callable[[], str | None],
    executor: Callable[[], dict[str, Any]],
    verify: Callable[[dict[str, Any], str | None], bool],
    on_before_execute: Callable[[], None] | None = None,
    on_after_executor: Callable[[dict[str, Any]], None] | None = None,
    on_after_observed: Callable[[str | None], None] | None = None,
    on_after_receipt: Callable[[ToolReceipt], None] | None = None,
) -> ToolReceipt | FailureState:
    existing = begin_mutation(
        mutation_id=request.mutation_id,
        workflow_id=request.workflow_id,
        tool_id=request.tool_id,
        target=request.scene_id or request.project_id,
        action=request.action,
        before_hash=before_hash,
    )
    if existing and existing.get("status") == "verified" and existing.get("receipt_json"):
        import json

        prior = json.loads(existing["receipt_json"])
        return ToolReceipt.model_validate(prior)

    admitted_before = before_hash if existing is None else existing.get("before_hash")
    current = read_hash()
    already_entered = existing is not None and str(existing.get("status")) == "executing"
    master_moved = existing is not None and current != admitted_before
    if already_entered or master_moved:
        reconstructed = _reconstruct(request, admitted_before, current, verify)
        if isinstance(reconstructed, FailureState):
            save_receipt(
                request.mutation_id,
                after_hash=current,
                status="ambiguous",
                receipt=reconstructed.model_dump(),
            )
        elif isinstance(reconstructed, ToolReceipt) and reconstructed.verification_status == "verified":
            save_receipt(
                request.mutation_id,
                after_hash=current,
                status="verified",
                receipt=reconstructed.model_dump(),
            )
        return reconstructed

    if on_before_execute is not None:
        on_before_execute()
    mark_executing(request.mutation_id)
    try:
        raw = executor()
    except Exception as exc:
        failure = FailureState(
            code="TOOL_EXECUTION_FAILED",
            message=str(exc),
            workflow_id=request.workflow_id,
            tool_id=request.tool_id,
            mutation_id=request.mutation_id,
        )
        save_receipt(
            request.mutation_id,
            after_hash=read_hash(),
            status="failed",
            receipt=failure.model_dump(),
        )
        return failure

    if on_after_executor is not None:
        on_after_executor(raw if isinstance(raw, dict) else {"value": raw})
    after = read_hash()
    verified = verify(raw, after)
    if verified and on_after_observed is not None:
        on_after_observed(after)
    if not verified:
        failure = FailureState(
            code="VERIFICATION_FAILED",
            message="The change could not be verified against project state.",
            workflow_id=request.workflow_id,
            tool_id=request.tool_id,
            mutation_id=request.mutation_id,
            evidence={"before": admitted_before, "after": after},
        )
        save_receipt(
            request.mutation_id,
            after_hash=after,
            status="verification_failed",
            receipt=failure.model_dump(),
        )
        return failure

    receipt = ToolReceipt(
        requested_action=request.action,
        target=request.scene_id or request.project_id,
        tool_id=request.tool_id,
        execution_status="succeeded",
        mutation_status="written",
        verification_status="verified",
        master_hash_before=admitted_before,
        master_hash_after=after,
        evidence={"handler": _brief(raw)},
    )
    save_receipt(
        request.mutation_id,
        after_hash=after,
        status="verified",
        receipt=receipt.model_dump(),
    )
    if on_after_receipt is not None:
        on_after_receipt(receipt)
    return receipt


def _reconstruct(
    request: ToolRequest,
    before_hash: str | None,
    current_hash: str | None,
    verify: Callable[[dict[str, Any], str | None], bool],
) -> ToolReceipt | FailureState:
    stored = get_mutation(request.mutation_id)
    if stored and stored.get("status") == "verified" and stored.get("receipt_json"):
        import json

        return ToolReceipt.model_validate(json.loads(stored["receipt_json"]))
    placeholder = {"replay": True, "masterChanged": True}
    if verify(placeholder, current_hash):
        return ToolReceipt(
            requested_action=request.action,
            target=request.scene_id or request.project_id,
            tool_id=request.tool_id,
            execution_status="succeeded",
            mutation_status="written",
            verification_status="verified",
            master_hash_before=before_hash,
            master_hash_after=current_hash,
            evidence={"reconstructed": True},
        )
    return FailureState(
        code="AMBIGUOUS_REPLAY",
        message="A previous attempt may have changed the project, but it could not be verified. Nothing was written again.",
        workflow_id=request.workflow_id,
        tool_id=request.tool_id,
        mutation_id=request.mutation_id,
        evidence={"before": before_hash, "after": current_hash},
    )


def _brief(raw: dict[str, Any]) -> dict[str, Any]:
    from .redact import redact

    if not isinstance(raw, dict):
        return {"result": str(raw)[:500]}
    keep = (
        "ok",
        "verified",
        "status",
        "toolId",
        "jobId",
        "propId",
        "assetId",
        "message",
        "provider",
        "model",
        "workflowKey",
        "endpoint",
    )
    brief = {key: raw.get(key) for key in keep if key in raw}
    tool_result = raw.get("toolResult")
    if isinstance(tool_result, dict):
        for key in keep:
            if key not in brief and key in tool_result:
                brief[key] = tool_result.get(key)
    return redact(brief or {"keys": sorted(raw.keys())[:12]})
