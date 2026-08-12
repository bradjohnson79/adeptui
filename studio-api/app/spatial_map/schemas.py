from __future__ import annotations

import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


CoordinateSystem = Literal["adept-world-v1"]
ProviderHonestyMode = Literal["approximate_translation", "native_coordinates"]
SpatialDirection = Literal[
    "front",
    "front_right",
    "right",
    "rear_right",
    "rear",
    "rear_left",
    "left",
    "front_left",
    "ceiling",
    "floor",
    "hero",
]
SpatialCaptureMode = Literal["environment_only", "include_characters"]
SpatialBundleTarget = Literal["image", "video"]
SpatialPathSubjectType = Literal["character", "prop", "camera"]
SpatialMapTypedErrorCode = Literal[
    "PROJECT_NOT_FOUND",
    "SPATIAL_MAP_NOT_FOUND",
    "SCENE_NOT_FOUND",
    "PLACEMENT_NOT_FOUND",
    "CHARACTER_LIMIT_REACHED",
    "PROP_LIMIT_REACHED",
    "CAMERA_LIMIT_REACHED",
    "COORDINATE_SYSTEM_UNSUPPORTED",
    "COLLAGE_MINIMUM_DIRECTIONS_REQUIRED",
    "COLLAGE_DIRECTION_INVALID",
    "PATH_SUBJECT_NOT_FOUND",
    "ASSIGNMENT_INVALID",
    "REFERENCE_BUNDLE_TARGET_INVALID",
]

REQUIRED_360_DIRECTIONS: tuple[str, ...] = (
    "front",
    "front_right",
    "right",
    "rear_right",
    "rear",
    "rear_left",
    "left",
    "front_left",
)


class SpatialBounds(BaseModel):
    coordinateSystem: CoordinateSystem = "adept-world-v1"
    minX: float = -5.0
    maxX: float = 5.0
    minY: float = 0.0
    maxY: float = 3.0
    minZ: float = -5.0
    maxZ: float = 5.0


