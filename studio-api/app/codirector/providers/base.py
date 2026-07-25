"""Provider-neutral Co-Director contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol


@dataclass
class ProviderModel:
    id: str
    name: str
    size_bytes: int | None = None
    modified_at: str | None = None
    family: str | None = None
    parameter_size: str | None = None
    quantization: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "sizeBytes": self.size_bytes,
            "modifiedAt": self.modified_at,
            "family": self.family,
            "parameterSize": self.parameter_size,
            "quantization": self.quantization,
        }


@dataclass
class ProviderHealthResult:
    provider_id: str
    display_name: str
    status: str  # Ready | Not Running | Not Configured | Model Missing | No Models | Degraded
    reachable: bool
    endpoint: str
    selected_model: str | None
    model_available: bool
    models: list[ProviderModel] = field(default_factory=list)
    message: str = ""
    code: str | None = None
    recommended_action: str | None = None
    intelligence_enabled: bool = False
    vision_validation_enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "providerId": self.provider_id,
            "displayName": self.display_name,
            "status": self.status,
            "reachable": self.reachable,
            "endpoint": self.endpoint,
            "selectedModel": self.selected_model,
            "modelAvailable": self.model_available,
            "models": [m.to_dict() for m in self.models],
            "message": self.message,
            "code": self.code,
            "recommendedAction": self.recommended_action,
            "intelligenceEnabled": self.intelligence_enabled,
            "visionValidationEnabled": self.vision_validation_enabled,
            "ok": self.status == "Ready",
        }


@dataclass
class ChatRequest:
    request_id: str
    messages: list[dict[str, str]]
    model_id: str | None
    project_context: str = ""
    temperature: float = 0.55
    mode: str = "chat"


@dataclass
class ChatResult:
    request_id: str
    reply: str
    model_id: str
    provider_id: str
    raw: dict[str, Any] = field(default_factory=dict)


class CoDirectorProvider(Protocol):
    id: str
    display_name: str

    async def health(self) -> ProviderHealthResult: ...

    async def list_models(self) -> list[ProviderModel]: ...

    async def generate(self, request: ChatRequest) -> ChatResult: ...

    def supports_stream(self) -> bool: ...

    def stream(self, request: ChatRequest) -> AsyncIterator[dict[str, Any]]: ...
