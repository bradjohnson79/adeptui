"""Scene read handlers plus the preview/apply pairs for scene mutations.

`apply_*` functions are the only place in the tool registry that writes to `scenes`, and they
are called exclusively by `ToolExecutionService.execute_approved_proposal` after a human has
approved the recorded arguments. Nothing in a chat turn can reach them.

CRUD goes through PSR `SceneService` (patch-only-present-fields). Compact tool-facing summaries
and proposal fingerprints remain in `app.scene_service` helpers.
"""

from __future__ import annotations

import re
from typing import Any

from .... import scene_service as scene_helpers
from ....capabilities.errors import CapabilityError
from ....db import Project, Scene
from ....services.scene_service import SceneService
from ...errors import TOOL_EXECUTION_FAILED, TOOL_TARGET_NOT_FOUND, CoDirectorError
from ..definitions import ToolContext, ToolPreview

DEFAULT_SCENE_LIMIT = 40


def _require_project(ctx: ToolContext) -> Project:
    try:
        return SceneService.require_project(ctx.db, ctx.project_id)
    except CapabilityError as exc:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "Project not found.",
            details={"projectId": ctx.project_id},
            recoverable=False,
            recommended_action="none",
        ) from exc


def _require_scene(ctx: ToolContext, scene_id: str) -> Scene:
    try:
        return SceneService.get(ctx.db, ctx.project_id, scene_id)
    except CapabilityError as exc:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "That scene isn't part of this project.",
            details={"projectId": ctx.project_id, "sceneId": scene_id},
            recoverable=False,
            recommended_action="none",
        ) from exc


async def list_scenes(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ..read_envelope import clamp_limit

    limit = clamp_limit(args.get("limit"), default=DEFAULT_SCENE_LIMIT)
    scenes = SceneService.list_for_project(ctx.db, ctx.project_id)
    page = [scene_helpers.scene_summary(s) for s in scenes[:limit]]
    has_more = len(scenes) > limit
    return {
        "projectId": ctx.project_id,
        "sceneCount": len(scenes),
        "returned": len(page),
        "scenes": page,
        "_summary": f"{len(page)} of {len(scenes)} scene(s).",
        "_pagination": {
            "limit": limit,
            "total": len(scenes),
            "hasMore": has_more,
            "returnedCount": len(page),
            "nextCursor": str(limit) if has_more else None,
            "appliedFilters": {},
        },
        "_evidence": [
            {"sourceType": "scene", "sourceId": s.get("id") or s.get("sceneId"), "repository": "scene_service"}
            for s in page
            if s.get("id") or s.get("sceneId")
        ],
    }


async def get_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _require_scene(ctx, str(args["sceneId"]))
    detail = scene_helpers.scene_summary(scene)
    detail["continuityNote"] = (scene.continuity_json or "")[:1000]
    detail["summary"] = getattr(scene, "summary", "") or ""
    detail["_summary"] = f"Scene '{getattr(scene, 'name', scene.id)}'."
    detail["_evidence"] = [
        {
            "sourceType": "scene",
            "sourceId": scene.id,
            "sourceName": getattr(scene, "name", None),
            "repository": "scene_service",
        }
    ]
    return detail


async def get_active_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """The selected scene is client state, so it arrives with the turn rather than from the DB."""

    if not ctx.scene_id:
        return {"projectId": ctx.project_id, "activeScene": None, "reason": "No scene is selected."}
    try:
        scene = SceneService.get(ctx.db, ctx.project_id, ctx.scene_id)
    except CapabilityError:
        return {"projectId": ctx.project_id, "activeScene": None, "reason": "The selected scene no longer exists."}
    return {"projectId": ctx.project_id, "activeScene": scene_helpers.scene_summary(scene)}


_REAL_ID = re.compile(
    r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|shot_[0-9a-f]{6,})$",
    re.I,
)


def _usable_id(value: Any) -> str:
    token = str(value or "").strip()
    if not _REAL_ID.match(token):
        return ""
    return token


def _latest_draft_shot(ctx: ToolContext) -> tuple[str, str] | None:
    """The last Timeline shot that is still a draft. Earlier scenes stay untouched."""

    from ....film_timeline.store import load_film
    from ....scene_service import list_scenes

    found: tuple[str, str] | None = None
    for scene in list_scenes(ctx.db, ctx.project_id):
        loaded = load_film(ctx.db, ctx.project_id, scene.id)
        if not loaded.get("ok"):
            continue
        film = loaded.get("film")
        shots = list(getattr(film, "shots", None) or [])
        for shot in shots:
            status = str(getattr(shot, "status", "") or "")
            segments = list(getattr(shot, "segments", None) or [])
            if status == "draft" and not segments:
                found = (str(scene.id), str(shot.id))
    return found


