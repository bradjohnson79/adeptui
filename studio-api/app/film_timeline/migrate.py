"""One-time SceneTimelineMaster → FilmTimeline transform.

A whole-scene take's ordered windows become segments of one shot, because
those windows were continuation, not cinematic cuts.
"""

from __future__ import annotations

from typing import Any

from .contracts import FilmTimeline, MediaClip, PendingPlacement, ReferenceAsset, Segment, Shot, ShotState


def _text(value: Any) -> str:
    return str(value or "").strip()


def _ref_from_dict(raw: dict[str, Any], *, inherited: bool) -> ReferenceAsset | None:
    asset_id = _text(raw.get("assetId") or raw.get("asset_id") or raw.get("id"))
    if not asset_id:
        return None
    kind = _text(raw.get("type") or raw.get("kind") or raw.get("role") or "other").lower()
    mapping = {
        "character": "character",
        "crs": "character",
        "prop": "prop",
        "prs": "prop",
        "environment": "environment",
        "place": "environment",
        "ers": "environment",
        "first_frame": "first_frame",
        "start": "first_frame",
        "storyboard": "storyboard",
        "image": "image",
        "video": "video",
        "motion": "video",
    }
    return ReferenceAsset(
        type=mapping.get(kind, "other"),  # type: ignore[arg-type]
        assetId=asset_id,
        label=_text(raw.get("label") or raw.get("name") or raw.get("tag")),
        role=_text(raw.get("role")),
        source="timeline-master",
        inherited=inherited,
    )


def _prompt_text(block: dict[str, Any]) -> str:
    lines: list[str] = []
    for segment in block.get("promptSegments") or []:
        if not isinstance(segment, dict):
            continue
        text = _text(segment.get("text"))
        if not text:
            continue
        start = float(segment.get("start") or 0)
        length = float(segment.get("length") or 0)
        end = start + length
        lines.append(f"{start:g}–{end:g} sec\n{text}")
    return "\n\n".join(lines)


def _clip(raw: dict[str, Any], track: str) -> MediaClip | None:
    asset_id = _text(raw.get("assetId") or raw.get("asset_id"))
    if not asset_id:
        return None
    return MediaClip(
        id=_text(raw.get("id")) or MediaClip().id,
        trackType=track,  # type: ignore[arg-type]
        assetId=asset_id,
        label=_text(raw.get("label") or raw.get("title")),
        startSec=float(raw.get("start") or raw.get("startSec") or 0),
        durationSec=float(raw.get("length") or raw.get("durationSec") or raw.get("duration") or 0),
        trimInSec=float(raw.get("trimStart") or raw.get("trimInSec") or 0),
        volume=float(raw.get("volume") if raw.get("volume") is not None else 1),
        fadeInSec=float(raw.get("fade_in") or raw.get("fadeInSec") or 0),
        fadeOutSec=float(raw.get("fade_out") or raw.get("fadeOutSec") or 0),
        muted=bool(raw.get("muted")),
        metadata={"migratedFrom": "timeline-master"},
    )


def _audio_track(raw: dict[str, Any]) -> str | None:
    blob = " ".join(
        _text(raw.get(key))
        for key in ("kind", "role", "label", "track", "category")
    ).lower()
    if any(token in blob for token in ("ambience", "room tone", "room_tone", "bed")):
        return "ambience"
    if "sfx" in blob or "effect" in blob:
        return "sfx"
    if "music" in blob or "score" in blob:
        return "music"
    if any(token in blob for token in ("voice", "dialogue", "narration", "dialog")):
        return "voice"
    return None


