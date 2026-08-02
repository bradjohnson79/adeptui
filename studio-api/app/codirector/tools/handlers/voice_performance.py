"""Co-Director tools for Voice Performance — grounded, approval-gated mutations."""

from __future__ import annotations

from typing import Any

from ..definitions import ToolContext, ToolPreview


def _require_character(ctx: ToolContext, args: dict[str, Any]) -> str:
    cid = str(args.get("characterId") or "").strip()
    if not cid:
        raise ValueError("characterId is required")
    return cid


async def get_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....voice_performance.production_gate import evaluate_m42_voice_performance_gate
    from ....voice_performance.runtime import index_tts2
    from ....voice_performance import m410_service

    gate = evaluate_m42_voice_performance_gate()
    runtime = m410_service.get_runtime_status()
    inspection = index_tts2.get_index_tts2_runtime().inspect_installation()
    runtime_state = str(inspection.get("state") or inspection.get("status") or "").strip() or (
        "ready" if runtime.get("ready") else "not_installed"
    )
    return {
        "ok": True,
        "voicePerformanceGo": gate.get("voicePerformanceGo"),
        "phase": "M42-W44",
        "mock": False,
        "indexTts2Runtime": {
            **runtime,
            "state": runtime_state,
            "status": runtime_state,
            "message": inspection.get("message") or runtime.get("message"),
            "runtimeReady": bool(inspection.get("runtimeReady") or runtime.get("ready")),
        },
        "_evidence": {"source": "voice_performance.production_gate"},
    }


