"""Execution dispatcher — resolves capabilities and submits real jobs.

Spec §7: "If sufficient: EXECUTE."
Spec §14: "The execution plan should be machine-readable and traceable."
Spec §15: "Each long-running execution needs: execution_id, job_id, project_id,
capability, provider, model, status, progress, created_at, updated_at,
result_asset_ids, error."

The dispatcher:
1. Resolves the CapabilityDefinition from the registry.
2. Checks approval policy (spec §50).
3. For CAPABILITY_HANDLER kinds: imports the handler module by convention
   and calls its `handle()` function.
4. For TOOL kinds: delegates to the existing ToolExecutionService.
5. Creates the ExecutionPlan pack, publishes execution.started event.
"""

from __future__ import annotations

import importlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ..capabilities.registry import (
    ApprovalPolicy,
    CapabilityDefinition,
    HandlerKind,
    get_capability,
    surface_type_for,
)
from ..routing.unified_intent import UnifiedIntent, UnifiedIntentKind
from .contracts import ChildJobStatus, ChildJobView, ExecutionPlan, ExecutionStatus
from .events import ExecutionEvent, ExecutionEventType
from .pack_store import load_pack, save_pack

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_handler(capability_id: str):
    """Import the handler module for a CAPABILITY_HANDLER capability by convention."""
    module_name = capability_id.replace(".", "_")
    module_path = f"app.codirector.capabilities.handlers.{module_name}"
    try:
        module = importlib.import_module(module_path)
        if not hasattr(module, "handle"):
            logger.error("Handler module %s has no handle() function", module_path)
            return None
        return module.handle
    except ImportError as exc:
        logger.warning("Handler module %s not available: %s", module_path, exc)
        return None
    except Exception as exc:
        logger.error("Failed to load handler %s: %s", module_path, exc)
        return None


def _publish_event(event: ExecutionEvent) -> None:
    """Publish an execution event to the status SSE bus."""
    try:
        from ..status.runner import publish_event as _publish

        _publish(event.to_sse_data())
    except Exception as exc:
        # Non-fatal — SSE bus may not be available.
        logger.debug("Failed to publish execution event: %s", exc)


def creator_readable_handler_error(exc: BaseException, *, capability: str = "") -> str:
    """Creator-facing handler failure. Never HANDLER_ERROR + raw TypeError."""
    raw = str(exc).strip()
    name = type(exc).__name__
    if raw.startswith("HANDLER_ERROR:"):
        raw = raw.split(":", 1)[-1].strip()
    if name in {"SpatialCaptureGeometryError", "PropAttachmentError"} and raw:
        return raw
    details = f"{name}: {raw}" if raw else name
    low = raw.lower()
    if isinstance(exc, TypeError) and (
        "unsupported operand" in low or "nonetype" in low or "not supported between" in low
    ):
        return (
            "This request could not run because a Spatial Map placement is "
            "missing a world position (attached or unplaced). Place it on the "
            f"grid or attach it to a character, then try again. Details: {details}"
        )
    if name == "TypeError":
        return (
            "This request could not run because a value had the wrong type. "
            f"Details: {details}"
        )
    labels = {
        "ers.generate": "Environment Reference Sheet",
        "atlas.generate": "Atlas Shot",
        "image.generate": "Image generation",
        "scene.generate": "Scene generation",
        "storyboard.generate": "Storyboard",
    }
    label = labels.get(capability, "This action")
    if raw:
        return f"{label} could not start. Details: {details}"
    return f"{label} could not start. Details: {details}"


def _creator_readable_handler_error(exc: BaseException, capability: str = "") -> str:
    return creator_readable_handler_error(exc, capability=capability)


