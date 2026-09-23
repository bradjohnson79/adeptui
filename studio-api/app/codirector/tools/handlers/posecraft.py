"""Co-Director posecraft.* tool handlers.

Reads hydrate the PoseCraft scene from the project-scoped persistence layer.
Mutations are approval-gated by the Co-Director tool execution layer before
reaching these handlers; `apply_tool_mutation` additionally refuses to
silently overwrite a creatorModified scene without an explicit `force` flag
(set only after creator consent). No silent overwrite.
"""

from __future__ import annotations

import json
from typing import Any

from ....posecraft import pose_catalog
from ....posecraft import service as posecraft_service
from ....posecraft.schemas import (
    FigureInstance,
    JointRotation,
    PoseCraftDocument,
    PoseCraftScene,
)
from ..definitions import ToolContext, ToolPreview


def _semantic_lines(scene: PoseCraftScene) -> list[str]:
    lines: list[str] = []
    for f in scene.figures:
        role = getattr(f, "role", None) or "unspecified"
        role_s = f" ({role})" if role != "unspecified" else ""
        pose = getattr(f, "poseLabel", None) or getattr(f, "poseId", None) or "Neutral"
        lines.append(f"{f.name}{role_s} — {f.archetypeId} — {pose}")
    for p in scene.primitives:
        lines.append(f"{p.name} — {p.kind}")
    return lines


def _doc_summary(doc: PoseCraftDocument) -> dict[str, Any]:
    scene = doc.currentScene
    return {
        "sceneName": scene.name,
        "revision": scene.revision,
        "figureCount": len(scene.figures),
        "primitiveCount": len(scene.primitives),
        "creatorModified": scene.creatorModified,
        "lensMm": scene.camera.lensMm,
        "aspect": scene.camera.aspect,
        "semanticSummary": "\n".join(_semantic_lines(scene)),
        "figures": [
            {
                "id": f.id,
                "label": f.name,
                "name": f.name,
                "role": getattr(f, "role", None) or "unspecified",
                "type": f.archetypeId,
                "archetypeId": f.archetypeId,
                "colorId": f.colorId,
                "characterId": f.characterId,
                "identityId": f.identityId,
                "poseId": getattr(f, "poseId", None),
                "poseLabel": getattr(f, "poseLabel", None),
                "position": f.position,
            }
            for f in scene.figures
        ],
        "objects": [
            {
                "id": o.id,
                "label": o.name,
                "name": o.name,
                "type": o.source,
                "source": o.source,
                "position": o.position,
            }
            for o in (getattr(scene, "objects", None) or scene.primitives)
        ],
        "shots": [{"shotId": s.shotId, "name": s.name} for s in getattr(scene, "shots", []) or []],
        "environment": getattr(scene.environment, "name", None) if getattr(scene, "environment", None) else None,
    }


async def get_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc = posecraft_service.load_scene(ctx.project_id, ctx.db)
    return {"status": _doc_summary(doc)}


async def get_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc = posecraft_service.load_scene(ctx.project_id, ctx.db)
    summary = _doc_summary(doc)
    return {
        "scene": {
            "schemaVersion": doc.schemaVersion,
            "currentScene": json.loads(doc.currentScene.model_dump_json()),
            "selectedSnapshotId": doc.selectedSnapshotId,
            "loadState": doc.loadState,
            "igHandoffSnapshotId": doc.igHandoffSnapshotId,
        },
        "semantic": summary,
    }


