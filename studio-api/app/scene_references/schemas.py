"""Pydantic schemas for Scene Reference Bindings."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SceneReferenceBindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(..., min_length=1)
    scope_type: str
    scope_id: str
    reference_type: str
    usage_modes: list[str] = Field(default_factory=list)
    reference_roles: list[str] = Field(default_factory=list)
    identity_id: Optional[str] = None
    identity_version_id: Optional[str] = None
    variant_ids: list[str] = Field(default_factory=list)
    enabled: bool = True
    order_index: Optional[int] = None
    requested_weight: Optional[float] = None
    notes: Optional[str] = None
    alias: Optional[str] = None
    media_kind: Optional[str] = None


class SceneReferenceBindingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_type: Optional[str] = None
    usage_modes: Optional[list[str]] = None
    reference_roles: Optional[list[str]] = None
    identity_id: Optional[str] = None
    identity_version_id: Optional[str] = None
    variant_ids: Optional[list[str]] = None
    enabled: Optional[bool] = None
    order_index: Optional[int] = None
    requested_weight: Optional[float] = None
    notes: Optional[str] = None
    alias: Optional[str] = None
    media_kind: Optional[str] = None


class SceneReferenceBindingOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    schema_version: int
    project_id: str
    asset_id: str
    scope_type: str
    scope_id: str
    reference_type: str
    usage_modes: list[str]
    reference_roles: list[str]
    identity_id: Optional[str] = None
    identity_version_id: Optional[str] = None
    variant_ids: list[str] = Field(default_factory=list)
    enabled: bool
    order_index: int
    requested_weight: Optional[float] = None
    notes: Optional[str] = None
    alias: Optional[str] = None
    media_kind: Optional[str] = None
    display_token: Optional[str] = None
    broken: bool = False
    broken_reason: Optional[str] = None
    alias_adjusted: bool = False
    inherited_from: Optional[str] = None
    is_override: bool = False
    asset_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    approval_status: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ReorderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding_ids: list[str]


class ApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding_ids: list[str]
    target_scopes: list[dict[str, str]]
    mode: str = "copy"  # copy | replace


class CopyFromSceneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_scope_type: str = "scene"
    source_scope_id: str
    target_scope_type: str = "scene"
    target_scope_id: str


class PreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: str
    scope_id: str
    workflow_key: str
    override_binding_ids: list[str] = Field(default_factory=list)


class ResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: str
    scope_id: str
    include_inherited: bool = True


class EnqueueProvenanceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding_ids: list[str]
    selected_asset_ids: list[str]
    selected_identity_version_ids: list[str]
    continuity_packet_id: Optional[str] = None
    workflow_capability_key: str
    selection_reasons: dict[str, str]
    excluded_reference_ids: list[str]
    exclusion_reasons: dict[str, str]
    extras: dict[str, Any] = Field(default_factory=dict)