async def dispatch(
    db: Session,
    project_id: str,
    unified_intent: UnifiedIntent,
    context: dict[str, Any] | None = None,
    *,
    pre_approved: bool = False,
) -> ExecutionPlan:
    """Dispatch an executable intent through the real Adept UI pipeline.

    Returns an ExecutionPlan. If the capability requires approval and was not
    pre-approved, returns a plan with status=PREVIEW (not executed yet).
    """
    ctx = context or {}
    capability_id = unified_intent.capability
    cap = get_capability(capability_id)

    if cap is None:
        return ExecutionPlan(
            execution_id=str(uuid4()),
            capability=capability_id,
            project_id=project_id,
            status=ExecutionStatus.FAILED,
            error=f"UNKNOWN_CAPABILITY: {capability_id}",
            intent=unified_intent.intent.value,
            classifier_source=unified_intent.classifier_source,
            created_at=_now(),
            updated_at=_now(),
        )

    execution_id = str(uuid4())
    plan = ExecutionPlan(
        execution_id=execution_id,
        capability=capability_id,
        project_id=project_id,
        status=ExecutionStatus.PREPARING,
        surface_type=surface_type_for(capability_id),
        character_id=ctx.get("character_id"),
        scene_id=ctx.get("scene_id"),
        attachment_asset_ids=ctx.get("attachment_asset_ids", []),
        intent=unified_intent.intent.value,
        classifier_source=unified_intent.classifier_source,
        user_turn_id=ctx.get("user_turn_id"),
        provider=ctx.get("provider"),
        model=ctx.get("model"),
        created_at=_now(),
        updated_at=_now(),
    )

    # Check approval policy (spec §50).
    if cap.approval_policy != ApprovalPolicy.DIRECT and not pre_approved:
        if cap.handler_kind == HandlerKind.TOOL:
            # CDX-084: TOOL-kind capabilities never complete through the
            # CAPABILITY_HANDLER plan_only path. Bridge them to the
            # ProposalService: create the durable proposal now so the approve
            # endpoint / chat confirmation can execute it through
            # execute_approved_proposal instead of erroring.
            try:
                await _prepare_tool_proposal(db, project_id, plan, cap, unified_intent, ctx)
            except Exception as exc:
                logger.warning("Tool proposal preparation failed for %s: %s", cap.id, exc)
        elif cap.approval_policy == ApprovalPolicy.NEEDS_APPROVAL:
            # For NEEDS_APPROVAL, call the handler in plan_only mode to get the
            # generation plan before returning PREVIEW status.
            try:
                plan_result = _dispatch_capability_handler_plan_only(
                    db, project_id, plan, cap, unified_intent, ctx
                )
                if plan_result:
                    plan.plan_data = plan_result.get("plan_data", {})
            except Exception as exc:
                logger.warning("Plan-only dispatch failed: %s", exc)

        plan.status = ExecutionStatus.PREVIEW
        plan.error = "APPROVAL_REQUIRED"
        save_pack(db, project_id, plan)
        return plan

    # Dispatch based on handler kind.
    if cap.handler_kind == HandlerKind.CAPABILITY_HANDLER:
        return _dispatch_capability_handler(db, project_id, plan, cap, unified_intent, ctx)
    elif cap.handler_kind == HandlerKind.TOOL:
        return await _dispatch_tool(
            db, project_id, plan, cap, unified_intent, ctx, pre_approved=pre_approved
        )
    else:
        plan.status = ExecutionStatus.FAILED
        plan.error = f"UNSUPPORTED_HANDLER_KIND: {cap.handler_kind}"
        save_pack(db, project_id, plan)
        return plan


ZERO_JOBS_ERROR = "No valid scene-generation jobs were created."


