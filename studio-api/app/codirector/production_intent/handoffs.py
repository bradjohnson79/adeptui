"""Specialist handoff contracts (W6P-7) — propose only, never builders."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from .compiler import compile_intent
from .schemas import ProductionOperation, SpecialistHandoff
from .store import get_intent_store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def create_handoff(
    *,
    project_id: str,
    specialist_id: str,
    task_type: str,
    inputs: Optional[dict[str, Any]] = None,
    constraints: Optional[dict[str, Any]] = None,
    expected_outputs: Optional[list[str]] = None,
    recommended_operation: Optional[ProductionOperation | str] = None,
    parent_intent_id: Optional[str] = None,
) -> SpecialistHandoff:
    handoff = SpecialistHandoff(
        handoffId=str(uuid4()),
        parentIntentId=parent_intent_id,
        specialistId=specialist_id,
        taskType=task_type,
        inputs=dict(inputs or {}),
        constraints=dict(constraints or {}),
        expectedOutputs=list(expected_outputs or []),
        recommendedOperation=recommended_operation,  # type: ignore[arg-type]
        approvalState="awaiting_approval",
        executionState="draft",
        projectId=project_id,
        createdAt=_now(),
    )
    get_intent_store().save_handoff(handoff)
    return handoff


def handoff_to_intent(handoff: SpecialistHandoff, *, db: Any = None):
    """Compile a ProductionIntent from specialist recommendation — does not execute."""
    op = handoff.recommendedOperation or "video.scene_render"
    inp = handoff.inputs or {}
    intent = compile_intent(
        project_id=handoff.projectId,
        operation=op,
        source_surface="specialist",
        scene_id=inp.get("sceneId"),
        shot_id=inp.get("shotId"),
        prompt=str(inp.get("prompt") or inp.get("text") or ""),
        objective=str(inp.get("objective") or handoff.taskType),
        references=list(inp.get("references") or []),
        source_assets=[str(a) for a in (inp.get("sourceAssets") or []) if a],
        engine_preference=inp.get("engine"),
        workflow_preference=inp.get("workflowKey"),
        duration=float(inp["durationSec"]) if inp.get("durationSec") is not None else None,
        handoff_id=handoff.handoffId,
        parent_intent_id=handoff.parentIntentId,
        metadata={
            "specialistId": handoff.specialistId,
            "taskType": handoff.taskType,
            "constraints": handoff.constraints,
            "expectedOutputs": handoff.expectedOutputs,
        },
        db=db,
    )
    get_intent_store().save(intent)
    handoff.executionState = "awaiting_approval"
    get_intent_store().save_handoff(handoff)
    return intent


def attach_result(handoff: SpecialistHandoff, *, result_refs: list[str], execution_state: str = "completed"):
    handoff.resultRefs = list(result_refs)
    handoff.executionState = execution_state  # type: ignore[assignment]
    get_intent_store().save_handoff(handoff)
    return handoff