async def list_scenes(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """List the current project PoseCraft scene with semantic labels."""
    doc = posecraft_service.load_scene(ctx.project_id, ctx.db)
    summary = _doc_summary(doc)
    return {
        "scenes": [
            {
                "sceneName": summary["sceneName"],
                "revision": summary["revision"],
                "figureCount": summary["figureCount"],
                "primitiveCount": summary["primitiveCount"],
                "labels": [f["label"] for f in summary["figures"]]
                + [o["label"] for o in summary["objects"]],
            }
        ]
    }


async def inspect_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Return Co-Director-facing semantic labels for the staged scene.

    Prefer creator labels (Maya, Coffee Table) over color/number descriptions.
    When ``snapshotId`` is supplied, inspect the frozen Snapshot composition
    (PoseCraft Snapshot — Visual Staging Reference) instead of the live scene.
    """
    snapshot_id = args.get("snapshotId")
    if snapshot_id:
        snap = posecraft_service.get_snapshot(ctx.project_id, str(snapshot_id), ctx.db)
        summary = {
            "sceneName": snap.name,
            "revision": snap.sceneRevision,
            "figureCount": len(snap.figures),
            "primitiveCount": len(snap.primitives),
            "creatorModified": False,
            "lensMm": snap.camera.lensMm,
            "aspect": snap.camera.aspect,
            "semanticSummary": snap.semanticSummary,
            "snapshotId": snap.snapshotId,
            "imageAssetId": snap.imageAssetId,
            "honestyLabel": "PoseCraft Snapshot — Visual Staging Reference",
            "figures": [
                {
                    "id": f.id,
                    "label": f.name,
                    "name": f.name,
                    "role": getattr(f, "role", None) or "unspecified",
                    "type": f.archetypeId,
                    "archetypeId": f.archetypeId,
                    "colorId": f.colorId,
                    "characterId": f.characterId,
                    "identityId": f.identityId,
                    "poseId": getattr(f, "poseId", None),
                    "poseLabel": getattr(f, "poseLabel", None),
                    "position": f.position,
                }
                for f in snap.figures
            ],
            "objects": [
                {
                    "id": p.id,
                    "label": p.name,
                    "name": p.name,
                    "type": p.kind,
                    "furnitureKind": p.kind,
                    "position": p.position,
                }
                for p in snap.primitives
            ],
        }
        return {
            "inspection": summary,
            "narrativeHint": (
                "Describe the Snapshot using the provided labels and roles. "
                "Treat it as a PoseCraft Snapshot — Visual Staging Reference "
                "(a frozen camera composition), not a final frame. Do not refer "
                "to figures only by staging color or anonymous object numbers."
            ),
            "summaryText": snap.semanticSummary,
        }
    doc = posecraft_service.load_scene(ctx.project_id, ctx.db)
    summary = _doc_summary(doc)
    return {
        "inspection": summary,
        "narrativeHint": (
            "Describe the scene using the provided labels and roles. "
            "Do not refer to figures only by staging color or anonymous object numbers."
        ),
        "summaryText": summary["semanticSummary"],
    }


async def export_reference(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    snapshot_id = args.get("snapshotId")
    preview = posecraft_service.build_export_preview(ctx.project_id, ctx.db, snapshot_id=snapshot_id)
    return {"exportPreview": preview.model_dump()}


def _packet_tool_view(packet: Any) -> dict[str, Any]:
    """Compact Co-Director view — no WorldStatePacket dump, no embeddings."""
    character = getattr(packet, "character", None)
    interaction = getattr(packet, "interaction", None)
    world = getattr(packet, "world", None)
    return {
        "packetId": getattr(packet, "packetId", ""),
        "availability": getattr(packet, "availability", "unavailable"),
        "reason": getattr(packet, "reason", ""),
        "stateKind": getattr(packet, "stateKind", "intended"),
        "projectId": getattr(packet, "projectId", ""),
        "snapshotId": getattr(packet, "snapshotId", ""),
        "summary": getattr(packet, "creatorFacingSummary", ""),
        "details": getattr(packet, "creatorFacingDetails", ""),
        "character": {
            "figureName": getattr(character, "figureName", ""),
            "figureId": getattr(character, "figureId", ""),
            "stance": getattr(character, "stance", "unknown"),
            "balance": getattr(character, "balance", "uncertain"),
            "primarySupport": getattr(character, "primarySupport", "uncertain"),
            "facingDirection": getattr(character, "facingDirection", 0.0),
        },
        "interaction": {
            "groundContact": bool(getattr(interaction, "groundContact", False)),
            "footContact": list(getattr(interaction, "footContact", []) or []),
            "handContact": list(getattr(interaction, "handContact", []) or []),
            "bodyToObject": list(getattr(interaction, "bodyToObject", []) or []),
        },
        "warnings": list(getattr(packet, "warnings", []) or []),
        "honorsCreatorIntent": bool(packet.honors_creator_intent()) if hasattr(packet, "honors_creator_intent") else True,
        "worldAvailability": getattr(world, "availability", "unavailable") if world is not None else "unavailable",
    }


async def get_pose_intelligence(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....codirector.pose_intelligence.service import analyze_project_scene

    packet = analyze_project_scene(
        ctx.db,
        ctx.project_id,
        snapshot_id=str(args.get("snapshotId") or ""),
        figure_id=str(args.get("figureId") or ""),
    )
    view = _packet_tool_view(packet)
    return {
        "_summary": view["summary"] or "Pose Intelligence is ready.",
        "packet": view,
        "summary": view["summary"],
        "warnings": view["warnings"],
        "honorsCreatorIntent": view["honorsCreatorIntent"],
    }


async def compare_poses(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....codirector.pose_intelligence.service import compare_project_poses

    raw = compare_project_poses(
        ctx.db,
        ctx.project_id,
        from_snapshot_id=str(args.get("fromSnapshotId") or ""),
        to_snapshot_id=str(args.get("toSnapshotId") or ""),
    )
    from ....codirector.pose_intelligence.contracts import PoseWorldStatePacket

    first = PoseWorldStatePacket.model_validate(raw.get("from") or {})
    second = PoseWorldStatePacket.model_validate(raw.get("to") or {})
    transition = raw.get("transition") or {}
    action = str(transition.get("actionProgression") or "")
    warnings = list(transition.get("plausibilityWarnings") or [])
    return {
        "_summary": action or "Pose comparison ready.",
        "from": _packet_tool_view(first),
        "to": _packet_tool_view(second),
        "transition": {
            "actionProgression": action,
            "changes": transition.get("changes") or [],
            "warnings": warnings,
            "nextStateSuggestion": transition.get("nextStateSuggestion") or "",
        },
        "honorsCreatorIntent": True,
    }


# ---- Mutation handlers (approval-gated by the execution layer) ----


def _load_scene_for_mutation(ctx: ToolContext) -> PoseCraftScene:
    doc = posecraft_service.load_scene(ctx.project_id, ctx.db)
    return doc.currentScene


def _persist_scene(ctx: ToolContext, scene: PoseCraftScene, *, actor: str = "codirector") -> PoseCraftDocument:
    doc = posecraft_service.load_scene(ctx.project_id, ctx.db)
    doc.currentScene = scene
    return posecraft_service.save_scene(ctx.project_id, doc, ctx.db, saved_by=actor)


def preview_create_scene(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene = _load_scene_for_mutation(ctx)
    summary = f"Create PoseCraft scene '{args.get('name') or scene.name}'."
    return ToolPreview(summary=summary, lines=["Affects: project"])


def apply_create_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _load_scene_for_mutation(ctx)
    if args.get("name"):
        scene.name = str(args["name"])[:200]
    if args.get("notes"):
        scene.notes = str(args["notes"])[:2000]
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc)}


def preview_add_figure(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Add {args.get('archetypeId', 'figure')} to PoseCraft scene.",
        lines=["Affects: project"],
    )


def apply_add_figure(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _load_scene_for_mutation(ctx)
    import uuid
    figure = FigureInstance(
        id=str(uuid.uuid4()),
        name=str(args.get("name") or args.get("archetypeId", "Figure"))[:120],
        archetypeId=str(args.get("archetypeId", "adult-male"))[:40],
        colorId=str(args.get("colorId", "seaglass"))[:40],
        position={"x": 0.0, "z": 0.0},
        rotationY=0.0,
        scale=1.0,
        pose={},
        characterId=args.get("characterId"),
        identityId=args.get("identityId"),
    )
    scene.figures.append(figure)
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc)}


def preview_rename_object(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    label = str(args.get("label") or args.get("name") or "")[:120]
    target = str(args.get("objectId") or args.get("figureId") or args.get("primitiveId") or "?")
    return ToolPreview(
        summary=f"Rename PoseCraft object {target} to '{label}'.",
        lines=["Affects: project"],
    )


def apply_rename_object(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Approval-gated rename: updates scene label only; permanent id unchanged."""
    scene = _load_scene_for_mutation(ctx)
    label = str(args.get("label") or args.get("name") or "").strip()[:120]
    if not label:
        return {"error": "label required", "scene": _doc_summary(PoseCraftDocument(currentScene=scene))}
    oid = str(args.get("objectId") or args.get("figureId") or args.get("primitiveId") or "")
    changed = False
    for f in scene.figures:
        if f.id == oid:
            f.name = label
            changed = True
            break
    if not changed:
        for p in scene.primitives:
            if p.id == oid:
                p.name = label
                changed = True
                break
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc), "renamed": changed, "objectId": oid, "label": label}


