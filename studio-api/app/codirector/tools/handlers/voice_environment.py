"""Co-Director tools for Voice Studio + Voice Environment."""

from __future__ import annotations

from urllib.parse import quote
from typing import Any

from ....character_identity import service as character_service
from ....character_identity.voice_creator import get_voice_workspace, save_voice_studio_draft
from ....db import Scene
from ....voice_environment import service as ve_service
from ....voice_environment.contracts import ProfileCreateRequest, ProfileUpdateRequest
from ....voice_environment.models import VoiceEnvironmentRenderRow
from ....voice_performance import m410_service
from ...bible.context_retrieval import ContextRetrievalService
from ..definitions import ToolContext, ToolPreview


def _text(args: dict[str, Any], key: str) -> str:
    return str(args.get(key) or "").strip()


def _optional_text(args: dict[str, Any], key: str) -> str | None:
    value = _text(args, key)
    return value or None


def _bool(args: dict[str, Any], key: str, default: bool = False) -> bool:
    value = args.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _require_project(ctx: ToolContext) -> str:
    if not ctx.project_id:
        raise ValueError("projectId is required")
    return ctx.project_id


def _require_character(args: dict[str, Any]) -> str:
    character_id = _text(args, "characterId")
    if not character_id:
        raise ValueError("characterId is required")
    return character_id


def _require_record(args: dict[str, Any]) -> str:
    record_id = _text(args, "recordId")
    if not record_id:
        raise ValueError("recordId is required")
    return record_id


def _require_profile(args: dict[str, Any], key: str = "profileId") -> str:
    profile_id = _text(args, key)
    if not profile_id:
        raise ValueError(f"{key} is required")
    return profile_id


def _require_render(args: dict[str, Any]) -> str:
    render_id = _text(args, "renderId")
    if not render_id:
        raise ValueError("renderId is required")
    return render_id


def _workspace_url(project_id: str, character_id: str) -> str:
    return f"/project/{quote(project_id)}?workspace=voicestudio&characterId={quote(character_id)}"


def _voice_handoff(project_id: str, character_id: str, ui_action: str = "open_voice_creator") -> dict[str, Any]:
    return {
        "projectId": project_id,
        "characterId": character_id,
        "uiAction": ui_action,
        "workspaceUrl": _workspace_url(project_id, character_id),
        "routeHint": "Voice Studio",
    }


def _record_out(ctx: ToolContext, record_id: str) -> dict[str, Any]:
    return m410_service.get_record(ctx.db, record_id).model_dump()


def _takes_out(ctx: ToolContext, record_id: str) -> dict[str, Any]:
    return m410_service.list_takes(ctx.db, record_id)


def _approved_take(takes_payload: dict[str, Any]) -> dict[str, Any] | None:
    approved_take_id = str(takes_payload.get("approvedTakeId") or "").strip()
    if not approved_take_id:
        return None
    for take in takes_payload.get("takes") or []:
        if str(take.get("id") or "") == approved_take_id:
            return take
    return None


def _scene_or_raise(ctx: ToolContext, scene_id: str) -> Scene:
    scene = ctx.db.get(Scene, scene_id)
    if not scene or scene.project_id != _require_project(ctx):
        raise ValueError("sceneId was not found in this project")
    return scene


