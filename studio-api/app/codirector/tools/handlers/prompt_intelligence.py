"""Co-Director tools for Prompt Intelligence enhance / analyze / apply."""

from __future__ import annotations

import json
from typing import Any

from ....db import Scene
from ....services.scene_service import SceneService
from ...errors import TOOL_TARGET_NOT_FOUND, CoDirectorError
from ...prompt_intelligence.models import ModulesEnabled, PromptIntelligenceRequest
from ...prompt_intelligence.pipeline import analyze_only, enhance
from ...prompt_intelligence.profiles import recommendation_banner, resolve_profile
from ..definitions import ToolContext, ToolPreview


def _modules_from_args(args: dict[str, Any]) -> ModulesEnabled:
    raw = args.get("modulesEnabled")
    if isinstance(raw, dict):
        return ModulesEnabled.model_validate(raw)
    language_modules = ["en"]
    if args.get("enableChinese") or args.get("bilingualLayer"):
        language_modules = ["en", "zh"]
    langs = args.get("languageModules")
    if isinstance(langs, list) and langs:
        language_modules = [str(x) for x in langs]
    return ModulesEnabled(
        productionRefinement=bool(args.get("productionRefinement", True)),
        cinematicRefinement=bool(args.get("cinematicRefinement", True)),
        motionRefinement=bool(args.get("motionRefinement", True)),
        audioRefinement=bool(args.get("audioRefinement", True)),
        characterContinuity=bool(args.get("characterContinuity", True)),
        providerOptimization=bool(args.get("providerOptimization", True)),
        languageModules=language_modules,
    )


def _request_from_args(ctx: ToolContext, args: dict[str, Any]) -> PromptIntelligenceRequest:
    creator = str(args.get("creatorPrompt") or args.get("prompt") or "").strip()
    if not creator and ctx.scene_id:
        try:
            scene = SceneService.get(ctx.db, ctx.project_id, ctx.scene_id)
            creator = (scene.prompt or "").strip()
        except Exception:
            pass
    domain = str(args.get("domain") or "video")
    return PromptIntelligenceRequest(
        creatorPrompt=creator,
        domain=domain,  # type: ignore[arg-type]
        providerId=args.get("providerId"),
        modelId=args.get("modelId"),
        modelVersion=args.get("modelVersion"),
        engineId=args.get("engineId"),
        negativePrompt=args.get("negativePrompt"),
        modulesEnabled=_modules_from_args(args),
        languageBalance=str(args.get("languageBalance") or "balanced"),  # type: ignore[arg-type]
        lockedTerms=list(args.get("lockedTerms") or []),
        continuityHints=list(args.get("continuityHints") or []),
        characterNames=list(args.get("characterNames") or []),
        projectId=ctx.project_id,
        sceneId=args.get("sceneId") or ctx.scene_id,
        manuallyOverridden=bool(args.get("manuallyOverridden")),
        existingFinalPrompt=args.get("existingFinalPrompt"),
    )