def preview_set_figure_role(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Set figure {args.get('figureId')} role to {args.get('role', 'unspecified')}.",
        lines=["Affects: project"],
    )


def apply_set_figure_role(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _load_scene_for_mutation(ctx)
    fid = str(args.get("figureId", ""))
    role = str(args.get("role", "unspecified")).lower()[:40]
    allowed = {"lead", "supporting", "background", "extra", "unspecified"}
    if role not in allowed:
        role = "unspecified"
    for f in scene.figures:
        if f.id == fid:
            f.role = role  # type: ignore[assignment]
            break
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc)}


def preview_map_character(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Map figure {args.get('figureId')} to a project character.",
        lines=["Affects: project"],
    )


def apply_map_character(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _load_scene_for_mutation(ctx)
    fid = str(args.get("figureId", ""))
    for f in scene.figures:
        if f.id == fid:
            f.characterId = args.get("characterId")
            f.identityId = args.get("identityId")
            break
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc)}


def preview_set_figure_color(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Set figure {args.get('figureId')} staging color to {args.get('colorId')}.",
        lines=["Affects: project"],
    )


def apply_set_figure_color(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _load_scene_for_mutation(ctx)
    fid = str(args.get("figureId", ""))
    color = str(args.get("colorId", "seaglass"))[:40]
    for f in scene.figures:
        if f.id == fid:
            f.colorId = color
            break
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc)}


