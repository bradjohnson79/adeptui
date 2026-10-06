"""Capability handler: analyze.video — watch and hear a Timeline clip.

Resolves the scene's playable video (approved clip / sceneStitch / latest video
asset on the scene), runs Media Intelligence, and returns a creatorAck with
counts of contact events, cue opportunities, and music opportunities. Does NOT
place audio — that is timeline.add_audio's job.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ....db import Asset, Scene
from ...video_intelligence import media_analyze, media_persist
from ...video_intelligence.media_packet import (
    MediaIntelligencePacket,
    TimelineAnalysisContext,
)
from ...video_intelligence.media_probe import probe_media

ANALYZE_VIDEO_QUESTION = (
    "You are the perception layer of a film production system. Watch AND listen to this clip carefully. "
    "Respond with ONLY a JSON object (no prose before or after) with these keys:\n"
    '"summary": one-paragraph description of what happens, including anything you hear;\n'
    '"visualEvents": list of {"startTime","endTime","label","detail","phase","confidence"} for visible actions;\n'
    '"audioEvents": list of {"startTime","endTime","eventType","intensity","material","context","presentInAudio","confidence"} '
    "for sounds you actually hear;\n"
    '"speechSegments": list of {"startTime","endTime","speaker","transcription","isSilence","overlap","confidence"} '
    "— transcribe any speech exactly word for word;\n"
    '"motionEvents": list of {"startTime","endTime","subject","motionType","direction","velocity","confidence"} '
    "for camera/character/object motion;\n"
    '"contactEvents": list of {"startTime","endTime","characterLabel","foot","surface","timingSource","confidence"} '
    "for visible foot/hand/body contacts that should produce a sound effect;\n"
    '"cueOpportunities": list of {"startTime","endTime","kind","label","suggestedQuery","presentInAudio","characterLabel","confidence"} '
    "for moments where a sound effect or ambience bed would help;\n"
    '"musicOpportunities": list of {"startTime","endTime","role","intensity","dialogueDensity","emotionalTone","duckUnderDialogue"} '
    "for moments where a music cue should enter or exit;\n"
    '"characters": list of {"label","actionState","actionCompletion","movementDirection","identityCertainty"};\n'
    '"camera": {"movementType","framing","certainty"};\n'
    '"confidence": number 0-1.\n'
    "Rules: report only what you genuinely see or hear; if the clip has audible sound, audioEvents or speechSegments "
    "must reflect it; if the clip is silent, say so in the summary and leave audioEvents empty; do not invent facts; "
    "times are seconds from clip start."
)


def _resolve_scene_stitch_asset_id(director_json: str) -> str | None:
    """Return the sceneStitch assetId from the embedded Timeline Master, if any."""
    try:
        data = json.loads(director_json or "{}")
        master = data.get("timelineMaster") or {}
        stitch = master.get("sceneStitch") or {}
        asset_id = stitch.get("assetId")
        if asset_id:
            return str(asset_id).strip()
    except Exception:
        pass
    return None


def _resolve_latest_video_asset_id(db: Session, project_id: str, scene_id: str) -> str | None:
    """Fail-closed fallback: the most recent video asset associated with this project/scene.

    The strongest link is a sceneStitch asset. If that is missing, we look for the
    latest project video asset whose tag or filename suggests it belongs to the scene
    (scene_stitch, editor_mix, scene_N lipsync, ingredients_render). If nothing is
    tagged, we take the latest project video asset and let the handler fail later if
    it is not actually the scene's playable clip.
    """
    rows = (
        db.query(Asset)
        .filter(Asset.project_id == project_id, Asset.kind == "video")
        .order_by(Asset.created_at.desc())
        .all()
    )
    if not rows:
        return None

    # Prefer scene-specific tags, then any video asset.
    scene_specific_tags = {"scene_stitch", "editor_mix", "ingredients_render"}
    for asset in rows:
        tag = str(getattr(asset, "tag", "") or "").lower()
        filename = str(getattr(asset, "filename", "") or "").lower()
        if (
            tag in scene_specific_tags
            or tag.startswith("scene_")
            or f"scene_{scene_id[:8]}" in tag
        ):
            return str(asset.id)
    return str(rows[0].id)


def _resolve_batch_visual_asset_id(director_json: str) -> str | None:
    """Prefer the first Timeline batch visual take when sceneStitch is absent.

    Scene 10-style multi-batch masters often have playable takes on
    batchBlocks[*].visualClips before a sceneStitch exists. Watching the
    wrong (latest project) video would break Omni->audio closed loop.
    """
    try:
        data = json.loads(director_json or "{}")
        master = data.get("timelineMaster") or {}
        for batch in master.get("batchBlocks") or []:
            for clip in batch.get("visualClips") or []:
                if str(clip.get("kind") or "video").lower() not in {"video", "take", ""}:
                    continue
                asset_id = str(clip.get("assetId") or "").strip()
                if asset_id:
                    return asset_id
    except Exception:
        pass
    return None


def _resolve_scene_output_asset_id(db: Session, project_id: str, scene: Scene) -> str | None:
    """Prefer the library asset that IS the scene's mastered render (scene.output_path).

    Batch visualClips can hold several full-length takes; the first take is not
    necessarily the mastered one. Watching a non-mastered take would produce
    lip-sync windows for the wrong footage.
    """
    output_path = str(getattr(scene, "output_path", None) or "").strip()
    if not output_path:
        return None
    row = (
        db.query(Asset)
        .filter(
            Asset.project_id == project_id,
            Asset.kind == "video",
            Asset.path == output_path,
        )
        .first()
    )
    return str(row.id) if row is not None else None


def _resolve_scene_publish_asset_id(db: Session, project_id: str, scene_id: str) -> str | None:
    """Prefer Timeline scenePublish.publishedAssetId over stitch/batch/latest."""
    try:
        from ....director_timeline_w46.store import load_master

        payload = load_master(db, project_id, scene_id)
    except Exception:
        return None
    if not payload.get("ok"):
        return None
    master = payload.get("master") or {}
    pub = master.get("scenePublish") or {}
    asset_id = str(pub.get("publishedAssetId") or "").strip()
    if not asset_id:
        return None
    asset = db.get(Asset, asset_id)
    if asset is None or asset.project_id != project_id or str(asset.kind or "") != "video":
        return None
    return asset_id


def _resolve_playable_video_asset_id(
    db: Session, project_id: str, scene_id: str
) -> str | None:
    """Resolve the scene's playable video asset, or None if nothing can be found."""
    scene = db.get(Scene, scene_id)
    if scene is None or scene.project_id != project_id:
        return None

    asset_id = _resolve_scene_publish_asset_id(db, project_id, scene_id)
    if asset_id:
        return asset_id

    asset_id = _resolve_scene_output_asset_id(db, project_id, scene)
    if asset_id:
        return asset_id

    asset_id = _resolve_scene_stitch_asset_id(scene.director_json)
    if asset_id:
        return asset_id

    asset_id = _resolve_batch_visual_asset_id(scene.director_json)
    if asset_id:
        return asset_id

    return _resolve_latest_video_asset_id(db, project_id, scene_id)


