"""Bridge ProductionPlan compile → live ExecutionPlan.planned_steps.

Reconnects compile_execution_steps onto ExecutionStep / ExecutionPlan packs.
Not a second planner service — mapping helpers only. Deliberation remains sole
TalkAskAct authority; dispatcher remains pack authority after ACT.
"""

from __future__ import annotations

from typing import Any, Optional

from .compile import compile_execution_steps
from .plan_contracts import ProductionPlan, PlanStepStatus


def _lifecycle(raw: Any) -> str:
    if raw is None:
        return "PLANNED"
    if hasattr(raw, "value"):
        return str(raw.value)
    return str(raw or "PLANNED")


def bridge_compile_to_execution_steps(
    plan: ProductionPlan,
    *,
    parent_execution_id: str = "",
) -> list[dict[str, Any]]:
    """Map ProductionPlan → ExecutionStep-shaped dicts (top-level lineage fields).

    dependsOn uses stepId slots; parentExecutionId lineage stamped when present.
    """
    parent = parent_execution_id or plan.parentExecutionId or ""
    compiled = compile_execution_steps(plan)
    out: list[dict[str, Any]] = []
    for row in compiled:
        meta = dict(row.get("metadata") or {})
        step_id = str(meta.get("stepId") or "")
        depends = list(meta.get("dependsOn") or [])
        lifecycle = str(meta.get("lifecycleStatus") or "PLANNED")
        # ChildJobStatus for pack step status column (queued until ACT runs)
        status = "queued"
        if lifecycle in {"BLOCKED", "FAILED"}:
            status = "failed" if lifecycle == "FAILED" else "queued"
        elif lifecycle == "COMPLETED":
            status = "completed"
        elif lifecycle == "CANCELLED":
            status = "cancelled"
        out.append(
            {
                "step_index": int(row.get("step_index") or 0),
                "label": str(row.get("label") or ""),
                "capability": str(row.get("capability") or ""),
                "status": status,
                "asset_id": row.get("asset_id"),
                "error": row.get("error"),
                "metadata": {
                    **meta,
                    "producesAssetSlot": meta.get("producesAssetSlot"),
                    "requiredAssetIds": list(meta.get("requiredAssetIds") or []),
                    "resultAssetIds": list(meta.get("resultAssetIds") or []),
                    "input_asset_slot": (meta.get("params") or {}).get("input_asset_slot"),
                },
                "step_id": step_id,
                "depends_on": depends,
                "lifecycle_status": lifecycle,
                "result_asset_ids": list(meta.get("resultAssetIds") or []),
                "failure_reason": row.get("error"),
                "failure_reason_codes": list(meta.get("failureReasonCodes") or meta.get("reasonCodes") or []),
                "parent_execution_id": parent or meta.get("parentExecutionId") or None,
                "parent_step_id": meta.get("parentStepId") or None,
                "plan_id": str(meta.get("planId") or plan.planId or ""),
            }
        )
    return out


def apply_production_plan_to_pack(
    pack: Any,
    *,
    production_plan: Optional[dict[str, Any] | ProductionPlan] = None,
    planned_steps: Optional[list[dict[str, Any]]] = None,
    parent_execution_id: str = "",
) -> Any:
    """Stamp ExecutionPlan pack with bridged planned_steps + lineage join keys.

    Safe no-op when neither plan nor steps provided. Does not decide TalkAskAct.
    """
    plan_obj: Optional[ProductionPlan] = None
    if isinstance(production_plan, ProductionPlan):
        plan_obj = production_plan
    elif isinstance(production_plan, dict) and production_plan:
        try:
            plan_obj = ProductionPlan.model_validate(production_plan)
        except Exception:
            plan_obj = None

    steps = list(planned_steps or [])
    if not steps and plan_obj is not None:
        steps = bridge_compile_to_execution_steps(
            plan_obj,
            parent_execution_id=parent_execution_id
            or getattr(pack, "parent_execution_id", None)
            or "",
        )

    if not steps and not plan_obj:
        return pack

    # Coerce to ExecutionStep models when pack typing requires it.
    try:
        from app.codirector.execution.contracts import ExecutionStep

        coerced = [ExecutionStep.model_validate(s) if not isinstance(s, ExecutionStep) else s for s in steps]
    except Exception:
        coerced = steps

    if hasattr(pack, "planned_steps"):
        pack.planned_steps = coerced
    if plan_obj is not None:
        if hasattr(pack, "plan_id"):
            pack.plan_id = plan_obj.planId or getattr(pack, "plan_id", "") or ""
        parent = parent_execution_id or plan_obj.parentExecutionId
        if parent and hasattr(pack, "parent_execution_id"):
            pack.parent_execution_id = parent
        # Keep plan snapshot in plan_data for Retry / UI (non-authoritative).
        if hasattr(pack, "plan_data") and isinstance(pack.plan_data, dict):
            pack.plan_data = {
                **pack.plan_data,
                "production_plan": plan_obj.model_dump(mode="json"),
                "planner_bridge": True,
            }
    return pack


def dependency_blocked_steps(planned_steps: list[Any]) -> list[str]:
    """Return step_ids marked DEPENDENCY_BLOCKED / lifecycle BLOCKED."""
    blocked: list[str] = []
    for s in planned_steps or []:
        if isinstance(s, dict):
            life = str(s.get("lifecycle_status") or "")
            codes = list(s.get("failure_reason_codes") or [])
            meta = s.get("metadata") or {}
            codes = codes + list(meta.get("failureReasonCodes") or meta.get("reasonCodes") or [])
            sid = str(s.get("step_id") or meta.get("stepId") or "")
        else:
            life = _lifecycle(getattr(s, "lifecycle_status", ""))
            codes = list(getattr(s, "failure_reason_codes", None) or [])
            sid = str(getattr(s, "step_id", "") or "")
        if life == PlanStepStatus.BLOCKED.value or "DEPENDENCY_BLOCKED" in codes:
            if sid:
                blocked.append(sid)
    return blocked