def _resolve_pose_figure(scene: PoseCraftScene, args: dict[str, Any]) -> FigureInstance | None:
    """Resolve the target figure by id first, then by creator-facing name."""
    fid = str(args.get("figureId") or "")
    for f in scene.figures:
        if f.id == fid:
            return f
    name = str(args.get("figureName") or args.get("figureId") or "").strip().lower()
    if name:
        for f in scene.figures:
            if f.name.strip().lower() == name:
                return f
    return None


def _resolve_pose_preset(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve pose joints: explicit joint map > canonical catalog > project custom poses."""
    explicit = args.get("joints")
    if isinstance(explicit, dict) and explicit:
        return {
            "id": str(args.get("posePresetId") or "custom-joints"),
            "label": str(args.get("poseLabel") or "Custom pose"),
            "joints": explicit,
            "archetypes": None,
        }
    pose_id = str(args.get("posePresetId") or "")
    if not pose_id:
        return None
    catalog_pose = pose_catalog.get_catalog_pose(pose_id)
    if catalog_pose:
        return catalog_pose
    for custom in posecraft_service.list_custom_poses(ctx.project_id, ctx.db):
        if custom.get("poseId") == pose_id or custom.get("id") == pose_id:
            return {
                "id": str(custom.get("poseId") or custom.get("id")),
                "label": str(custom.get("label") or "Custom pose"),
                "joints": custom.get("joints") or {},
                "archetypes": custom.get("archetypes") or None,
            }
    return None


def preview_apply_pose(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene = _load_scene_for_mutation(ctx)
    figure = _resolve_pose_figure(scene, args)
    preset = _resolve_pose_preset(ctx, args)
    figure_label = figure.name if figure else str(args.get("figureId") or "?")
    pose_label = preset["label"] if preset else str(args.get("posePresetId") or "?")
    lines = ["Affects: project"]
    if preset:
        changed = [j for j, r in (preset.get("joints") or {}).items() if any(abs(float(r.get(a, 0.0))) > 0.001 for a in ("x", "y", "z"))]
        if changed:
            lines.append("Joints: " + ", ".join(sorted(changed)))
    if not figure:
        lines.append("WARNING: figure not found in the scene")
    if not preset:
        lines.append("WARNING: pose preset not found in the catalog")
    return ToolPreview(summary=f"Pose {figure_label} as '{pose_label}'.", lines=lines)


def apply_apply_pose(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Write real joint rotations into the persisted scene.

    Resolves the preset server-side (canonical catalog mirror or project
    custom poses) or accepts an explicit ``joints`` map, clamps every
    rotation to the shared joint limits, and persists the full 17-joint
    pose so the viewport hydrates the applied pose. Unknown figure or pose
    is a hard error — never a fake success.
    """
    scene = _load_scene_for_mutation(ctx)
    figure = _resolve_pose_figure(scene, args)
    if figure is None:
        return {
            "error": f"Figure {args.get('figureId') or args.get('figureName') or '?'} not found in the PoseCraft scene.",
            "applied": False,
        }
    preset = _resolve_pose_preset(ctx, args)
    if preset is None:
        return {
            "error": f"Pose preset {args.get('posePresetId') or '?'} not found in the pose catalog or project poses.",
            "applied": False,
        }
    if not pose_catalog.is_pose_compatible(preset, figure.archetypeId):
        return {
            "error": f"Pose '{preset['label']}' is not compatible with archetype {figure.archetypeId}.",
            "applied": False,
        }
    clamped = pose_catalog.clamped_pose_map(preset.get("joints") or {})
    figure.pose = {joint: JointRotation(**rot) for joint, rot in clamped.items()}
    figure.poseId = str(preset["id"])
    figure.poseLabel = str(preset["label"])
    doc = _persist_scene(ctx, scene)
    changed = [j for j, r in clamped.items() if any(abs(r[a]) > 0.001 for a in ("x", "y", "z"))]
    return {
        "scene": _doc_summary(doc),
        "applied": True,
        "figureId": figure.id,
        "figureName": figure.name,
        "posePresetId": figure.poseId,
        "poseLabel": figure.poseLabel,
        "changedJoints": sorted(changed),
    }


def preview_update_figure_transform(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Move figure {args.get('figureId')} on the PoseCraft stage.",
        lines=["Affects: project"],
    )


def apply_update_figure_transform(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _load_scene_for_mutation(ctx)
    fid = str(args.get("figureId", ""))
    for f in scene.figures:
        if f.id == fid:
            if "x" in args:
                f.position["x"] = float(args["x"])
            if "z" in args:
                f.position["z"] = float(args["z"])
            if "rotationY" in args:
                f.rotationY = float(args["rotationY"])
            if "scale" in args:
                f.scale = float(args["scale"])
            break
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc)}