def migrate_master_dict(
    master: dict[str, Any] | None,
    *,
    project_id: str,
    scene_id: str,
    scene_name: str = "Scene",
    scene_prompt: str = "",
    scene_duration: float = 10.0,
    generator_id: str | None = None,
    dialogue_tracks: list[dict[str, Any]] | None = None,
) -> FilmTimeline:
    blocks = []
    if isinstance(master, dict):
        blocks = [item for item in (master.get("batchBlocks") or []) if isinstance(item, dict)]
        blocks.sort(key=lambda item: int(item.get("order") or 0))

    scene_refs: list[ReferenceAsset] = []
    seen: set[str] = set()
    segments: list[Segment] = []
    prompt_parts: list[str] = []
    first_frame = ""
    for index, block in enumerate(blocks):
        for raw in block.get("references") or []:
            if isinstance(raw, dict):
                ref = _ref_from_dict(raw, inherited=True)
                if ref and ref.assetId not in seen:
                    seen.add(ref.assetId)
                    scene_refs.append(ref)
        for anchor in block.get("sourceAnchors") or []:
            if isinstance(anchor, dict) and not first_frame:
                first_frame = _text(anchor.get("assetId"))
        text = _prompt_text(block)
        if text:
            prompt_parts.append(text)
        approved = block.get("approvedClip") if isinstance(block.get("approvedClip"), dict) else {}
        asset_id = _text(
            (approved or {}).get("assetId")
            or block.get("currentTakeAssetId")
            or ""
        )
        duration = float((block.get("duration") or {}).get("seconds") or (block.get("duration") or {}).get("durationSec") or 0)
        if duration <= 0:
            duration = float(block.get("durationSec") or 10)
        status = _text(block.get("status")).lower()
        segment_status = "completed" if asset_id else "empty"
        if status in {"failed", "cancelled", "generating", "queued"}:
            segment_status = "generating" if status == "generating" else status
            if status == "queued":
                segment_status = "queued"
        segments.append(
            Segment(
                order=index,
                durationSec=duration,
                requestedDurationSec=duration,
                status=segment_status,  # type: ignore[arg-type]
                timedPrompt=text,
                generatorId=_text(block.get("generatorId")) or generator_id,
                assetId=asset_id or None,
                continuationStrategy="reference_set" if index else None,
                firstFrameAssetId=first_frame or None,
                generationMetadata={"migratedFromBatchId": block.get("id")},
            )
        )

    film = FilmTimeline(
        projectId=project_id,
        sceneId=scene_id,
        name=scene_name or "Scene",
        generatorId=_text((master or {}).get("sceneGeneratorId")) or generator_id,
        references=scene_refs,
        migratedFromMaster=bool(blocks or (isinstance(master, dict) and master)),
        migration={
            "source": "SceneTimelineMaster",
            "batchCount": len(blocks),
            "rule": "ordered windows of one scene take become segments of one shot",
        },
    )

    shot_prompt = "\n\n".join(prompt_parts) or scene_prompt
    duration_total = sum(item.durationSec for item in segments) or float(scene_duration or 10)
    state = ShotState(
        sceneId=scene_id,
        modelId=film.generatorId,
        firstFrameAssetId=first_frame or None,
        references=list(scene_refs),
        promptHistory=[shot_prompt] if shot_prompt else [],
        segmentIds=[item.id for item in segments],
        priorSegmentId=segments[-1].id if segments else None,
    )
    shot = Shot(
        sceneId=scene_id,
        name="Shot 01",
        order=0,
        durationSec=segments[-1].durationSec if segments else float(scene_duration or 10),
        timedPrompt=shot_prompt,
        status="ready" if any(item.status == "completed" for item in segments) else "draft",
        state=state,
        segments=segments,
    )
    shot.state.shotId = shot.id
    film.shots = [shot]

    for block in blocks:
        for raw in block.get("sfxClips") or []:
            if isinstance(raw, dict):
                clip = _clip(raw, "sfx")
                if clip:
                    film.sfx.append(clip)
        for raw in block.get("audioClips") or []:
            if not isinstance(raw, dict):
                continue
            track = _audio_track(raw)
            if track == "sfx":
                clip = _clip(raw, "sfx")
                if clip:
                    film.sfx.append(clip)
                continue
            role = track or "generic"
            clip = _clip(raw, "audio")
            if clip is None:
                continue
            clip.role = role
            clip.metadata["role"] = role
            film.audio.append(clip)
        for raw in block.get("visualClips") or []:
            if isinstance(raw, dict) and _text(raw.get("kind")).lower() == "video":
                clip = _clip(raw, "voice")
                if clip:
                    film.videoClips.append(
                        MediaClip(
                            assetId=clip.assetId,
                            label=clip.label or "Video",
                            startSec=clip.startSec,
                            durationSec=clip.durationSec,
                            trackType="video",
                            metadata={"lane": "video", "migratedFrom": "visualClips"},
                        )
                    )

    for track in dialogue_tracks or []:
        if not isinstance(track, dict):
            continue
        for raw in track.get("clips") or []:
            if not isinstance(raw, dict):
                continue
            asset_id = _text(raw.get("assetId"))
            if not asset_id:
                continue
            start_ms = float(raw.get("startMs") or 0)
            duration_ms = float(raw.get("durationMs") or 0)
            film.audio.append(
                MediaClip(
                    trackType="audio",
                    role="voice",
                    assetId=asset_id,
                    label=_text(raw.get("label")) or "Dialogue",
                    startSec=start_ms / 1000.0,
                    durationSec=duration_ms / 1000.0 if duration_ms else 0,
                    metadata={"migratedFrom": "dialogueTracks", "recordId": raw.get("recordId"), "role": "voice"},
                )
            )

    # duration_total is retained on the shot via its segments; unused name kept honest.
    _ = duration_total
    return film
