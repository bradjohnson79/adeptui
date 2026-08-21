"""Co-Director posecraft.* tool handlers.

Reads hydrate the PoseCraft scene from the project-scoped persistence layer.
Mutations are approval-gated by the Co-Director tool execution layer before
reaching these handlers; `apply_tool_mutation` additionally refuses to
silently overwrite a creatorModified scene without an explicit `force` flag
(set only after creator consent). No silent overwrite.
"""

from __future__ import annotations

from typing import Any

from ....posecraft import service as posecraft_service
from ....posecraft.schemas import (
    FigureInstance,
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
                "id": p.id,
                "label": p.name,
                "name": p.name,
                "type": p.kind,
                "furnitureKind": p.kind,
                "position": p.position,
            }
            for p in scene.primitives
        ],
    }


async def get_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc = posecraft_service.load_scene(ctx.project_id, ctx.db)
    return {"status": _doc_summary(doc)}


async def get_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    doc = posecraft_service.load_scene(ctx.project_id, ctx.db)
    summary = _doc_summary(doc)
    return {"scene": doc.model_dump(), "semantic": summary}


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
    doc = PoseCraftDocument(currentScene=scene)
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


def preview_apply_pose(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Apply pose {args.get('posePresetId')} to figure {args.get('figureId')}.",
        lines=["Affects: project"],
    )


def apply_apply_pose(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # Pose preset application is performed client-side by the Babylon viewport
    # (joint rotations). Co-Director records the intent; the creator approves
    # and the UI applies the preset. Here we mark the scene modified.
    scene = _load_scene_for_mutation(ctx)
    doc = _persist_scene(ctx, scene)
    return {"scene": _doc_summary(doc), "posePresetId": args.get("posePresetId")}


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
    return {
        "exportPreview": preview.model_dump(),
        "purpose": args.get("purpose", "shot"),
        "prompt": args.get("prompt", ""),
        "snapshotId": snapshot_id,
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
    """Build a honesty-labelled Storyboard handoff package from PoseCraft.

    PoseCraft is a *visual staging reference*, not a final frame. The package
    carries the export preview (figures/camera/aspect), the target scene id,
    a creator-facing label, and notes. The Storyboard ingest consumes it as a
    blocking sketch. creatorModified protection is enforced upstream by
    apply_tool_mutation (refuses silent overwrite of a creator-modified scene).
    When ``snapshotId`` is supplied, the package is built from the frozen
    Snapshot composition (PoseCraft Snapshot — Visual Staging Reference).
    """
    snapshot_id = args.get("snapshotId")
    preview = posecraft_service.build_export_preview(ctx.project_id, ctx.db, snapshot_id=snapshot_id)
    return {
        "exportPreview": preview.model_dump(),
        "sceneId": str(args.get("sceneId", ""))[:64],
        "label": str(args.get("label", preview.sceneName))[:200],
        "notes": str(args.get("notes", ""))[:4000],
        "honestyLabel": preview.honestyLabel,
        "snapshotId": snapshot_id,
        "imageAssetId": args.get("imageAssetId"),
        "next": "storyboard.ingest_posecraft_sketch",
    }
