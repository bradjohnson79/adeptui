"""Image job contract + stages (M42 W1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class ImageJobStage(str, Enum):
    PLANNING = "Planning"
    RESOLVING = "Resolving"
    WAITING_FOR_APPROVAL = "WaitingForApproval"
    QUEUED = "Queued"
    PREPARING = "Preparing"
    PREPARING_CONTROLS = "PreparingControls"
    PREPARING_MASKS = "PreparingMasks"
    LOADING_MODELS = "LoadingModels"
    SAMPLING = "Sampling"
    COMPOSITING = "Compositing"
    SAVING = "Saving"
    VALIDATING = "Validating"
    REGISTERING_ASSET = "RegisteringAsset"
    CREATING_VERSION = "CreatingVersion"
    RETRYING = "Retrying"
    COMPLETED = "Completed"
    CANCELLING = "Cancelling"
    CANCELLED = "Cancelled"
    FAILED = "Failed"


class ProviderKindImage(str, Enum):
    LOCAL = "local"
    EXTERNAL_API = "external_api"


@dataclass
class ImageJobContract:
    """Parallel to VideoJobContract — embedded as imageRuntime in job params (Wave 2 enforcement)."""

    intent: str = ""
    workflow_key: str | None = None
    workflow_id: str | None = None
    workflow_version: str | None = None
    category: str | None = None
    provider_kind: ProviderKindImage = ProviderKindImage.LOCAL
    engine: str = "zimage"
    stage: ImageJobStage = ImageJobStage.QUEUED
    reference_ids: list[str] = field(default_factory=list)
    intent_id: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["provider_kind"] = self.provider_kind.value
        d["provider"] = self.provider_kind.value
        d["stage"] = self.stage.value
        return d


def merge_image_runtime_history(history: dict[str, Any], contract: ImageJobContract) -> dict[str, Any]:
    out = dict(history or {})
    out["imageRuntime"] = contract.to_dict()
    return out
