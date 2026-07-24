"""Reference / IC-LoRA model definitions and shared constants."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ReferenceIngredientRole = Literal[
    "character",
    "costume",
    "prop",
    "vehicle",
    "environment",
    "architecture",
    "lighting",
    "style",
    "other",
]

StrengthPreset = Literal["subtle", "balanced", "strong"]

STRENGTH_PRESETS: dict[str, float] = {
    "subtle": 0.8,
    "balanced": 1.4,
    "strong": 1.8,
}

ERROR_CODES = (
    "ic_lora_model_missing",
    "ic_lora_model_incompatible",
    "ic_lora_authorization_required",
    "ic_lora_workflow_missing",
    "ic_lora_nodes_missing",
    "ic_lora_metadata_invalid",
    "reference_sheet_missing",
    "reference_sheet_invalid",
    "reference_upload_failed",
    "reference_mapping_failed",
    "compiled_workflow_invalid",
)

INGREDIENTS_MODEL_ID = "ltx23_ic_lora_ingredients"
INGREDIENTS_FILENAME = "ltx-2.3-22b-ic-lora-ingredients-0.9.safetensors"
INGREDIENTS_HF_REPO = "Lightricks/LTX-2.3-22b-IC-LoRA-Ingredients"
WORKFLOW_KEY = "ltx.ingredients_ic_lora"
WORKFLOW_VERSION = "1.0.0"


@dataclass(frozen=True)
class ReferenceModelDefinition:
    id: str
    display_name: str
    family: str
    type: str
    purpose: str
    source_provider: str
    repository: str
    filename: str
    gated: bool
    base_models: tuple[str, ...]
    workflows: tuple[str, ...]
    target_model_category: str
    required_files: tuple[str, ...]
    license_name: str = "ltx-2-community-license"

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "displayName": self.display_name,
            "family": self.family,
            "type": self.type,
            "purpose": self.purpose,
            "source": {
                "provider": self.source_provider,
                "repository": self.repository,
                "filename": self.filename,
                "gated": self.gated,
            },
            "compatibility": {
                "baseModels": list(self.base_models),
                "workflows": list(self.workflows),
            },
            "install": {
                "targetModelCategory": self.target_model_category,
                "requiredFiles": list(self.required_files),
            },
            "licenseName": self.license_name,
        }


REFERENCE_MODELS: tuple[ReferenceModelDefinition, ...] = (
    ReferenceModelDefinition(
        id=INGREDIENTS_MODEL_ID,
        display_name="LTX 2.3 Ingredients IC-LoRA",
        family="ltx-2.3",
        type="ic-lora",
        purpose="ingredients-reference",
        source_provider="huggingface",
        repository=INGREDIENTS_HF_REPO,
        filename=INGREDIENTS_FILENAME,
        gated=True,
        base_models=("ltx_checkpoint", "ltx-2.3-22b"),
        workflows=(WORKFLOW_KEY,),
        target_model_category="loras",
        required_files=(INGREDIENTS_FILENAME,),
    ),
)

REFERENCE_MODELS_BY_ID = {m.id: m for m in REFERENCE_MODELS}


def get_reference_model(model_id: str = INGREDIENTS_MODEL_ID) -> ReferenceModelDefinition:
    try:
        return REFERENCE_MODELS_BY_ID[model_id]
    except KeyError as exc:
        raise KeyError(f"Unknown reference model: {model_id}") from exc


def resolve_strength(preset: str | None, value: float | None = None) -> tuple[str, float]:
    if value is not None:
        key = preset if preset in STRENGTH_PRESETS else "balanced"
        return key, float(value)
    key = preset if preset in STRENGTH_PRESETS else "balanced"
    return key, float(STRENGTH_PRESETS[key])


@dataclass
class ReferenceError(Exception):
    code: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:  # noqa: D105
        return self.message

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details or {}}


# Aliases used by queue_worker / diagnostics
IcLoraError = ReferenceError
ERR_REFERENCE_UPLOAD_FAILED = "reference_upload_failed"
ERR_IC_LORA_NODES_MISSING = "ic_lora_nodes_missing"
ERR_IC_LORA_MODEL_MISSING = "ic_lora_model_missing"
ERR_IC_LORA_AUTHORIZATION_REQUIRED = "ic_lora_authorization_required"
ERR_IC_LORA_MODEL_INCOMPATIBLE = "ic_lora_model_incompatible"
INGREDIENTS_WORKFLOW_VERSION = WORKFLOW_VERSION