def _apply_handler_result(
    plan: ExecutionPlan,
    result: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> ExecutionPlan:
    """Populate a plan from a capability-handler result with the
    ZERO-JOBS LAW enforced.

    A handler result with no child jobs is TERMINAL (failed with a clear
    error) — never QUEUED/RUNNING. This makes an infinite 0/0 work surface
    impossible at the source: no EXECUTION_STARTED event is published for
    a zero-job result, and no poller can ever hang on an empty pack.
    """
    plan.child_jobs = [
        ChildJobView(
            job_id=cj["job_id"],
            label=cj.get("label", ""),
            status=ChildJobStatus(cj.get("status", "queued")),
            child_index=cj.get("child_index", i),
            metadata=cj.get("metadata", {}),
            asset_id=cj.get("asset_id"),
            error=cj.get("error"),
        )
        for i, cj in enumerate(result.get("child_jobs", []))
    ]
    plan.planned_steps = result.get("planned_steps", [])
    plan.surface_type = result.get("surface_type", plan.surface_type)
    if result.get("character_id"):
        plan.character_id = result.get("character_id", plan.character_id)
    if result.get("spatial_map_id"):
        plan.plan_data = {**dict(plan.plan_data or {}), "spatial_map_id": result.get("spatial_map_id")}
    # Retry context snapshot (scene generation): keep the inputs so a
    # frontend Retry can start a FRESH transaction with the same intent.
    if context and isinstance(context, dict):
        retry_ctx = {
            "shot_requests_raw": context.get("shot_requests_raw"),
            "ers_package_id": context.get("ers_package_id"),
        }
        retry_ctx = {k: v for k, v in retry_ctx.items() if v is not None}
        if retry_ctx:
            plan.plan_data = {**dict(plan.plan_data or {}), "retryContext": retry_ctx}

    first_meta = ((result.get("child_jobs") or [{}])[0] or {}).get("metadata") or {}
    if first_meta.get("resolvedProvider") and not plan.provider:
        plan.provider = first_meta.get("resolvedProvider")
    if first_meta.get("resolvedWorkflowKey") and not plan.model:
        plan.model = first_meta.get("resolvedWorkflowKey")

    # Phase 6 contract: expose accepted/rejected/jobIds on the plan.
    if "accepted" in result or "rejected" in result or "job_ids" in result:
        plan.plan_data = {
            **dict(plan.plan_data or {}),
            "accepted": int(result.get("accepted") or len(plan.child_jobs)),
            "rejected": int(result.get("rejected") or 0),
            "jobIds": list(result.get("job_ids") or [c.job_id for c in plan.child_jobs]),
        }

    if not plan.child_jobs:
        # ZERO-JOBS LAW: zero accepted jobs is a terminal failure state.
        plan.status = ExecutionStatus.FAILED
        plan.error = str(result.get("error") or ZERO_JOBS_ERROR)
        plan.progress = 0.0
        return plan

    plan.status = ExecutionStatus.QUEUED
    plan.recompute_progress()
    return plan


def _dispatch_capability_handler(
    db: Session,
    project_id: str,
    plan: ExecutionPlan,
    cap: CapabilityDefinition,
    unified_intent: UnifiedIntent,
    ctx: dict[str, Any],
) -> ExecutionPlan:
    """Dispatch to a capability handler module."""
    handle = _resolve_handler(cap.id)
    if handle is None:
        plan.status = ExecutionStatus.FAILED
        plan.error = "CAPABILITY_NOT_IMPLEMENTED"
        save_pack(db, project_id, plan)
        return plan

    try:
        # Build handler kwargs from the execution decision, filtered to
        # only what the handler accepts (avoid unexpected keyword errors).
        import inspect

        sig = inspect.signature(handle)
        accepted = set(sig.parameters.keys())
        all_kwargs = {
            "db": db,
            "project_id": project_id,
            "execution_id": plan.execution_id,
            "prompt": ctx.get("prompt", ""),
            "character_name": ctx.get("character_name", ""),
            "character_id": ctx.get("character_id", ""),
            "scene_id": ctx.get("scene_id", ""),
            "visual_style": ctx.get("visual_style", ""),
            "attachment_asset_ids": ctx.get("attachment_asset_ids", []),
            "scene_description": ctx.get("scene_description") or ctx.get("sceneDescription") or "",
            "scene_intent": ctx.get("scene_intent") or ctx.get("sceneIntent"),
            "aspect_ratio": ctx.get("aspect_ratio", "16:9"),
            "count": ctx.get("count", 1),
            "user_instructions": ctx.get("user_instructions", ""),
            "project_style": ctx.get("project_style", ""),
            "scene_context": ctx.get("scene_context"),
            "character_names": ctx.get("character_names"),
            "frame_index": ctx.get("frame_index", 0),
            "frame_metadata": ctx.get("frame_metadata"),
            "reference_asset_id": ctx.get("reference_asset_id"),
            "plan_data": ctx.get("plan_data"),
            "spatial_map_id": ctx.get("spatial_map_id") or ctx.get("spatialMapId"),
            "ers_package_id": ctx.get("ers_package_id"),
            "shot_requests_raw": ctx.get("shot_requests_raw"),
            "output_count": ctx.get("output_count"),
            "name": ctx.get("name"),
            "description": ctx.get("description"),
            "hosted_model_id": ctx.get("hosted_model_id") or ctx.get("hostedModelId") or "",
            "model": ctx.get("model") or ctx.get("modelId") or "",
            "model_family_preference": ctx.get("model_family_preference")
            or ctx.get("modelFamilyPreference")
            or "",
            "source": ctx.get("source") or ctx.get("providerKind") or ctx.get("provider_kind") or "",
            "kie_image_model_id": ctx.get("kie_image_model_id") or ctx.get("kieImageModelId") or "",
            "fal_image_model_id": ctx.get("fal_image_model_id") or ctx.get("falImageModelId") or "",
            "provider_kind": ctx.get("provider_kind") or ctx.get("providerKind") or "",
            "hostedModelId": ctx.get("hostedModelId") or ctx.get("hosted_model_id") or "",
            "forceWorkflowKey": ctx.get("forceWorkflowKey") or ctx.get("force_workflow_key") or "",
            "lockModelFamily": bool(ctx.get("lockModelFamily") or ctx.get("lock_model_family")),
            "kieImageModelId": ctx.get("kieImageModelId") or ctx.get("kie_image_model_id") or "",
            "panel_task": ctx.get("panel_task") or ctx.get("panelTask") or "",
            "panelTask": ctx.get("panelTask") or ctx.get("panel_task") or "",
            "visual_canon_corrections": ctx.get("visual_canon_corrections")
            or ctx.get("visualCanonCorrections"),
        }
        handler_kwargs = {k: v for k, v in all_kwargs.items() if k in accepted}

        result = handle(**handler_kwargs)

        # Populate the plan from the handler result (zero-job results are
        # terminal — never QUEUED with an empty work surface).
        plan = _apply_handler_result(plan, result, context=ctx)

        save_pack(db, project_id, plan)

        if plan.is_terminal:
            # ZERO-JOBS LAW: publish failure, never a started-with-zero event.
            _publish_event(ExecutionEvent(
                event_type=ExecutionEventType.EXECUTION_FAILED,
                project_id=project_id,
                execution_id=plan.execution_id,
                status="failed",
                error=plan.error,
                surface_type=plan.surface_type,
                total=0,
                timestamp=_now(),
            ))
            return plan

        # Publish execution.started event (only when real jobs exist).
        _publish_event(ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_STARTED,
            project_id=project_id,
            execution_id=plan.execution_id,
            status="queued",
            surface_type=plan.surface_type,
            total=plan.total_children,
            timestamp=_now(),
        ))

        return plan

    except Exception as exc:
        logger.exception("Capability handler %s failed", cap.id)
        plan.status = ExecutionStatus.FAILED
        plan.error = creator_readable_handler_error(exc, capability=cap.id)
        save_pack(db, project_id, plan)
        return plan


