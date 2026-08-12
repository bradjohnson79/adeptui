"""ImageIntent — product→runtime language. No Bible/story payloads."""

from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

ImageOperation = Literal[
    "image.generate",
    "image.edit",
    "image.upscale",
    "image.inpaint",
    "image.outpaint",
    "image.chroma_key",
    "image.reference",
    "image.storyboard_frame",
]


class ImageIntent(BaseModel):
    """Executable intent. CreativeContext stays outside — only referenceIds + prefs enter runtime."""

    intentId: str = Field(default_factory=lambda: str(uuid4()))
    projectId: str
    operation: ImageOperation = "image.generate"
    purpose: str = ""
    prompt: str = ""
    negativePrompt: str = ""
    referenceIds: list[str] = Field(default_factory=list)
    style: dict[str, Any] = Field(default_factory=dict)
    quality: str = "standard"
    providerPreference: str = "local"
    workflowPreference: Optional[str] = None
    enginePreference: Optional[str] = None
    approvalPolicy: str = "awaiting_approval"
    seed: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    sourceAssetId: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Traceability only — not CreativeContext content
    creativeContextDigest: Optional[str] = None
    productionIntentId: Optional[str] = None

    def to_resolver_request(self) -> dict[str, Any]:
        return {
            "modality": "image",
            "intent": self.operation,
            "engine": self.enginePreference or "zimage",
            "workflowPreference": self.workflowPreference,
            "prompt": self.prompt,
            "referenceIds": list(self.referenceIds),
            "sourceAssetId": self.sourceAssetId,
            "providerPreference": self.providerPreference,
        }

    def to_image_runtime_block(self, contract: dict[str, Any] | None = None) -> dict[str, Any]:
        contract = contract or {}
        return {
            "intent_id": self.intentId,
            "operation": self.operation,
            "workflow_key": contract.get("workflowKey") or contract.get("workflow_key") or self.workflowPreference,
            "workflow_id": contract.get("workflowId") or contract.get("workflow_id"),
            "workflow_version": contract.get("workflowVersion") or contract.get("workflow_version"),
            "category": contract.get("category"),
            "provider_kind": contract.get("providerKind") or self.providerPreference or "local",
            "engine": contract.get("engine") or self.enginePreference or "zimage",
            "reference_ids": list(self.referenceIds),
            "creative_context_digest": self.creativeContextDigest,
        }
