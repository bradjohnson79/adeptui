"""Create a PoseCraft previz snapshot on the document. Frozen PNG key is imageAssetId."""

from __future__ import annotations

import uuid

from .schemas import PoseCraftDocument, PoseCraftSnapshot
from .service import _now_iso, _semantic_summary


def append_snapshot(doc: PoseCraftDocument, image_asset_id: str, *, name: str = "Previz") -> PoseCraftSnapshot:
    scene = doc.currentScene
    snap = PoseCraftSnapshot(
        snapshotId=str(uuid.uuid4()),
        projectId="",
        sceneId=scene.name or "scene",
        sceneRevision=int(scene.revision or 1),
        name=name[:200],
        imageAssetId=image_asset_id,
        camera=scene.camera,
        figures=list(scene.figures),
        objects=list(scene.objects),
        primitives=list(scene.primitives),
        customFigures=[f for f in scene.figures if getattr(f, "kind", None) == "custom"],
        shotId=scene.selectedShotId,
        cameraId=scene.selectedCameraId,
        figureIds=[f.id for f in scene.figures],
        objectIds=[o.id for o in scene.objects],
        semanticSummary=_semantic_summary(scene),
        createdAt=_now_iso(),
        updatedAt=_now_iso(),
    )
    doc.snapshots = list(doc.snapshots or []) + [snap]
    doc.selectedSnapshotId = snap.snapshotId
    return snap