def _stamp_manual_megapixels(ctx: ToolContext, scene_id: str, shot_id: str, megapixels: float) -> None:
    from ....film_timeline.store import require_film, save_film

    film = require_film(ctx.db, ctx.project_id, scene_id)
    shot = next((item for item in film.shots if item.id == shot_id), None)
    if shot is None:
        return
    stored = dict(shot.state.resolvedGeneration or {})
    stored["h3Resolution"] = {"mode": "manual", "megapixels": float(megapixels)}
    shot.state.resolvedGeneration = stored
    save_film(ctx.db, ctx.project_id, scene_id, film)


def latest_ready_published_scene(db: Any, project_id: str) -> tuple[str, str] | None:
    """The last scene whose published master is still the ready stitch.

    Reads the stored film document. Does not load or adopt a timeline.
    """

    import json

    from ....scene_service import list_scenes

    found: tuple[str, str] | None = None
    for scene in list_scenes(db, project_id):
        raw = getattr(scene, "director_json", None)
        try:
            data = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw if isinstance(raw, dict) else {})
        except json.JSONDecodeError:
            continue
        film = data.get("filmTimeline") if isinstance(data, dict) else None
        if not isinstance(film, dict):
            continue
        published = str(film.get("publishedAssetId") or "").strip()
        source = str(film.get("publishedSourceAssetId") or "").strip()
        if not published or not source:
            continue
        shots = film.get("shots") if isinstance(film.get("shots"), list) else []
        for shot in shots:
            if not isinstance(shot, dict):
                continue
            state = shot.get("state") if isinstance(shot.get("state"), dict) else {}
            stitch = str(state.get("stitchAssetId") or "").strip()
            status = str(state.get("stitchStatus") or "").strip().lower()
            if status == "ready" and stitch == source:
                found = (str(scene.id), str(shot.get("id") or ""))
    return found


def _latest_completed_shot(ctx: ToolContext) -> tuple[str, str] | None:
    """The last shot that already has a finished picture. Continuation stays on that shot."""

    from ....film_timeline.store import load_film
    from ....scene_service import list_scenes

    found: tuple[str, str] | None = None
    for scene in list_scenes(ctx.db, ctx.project_id):
        loaded = load_film(ctx.db, ctx.project_id, scene.id)
        if not loaded.get("ok"):
            continue
        film = loaded.get("film")
        for shot in list(getattr(film, "shots", None) or []):
            segments = list(getattr(shot, "segments", None) or [])
            if any(str(getattr(segment, "status", "") or "") == "completed" and getattr(segment, "assetId", None) for segment in segments):
                found = (str(scene.id), str(shot.id))
    return found


