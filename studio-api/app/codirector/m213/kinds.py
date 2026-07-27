"""M2.13 asset kind taxonomy (honest labels)."""
from __future__ import annotations

ASSET_KINDS: tuple[str, ...] = (
    "3d.model",
    "3d.environment",
    "environment.camera_spin",
    "environment.panorama",
    "environment.cubemap",
    "environment.proxy",
    "blocking.annotation",
    "video.concept",
    "video.concept_draft",
    "video.concept_final",
    "scene.camera_state",
    "scene.lighting_state",
    "theme.profile",
)

CAPABILITY_IDS: tuple[tuple[str, str, str], ...] = (
    # id, display, baseline_status key
    ("ve.import.validate", "3D import validation", "partially_wired"),
    ("ve.import.convert", "3D convert to GLB (Blender if present)", "unavailable"),
    ("ve.environment.imported", "Imported 3D environment route B", "partially_wired"),
    ("ve.environment.camera_spin", "Camera-spin environment route C", "partially_wired"),
    ("ve.environment.reconstruct", "Photo/video reconstruction route A", "unavailable"),
    ("ve.theme.translate", "Visual theme translation", "partially_wired"),
    ("ve.blocking.canvas", "Character blocking canvas", "partially_wired"),
    ("ve.camera.state", "Scene camera state", "partially_wired"),
    ("ve.lighting.state", "Scene lighting state", "partially_wired"),
    ("ve.concept.generate", "Concept video generation", "partially_wired"),
    ("ve.timeline.publish", "Publish concepts to Director Timeline", "partially_wired"),
    ("ve.scene_production.plan", "A-Z scene production plan", "partially_wired"),
    ("ve.vpc.coordinate", "Virtual Production Coordinator", "partially_wired"),
)