async def get_character_readiness(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....voice_performance.compiler import character_readiness

    character_id = _require_character(ctx, args)
    out = character_readiness(ctx.db, ctx.project_id, character_id, request=getattr(ctx, "request", None))
    return {**out, "mock": False, "_evidence": {"source": "voice_performance.compiler.readiness"}}


async def parse_markup(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....voice_performance.compiler import compile_performance

    character_id = _require_character(ctx, args)
    source = str(args.get("sourceText") or args.get("markup") or "")
    out = compile_performance(
        ctx.db,
        project_id=ctx.project_id,
        character_id=character_id,
        source_text=source,
        voice_version_id=str(args.get("voiceVersionId") or "") or None,
        request=getattr(ctx, "request", None),
    )
    return {**out.model_dump(), "_evidence": {"source": "voice_performance.compiler"}}


async def preview_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return await parse_markup(ctx, args)


async def validate_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return await parse_markup(ctx, args)


async def get_provider_translation(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....voice_performance import service as vp

    plan_id = str(args.get("planId") or "").strip()
    if not plan_id:
        raise ValueError("planId is required")
    out = vp.provider_translation_for_plan(ctx.db, plan_id, provider_key=str(args.get("provider") or "") or None)
    return {**out, "mock": False, "_evidence": {"source": "voice_performance.provider_translation"}}


async def get_pronunciation_issues(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = await parse_markup(ctx, args)
    issues = [i for i in (parsed.get("issues") or []) if "pronunci" in str(i.get("code") or "").lower() or "pronunci" in str(i.get("message") or "").lower()]
    return {"ok": True, "issues": issues, "mock": False, "_evidence": {"source": "voice_performance.parser"}}


async def get_reaction_coverage(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....voice_performance.compiler import resolve_character_context

    character_id = _require_character(ctx, args)
    ctx_data = resolve_character_context(ctx.db, ctx.project_id, character_id)
    voice = ctx_data.get("voice") or {}
    reactions = voice.get("reactions") or []
    return {
        "ok": True,
        "voiceVersionId": voice.get("id"),
        "reactionCount": len(reactions),
        "reactions": reactions,
        "mock": False,
        "_evidence": {"source": "character_identity.voice"},
    }


async def open_workspace(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    return {
        "ok": True,
        "uiAction": "open_voice_performance",
        "characterId": character_id,
        "projectId": ctx.project_id,
        "_evidence": {"source": "voice_performance.ui"},
    }


def preview_generate_segments(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Generate segmented dialogue performance from an immutable plan.",
        lines=[
            f"planId: {args.get('planId')}",
            "Uses approved Character Voice Version — does not invent a new voice.",
            "Registers real audio assets per segment. Failed segments block assembly.",
            "Requires explicit owner approval before this mutation executes.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_generate_segments(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....voice_performance import service as vp

    plan_id = str(args.get("planId") or "").strip()
    if not plan_id:
        raise ValueError("planId is required")
    plan = vp.generate_segments(
        ctx.db,
        plan_id,
        allow_kokoro_fallback=bool(args.get("allowKokoroFallback")),
        request=getattr(ctx, "request", None),
    )
    return {
        "ok": True,
        "plan": plan.model_dump(),
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "voice_performance.generate"},
    }


def preview_retry_segment(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Retry a failed segment (creates new lineage — no overwrite).",
        lines=[f"segmentId: {args.get('segmentId')}", "Parent segment retained in history."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_retry_segment(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....voice_performance import service as vp

    segment_id = str(args.get("segmentId") or "").strip()
    if not segment_id:
        raise ValueError("segmentId is required")
    plan = vp.retry_segment(ctx.db, segment_id, allow_kokoro_fallback=bool(args.get("allowKokoroFallback")))
    return {"ok": True, "plan": plan.model_dump(), "persisted": True, "mock": False}


def preview_refine_segment(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Refine selected segment (new version lineage).",
        lines=[f"segmentId: {args.get('segmentId')}", f"notes: {args.get('refinement') or ''}"],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_refine_segment(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    # Refine = retry with optional text override stored as new lineage
    return apply_retry_segment(ctx, args)


def preview_approve_take(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Owner-approve a performance segment take.",
        lines=["Does not auto-place on Timeline.", f"segmentId: {args.get('segmentId')}"],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_approve_take(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....voice_performance import service as vp

    segment_id = str(args.get("segmentId") or "").strip()
    if not segment_id:
        raise ValueError("segmentId is required")
    return {**vp.approve_segment(ctx.db, segment_id, approved=True), "_evidence": {"source": "voice_performance.approve"}}


def preview_assemble_dialogue(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Assemble ready/approved segments into a composite dialogue asset.",
        lines=["Blocked if any failed segment lacks a successful retry.", "Retains individual segment assets."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_assemble_dialogue(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....voice_performance import service as vp

    plan_id = str(args.get("planId") or "").strip()
    if not plan_id:
        raise ValueError("planId is required")
    return {**vp.assemble_plan(ctx.db, plan_id), "_evidence": {"source": "voice_performance.assemble"}}


def preview_place_on_timeline(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Place approved assembly dialogue clips on the canonical Timeline.",
        lines=[
            f"assemblyId: {args.get('assemblyId')}",
            "Persists into project.settings_json timeline dialogueTracks.",
            "Does not invent voice identity.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_place_on_timeline(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....voice_performance import service as vp

    assembly_id = str(args.get("assemblyId") or "").strip()
    if not assembly_id:
        raise ValueError("assemblyId is required")
    return {
        **vp.place_on_timeline(
            ctx.db,
            assembly_id,
            timeline_id=str(args.get("timelineId") or "") or None,
            start_ms=int(args.get("startMs") or 0),
        ),
        "_evidence": {"source": "voice_performance.timeline"},
    }


def preview_compare_takes(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Compare performance takes (read-only preview of lineage).",
        lines=["Human audition remains authoritative.", f"planId: {args.get('planId')}"],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_compare_takes(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....voice_performance import service as vp

    plan_id = str(args.get("planId") or "").strip()
    if not plan_id:
        raise ValueError("planId is required")
    plan = vp.get_plan(ctx.db, plan_id)
    segs = [s.model_dump() for s in plan.segments]
    return {
        "ok": True,
        "takes": segs,
        "persisted": False,
        "mock": False,
        "_evidence": {"source": "voice_performance.compare"},
    }