class SpatialAnchor(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str = "Anchor"
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    notes: str = ""


class SpatialPlacement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str = ""
    assetId: Optional[str] = None
    anchorId: Optional[str] = None
    notes: str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yawDegrees: float = 0.0
    pitchDegrees: float = 0.0
    rollDegrees: float = 0.0
    scale: float = 1.0
    # Grid placement extension (Spatial Map V1).
    # 10x10 grid; gridRow/gridColumn are 0-9.
    gridRow: int = -1
    gridColumn: int = -1
    slotIndex: int = -1  # 0-3 for V1's 4 slots per type
    colorKey: str = ""  # red|blue|orange|green (characters), purple|brown|aqua|gray (props)
    miniPrompt: str = ""  # e.g. "@Korri is standing behind the barista bar."
    tag: str = ""  # "@Korri" or "#coffeecup" — friendly reference, not DB identity


class SpatialCharacterPlacement(SpatialPlacement):
    characterId: str
    pose: str = ""
    expression: str = ""
    eyeLine: str = ""
    providerHonesty: ProviderHonestyMode = "approximate_translation"


class SpatialPropPlacement(SpatialPlacement):
    propId: Optional[str] = None
    category: str = ""
    state: str = ""
    providerHonesty: ProviderHonestyMode = "approximate_translation"


class SpatialCamera(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str = "Camera"
    x: float = 0.0
    y: float = 1.6
    z: float = 0.0
    yawDegrees: float = 0.0
    pitchDegrees: float = 0.0
    rollDegrees: float = 0.0
    lensMm: float = 35.0
    heightMeters: float = 1.6
    shotType: str = "medium"
    targetCharacterIds: list[str] = Field(default_factory=list)
    hero: bool = False
    lockedFor360: bool = False


class SpatialMovementWaypoint(BaseModel):
    x: float
    y: float
    z: float
    holdSeconds: float = 0.0


class SpatialMovementPath(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str = "Movement Path"
    subjectType: SpatialPathSubjectType
    subjectId: str
    waypoints: list[SpatialMovementWaypoint] = Field(default_factory=list)
    notes: str = ""
    loop: bool = False


class Spatial360View(BaseModel):
    direction: SpatialDirection
    yawDegrees: float
    assetId: Optional[str] = None
    prompt: str = ""
    status: Literal["planned", "captured", "approved"] = "planned"
    continuityScore: float = 1.0
    adjacencyWarnings: list[str] = Field(default_factory=list)


class Spatial360Collage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    masterEnvironmentPrompt: str = ""
    captureMode: SpatialCaptureMode = "environment_only"
    cameraHeightMeters: float = 1.6
    lensMm: float = 24.0
    heroDirection: Optional[SpatialDirection] = None
    views: list[Spatial360View] = Field(default_factory=list)
    continuityWarnings: list[str] = Field(default_factory=list)
    minimumDirectionsMet: bool = False

    @model_validator(mode="after")
    def _unique_directions(self) -> "Spatial360Collage":
        seen: set[str] = set()
        for view in self.views:
            if view.direction in seen:
                raise ValueError(f"duplicate collage direction: {view.direction}")
            seen.add(view.direction)
        return self


class SpatialReferenceAsset(BaseModel):
    assetId: str
    kind: str = ""
    filename: str = ""
    path: str = ""


class SpatialReferenceBundle(BaseModel):
    documentId: str
    documentVersion: Optional[str] = None
    projectId: str
    sceneId: Optional[str] = None
    locationId: Optional[str] = None
    target: SpatialBundleTarget = "image"
    coordinateSystem: CoordinateSystem = "adept-world-v1"
    providerHonesty: ProviderHonestyMode = "approximate_translation"
    environmentPrompt: str = ""
    backgroundAssetId: Optional[str] = None
    referenceAssetIds: list[str] = Field(default_factory=list)
    assetReferences: list[SpatialReferenceAsset] = Field(default_factory=list)
    characters: list[SpatialCharacterPlacement] = Field(default_factory=list)
    props: list[SpatialPropPlacement] = Field(default_factory=list)
    primaryCamera: Optional[SpatialCamera] = None
    movementPaths: list[SpatialMovementPath] = Field(default_factory=list)
    availableCollageDirections: list[SpatialDirection] = Field(default_factory=list)
    creatorPositionLabels: dict[str, str] = Field(default_factory=dict)
    directionalPrompts: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SpatialCaptureShot(BaseModel):
    direction: SpatialDirection
    yawDegrees: float
    prompt: str = ""


class SpatialCapturePlan(BaseModel):
    documentId: str
    captureMode: SpatialCaptureMode = "environment_only"
    masterEnvironmentPrompt: str = ""
    cameraHeightMeters: float = 1.6
    lensMm: float = 24.0
    coordinateSystem: CoordinateSystem = "adept-world-v1"
    providerHonesty: ProviderHonestyMode = "approximate_translation"
    shots: list[SpatialCaptureShot] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)


class SpatialMapDocument(BaseModel):
    schemaVersion: int = 1
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1"
    projectId: str
    sceneId: Optional[str] = None
    locationId: Optional[str] = None
    title: str = "Spatial Map"
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    bounds: SpatialBounds = Field(default_factory=SpatialBounds)
    backgroundAssetId: Optional[str] = None
    masterEnvironmentPrompt: str = ""
    providerHonesty: ProviderHonestyMode = "approximate_translation"
    anchors: list[SpatialAnchor] = Field(default_factory=list)
    characters: list[SpatialCharacterPlacement] = Field(default_factory=list)
    props: list[SpatialPropPlacement] = Field(default_factory=list)
    cameras: list[SpatialCamera] = Field(default_factory=list)
    paths: list[SpatialMovementPath] = Field(default_factory=list)
    collage: Optional[Spatial360Collage] = None
    warnings: list[str] = Field(default_factory=list)
    variantOfId: Optional[str] = None
    variantIds: list[str] = Field(default_factory=list)
    assignedSceneIds: list[str] = Field(default_factory=list)
    createdAt: str = ""
    updatedAt: str = ""


class SpatialMapCreateBody(BaseModel):
    title: str = "Spatial Map"
    sceneId: Optional[str] = None
    locationId: Optional[str] = None
    notes: str = ""
    bounds: SpatialBounds = Field(default_factory=SpatialBounds)
    backgroundAssetId: Optional[str] = None
    masterEnvironmentPrompt: str = ""
    providerHonesty: ProviderHonestyMode = "approximate_translation"


class SpatialMapUpdateBody(BaseModel):
    title: Optional[str] = None
    sceneId: Optional[str] = None
    locationId: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    bounds: Optional[SpatialBounds] = None
    backgroundAssetId: Optional[str] = None
    masterEnvironmentPrompt: Optional[str] = None
    providerHonesty: Optional[ProviderHonestyMode] = None


class SpatialCharacterPlacementBody(BaseModel):
    characterId: str
    label: str
    assetId: Optional[str] = None
    anchorId: Optional[str] = None
    notes: str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yawDegrees: float = 0.0
    pitchDegrees: float = 0.0
    rollDegrees: float = 0.0
    scale: float = 1.0
    pose: str = ""
    expression: str = ""
    eyeLine: str = ""


class SpatialPropPlacementBody(BaseModel):
    label: str
    propId: Optional[str] = None
    assetId: Optional[str] = None
    anchorId: Optional[str] = None
    notes: str = ""
    category: str = ""
    state: str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yawDegrees: float = 0.0
    pitchDegrees: float = 0.0
    rollDegrees: float = 0.0
    scale: float = 1.0


class SpatialCameraCreateBody(BaseModel):
    label: str = "Camera"
    x: float = 0.0
    y: float = 1.6
    z: float = 0.0
    yawDegrees: float = 0.0
    pitchDegrees: float = 0.0
    rollDegrees: float = 0.0
    lensMm: float = 35.0
    heightMeters: float = 1.6
    shotType: str = "medium"
    targetCharacterIds: list[str] = Field(default_factory=list)
    hero: bool = False
    lockedFor360: bool = False


class SpatialCharacterPlacementUpdateBody(BaseModel):
    label: Optional[str] = None
    assetId: Optional[str] = None
    anchorId: Optional[str] = None
    notes: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    yawDegrees: Optional[float] = None
    pitchDegrees: Optional[float] = None
    rollDegrees: Optional[float] = None
    scale: Optional[float] = None
    pose: Optional[str] = None
    expression: Optional[str] = None
    eyeLine: Optional[str] = None


class SpatialPropPlacementUpdateBody(BaseModel):
    label: Optional[str] = None
    propId: Optional[str] = None
    assetId: Optional[str] = None
    anchorId: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    state: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    yawDegrees: Optional[float] = None
    pitchDegrees: Optional[float] = None
    rollDegrees: Optional[float] = None
    scale: Optional[float] = None


class SpatialCameraUpdateBody(BaseModel):
    label: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    yawDegrees: Optional[float] = None
    pitchDegrees: Optional[float] = None
    rollDegrees: Optional[float] = None
    lensMm: Optional[float] = None
    heightMeters: Optional[float] = None
    shotType: Optional[str] = None
    targetCharacterIds: Optional[list[str]] = None
    hero: Optional[bool] = None
    lockedFor360: Optional[bool] = None


class SpatialMovementPathCreateBody(BaseModel):
    label: str = "Movement Path"
    subjectType: SpatialPathSubjectType
    subjectId: str
    waypoints: list[SpatialMovementWaypoint] = Field(default_factory=list)
    notes: str = ""
    loop: bool = False


class SpatialAssignSceneBody(BaseModel):
    sceneId: str
    locationId: Optional[str] = None


class SpatialVariantCreateBody(BaseModel):
    name: str = "Variant"
    sceneId: Optional[str] = None
    locationId: Optional[str] = None
    notesSuffix: str = ""


class SpatialCollageCreateBody(BaseModel):
    masterEnvironmentPrompt: str = ""
    captureMode: SpatialCaptureMode = "environment_only"
    cameraHeightMeters: float = 1.6
    lensMm: float = 24.0
    heroDirection: Optional[SpatialDirection] = None


class Spatial360ViewUpsertBody(BaseModel):
    assetId: Optional[str] = None
    prompt: str = ""
    status: Literal["planned", "captured", "approved"] = "planned"


class SpatialReferenceBundleRequest(BaseModel):
    target: SpatialBundleTarget = "image"
    cameraId: Optional[str] = None


class SpatialCapturePlanBody(BaseModel):
    includeCharacters: bool = False
    masterEnvironmentPrompt: Optional[str] = None
    cameraHeightMeters: float = 1.6
    lensMm: float = 24.0


class SpatialConsistencyCheck(BaseModel):
    warnings: list[str] = Field(default_factory=list)


class SpatialMapErrorDetail(BaseModel):
    code: SpatialMapTypedErrorCode
    message: str
    explanation: str = ""
    recovery: str = ""
