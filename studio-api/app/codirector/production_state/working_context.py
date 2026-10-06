"""CoDirectorWorkingContext — compact persisted production working state.

Canonical stores (CRS, Spatial Map, PoseCraft scene, Library) remain
authoritative. This document references them. It is not a second SoT and
not a second Co-Director. Schema: working-context-v1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

WORKING_CONTEXT_SCHEMA = "working-context-v1"

ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW"]
MemoryLayer = Literal[
    "PROJECT",
    "SCENE",
    "SHOT",
    "PERFORMANCE",
    "RECENT_INTENT",
    "CANON",
    "OBSERVED",
    "USER_PREFERENCE",
]
AuthorityRank = Literal[
    "filmmaker_instruction",
    "approved_scene_shot",
    "crs_identity",
    "spatial_map_ers",
    "posecraft_performance",
    "observed_result",
    "inference",
    "stale_cache_preference",
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ProvenanceRecord(BaseModel):
    fact: str
    layer: MemoryLayer = "PROJECT"
    authority: AuthorityRank = "inference"
    source: str = ""
    at: str = Field(default_factory=_now)


class ApprovalRecord(BaseModel):
    what: str
    source: str = "creator"
    at: str = Field(default_factory=_now)
    sceneId: str = ""
    shotId: str = ""
    assetId: str = ""
    characterId: str = ""


class ConfirmationRecord(BaseModel):
    """Binds the original instruction to the creator's clarifying answer."""

    originalInstruction: str
    question: str
    answer: str
    resolved: bool = False
    at: str = Field(default_factory=_now)
    boundSceneId: str = ""
    boundCharacterId: str = ""


class PreferenceHint(BaseModel):
    """Workflow preference only. Never creative canon. Never Spatial Map / CRS."""

    hint: str
    source: str = "learning"
    at: str = Field(default_factory=_now)


class ConfidenceState(BaseModel):
    level: ConfidenceLevel = "LOW"
    reasons: list[str] = Field(default_factory=list)
    asked: bool = False
    question: str = ""
    locked: list[str] = Field(default_factory=list)
    changing: list[str] = Field(default_factory=list)


class SceneSlice(BaseModel):
    sceneId: str = ""
    name: str = ""
    approved: bool = False


class ShotSlice(BaseModel):
    shotId: str = ""
    framing: str = ""
    angle: str = ""
    elevationDegrees: float | None = None


class CameraSlice(BaseModel):
    framing: str = ""
    angle: str = ""
    elevationDegrees: float | None = None
    lensMm: float | None = None
    notes: str = ""


class PerformanceSlice(BaseModel):
    intent: str = ""
    posePresetId: str = ""
    posePresetName: str = ""
    semantic: list[str] = Field(default_factory=list)


class PoseCraftFigureRef(BaseModel):
    figureId: str
    characterId: str = ""
    name: str = ""
    archetypeId: str = ""
    modelId: str = ""
    posePresetId: str = ""
    posePresetName: str = ""
    jointStateRef: str = ""
    worldPosition: dict[str, float] = Field(default_factory=dict)
    worldOrientation: dict[str, float] = Field(default_factory=dict)
    contacts: list[str] = Field(default_factory=list)
    poseWorldStatePacketId: str = ""
    snapshotAssetId: str = ""


class PoseCraftSlice(BaseModel):
    sceneId: str = ""
    revision: int = 0
    activeFigureIds: list[str] = Field(default_factory=list)
    snapshotAssetId: str = ""
    worldOriginMeters: dict[str, float] = Field(default_factory=dict)
    poseWorldStatePacketIds: list[str] = Field(default_factory=list)
    figures: list[PoseCraftFigureRef] = Field(default_factory=list)


class CoDirectorWorkingContext(BaseModel):
    documentSchema: Literal["working-context-v1"] = WORKING_CONTEXT_SCHEMA
    activeProjectId: str
    activeSceneId: str = ""
    activeShotId: str = ""
    scene: SceneSlice = Field(default_factory=SceneSlice)
    performance: PerformanceSlice = Field(default_factory=PerformanceSlice)
    camera: CameraSlice = Field(default_factory=CameraSlice)
    posecraft: PoseCraftSlice = Field(default_factory=PoseCraftSlice)
    approvals: list[ApprovalRecord] = Field(default_factory=list)
    confirmations: list[ConfirmationRecord] = Field(default_factory=list)
    confidence: ConfidenceState = Field(default_factory=ConfidenceState)
    provenance: list[ProvenanceRecord] = Field(default_factory=list)
    preferenceHints: list[PreferenceHint] = Field(default_factory=list)
    updatedAt: str = Field(default_factory=_now)

    def pending_confirmation(self) -> ConfirmationRecord | None:
        for row in reversed(self.confirmations):
            if not row.resolved and row.question:
                return row
        return None


def empty_working_context(project_id: str) -> CoDirectorWorkingContext:
    return CoDirectorWorkingContext(activeProjectId=project_id)


def context_to_dict(ctx: CoDirectorWorkingContext) -> dict[str, Any]:
    return ctx.model_dump(mode="json")
