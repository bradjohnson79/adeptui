"""Co-Director tools for Audio Studio — explicit preview, approval, and placement only."""

from __future__ import annotations

from typing import Any

from ....audio_studio import service as audio_service
from ....audio_studio import store as audio_store
from ....audio_studio.provider_resolver import resolve_execution
from ....db import Asset, Scene
from ...errors import TOOL_ARGUMENTS_INVALID, TOOL_TARGET_NOT_FOUND, CoDirectorError
from ..definitions import ToolContext, ToolPreview


def _argument_error(message: str, **details: Any) -> CoDirectorError:
    return CoDirectorError(
        TOOL_ARGUMENTS_INVALID,
        message,
        details=details,
        recoverable=True,
        recommended_action="retry",
    )


def _target_not_found(message: str, **details: Any) -> CoDirectorError:
    return CoDirectorError(
        TOOL_TARGET_NOT_FOUND,
        message,
        details=details,
        recoverable=False,
        recommended_action="none",
    )


def _require_text(args: dict[str, Any], key: str) -> str:
    value = str(args.get(key) or "").strip()
    if not value:
        raise _argument_error(f"{key} is required.", parameter=key)
    return value


def _optional_text(args: dict[str, Any], key: str) -> str | None:
    value = str(args.get(key) or "").strip()
    return value or None


def _require_batch(project_id: str, batch_id: str) -> dict[str, Any]:
    batch = audio_store.get_batch(project_id, batch_id)
    if not batch:
        raise _target_not_found("Audio batch not found in this project.", batchId=batch_id, projectId=project_id)
    return batch


