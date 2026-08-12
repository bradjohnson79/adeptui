from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .errors import InstallJobError
from .heartbeat import InstallHeartbeat
from .states import InstallState

StallStatus = Literal["none", "possible_stall", "interrupted", "waiting_for_source"]


class RecoveryAction(BaseModel):
    action: str
    label: str
    description: str
    enabled: bool = True
    destructive: bool = False


class RequiredNodeResolution(BaseModel):
    node_type: str = Field(alias="nodeType")
    extension_component_id: str | None = Field(default=None, alias="extensionComponentId")
    source_status: str = Field(alias="sourceStatus")
    message: str

    model_config = {"populate_by_name": True}


class RequiredComponentResolution(BaseModel):
    capability_id: str = Field(alias="capabilityId")
    workflow_ids: list[str] = Field(default_factory=list, alias="workflowIds")
    required_node_types: list[str] = Field(default_factory=list, alias="requiredNodeTypes")
    missing_node_types: list[str] = Field(default_factory=list, alias="missingNodeTypes")
    required_component_ids: list[str] = Field(default_factory=list, alias="requiredComponentIds")
    missing_component_ids: list[str] = Field(default_factory=list, alias="missingComponentIds")
    node_resolutions: list[RequiredNodeResolution] = Field(
        default_factory=list,
        alias="nodeResolutions",
    )
    status: str = "unknown"
    recommended_action: str | None = Field(default=None, alias="recommendedAction")
    message: str = ""
    checked_at: str | None = Field(default=None, alias="checkedAt")

    model_config = {"populate_by_name": True}


class InstallJob(BaseModel):
    id: str
    component_id: str = Field(alias="componentId")
    component_name: str = Field(alias="componentName")
    state: InstallState
    kind: str
    phase: str | None = None
    message: str = ""
    progress_bytes: int | None = Field(default=None, alias="progressBytes")
    total_bytes: int | None = Field(default=None, alias="totalBytes")
    percent: float | None = None
    indeterminate: bool = False
    files_completed: int | None = Field(default=None, alias="filesCompleted")
    files_total: int | None = Field(default=None, alias="filesTotal")
    queue_position: int | None = Field(default=None, alias="queuePosition")
    active: bool = False
    terminal: bool = False
    recoverable: bool = False
    capabilities: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)
    destination: str | None = None
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    completed_at: str | None = Field(default=None, alias="completedAt")
    preflight: dict[str, Any] = Field(default_factory=dict)
    error: InstallJobError | None = None
    recovery_actions: list[RecoveryAction] = Field(default_factory=list, alias="recoveryActions")
    heartbeat: InstallHeartbeat | None = None
    stall_status: StallStatus = Field(default="none", alias="stallStatus")
    stall_label: str | None = Field(default=None, alias="stallLabel")
    phase_steps: list[dict[str, str]] = Field(default_factory=list, alias="phaseSteps")
    raw: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}