async def prompt_enhance(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    req = _request_from_args(ctx, args)
    if not req.creatorPrompt:
        return {"ok": False, "error": {"code": "FINAL_PROMPT_EMPTY", "message": "No creator prompt available."}}
    result = enhance(req)
    profile = resolve_profile(
        provider_id=req.providerId,
        model_id=req.modelId,
        model_version=req.modelVersion,
        engine_id=req.engineId,
        domain=req.domain,
    )
    record = result.record.model_dump(mode="json")
    record["originalPrompt"] = record.get("creatorPrompt", "")
    record["chineseEnhancement"] = (record.get("languageEnhancements") or {}).get("zh", "")
    return {
        "ok": result.ok,
        "record": record,
        "profileRecommendation": result.profileRecommendation or recommendation_banner(profile),
        "error": result.error,
        "_summary": f"Prompt Intelligence: quality {(record.get('qualityReport') or {}).get('overall', '—')}/100",
    }


async def prompt_analyze(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    req = _request_from_args(ctx, args)
    if not req.creatorPrompt:
        return {"ok": False, "error": {"code": "FINAL_PROMPT_EMPTY", "message": "No creator prompt available."}}
    out = analyze_only(req)
    out["_summary"] = f"Prompt quality {out.get('qualityReport', {}).get('overall', '—')}/100"
    return out


async def prompt_benchmark_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ...prompt_intelligence.benchmark_runner import plan_suite

    suite_id = str(args.get("suiteId") or "image-core")
    provider_id = str(args.get("providerId") or "comfyui")
    plan = plan_suite(
        suite_id,
        provider_id=provider_id,
        model_revision=str(args.get("modelRevision") or "default"),
        samples_per_strategy=int(args.get("samplesPerStrategy") or 1),
    )
    return {"ok": True, "plan": plan.model_dump(mode="json"), "_summary": f"Plan {plan.estimatedJobs} jobs for {suite_id}"}


async def prompt_benchmark_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ...prompt_intelligence.benchmark_runner import suite_status

    suite_run_id = str(args.get("suiteRunId") or "")
    if not suite_run_id:
        return {"ok": False, "error": {"code": "SUITE_RUN_NOT_FOUND", "message": "suiteRunId required"}}
    return suite_status(suite_run_id)


async def prompt_compare_results(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ...prompt_intelligence.benchmark_store import list_reviews, load_review

    comparison_id = args.get("comparisonId")
    if comparison_id:
        review = load_review(str(comparison_id))
        if not review:
            return {"ok": False, "error": {"code": "REVIEW_NOT_FOUND"}}
        payload = review.model_dump(mode="json")
        if not review.submitted:
            payload["strategyMap"] = {}
        return {"ok": True, "review": payload}
    return {"ok": True, "reviews": [r.model_dump(mode="json") for r in list_reviews()]}


async def prompt_recommend_strategy(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ...prompt_intelligence.recommendation import resolve_strategy_recommendation

    rec = resolve_strategy_recommendation(
        domain=str(args.get("domain") or "video"),
        category=str(args.get("category") or "general"),
        provider_id=args.get("providerId"),
        model_revision=str(args.get("modelRevision") or "default"),
        strategy_mode=str(args.get("strategyMode") or "recommend"),  # type: ignore[arg-type]
        manual_override=args.get("manualOverride"),
        project_prefs=args.get("projectPrefs") if isinstance(args.get("projectPrefs"), dict) else None,
    )
    return {"ok": True, "strategyRecommendation": rec.model_dump(mode="json"), "_summary": f"Recommend {rec.strategy}"}


async def prompt_review_evidence(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ...prompt_intelligence.benchmark_store import list_evidence, load_evidence

    if args.get("providerId") and args.get("domain") and args.get("category"):
        ev = load_evidence(
            str(args["providerId"]),
            str(args.get("modelRevision") or "default"),
            str(args["domain"]),
            str(args["category"]),
        )
        return {"ok": True, "evidence": ev.model_dump(mode="json") if ev else None}
    return {"ok": True, "evidence": [e.model_dump(mode="json") for e in list_evidence()]}


async def prompt_certification_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ...prompt_intelligence.benchmark_certify import certification_status

    return certification_status(
        provider_id=str(args.get("providerId") or ""),
        model_revision=str(args.get("modelRevision") or "default"),
        domain=str(args.get("domain") or "video"),
        category=str(args.get("category") or "general"),
    )


def preview_prompt_benchmark_run(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    suite_id = str(args.get("suiteId") or "image-core")
    provider_id = str(args.get("providerId") or "comfyui")
    dry = bool(args.get("dryRun", True))
    return ToolPreview(
        summary=f"Start Prompt Intelligence V2 suite run {suite_id} on {provider_id}",
        lines=[
            f"dryRun={dry}",
            f"samplesPerStrategy={args.get('samplesPerStrategy') or 1}",
            "Queue-safe; pause/resume/cancel available",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=[] if dry else ["Live generation may consume GPU and disk."],
    )


def apply_prompt_benchmark_run(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ...prompt_intelligence.benchmark_runner import start_suite_run

    suite_run = start_suite_run(
        str(args.get("suiteId") or "image-core"),
        provider_id=str(args.get("providerId") or "comfyui"),
        model_revision=str(args.get("modelRevision") or "default"),
        samples_per_strategy=int(args.get("samplesPerStrategy") or 1),
        dry_run=bool(args.get("dryRun", True)),
    )
    return {"suiteRun": suite_run.model_dump(mode="json"), "suiteRunId": suite_run.suiteRunId}


def preview_prompt_promote_strategy(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Promote strategy {args.get('strategy')} for {args.get('domain')}/{args.get('category')}",
        lines=[
            f"provider={args.get('providerId')}",
            "Requires ≥3 samples unless force=true (force is test-only)",
            "Writes evidence overlay — does not mutate historical generations",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=["Human review should precede creative certification."],
    )


def apply_prompt_promote_strategy(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ...prompt_intelligence.benchmark_certify import promote_strategy
    from ...prompt_intelligence.errors import PromptIntelligenceError

    try:
        return promote_strategy(
            provider_id=str(args.get("providerId") or ""),
            model_revision=str(args.get("modelRevision") or "default"),
            domain=str(args.get("domain") or "video"),
            category=str(args.get("category") or "general"),
            strategy=str(args.get("strategy") or "refined-english"),
            force=bool(args.get("force")),
        )
    except PromptIntelligenceError as exc:
        return {"ok": False, "error": exc.to_dict()}


def preview_prompt_rollback_strategy(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Rollback certification for {args.get('domain')}/{args.get('category')}",
        lines=["Restores prior evidence overlay or resets to not_tested"],
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=[],
    )


def apply_prompt_rollback_strategy(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ...prompt_intelligence.benchmark_certify import rollback_strategy
    from ...prompt_intelligence.errors import PromptIntelligenceError

    try:
        return rollback_strategy(
            provider_id=str(args.get("providerId") or ""),
            model_revision=str(args.get("modelRevision") or "default"),
            domain=str(args.get("domain") or "video"),
            category=str(args.get("category") or "general"),
        )
    except PromptIntelligenceError as exc:
        return {"ok": False, "error": exc.to_dict()}


def preview_prompt_apply_enhancement(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    scene_id = str(args.get("sceneId") or ctx.scene_id or "")
    if not scene_id:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "sceneId is required to apply a prompt enhancement.",
            recoverable=False,
            recommended_action="select_scene",
        )
    try:
        scene = SceneService.get(ctx.db, ctx.project_id, scene_id)
    except Exception as exc:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "Scene not found.",
            details={"sceneId": scene_id},
            recoverable=False,
            recommended_action="none",
        ) from exc

    req = _request_from_args(ctx, {**args, "sceneId": scene_id})
    if not req.creatorPrompt:
        req.creatorPrompt = (scene.prompt or "").strip()
    result = enhance(req)
    final = result.record.finalProviderPrompt
    return ToolPreview(
        summary=f"Apply Prompt Intelligence final prompt to scene “{scene.name}”.",
        lines=[
            f"Original preserved in metadata ({len(result.record.creatorPrompt)} chars)",
            f"Final provider prompt: {final[:220]}",
            f"Profile: {result.record.promptProfileId}@{result.record.promptProfileVersion}",
            f"Chinese layer: {'yes' if result.record.languageEnhancements.get('zh') else 'no'}",
        ],
        resourceKind="scene",
        resourceId=scene.id,
        warnings=[] if result.ok else ["Enhancement used English-only fallback."],
        # Stash for apply via arguments re-enhance (apply re-runs for determinism)
    )


def apply_prompt_apply_enhancement(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id = str(args.get("sceneId") or ctx.scene_id or "")
    scene = SceneService.get(ctx.db, ctx.project_id, scene_id)
    req = _request_from_args(ctx, {**args, "sceneId": scene_id})
    if not req.creatorPrompt:
        req.creatorPrompt = (scene.prompt or "").strip()
    # Prefer explicit final if provided (manual apply path)
    explicit_final = str(args.get("finalProviderPrompt") or "").strip()
    if explicit_final:
        final = explicit_final
        record = enhance(req).record
        record.finalProviderPrompt = final
        record.manuallyOverridden = bool(args.get("manuallyOverridden"))
    else:
        result = enhance(req)
        record = result.record
        final = record.finalProviderPrompt

    # Persist working prompt as final for generation; keep intelligence record on director_json
    director: dict[str, Any] = {}
    raw = scene.director_json
    if isinstance(raw, str) and raw.strip():
        try:
            director = json.loads(raw)
        except Exception:
            director = {}
    elif isinstance(raw, dict):
        director = dict(raw)
    director["promptIntelligence"] = record.model_dump(mode="json")
    # Never overwrite creator original inside the record
    previous = scene.prompt or ""
    scene = SceneService.update(
        ctx.db,
        ctx.project_id,
        scene.id,
        {"prompt": final, "director_json": json.dumps(director, ensure_ascii=False)},
    )
    return {
        "updated": "scene.prompt+promptIntelligence",
        "previousLength": len(previous),
        "finalLength": len(final),
        "creatorPrompt": record.creatorPrompt,
        "promptIntelligence": record.model_dump(mode="json"),
        "sceneId": scene.id,
    }
