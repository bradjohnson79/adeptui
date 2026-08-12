from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

HealthCriticality = Literal["critical", "high", "standard", "optional"]
HealthCategory = Literal[
    "core",
    "project",
    "creative_studio",
    "provider",
    "runtime",
    "persistence",
    "jobs",
    "integration",
]
HealthStatus = Literal[
    "healthy",
    "ready",
    "connected",
    "busy",
    "starting",
    "slow",
    "degraded",
    "warning",
    "blocked",
    "failed",
    "offline",
    "timed_out",
    "not_installed",
    "disabled",
    "not_configured",
    "not_tested",
    "experimental",
    "unknown",
    "not_applicable",
]
StatusMode = Literal["standard", "deep"]
StatusIndicator = Literal["Operational", "Degraded", "Blocked", "Not Checked", "Checking"]


class RecoveryAction(BaseModel):
    id: str
    label: str
    description: str = ""
    kind: Literal["open_route", "open_panel", "open_logs", "refresh", "confirm_api"]
    path: Optional[str] = None
    panel: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    requiresConfirmation: bool = False


class HealthCheckDefinition(BaseModel):
    id: str
    title: str
    description: str
    category: HealthCategory
    criticality: HealthCriticality
    standard: bool = True
    deep: bool = True
    projectScoped: bool = False
    sceneScoped: bool = False
    recoveryActions: list[RecoveryAction] = Field(default_factory=list)


class HealthCheckResult(BaseModel):
    checkId: str
    title: str
    category: HealthCategory
    criticality: HealthCriticality
    status: HealthStatus
    score: int
    summary: str
    message: str = ""
    durationMs: int = 0
    timeoutMs: Optional[int] = None
    awaitedDependency: Optional[str] = None
    lastHealthyAt: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    recoveryActions: list[RecoveryAction] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    checkedAt: str
    timedOut: bool = False
    partial: bool = False
    stale: bool = False


class HealthCategoryTally(BaseModel):
    category: HealthCategory
    label: str
    total: int
    healthy: int
    warnings: int
    blocked: int


class HealthExplainability(BaseModel):
    band: str
    dominantChecks: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class HealthRunSummary(BaseModel):
    statusIndicator: StatusIndicator
    score: int
    band: str
    mode: StatusMode
    totalChecks: int
    healthyChecks: int
    warningChecks: int
    blockedChecks: int
    checkedAt: str
    scoreExplanation: str


class HealthRun(BaseModel):
    runId: str
    mode: StatusMode
    projectId: Optional[str] = None
    sceneId: Optional[str] = None
    workspace: Optional[str] = None
    startedAt: str
    completedAt: str
    partial: bool = False
    cancelled: bool = False
    summary: HealthRunSummary
    categories: list[HealthCategoryTally]
    explainability: HealthExplainability
    results: list[HealthCheckResult]


class StatusCheckRequest(BaseModel):
    projectId: Optional[str] = None
    sceneId: Optional[str] = None
    workspace: Optional[str] = None
    checkIds: list[str] = Field(default_factory=list)


class DeepDiagnosticRequest(StatusCheckRequest):
    confirm: bool = False