def _profile_create_fields(args: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in (
        "projectId",
        "characterId",
        "sceneId",
        "locationId",
        "name",
        "spacePreset",
        "customSpacePrompt",
        "distancePreset",
        "customDistancePrompt",
        "directionPreset",
        "customDirectionPrompt",
        "tonePreset",
        "customTonePrompt",
        "devicePreset",
        "customDevicePrompt",
        "wallaPreset",
        "wallaLevel",
        "wallaDistance",
        "wallaBehavior",
        "customWallaPrompt",
        "source",
    ):
        if key in args and args.get(key) is not None:
            payload[key] = args.get(key)
    return payload


def _profile_update_fields(args: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in (
        "name",
        "characterId",
        "sceneId",
        "locationId",
        "spacePreset",
        "customSpacePrompt",
        "distancePreset",
        "customDistancePrompt",
        "directionPreset",
        "customDirectionPrompt",
        "tonePreset",
        "customTonePrompt",
        "devicePreset",
        "customDevicePrompt",
        "wallaPreset",
        "wallaLevel",
        "wallaDistance",
        "wallaBehavior",
        "customWallaPrompt",
        "source",
    ):
        if key in args:
            payload[key] = args.get(key)
    return payload


def _profile_to_create_payload(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "projectId": profile.get("projectId"),
        "characterId": profile.get("characterId"),
        "sceneId": profile.get("sceneId"),
        "locationId": profile.get("locationId"),
        "name": profile.get("name"),
        "spacePreset": profile.get("spacePreset"),
        "customSpacePrompt": profile.get("customSpacePrompt"),
        "distancePreset": profile.get("distancePreset"),
        "customDistancePrompt": profile.get("customDistancePrompt"),
        "directionPreset": profile.get("directionPreset"),
        "customDirectionPrompt": profile.get("customDirectionPrompt"),
        "tonePreset": profile.get("tonePreset"),
        "customTonePrompt": profile.get("customTonePrompt"),
        "devicePreset": profile.get("devicePreset"),
        "customDevicePrompt": profile.get("customDevicePrompt"),
        "wallaPreset": profile.get("wallaPreset"),
        "wallaLevel": profile.get("wallaLevel"),
        "wallaDistance": profile.get("wallaDistance"),
        "wallaBehavior": profile.get("wallaBehavior"),
        "customWallaPrompt": profile.get("customWallaPrompt"),
        "source": profile.get("source") or "codirector",
    }


def _voice_identity_plan(workspace: dict[str, Any], preferred_method: str | None = None) -> dict[str, Any]:
    methods = list(workspace.get("methods") or [])
    selected = None
    if preferred_method:
        selected = next((item for item in methods if str(item.get("id") or "") == preferred_method), None)
    if selected is None:
        selected = next((item for item in methods if item.get("ready")), methods[0] if methods else None)
    return {
        "preferredMethod": selected.get("id") if isinstance(selected, dict) else None,
        "method": selected,
        "designBrief": workspace.get("designBrief") or {},
        "compiledDesignPrompt": workspace.get("compiledDesignPrompt") or "",
        "performanceAttached": bool(workspace.get("performanceAttached")),
        "emotionAttached": bool(workspace.get("emotionAttached")),
        "activeVoiceProfileId": workspace.get("activeVoiceProfileId"),
    }


async def inspect_studio(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _require_project(ctx)
    character_id = _require_character(args)
    workspace = get_voice_workspace(ctx.db, project_id, character_id)
    voice_profiles = character_service.list_voice_profiles(ctx.db, project_id, character_id)
    renders = ve_service.list_renders(ctx.db, project_id, character_id=character_id)
    profiles = ve_service.list_profiles(ctx.db, project_id, character_id=character_id)
    return {
        "ok": True,
        "projectId": project_id,
        "characterId": character_id,
        "workspaceUrl": _workspace_url(project_id, character_id),
        "workspace": workspace,
        "voiceIdentity": {
            "activeVoiceProfileId": workspace.get("activeVoiceProfileId"),
            "voiceProfileCount": len(voice_profiles),
            "approvedVoiceCount": sum(1 for item in voice_profiles if item.get("approval_status") == "approved"),
            "methods": workspace.get("methods") or [],
            "draft": workspace.get("voiceStudioDraft") or {},
        },
        "voiceEnvironment": {
            "runtime": ve_service.runtime_status(),
            "profileCount": len(profiles),
            "renderCount": len(renders),
            "latestProfile": profiles[0].model_dump() if profiles else None,
            "latestRender": renders[0].model_dump() if renders else None,
        },
        "mock": False,
        "_evidence": {"source": "voice_studio.workspace"},
    }


async def inspect_character(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _require_project(ctx)
    character_id = _require_character(args)
    profile = character_service.get_profile(ctx.db, project_id, character_id).model_dump()
    voice_workspace = get_voice_workspace(ctx.db, project_id, character_id)
    return {
        "ok": True,
        "projectId": project_id,
        "characterId": character_id,
        "character": profile,
        "voiceWorkspace": {
            "activeVoiceProfileId": voice_workspace.get("activeVoiceProfileId"),
            "activeVoice": voice_workspace.get("activeVoice"),
            "performanceAttached": bool(voice_workspace.get("performanceAttached")),
            "emotionAttached": bool(voice_workspace.get("emotionAttached")),
            "draft": voice_workspace.get("voiceStudioDraft") or {},
        },
        "workspaceUrl": _workspace_url(project_id, character_id),
        "mock": False,
        "_evidence": {"source": "character_identity.service"},
    }


async def inspect_identity(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _require_project(ctx)
    character_id = _require_character(args)
    workspace = get_voice_workspace(ctx.db, project_id, character_id)
    return {
        "ok": True,
        "projectId": project_id,
        "characterId": character_id,
        "workspaceUrl": _workspace_url(project_id, character_id),
        "activeVoiceProfileId": workspace.get("activeVoiceProfileId"),
        "activeVoice": workspace.get("activeVoice"),
        "methods": workspace.get("methods") or [],
        "designBrief": workspace.get("designBrief") or {},
        "compiledDesignPrompt": workspace.get("compiledDesignPrompt") or "",
        "candidateBatches": workspace.get("candidateBatches") or [],
        "voiceStudioDraft": workspace.get("voiceStudioDraft") or {},
        "mock": False,
        "_evidence": {"source": "character_identity.voice_creator"},
    }


async def inspect_performance(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record_id = _require_record(args)
    record = _record_out(ctx, record_id)
    takes = _takes_out(ctx, record_id)
    approved_take = _approved_take(takes)
    return {
        "ok": True,
        "recordId": record_id,
        "record": record,
        "takes": takes.get("takes") or [],
        "approvedTake": approved_take,
        "timelineLinkage": record.get("timelineLinkage") or {},
        "lipsyncLinkage": record.get("lipsyncLinkage") or {},
        "mock": False,
        "_evidence": {"source": "voice_performance.m410_service"},
    }


async def inspect_dialogue(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record_id = _require_record(args)
    record = _record_out(ctx, record_id)
    proposed_plan = record.get("performancePlan") or m410_service.build_codirector_performance_plan(
        str(record.get("dialogueText") or ""),
        {
            "sceneId": record.get("sceneId"),
            "scriptElementId": record.get("scriptElementId"),
            "characterId": record.get("characterId"),
            "sceneArcId": record.get("sceneArcId"),
        },
    )
    return {
        "ok": True,
        "recordId": record_id,
        "characterId": record.get("characterId"),
        "sceneId": record.get("sceneId"),
        "dialogueText": record.get("dialogueText"),
        "performancePlan": record.get("performancePlan") or {},
        "proposedPlan": proposed_plan,
        "directionMode": record.get("directionMode"),
        "timelineLinkage": record.get("timelineLinkage") or {},
        "lipsyncLinkage": record.get("lipsyncLinkage") or {},
        "mock": False,
        "_evidence": {"source": "voice_performance.m410_service"},
    }


async def inspect_takes(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record_id = _require_record(args)
    takes = _takes_out(ctx, record_id)
    return {
        "ok": True,
        "recordId": record_id,
        "approvedTakeId": takes.get("approvedTakeId"),
        "approvedTake": _approved_take(takes),
        "takeCount": len(takes.get("takes") or []),
        "takes": takes.get("takes") or [],
        "mock": False,
        "_evidence": {"source": "voice_performance.list_takes"},
    }


async def inspect_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....spatial_map import service as spatial_service

    project_id = _require_project(ctx)
    scene_id = _text(args, "sceneId")
    if not scene_id:
        raise ValueError("sceneId is required")
    scene = _scene_or_raise(ctx, scene_id)
    character_id = _optional_text(args, "characterId")
    spatial_maps = [
        document.model_dump()
        for document in spatial_service.list_documents(ctx.db, project_id)
        if document.sceneId == scene_id or scene_id in (document.assignedSceneIds or [])
    ]
    profiles = [
        profile.model_dump()
        for profile in ve_service.list_profiles(ctx.db, project_id, character_id=character_id)
        if profile.sceneId == scene_id
    ]
    recommendation = (
        ve_service.recommend(ctx.db, project_id=project_id, character_id=character_id, scene_id=scene_id).model_dump()
        if character_id
        else None
    )
    return {
        "ok": True,
        "scene": {
            "id": scene.id,
            "projectId": scene.project_id,
            "name": scene.name,
            "summary": scene.summary,
            "prompt": scene.prompt,
            "audioAssetId": scene.audio_asset_id,
            "lipsyncAudioAssetId": scene.lipsync_audio_asset_id,
        },
        "spatialMaps": spatial_maps,
        "environmentProfiles": profiles,
        "recommendation": recommendation,
        "mock": False,
        "_evidence": {"source": "voice_environment.scene_context"},
    }


async def inspect_location(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....spatial_map import service as spatial_service

    project_id = _require_project(ctx)
    location_id = _text(args, "locationId")
    if not location_id:
        raise ValueError("locationId is required")
    maps = [
        document.model_dump()
        for document in spatial_service.list_documents(ctx.db, project_id)
        if str(document.locationId or "") == location_id
    ]
    profiles = [
        profile.model_dump()
        for profile in ve_service.list_profiles(ctx.db, project_id)
        if str(profile.locationId or "") == location_id
    ]
    bible_context = ContextRetrievalService.location_context(ctx.db, project_id, location_id)
    return {
        "ok": True,
        "projectId": project_id,
        "locationId": location_id,
        "bibleLocation": bible_context,
        "spatialMaps": maps,
        "environmentProfiles": profiles,
        "found": bool(maps or profiles or bible_context.get("found")),
        "mock": False,
        "_evidence": {"source": "voice_environment.location_context"},
    }


async def inspect_spatial_map(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....spatial_map import service as spatial_service

    project_id = _require_project(ctx)
    spatial_map_id = _text(args, "spatialMapId") or _text(args, "documentId")
    if not spatial_map_id:
        raise ValueError("spatialMapId is required")
    document = spatial_service.get_document(ctx.db, project_id, spatial_map_id).model_dump()
    character_id = _optional_text(args, "characterId")
    recommendation = (
        ve_service.recommend(
            ctx.db,
            project_id=project_id,
            character_id=character_id,
            scene_id=document.get("sceneId"),
            location_id=document.get("locationId"),
        ).model_dump()
        if character_id
        else None
    )
    return {
        "ok": True,
        "spatialMap": document,
        "recommendation": recommendation,
        "mock": False,
        "_evidence": {"source": "spatial_map.service"},
    }


async def inspect_environment_performance(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _require_project(ctx)
    record_id = _require_record(args)
    record = _record_out(ctx, record_id)
    take_id = _optional_text(args, "performanceTakeId") or record.get("approvedTakeId")
    renders = ve_service.list_renders(
        ctx.db,
        project_id,
        character_id=str(record.get("characterId") or ""),
        performance_take_id=take_id,
    )
    return {
        "ok": True,
        "record": record,
        "performanceTakeId": take_id,
        "renders": [render.model_dump() for render in renders],
        "mock": False,
        "_evidence": {"source": "voice_environment.performance_context"},
    }


async def inspect_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    profile_id = _require_profile(args)
    profile = ve_service.get_profile(ctx.db, profile_id).model_dump()
    render_rows = (
        ctx.db.query(VoiceEnvironmentRenderRow)
        .filter(VoiceEnvironmentRenderRow.environment_profile_id == profile_id)
        .order_by(VoiceEnvironmentRenderRow.created_at.desc())
        .all()
    )
    renders = [ve_service.get_render(ctx.db, row.id).model_dump() for row in render_rows]
    return {
        "ok": True,
        "profile": profile,
        "renderCount": len(renders),
        "renders": renders,
        "mock": False,
        "_evidence": {"source": "voice_environment.profile"},
    }


async def list_profiles(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    profiles = ve_service.list_profiles(ctx.db, _require_project(ctx), character_id=_optional_text(args, "characterId"))
    return {
        "ok": True,
        "count": len(profiles),
        "profiles": [profile.model_dump() for profile in profiles],
        "mock": False,
        "_evidence": {"source": "voice_environment.list_profiles"},
    }


async def list_renders(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    renders = ve_service.list_renders(
        ctx.db,
        _require_project(ctx),
        character_id=_optional_text(args, "characterId"),
        performance_take_id=_optional_text(args, "performanceTakeId"),
    )
    return {
        "ok": True,
        "count": len(renders),
        "renders": [render.model_dump() for render in renders],
        "mock": False,
        "_evidence": {"source": "voice_environment.list_renders"},
    }


async def inspect_runtime(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    status = ve_service.runtime_status()
    return {**status, "mock": False, "_evidence": {"source": "voice_environment.runtime_status"}}


async def inspect_timeline_link(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    render_id = _require_render(args)
    handoff = ve_service.prepare_timeline(
        ctx.db,
        render_id,
        scene_id=_optional_text(args, "sceneId"),
        use_processed=_bool(args, "useProcessedMix", True),
    )
    record = _record_out(ctx, str(handoff["handoff"].get("performanceRecordId") or ""))
    return {
        "ok": True,
        "renderId": render_id,
        "timelineHandoff": handoff,
        "currentTimelineLinkage": record.get("timelineLinkage") or {},
        "mock": False,
        "_evidence": {"source": "voice_environment.prepare_timeline"},
    }


async def inspect_lipsync_link(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    render_id = _require_render(args)
    render = ve_service.get_render(ctx.db, render_id).model_dump()
    record = _record_out(ctx, str(render.get("performanceRecordId") or ""))
    scene_id = _optional_text(args, "sceneId") or record.get("sceneId")
    handoff = {
        "projectId": render.get("projectId"),
        "sceneId": scene_id,
        "characterId": render.get("characterId"),
        "performanceRecordId": render.get("performanceRecordId"),
        "performanceTakeId": render.get("performanceTakeId"),
        "dryAudioAssetId": render.get("dryAudioAssetId"),
        "timing": render.get("timing") or {},
        "useDryTiming": True,
    }
    return {
        "ok": True,
        "renderId": render_id,
        "handoff": handoff,
        "currentLipsyncLinkage": record.get("lipsyncLinkage") or {},
        "mock": False,
        "_evidence": {"source": "voice_environment.inspect_lipsync_link"},
    }


async def preview_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    recommendation = ve_service.recommend(
        ctx.db,
        project_id=_require_project(ctx),
        character_id=_require_character(args),
        scene_id=_optional_text(args, "sceneId"),
        location_id=_optional_text(args, "locationId"),
    )
    return {
        "ok": True,
        "recommendation": recommendation.model_dump(),
        "runtime": ve_service.runtime_status(),
        "mock": False,
        "_evidence": {"source": "voice_environment.recommend"},
    }


def preview_select_character(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    project_id = _require_project(ctx)
    character_id = _require_character(args)
    profile = character_service.get_profile(ctx.db, project_id, character_id)
    return ToolPreview(
        summary=f"Open Voice Studio for {profile.name}.",
        lines=[
            f"characterId: {character_id}",
            "Stores a real Voice Studio draft hint for this character.",
            "Does not approve a voice or generate audio.",
        ],
        resourceKind="project",
        resourceId=project_id,
    )


def apply_select_character(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _require_project(ctx)
    character_id = _require_character(args)
    draft = save_voice_studio_draft(
        ctx.db,
        project_id,
        character_id,
        {
            "phase": "identity",
            "selectedCharacterId": character_id,
            "openedFrom": "codirector",
        },
    )
    return {
        "ok": True,
        **_voice_handoff(project_id, character_id),
        "voiceStudioDraft": draft.get("voiceStudioDraft"),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "character_identity.voice_creator.save_voice_studio_draft"},
    }


def preview_create_character_handoff(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    character_id = _require_character(args)
    return ToolPreview(
        summary="Create a creator-facing Voice Studio handoff for the selected character.",
        lines=[
            f"characterId: {character_id}",
            "Stores the handoff in the character's Voice Studio draft.",
            "Opens the existing creator workspace instead of inventing a new surface.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
    )


def apply_create_character_handoff(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _require_project(ctx)
    character_id = _require_character(args)
    workspace = get_voice_workspace(ctx.db, project_id, character_id)
    handoff = {
        "characterId": character_id,
        "characterName": workspace.get("characterName"),
        "activeVoiceProfileId": workspace.get("activeVoiceProfileId"),
        "performanceAttached": bool(workspace.get("performanceAttached")),
        "emotionAttached": bool(workspace.get("emotionAttached")),
    }
    draft = save_voice_studio_draft(
        ctx.db,
        project_id,
        character_id,
        {
            "phase": "identity",
            "codirectorCharacterHandoff": handoff,
            "openedFrom": "codirector",
        },
    )
    return {
        "ok": True,
        **_voice_handoff(project_id, character_id),
        "handoff": handoff,
        "voiceStudioDraft": draft.get("voiceStudioDraft"),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "character_identity.voice_creator.get_voice_workspace"},
    }


def preview_create_identity_plan(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    character_id = _require_character(args)
    preferred_method = _optional_text(args, "preferredMethod")
    return ToolPreview(
        summary="Create a Voice Studio identity plan from the current character profile.",
        lines=[
            f"characterId: {character_id}",
            f"preferredMethod: {preferred_method or 'best ready method'}",
            "Saves a real creator-facing draft plan only.",
            "Does not generate voice candidates yet.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
    )


def apply_create_identity_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _require_project(ctx)
    character_id = _require_character(args)
    preferred_method = _optional_text(args, "preferredMethod")
    workspace = get_voice_workspace(ctx.db, project_id, character_id)
    plan = _voice_identity_plan(workspace, preferred_method=preferred_method)
    draft = save_voice_studio_draft(
        ctx.db,
        project_id,
        character_id,
        {
            "phase": "identity",
            "preferredMethod": plan.get("preferredMethod"),
            "codirectorIdentityPlan": plan,
            "openedFrom": "codirector",
        },
    )
    return {
        "ok": True,
        **_voice_handoff(project_id, character_id),
        "identityPlan": plan,
        "voiceStudioDraft": draft.get("voiceStudioDraft"),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "character_identity.voice_creator.get_voice_workspace"},
    }


def preview_create_profile(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    name = _text(args, "name") or "Untitled Environment"
    return ToolPreview(
        summary=f"Create Voice Environment profile '{name}'.",
        lines=[
            f"characterId: {_text(args, 'characterId') or 'not set'}",
            f"sceneId: {_text(args, 'sceneId') or 'not set'}",
            "Creates a real stored environment profile for this project.",
            "No audio processing starts until preview or render is approved separately.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
    )


def apply_create_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    payload = _profile_create_fields(args)
    payload["projectId"] = _require_project(ctx)
    profile = ve_service.create_profile(ctx.db, ProfileCreateRequest(**payload))
    return {
        "ok": True,
        "profile": profile.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "voice_environment.create_profile"},
    }


def preview_update_profile(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    profile_id = _require_profile(args)
    profile = ve_service.get_profile(ctx.db, profile_id)
    changed = sorted(_profile_update_fields(args).keys())
    return ToolPreview(
        summary=f"Update Voice Environment profile '{profile.name}'.",
        lines=[
            f"profileId: {profile_id}",
            f"fields: {', '.join(changed) if changed else 'none specified'}",
            "Updates the stored environment profile only after approval.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
    )


def apply_update_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    profile_id = _require_profile(args)
    body = ProfileUpdateRequest(**_profile_update_fields(args))
    profile = ve_service.update_profile(ctx.db, profile_id, body)
    return {
        "ok": True,
        "profile": profile.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "voice_environment.update_profile"},
    }


def preview_apply_codirector_recommendation(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    recommendation = ve_service.recommend(
        ctx.db,
        project_id=_require_project(ctx),
        character_id=_require_character(args),
        scene_id=_optional_text(args, "sceneId"),
        location_id=_optional_text(args, "locationId"),
    )
    target = _optional_text(args, "profileId")
    return ToolPreview(
        summary="Apply the current Co-Director Voice Environment recommendation.",
        lines=[
            f"target: {'update existing profile' if target else 'create new profile'}",
            f"space: {recommendation.spaceLabel}",
            f"distance: {recommendation.distanceLabel}",
            "Uses live scene/spatial evidence. No silent render or approval.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
    )


def apply_apply_codirector_recommendation(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    recommendation = ve_service.recommend(
        ctx.db,
        project_id=_require_project(ctx),
        character_id=_require_character(args),
        scene_id=_optional_text(args, "sceneId"),
        location_id=_optional_text(args, "locationId"),
    ).model_dump()
    draft = dict(recommendation.get("profileDraft") or {})
    profile_id = _optional_text(args, "profileId")
    if profile_id:
        profile = ve_service.update_profile(ctx.db, profile_id, ProfileUpdateRequest(**_profile_update_fields(draft)))
        action = "updated"
    else:
        draft["projectId"] = _require_project(ctx)
        profile = ve_service.create_profile(ctx.db, ProfileCreateRequest(**draft))
        action = "created"
    return {
        "ok": True,
        "action": action,
        "recommendation": recommendation,
        "profile": profile.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "voice_environment.recommend"},
    }


def preview_create_preview(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Create a Voice Environment preview render.",
        lines=[
            f"profileId: {_require_profile(args, 'environmentProfileId')}",
            f"recordId: {_text(args, 'performanceRecordId')}",
            f"takeId: {_text(args, 'performanceTakeId')}",
            "Processes dry voice into a preview-ready environment mix without approving it.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
    )


def apply_create_preview(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    render = ve_service.create_render(
        ctx.db,
        project_id=_require_project(ctx),
        character_id=_require_character(args),
        performance_record_id=_text(args, "performanceRecordId"),
        performance_take_id=_text(args, "performanceTakeId"),
        environment_profile_id=_require_profile(args, "environmentProfileId"),
        preview=True,
    )
    return {
        "ok": True,
        "render": render.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "voice_environment.create_render.preview"},
    }


def preview_render(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Render a finalized Voice Environment mix.",
        lines=[
            f"profileId: {_require_profile(args, 'environmentProfileId')}",
            f"recordId: {_text(args, 'performanceRecordId')}",
            f"takeId: {_text(args, 'performanceTakeId')}",
            "Creates processed mix + stems. The dry take remains unchanged.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
    )


def apply_render(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    render = ve_service.create_render(
        ctx.db,
        project_id=_require_project(ctx),
        character_id=_require_character(args),
        performance_record_id=_text(args, "performanceRecordId"),
        performance_take_id=_text(args, "performanceTakeId"),
        environment_profile_id=_require_profile(args, "environmentProfileId"),
        preview=False,
    )
    return {
        "ok": True,
        "render": render.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "voice_environment.create_render"},
    }


def preview_approve(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    render_id = _require_render(args)
    render = ve_service.get_render(ctx.db, render_id)
    return ToolPreview(
        summary="Approve a Voice Environment preview or render.",
        lines=[
            f"renderId: {render_id}",
            f"status: {render.status}",
            f"approved: {bool(render.approved)} -> {_bool(args, 'approved', True)}",
            "Approval does not silently place audio on the Timeline.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
    )


def apply_approve(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    render = ve_service.approve_render(ctx.db, _require_render(args), _bool(args, "approved", True))
    return {
        "ok": True,
        "render": render.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "voice_environment.approve_render"},
    }


def preview_create_alternate(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    profile_id = _require_profile(args)
    profile = ve_service.get_profile(ctx.db, profile_id)
    return ToolPreview(
        summary=f"Create an alternate environment profile from '{profile.name}'.",
        lines=[
            f"profileId: {profile_id}",
            f"name: {_text(args, 'name') or f'{profile.name} Alternate'}",
            "Copies the real stored profile and applies the requested overrides.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
    )


def apply_create_alternate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    base = ve_service.get_profile(ctx.db, _require_profile(args)).model_dump()
    payload = _profile_to_create_payload(base)
    payload.update({k: v for k, v in _profile_update_fields(args).items() if v is not None})
    payload["projectId"] = _require_project(ctx)
    payload["name"] = _text(args, "name") or f"{base.get('name') or 'Environment'} Alternate"
    payload["source"] = "codirector"
    profile = ve_service.create_profile(ctx.db, ProfileCreateRequest(**payload))
    return {
        "ok": True,
        "profile": profile.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "voice_environment.create_profile.alternate"},
    }


def preview_apply_to_scene(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    render_id = _require_render(args)
    scene_id = _text(args, "sceneId")
    if not scene_id:
        raise ValueError("sceneId is required")
    _scene_or_raise(ctx, scene_id)
    return ToolPreview(
        summary="Attach this Voice Environment setup to a scene.",
        lines=[
            f"renderId: {render_id}",
            f"sceneId: {scene_id}",
            "Associates the environment profile with the scene. Scene dialogue stays dry until a Timeline handoff is approved.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
    )


def apply_apply_to_scene(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    result = ve_service.apply_to_scene(ctx.db, _require_render(args), _text(args, "sceneId"))
    return {**result, "persisted": True, "mock": False, "_evidence": {"source": "voice_environment.apply_to_scene"}}


def preview_prepare_timeline(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    proposal = ve_service.prepare_timeline(
        ctx.db,
        _require_render(args),
        scene_id=_optional_text(args, "sceneId"),
        use_processed=_bool(args, "useProcessedMix", True),
    )
    clip = proposal.get("clip") or {}
    return ToolPreview(
        summary="Place the Voice Environment result onto the project Timeline.",
        lines=[
            f"renderId: {_require_render(args)}",
            f"sceneId: {proposal.get('handoff', {}).get('sceneId') or 'not set'}",
            f"assetId: {clip.get('assetId')}",
            "Replaces prior environment-linked clips for the same record on approval.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
    )


def apply_prepare_timeline(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    result = ve_service.place_timeline(
        ctx.db,
        _require_render(args),
        scene_id=_optional_text(args, "sceneId"),
        use_processed=_bool(args, "useProcessedMix", True),
    )
    return {**result, "mock": False, "_evidence": {"source": "voice_environment.place_timeline"}}


def preview_prepare_lipsync(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    render_id = _require_render(args)
    render = ve_service.get_render(ctx.db, render_id)
    record = m410_service.get_record(ctx.db, render.performanceRecordId).model_dump()
    target_scene = _optional_text(args, "sceneId") or record.get("sceneId") or "not set"
    return ToolPreview(
        summary="Bind the dry Voice Performance timing for lip sync.",
        lines=[
            f"renderId: {render_id}",
            f"sceneId: {target_scene}",
            "Uses dry timing only. Environment tails remain excluded from mouth sync.",
            "Updates the scene lip-sync audio target on approval.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
    )


def apply_prepare_lipsync(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    result = ve_service.prepare_lipsync(ctx.db, _require_render(args), scene_id=_optional_text(args, "sceneId"))
    return {**result, "persisted": True, "mock": False, "_evidence": {"source": "voice_environment.prepare_lipsync"}}


def preview_open_audio_studio(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    payload = ve_service.open_audio_studio_payload(ctx.db, _require_render(args))
    return ToolPreview(
        summary="Open Audio Studio with the current Voice Environment handoff.",
        lines=[
            f"renderId: {_require_render(args)}",
            f"workspace: {payload.get('workspace')}",
            "Carries processed mix and stems into Audio Studio after approval.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
    )


def apply_open_audio_studio(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    payload = ve_service.open_audio_studio_payload(ctx.db, _require_render(args))
    return {
        **payload,
        "projectId": _require_project(ctx),
        "uiAction": "open_audio_studio",
        "workspaceUrl": f"/project/{quote(_require_project(ctx))}?workspace=audiostudio",
        "persisted": False,
        "mock": False,
        "_evidence": {"source": "voice_environment.open_audio_studio"},
    }


def preview_request_repair(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    render_id = _require_render(args)
    render = ve_service.get_render(ctx.db, render_id)
    runtime = ve_service.runtime_status()
    return ToolPreview(
        summary="Retry Voice Environment processing from the stored render inputs.",
        lines=[
            f"renderId: {render_id}",
            f"currentStatus: {render.status}",
            f"runtimeStatus: {runtime.get('status')}",
            "Re-runs processing using the same stored record, take, and profile.",
        ],
        resourceKind="project",
        resourceId=_require_project(ctx),
        warnings=[str(render.errorMessage)] if render.errorMessage else [],
    )


def apply_request_repair(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    render = ve_service.get_render(ctx.db, _require_render(args)).model_dump()
    retried = ve_service.create_render(
        ctx.db,
        project_id=_require_project(ctx),
        character_id=str(render.get("characterId") or ""),
        performance_record_id=str(render.get("performanceRecordId") or ""),
        performance_take_id=str(render.get("performanceTakeId") or ""),
        environment_profile_id=str(render.get("environmentProfileId") or ""),
        preview=_bool(args, "preview", False),
    )
    return {
        "ok": True,
        "repairedFromRenderId": render.get("id"),
        "render": retried.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "voice_environment.create_render.repair"},
    }
