from pydantic import BaseModel
from typing import Optional
from enum import Enum


class ServiceOwnership(str, Enum):
    OWNED = "owned"
    REUSED = "reused"
    EXTERNAL = "external"


class ServiceStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    NOT_CONFIGURED = "not_configured"
    STARTING = "starting"


class ComfyUiStatus(BaseModel):
    status: ServiceStatus
    ownership: ServiceOwnership = ServiceOwnership.EXTERNAL
    logicalId: str = "runtime.comfy"
    version: Optional[str] = None
    device: Optional[str] = None
    vram_total: Optional[int] = None


class StudioApiStatus(BaseModel):
    status: ServiceStatus
    ownership: ServiceOwnership = ServiceOwnership.EXTERNAL
    workers: Optional[int] = None


class OllamaStatus(BaseModel):
    status: ServiceStatus
    ownership: ServiceOwnership = ServiceOwnership.EXTERNAL
    version: Optional[str] = None
    logicalId: str = "runtime.local_llm"
    configured: bool = False
    daemonOnline: bool = False
    modelReady: bool = False
    requiredModel: Optional[str] = None
    models: list[str] = []
    pid: Optional[int] = None
    message: Optional[str] = None


class TunnelStatus(BaseModel):
    status: ServiceStatus
    ownership: ServiceOwnership = ServiceOwnership.EXTERNAL
    hostname: Optional[str] = None


class GpuInfo(BaseModel):
    detected: bool = False
    name: Optional[str] = None
    driver: Optional[str] = None
    vram_total_mib: Optional[int] = None
    vram_used_mib: Optional[int] = None
    vram_free_mib: Optional[int] = None
    source: str = "nvidia-smi"


class RouteAStatus(BaseModel):
    status: ServiceStatus
    ownership: ServiceOwnership = ServiceOwnership.EXTERNAL
    logicalId: str = "runtime.video"
    port: int = 8192
    adeptOwnedReady: bool = False
    message: Optional[str] = None


class GpuAdmission(BaseModel):
    dualResident: bool = False
    comfyuiAllowed: bool = True
    routeAAllowed: bool = True
    reason: Optional[str] = None


class RuntimeManagerPreferences(BaseModel):
    comfyuiBackgroundManagerEnabled: bool = False
    localhostBackgroundManagerEnabled: bool = False
    startWithWindows: bool = False
    remoteAccessEnabled: bool = False


class ChildRuntimeStatus(BaseModel):
    pid: Optional[int] = None
    owned: bool = False
    startedAt: Optional[str] = None
    health: str = "unknown"
    port: Optional[int] = None
    lastExit: Optional[str] = None
    restartCount: int = 0
    lastRestartReason: Optional[str] = None
    logPath: Optional[str] = None


class AdeptRuntimeServiceStatus(BaseModel):
    configured: bool = False
    taskRegistered: bool = False
    startWithWindows: bool = False
    windowsStartupPresent: bool = False
    legacyOwners: list[str] = []
    canonicalTask: str = "AdeptRuntimeService"
    serviceState: str = "offline"
    comfyState: str = "offline"
    worker: str = "idle"
    falConnected: Optional[bool] = None
    creatorMessage: str = ""
    comfyPid: Optional[int] = None
    owned: bool = False
    managerPid: Optional[int] = None
    controlPlaneReachable: Optional[bool] = None
    studioApiPid: Optional[int] = None
    studioApiOwned: bool = False
    studioApiHealth: str = "unknown"
    studioApiStartedAt: Optional[str] = None
    studioApiChild: Optional[ChildRuntimeStatus] = None
    comfyChild: Optional[ChildRuntimeStatus] = None


class RuntimeManagerStatus(BaseModel):
    comfyui: ComfyUiStatus
    studioApi: StudioApiStatus
    ollama: OllamaStatus
    tunnel: TunnelStatus
    gpu: GpuInfo
    routeA: Optional[RouteAStatus] = None
    gpuAdmission: Optional[GpuAdmission] = None
    preferences: RuntimeManagerPreferences
    adeptRuntime: Optional[AdeptRuntimeServiceStatus] = None
    logicalServices: dict[str, dict] = {}  # noqa: RUF012 — pydantic default copied per instance


class EnableRecommendedBody(BaseModel):
    startWithWindows: bool = True


class RuntimeActionResponse(BaseModel):
    success: bool
    message: str
    status: Optional[RuntimeManagerStatus] = None


class RuntimeConfigValidation(BaseModel):
    """Read-only configuration check. Never starts, stops, or restarts services."""

    ok: bool
    message: str
    errors: list[str] = []
    source: str = "saved"