def _dispatch_capability_handler_plan_only(
    db: Session,
    project_id: str,
    plan: ExecutionPlan,
    cap: CapabilityDefinition,
    unified_intent: UnifiedIntent,
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    """Call the capability handler in plan_only mode to get the generation plan.

    Used by NEEDS_APPROVAL capabilities to generate plan_data (shot plan)
    without enqueueing GPU jobs. The plan_data is stored in the ExecutionPlan
    and later presented to the user for approval.
    """
    handle = _resolve_handler(cap.id)
    if handle is None:
        return None
    try:
        import inspect

        sig = inspect.signature(handle)
        accepted = set(sig.parameters.keys())
        all_kwargs = {
            "db": db,
            "project_id": project_id,
            "execution_id": plan.execution_id,
            "prompt": ctx.get("prompt", ""),
            "character_name": ctx.get("character_name", ""),
            "character_id": ctx.get("character_id", ""),
            "scene_id": ctx.get("scene_id", ""),
            "visual_style": ctx.get("visual_style", ""),
            "attachment_asset_ids": ctx.get("attachment_asset_ids", []),
            "count": ctx.get("count", 1),
            "user_instructions": ctx.get("user_instructions", ""),
            "project_style": ctx.get("project_style", ""),
            "scene_context": ctx.get("scene_context"),
            "character_names": ctx.get("character_names"),
            "spatial_map_id": ctx.get("spatial_map_id") or ctx.get("spatialMapId"),
            "plan_only": True,
        }
        handler_kwargs = {k: v for k, v in all_kwargs.items() if k in accepted}
        result = handle(**handler_kwargs)
        return result
    except Exception as exc:
        logger.exception("Plan-only handler call failed for %s", cap.id)
        return None


async def approve_and_execute(
    db: Session,
    project_id: str,
    execution_id: str,
) -> ExecutionPlan | None:
    """Approve a pending plan and execute it.

    Loads the PREVIEW execution pack, calls the handler with the saved
    plan_data, and returns the now-executing plan (same execution_id).

    Only works for executions in PREVIEW status that have plan_data.
    """
    plan = load_pack(db, project_id, execution_id)
    if not plan:
        return None
    if plan.status != ExecutionStatus.PREVIEW:
        logger.warning(
            "Cannot approve execution %s: status is %s, not PREVIEW",
            execution_id, plan.status,
        )
        return None
    if not plan.plan_data:
        logger.warning("Cannot approve execution %s: no plan_data", execution_id)
        return None

    cap = get_capability(plan.capability)
    if cap is None:
        plan.status = ExecutionStatus.FAILED
        plan.error = "APPROVE_FAILED: capability not found"
        save_pack(db, project_id, plan)
        return plan

    if cap.handler_kind == HandlerKind.TOOL:
        # CDX-084: TOOL-kind capabilities execute through the ProposalService
        # approved path — the proposal was created at dispatch time.
        return await _approve_tool_execution(db, project_id, plan, cap)
    if cap.handler_kind != HandlerKind.CAPABILITY_HANDLER:
        plan.status = ExecutionStatus.FAILED
        plan.error = "APPROVE_FAILED: non-capability handler"
        save_pack(db, project_id, plan)
        return plan

    handle = _resolve_handler(cap.id)
    if handle is None:
        plan.status = ExecutionStatus.FAILED
        plan.error = "APPROVE_FAILED: handler not found"
        save_pack(db, project_id, plan)
        return plan

    try:
        import inspect

        sig = inspect.signature(handle)
        accepted = set(sig.parameters.keys())
        all_kwargs = {
            "db": db,
            "project_id": project_id,
            "execution_id": plan.execution_id,
            "prompt": "",
            "character_name": "",
            "character_id": plan.character_id or "",
            "scene_id": plan.scene_id or "",
            "visual_style": plan.plan_data.get("style_context", ""),
            "attachment_asset_ids": plan.attachment_asset_ids,
            "count": len(plan.plan_data.get("outputs", [])),
            "user_instructions": "",
            "project_style": "",
            "scene_context": plan.plan_data.get("scene_context"),
            "character_names": [
                c["name"] for c in plan.plan_data.get("references", {}).get("character_refs", [])
            ],
            "plan_only": False,
            "plan_data": plan.plan_data,
        }
        handler_kwargs = {k: v for k, v in all_kwargs.items() if k in accepted}
        result = handle(**handler_kwargs)

        plan = _apply_handler_result(plan, result, context=plan.plan_data)

        save_pack(db, project_id, plan)

        if plan.is_terminal:
            _publish_event(ExecutionEvent(
                event_type=ExecutionEventType.EXECUTION_FAILED,
                project_id=project_id,
                execution_id=plan.execution_id,
                status="failed",
                error=plan.error,
                surface_type=plan.surface_type,
                total=0,
                timestamp=_now(),
            ))
            return plan

        _publish_event(ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_STARTED,
            project_id=project_id,
            execution_id=plan.execution_id,
            status="queued",
            surface_type=plan.surface_type,
            total=plan.total_children,
            timestamp=_now(),
        ))

        return plan

    except Exception as exc:
        logger.exception("Approve and execute failed for %s", cap.id)
        plan.status = ExecutionStatus.FAILED
        plan.error = f"APPROVE_EXECUTE_ERROR: {exc}"
        save_pack(db, project_id, plan)
        return plan