def preview_timeline_publish_scene(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene_id = _usable_id(args.get("sceneId"))
    if not scene_id:
        found = _latest_completed_shot(ctx)
        if found:
            scene_id = found[0]
    return ToolPreview(
        summary="Publish the finished Timeline scene.",
        lines=["Use the ready stitch as the published master."],
        resourceKind="scene",
        resourceId=scene_id or ctx.project_id,
    )


def apply_timeline_publish_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....film_timeline.publish_media import publish_film_media

    scene_id = _usable_id(args.get("sceneId"))
    shot_id = _usable_id(args.get("shotId"))
    if not scene_id or not shot_id:
        found = _latest_completed_shot(ctx)
        if not found:
            raise CoDirectorError(
                TOOL_EXECUTION_FAILED,
                "Publish needs a finished scene.",
                details={"toolId": "timeline.publish_scene"},
                recoverable=True,
                recommended_action="retry",
            )
        scene_id, shot_id = found
    result = publish_film_media(
        ctx.db,
        ctx.project_id,
        scene_id,
        asset_id="",
        shot_id=shot_id,
    )
    if not result.get("ok"):
        raise CoDirectorError(
            TOOL_EXECUTION_FAILED,
            str(result.get("message") or "Timeline could not publish that scene."),
            details={"toolId": "timeline.publish_scene", "code": result.get("error")},
            recoverable=True,
            recommended_action="retry",
        )
    result["toolId"] = "timeline.publish_scene"
    return result


def preview_timeline_prepend_shot(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene_id = _usable_id(args.get("sceneId"))
    if not scene_id:
        found = _latest_completed_shot(ctx)
        if found:
            scene_id = found[0]
    return ToolPreview(
        summary="Create the opening shot before the first finished picture.",
        lines=["Insert it at the start after the file exists.", f"Prompt: {str(args.get('prompt') or '')[:160]}"],
        resourceKind="scene",
        resourceId=scene_id or ctx.project_id,
    )


def apply_timeline_prepend_shot(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....film_timeline.orchestrator import FilmTimelineError, prepend_shot

    scene_id = _usable_id(args.get("sceneId"))
    shot_id = _usable_id(args.get("shotId"))
    if not scene_id or not shot_id:
        found = _latest_completed_shot(ctx)
        if not found:
            raise CoDirectorError(
                TOOL_EXECUTION_FAILED,
                "The opening shot needs a finished picture to come before. Generate the first shot first.",
                details={"toolId": "timeline.prepend_shot"},
                recoverable=True,
                recommended_action="retry",
            )
        scene_id, shot_id = found
    prompt = str(args.get("prompt") or "").strip()
    duration = args.get("durationSec")
    try:
        result = prepend_shot(
            ctx.db,
            ctx.project_id,
            scene_id,
            shot_id,
            duration_sec=float(duration) if duration is not None else 15.0,
            timed_prompt=prompt,
        )
    except FilmTimelineError as exc:
        raise CoDirectorError(
            TOOL_EXECUTION_FAILED,
            exc.message,
            details={"toolId": "timeline.prepend_shot", "code": exc.code},
            recoverable=True,
            recommended_action="retry",
        ) from exc
    if not result.get("ok"):
        raise CoDirectorError(
            TOOL_EXECUTION_FAILED,
            str(result.get("message") or "Timeline could not add the opening shot."),
            details={"toolId": "timeline.prepend_shot"},
            recoverable=True,
            recommended_action="retry",
        )
    result["toolId"] = "timeline.prepend_shot"
    return result


def preview_timeline_continue_shot(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene_id = str(args.get("sceneId") or "").strip()
    if not scene_id:
        found = _latest_completed_shot(ctx)
        if found:
            scene_id = found[0]
    return ToolPreview(
        summary="Continue the finished Timeline shot.",
        lines=["Add the next part after the finished picture.", f"Prompt: {str(args.get('prompt') or '')[:160]}"],
        resourceKind="scene",
        resourceId=scene_id or ctx.project_id,
    )


def apply_timeline_continue_shot(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....film_timeline.orchestrator import FilmTimelineError, continue_shot

    scene_id = _usable_id(args.get("sceneId"))
    shot_id = _usable_id(args.get("shotId"))
    if not scene_id or not shot_id:
        found = _latest_completed_shot(ctx)
        if not found:
            raise CoDirectorError(
                TOOL_EXECUTION_FAILED,
                "Continue Shot needs a finished segment on this shot. Generate the shot first.",
                details={"toolId": "timeline.continue_shot"},
                recoverable=True,
                recommended_action="retry",
            )
        scene_id, shot_id = found
    prompt = str(args.get("prompt") or "").strip()
    duration = args.get("durationSec")
    try:
        result = continue_shot(
            ctx.db,
            ctx.project_id,
            scene_id,
            shot_id,
            duration_sec=float(duration) if duration is not None else 15.0,
            timed_prompt=prompt,
        )
    except FilmTimelineError as exc:
        raise CoDirectorError(
            TOOL_EXECUTION_FAILED,
            exc.message,
            details={"toolId": "timeline.continue_shot", "code": exc.code},
            recoverable=True,
            recommended_action="retry",
        ) from exc
    if not result.get("ok"):
        raise CoDirectorError(
            TOOL_EXECUTION_FAILED,
            str(result.get("message") or "Timeline could not continue that shot."),
            details={"toolId": "timeline.continue_shot"},
            recoverable=True,
            recommended_action="retry",
        )
    result["toolId"] = "timeline.continue_shot"
    return result


def preview_timeline_generate_shot(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene_id = str(args.get("sceneId") or "").strip()
    shot_id = str(args.get("shotId") or "").strip()
    if not scene_id or not shot_id:
        found = _latest_draft_shot(ctx)
        if found:
            scene_id, shot_id = found
    lines = ["Generate the prepared Timeline shot."]
    if scene_id:
        lines.append(f"Scene: {scene_id}")
    megapixels = args.get("megapixels")
    if megapixels is not None:
        lines.append(f"Picture size: {megapixels} megapixels")
    return ToolPreview(
        summary="Generate the prepared Timeline shot.",
        lines=lines,
        resourceKind="scene",
        resourceId=scene_id or ctx.project_id,
    )


def _ensure_named_character_reference(ctx: ToolContext, scene_id: str, shot_id: str) -> None:
    """Copy the character already named on the shot onto the existing reference owner."""

    from ....director_timeline_w46.generation.character_identity_bind import mentioned_character_names
    from ....film_timeline.orchestrator import attach_reference
    from ....film_timeline.store import require_film
    from ...entity_resolver import resolve_character

    film = require_film(ctx.db, ctx.project_id, scene_id)
    shot = next((item for item in film.shots if item.id == shot_id), None)
    if shot is None:
        return
    if shot.state.firstFrameAssetId or any(ref.assetId for ref in [*film.references, *shot.state.references]):
        return
    from ....character_identity.service import list_profiles

    known = [str(profile.name).strip() for profile in list_profiles(ctx.db, ctx.project_id) if str(profile.name or "").strip()]
    names = mentioned_character_names(str(shot.timedPrompt or ""), known)
    if not names:
        return
    hit = resolve_character(ctx.db, ctx.project_id, names[0]) or {}
    asset_id = str(hit.get("approved_casting_asset_id") or hit.get("approved_sheet_asset_id") or "").strip()
    if not asset_id:
        return
    attach_reference(
        ctx.db,
        ctx.project_id,
        scene_id,
        shot_id,
        asset_id=asset_id,
        ref_type="character",
        label=names[0],
        tag=names[0],
    )


def apply_timeline_generate_shot(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....film_timeline.orchestrator import FilmTimelineError
    from ...production.orchestrator import generate_prepared_scene

    scene_id = _usable_id(args.get("sceneId"))
    shot_id = _usable_id(args.get("shotId"))
    if not scene_id or not shot_id:
        found = _latest_draft_shot(ctx)
        if not found:
            return {"ok": False, "error": "No prepared Timeline shot is available to generate."}
        scene_id, shot_id = found
    megapixels = args.get("megapixels")
    if isinstance(megapixels, (int, float)) and not isinstance(megapixels, bool):
        _stamp_manual_megapixels(ctx, scene_id, shot_id, float(megapixels))
    try:
        _ensure_named_character_reference(ctx, scene_id, shot_id)
        result = generate_prepared_scene(ctx.db, project_id=ctx.project_id, scene_id=scene_id, shot_id=shot_id)
    except FilmTimelineError as exc:
        raise CoDirectorError(
            TOOL_EXECUTION_FAILED,
            exc.message,
            details={"toolId": "timeline.generate_shot", "code": exc.code},
            recoverable=True,
            recommended_action="retry",
        ) from exc
    result["toolId"] = "timeline.generate_shot"
    return result


def preview_create_scene(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _require_project(ctx)
    next_index = SceneService.count_for_project(ctx.db, ctx.project_id)
    name = str(args.get("name") or f"Scene {next_index + 1}")
    engine = str(args.get("engine") or "")
    duration = args.get("durationSec")
    prompt = str(args.get("prompt") or "")
    lines = [f"Add scene “{name}” at position {next_index + 1}"]
    if engine:
        lines.append(f"Engine: {engine}")
    if duration:
        lines.append(f"Duration: {duration}s")
    if prompt:
        lines.append(f"Prompt: {prompt[:160]}")
    character_name = str(args.get("characterName") or "").strip()
    if character_name:
        lines.append(f"Character: {character_name}")
    return ToolPreview(
        summary=f"Create a new scene “{name}” at the end of the timeline.",
        lines=lines,
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def _attach_kept_stills(ctx: ToolContext, scene_id: str, character_asset: str, environment_asset: str) -> None:
    """Put the kept library stills on the Film Timeline shot H3 actually reads."""

    if not character_asset and not environment_asset:
        return
    from ....film_timeline.orchestrator import FilmTimelineError, attach_reference
    from ....film_timeline.store import load_film

    loaded = load_film(ctx.db, ctx.project_id, scene_id)
    film = loaded.get("film")
    shots = list(getattr(film, "shots", None) or [])
    if not shots:
        raise CoDirectorError(
            TOOL_EXECUTION_FAILED,
            "The new scene has no shot to attach the stills to.",
            details={"toolId": "create_scene", "sceneId": scene_id},
            recoverable=True,
            recommended_action="retry",
        )
    shot_id = str(shots[0].id)
    pairs = (
        (character_asset, "character", "Analyst"),
        (environment_asset, "environment", "Records Room"),
    )
    for asset_id, ref_type, label in pairs:
        if not asset_id:
            continue
        try:
            attach_reference(
                ctx.db,
                ctx.project_id,
                scene_id,
                shot_id,
                asset_id=asset_id,
                ref_type=ref_type,
                label=label,
                tag=label,
                scene_level=True,
            )
        except FilmTimelineError as exc:
            raise CoDirectorError(
                TOOL_EXECUTION_FAILED,
                exc.message,
                details={"toolId": "create_scene", "code": exc.code, "sceneId": scene_id},
                recoverable=True,
                recommended_action="retry",
            ) from exc


def apply_create_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project = _require_project(ctx)
    scene = SceneService.create(
        ctx.db,
        ctx.project_id,
        {
            "name": str(args.get("name") or ""),
            "engine": str(args.get("engine") or project.engine_default or "ltx"),
            "prompt": str(args.get("prompt") or ""),
            # None when the creator did not choose -> SceneService.create seeds
            # by engine law (MiniMax H3 / blank / "auto" -> 15.0s). An explicit
            # creator duration is never overridden.
            "duration_sec": (float(args["durationSec"]) if args.get("durationSec") is not None else None),
            "aspect_ratio": (str(args["aspectRatio"]) if args.get("aspectRatio") else None),
        },
    )
    _attach_kept_stills(
        ctx,
        str(scene.id),
        str(args.get("characterAssetId") or "").strip(),
        str(args.get("environmentAssetId") or "").strip(),
    )
    character_id = str(args.get("characterId") or "").strip()
    asset_id = str(args.get("assetId") or "").strip()
    reference = None
    if character_id and asset_id:
        try:
            from ....scene_references import service as scene_references

            reference = scene_references.attach(
                ctx.db,
                ctx.project_id,
                {
                    "asset_id": asset_id,
                    "scope_type": "scene",
                    "scope_id": str(scene.id),
                    "reference_type": "character",
                    "usage_modes": ["informational", "generation"],
                    "reference_roles": ["character"],
                    "identity_id": str(args.get("identityId") or character_id),
                },
                actor="codirector",
            )
        except Exception:
            reference = None
    summary = scene_helpers.scene_summary(scene)
    return {
        "created": "scene",
        "scene": summary,
        "characterName": str(args.get("characterName") or ""),
        "referenceAttached": reference is not None,
    }


def preview_update_scene_title(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene = _require_scene(ctx, str(args["sceneId"]))
    new_name = str(args["name"])
    return ToolPreview(
        summary=f"Rename scene {scene.index + 1} to “{new_name}”.",
        lines=[f"Current title: {scene.name}", f"New title: {new_name}"],
        resourceKind="scene",
        resourceId=scene.id,
        warnings=[] if new_name != scene.name else ["The new title is the same as the current one."],
    )


def apply_update_scene_title(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _require_scene(ctx, str(args["sceneId"]))
    previous = scene.name
    scene = SceneService.update(ctx.db, ctx.project_id, scene.id, {"name": str(args["name"])})
    return {"updated": "scene.name", "previous": previous, "scene": scene_helpers.scene_summary(scene)}


def preview_set_scene_prompt(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene = _require_scene(ctx, str(args["sceneId"]))
    new_prompt = str(args["prompt"])
    warnings = ["This replaces the scene's existing prompt."] if (scene.prompt or "").strip() else []
    return ToolPreview(
        summary=f"Set the prompt for scene {scene.index + 1} (“{scene.name}”).",
        lines=[
            f"Current prompt: {(scene.prompt or '(empty)')[:200]}",
            f"New prompt: {new_prompt[:200]}",
        ],
        resourceKind="scene",
        resourceId=scene.id,
        warnings=warnings,
    )


def apply_set_scene_prompt(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene = _require_scene(ctx, str(args["sceneId"]))
    previous = scene.prompt or ""
    scene = SceneService.update(ctx.db, ctx.project_id, scene.id, {"prompt": str(args["prompt"])})
    return {
        "updated": "scene.prompt",
        "previousLength": len(previous),
        "scene": scene_helpers.scene_summary(scene),
    }
