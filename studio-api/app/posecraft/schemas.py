"""PoseCraft API contracts (mirror of the TypeScript PoseCraft v1.1 types)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

POSECRAFT_SCHEMA_VERSION = 2

JointName = Literal[
    "pelvis", "spine", "chest", "neck", "head",
    "leftShoulder", "leftElbow", "leftWrist",
    "rightShoulder", "rightElbow", "rightWrist",
    "leftHip", "leftKnee", "leftAnkle",
    "rightHip", "rightKnee", "rightAnkle",
]
JointAxis = Literal["x", "y", "z"]

# Canonical joint set (mirror of the TypeScript JOINT_NAMES). Used by the
# backward-compat migration gate to distinguish known joints from unsupported
# legacy joints retained in figure.legacyJointData.
JOINT_NAMES = (
    "pelvis", "spine", "chest", "neck", "head",
    "leftShoulder", "leftElbow", "leftWrist",
    "rightShoulder", "rightElbow", "rightWrist",
    "leftHip", "leftKnee", "leftAnkle",
    "rightHip", "rightKnee", "rightAnkle",
)


class JointRotation(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


PoseMap = dict[str, JointRotation]


FigureRole = Literal["lead", "supporting", "background", "extra", "unspecified"]


class FigureInstance(BaseModel):
    """id = permanent machine identity; name = creator-editable scene label."""

    id: str
    name: str
    archetypeId: str
    colorId: str
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "z": 0.0})
    rotationY: float = 0.0
    scale: float = 1.0
    pose: PoseMap = Field(default_factory=dict)
    # Optional association to a project character/identity (Co-Director mapping).
    characterId: str | None = None
    identityId: str | None = None
    role: FigureRole = "unspecified"
    poseId: str | None = None
    poseLabel: str | None = None
    eyelineTargetId: str | None = None
    visible: bool = True
    locked: bool = False
    kind: str | None = None
    customAssetId: str | None = None
    customAssetName: str | None = None
    # Backward-compat: joint data for joints valid in an older schemaVersion
    # but no longer in the canonical joint set is retained here rather than
    # discarded silently when a scene is migrated to the current schema.
    legacyJointData: dict[str, JointRotation] | None = None


class BlockingPrimitive(BaseModel):
    """id = permanent machine identity; name = creator-editable scene label."""

    id: str
    name: str
    kind: str = "apple-box"
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "z": 0.0})
    rotationY: float = 0.0
    scale: float = 1.0
    size: dict[str, float] = Field(default_factory=lambda: {"x": 0.6, "y": 0.5, "z": 0.4})
    color: str = "#94a3b8"
    visible: bool = True
    locked: bool = False


class CameraState(BaseModel):
    lensMm: float = 35.0
    aspect: str = "16:9"
    guides: list[str] = Field(default_factory=lambda: ["safe", "center", "thirds"])
    alpha: float = -1.5707963
    beta: float = 1.12
    radius: float = 7.5
    target: dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 1.2, "z": 0.0})


class PoseCraftProvenance(BaseModel):
    """Backward-compat provenance: records when/how a scene was migrated."""

    migratedFrom: int | None = None
    migratedAt: str | None = None
    notes: str | None = None


class PoseCraftScene(BaseModel):
    schemaVersion: int = POSECRAFT_SCHEMA_VERSION
    revision: int = 1
    updatedAt: str = ""
    name: str = "PoseCraft Blocking Study"
    notes: str = ""
    stage: dict[str, object] = Field(default_factory=dict)
    camera: CameraState = Field(default_factory=CameraState)
    figures: list[FigureInstance] = Field(default_factory=list)
    primitives: list[BlockingPrimitive] = Field(default_factory=list)
    selectedFigureId: str | None = None
    selectedJoint: str = "head"
    # True once a creator has manually edited the scene; Co-Director must not
    # silently overwrite a creator-modified scene (approval-gated mutations).
    creatorModified: bool = False
    # Backward-compat provenance.
    provenance: PoseCraftProvenance | None = None


class PoseCraftRevision(BaseModel):
    id: str
    label: str
    savedAt: str
    revision: int
    scene: PoseCraftScene


class PoseCraftLayoutPrefs(BaseModel):
    """Mandatory GO Corrective — Gate I: persisted layout preferences.

    Stored on the PoseCraftDocument so pane widths, collapse state, open
    accordions, and fullscreen survive reload (API is the SoT).
    """
    leftWidth: float = 320.0
    rightWidth: float = 340.0
    leftCollapsed: bool = False
    rightCollapsed: bool = False
    leftOpenAccordions: list[str] = Field(default_factory=lambda: ["cast", "pose-library", "furniture", "scene"])
    rightOpenAccordions: list[str] = Field(default_factory=lambda: ["figure", "transform", "pose", "camera", "export"])
    fullscreen: bool = False


class PoseCraftSnapshot(BaseModel):
    """One exact camera composition frozen for production handoff.

    Immutable frozen copy of camera/figures/primitives/semanticSummary at
    capture time. Rename is the only mutating op (and only changes `name`).
    The PNG capture is stored in the project Library (imageAssetId).
    """

    snapshotId: str
    projectId: str
    sceneId: str
    sceneRevision: int
    name: str
    imageAssetId: str
    camera: CameraState = Field(default_factory=CameraState)
    figures: list["FigureInstance"] = Field(default_factory=list)
    primitives: list["BlockingPrimitive"] = Field(default_factory=list)
    customFigures: list["FigureInstance"] = Field(default_factory=list)
    semanticSummary: str = ""
    createdAt: str = ""
    updatedAt: str = ""


class PoseCraftDocument(BaseModel):
    schemaVersion: int = POSECRAFT_SCHEMA_VERSION
    currentScene: PoseCraftScene = Field(default_factory=PoseCraftScene)
    savedVersions: list[PoseCraftRevision] = Field(default_factory=list)
    # Frozen camera-composition Snapshots for production handoff. A Snapshot
    # is NOT a scene save — it freezes one exact camera composition. Scene
    # autosave/flush stays independent and never PNG-captures.
    snapshots: list[PoseCraftSnapshot] = Field(default_factory=list)
    selectedSnapshotId: str | None = None
    layoutPrefs: PoseCraftLayoutPrefs | None = None


PoseCraftSnapshot.model_rebuild()


class PoseCraftRevisionRecord(BaseModel):
    """One saved milestone row from posecraft_revisions."""

    id: str
    projectId: str
    revision: int
    label: str
    creatorModified: bool
    savedBy: str
    createdAt: datetime | None = None


class PoseCraftExportPreview(BaseModel):
    """Honesty-labelled staging reference preview for the Image Pipeline.

    PoseCraft is a *visual staging reference*, not a final pixel source.
    """

    schemaVersion: int = POSECRAFT_SCHEMA_VERSION
    sceneName: str
    revision: int
    figureCount: int
    primitiveCount: int
    lensMm: float
    aspect: str
    honestyLabel: str = "PoseCraft visual staging reference"
    notes: str = ""
    figures: list[dict[str, object]] = Field(default_factory=list)
    objects: list[dict[str, object]] = Field(default_factory=list)
    semanticSummary: str = ""
    camera: CameraState = Field(default_factory=CameraState)


class PoseCraftCustomPose(BaseModel):
    """A creator-defined pose saved to a project (Master Program persistence).

    Project-scoped CRUD; the thumbnail is generated from the canonical joint
    data so it always matches the pose (no placeholder images).
    """

    id: str
    projectId: str
    poseId: str
    label: str
    description: str = ""
    category: str = "custom"
    archetypes: list[str] = Field(default_factory=list)
    joints: PoseMap = Field(default_factory=dict)
    thumbnail: str = ""
    creatorModified: bool = True
    savedBy: str = "creator"
    createdAt: datetime | None = None
    updatedAt: datetime | None = None
