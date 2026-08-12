"""Filesystem-friendly generation recipe contracts for character consistency."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .reference_roles import ReferenceRole
from .seed_policy import SeedPolicy


class RecipeReferenceAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(..., min_length=1)
    roles: list[ReferenceRole] = Field(default_factory=list)
    notes: str | None = None


class RecipeLoRA(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1)
    version: str | None = None
    weight: float | None = Field(default=None, ge=0.0)


class RecipeResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(..., ge=64)
    height: int = Field(..., ge=64)


class GenerationRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    recipe_id: str = Field(..., min_length=1)
    model_key: str = Field(..., min_length=1)
    workflow_version: str = Field(..., min_length=1)
    prompt_package_version: str = Field(..., min_length=1)
    reference_assets: list[RecipeReferenceAsset] = Field(default_factory=list)
    seed_policy: SeedPolicy
    seed: int = Field(..., ge=0)
    sampler: str = Field(..., min_length=1)
    scheduler: str = Field(..., min_length=1)
    steps: int = Field(..., ge=1)
    guidance: float = Field(..., ge=0.0)
    resolution: RecipeResolution
    vae: str | None = None
    loras: list[RecipeLoRA] = Field(default_factory=list)
    style: str | None = None
    negatives: list[str] = Field(default_factory=list)


def save_generation_recipe(recipe: GenerationRecipe, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(recipe.model_dump(mode="json"), indent=2), encoding="utf-8")
    return path


def load_generation_recipe(input_path: str | Path) -> GenerationRecipe:
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    return GenerationRecipe.model_validate(data)
