"""Execution plan contracts — machine-readable plans for Co-Director execution.

Spec §14: "The execution plan should be machine-readable and traceable."
Spec §15: "Each long-running execution needs: execution_id, job_id, project_id,
capability, provider, model, status, progress, created_at, updated_at,
result_asset_ids, error."
Spec §16: "Support batch work. Parent/child jobs."

The execution pack (parent) tracks child jobs. One failure must not destroy
completed siblings (spec §16).

FROZEN CONTRACT — Law #16. Do not change field names without primary approval.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    """Spec §15 states: queued, preparing, running, preview, completed, failed, cancelled."""

    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    PREVIEW = "preview"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChildJobStatus(str, Enum):
    """Per-child job status (mirrors Studio Job states)."""

    QUEUED = "queued"
    RUNNING = "running"
    PREVIEW = "preview"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionStep(BaseModel):
    """One step in a multi-step execution plan (spec §14)."""

    step_index: int
    label: str = ""
    capability: str = ""
    job_id: Optional[str] = None
    status: ChildJobStatus = ChildJobStatus.QUEUED
    asset_id: Optional[str] = None
    error: Optional[str] = None
    # Shot/frame metadata for storyboard steps.
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChildJobView(BaseModel):
    """A child job in the execution pack — drives the Live Agent Work Surface."""

    job_id: str
    label: str = ""
    status: ChildJobStatus = ChildJobStatus.QUEUED
    asset_id: Optional[str] = None
    error: Optional[str] = None
    # Progress 0.0–1.0 for this child (stage-based, never invented — spec §20).
    progress: float = 0.0
    stage: str = ""
    # Index within the pack (e.g. Frame 1, Frame 2).
    child_index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    """The full execution plan — the parent of a pack of child jobs.

    Persisted as a JSON pack trait (mirrors the visual_sheet pack pattern)
    in the project's trait store. The `advance` endpoint polls and updates
    this plan by checking each child job's real status.
    """

    execution_id: str
    capability: str
    project_id: str
    character_id: Optional[str] = None
    scene_id: Optional[str] = None

    # The pack status (parent). One child failure does not fail the pack.
    status: ExecutionStatus = ExecutionStatus.QUEUED
    progress: float = 0.0  # completed_children / total_children

    # Child jobs — the core of the work surface.
    child_jobs: list[ChildJobView] = Field(default_factory=list)

    # Steps that were planned (spec §14) — populated before dispatch.
    planned_steps: list[ExecutionStep] = Field(default_factory=list)

    # Result assets — populated as children complete.
    result_asset_ids: list[str] = Field(default_factory=list)

    # Collection ID if results are grouped (e.g. storyboard collection).
    collection_id: Optional[str] = None

    # Surface type for the Live Agent Work Surface.
    surface_type: str = ""

    # Error details (only when the pack itself fails, not individual children).
    error: Optional[str] = None

    # Provider/model provenance (spec §15, §35).
    provider: Optional[str] = None
    model: Optional[str] = None

    # Attachment IDs used as references (spec §12).
    attachment_asset_ids: list[str] = Field(default_factory=list)

    # Observability trace (spec §48).
    user_turn_id: Optional[str] = None
    intent: str = ""
    classifier_source: str = ""

    created_at: str = ""
    updated_at: str = ""

    @property
    def total_children(self) -> int:
        return len(self.child_jobs)

    @property
    def completed_children(self) -> int:
        return sum(1 for c in self.child_jobs if c.status == ChildJobStatus.COMPLETED)

    @property
    def failed_children(self) -> int:
        return sum(1 for c in self.child_jobs if c.status == ChildJobStatus.FAILED)

    @property
    def is_terminal(self) -> bool:
        return self.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED)

    def recompute_progress(self) -> None:
        """Recompute parent progress from child statuses."""
        if not self.child_jobs:
            return
        done = self.completed_children
        total = self.total_children
        self.progress = done / total if total > 0 else 0.0

        # Parent status reflects children (spec §46 — one failure doesn't destroy siblings).
        if all(c.status == ChildJobStatus.COMPLETED for c in self.child_jobs):
            self.status = ExecutionStatus.COMPLETED
        elif all(c.status in (ChildJobStatus.COMPLETED, ChildJobStatus.FAILED) for c in self.child_jobs):
            # All children resolved; if any failed, pack is FAILED (but siblings kept).
            if self.failed_children > 0:
                self.status = ExecutionStatus.FAILED
            else:
                self.status = ExecutionStatus.COMPLETED
        elif any(c.status == ChildJobStatus.RUNNING for c in self.child_jobs):
            self.status = ExecutionStatus.RUNNING
        elif any(c.status == ChildJobStatus.QUEUED for c in self.child_jobs):
            self.status = ExecutionStatus.QUEUED