def _video_duration_sec(asset: Asset) -> float:
    """Best-effort full duration of the playable video asset."""
    path = getattr(asset, "path", None)
    if path:
        try:
            facts = probe_media(path)
            duration = float(facts.durationSec or 0.0)
            if duration > 0:
                return duration
        except Exception:
            pass
    return 0.0


def _set_timeline_context(
    packet: MediaIntelligencePacket,
    *,
    project_id: str,
    scene_id: str,
    asset_id: str,
    execution_id: str,
    duration_sec: float,
    playhead_sec: float | None,
) -> MediaIntelligencePacket:
    """Stamp the packet with the Timeline context it was analyzed for and re-save."""
    packet.timelineContext = TimelineAnalysisContext(
        projectId=project_id,
        sceneId=scene_id,
        clipAssetId=asset_id,
        executionId=execution_id,
        rangeStartSec=0.0,
        rangeEndSec=duration_sec if duration_sec > 0 else None,
        playheadSec=playhead_sec,
    )
    return packet


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    prompt: str = "",
    scene_id: str = "",
    playhead_sec: float | None = None,
    **_: Any,
) -> dict[str, Any]:
    from ....director_timeline_w46 import store as timeline_store

    if not scene_id:
        return {
            "status": "failed",
            "error": "Open a scene on the Timeline first so I know which clip to review.",
            "child_jobs": [],
            "surface_type": "media_intelligence",
        }

    scene = db.get(Scene, scene_id)
    if scene is None or scene.project_id != project_id:
        return {
            "status": "failed",
            "error": "That scene is not in this project.",
            "child_jobs": [],
            "surface_type": "media_intelligence",
        }

    asset_id = _resolve_playable_video_asset_id(db, project_id, scene_id)
    if not asset_id:
        # Ensure Timeline Master is loaded so a freshly-migrated scene gets its
        # sceneStitch field materialized before we give up.
        timeline_store.load_master(db, project_id, scene_id)
        asset_id = _resolve_playable_video_asset_id(db, project_id, scene_id)
    if not asset_id:
        return {
            "status": "failed",
            "error": "No playable video clip was found for this scene. Generate or stitch a scene preview first.",
            "child_jobs": [],
            "surface_type": "media_intelligence",
        }

    asset = db.get(Asset, asset_id)
    if asset is None or asset.project_id != project_id or asset.kind != "video":
        return {
            "status": "failed",
            "error": f"The resolved clip asset ({asset_id}) is not a video in this project.",
            "child_jobs": [],
            "surface_type": "media_intelligence",
        }

    path = getattr(asset, "path", None)
    if not path or not Path(str(path)).is_file():
        return {
            "status": "failed",
            "error": "The playable video file is missing on disk.",
            "child_jobs": [],
            "surface_type": "media_intelligence",
        }

    duration_sec = _video_duration_sec(asset)

    packet = media_analyze.analyze_asset(
        db,
        project_id,
        asset_id,
        mode="full",
        question=ANALYZE_VIDEO_QUESTION,
        duration_sec=duration_sec if duration_sec > 0 else float(scene.duration_sec or 5.0),
    )

    if packet.is_ready():
        packet = _set_timeline_context(
            packet,
            project_id=project_id,
            scene_id=scene_id,
            asset_id=asset_id,
            execution_id=execution_id,
            duration_sec=duration_sec,
            playhead_sec=playhead_sec,
        )
        media_persist.save_packet(db, project_id, packet)
        # WAVE 4: CD writes VerifiedContinuityMemory after Perception Authority.
        # parseOk=false never becomes canon (empty verifiedFacts).
        try:
            from ...verified_continuity_memory import (
                facts_from_media_packet,
                write_verified_continuity,
            )
            parse_ok = bool(packet.is_ready())
            extras = getattr(packet, "extras", None) or {}
            if not isinstance(extras, dict):
                extras = {}
            tc = getattr(packet, "timelineContext", None)
            take_id = str(
                extras.get("takeId")
                or extras.get("take_id")
                or (getattr(tc, "takeId", None) if tc is not None else None)
                or "scene-watch"
            ).strip()
            revision = str(
                extras.get("revision")
                or extras.get("sceneRevision")
                or (getattr(tc, "revision", None) if tc is not None else None)
                or "1"
            ).strip()
            batch_index = int(
                extras.get("batchIndex")
                or extras.get("batch_index")
                or (getattr(tc, "batchIndex", None) if tc is not None else None)
                or 0
            )
            write_verified_continuity(
                project_id=project_id,
                scene_id=scene_id,
                take_id=take_id,
                revision=revision,
                batch_index=batch_index,
                facts=facts_from_media_packet(packet),
                source_packet_id=str(getattr(packet, "packetId", "") or ""),
                parse_ok=parse_ok,
            )
        except Exception:
            pass
        # Contract: Timeline Master points at the packet Co-Director just produced
        # so audio.generate_* / timeline.add_audio can consume the same watch.
        try:
            from ....director_timeline_w46 import store as timeline_store
            from ....director_timeline_w46.contracts import SceneTimelineMaster

            payload = timeline_store.load_master(db, project_id, scene_id)
            if payload.get("ok"):
                master = SceneTimelineMaster.model_validate(payload["master"])
                master.lastMediaIntelligencePacketId = packet.packetId
                timeline_store.save_master(
                    db, project_id, scene_id, master, touch_batches=False
                )
        except Exception:
            # Perception succeeded; Timeline pointer is best-effort and must not
            # fail the creator-facing analyze.video ack.
            pass

    summary = (packet.summary or "").strip() or "Adept watched the clip but produced no summary."
    contact_count = len(packet.contactEvents or [])
    cue_count = len(packet.cueOpportunities or [])
    music_count = len(packet.musicOpportunities or [])

    ack = (
        f"Watched the scene clip. {summary} "
        f"Found {contact_count} contact event(s), {cue_count} cue opportunity(s), "
        f"and {music_count} music opportunity(s)."
    ).strip()

    if not packet.is_ready():
        return {
            "status": "failed",
            "error": packet.reason or "Media Intelligence could not review this clip.",
            "child_jobs": [],
            "job_ids": [execution_id],
            "surface_type": "media_intelligence",
            "result_asset_ids": [asset_id],
            "creatorAck": ack,
        }

    return {
        "status": "completed",
        "child_jobs": [],
        "job_ids": [execution_id],
        "surface_type": "media_intelligence",
        "result_asset_ids": [asset_id],
        "mediaIntelligencePacketId": packet.packetId,
        "creatorAck": ack,
    }
