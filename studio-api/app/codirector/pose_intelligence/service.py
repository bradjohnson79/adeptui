"""Pose intelligence orchestration.

Kinematic analysis always runs.
V-JEPA is reused from world_intelligence only when a snapshot/image exists.
PoseCraft remains usable when JEPA is down.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..world_intelligence.contracts import WorldStatePacket
from ..world_intelligence.service import is_available as world_is_available
from .analyze import (
    build_character_state,
    build_contacts,
    environment_from,
    plausibility_static,
    pose_cache_key,
    production_constraints,
    solve_joints,
    summarize,
)
from .compare import build_sequence, compare_pose_packets, review_intended_vs_observed
from .compile import build_conditioning_packet, compile_pose_motion_conditioning
from .contracts import (
    POSE_ANALYSIS_VERSION,
    MotionInterpretation,
    PoseMotionConditioningPacket,
    PoseWorldStatePacket,
)
from .persist import (
    load_conditioning,
    load_handoff,
    load_packet,
    load_sequence,
    save_conditioning,
    save_handoff,
    save_packet,
    save_sequence,
)

logger = logging.getLogger(__name__)


def _spatial_context(db: Optional[Session], project_id: str) -> dict[str, Any]:
    if db is None or not project_id:
        return {}
    try:
        from ...spatial_map.service import list_documents
        from ..perception.spatial_draft import load_spatial_draft

        docs = list_documents(db, project_id)
        map_id = str(getattr(docs[0], "id", "") or "") if docs else ""
        origins: dict[str, dict[str, float]] = {}
        if docs:
            from ...spatial_map.metric import compile_metric_lines, entity_meters

            for ch in docs[0].characters:
                meters = entity_meters(ch)
                if meters is None:
                    continue
                for key in (getattr(ch, "label", ""), getattr(ch, "tag", ""), getattr(ch, "characterId", "")):
                    name = str(key or "").strip().lower()
                    if name:
                        origins[name] = {"x": meters[0], "y": meters[1], "z": meters[2]}
        draft = load_spatial_draft(db, project_id, map_id) if map_id else None
        if draft is None and not origins:
            return {}
        return {
            "characterLocation": next(
                (fill.label for fill in (getattr(draft, "proposedFills", None) or []) if fill.kind == "character"),
                "",
            ) if draft is not None else "",
            "zonePhrases": [item.phrase for item in (getattr(draft, "zonePhrases", None) or [])[:8]] if draft is not None else [],
            "relationships": [
                f"{rel.subjectLabel} {rel.relation} {rel.objectLabel}"
                for rel in (getattr(draft, "relationships", None) or [])[:8]
            ] if draft is not None else [],
            "characterOrigins": origins,
            "metricLines": compile_metric_lines(docs[0]) if docs else [],
            "fingerprint": f"{map_id}:{len(origins)}:{len(getattr(draft, 'proposedFills', None) or [])}",
        }
    except Exception:
        logger.debug("Spatial extras unavailable for pose intelligence")
        return {}


def _jepa_for_asset(
    db: Session,
    project_id: str,
    asset_id: str,
    reference_asset_id: str = "",
) -> WorldStatePacket:
    if not asset_id:
        return WorldStatePacket(availability="insufficient_reference", reason="No pose snapshot image.")
    status = world_is_available(probe=False)
    if not status.get("available"):
        return WorldStatePacket(
            availability="unavailable",
            reason=str(status.get("reason") or "World intelligence unavailable."),
        )
    try:
        from ..world_intelligence.service import evaluate_project_assets

        refs = [reference_asset_id] if reference_asset_id else []
        return evaluate_project_assets(
            db,
            project_id=project_id,
            asset_id=asset_id,
            reference_asset_ids=refs,
            scene_id="",
        )
    except Exception as exc:
        logger.info("JEPA pose compare skipped: %s", exc)
        return WorldStatePacket(availability="unavailable", reason=str(exc)[:160])


def _pick_figure(figures: list[Any], figure_id: str = "") -> Any | None:
    if not figures:
        return None
    if figure_id:
        for fig in figures:
            fid = getattr(fig, "id", None) if not isinstance(fig, dict) else fig.get("id")
            if str(fid) == figure_id:
                return fig
    return figures[0]


def analyze_figure(
    *,
    project_id: str,
    scene: Any,
    figure: Any,
    primitives: list[Any],
    snapshot_id: str = "",
    image_asset_id: str = "",
    scene_id: str = "",
    db: Optional[Session] = None,
    reference_asset_id: str = "",
    persist: bool = True,
) -> PoseWorldStatePacket:
    revision = int(getattr(scene, "revision", 1) or 1)
    spatial = _spatial_context(db, project_id)
    cache_key = pose_cache_key(
        project_id,
        revision,
        figure,
        primitives,
        str(spatial.get("fingerprint") or ""),
        image_asset_id=image_asset_id,
    )
    if db is not None:
        existing = load_packet(db, project_id, snapshot_id=snapshot_id, fallback_latest=not snapshot_id)
        if (
            existing
            and existing.cacheKey == cache_key
            and existing.analysisVersion == POSE_ANALYSIS_VERSION
            and existing.projectId == project_id
        ):
            return existing

    origins = spatial.get("characterOrigins") or {}
    fig_name = str(getattr(figure, "name", None) or (figure.get("name") if isinstance(figure, dict) else "") or "").strip().lower()
    origin = origins.get(fig_name)
    if origin:
        ox, oz = float(origin.get("x") or 0.0), float(origin.get("z") or 0.0)
        if isinstance(figure, dict):
            pos = dict(figure.get("position") or {})
            if abs(float(pos.get("x") or 0.0)) < 1e-6 and abs(float(pos.get("z") or 0.0)) < 1e-6:
                figure = {**figure, "position": {"x": ox, "z": oz}}
        else:
            pos = getattr(figure, "position", None)
            if pos is not None and abs(float(getattr(pos, "x", 0.0) or 0.0)) < 1e-6 and abs(float(getattr(pos, "z", 0.0) or 0.0)) < 1e-6:
                pos.x = ox
                pos.z = oz
    world = solve_joints(figure)
    character = build_character_state(figure, world, revision)
    interaction = build_contacts(world, primitives, spatial.get("zonePhrases") or [])
    environment = environment_from(primitives, interaction, spatial)
    warnings = plausibility_static(character, interaction, primitives)
    motion = MotionInterpretation(confidence="insufficient_reference")
    constraints = production_constraints(character, interaction, warnings)
    summary, details = summarize(character, interaction, motion, warnings)

    jepa = WorldStatePacket(availability="insufficient_reference", reason="No snapshot image for visual compare.")
    if image_asset_id and db is not None:
        jepa = _jepa_for_asset(db, project_id, image_asset_id, reference_asset_id)

    availability = "available"
    reason = ""
    if jepa.availability == "unavailable" and image_asset_id:
        availability = "degraded"
        reason = "Pose analysis ready. Visual world intelligence unavailable."
    elif warnings:
        availability = "low_confidence" if character.balance == "uncertain" else "available"

    packet = PoseWorldStatePacket(
        availability=availability,
        reason=reason,
        stateKind="intended",
        projectId=project_id,
        sceneId=scene_id or str(getattr(scene, "name", "") or ""),
        snapshotId=snapshot_id or None,
        imageAssetId=image_asset_id or None,
        character=character,
        interaction=interaction,
        environment=environment,
        motion=motion,
        constraints=constraints,
        warnings=warnings,
        creatorFacingSummary=summary,
        creatorFacingDetails=details,
        world=jepa,
        cacheKey=cache_key,
        extras={
            "layer": "pose_intelligence",
            "complements": ["world_intelligence", "creation_perception", "temporal_continuity"],
            "doesNotOverwriteCRS": True,
        },
    )
    if db is not None and persist:
        save_packet(db, project_id, packet, snapshot_id=snapshot_id)
    return packet


def analyze_project_scene(
    db: Session,
    project_id: str,
    *,
    snapshot_id: str = "",
    figure_id: str = "",
    persist: bool = True,
) -> PoseWorldStatePacket:
    from ...posecraft import service as posecraft_service

    doc = posecraft_service.load_scene(project_id, db)
    scene = doc.currentScene
    figures = list(scene.figures)
    primitives = list(scene.primitives)
    image_asset_id = ""
    snap_id = snapshot_id or (doc.selectedSnapshotId or "")
    if snap_id:
        try:
            snap = posecraft_service.get_snapshot(project_id, snap_id, db)
            figures = list(snap.figures)
            primitives = list(snap.primitives)
            image_asset_id = snap.imageAssetId
            snap_id = snap.snapshotId
        except Exception:
            snap_id = ""
    figure = _pick_figure(figures, figure_id)
    if figure is None:
        return PoseWorldStatePacket(
            availability="unavailable",
            reason="No PoseCraft figure to analyze.",
            projectId=project_id,
        )
    return analyze_figure(
        project_id=project_id,
        scene=scene,
        figure=figure,
        primitives=primitives,
        snapshot_id=snap_id,
        image_asset_id=image_asset_id,
        db=db,
        persist=persist,
    )


def compare_project_poses(
    db: Session,
    project_id: str,
    *,
    from_snapshot_id: str,
    to_snapshot_id: str,
) -> dict[str, Any]:
    from ...posecraft import service as posecraft_service

    first = analyze_project_scene(db, project_id, snapshot_id=from_snapshot_id)
    second = analyze_project_scene(db, project_id, snapshot_id=to_snapshot_id)
    first_fig = None
    second_fig = None
    try:
        a = posecraft_service.get_snapshot(project_id, from_snapshot_id, db)
        b = posecraft_service.get_snapshot(project_id, to_snapshot_id, db)
        first_fig = a.figures[0] if a.figures else None
        second_fig = b.figures[0] if b.figures else None
    except Exception:
        pass
    if first_fig is not None and second_fig is not None:
        a_world = solve_joints(first_fig)
        b_world = solve_joints(second_fig)
        from .analyze import compare_worlds

        _changes, warnings, motion = compare_worlds(
            a_world, b_world, first.character, second.character, first.interaction, second.interaction
        )
        second.motion = motion
        second.warnings = list(dict.fromkeys([*second.warnings, *warnings]))
        second.constraints = production_constraints(second.character, second.interaction, second.warnings)
        second.creatorFacingSummary, second.creatorFacingDetails = summarize(
            second.character, second.interaction, motion, second.warnings
        )
        if first.imageAssetId and second.imageAssetId:
            second.world = _jepa_for_asset(db, project_id, second.imageAssetId, first.imageAssetId)
        save_packet(db, project_id, second, snapshot_id=to_snapshot_id)

    transition = compare_pose_packets(first, second, first_figure=first_fig, second_figure=second_fig)
    sequence = build_sequence(project_id, [first, second], [first_fig, second_fig])
    save_sequence(db, project_id, sequence)
    return {
        "from": first.model_dump(mode="json"),
        "to": second.model_dump(mode="json"),
        "transition": transition.model_dump(mode="json"),
        "sequence": sequence.model_dump(mode="json"),
    }


def latest(db: Session, project_id: str, *, snapshot_id: str = "") -> dict[str, Any]:
    packet = load_packet(db, project_id, snapshot_id=snapshot_id)
    sequence = load_sequence(db, project_id)
    conditioning = load_conditioning(db, project_id)
    status = world_is_available(probe=False)
    return {
        "available": bool(packet and packet.is_actionable()),
        "worldAvailable": bool(status.get("available")),
        "worldInstalled": bool(status.get("installed", status.get("available"))),
        "packet": packet.model_dump(mode="json") if packet else None,
        "sequence": sequence.model_dump(mode="json") if sequence else None,
        "conditioning": conditioning.model_dump(mode="json") if conditioning else None,
        "sceneCreatorHandoff": load_handoff(db, project_id, "scene-creator"),
        "timelineHandoff": load_handoff(db, project_id, "timeline"),
    }


def handoff_scene_creator(db: Session, project_id: str, *, snapshot_id: str = "") -> dict[str, Any]:
    packet = analyze_project_scene(db, project_id, snapshot_id=snapshot_id)
    invariants = {
        "facing": packet.character.facingDirection,
        "support": packet.character.primarySupport,
        "stance": packet.character.stance,
        "contacts": packet.interaction.handContact + packet.interaction.footContact,
        "stylization": packet.constraints.stylizationOverride,
        "creatorIntentHonored": True,
    }
    payload = {
        "kind": "scene-creator",
        "poseWorldStatePacketId": packet.packetId,
        "poseSnapshotId": packet.snapshotId,
        "imageAssetId": packet.imageAssetId,
        "poseInvariants": invariants,
        "packet": packet.model_dump(mode="json"),
    }
    save_handoff(db, project_id, "scene-creator", payload)
    return payload


def handoff_timeline(db: Session, project_id: str, *, snapshot_id: str = "") -> dict[str, Any]:
    packet = analyze_project_scene(db, project_id, snapshot_id=snapshot_id)
    conditioning = build_conditioning_packet(packet)
    save_conditioning(db, project_id, conditioning)
    compiled = compile_pose_motion_conditioning(packet)
    payload = {
        "kind": "timeline",
        "poseWorldStatePacketId": packet.packetId,
        "conditioningPacketId": conditioning.packetId,
        "poseSnapshotId": packet.snapshotId,
        "imageAssetId": packet.imageAssetId,
        "compiled": compiled,
        "packet": packet.model_dump(mode="json"),
        "conditioning": conditioning.model_dump(mode="json"),
    }
    save_handoff(db, project_id, "timeline", payload)
    return payload


def load_timeline_conditioning(db: Session, project_id: str) -> PoseMotionConditioningPacket | None:
    return load_conditioning(db, project_id)


def load_intended_packet(db: Session, project_id: str) -> PoseWorldStatePacket | None:
    return load_packet(db, project_id)


def continuity_review_for_observation(
    db: Session,
    project_id: str,
    *,
    observed_text: str,
    observed_world: WorldStatePacket | None = None,
) -> dict[str, Any]:
    intended = load_packet(db, project_id)
    review = review_intended_vs_observed(
        intended,
        observed_world=observed_world,
        observed_text=observed_text,
        project_id=project_id,
    )
    return review.model_dump(mode="json")
