"""ACTIVE TIMELINE SCENE SNAPSHOT — composed, not a second store.

When Co-Director is in workspace=timeline, answers about the active shot
must read this join. Do not invent scenes[0]. Do not treat @tokens as
bindings unless they resolved to IDs. Approval = approvedClip on the
bound scene's batches.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

_PROMPT_CLIP_CHARS = 400
_SUMMARY_CLIP_CHARS = 240


def _clip(text: str, limit: int) -> str:
    value = " ".join((text or "").split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _dump(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return {}



# ---------------------------------------------------------------------------
# Timeline V2 (filmTimeline) observation - additive, V2-first / W46-fallback.
#
# The live Timeline owner is the V2 document persisted under
# director_json.filmTimeline. The W46 timelineMaster is retired. These helpers
# let Co-Director observe V2 without touching the certified W46 path: when no
# V2 document exists the caller falls through to the existing W46 join exactly
# as before.
# ---------------------------------------------------------------------------


def _film_document_exists(db: Session, project_id: str, scene_id: str) -> bool:
    """True only when director_json already holds a V2 film document.

    Mirrors film_timeline.store.load_film's own condition (a versioned dict).
    Detection stays read-only: calling load_film on a W46-only scene would
    migrate and persist a brand-new filmTimeline, which would silently make
    every scene V2 and change the fallback path.
    """
    try:
        from ..film_timeline import store as film_store
        from ..scene_service import get_scene

        scene = get_scene(db, project_id, scene_id)
        if scene is None:
            return False
        raw = json.loads(scene.director_json or "{}")
    except Exception:
        return False
    doc = raw.get(film_store.FILM_KEY) if isinstance(raw, dict) else None
    return isinstance(doc, dict) and bool(doc.get("version"))


def _pick_active_shot(shots: Any, playhead_sec: float | None):
    """Ordered shots -> (active shot, its scene-start second). Playhead-scoped."""
    ordered = sorted(shots or [], key=lambda shot: int(getattr(shot, "order", 0) or 0))
    if not ordered:
        return None, 0.0
    if playhead_sec is not None:
        cursor = 0.0
        for shot in ordered:
            end = cursor + float(getattr(shot, "durationSec", 0.0) or 0.0)
            if cursor <= playhead_sec < end:
                return shot, cursor
            cursor = end
    return ordered[0], 0.0


def _pick_active_segment(shot: Any, offset_sec: float | None):
    segments = sorted(
        getattr(shot, "segments", None) or [],
        key=lambda seg: int(getattr(seg, "order", 0) or 0),
    )
    if not segments:
        return None
    if offset_sec is not None:
        cursor = 0.0
        for seg in segments:
            end = cursor + float(getattr(seg, "durationSec", 0.0) or 0.0)
            if cursor <= offset_sec < end:
                return seg
            cursor = end
    for seg in reversed(segments):
        if getattr(seg, "assetId", None) or str(getattr(seg, "status", "") or "") not in ("", "empty"):
            return seg
    return segments[-1]


def _reference_rows(refs: Any, source: str, out: list[dict[str, Any]], seen: set) -> None:
    for ref in refs or []:
        key = (
            str(getattr(ref, "id", "") or ""),
            str(getattr(ref, "assetId", "") or ""),
            str(getattr(ref, "tag", "") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "id": key[0],
                "type": str(getattr(ref, "type", "") or "other"),
                "tag": str(getattr(ref, "tag", "") or ""),
                "label": str(getattr(ref, "label", "") or ""),
                "assetId": key[1],
                "role": str(getattr(ref, "role", "") or ""),
                "inherited": bool(getattr(ref, "inherited", False)),
                "source": source,
            }
        )


def _build_film_timeline_v2_snapshot(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    grounding: dict[str, Any],
    workspace: str | None,
    playhead_sec: float | None,
    selected_batch_id: str | None,
) -> dict[str, Any] | None:
    """Observe the live Timeline V2 document. None when the scene is not V2.

    The returned shape keeps every existing snapshot key and adds a structured
    timelineV2 block. Important facts are mirrored into the existing keys
    only where the V2 document is their truth.
    """
    if not _film_document_exists(db, project_id, scene_id):
        return None
    try:
        from ..db import Scene
        from ..film_timeline.store import load_film

        loaded = load_film(db, project_id, scene_id)
        if not loaded.get("ok"):
            return None
        film = loaded["film"]

        scene_row = db.get(Scene, scene_id)
        scene_aspect = str(getattr(scene_row, "aspect_ratio", "") or "") or None
        scene_prompt = str(getattr(scene_row, "prompt", "") or "")
        scene_summary = str(getattr(scene_row, "summary", "") or "")

        playhead = float(playhead_sec) if playhead_sec is not None else 0.0
        shot, shot_start = _pick_active_shot(film.shots, playhead_sec)
        offset = max(0.0, playhead - shot_start) if shot is not None and playhead_sec is not None else None
        segment = _pick_active_segment(shot, offset) if shot is not None else None
        state = getattr(shot, "state", None) if shot is not None else None
        resolved_state = dict(getattr(state, "resolvedGeneration", None) or {}) if state is not None else {}

        references: list[dict[str, Any]] = []
        scene_seen: set = set()
        _reference_rows(getattr(film, "references", None), "scene", references, scene_seen)
        if state is not None:
            _reference_rows(getattr(state, "references", None), "shot", references, scene_seen)

        def _canvas_from(candidate_seg: Any) -> dict[str, Any]:
            meta = dict(getattr(candidate_seg, "generationMetadata", None) or {}) if candidate_seg is not None else {}
            for meta_key in ("legalCanvas", "resolvedGeneration"):
                candidate = meta.get(meta_key)
                if isinstance(candidate, dict) and candidate:
                    return dict(candidate)
            return {}

        # Resolved legal canvas: the active segment first, else the most recent
        # segment that actually resolved one (e.g. a queued active segment that
        # has not resolved yet must not erase the scene's known canvas).
        canvas: dict[str, Any] = _canvas_from(segment)
        if not canvas:
            for candidate_seg in sorted(
                getattr(shot, "segments", None) or [],
                key=lambda seg: int(getattr(seg, "order", 0) or 0),
                reverse=True,
            ):
                if candidate_seg is segment:
                    continue
                canvas = _canvas_from(candidate_seg)
                if canvas:
                    break
        if not canvas:
            candidate = resolved_state.get("resolvedGeneration")
            canvas = dict(candidate) if isinstance(candidate, dict) else {}
        width = canvas.get("width")
        height = canvas.get("height")
        legal_canvas = (
            {
                "width": width,
                "height": height,
                "resolution": canvas.get("resolution") or (str(width) + "x" + str(height) if width and height else None),
                "megapixels": canvas.get("megapixels"),
                "aspect": canvas.get("aspect"),
                "label": canvas.get("label"),
                "source": canvas.get("source"),
                "productId": canvas.get("productId"),
            }
            if canvas
            else None
        )

        h3_resolution = resolved_state.get("h3Resolution") if isinstance(resolved_state.get("h3Resolution"), dict) else None
        megapixel_tier = None
        if isinstance(h3_resolution, dict):
            megapixel_tier = h3_resolution.get("megapixels")
        if megapixel_tier is None:
            megapixel_tier = resolved_state.get("megapixels")
        if megapixel_tier is None and canvas:
            megapixel_tier = canvas.get("megapixels")

        generator_id = getattr(state, "modelId", None) if state is not None else None
        if not generator_id:
            generator_id = getattr(film, "generatorId", None)
        if not generator_id and segment is not None:
            generator_id = getattr(segment, "generatorId", None)
        if not generator_id and scene_row is not None:
            generator_id = getattr(scene_row, "engine", None)

        shot_duration = float(getattr(shot, "durationSec", 0.0) or 0.0) if shot is not None else 0.0
        ordered_segments = (
            sorted(
                getattr(shot, "segments", None) or [],
                key=lambda seg: int(getattr(seg, "order", 0) or 0),
            )
            if shot is not None
            else []
        )

        from ..film_timeline.shot_identity import creator_shot_label

        def _segment_row(seg: Any) -> dict[str, Any]:
            number = int(getattr(seg, "shotNumber", 0) or 0)
            return {
                "id": str(getattr(seg, "id", "") or ""),
                "order": int(getattr(seg, "order", 0) or 0),
                "shotNumber": number,
                "shotLabel": creator_shot_label(number),
                "compositionRole": str(getattr(seg, "compositionRole", "") or "generated"),
                "sourceSegmentId": str(getattr(seg, "sourceSegmentId", "") or ""),
                "origin": str(getattr(seg, "origin", "") or "generated"),
                "durationSec": float(getattr(seg, "durationSec", 0.0) or 0.0),
                "requestedDurationSec": float(getattr(seg, "requestedDurationSec", 0.0) or 0.0),
                "status": str(getattr(seg, "status", "") or ""),
                "assetId": getattr(seg, "assetId", None),
                "generatorId": getattr(seg, "generatorId", None),
                "timedPrompt": str(getattr(seg, "timedPrompt", "") or ""),
                "error": getattr(seg, "error", None),
            }

        segment_rows = [_segment_row(seg) for seg in ordered_segments]
        active_segment_prompt = str(getattr(segment, "timedPrompt", "") or "") if segment is not None else ""
        shot_timed_prompt = str(getattr(shot, "timedPrompt", "") or "") if shot is not None else ""

        shots_summary: list[dict[str, Any]] = []
        for candidate_shot in sorted(film.shots, key=lambda s: int(getattr(s, "order", 0) or 0)):
            candidate_state = getattr(candidate_shot, "state", None)
            candidate_segments = sorted(
                getattr(candidate_shot, "segments", None) or [],
                key=lambda seg: int(getattr(seg, "order", 0) or 0),
            )
            shots_summary.append(
                {
                    "id": str(getattr(candidate_shot, "id", "") or ""),
                    "name": str(getattr(candidate_shot, "name", "") or ""),
                    "order": int(getattr(candidate_shot, "order", 0) or 0),
                    "durationSec": float(getattr(candidate_shot, "durationSec", 0.0) or 0.0),
                    "status": str(getattr(candidate_shot, "status", "") or ""),
                    "modelId": getattr(candidate_state, "modelId", None) if candidate_state is not None else None,
                    "segmentCount": len(candidate_segments),
                    "segmentStatuses": [str(getattr(seg, "status", "") or "") for seg in candidate_segments],
                    "stitchAssetId": getattr(candidate_state, "stitchAssetId", None) if candidate_state is not None else None,
                    "stitchStatus": str(getattr(candidate_state, "stitchStatus", "") or "") if candidate_state is not None else "",
                    "dialogueAuthority": str(getattr(candidate_state, "dialogueAuthority", "") or "native_model") if candidate_state is not None else "native_model",
                    "spokenLanguage": str(getattr(candidate_state, "spokenLanguage", "") or "en") if candidate_state is not None else "en",
                    "active": bool(shot is not None and getattr(candidate_shot, "id", None) == getattr(shot, "id", None)),
                }
            )

        current_take = None
        if shot is not None and state is not None:
            current_take = {
                "shotId": str(getattr(shot, "id", "") or ""),
                "shotName": str(getattr(shot, "name", "") or ""),
                "stitchAssetId": getattr(state, "stitchAssetId", None),
                "stitchStatus": str(getattr(state, "stitchStatus", "") or ""),
                "stitchError": getattr(state, "stitchError", None),
                "takeId": getattr(state, "stitchAssetId", None),
                "status": str(getattr(shot, "status", "") or ""),
            }

        prompt_block = {
            "timedPrompt": shot_timed_prompt,
            "modelPrompt": str(getattr(state, "modelPrompt", "") or "") if state is not None else "",
            "promptHistory": list(getattr(state, "promptHistory", None) or []) if state is not None else [],
            "activeSegmentPrompt": active_segment_prompt,
            "segments": [
                {
                    "id": row["id"],
                    "order": row["order"],
                    "timedPrompt": row["timedPrompt"],
                    "durationSec": row["durationSec"],
                }
                for row in segment_rows
            ],
        }
        status_block = {
            "shotStatus": str(getattr(shot, "status", "") or "") if shot is not None else "",
            "segments": [
                {
                    "id": row["id"],
                    "order": row["order"],
                    "status": row["status"],
                    "assetId": row["assetId"],
                    "error": row["error"],
                }
                for row in segment_rows
            ],
        }

        # Mirror into the existing keys - only where the V2 document is truth.
        active_scene = grounding.get("activeScene") or {}
        mirrored_refs = [
            {
                "bindingId": ref["id"],
                "promptName": ref["label"] or ref["tag"],
                "type": ref["type"],
                "tag": ref["tag"],
                "assetId": ref["assetId"],
            }
            for ref in references
        ]
        mirrored_env = next((ref for ref in mirrored_refs if ref.get("type") == "environment"), None)
        current_timed = None
        if segment is not None:
            prior_seconds = sum(
                float(getattr(seg, "durationSec", 0.0) or 0.0)
                for seg in ordered_segments
                if int(getattr(seg, "order", 0) or 0) < int(getattr(segment, "order", 0) or 0)
            )
            active_number = int(getattr(segment, "shotNumber", 0) or 0)
            current_timed = {
                "id": str(getattr(segment, "id", "") or ""),
                "start": round(shot_start + prior_seconds, 3),
                "length": float(getattr(segment, "durationSec", 0.0) or 0.0),
                "text": active_segment_prompt or shot_timed_prompt,
                "shotNumber": active_number,
                "shotLabel": creator_shot_label(active_number),
                "referenceBindingIds": [],
                "resolved": [],
            }

        timeline_v2 = {
            "source": "filmTimeline",
            "version": getattr(film, "version", None),
            "sceneId": scene_id,
            "sceneName": str(getattr(film, "name", "") or "") or active_scene.get("name"),
            "activeShotId": str(getattr(shot, "id", "") or "") if shot is not None else None,
            "activeShotName": str(getattr(shot, "name", "") or "") if shot is not None else None,
            "generatorId": generator_id,
            "aspectRatio": scene_aspect,
            "resolvedAspect": canvas.get("aspect"),
            "megapixelTier": megapixel_tier,
            "h3Resolution": dict(h3_resolution) if isinstance(h3_resolution, dict) else None,
            "legalCanvas": legal_canvas,
            "durationSec": shot_duration,
            "segmentDurationsSec": [row["durationSec"] for row in segment_rows],
            "references": references,
            "prompt": prompt_block,
            "status": status_block,
            "shots": shots_summary,
            "shotIdentity": {
                "highestShotNumber": int(getattr(film, "highestShotNumber", 0) or 0),
                "nextShotNumber": int(getattr(film, "highestShotNumber", 0) or 0) + 1,
                "segments": [
                    _segment_row(seg)
                    for candidate in sorted(film.shots, key=lambda item: int(getattr(item, "order", 0) or 0))
                    for seg in sorted(getattr(candidate, "segments", None) or [], key=lambda item: int(getattr(item, "order", 0) or 0))
                ],
            },
            "currentTake": current_take,
            "publishedAssetId": getattr(film, "publishedAssetId", None),
            "dialogueAuthority": str(getattr(state, "dialogueAuthority", "") or "native_model") if state is not None else "native_model",
            "spokenLanguage": str(getattr(state, "spokenLanguage", "") or "en") if state is not None else "en",
        }

        return {
            "bound": True,
            "sessionStatus": "bound",
            "workspace": grounding.get("workspace") or workspace or "timeline",
            "project": grounding.get("project"),
            "activeScene": grounding.get("activeScene"),
            "activeSceneId": scene_id,
            "hasTimelineSnapshot": True,
            "playheadSec": playhead,
            "selectedBatchId": (selected_batch_id or "").strip() or None,
            "generatorId": generator_id,
            "generatorReadiness": None,
            "batches": [],
            "batchApproval": {"approved": 0, "draft": 0, "total": 0},
            "promptSegments": segment_rows,
            "referencedInShot": mirrored_refs,
            "environment": mirrored_env,
            "lipsyncClips": [],
            "incomingBridge": None,
            "scenePrompt": scene_prompt,
            "sceneSummary": scene_summary,
            "currentTimedPrompt": current_timed,
            "currentTake": current_take,
            "sceneTakes": [],
            "currentSceneTake": None,
            "publishedTake": (
                {"id": None, "label": None, "publishedAssetId": getattr(film, "publishedAssetId", None)}
                if getattr(film, "publishedAssetId", None)
                else None
            ),
            "characters": grounding.get("characters") or [],
            "voiceAssignments": grounding.get("voiceAssignments") or [],
            "timelineV2": timeline_v2,
            "grounding": grounding,
        }
    except Exception:
        return None


def build_timeline_v2_read_block(
    db: Session,
    project_id: str | None,
    scene_id: str | None,
    *,
    playhead_sec: float | None = None,
) -> dict[str, Any] | None:
    """Additive Timeline V2 block for timeline.* read tools.

    Returns None when the scene does not own a filmTimeline document, so
    non-V2 callers see byte-identical output. Reuses the same observation
    builder as the grounded active-scene snapshot.
    """
    if not project_id or not scene_id:
        return None
    snapshot = _build_film_timeline_v2_snapshot(
        db,
        str(project_id),
        str(scene_id),
        grounding={},
        workspace=None,
        playhead_sec=playhead_sec,
        selected_batch_id=None,
    )
    return (snapshot or {}).get("timelineV2")


def build_active_timeline_scene_snapshot(
    db: Session,
    project_id: str | None,
    scene_id: str | None,
    *,
    workspace: str | None = None,
    playhead_sec: float | None = None,
    selected_batch_id: str | None = None,
) -> dict[str, Any]:
    """Read-only join of W46 master + director + lipsync + voices + bridges."""
    from .project_grounding import build_project_grounding_snapshot

    grounding = build_project_grounding_snapshot(db, project_id, scene_id, workspace=workspace)
    empty = {
        "bound": bool(grounding.get("bound")),
        "sessionStatus": grounding.get("sessionStatus"),
        "workspace": grounding.get("workspace") or workspace,
        "project": grounding.get("project"),
        "activeScene": grounding.get("activeScene"),
        "hasTimelineSnapshot": False,
        "batches": [],
        "batchApproval": {"approved": 0, "draft": 0, "total": 0},
        "promptSegments": [],
        "referencedInShot": [],
        "environment": None,
        "lipsyncClips": [],
        "generatorId": None,
        "generatorReadiness": None,
        "incomingBridge": None,
        "scenePrompt": "",
        "sceneSummary": "",
        "currentTimedPrompt": None,
        "currentTake": None,
        "sceneTakes": [],
        "currentSceneTake": None,
        "publishedTake": None,
        "grounding": grounding,
    }
    if not project_id or not scene_id or not grounding.get("bound"):
        return empty
    # V2-FIRST (additive): the live Timeline owner is the filmTimeline document.
    # Only a genuinely V2 scene takes this branch; every other scene falls
    # through to the W46 path below completely unchanged.
    try:
        v2_snapshot = _build_film_timeline_v2_snapshot(
            db,
            project_id,
            scene_id,
            grounding=grounding,
            workspace=workspace,
            playhead_sec=playhead_sec,
            selected_batch_id=selected_batch_id,
        )
    except Exception:
        v2_snapshot = None
    if v2_snapshot is not None:
        return v2_snapshot
    try:
        from ..director_timeline_w46.generation.prompt_token_bindings import (
            hydrate_timeline_prompt_tokens,
            load_scene_reference_catalog,
        )
        from ..director_timeline_w46.service import load_timeline_bundle

        bundle = load_timeline_bundle(db, project_id, scene_id)
        if not bundle.get("ok"):
            return empty
        master = _dump(bundle.get("master"))
        catalog = load_scene_reference_catalog(db, project_id, scene_id)
        hydrate_timeline_prompt_tokens(
            None, catalog, db=db, project_id=project_id, master=bundle.get("master")
        )
        batches_raw = master.get("batchBlocks") or []
        batches: list[dict[str, Any]] = []
        approved = 0
        draft = 0
        for batch in batches_raw:
            clip = batch.get("approvedClip") or {}
            has_approved = bool(clip.get("assetId") or clip.get("asset_id"))
            status = str(batch.get("status") or "Draft")
            if has_approved:
                approved += 1
            else:
                draft += 1
            bridge = batch.get("continuityBridge") or {}
            batches.append(
                {
                    "id": str(batch.get("id") or ""),
                    "label": str(batch.get("label") or "Batch"),
                    "order": int(batch.get("order") or 0),
                    "status": status,
                    "approved": has_approved,
                    "approvedClipAssetId": clip.get("assetId") or clip.get("asset_id"),
                    "generatorId": batch.get("generatorId"),
                    "currentTakeId": batch.get("currentTakeId") or batch.get("current_take_id"),
                    "currentTakeAssetId": batch.get("currentTakeAssetId") or batch.get("current_take_asset_id"),
                    "activeTakeId": batch.get("activeTakeId") or batch.get("active_take_id"),
                    "bridge": {
                        "status": bridge.get("status"),
                        "strategy": bridge.get("continuityStrategy") or bridge.get("strategy"),
                        "lastFrameAssetId": bridge.get("lastFrameAssetId"),
                        "sourceBatchId": bridge.get("sourceBatchId") or bridge.get("predecessorBatchId"),
                    }
                    if bridge
                    else None,
                }
            )
        scene_gen = master.get("sceneGeneratorId") or (batches[0]["generatorId"] if batches else None)
        readiness = None

        playhead = float(playhead_sec if playhead_sec is not None else bundle.get("playhead") or 0.0)
        selected = (selected_batch_id or "").strip() or None
        prompt_rows: list[dict[str, Any]] = []
        referenced: list[dict[str, Any]] = []
        environment: dict[str, Any] | None = None
        seen_ref: set[str] = set()
        for batch in master.get("batchBlocks") or []:
            for seg in batch.get("promptSegments") or []:
                names = seg.get("referenceNameBindings") or seg.get("reference_name_bindings") or []
                ids = seg.get("referenceBindingIds") or seg.get("reference_binding_ids") or []
                resolved = []
                for row in names:
                    rec = row if isinstance(row, dict) else {}
                    bid = str(rec.get("binding_id") or rec.get("bindingId") or "").strip()
                    typ = str(rec.get("type") or "character")
                    item = {
                        "bindingId": bid,
                        "promptName": rec.get("prompt_name") or rec.get("promptName"),
                        "type": typ,
                        "tag": rec.get("tag"),
                    }
                    resolved.append(item)
                    if bid and bid not in seen_ref:
                        seen_ref.add(bid)
                        referenced.append(item)
                        if typ == "environment" and environment is None:
                            environment = item
                prompt_rows.append(
                    {
                        "id": str(seg.get("id") or ""),
                        "start": float(seg.get("start") or 0.0),
                        "length": float(seg.get("length") or 0.0),
                        "text": str(seg.get("text") or ""),
                        "referenceBindingIds": ids,
                        "resolved": resolved,
                    }
                )

        lips: list[dict[str, Any]] = []
        lipsync_obj = bundle.get("lipsyncTracks")
        tracks = []
        if lipsync_obj is not None:
            dumped = _dump(lipsync_obj)
            tracks = dumped.get("tracks") or [] if isinstance(dumped, dict) else []
        for track in tracks:
            for clip in track.get("clips") or []:
                lips.append(
                    {
                        "clipId": clip.get("id"),
                        "trackId": track.get("id"),
                        "audioAssetId": clip.get("audio_asset_id") or track.get("audio_asset_id"),
                        "speakerBindingId": clip.get("speaker_binding_id"),
                        "characterId": clip.get("character_id") or track.get("character_id"),
                        "characterName": clip.get("character_name") or track.get("character_name"),
                    }
                )

        incoming = None
        for batch in batches:
            if batch.get("bridge") and batch["bridge"].get("lastFrameAssetId"):
                incoming = batch["bridge"]
                break

        scene_prompt = ""
        scene_summary = ""
        try:
            from ..db import Scene

            scene_row = db.get(Scene, scene_id)
            if scene_row is not None:
                scene_prompt = str(getattr(scene_row, "prompt", "") or "")
                scene_summary = str(getattr(scene_row, "summary", "") or "")
        except Exception:
            scene_prompt = ""
            scene_summary = ""

        current_timed: dict[str, Any] | None = None
        for row in prompt_rows:
            start = float(row.get("start") or 0.0)
            end = start + float(row.get("length") or 0.0)
            if start <= playhead < end or (end <= start and abs(start - playhead) < 0.05):
                current_timed = row
                break
        if current_timed is None and prompt_rows:
            current_timed = min(prompt_rows, key=lambda row: abs(float(row.get("start") or 0.0) - playhead))

        target_batch = next((batch for batch in batches if selected and batch.get("id") == selected), None)
        if target_batch is None:
            target_batch = next(
                (
                    batch
                    for batch in batches
                    if batch.get("currentTakeId") or batch.get("currentTakeAssetId") or batch.get("approvedClipAssetId")
                ),
                batches[0] if batches else None,
            )
        current_take = None
        if target_batch:
            take_id = (
                target_batch.get("currentTakeId")
                or target_batch.get("activeTakeId")
                or target_batch.get("approvedClipAssetId")
            )
            current_take = {
                "batchId": target_batch.get("id"),
                "batchLabel": target_batch.get("label"),
                "status": target_batch.get("status"),
                "currentTakeId": target_batch.get("currentTakeId"),
                "currentTakeAssetId": target_batch.get("currentTakeAssetId"),
                "activeTakeId": target_batch.get("activeTakeId"),
                "approvedClipAssetId": target_batch.get("approvedClipAssetId"),
                "takeId": take_id,
            }

        scene_takes_raw = master.get("sceneTakes") or []
        scene_takes: list[dict[str, Any]] = []
        for row in scene_takes_raw:
            scene_takes.append(
                {
                    "id": row.get("id"),
                    "label": row.get("label"),
                    "displayLabel": f"Take {row.get('label')}" if row.get("label") and not str(row.get("label")).lower().startswith("take ") else row.get("label"),
                    "status": row.get("status"),
                    "current": row.get("id") == master.get("currentSceneTakeId"),
                    "resultAssetId": row.get("resultAssetId"),
                    "quality": row.get("quality"),
                    "batchCount": len(row.get("batches") or []),
                }
            )
        current_scene_take = next((t for t in scene_takes if t.get("current")), scene_takes[0] if scene_takes else None)
        pub = master.get("scenePublish") or {}
        published_take = next((t for t in scene_takes if t.get("id") and t["id"] == pub.get("takeId")), None)
        if current_scene_take:
            current_take = {
                **(current_take or {}),
                "sceneTakeId": current_scene_take.get("id"),
                "sceneTakeLabel": current_scene_take.get("displayLabel") or current_scene_take.get("label"),
                "takeId": current_scene_take.get("id") or (current_take or {}).get("takeId"),
            }

        return {
            "bound": True,
            "sessionStatus": "bound",
            "workspace": grounding.get("workspace") or workspace or "timeline",
            "project": grounding.get("project"),
            "activeScene": grounding.get("activeScene"),
            "hasTimelineSnapshot": True,
            "playheadSec": playhead,
            "selectedBatchId": selected,
            "generatorId": scene_gen,
            "generatorReadiness": readiness,
            "batches": batches,
            "batchApproval": {"approved": approved, "draft": draft, "total": len(batches)},
            "promptSegments": prompt_rows,
            "referencedInShot": referenced,
            "environment": environment,
            "lipsyncClips": lips,
            "incomingBridge": incoming,
            "scenePrompt": scene_prompt,
            "sceneSummary": scene_summary,
            "currentTimedPrompt": current_timed,
            "currentTake": current_take,
            "sceneTakes": scene_takes,
            "currentSceneTake": current_scene_take,
            "publishedTake": published_take
            or (
                {
                    "id": pub.get("takeId"),
                    "label": pub.get("takeLabel"),
                    "publishedAssetId": pub.get("publishedAssetId"),
                }
                if pub.get("takeId") or pub.get("takeLabel")
                else None
            ),
            "characters": grounding.get("characters") or [],
            "voiceAssignments": grounding.get("voiceAssignments") or [],
            "grounding": grounding,
        }
    except Exception:
        return empty


def render_timeline_snapshot_block(snap: dict[str, Any]) -> str:
    if not snap.get("hasTimelineSnapshot"):
        return ""
    scene = snap.get("activeScene") or {}
    lines = [
        "ACTIVE TIMELINE SCENE SNAPSHOT",
        f"Scene: {scene.get('name') or 'unselected'}",
        f"Generator: {snap.get('generatorId') or 'none'} ({snap.get('generatorReadiness') or 'unknown'})",
    ]
    counts = snap.get("batchApproval") or {}
    lines.append(
        f"Batches: {counts.get('approved', 0)} Approved / {counts.get('draft', 0)} Draft "
        f"(authority: approvedClip on this scene)"
    )
    refs = snap.get("referencedInShot") or []
    if refs:
        lines.append("Referenced in this shot: " + ", ".join(
            f"{r.get('tag') or r.get('promptName')} ({r.get('type')})" for r in refs
        ))
    else:
        lines.append("Referenced in this shot: none bound")
    env = snap.get("environment")
    lines.append(f"Environment: {(env or {}).get('promptName') or (env or {}).get('tag') or 'none assigned'}")
    scene_prompt = _clip(str(snap.get("scenePrompt") or ""), _PROMPT_CLIP_CHARS)
    if scene_prompt:
        lines.append(f"Scene Prompt: {scene_prompt}")
    scene_summary = _clip(str(snap.get("sceneSummary") or ""), _SUMMARY_CLIP_CHARS)
    if scene_summary:
        lines.append(f"What happens: {scene_summary}")
    timed = snap.get("currentTimedPrompt") or {}
    timed_text = _clip(str(timed.get("text") or ""), _PROMPT_CLIP_CHARS)
    if timed_text:
        start = timed.get("start")
        label = f"Timed Prompt @ {float(start):.1f}s" if start is not None else "Timed Prompt"
        lines.append(f"{label}: {timed_text}")
    take = snap.get("currentSceneTake") or snap.get("currentTake") or {}
    take_label = take.get("sceneTakeLabel") or take.get("displayLabel") or take.get("label") or take.get("takeId")
    if take_label:
        lines.append(f"Current whole-scene Take: {take_label}")
    published = snap.get("publishedTake") or {}
    if published.get("label") or published.get("id"):
        lines.append(f"Published Take: {published.get('label') or published.get('id')}")
    takes = snap.get("sceneTakes") or []
    if takes:
        bits = []
        for row in takes:
            mark = " current" if row.get("current") else ""
            bits.append(f"{row.get('displayLabel') or row.get('label')} ({row.get('status')}{mark})")
        lines.append("Scene Takes: " + ", ".join(bits))
    return "\n".join(lines)