def _require_candidate(batch: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    for candidate in batch.get("candidates") or []:
        if candidate.get("id") == candidate_id:
            return candidate
    raise _target_not_found(
        "Audio candidate not found in this batch.",
        batchId=batch.get("id"),
        candidateId=candidate_id,
    )


def _kind_runtime(kind: str) -> str:
    return "music" if kind == "music" else "sfx"


def _kind_defaults(kind: str) -> tuple[float, int]:
    # Match Audio Studio service clamps (music/ambience ≤20s) so previews are honest.
    if kind == "music":
        return 20.0, 3
    if kind == "ambience":
        return 12.0, 3
    return 4.0, 3


def _parse_mood(args: dict[str, Any]) -> list[str]:
    raw = str(args.get("mood") or "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()][:6]


def _build_brief(ctx: ToolContext, args: dict[str, Any], *, kind: str) -> dict[str, Any]:
    prompt = _require_text(args, "prompt")
    duration_default, _ = _kind_defaults(kind)
    brief: dict[str, Any] = {
        "prompt": prompt,
        "scene_id": _optional_text(args, "sceneId") or ctx.scene_id,
        "duration_seconds": float(args.get("durationSec") or duration_default),
        "mood": _parse_mood(args),
    }
    genre = _optional_text(args, "genre")
    if genre:
        brief["genre"] = genre
    notes = _optional_text(args, "notes")
    if notes:
        brief["notes"] = notes
    category = _optional_text(args, "category")
    if category:
        brief["category"] = category
    elif kind == "ambience":
        brief["category"] = "ambience"
    elif kind == "sfx":
        brief["category"] = "sfx"
    loop_required = args.get("loopRequired")
    if loop_required is not None:
        brief["loop_required"] = bool(loop_required)
    elif kind == "ambience":
        brief["loop_required"] = True
    return brief


def _candidate_count(args: dict[str, Any], *, kind: str) -> int:
    _, default_count = _kind_defaults(kind)
    raw = args.get("candidateCount")
    if raw is None:
        return default_count
    count = int(raw)
    if count < 1 or count > 6:
        raise _argument_error("candidateCount must be between 1 and 6.", candidateCount=count)
    return count


def _category_from_value(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "ambience" in text or "ambient" in text or "atmosphere" in text:
        return "ambience"
    if "sfx" in text or "sound" in text or "foley" in text:
        return "sfx"
    if "dialogue" in text or "voice" in text or "speech" in text:
        return "dialogue"
    if "music" in text:
        return "music"
    return ""


def _category_for_item(item: dict[str, Any]) -> str:
    for key in ("category", "libraryKey", "tag", "name", "filename", "role"):
        category = _category_from_value(item.get(key))
        if category:
            return category
    return "audio"


def _filter_library(items: list[dict[str, Any]], *, category: str | None, limit: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    wanted = (_category_from_value(category) if category else "") or None
    for item in items:
        entry = dict(item)
        entry["category"] = _category_for_item(entry)
        if wanted and entry["category"] != wanted:
            continue
        normalized.append(entry)
    return normalized[:limit]


def _summarize_batch(batch: dict[str, Any]) -> dict[str, Any]:
    candidates = list(batch.get("candidates") or [])
    by_status: dict[str, int] = {}
    selected_id = None
    approved_id = None
    for candidate in candidates:
        status = str(candidate.get("status") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        if status == "selected":
            selected_id = candidate.get("id")
        if status == "approved":
            approved_id = candidate.get("id")
    return {
        "batchId": batch.get("id"),
        "kind": batch.get("method"),
        "createdAt": batch.get("created_at"),
        "candidateCount": len(candidates),
        "statusCounts": by_status,
        "selectedCandidateId": selected_id,
        "approvedCandidateId": approved_id,
        "brief": batch.get("brief_snapshot") or {},
        "candidates": candidates,
    }


def _preview_payload(ctx: ToolContext, args: dict[str, Any], *, kind: str) -> dict[str, Any]:
    brief = _build_brief(ctx, args, kind=kind)
    preferred_provider = _optional_text(args, "preferredProvider")
    allow_provider_switch = bool(args.get("allowProviderSwitch"))
    allow_cpu_fallback = bool(args.get("allowCpuFallback"))
    resolution = resolve_execution(
        _kind_runtime(kind),
        preferred_provider=preferred_provider,
        allow_switch=allow_provider_switch,
        allow_cpu_fallback=allow_cpu_fallback,
    )
    rec = resolution.get("recommendation") or {}
    candidate_count = _candidate_count(args, kind=kind)
    duration = float(brief.get("duration_seconds") or 0.0)
    label = "music tracks" if kind == "music" else "ambience beds" if kind == "ambience" else "sound effects"
    return {
        "ok": True,
        "kind": kind,
        "summary": f"Preview {candidate_count} {label} for the current project.",
        "projectId": ctx.project_id,
        "brief": brief,
        "candidateCount": candidate_count,
        "durationSeconds": duration,
        "providerResolution": resolution,
        "recommendedRuntime": rec.get("runtime"),
        "recommendedProvider": rec.get("provider"),
        "recommendedMode": rec.get("mode"),
        "gpuRequired": True,
        "cuda": rec.get("cuda"),
        "providerPolicy": "Provider switches stay off unless allowProviderSwitch=true.",
        "cpuPolicy": "CPU fallback stays blocked unless allowCpuFallback=true with explicit approval.",
        "allowProviderSwitch": allow_provider_switch,
        "allowCpuFallback": allow_cpu_fallback,
        "preferredProvider": preferred_provider,
        "asyncGeneration": True,
        "mock": False,
    }


def _preview_to_tool(ctx: ToolContext, args: dict[str, Any], *, kind: str) -> ToolPreview:
    payload = _preview_payload(ctx, args, kind=kind)
    resolution = payload.get("providerResolution") or {}
    recommendation = resolution.get("recommendation") or {}
    mode = str(recommendation.get("mode") or "unavailable")
    lines = [
        str(payload.get("summary") or ""),
        f"Prompt: {payload['brief'].get('prompt')}",
        f"Duration: {payload.get('durationSeconds')}s • Candidates: {payload.get('candidateCount')}",
        f"Runtime: {recommendation.get('runtime') or 'unavailable'} • mode={mode}",
        f"GPU/CUDA: {recommendation.get('cuda')} • device={recommendation.get('device') or 'n/a'}",
        "Starts async after approval — poll audio.compare_candidates; cancel with audio.cancel_batch.",
        "Provider switches stay off unless allowProviderSwitch=true.",
        "CPU fallback stays blocked unless allowCpuFallback=true.",
        "Applies only after explicit approval.",
    ]
    if kind == "ambience":
        lines.insert(2, "Loop-first ambience bed. Separate from Foley / one-shot SFX.")
    warnings = [
        "No silent provider switch.",
        "No silent CPU fallback.",
        "No automatic mix suggestions or auto-placement.",
    ]
    if mode == "blocked_cpu":
        warnings.append("Local runtime is CPU-only — approve will fail unless allowCpuFallback=true.")
    return ToolPreview(
        summary=str(payload.get("summary") or ""),
        lines=lines,
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=warnings,
    )


def _start_async_generate(ctx: ToolContext, args: dict[str, Any], *, kind: str) -> dict[str, Any]:
    """Approval apply path: queue batch + background worker (never block the approve request)."""
    import threading

    batch = audio_service.begin_generate_batch(
        ctx.project_id,
        kind=kind,
        brief=_build_brief(ctx, args, kind=kind),
        candidate_count=_candidate_count(args, kind=kind),
        preferred_provider=_optional_text(args, "preferredProvider"),
        allow_provider_switch=bool(args.get("allowProviderSwitch")),
        allow_cpu_fallback=bool(args.get("allowCpuFallback")),
    )
    thread = threading.Thread(
        target=audio_service.run_generate_batch_job,
        args=(ctx.project_id, batch["id"]),
        daemon=True,
        name=f"audio-studio-{kind}-{str(batch.get('id') or '')[:8]}",
    )
    thread.start()
    return {
        "ok": True,
        "async": True,
        "status": "queued",
        "batchId": batch.get("id"),
        "batch": batch,
        "workspaceUrl": f"/project/{ctx.project_id}?workspace=audiostudio",
        "uiAction": "open_audio_studio",
        "projectId": ctx.project_id,
        "pollTool": "audio.compare_candidates",
        "cancelTool": "audio.cancel_batch",
        "note": (
            "Generation started in the background with distinct seeds/variations. "
            "Poll audio.compare_candidates or open Audio Studio. "
            "Cancel with audio.cancel_batch to terminate GPU workers at source."
        ),
        "mock": False,
        "_evidence": {"source": "audio_studio.service.begin_generate_batch + background thread"},
    }


def _resolve_asset_for_placement(ctx: ToolContext, args: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    asset_id = _optional_text(args, "assetId")
    batch_id = _optional_text(args, "batchId")
    candidate_id = _optional_text(args, "candidateId")
    if asset_id:
        asset = ctx.db.get(Asset, asset_id)
        if not asset or asset.project_id != ctx.project_id:
            raise _target_not_found("Audio asset not found in this project.", assetId=asset_id, projectId=ctx.project_id)
        return asset_id, None
    if not batch_id or not candidate_id:
        raise _argument_error(
            "Provide assetId or the batchId/candidateId pair.",
            assetId=asset_id,
            batchId=batch_id,
            candidateId=candidate_id,
        )
    batch = _require_batch(ctx.project_id, batch_id)
    candidate = _require_candidate(batch, candidate_id)
    resolved = str(candidate.get("asset_id") or "").strip()
    if not resolved:
        raise _target_not_found(
            "The selected candidate does not have a registered audio asset yet.",
            batchId=batch_id,
            candidateId=candidate_id,
        )
    if str(candidate.get("status") or "") != "approved":
        raise _argument_error(
            "Candidate must be approved before placement when using batchId/candidateId.",
            batchId=batch_id,
            candidateId=candidate_id,
            status=candidate.get("status"),
        )
    return resolved, candidate


def _place_category(args: dict[str, Any], candidate: dict[str, Any] | None) -> str:
    requested = _category_from_value(args.get("category"))
    if requested in {"music", "sfx", "ambience"}:
        return requested
    if candidate:
        batch_kind = _category_from_value(candidate.get("summary")) or _category_from_value(candidate.get("name"))
        if batch_kind in {"music", "sfx", "ambience"}:
            return batch_kind
    return "music"


async def status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    workspace = audio_service.workspace(ctx.db, ctx.project_id)
    mix = workspace.get("mix") or {}
    clips = mix.get("clips") or {}
    library = list(workspace.get("library") or [])
    return {
        "ok": True,
        "projectId": ctx.project_id,
        "tabs": workspace.get("tabs") or [],
        "providers": workspace.get("providers") or {},
        "latestDraft": workspace.get("draft") or {},
        "batchCount": len(workspace.get("batches") or []),
        "mixClipCount": len(clips),
        "libraryCount": len(library),
        "libraryPreview": library[:8],
        "mock": False,
        "_evidence": {"source": "audio_studio.service.workspace"},
    }


async def library(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    workspace = audio_service.workspace(ctx.db, ctx.project_id)
    limit = int(args.get("limit") or 20)
    limit = max(1, min(limit, 100))
    category = _optional_text(args, "category")
    items = _filter_library(list(workspace.get("library") or []), category=category, limit=limit)
    categories = sorted({str(item.get("category") or "audio") for item in items})
    return {
        "ok": True,
        "projectId": ctx.project_id,
        "count": len(items),
        "category": category,
        "categories": categories,
        "items": items,
        "mock": False,
        "_evidence": {"source": "audio_studio.service.workspace"},
    }


async def scene_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id = _optional_text(args, "sceneId") or ctx.scene_id
    if not scene_id:
        return {
            "ok": True,
            "projectId": ctx.project_id,
            "sceneId": None,
            "scene": None,
            "mixClipCount": len((audio_store.get_mix(ctx.project_id).get("clips") or {}).keys()),
            "sceneClipCount": 0,
            "sceneAudioAsset": None,
            "note": "No active scene was provided, so scene-specific audio cannot be summarized yet.",
            "mock": False,
        }
    scene = ctx.db.get(Scene, scene_id)
    if not scene or scene.project_id != ctx.project_id:
        raise _target_not_found("Scene not found in this project.", sceneId=scene_id, projectId=ctx.project_id)
    mix = audio_store.get_mix(ctx.project_id)
    clips = list((mix.get("clips") or {}).values())
    scene_clips = [
        clip
        for clip in clips
        if str(clip.get("scene_id") or clip.get("sceneId") or "").strip() == scene_id
    ]
    scene_audio_asset = None
    if scene.audio_asset_id:
        asset = ctx.db.get(Asset, scene.audio_asset_id)
        if asset and asset.project_id == ctx.project_id:
            scene_audio_asset = {
                "assetId": asset.id,
                "filename": asset.filename,
                "path": asset.path,
                "tag": asset.tag,
            }
    return {
        "ok": True,
        "projectId": ctx.project_id,
        "sceneId": scene.id,
        "scene": {
            "id": scene.id,
            "name": scene.name,
            "summary": scene.summary,
            "durationSec": scene.duration_sec,
            "audioAssetId": scene.audio_asset_id,
        },
        "sceneAudioAsset": scene_audio_asset,
        "mixClipCount": len(clips),
        "sceneClipCount": len(scene_clips),
        "sceneClips": scene_clips,
        "note": (
            "Audio mix clips without scene_id metadata are not attributed to this scene."
            if not scene_clips and clips
            else None
        ),
        "mock": False,
        "_evidence": {"source": "audio_studio.store + scenes"},
    }


async def preview_music(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return _preview_payload(ctx, args, kind="music")


async def preview_sfx(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return _preview_payload(ctx, args, kind="sfx")


async def preview_ambience(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return _preview_payload(ctx, args, kind="ambience")


async def compare_candidates(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    batch_id = _require_text(args, "batchId")
    batch = _require_batch(ctx.project_id, batch_id)
    return {
        "ok": True,
        "projectId": ctx.project_id,
        "batch": _summarize_batch(batch),
        "mock": False,
        "_evidence": {"source": "audio_studio.store.get_batch"},
    }


async def get_batch(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    batch_id = _require_text(args, "batchId")
    batch = audio_service.get_batch(ctx.project_id, batch_id)
    return {
        "ok": True,
        "projectId": ctx.project_id,
        "batch": batch,
        "summary": _summarize_batch(batch),
        "mock": False,
        "_evidence": {"source": "audio_studio.service.get_batch"},
    }


async def open_studio(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "projectId": ctx.project_id,
        "uiAction": "open_audio_studio",
        "workspaceUrl": f"/project/{ctx.project_id}?workspace=audiostudio",
        "_evidence": {"source": "audio_studio.ui"},
    }


def preview_generate_music(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_to_tool(ctx, args, kind="music")


def apply_generate_music(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return _start_async_generate(ctx, args, kind="music")


def preview_generate_sfx(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_to_tool(ctx, args, kind="sfx")


def apply_generate_sfx(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return _start_async_generate(ctx, args, kind="sfx")


def preview_generate_ambience(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return _preview_to_tool(ctx, args, kind="ambience")


def apply_generate_ambience(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return _start_async_generate(ctx, args, kind="ambience")


def preview_cancel_batch(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    batch_id = _require_text(args, "batchId")
    batch = _require_batch(ctx.project_id, batch_id)
    return ToolPreview(
        summary="Cancel an Audio Studio batch and terminate GPU workers at source.",
        lines=[
            f"Batch: {batch_id}",
            f"Current status: {batch.get('status') or 'unknown'}",
            "Kills ACE-Step / MMAudio worker process trees for this batch.",
            "Emergency GPU/RAM safety — no silent continue.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=["In-flight candidates will be marked cancelled."],
    )


def apply_cancel_batch(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    batch_id = _require_text(args, "batchId")
    _require_batch(ctx.project_id, batch_id)
    result = audio_service.cancel_batch(ctx.project_id, batch_id)
    return {
        **result,
        "_evidence": {"source": "audio_studio.service.cancel_batch"},
    }


def preview_select_candidate(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    batch_id = _require_text(args, "batchId")
    candidate_id = _require_text(args, "candidateId")
    batch = _require_batch(ctx.project_id, batch_id)
    candidate = _require_candidate(batch, candidate_id)
    return ToolPreview(
        summary="Select an Audio Studio candidate for audition.",
        lines=[
            f"Batch: {batch_id}",
            f"Candidate: {candidate_id}",
            f"Current status: {candidate.get('status') or 'unknown'}",
            "Selection does not auto-approve or auto-place.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=["No automatic placement will happen from selection alone."],
    )


def apply_select_candidate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    batch_id = _require_text(args, "batchId")
    candidate_id = _require_text(args, "candidateId")
    return {
        **audio_service.select_candidate(ctx.project_id, batch_id, candidate_id),
        "batchId": batch_id,
        "candidateId": candidate_id,
        "_evidence": {"source": "audio_studio.service.select_candidate"},
    }


def preview_approve_candidate(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    batch_id = _require_text(args, "batchId")
    candidate_id = _require_text(args, "candidateId")
    batch = _require_batch(ctx.project_id, batch_id)
    candidate = _require_candidate(batch, candidate_id)
    return ToolPreview(
        summary="Approve an Audio Studio candidate for placement.",
        lines=[
            f"Batch: {batch_id}",
            f"Candidate: {candidate_id}",
            f"Asset: {candidate.get('asset_id') or 'not registered'}",
            "Approval does not auto-place on the timeline.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=["Approval is separate from placement."],
    )


def apply_approve_candidate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    batch_id = _require_text(args, "batchId")
    candidate_id = _require_text(args, "candidateId")
    return {
        **audio_service.approve_candidate(ctx.project_id, batch_id, candidate_id),
        "batchId": batch_id,
        "candidateId": candidate_id,
        "_evidence": {"source": "audio_studio.service.approve_candidate"},
    }


def preview_place(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    asset_id, candidate = _resolve_asset_for_placement(ctx, args)
    scene_id = _optional_text(args, "sceneId") or ctx.scene_id or "current project"
    category = _place_category(args, candidate)
    return ToolPreview(
        summary="Place approved audio onto the timeline.",
        lines=[
            f"Asset: {asset_id}",
            f"Category: {category}",
            f"Scene: {scene_id}",
            f"Start: {int(args.get('startMs') or 0)}ms",
            "No automatic mix suggestions will be applied.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_place(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    asset_id, candidate = _resolve_asset_for_placement(ctx, args)
    category = _place_category(args, candidate)
    scene_id = _optional_text(args, "sceneId") or ctx.scene_id
    result = audio_service.place_on_timeline(
        ctx.db,
        ctx.project_id,
        asset_id=asset_id,
        category=category,
        start_ms=int(args.get("startMs") or 0),
        loop=bool(args.get("loop")),
        scene_id=scene_id,
    )
    return {
        **result,
        "_evidence": {"source": "audio_studio.service.place_on_timeline"},
    }


def preview_replace_clip(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    replace_clip_id = _require_text(args, "replaceClipId")
    mix = audio_store.get_mix(ctx.project_id)
    existing = (mix.get("clips") or {}).get(replace_clip_id)
    if not existing:
        raise _target_not_found("Timeline clip not found in the Audio Studio mix.", clipId=replace_clip_id)
    asset_id, candidate = _resolve_asset_for_placement(ctx, args)
    category = _place_category(args, candidate) or str(existing.get("category") or "music")
    start_ms = int(args.get("startMs") if args.get("startMs") is not None else existing.get("start_ms") or 0)
    return ToolPreview(
        summary="Replace an existing Audio Studio clip with approved audio.",
        lines=[
            f"Replace clip: {replace_clip_id}",
            f"New asset: {asset_id}",
            f"Category: {category}",
            f"Start: {start_ms}ms",
            "Replacement mutes the old clip after the new one is placed.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_replace_clip(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    replace_clip_id = _require_text(args, "replaceClipId")
    mix = audio_store.get_mix(ctx.project_id)
    existing = (mix.get("clips") or {}).get(replace_clip_id)
    if not existing:
        raise _target_not_found("Timeline clip not found in the Audio Studio mix.", clipId=replace_clip_id)
    asset_id, candidate = _resolve_asset_for_placement(ctx, args)
    category = _place_category(args, candidate) or str(existing.get("category") or "music")
    start_ms = int(args.get("startMs") if args.get("startMs") is not None else existing.get("start_ms") or 0)
    scene_id = _optional_text(args, "sceneId") or ctx.scene_id
    placed = audio_service.place_on_timeline(
        ctx.db,
        ctx.project_id,
        asset_id=asset_id,
        category=category,
        start_ms=start_ms,
        loop=bool(args.get("loop", existing.get("loop"))),
        scene_id=scene_id,
    )
    updated_mix = audio_service.update_mix(
        ctx.project_id,
        {
            "clips": {
                replace_clip_id: {
                    "clip_id": replace_clip_id,
                    "mute": True,
                    "solo": False,
                    "approval_status": "replaced",
                    "replaced_by_clip_id": placed.get("clipId"),
                },
                str(placed.get("clipId") or ""): {
                    "clip_id": placed.get("clipId"),
                    "replaces_clip_id": replace_clip_id,
                },
            }
        },
    )
    return {
        **placed,
        "replacedClipId": replace_clip_id,
        "mix": updated_mix,
        "_evidence": {
            "source": "audio_studio.service.place_on_timeline + audio_studio.service.update_mix",
        },
    }
