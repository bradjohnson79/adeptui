"""Pydantic request/response schemas for timeline reference APIs."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class AddBindingRequest(BaseModel):
    referenceAssetId: str
    role: str
    influence: str = "moderate"
    source: str = "project_asset"
    bibleEntityStableId: Optional[str] = None
    bibleVersionId: Optional[str] = None
    sourceTimelineItemId: Optional[str] = None
    label: str = ""
    notes: str = ""


class PatchBindingRequest(BaseModel):
    role: Optional[str] = None
    influence: Optional[str] = None
    label: Optional[str] = None
    notes: Optional[str] = None
    sortOrder: Optional[int] = None
    expectedVersion: Optional[int] = None


class ClearReferencesRequest(BaseModel):
    expectedVersion: Optional[int] = None


class RestoreVersionRequest(BaseModel):
    expectedVersion: Optional[int] = None


class CreatePresetRequest(BaseModel):
    name: str
    description: str = ""
    bindings: list[AddBindingRequest] = Field(default_factory=list)


class ApplyPresetRequest(BaseModel):
    presetId: str
    mode: Literal["replace", "merge"] = "replace"
    expectedVersion: Optional[int] = None


class ValidatePackageRequest(BaseModel):
    providerHints: dict[str, Any] = Field(default_factory=dict)
