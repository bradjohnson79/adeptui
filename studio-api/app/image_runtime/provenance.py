"""ImageProvenance schema (M42 W1) — QueueWorker write deferred to Wave 2."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class ImageProvenance(BaseModel):
    workflow: Optional[str] = None
    workflowVersion: Optional[str] = None
    runtime: str = "comfy"
    provider: str = "local"
    references: list[str] = Field(default_factory=list)
    prompt: str = ""
    seed: Optional[int] = None
    parentImages: list[str] = Field(default_factory=list)
    generationTime: Optional[str] = None
    validation: dict[str, Any] = Field(default_factory=dict)
    continuity: dict[str, Any] = Field(default_factory=dict)
    approval: dict[str, Any] = Field(default_factory=dict)
    projectLocation: Optional[str] = None
    intentId: Optional[str] = None
    toolId: Optional[str] = None
    settings: dict[str, Any] = Field(default_factory=dict)
    # LoRA provenance (Adept LoRA support): populated only when a LoRA was
    # actually applied. Keeps the asset reproducible/inspectable without a
    # separate LoRA history system.
    lora: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def executed_image_stamp(
    params: dict[str, Any] | None,
    *,
    contract_key: str = "",
    model: str = "",
) -> tuple[str, str, str]:
    """Resolve ImageProvenance provider/runtime/official model from the executed job.

    Hosted Kie/fal must stamp provider=kie|fal and the official model id.
    Local Comfy stays provider=local, runtime=comfy.
    selected = executed = provenance — do not inherit Production Dock local defaults.
    """
    params = params or {}
    runtime_block = params.get("imageRuntime") if isinstance(params.get("imageRuntime"), dict) else {}
    key = str(contract_key or runtime_block.get("workflowKey") or runtime_block.get("workflowId") or "").strip()
    raw_provider = str(runtime_block.get("provider") or params.get("provider") or "").strip().lower()
    if raw_provider in {"kie.ai", "kieai"}:
        raw_provider = "kie"
    if raw_provider in {"fal.ai", "falai"}:
        raw_provider = "fal"

    official_pin = str(
        runtime_block.get("officialModelId")
        or params.get("officialModelId")
        or ""
    ).strip()
    kie_official = str(
        runtime_block.get("kieImageModelId")
        or params.get("kieImageModelId")
        or params.get("kie_image_model_id")
        or ""
    ).strip()
    fal_official = str(
        runtime_block.get("falImageModelId")
        or params.get("falImageModelId")
        or params.get("fal_image_model_id")
        or ""
    ).strip()
    hosted = str(runtime_block.get("hostedModelId") or params.get("hostedModelId") or model or "").strip()

    if key.startswith("kie:") or raw_provider == "kie" or kie_official:
        official = ""
        if key.startswith("kie:") and key.split(":", 1)[1].strip():
            official = key.split(":", 1)[1].strip()
        official = official or official_pin or kie_official or hosted
        return "kie", "kie", official

    if raw_provider == "fal" or fal_official or key.startswith("fal:") or key.startswith("fal-ai/"):
        official = official_pin or fal_official or hosted or (key.split(":", 1)[1].strip() if key.startswith("fal:") else key)
        return "fal", "fal", official

    provider = raw_provider or "local"
    if provider in {"comfy", "comfyui", "local"}:
        provider = "local"
    runtime = str(runtime_block.get("engine") or runtime_block.get("runtime") or "comfy").strip() or "comfy"
    if runtime in {"comfyui"}:
        runtime = "comfy"
    return provider, runtime, hosted or model


class EditProvenance(ImageProvenance):
    """Extended provenance for Wave 4 edit operations — backward compatible with ImageProvenance."""

    operation: Optional[str] = None
    maskAssetIds: list[str] = Field(default_factory=list)
    controlAssetIds: list[str] = Field(default_factory=list)
    imageEditIntentId: Optional[str] = None
    sourceAssetId: Optional[str] = None
    controlType: Optional[str] = None
    compositeLayerAssetIds: list[str] = Field(default_factory=list)
    editParameters: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