def preview_set_eyeline(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Set eyeline for figure {args.get('figureId')}.",
        lines=["Affects: project"],
    )


def apply_set_eyeline(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # Eyeline is a staging intent recorded on the scene notes; the viewport
    # renders the gaze. Persist the intent.
    scene = _load_scene_for_mutation(ctx)
    intent = f"eyeline:{args.get('figureId')}→{args.get('targetFigureId') or (args.get('targetX'), args.get('targetZ'))}"
    scene.notes = (scene.notes + " | " + intent)[:2000] if scene.notes else intent
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc)}


def preview_set_camera(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Set PoseCraft camera (lens {args.get('lensMm', '?')}mm).",
        lines=["Affects: project"],
    )


def apply_set_camera(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _load_scene_for_mutation(ctx)
    cam = scene.camera
    if "lensMm" in args:
        cam.lensMm = float(args["lensMm"])
    if "aspect" in args:
        cam.aspect = str(args["aspect"])[:12]
    if "alpha" in args:
        cam.alpha = float(args["alpha"])
    if "beta" in args:
        cam.beta = float(args["beta"])
    if "radius" in args:
        cam.radius = float(args["radius"])
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc)}


def preview_save_scene(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Save PoseCraft scene revision '{args.get('label', '')}'.",
        lines=["Affects: project"],
    )


def apply_save_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _load_scene_for_mutation(ctx)
    rev = posecraft_service.save_revision(
        ctx.project_id, str(args.get("label", "")), scene, ctx.db, saved_by="codirector"
    )
    return {"revision": rev.model_dump()}


def preview_send_to_image_pipeline(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Send PoseCraft staging reference to Image Pipeline.",
        lines=["Affects: project"],
    )


