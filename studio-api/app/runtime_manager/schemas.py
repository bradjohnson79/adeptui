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


class TunnelStatus(BaseModel):
    status: ServiceStatus
    ownership: ServiceOwnership = ServiceOwnership.EXTERNAL
    hostname: Optional[str] = None


class GpuInfo(BaseModel):
    detected: bool = False
    name: Optional[str] = None
    driver: Optional[str] = None
    vram_total_mib: Optional[int] = None


class RuntimeManagerPreferences(BaseModel):
    comfyuiBackgroundManagerEnabled: bool = False
    localhostBackgroundManagerEnabled: bool = False
    startWithWindows: bool = False
    remoteAccessEnabled: bool = False


class RuntimeManagerStatus(BaseModel):
    comfyui: ComfyUiStatus
    studioApi: StudioApiStatus
    ollama: OllamaStatus
    tunnel: TunnelStatus
    gpu: GpuInfo
    preferences: RuntimeManagerPreferences


class RuntimeActionResponse(BaseModel):
    success: bool
    message: str
    status: Optional[RuntimeManagerStatus] = None
