"""M42 W47 frozen Docker runtime contracts (schema_version 1)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1

RuntimeClassification = Literal["core_mandatory", "official_optional", "user_added"]
RuntimeOwnership = Literal["adept_core", "adept_official", "user"]
RuntimeReadiness = Literal[
    "unverified",
    "inspecting",
    "building",
    "installing",
    "testing",
    "tested_locally",
    "ready",
    "disabled",
    "update_available",
    "degraded",
    "error",
    "requires_repair",
]
RuntimeLifecycleState = Literal[
    "absent",
    "created",
    "starting",
    "running",
    "stopping",
    "stopped",
    "restarting",
    "removing",
    "error",
]
RuntimeModality = Literal["llm", "video", "image", "audio", "multi"]
ExecutionClass = Literal["native_local", "docker_local", "hosted_api"]
StorageClass = Literal["core", "shared_optional", "private"]
UninstallOption = Literal[
    "ui_only",
    "container",
    "container_and_image",
    "container_image_and_private",
]


class RuntimeGpuRequirement(BaseModel):
    required: bool = True
    minimumVramGb: float = 0
    cpuFallback: bool = False


class RuntimeHealthCheck(BaseModel):
    type: Literal["http", "tcp", "none"] = "http"
    endpoint: str = "/system_stats"
    timeoutSeconds: int = 30


class RuntimeMountPolicy(BaseModel):
    hostClass: StorageClass | Literal["job_inputs", "job_outputs"] = "private"
    containerPath: str
    access: Literal["read_only", "read_write"] = "read_only"


class RuntimePortMapping(BaseModel):
    internalPort: int
    hostPort: Optional[int] = None


class RuntimeCapabilityDeclaration(BaseModel):
    id: str
    label: str
    modality: RuntimeModality = "video"
    supports: list[str] = Field(default_factory=list)


class RuntimeAdapterDeclaration(BaseModel):
    protocol: str = "comfyui"
    workflow: Optional[str] = None


class RuntimeSecurityPolicy(BaseModel):
    privileged: bool = False
    hostNetwork: bool = False
    dockerSocket: bool = False
    allowUnpinnedImages: bool = False


class RuntimeImageDescriptor(BaseModel):
    image: str
    digest: Optional[str] = None


class RuntimeBuildDescriptor(BaseModel):
    dockerfile: Optional[str] = None
    context: Optional[str] = None
    tag: Optional[str] = None


class AdeptRuntimeManifest(BaseModel):
    schemaVersion: int = SCHEMA_VERSION
    runtimeId: str
    name: str
    version: str = "1.0.0"
    classification: RuntimeClassification = "user_added"
    modality: RuntimeModality = "video"
    engine: str = "comfyui"
    source: str = "docker"
    image: RuntimeImageDescriptor
    build: Optional[RuntimeBuildDescriptor] = None
    internalPort: int = 8188
    restartPolicy: str = "unless-stopped"
    gpu: RuntimeGpuRequirement = Field(default_factory=RuntimeGpuRequirement)
    health: RuntimeHealthCheck = Field(default_factory=RuntimeHealthCheck)
    capabilities: list[RuntimeCapabilityDeclaration] = Field(default_factory=list)
    mounts: dict[str, RuntimeMountPolicy] = Field(default_factory=dict)
    adapter: RuntimeAdapterDeclaration = Field(default_factory=RuntimeAdapterDeclaration)
    security: RuntimeSecurityPolicy = Field(default_factory=RuntimeSecurityPolicy)
    envAllowlist: list[str] = Field(default_factory=list)


class DockerRuntimeDescriptor(BaseModel):
    id: str
    name: str
    version: str = "1.0.0"
    classification: RuntimeClassification
    ownership: RuntimeOwnership = "user"
    modality: RuntimeModality = "video"
    readiness: RuntimeReadiness = "unverified"
    lifecycle: RuntimeLifecycleState = "absent"
    executionClass: ExecutionClass = "docker_local"
    image: str = ""
    imageDigest: Optional[str] = None
    containerId: Optional[str] = None
    hostPort: Optional[int] = None
    healthOk: bool = False
    gpuReady: bool = False
    minimumVramGb: float = 0
    lastError: Optional[str] = None
    lastSuccessfulJobAt: Optional[str] = None
    uninstallAllowed: bool = True
    models: list[str] = Field(default_factory=list)
    nodes: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    manifest: Optional[AdeptRuntimeManifest] = None
    privateStoragePath: Optional[str] = None
    rollbackImage: Optional[str] = None
    disabled: bool = False


class RuntimeSecurityScanReport(BaseModel):
    ok: bool
    blocked: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RuntimeValidationReport(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RuntimeDependencyReport(BaseModel):
    missingModels: list[str] = Field(default_factory=list)
    missingNodes: list[str] = Field(default_factory=list)
    sharedArtifacts: list[str] = Field(default_factory=list)


class RuntimeInstallationPlan(BaseModel):
    runtimeId: str
    steps: list[str] = Field(default_factory=list)
    security: RuntimeSecurityScanReport
    validation: RuntimeValidationReport
    dependencies: RuntimeDependencyReport = Field(default_factory=RuntimeDependencyReport)
    estimatedDiskGb: float = 0


class RuntimeInstallationResult(BaseModel):
    ok: bool
    runtime: Optional[DockerRuntimeDescriptor] = None
    error: Optional[str] = None
    stepsCompleted: list[str] = Field(default_factory=list)


class RuntimeUsageReport(BaseModel):
    runtimeId: str
    activeJobs: int = 0
    queuedJobs: int = 0
    projectIds: list[str] = Field(default_factory=list)
    timelineBlocks: int = 0
    generationRecords: int = 0
    sharedArtifacts: list[dict[str, Any]] = Field(default_factory=list)
    privateStorageBytes: int = 0
    imageSizeBytes: int = 0
    rollbackAvailable: bool = False


class RuntimeUninstallPlan(BaseModel):
    runtimeId: str
    option: UninstallOption
    usage: RuntimeUsageReport
    willPreserve: list[str] = Field(default_factory=list)
    willRemove: list[str] = Field(default_factory=list)
    blockedReason: Optional[str] = None


class RuntimeUninstallResult(BaseModel):
    ok: bool
    runtimeId: str
    option: UninstallOption
    removed: list[str] = Field(default_factory=list)
    preserved: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    rolledBack: bool = False


class RuntimeGpuStatus(BaseModel):
    hostGpuVisible: bool = False
    containerGpuVisible: bool = False
    cudaAvailable: bool = False
    frameworkAccelerator: bool = False
    gpuModel: Optional[str] = None
    vramGb: Optional[float] = None
    cpuFallback: bool = False
    evidence: dict[str, Any] = Field(default_factory=dict)


class RuntimeHealthStatus(BaseModel):
    ok: bool
    lifecycle: RuntimeLifecycleState = "absent"
    detail: str = ""
    latencyMs: Optional[float] = None


class RuntimeDiagnosticReport(BaseModel):
    runtimeId: str
    platform: dict[str, Any] = Field(default_factory=dict)
    health: RuntimeHealthStatus
    gpu: RuntimeGpuStatus
    security: RuntimeSecurityScanReport
    issues: list[str] = Field(default_factory=list)


class RuntimeProvenance(BaseModel):
    runtimeId: str
    classification: RuntimeClassification
    image: str
    imageDigest: Optional[str] = None
    runtimeVersion: str = ""
    modelId: Optional[str] = None
    workflowId: Optional[str] = None
    gpuDevice: Optional[str] = None
    executionSource: ExecutionClass = "docker_local"
    fallbackUsed: bool = False


class InstalledRuntimeRegistry(BaseModel):
    schemaVersion: int = SCHEMA_VERSION
    runtimes: dict[str, DockerRuntimeDescriptor] = Field(default_factory=dict)
    sharedRefs: dict[str, int] = Field(default_factory=dict)