def apply_send_to_image_pipeline(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    snapshot_id = args.get("snapshotId")
    preview = posecraft_service.build_export_preview(ctx.project_id, ctx.db, snapshot_id=snapshot_id)
    doc = posecraft_service.load_scene(ctx.project_id, ctx.db)
    doc.igHandoffSnapshotId = str(snapshot_id or doc.selectedSnapshotId or "") or None
    posecraft_service.save_scene(ctx.project_id, doc, ctx.db, saved_by="codirector")
    return {
        "exportPreview": preview.model_dump(),
        "purpose": args.get("purpose", "shot"),
        "prompt": args.get("prompt", ""),
        "snapshotId": snapshot_id or doc.igHandoffSnapshotId,
        "imageAssetId": args.get("imageAssetId"),
        "honestyLabel": preview.honestyLabel,
        "next": "image_pipeline.prepare_plan",
    }


def preview_send_to_storyboard(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Send PoseCraft staging reference to Storyboard scene {args.get('sceneId', '?')}.",
        lines=["Affects: project"],
    )


def apply_send_to_storyboard(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Send a PoseCraft Snapshot to Storyboard and place it on the board.

    PoseCraft is a *visual staging reference*, not a final frame. The handoff
    package carries the export preview (figures/camera/aspect), the target
    scene id, a creator-facing label, notes, and an honesty label. When a
    frozen Snapshot is supplied, its PNG (``imageAssetId``) is placed onto the
    next free Storyboard panel through the same backend ingest path the image
    surfaces use — a real placement, not a dead next-step pointer.
    creatorModified protection is enforced upstream by
    apply_tool_mutation (refuses silent overwrite of a creator-modified scene).
    """
    snapshot_id = str(args.get("snapshotId") or "")
    preview = posecraft_service.build_export_preview(ctx.project_id, ctx.db, snapshot_id=snapshot_id or None)
    scene_id = str(args.get("sceneId", ""))[:64]
    label = str(args.get("label", preview.sceneName))[:200]
    notes = str(args.get("notes", ""))[:4000]
    image_asset_id = str(args.get("imageAssetId") or "")

    # Resolve the frozen Snapshot's PNG when the caller passed only snapshotId.
    if not image_asset_id and snapshot_id:
        try:
            snap = posecraft_service.get_snapshot(ctx.project_id, snapshot_id, ctx.db)
        except Exception:
            snap = None
        if snap is not None:
            image_asset_id = str(getattr(snap, "imageAssetId", "") or "")

    result: dict[str, Any] = {
        "exportPreview": preview.model_dump(),
        "sceneId": scene_id,
        "label": label,
        "notes": notes,
        "honestyLabel": preview.honestyLabel,
        "snapshotId": snapshot_id or None,
        "imageAssetId": image_asset_id or None,
    }

    if image_asset_id:
        from ....storyboard_studio.add_from_image import add_image_to_next_panel

        try:
            placed = add_image_to_next_panel(
                ctx.project_id,
                asset_id=image_asset_id,
                prompt=notes or preview.sceneName or "PoseCraft staging reference",
                label=label,
                lens=str(getattr(preview, "lensMm", "") or ""),
                scene_id=scene_id or None,
            )
        except Exception as exc:  # placement failed — report honestly, never fake success
            result["placed"] = False
            result["placementError"] = str(exc)[:400]
        else:
            result["placed"] = True
            result["panelId"] = placed.get("panelId")
            result["documentId"] = placed.get("documentId")
            result["slot"] = placed.get("slot")
    else:
        result["placed"] = False
        result["placementError"] = "No Snapshot image available to place on the Storyboard."

    return result


def preview_add_object(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(summary=f"Add object '{args.get('name') or args.get('kind') or 'object'}' to the stage.", lines=["Affects: project"])


def apply_add_object(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....posecraft.schemas import PoseCraftObject

    scene = _load_scene_for_mutation(ctx)
    obj = PoseCraftObject(
        id=str(__import__("uuid").uuid4()),
        name=str(args.get("name") or args.get("kind") or "Object")[:120],
        source="procedural",
        primitiveKind=str(args.get("kind") or "apple-box"),
        position={"x": float(args.get("x") or 0.0), "y": 0.0, "z": float(args.get("z") or 0.0)},
    )
    scene.objects.append(obj)
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc), "objectId": obj.id}


def preview_move_object(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(summary=f"Move object {args.get('objectId')}.", lines=["Affects: project"])


def apply_move_object(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....posecraft import scene_ops

    scene = _load_scene_for_mutation(ctx)
    ok = scene_ops.move_object(
        scene,
        str(args.get("objectId") or ""),
        x=args.get("x"),
        y=args.get("y"),
        z=args.get("z"),
    )
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc), "moved": ok}


def preview_place_figure(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(summary=f"Place figure {args.get('figureId')}.", lines=["Affects: project"])


def apply_place_figure(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....posecraft import scene_ops

    scene = _load_scene_for_mutation(ctx)
    ok = scene_ops.place_figure(
        scene,
        str(args.get("figureId") or ""),
        float(args.get("x") or 0.0),
        float(args.get("z") or 0.0),
        float(args.get("y") or 0.0),
        args.get("rotationY"),
    )
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc), "placed": ok}


def preview_sit_on_object(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(summary=f"Sit {args.get('figureId')} on {args.get('objectId')}.", lines=["Affects: project"])


def apply_sit_on_object(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....posecraft import scene_ops

    scene = _load_scene_for_mutation(ctx)
    result = scene_ops.sit_on_object(scene, str(args.get("figureId") or ""), str(args.get("objectId") or ""))
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc), **result}


def preview_look_at(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(summary=f"Turn {args.get('figureId')} to look at a target.", lines=["Affects: project"])


def apply_look_at(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....posecraft import scene_ops

    scene = _load_scene_for_mutation(ctx)
    result = scene_ops.look_at(
        scene,
        str(args.get("figureId") or ""),
        target_figure_id=args.get("targetFigureId"),
        target_object_id=args.get("targetObjectId"),
    )
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc), **result}


def preview_focus_figure(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(summary=f"Focus camera on {args.get('figureId') or 'stage'}.", lines=["Affects: project"])


def apply_focus_figure(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....posecraft import scene_ops

    scene = _load_scene_for_mutation(ctx)
    kind = str(args.get("kind") or "face")
    scene_ops.focus_subject(scene, kind=kind, subject_id=args.get("figureId") or args.get("objectId"))  # type: ignore[arg-type]
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc)}


def preview_save_shot(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(summary=f"Save shot '{args.get('name') or 'Shot'}'.", lines=["Affects: project"])


def apply_save_shot(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....posecraft import scene_ops

    scene = _load_scene_for_mutation(ctx)
    shot = scene_ops.save_shot(scene, str(args.get("name") or "Shot"))
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc), "shotId": shot.shotId}


def preview_capture_previz(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(summary="Capture a PoseCraft previz snapshot (requires imageAssetId).", lines=["Affects: project"])


def apply_capture_previz(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    image_asset_id = str(args.get("imageAssetId") or "")
    if not image_asset_id:
        return {"captured": False, "error": "imageAssetId is required. Capture writes a Library PNG first."}
    doc = posecraft_service.load_scene(ctx.project_id, ctx.db)
    from ....posecraft.state_snapshot import append_snapshot

    snap = append_snapshot(doc, image_asset_id, name=str(args.get("name") or "Previz"))
    posecraft_service.save_scene(ctx.project_id, doc, ctx.db, saved_by="codirector")
    return {"captured": True, "snapshotId": snap.snapshotId, "imageAssetId": image_asset_id}


def preview_propose_previz_plan(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(summary="Propose an Auto Previz shot plan.", lines=["Affects: project"])


def apply_propose_previz_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....posecraft.auto_previz import store_plan

    scene = _load_scene_for_mutation(ctx)
    names = [f.name for f in scene.figures[:3]] or ["the lead"]
    return store_plan(
        ctx.project_id,
        {
            "planId": f"previz-{scene.revision}",
            "approved": False,
            "shots": [
                {"name": "Shot 01 — Establishing wide", "focusKind": "stage"},
                {"name": "Shot 02 — Medium", "focusKind": "figure"},
                {"name": f"Shot 03 — {names[0]} close-up", "focusKind": "face"},
            ],
        },
    )


def preview_execute_previz_plan(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(summary="Execute an approved Auto Previz plan.", lines=["Affects: project"])


def apply_execute_previz_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....posecraft import scene_ops
    from ....posecraft.auto_previz import approve_plan, get_plan

    if not args.get("approved"):
        return {"executed": False, "error": "Creator approval is required."}
    plan = get_plan(str(args.get("planId") or ""))
    if plan is None or plan.get("projectId") != ctx.project_id:
        return {"executed": False, "error": "Auto Previz plan not found."}
    approve_plan(plan["planId"], ctx.project_id)
    scene = _load_scene_for_mutation(ctx)
    for shot in plan.get("shots") or []:
        scene_ops.focus_subject(
            scene,
            kind=shot.get("focusKind") or "stage",
            subject_id=scene.figures[0].id if scene.figures else None,
        )
        scene_ops.save_shot(scene, str(shot.get("name") or "Shot"))
    doc = _persist_scene(ctx, scene)
    return {"executed": True, "scene": _doc_summary(doc)}
