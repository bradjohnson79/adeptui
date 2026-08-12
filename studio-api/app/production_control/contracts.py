"""Frozen M42 Production Dock shared contracts — see docs/release-gate/m42/PRODUCTION_DOCK_SHARED_CONTRACTS.md."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

PreferenceScope = Literal["system", "user", "project"]
ProductionRuntimeSource = Literal["local", "api", "hybrid"]
CpuFallbackPolicy = Literal["disabled", "ask", "lightweight_only"]
CapabilityLabel = Literal[
    "Certified",
    "Testing",
    "Available",
    "Unavailable",
    "Unsupported",
    "Requires Setup",
    "Loading",
    "Error",
]
LocalLifecycle = Literal[
    "Installed",
    "Loading",
    "Loaded",
    "Unloading",
    "VRAM insufficient",
    "Worker offline",
    "Dependency error",
    "CPU-only framework detected",
]
Modality = Literal["llm", "video", "image", "audio"]
RoutingPreference = Literal[
    "local_preferred",
    "hosted_preferred",
    "ask_before_switching",
    "manual_only",
]
ThemePreference = Literal["aurora-night", "aurora-day", "system"]
GpuStatus = Literal["Ready", "Unavailable", "Unknown"]


ExecutionClass = Literal["native_local", "docker_local", "hosted_api"]


class ModelDescriptor(BaseModel):
    id: str
    modality: Modality
    label: str
    locality: Literal["local", "hosted"]
    """W47 additive: Native Local / Docker Local / Hosted API honesty."""
    executionClass: Optional[ExecutionClass] = None
    runtimeId: Optional[str] = None
    providerId: Optional[str] = None
    capabilityLabel: CapabilityLabel
    lifecycle: Optional[LocalLifecycle] = None
    supports: list[str] = Field(default_factory=list)
    doesNotSupport: list[str] = Field(default_factory=list)
    estimatedVramGb: Optional[float] = None
    gpuCompatible: bool = False
    executable: bool = False


class ModelRoutingPreference(BaseModel):
    modality: Modality
    preference: RoutingPreference = "local_preferred"
    availableModelIds: list[str] = Field(default_factory=list)
    activeModelId: Optional[str] = None
    fallbackModelId: Optional[str] = None
    allowFallback: bool = False


class PreferenceProvenance(BaseModel):
    activeModelId: Optional[str] = None
    activeLabel: str = ""
    source: PreferenceScope = "system"
    fallbackPolicy: str = "disabled"
    gpu: GpuStatus = "Unknown"
    executable: bool = False
    blockedReason: Optional[str] = None
    runtime: Optional[str] = None
    providerId: Optional[str] = None
    cpuFallbackPolicy: CpuFallbackPolicy = "disabled"


class ResolvedSelection(BaseModel):
    modality: Modality
    activeModelId: Optional[str] = None
    activeLabel: str = ""
    source: PreferenceScope = "system"
    fallbackPolicy: str = "disabled"
    gpu: GpuStatus = "Unknown"
    executable: bool = False
    blockedReason: Optional[str] = None
    runtime: Optional[str] = None
    providerId: Optional[str] = None
    cpuFallbackPolicy: CpuFallbackPolicy = "disabled"
    availableModelIds: list[str] = Field(default_factory=list)
    fallbackModelId: Optional[str] = None
    allowFallback: bool = False
    provenance: PreferenceProvenance = Field(default_factory=PreferenceProvenance)


class UserGlobalPreferences(BaseModel):
    theme: ThemePreference = "aurora-night"
    dockCollapsed: bool = False
    dockAutoCollapse: bool = True
    runtimeSource: ProductionRuntimeSource = "hybrid"
    defaultHostedProviderId: Optional[str] = None
    cpuFallbackPolicy: CpuFallbackPolicy = "disabled"
    llm: ModelRoutingPreference = Field(
        default_factory=lambda: ModelRoutingPreference(modality="llm")
    )
    video: ModelRoutingPreference = Field(
        default_factory=lambda: ModelRoutingPreference(modality="video")
    )
    image: ModelRoutingPreference = Field(
        default_factory=lambda: ModelRoutingPreference(modality="image")
    )
    audio: ModelRoutingPreference = Field(
        default_factory=lambda: ModelRoutingPreference(modality="audio")
    )
    defaultVideoQuality: str = "balanced"
    defaultImageQuality: str = "balanced"
    defaultAudioQuality: str = "balanced"


class ProjectPreferences(BaseModel):
    projectId: str
    activeVideoModelId: Optional[str] = None
    activeImageModelId: Optional[str] = None
    activeAudioModelId: Optional[str] = None
    codirectorModelId: Optional[str] = None
    resolution: Optional[str] = None
    videoQuality: Optional[str] = None
    imageQuality: Optional[str] = None
    audioQuality: Optional[str] = None
    generatorLocks: dict[str, bool] = Field(default_factory=dict)


class ActiveModelSelection(BaseModel):
    modality: Modality
    activeModelId: Optional[str] = None
    availableModelIds: list[str] = Field(default_factory=list)
    fallbackModelId: Optional[str] = None
    allowFallback: bool = False
    provenance: PreferenceProvenance = Field(default_factory=PreferenceProvenance)
