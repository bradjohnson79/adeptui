"""Canonical continuity contract — one structured truth for ERS instruction packets.

English and Chinese are compiled views of this schema. They are never independent
authorities. Additive to Visual Canon; not a second environment database.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

COMPILER_VERSION = "cd-multimodal-continuity-v1"

FactStatus = Literal[
    "observed",
    "creator_confirmed",
    "spatial_map_authoritative",
    "inferred",
    "uncertain",
]

HARD_FACT_STATUSES: frozenset[str] = frozenset(
    {"observed", "creator_confirmed", "spatial_map_authoritative"}
)

PanelTask = Literal[
    "whole_sheet",
    "hero",
    "top_down",
    "greybox",
    "elevation",
    "east_elevation",
    "occupied_scale",
    "materials",
]

SourceType = Literal["original_environment", "atlas"]


class SourceAuthority(BaseModel):
    assetId: str = ""
    type: SourceType | str = "original_environment"
    lineageFingerprint: str = ""
    isPixelAuthority: bool = True


class ActorPlacement(BaseModel):
    actor: str = ""
    characterId: str = ""
    zone: str = ""
    landmark: str = ""
    relativePosition: str = ""
    barrierSide: str = ""
    facing: str = ""
    forbiddenZones: list[str] = Field(default_factory=list)
    gridCell: str = ""
    miniPrompt: str = ""
    factStatus: FactStatus | str = "uncertain"
    occludedFrom: list[str] = Field(default_factory=list)


class PropPlacement(BaseModel):
    prop: str = ""
    propId: str = ""
    landmark: str = ""
    relativePosition: str = ""
    attachedTo: str = ""
    gridCell: str = ""
    factStatus: FactStatus | str = "uncertain"
    occludedFrom: list[str] = Field(default_factory=list)


class CameraTask(BaseModel):
    panelTask: PanelTask | str = "whole_sheet"
    view: str = ""
    note: str = ""


class CanonicalContinuity(BaseModel):
    """One production-truth record. Hard constraints are only high-status facts."""

    environmentIdentity: dict[str, Any] = Field(default_factory=dict)
    geometry: dict[str, Any] = Field(default_factory=dict)
    fixedArchitecture: dict[str, Any] = Field(default_factory=dict)
    persistentFurniture: dict[str, Any] = Field(default_factory=dict)
    materials: dict[str, Any] = Field(default_factory=dict)
    lighting: dict[str, Any] = Field(default_factory=dict)
    spatialRelationships: list[str] = Field(default_factory=list)
    actors: list[ActorPlacement] = Field(default_factory=list)
    props: list[PropPlacement] = Field(default_factory=list)
    hardInvariants: list[str] = Field(default_factory=list)
    forbiddenChanges: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    factStatus: dict[str, str] = Field(default_factory=dict)
    cameraTask: CameraTask = Field(default_factory=CameraTask)
    sourceAuthority: SourceAuthority = Field(default_factory=SourceAuthority)
    occlusionNotes: list[str] = Field(default_factory=list)
    sceneTitle: str = ""
    locationType: str = ""


class InstructionPacket(BaseModel):
    compilerVersion: str = COMPILER_VERSION
    referenceImage: dict[str, str] = Field(default_factory=dict)
    continuityJson: CanonicalContinuity = Field(default_factory=CanonicalContinuity)
    englishPrompt: str = ""
    chinesePrompt: str = ""
    hardInvariants: list[str] = Field(default_factory=list)
    forbiddenChanges: list[str] = Field(default_factory=list)
    panelTask: PanelTask | str = "whole_sheet"
    provider: str = ""
    providerPrompt: str = ""
    fingerprint: str = ""
    syncOk: bool = True
    syncConflicts: list[str] = Field(default_factory=list)


class ContinuityCompileError(RuntimeError):
    """Blocked compilation — do not enqueue the provider request."""

    def __init__(self, message: str, *, field: str = "", conflicts: list[str] | None = None):
        super().__init__(message)
        self.field = field
        self.conflicts = list(conflicts or [])
