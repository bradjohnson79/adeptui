"""PoseCraft reconstruction contracts.

These are Adept-normalized. Fire3D native files are parsed in normalize.py
and must not leak through the PoseCraft UI or Co-Director tools.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ReconstructionProvider = Literal["LOCAL_FIRE3D", "CLOUD_FIRE3D"]
ReconstructionSourceType = Literal["image", "video"]
ObjectStatus = Literal["ok", "failed"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "unavailable"]
ProgressStage = Literal[
    "queued",
    "analyzing",
    "detecting",
    "reconstructing",
    "building_environment",
    "assembling",
    "done",
    "failed",
]

# Official fire3d_single_image_v1 defaults are 16/16/8 (96 GB). Adept overlay
# only changes config knobs. It does not fork Fire3D.
ADEPT_FIRE3D_32GB_PROFILE: dict[str, Any] = {
    "name": "adept_local_fire3d_32gb_v1",
    "skip_render": True,
    "object_batch_size": 1,
    "ss_shape_object_batch_size": 1,
    "pbr_object_batch_size": 1,
    "appearance_decode_object_chunk_size": 1,
    "mesh_postprocess_object_batch_size": 1,
    "anyup_frame_batch_size": 1,
    "continue_on_error": True,
    "sequential_objects": True,
}


class Vec3(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class Fire3DReconstructionObject(BaseModel):
    objectId: str
    name: str
    detectedLabel: str = ""
    meshAssetId: str | None = None
    position: Vec3 = Field(default_factory=Vec3)
    rotation: Vec3 = Field(default_factory=Vec3)
    scale: Vec3 = Field(default_factory=lambda: Vec3(x=1.0, y=1.0, z=1.0))
    boundingBox: dict[str, Any] = Field(default_factory=dict)
    sourceInstanceId: str = ""
    status: ObjectStatus = "ok"
    detectedHuman: bool = False
    categoryHint: str = "object"
    failureReason: str = ""


class DetectedHuman(BaseModel):
    objectId: str
    sourceInstanceId: str = ""
    position: Vec3 = Field(default_factory=Vec3)
    rotation: Vec3 = Field(default_factory=Vec3)
    suggestedReplace: bool = True


class Fire3DReconstructionPackage(BaseModel):
    reconstructionId: str
    sourceAssetId: str
    sourceType: ReconstructionSourceType
    provider: ReconstructionProvider = "LOCAL_FIRE3D"
    sceneGlbAssetId: str | None = None
    backgroundAssetId: str | None = None
    objects: list[Fire3DReconstructionObject] = Field(default_factory=list)
    detectedHumans: list[DetectedHuman] = Field(default_factory=list)
    cameraData: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    partialSuccess: bool = False
    protocol: str = "fire3d_single_image_v1"


class ReconstructionProgress(BaseModel):
    stage: ProgressStage
    objectsDone: int = 0
    objectsTotal: int = 0
    message: str = ""
    realEngine: bool = True


class ReconstructionJob(BaseModel):
    jobId: str
    projectId: str
    provider: ReconstructionProvider
    status: JobStatus
    progress: ReconstructionProgress
    package: Fire3DReconstructionPackage | None = None
    error: str = ""
    profile: dict[str, Any] = Field(default_factory=lambda: dict(ADEPT_FIRE3D_32GB_PROFILE))