def _tool_params(ctx: dict[str, Any]) -> dict[str, Any]:
    """Tool arguments for a TOOL-kind capability from the execution context.

    The deterministic context does not populate tool_params itself; the
    caller (REST body context / chat enrichment) supplies structured tool
    arguments under tool_params. The tool registry's sanitizer drops
    unknown keys, so this stays safe even when the context only carries
    free-form keys.
    """
    params = ctx.get("tool_params") or {}
    return params if isinstance(params, dict) else {}


def _extract_asset_id(tool_result: Any) -> str | None:
    """Best-effort single asset id from an approved tool result (if any)."""
    if not isinstance(tool_result, dict):
        return None
    for key in ("assetId", "asset_id", "id"):
        value = tool_result.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _receipt_error_text(receipt: Any) -> str:
    err = getattr(receipt, "error", None)
    if isinstance(err, dict):
        return str(err.get("message") or err)
    return str(err) if err else "APPROVE_EXECUTE_FAILED"


async def _prepare_tool_proposal(
    db: Session,
    project_id: str,
    plan: ExecutionPlan,
    cap: CapabilityDefinition,
    unified_intent: UnifiedIntent,
    ctx: dict[str, Any],
) -> None:
    """Create the durable Proposal for a TOOL-kind capability (CDX-084).

    Uses the canonical ToolExecutionService.propose so the proposal gets
    the same server-side preview, sanitization, resource pinning, and input
    hash as any chat-path tool proposal. Nothing is applied here — the human
    decision happens at approve time.
    """
    from ..tools.execution import ToolExecutionService

    tool_id = cap.tool_ids[0] if cap.tool_ids else ""
    if not tool_id:
        return
    proposal = await ToolExecutionService.propose(
        db,
        project_id=project_id,
        tool_id=tool_id,
        arguments=_tool_params(ctx),
        scene_id=ctx.get("scene_id"),
        request_id=ctx.get("user_turn_id") or ctx.get("request_id"),
        created_by=str(ctx.get("user_id") or "assistant"),
    )
    plan.proposal_id = proposal.id
    plan.plan_data = {"proposal_id": proposal.id, "tool_id": tool_id}


