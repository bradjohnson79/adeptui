"""Import a reviewed Fire3DReconstructionPackage into PoseCraftScene.

Fire3D structures stop here. The scene only stores PoseCraft objects/environment.
"""

from __future__ import annotations

import uuid
from typing import Iterable

from .reconstruction.contracts import Fire3DReconstructionPackage
from .schemas import PoseCraftEnvironment, PoseCraftObject, PoseCraftScene
from .service import migrate_scene_to_current
from .vec3 import as_vec3


def import_reconstruction(
    scene: PoseCraftScene,
    package: Fire3DReconstructionPackage,
    *,
    selected_object_ids: Iterable[str] | None = None,
    include_failed: bool = False,
    environment_name: str | None = None,
    ers_environment_name: str | None = None,
) -> PoseCraftScene:
    allowed = set(selected_object_ids) if selected_object_ids is not None else None
    data = migrate_scene_to_current(scene.model_dump())
    next_scene = PoseCraftScene.model_validate(data)
    imported: list[PoseCraftObject] = []
    for item in package.objects:
        if allowed is not None and item.objectId not in allowed:
            continue
        if item.status != "ok" and not include_failed:
            continue
        if item.detectedHuman:
            # Detected humans stay out of the object set unless explicitly selected
            # and not treated as figures.
            if allowed is None:
                continue
        imported.append(
            PoseCraftObject(
                id=str(uuid.uuid4()),
                name=item.name or item.detectedLabel or item.objectId,
                source="reconstructed",
                meshAssetId=item.meshAssetId,
                reconstructionId=package.reconstructionId,
                sourceInstanceId=item.sourceInstanceId or item.objectId,
                detectedLabel=item.detectedLabel,
                detectedHuman=item.detectedHuman,
                position=as_vec3(item.position.model_dump()),
                rotation=as_vec3(item.rotation.model_dump()),
                scale=as_vec3(item.scale.model_dump(), default_y=1.0)
                if item.scale.y
                else {"x": item.scale.x or 1.0, "y": item.scale.y or 1.0, "z": item.scale.z or 1.0},
                nameConfirmed=False,
            )
        )
    next_scene.objects = list(next_scene.objects) + imported
    next_scene.environment = PoseCraftEnvironment(
        id="environment",
        name=environment_name or next_scene.name or "Reconstructed Stage",
        visible=True,
        locked=False,
        meshAssetId=package.backgroundAssetId,
        reconstructionId=package.reconstructionId,
        ersEnvironmentName=ers_environment_name,
        source="reconstructed" if package.backgroundAssetId or package.sceneGlbAssetId else next_scene.environment.source,
    )
    next_scene.revision = int(next_scene.revision or 1) + 1
    return next_scene
