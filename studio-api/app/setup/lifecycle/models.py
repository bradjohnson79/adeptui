from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

LifecycleChainState = Literal[
    "discover",
    "compare",
    "verify_source",
    "review_install_plan",
    "approve",
    "install",
    "configure",
    "calibrate",
    "certify",
    "ready",
    "monitor",
    "update",
    "repair",
    "recertify",
    "archive",
    "remove",
]

LifecycleAttentionState = Literal[
    "repair_recommended",
    "repair_required",
    "failed",
    "incompatible",
    "update_available",
    "archived",
]


class MonitorFinding(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"] = "info"
    message: str
    recommendedAction: str | None = None


class LifecycleCapabilityBadge(BaseModel):
    id: str
    label: str
    enabled: bool


class CalibrationProfile(BaseModel):
    preferredPrecision: str | None = None
    nativeResolution: str | None = None
    vramUsageGb: float | None = None
    safeBatchSize: int | None = None
    maxRecommendedResolution: str | None = None
    avgGenerationSeconds: float | None = None
    recommendedScheduler: str | None = None
    defaultCfg: float | None = None
    optimalStepCount: int | None = None
    machineProfile: dict[str, Any] = Field(default_factory=dict)


class CertifiedRecipe(BaseModel):
    recipeId: str
    componentId: str
    title: str
    capabilityTags: list[str] = Field(default_factory=list)
    providerKind: Literal["local", "cloud"] = "local"
    installStrategy: str
    certifiedVersion: str
    certifiedDate: str
    source: dict[str, Any] = Field(default_factory=dict)
    requirements: dict[str, Any] = Field(default_factory=dict)
    calibrationDefaults: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class InstallPlan(BaseModel):
    componentId: str
    componentName: str
    action: Literal["install", "update", "repair", "link_existing"] = "install"
    lifecycleState: LifecycleChainState = "review_install_plan"
    requiresRuntimeConfirmation: bool = True
    requiresModelDownloadConfirmation: bool = False
    destinationRoot: str | None = None
    estimatedDownloadBytes: int | None = None
    estimatedInstalledBytes: int | None = None
    currentVersion: str | None = None
    targetVersion: str | None = None
    certifiedRecipeId: str | None = None
    recommendedSource: dict[str, Any] = Field(default_factory=dict)
    steps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class UpdatePlan(InstallPlan):
    updateReason: str | None = None


class ProviderCertificationRecord(BaseModel):
    componentId: str
    componentName: str
    status: Literal["ready", "repair_recommended", "repair_required", "failed", "archived"] = "ready"
    certified: bool = False
    certifiedVersion: str | None = None
    certifiedDate: str | None = None
    recipeId: str | None = None
    installJobId: str | None = None
    verificationSummary: str | None = None
    calibration: CalibrationProfile | None = None
    monitorFindings: list[MonitorFinding] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class ProviderLifecycleState(BaseModel):
    componentId: str
    componentName: str
    chainState: LifecycleChainState | None = None
    attentionState: LifecycleAttentionState | None = None
    statusLabel: str
    certified: bool = False
    certifiedRecipeId: str | None = None
    certifiedVersion: str | None = None
    certifiedDate: str | None = None
    installJobId: str | None = None
    installState: str | None = None
    verificationHealthy: bool | None = None
    verificationSummary: str | None = None
    monitorFindings: list[MonitorFinding] = Field(default_factory=list)
    calibration: CalibrationProfile | None = None
    recommendations: list[str] = Field(default_factory=list)