async def _approve_tool_execution(
    db: Session,
    project_id: str,
    plan: ExecutionPlan,
    cap: CapabilityDefinition,
) -> ExecutionPlan:
    """Execute an approved TOOL-kind capability through the ProposalService.

    The proposal was created at dispatch time (PREVIEW status). Approving it
    records the human decision and replays the proposal's stored arguments
    through ToolExecutionService.execute_approved_proposal — the same
    approved path a chat proposal approval uses (CDX-084).
    """
    from ..bible.proposals import ProposalService

    proposal_id = plan.proposal_id or ((plan.plan_data or {}).get("proposal_id"))
    if not proposal_id:
        plan.status = ExecutionStatus.FAILED
        plan.error = "APPROVE_FAILED: no proposal recorded for tool capability"
        save_pack(db, project_id, plan)
        return plan

    try:
        receipt = ProposalService.approve(db, project_id, proposal_id, note=None, decided_by="user")
    except Exception as exc:  # noqa: BLE001 - surface the specific failure to the user
        logger.exception("Tool proposal approval failed for %s", cap.id)
        plan.status = ExecutionStatus.FAILED
        plan.error = f"APPROVE_FAILED: {exc}"
        save_pack(db, project_id, plan)
        return plan

    ok = receipt.status == "success"
    asset_id = _extract_asset_id(getattr(receipt, "toolResult", None)) if ok else None
    plan.child_jobs = [
        ChildJobView(
            job_id=str(uuid4()),
            label=cap.title,
            status=ChildJobStatus.COMPLETED if ok else ChildJobStatus.FAILED,
            child_index=0,
            asset_id=asset_id,
            error=None if ok else _receipt_error_text(receipt),
        )
    ]
    if asset_id and asset_id not in plan.result_asset_ids:
        plan.result_asset_ids.append(asset_id)
    plan.recompute_progress()
    save_pack(db, project_id, plan)

    _publish_event(ExecutionEvent(
        event_type=ExecutionEventType.EXECUTION_STARTED,
        project_id=project_id,
        execution_id=plan.execution_id,
        status="completed" if ok else "failed",
        surface_type=plan.surface_type,
        timestamp=_now(),
    ))
    return plan


