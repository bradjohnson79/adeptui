"""M4.10 Co-Director voice.* tools for proposal-first performance direction."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from ....db import Scene
from ....voice_performance import m410_service
from ....voice_performance.m410_models import VoicePerformanceRecordRow
from ....voice_performance.runtime import index_tts2
from ..definitions import ToolContext, ToolPreview


def _record_id(args: dict[str, Any]) -> str:
    record_id = str(args.get("recordId") or "").strip()
    if not record_id:
        raise ValueError("recordId is required")
    return record_id


def _string(args: dict[str, Any], key: str) -> str:
    return str(args.get(key) or "").strip()


def _int(args: dict[str, Any], key: str, default: int = 0) -> int:
    value = args.get(key)
    if value in (None, ""):
        return default
    return int(value)


def _bool(args: dict[str, Any], key: str, default: bool = False) -> bool:
    value = args.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _json_object_arg(args: dict[str, Any], key: str) -> dict[str, Any]:
    value = args.get(key)
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{key} must be valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"{key} must decode to a JSON object.")
        return parsed
    raise ValueError(f"{key} must be a JSON object or JSON string.")


def _runtime_context() -> dict[str, Any]:
    runtime = m410_service.get_runtime_status()
    inspection = index_tts2.get_index_tts2_runtime().inspect_installation()
    state = str(inspection.get("state") or inspection.get("status") or "").strip() or (
        "ready" if runtime.get("ready") else "not_installed"
    )
    return {
        **runtime,
        "state": state,
        "status": state,
        "message": inspection.get("message") or runtime.get("message"),
        "runtimeReady": bool(inspection.get("runtimeReady") or runtime.get("ready")),
    }


def _scene_progression(index: int, total: int, scene_arc_id: str | None) -> dict[str, Any]:
    if total <= 1:
        label = "standalone beat"
    else:
        ratio = index / max(total - 1, 1)
        if ratio <= 0.2:
            label = "opening pressure"
        elif ratio <= 0.5:
            label = "rising complication"
        elif ratio <= 0.8:
            label = "turning pressure"
        else:
            label = "late-scene payoff"
    return {"index": index + 1, "total": total, "sceneProgression": label, "sceneArcId": scene_arc_id}


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


def _plan_context(record: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {
        "sceneId": record.get("sceneId"),
        "scriptElementId": record.get("scriptElementId"),
        "characterId": record.get("characterId"),
        "sceneArcId": record.get("sceneArcId"),
    }
    for key in ("parenthetical", "presetId", "sceneProgression", "sceneArcId"):
        value = args.get(key)
        if value not in (None, ""):
            context[key] = value
    return context


def _base_plan(record: dict[str, Any]) -> dict[str, Any]:
    plan = record.get("performancePlan") or {}
    if isinstance(plan, dict) and plan:
        return copy.deepcopy(plan)
    return m410_service.build_codirector_performance_plan(
        str(record.get("dialogueText") or ""),
        {
            "sceneId": record.get("sceneId"),
            "scriptElementId": record.get("scriptElementId"),
            "characterId": record.get("characterId"),
            "sceneArcId": record.get("sceneArcId"),
        },
    )


def _dialogue_metrics(dialogue_text: str) -> dict[str, Any]:
    words = re.findall(r"\b[\w']+\b", dialogue_text)
    emphatic_words = re.findall(r"\b[A-Z]{3,}\b", dialogue_text)
    sentence_chunks = [chunk for chunk in re.split(r"[.!?]+", dialogue_text) if chunk.strip()]
    return {
        "characterCount": len(dialogue_text),
        "wordCount": len(words),
        "sentenceCount": len(sentence_chunks) or (1 if dialogue_text.strip() else 0),
        "hasQuestion": "?" in dialogue_text,
        "hasExclamation": "!" in dialogue_text,
        "hasTrailingPause": "..." in dialogue_text,
        "emphasisWords": emphatic_words,
    }


def _suggested_take_count(dialogue_text: str) -> int:
    metrics = _dialogue_metrics(dialogue_text)
    if metrics["wordCount"] >= 18 or metrics["hasExclamation"] or metrics["hasTrailingPause"]:
        return 3
    if metrics["wordCount"] >= 8 or metrics["hasQuestion"]:
        return 2
    return 1


async def performance_context(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record_id = _record_id(args)
    record = _record_out(ctx, record_id)
    takes = _takes_out(ctx, record_id)
    approved_take = _approved_take(takes)
    runtime = _runtime_context()
    return {
        "ok": True,
        "recordId": record_id,
        "record": record,
        "takes": takes.get("takes") or [],
        "approvedTake": approved_take,
        "runtime": runtime,
        "statusSummary": {
            "directionMode": record.get("directionMode"),
            "hasApprovedTake": bool(approved_take),
            "takeCount": len(takes.get("takes") or []),
            "runtimeState": runtime.get("state"),
            "runtimeReady": runtime.get("ready"),
            "timelinePlaced": bool(record.get("timelineLinkage")),
            "lipsyncPrepared": bool(record.get("lipsyncLinkage")),
        },
        "mock": False,
        "_evidence": {"source": "voice_performance.m410_service"},
    }


async def analyze_dialogue(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    dialogue_text = _string(args, "dialogueText")
    if not dialogue_text:
        raise ValueError("dialogueText is required")
    context = {
        key: args.get(key)
        for key in ("parenthetical", "presetId", "sceneProgression", "sceneArcId")
        if args.get(key) not in (None, "")
    }
    plan = m410_service.build_codirector_performance_plan(dialogue_text, context)
    metrics = _dialogue_metrics(dialogue_text)
    return {
        "ok": True,
        "dialogueText": dialogue_text,
        "analysis": {
            **metrics,
            "recommendedTakeCount": _suggested_take_count(dialogue_text),
            "lineShape": "interrogative"
            if metrics["hasQuestion"]
            else "emphatic"
            if metrics["hasExclamation"]
            else "reflective"
            if metrics["hasTrailingPause"]
            else "declarative",
        },
        "proposedPlan": plan,
        "runtime": _runtime_context(),
        "mock": False,
        "_evidence": {"source": "voice_performance.build_codirector_performance_plan"},
    }


async def create_performance_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record_id = _record_id(args)
    record = _record_out(ctx, record_id)
    context = _plan_context(record, args)
    plan = m410_service.build_codirector_performance_plan(str(record.get("dialogueText") or ""), context)
    return {
        "ok": True,
        "recordId": record_id,
        "currentDirectionMode": record.get("directionMode"),
        "context": context,
        "proposedPlan": plan,
        "mock": False,
        "_evidence": {"source": "voice_performance.build_codirector_performance_plan"},
    }


async def create_scene_performance_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id = _string(args, "sceneId")
    if not scene_id:
        raise ValueError("sceneId is required")
    rows = (
        ctx.db.query(VoicePerformanceRecordRow)
        .filter(
            VoicePerformanceRecordRow.project_id == ctx.project_id,
            VoicePerformanceRecordRow.scene_id == scene_id,
        )
        .order_by(VoicePerformanceRecordRow.created_at.asc(), VoicePerformanceRecordRow.id.asc())
        .all()
    )
    plans: list[dict[str, Any]] = []
    total = len(rows)
    for index, row in enumerate(rows):
        progression = _scene_progression(index, total, row.scene_arc_id)
        plan = m410_service.build_codirector_performance_plan(
            row.dialogue_text,
            {
                **progression,
                "sceneId": row.scene_id,
                "scriptElementId": row.script_element_id,
                "characterId": row.character_id,
                "sceneArcId": row.scene_arc_id,
            },
        )
        plans.append(
            {
                "recordId": row.id,
                "characterId": row.character_id,
                "scriptElementId": row.script_element_id,
                "dialogueText": row.dialogue_text,
                "sceneProgression": progression,
                "proposedPlan": plan,
            }
        )
    return {
        "ok": True,
        "sceneId": scene_id,
        "recordCount": total,
        "plans": plans,
        "mock": False,
        "_evidence": {"source": "voice_performance.scene_batch_planning"},
    }


async def suggest_take_variations(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record = _record_out(ctx, _record_id(args))
    base_plan = _base_plan(record)
    count = max(1, min(5, _int(args, "count", 3)))
    templates = [
        ("Grounded", {"intensity": "low", "delivery": "grounded and cinematic", "pacing": "steady"}),
        ("Intimate", {"intensity": "low", "delivery": "intimate and restrained", "pacing": "slower"}),
        ("Heightened", {"intensity": "high", "delivery": "sharper emotional lift", "pacing": "faster"}),
        ("Measured Turn", {"intensity": "medium", "delivery": "controlled but conflicted", "pacing": "steady"}),
        ("Quiet Resolve", {"intensity": "medium", "delivery": "quietly determined", "pacing": "slower"}),
    ]
    variations: list[dict[str, Any]] = []
    for index, (label, overrides) in enumerate(templates[:count], start=1):
        plan = copy.deepcopy(base_plan)
        plan.update(overrides)
        note_suffix = f"Variation {index}: {label.lower()} read. Keep the approved character voice identity intact."
        existing_notes = str(plan.get("notes") or "").strip()
        plan["notes"] = f"{existing_notes} {note_suffix}".strip()
        variations.append({"label": label, "takeNumberHint": index, "performancePlan": plan})
    return {
        "ok": True,
        "recordId": record.get("id"),
        "approvedTakeId": record.get("approvedTakeId"),
        "variationCount": len(variations),
        "variations": variations,
        "mock": False,
        "_evidence": {"source": "voice_performance.plan_variations"},
    }


async def compare_takes(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record_id = _record_id(args)
    take_ids_csv = _string(args, "takeIdsCsv")
    take_ids = [value.strip() for value in take_ids_csv.split(",") if value.strip()] if take_ids_csv else None
    takes = _takes_out(ctx, record_id)
    comparison = m410_service.compare_takes(ctx.db, record_id, take_ids=take_ids)
    return {**comparison, "takes": takes.get("takes") or [], "_evidence": {"source": "voice_performance.compare_takes"}}


async def adjust_performance(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record = _record_out(ctx, _record_id(args))
    plan = _base_plan(record)
    preset_id = _string(args, "presetId")
    if preset_id:
        preset_plan = m410_service.build_codirector_performance_plan(
            str(record.get("dialogueText") or ""),
            {"presetId": preset_id, "sceneArcId": record.get("sceneArcId")},
        )
        for key in ("emotionVector", "intensity", "delivery", "pacing", "breath", "notes", "summary"):
            if key in preset_plan:
                plan[key] = copy.deepcopy(preset_plan[key])
    explicit_updates = {
        "intensity": _string(args, "intensity"),
        "delivery": _string(args, "delivery"),
        "pacing": _string(args, "pacing"),
        "breath": _string(args, "breath"),
        "summary": _string(args, "summary"),
    }
    for key, value in explicit_updates.items():
        if value:
            plan[key] = value
    notes = _string(args, "notes")
    if notes:
        existing_notes = str(plan.get("notes") or "").strip()
        plan["notes"] = f"{existing_notes} {notes}".strip()
    emotion_vector = _json_object_arg(args, "emotionVectorJson")
    if emotion_vector:
        plan["emotionVector"] = emotion_vector
    return {
        "ok": True,
        "recordId": record.get("id"),
        "currentPlan": record.get("performancePlan") or {},
        "adjustedPlan": plan,
        "mock": False,
        "_evidence": {"source": "voice_performance.adjust_performance"},
    }


async def prepare_timeline_dialogue(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record_id = _record_id(args)
    return {
        **m410_service.prepare_timeline_dialogue(
            ctx.db,
            record_id,
            track_id=_string(args, "trackId") or "dialogue-main",
            start_ms=_int(args, "startMs", 0),
        ),
        "_evidence": {"source": "voice_performance.prepare_timeline_dialogue"},
    }


async def prepare_lipsync(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record = _record_out(ctx, _record_id(args))
    takes = _takes_out(ctx, str(record.get("id") or ""))
    approved_take = _approved_take(takes)
    if not approved_take:
        raise ValueError("An approved take is required before preparing lip sync.")
    set_scene_audio_asset = _bool(args, "setSceneAudioAsset", True)
    scene_id = str(record.get("sceneId") or "").strip()
    scene = ctx.db.get(Scene, scene_id) if scene_id else None
    would_replace = False
    if scene:
        if scene.lipsync_audio_asset_id and scene.lipsync_audio_asset_id != approved_take.get("audioAssetId"):
            would_replace = True
        if set_scene_audio_asset and scene.audio_asset_id and scene.audio_asset_id != approved_take.get("audioAssetId"):
            would_replace = True
    proposal = {
        "sceneId": scene_id or None,
        "recordId": record.get("id"),
        "takeId": approved_take.get("id"),
        "audioAssetId": approved_take.get("audioAssetId"),
        "setSceneAudioAsset": set_scene_audio_asset,
        "wouldUpdateScene": bool(scene),
        "wouldReplace": would_replace,
    }
    return {
        "ok": True,
        "recordId": record.get("id"),
        "approvedTakeId": approved_take.get("id"),
        "lipsyncProposal": proposal,
        "mock": False,
        "_evidence": {"source": "voice_performance.prepare_lipsync"},
    }


def preview_apply_performance_plan(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    record_id = _record_id(args)
    mode = _string(args, "mode") or "current"
    return ToolPreview(
        summary="Apply a proposed M4.10 performance plan to the selected dialogue record.",
        lines=[
            f"recordId: {record_id}",
            f"mode: {mode}",
            "Updates direction metadata only. Does not auto-generate takes.",
            "Creator confirmation is required before the active plan changes.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_apply_performance_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record_id = _record_id(args)
    performance_plan = _json_object_arg(args, "performancePlanJson")
    mode = _string(args, "mode") or None
    emotion_source = _string(args, "emotionSource") or None
    emotion_vector = _json_object_arg(args, "emotionVectorJson") or None
    record = m410_service.apply_performance_plan(
        ctx.db,
        record_id,
        performance_plan,
        mode=mode,  # type: ignore[arg-type]
        emotion_source=emotion_source,
        emotion_vector=emotion_vector,
    )
    return {
        "ok": True,
        "record": record.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "voice_performance.apply_performance_plan"},
    }


def preview_approve_take(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    record_id = _record_id(args)
    take_id = _string(args, "takeId")
    if not take_id:
        raise ValueError("takeId is required")
    return ToolPreview(
        summary="Approve one generated M4.10 take as the creator-selected performance.",
        lines=[
            f"recordId: {record_id}",
            f"takeId: {take_id}",
            "Marks this take as approved for the record.",
            "Does not replace Timeline clips automatically.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_approve_take(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record_id = _record_id(args)
    take_id = _string(args, "takeId")
    if not take_id:
        raise ValueError("takeId is required")
    return {
        **m410_service.approve_take(ctx.db, record_id, take_id, approved_by=_string(args, "approvedBy") or "owner"),
        "_evidence": {"source": "voice_performance.approve_take"},
    }


def preview_replace_timeline_dialogue(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    record_id = _record_id(args)
    proposal = m410_service.prepare_timeline_dialogue(
        ctx.db,
        record_id,
        track_id=_string(args, "trackId") or "dialogue-main",
        start_ms=_int(args, "startMs", 0),
    )
    lines = [
        f"recordId: {record_id}",
        f"trackId: {proposal.get('trackId')}",
        f"startMs: {proposal.get('clip', {}).get('startMs')}",
        "Replaces existing dialogue clips for the same record/scene match on approval.",
    ]
    if proposal.get("wouldReplace"):
        lines.append(f"existingClipIds: {', '.join(proposal.get('existingClipIds') or [])}")
    return ToolPreview(
        summary="Replace Timeline dialogue placement with the currently approved M4.10 take.",
        lines=lines,
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=["Existing matching dialogue clips will be removed from the target track."]
        if proposal.get("wouldReplace")
        else [],
    )


def apply_replace_timeline_dialogue(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    record_id = _record_id(args)
    return {
        **m410_service.place_timeline_dialogue(
            ctx.db,
            record_id,
            track_id=_string(args, "trackId") or "dialogue-main",
            start_ms=_int(args, "startMs", 0),
            confirm_replace=True,
        ),
        "_evidence": {"source": "voice_performance.place_timeline_dialogue"},
    }
