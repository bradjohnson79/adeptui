"""Planner ProductionPlan / PlanStep — compile-time contracts (cd-production-planner-v1).

Reconnect map (EXISTS before invent):
- Wave4 `plans/schemas.py:ProductionPlan` = durable plan persistence candidate
- `execution/contracts.py:ExecutionPlan` = post-ACT pack spine
- This module = deliberation-facing compile stub + multi-step graph

Does NOT decide TalkAskAct. Does NOT dispatch. Versioned; maps into Wave4 / ExecutionPlan.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

PLANNER_SCHEMA_VERSION: Literal["cd-production-planner-v1"] = "cd-production-planner-v1"


class PlanStepStatus(str, Enum):
    """Step lifecycle for planner/ExecutionPlan multi-step (additive to ChildJobStatus)."""

    PLANNED = "PLANNED"
    READY = "READY"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class CreatorDecision(BaseModel):
    """A creator-facing choice already made or still required."""

    key: str
    value: Any = None
    required: bool = False
    decided: bool = False
    question: str = ""


class PlanStep(BaseModel):
    """One capability-bound step with asset-ID dependency slots (not free-text deps)."""

    stepId: str = Field(default_factory=lambda: f"step-{uuid4().hex[:12]}")
    order: int = 0
    title: str = ""
    goal: str = ""
    capabilityId: str = ""  # must be CAPABILITY_REGISTRY id when dispatchable
    status: PlanStepStatus = PlanStepStatus.PLANNED

    # Asset-ID dependency slots (machine-readable)
    dependsOn: list[str] = Field(default_factory=list)  # stepIds
    requiredAssetIds: list[str] = Field(default_factory=list)
    producesAssetSlot: str = ""  # logical slot name e.g. "image_0"
    resultAssetIds: list[str] = Field(default_factory=list)

    params: dict[str, Any] = Field(default_factory=dict)
    routeLock: dict[str, Any] = Field(default_factory=dict)
    runtimeNeeds: list[str] = Field(default_factory=list)  # e.g. comfy, hosted_image
    risks: list[str] = Field(default_factory=list)
    reasonCodes: list[str] = Field(default_factory=list)
    failureReason: str = ""
    failureReasonCodes: list[str] = Field(default_factory=list)

    parentExecutionId: str = ""
    parentStepId: str = ""
    wave4StepId: str = ""  # join key to Wave4 ProductionPlanStep when persisted


class ProductionPlan(BaseModel):
    """Versioned multi-step production plan stub attached to DeliberationDecision.

    Maps to Wave4 ProductionPlan for durable storage; compiles to ExecutionPlan.planned_steps.
    """

    schemaVersion: Literal["cd-production-planner-v1"] = PLANNER_SCHEMA_VERSION
    planId: str = Field(default_factory=lambda: f"plan-{uuid4().hex[:12]}")
    version: int = 1
    goal: str = ""
    projectId: str = ""
    conversationId: str = ""

    steps: list[PlanStep] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    requiredAssets: list[str] = Field(default_factory=list)
    runtimeNeeds: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    creatorDecisions: list[CreatorDecision] = Field(default_factory=list)

    # Join keys (reconnect EXISTS)
    wave4PlanId: str = ""  # plans/schemas.ProductionPlan.planId when linked
    executionId: str = ""  # execution pack id when dispatched
    parentExecutionId: str = ""

    status: PlanStepStatus = PlanStepStatus.PLANNED
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def capability_ids(self) -> list[str]:
        caps = [s.capabilityId for s in self.steps if s.capabilityId]
        return list(dict.fromkeys(caps + list(self.capabilities)))

    def blocked_steps(self) -> list[PlanStep]:
        return [s for s in self.steps if s.status == PlanStepStatus.BLOCKED]

    def ready_steps(self) -> list[PlanStep]:
        done = {s.stepId for s in self.steps if s.status == PlanStepStatus.COMPLETED}
        ready: list[PlanStep] = []
        for s in self.steps:
            if s.status in {PlanStepStatus.COMPLETED, PlanStepStatus.SKIPPED, PlanStepStatus.CANCELLED}:
                continue
            if all(dep in done for dep in s.dependsOn):
                if s.status == PlanStepStatus.PLANNED:
                    ready.append(s)
                elif s.status == PlanStepStatus.READY:
                    ready.append(s)
            elif s.dependsOn:
                # dependency not satisfied → blocked
                pass
        return ready


class SelectivePreflight(BaseModel):
    """Structure-only preflight metadata for expensive / STRICT / multi-step turns.

    UI may render later; deliberation attaches when relevant. Not an act boss.
    """

    required: bool = False
    expensive: bool = False
    strict: bool = False
    multiStep: bool = False
    checks: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    runtimeNeeds: list[str] = Field(default_factory=list)