async def _dispatch_tool(
    db: Session,
    project_id: str,
    plan: ExecutionPlan,
    cap: CapabilityDefinition,
    unified_intent: UnifiedIntent,
    ctx: dict[str, Any],
    *,
    pre_approved: bool = False,
) -> ExecutionPlan:
    """Dispatch to an existing tool in the registry (CDX-084).

    Routes by the tool's own contract instead of assuming every tool executes
    through the audited path:
    - read tools → ToolExecutionService.execute_read
    - audited mutating tools (requires_approval=False) → execute_audited
    - approval-gated mutating tools → ProposalService bridge: the proposal is
      created (preview + pinned args), and only a pre-approved dispatch (or the
      approve endpoint) executes it through execute_approved_proposal.
    """
    from ..errors import CoDirectorError
    from ..tools import registry as tool_registry
    from ..tools.execution import ToolExecutionService

    tool_id = cap.tool_ids[0] if cap.tool_ids else ""
    if not tool_id:
        plan.status = ExecutionStatus.FAILED
        plan.error = "NO_TOOL_ID"
        save_pack(db, project_id, plan)
        return plan

    definition = tool_registry.find(tool_id)
    if definition is None:
        plan.status = ExecutionStatus.FAILED
        plan.error = f"TOOL_NOT_REGISTERED: {tool_id}"
        save_pack(db, project_id, plan)
        return plan

    request_id = ctx.get("user_turn_id") or ctx.get("request_id")
    try:
        if definition.kind == "read":
            invocation = await ToolExecutionService.execute_read(
                db,
                project_id=project_id,
                tool_id=tool_id,
                arguments=_tool_params(ctx),
                scene_id=ctx.get("scene_id"),
                request_id=request_id,
                created_by=str(ctx.get("user_id") or "assistant"),
            )
            ok = invocation.status == "succeeded"
            asset_id = _extract_asset_id(getattr(invocation, "result", None))
            error = None if ok else (invocation.errorMessage or "TOOL_EXECUTION_FAILED")
        elif definition.kind == "mutating" and not definition.requires_approval:
            invocation = await ToolExecutionService.execute_audited(
                db,
                project_id=project_id,
                tool_id=tool_id,
                arguments=_tool_params(ctx),
                scene_id=ctx.get("scene_id"),
                request_id=request_id,
                created_by=str(ctx.get("user_id") or "assistant"),
            )
            ok = invocation.status == "succeeded"
            asset_id = _extract_asset_id(getattr(invocation, "result", None))
            error = None if ok else (invocation.errorMessage or "TOOL_EXECUTION_FAILED")
        else:
            # Approval-gated mutating tool → ProposalService bridge. The
            # proposal is created even for a pre-approved dispatch so the
            # approval decision stays in the audit ledger.
            proposal = await ToolExecutionService.propose(
                db,
                project_id=project_id,
                tool_id=tool_id,
                arguments=_tool_params(ctx),
                scene_id=ctx.get("scene_id"),
                request_id=request_id,
                created_by=str(ctx.get("user_id") or "assistant"),
            )
            plan.proposal_id = proposal.id
            plan.plan_data = {"proposal_id": proposal.id, "tool_id": tool_id}
            if not pre_approved:
                plan.status = ExecutionStatus.PREVIEW
                plan.error = "APPROVAL_REQUIRED"
                save_pack(db, project_id, plan)
                return plan
            from ..bible.proposals import ProposalService

            receipt = ProposalService.approve(db, project_id, proposal.id, note=None, decided_by="user")
            ok = receipt.status == "success"
            asset_id = _extract_asset_id(getattr(receipt, "toolResult", None)) if ok else None
            error = None if ok else _receipt_error_text(receipt)

        job_id = str(uuid4())
        plan.child_jobs = [
            ChildJobView(
                job_id=job_id,
                label=cap.title,
                status=ChildJobStatus.COMPLETED if ok else ChildJobStatus.FAILED,
                child_index=0,
                asset_id=asset_id,
                error=error,
            )
        ]
        if asset_id and asset_id not in plan.result_asset_ids:
            plan.result_asset_ids.append(asset_id)
        plan.recompute_progress()
        save_pack(db, project_id, plan)

        _publish_event(ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_STARTED,
            project_id=project_id,
            execution_id=plan.execution_id,
            status="completed" if ok else "failed",
            surface_type=plan.surface_type,
            timestamp=_now(),
        ))

        return plan

    except CoDirectorError as err:
        logger.warning("Tool dispatch for %s rejected: %s", cap.id, err.code)
        plan.status = ExecutionStatus.FAILED
        plan.error = f"TOOL_ERROR: {err.code}: {err.message}"
        save_pack(db, project_id, plan)
        return plan
    except Exception as exc:
        logger.exception("Tool dispatch for %s failed", cap.id)
        plan.status = ExecutionStatus.FAILED
        plan.error = f"TOOL_ERROR: {exc}"
        save_pack(db, project_id, plan)
        return plan
