"""Wave 6P media execution handlers — ProductionIntent → Resolver → QueueWorker."""

from __future__ import annotations

from typing import Any, Optional

from ...production_intent.approval import build_disclosure, evaluate_approval_requirement
from ...production_intent.compiler import compile_intent
from ...production_intent.execute import IntentExecutionError, enqueue_intent, preflight_intent
from ...production_intent.recovery import classify_failure
from ...production_intent.store import get_intent_store
from ..definitions import ToolContext, ToolPreview


def _assets(args: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("sourceAssetId", "startAssetId", "middleAssetId", "endAssetId", "audioAssetId"):
        v = args.get(key)
        if v:
            out.append(str(v))
    for a in args.get("sourceAssets") or []:
        if a and str(a) not in out:
            out.append(str(a))
    # Prefer ordered three-frame
    start = args.get("startAssetId")
    mid = args.get("middleAssetId")
    end = args.get("endAssetId")
    if start and mid and end:
        return [str(start), str(mid), str(end)]
    if start and end and not mid:
        return [str(start), str(end)]
    return out


def _build_intent(ctx: ToolContext, args: dict[str, Any], *, operation: str, tool_id: str):
    refs = []
    for role, key in (("start", "startAssetId"), ("middle", "middleAssetId"), ("end", "endAssetId")):
        if args.get(key):
            refs.append({"role": role, "assetId": str(args[key])})
    meta = {
        "audioAssetId": args.get("audioAssetId"),
        "characterId": args.get("characterId"),
        "editOp": args.get("editOp"),
        "jobId": args.get("jobId"),
        "parentIntentId": args.get("parentIntentId"),
        "ingredients": args.get("ingredients"),
    }
    return compile_intent(
        project_id=ctx.project_id,
        operation=operation,
        source_surface="codirector",
        scene_id=str(args.get("sceneId") or ctx.scene_id or "") or None,
        shot_id=str(args["shotId"]) if args.get("shotId") else None,
        prompt=str(args.get("prompt") or args.get("text") or args.get("transcript") or ""),
        objective=str(args.get("objective") or args.get("prompt") or operation),
        references=refs,
        source_assets=_assets(args),
        engine_preference=str(args["engine"]) if args.get("engine") else None,
        workflow_preference=str(args["workflowKey"]) if args.get("workflowKey") else None,
        quality_profile=str(args.get("qualityProfile") or "standard"),
        duration=float(args["durationSec"]) if args.get("durationSec") is not None else None,
        aspect_ratio=str(args["aspectRatio"]) if args.get("aspectRatio") else None,
        target_placement=args.get("targetPlacement")
        if isinstance(args.get("targetPlacement"), dict)
        else {
            "startSec": args.get("startSec"),
            "durationSec": args.get("durationSec"),
            "track": args.get("track") or args.get("kind"),
            "sceneId": args.get("sceneId"),
        },
        tool_id=tool_id,
        handoff_id=str(args["handoffId"]) if args.get("handoffId") else None,
        parent_intent_id=str(args["parentIntentId"]) if args.get("parentIntentId") else None,
        plan_id=str(args["planId"]) if args.get("planId") else None,
        plan_step_id=str(args["planStepId"]) if args.get("planStepId") else None,
        metadata={k: v for k, v in meta.items() if v is not None},
        db=ctx.db,
    )


def _preview_for(operation: str, args: dict[str, Any], disclosure: dict[str, Any]) -> ToolPreview:
    lines = [
        f"Operation: {operation}",
        f"Capability: {disclosure.get('capability')}",
        f"Provider: {disclosure.get('provider')} · Engine: {disclosure.get('engine')}",
        f"Expected outputs: {', '.join(disclosure.get('expectedOutputs') or []) or '—'}",
        f"May consume credits: {disclosure.get('mayConsumeCredits')}",
        f"Replaces existing asset: {disclosure.get('replacesExistingAsset')}",
    ]
    for reason in disclosure.get("reasons") or []:
        lines.append(f"Approval reason: {reason}")
    return ToolPreview(
        summary=f"Produce {operation} via Certified Workflow Library / approved adapter",
        lines=lines,
        resourceKind="scene" if args.get("sceneId") else "project",
        resourceId=str(args.get("sceneId") or ""),
        warnings=list(disclosure.get("reasons") or [])
        + ["Success only after Output Gate and asset registration."],
    )


def make_handlers(operation: str, tool_id: str):
    def preview(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
        intent = _build_intent(ctx, args, operation=operation, tool_id=tool_id)
        try:
            pf = preflight_intent(intent)
            disclosure = (pf.get("approval") or {}).get("disclosure") or build_disclosure(intent)
        except IntentExecutionError as exc:
            recovery = exc.recovery or classify_failure(exc)
            disclosure = build_disclosure(intent, reasons=[recovery.userMessage])
            return ToolPreview(
                summary=f"Blocked: {operation}",
                lines=[recovery.userMessage, f"code={recovery.diagnosticCode}"],
                warnings=["Not executable until remediated."],
            )
        return _preview_for(operation, args, disclosure)

    def apply(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        intent = _build_intent(ctx, args, operation=operation, tool_id=tool_id)
        get_intent_store().save(intent)
        try:
            # Re-preflight to reject Blocked/Deferred before queue
            if intent.modality == "video" and operation.startswith("video."):
                preflight_intent(intent)
            result = enqueue_intent(ctx.db, intent)
            return {
                "ok": bool(result.get("ok", True)),
                "toolId": tool_id,
                "operation": operation,
                "intentId": intent.intentId,
                "jobId": result.get("jobId"),
                "status": result.get("status"),
                "workflowKey": result.get("workflowKey"),
                "result": result.get("result"),
                "completed": bool(result.get("completed")),
                "disclosure": "Queued or completed only via public contracts. No simulated success.",
            }
        except IntentExecutionError as exc:
            recovery = exc.recovery or classify_failure(exc)
            return {
                "ok": False,
                "toolId": tool_id,
                "operation": operation,
                "intentId": intent.intentId,
                "errorCode": exc.code,
                "errorMessage": str(exc),
                "recovery": {
                    "policy": recovery.policy,
                    "userMessage": recovery.userMessage,
                    "diagnosticCode": recovery.diagnosticCode,
                    "retryAvailable": recovery.retryAvailable,
                },
            }

    return preview, apply


def preview_propose_image_generate(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    """Image propose preview with recommend + cost/why + prompt intel (M42 W3)."""
    from ....image_product.prompt_intel import expand_prompt
    from ....image_product.recommend import recommend_image_family

    prompt = str(args.get("prompt") or args.get("text") or "")
    purpose = str(args.get("purpose") or "stills")
    family_pref = args.get("modelFamilyPreference") or args.get("engine") or args.get("family")
    prompt_info = expand_prompt(
        prompt,
        purpose=purpose,
        style_hints=dict(args.get("style") or {}),
    )
    accepted = (
        str(args["acceptedPrompt"])
        if args.get("acceptedPrompt")
        else (
            prompt_info["expandedPrompt"]
            if args.get("acceptExpandedPrompt", True)
            else prompt_info["originalPrompt"]
        )
    )
    rec = recommend_image_family(
        prompt=accepted,
        purpose=purpose,
        operation="image.generate",
        model_family_preference=str(family_pref) if family_pref else None,
        quality=str(args.get("quality") or args.get("qualityProfile") or "standard"),
    )
    est = rec.get("estimates") or {}
    intent = _build_intent(
        ctx,
        {
            **args,
            "prompt": accepted,
            "engine": rec.get("executionFamily") or family_pref,
        },
        operation="image.generate",
        tool_id="propose_image_generate",
    )
    intent.metadata = {
        **(intent.metadata or {}),
        "purpose": purpose,
        "presetId": args.get("presetId"),
        "modelFamilyPreference": family_pref or rec.get("recommendedFamily"),
        "acceptExpandedPrompt": args.get("acceptExpandedPrompt", True),
        "recommendation": rec,
        "promptIntel": prompt_info,
    }
    try:
        pf = preflight_intent(intent)
        disclosure = (pf.get("approval") or {}).get("disclosure") or build_disclosure(intent)
    except IntentExecutionError as exc:
        recovery = exc.recovery or classify_failure(exc)
        return ToolPreview(
            summary=f"Blocked: image.generate — {rec.get('recommendedFamily')}",
            lines=[
                recovery.userMessage,
                f"whyThisModel: {rec.get('whyThisModel')}",
                f"estimates: {est.get('costLabel')} · ~{est.get('generationTimeSec')}s · VRAM {est.get('vramGb')}",
            ],
            warnings=["Not executable until remediated."],
        )
    lines = [
        f"Recommended family: {rec.get('recommendedFamily')} (status={rec.get('status')})",
        f"whyThisModel: {rec.get('whyThisModel')}",
        f"Time: ~{est.get('generationTimeSec')}s · VRAM: {est.get('vramGb')} GB · Cost: {est.get('costLabel')}",
        f"Execution family: {rec.get('executionFamily')}"
        + (" (certified fallback)" if rec.get("fallbackApplied") else ""),
        f"Prompt (accepted): {accepted[:180]}",
        f"Capability: {disclosure.get('capability')}",
        f"Provider: {disclosure.get('provider')} · Engine: {disclosure.get('engine')}",
    ]
    if args.get("presetId"):
        lines.insert(0, f"Preset: {args.get('presetId')}")
    return ToolPreview(
        summary=f"Image · {rec.get('recommendedFamily')} · {est.get('costLabel')}",
        lines=lines,
        resourceKind="scene" if args.get("sceneId") else "project",
        resourceId=str(args.get("sceneId") or ""),
        warnings=list(disclosure.get("reasons") or [])
        + ["Success only after Output Gate and asset registration.", "Model recommendation is overridable."],
    )


def apply_propose_image_generate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....image_product.prompt_intel import expand_prompt
    from ....image_product.recommend import recommend_image_family

    prompt = str(args.get("prompt") or args.get("text") or "")
    purpose = str(args.get("purpose") or "stills")
    family_pref = args.get("modelFamilyPreference") or args.get("engine") or args.get("family")
    prompt_info = expand_prompt(prompt, purpose=purpose)
    accepted = (
        str(args["acceptedPrompt"])
        if args.get("acceptedPrompt")
        else (
            prompt_info["expandedPrompt"]
            if args.get("acceptExpandedPrompt", True)
            else prompt_info["originalPrompt"]
        )
    )
    rec = recommend_image_family(
        prompt=accepted,
        purpose=purpose,
        model_family_preference=str(family_pref) if family_pref else None,
    )
    intent = _build_intent(
        ctx,
        {
            **args,
            "prompt": accepted,
            "engine": family_pref or rec.get("recommendedFamily"),
        },
        operation="image.generate",
        tool_id="propose_image_generate",
    )
    intent.metadata = {
        **(intent.metadata or {}),
        "purpose": purpose,
        "presetId": args.get("presetId"),
        "modelFamilyPreference": family_pref or rec.get("recommendedFamily"),
        "acceptExpandedPrompt": args.get("acceptExpandedPrompt", True),
        "acceptedPrompt": accepted,
        "recommendation": rec,
        "promptIntel": prompt_info,
        "refs": args.get("refs") or [],
    }
    get_intent_store().save(intent)
    try:
        result = enqueue_intent(ctx.db, intent)
        return {
            "ok": bool(result.get("ok", True)),
            "toolId": "propose_image_generate",
            "operation": "image.generate",
            "intentId": intent.intentId,
            "jobId": result.get("jobId"),
            "status": result.get("status"),
            "workflowKey": result.get("workflowKey"),
            "recommendation": rec,
            "promptIntel": prompt_info,
            "result": result.get("result"),
            "disclosure": "Queued via Image Product → certified resolver. No simulated success.",
        }
    except IntentExecutionError as exc:
        recovery = exc.recovery or classify_failure(exc)
        return {
            "ok": False,
            "toolId": "propose_image_generate",
            "operation": "image.generate",
            "intentId": intent.intentId,
            "errorCode": exc.code,
            "errorMessage": str(exc),
            "recommendation": rec,
            "recovery": {
                "policy": recovery.policy,
                "userMessage": recovery.userMessage,
                "diagnosticCode": recovery.diagnosticCode,
                "retryAvailable": recovery.retryAvailable,
            },
        }
def preview_propose_image_edit(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    """Advanced edit propose: recommend_edit + recipe + certified path (M42 W4)."""
    from ....image_product.edit_recommend import recommend_edit
    from ....image_product.recipes import get_recipe, apply_recipe_to_request

    prompt = str(args.get("prompt") or args.get("text") or args.get("instruction") or "")
    operation = str(args.get("operation") or "image.inpaint")
    recipe_id = args.get("recipeId")
    if recipe_id:
        recipe = get_recipe(ctx.project_id, str(recipe_id))
        if recipe:
            applied = apply_recipe_to_request(recipe, detail=prompt)
            operation = str(applied.get("operation") or operation)
            prompt = str(applied.get("prompt") or prompt)
    source_ids = []
    if args.get("sourceAssetId"):
        source_ids.append(str(args["sourceAssetId"]))
    for a in args.get("sourceAssetIds") or []:
        if a and str(a) not in source_ids:
            source_ids.append(str(a))
    rec = recommend_edit(
        operation=operation,
        prompt=prompt,
        purpose=str(args.get("purpose") or ""),
        model_family_preference=args.get("modelFamilyPreference") or args.get("engine"),
        source_asset_ids=source_ids,
        has_masks=bool(args.get("masks") or args.get("maskAssetId")),
        has_references=bool(args.get("referenceAssetIds") or args.get("refs")),
    )
    est = rec.get("estimates") or {}
    missing = list(rec.get("requiredInputs") or [])
    if "sourceImage" in missing and source_ids:
        missing = [m for m in missing if m != "sourceImage"]
    if "replaceMask" in missing and (args.get("masks") or args.get("maskAssetId")):
        missing = [m for m in missing if m != "replaceMask"]
    lines = [
        f"Operation: {operation}",
        f"Recommended family: {rec.get('recommendedFamily')} (exec={rec.get('executionFamily')})",
        f"whyThisModel: {rec.get('whyThisModel')}",
        f"Time: ~{est.get('generationTimeSec')}s · VRAM: {est.get('vramGb')} · Cost: {est.get('costLabel')}",
        f"Sources: {', '.join(source_ids) or '— missing'}",
    ]
    if recipe_id:
        lines.insert(0, f"Recipe: {recipe_id}")
    if missing:
        lines.append(f"Missing inputs: {', '.join(missing)}")
    if args.get("targetAssetIds"):
        lines.append(f"Batch targets: {len(args.get('targetAssetIds') or [])}")
    warnings = []
    if missing:
        warnings.append("Provide missing inputs before execute.")
    if rec.get("fallbackApplied"):
        warnings.append("Certified fallback will be used for execution.")
    warnings.append("Success only after semantic Output Gate and derived asset registration.")
    return ToolPreview(
        summary=f"Edit · {operation} · {rec.get('recommendedFamily')} · {est.get('costLabel')}",
        lines=lines,
        resourceKind="project",
        resourceId=ctx.project_id,
        warnings=warnings,
    )


def apply_propose_image_edit(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from ....image_product.edit_service import enqueue_edit, enqueue_edit_batch

    body = dict(args or {})
    body.setdefault("projectId", ctx.project_id)
    if args.get("sourceAssetId") and not body.get("sourceAssetIds"):
        body["sourceAssetIds"] = [str(args["sourceAssetId"])]
    if args.get("maskAssetId") and not body.get("masks"):
        body["masks"] = [{"maskAssetId": str(args["maskAssetId"]), "role": "replace"}]
    targets = list(args.get("targetAssetIds") or [])
    try:
        if targets:
            result = enqueue_edit_batch(ctx.db, project_id=ctx.project_id, body={**body, "targetAssetIds": targets})
        else:
            result = enqueue_edit(ctx.db, project_id=ctx.project_id, body=body)
        return {
            "ok": bool(result.get("ok", True)),
            "toolId": "propose_image_edit",
            "operation": body.get("operation") or "image.inpaint",
            "jobId": result.get("jobId"),
            "jobs": result.get("jobs"),
            "recommendation": result.get("recommendation"),
            "imageEditIntentId": (result.get("imageEditIntent") or {}).get("intentId"),
            "disclosure": "Queued via ImageEditIntent → certified edit resolver. No simulated success.",
        }
    except Exception as exc:
        recovery = classify_failure(exc)
        return {
            "ok": False,
            "toolId": "propose_image_edit",
            "errorMessage": str(exc),
            "recovery": {
                "userMessage": recovery.userMessage,
                "diagnosticCode": recovery.diagnosticCode,
                "retryAvailable": recovery.retryAvailable,
            },
        }


preview_propose_shot_generate, apply_propose_shot_generate = make_handlers(
    "video.shot_render", "propose_shot_generate"
)
preview_propose_scene_generate, apply_propose_scene_generate = make_handlers(
    "video.scene_render", "propose_scene_generate"
)
preview_propose_video_generate, apply_propose_video_generate = make_handlers(
    "video.generate", "propose_video_generate"
)
preview_propose_three_frame_generate, apply_propose_three_frame_generate = make_handlers(
    "video.three_frame", "propose_three_frame_generate"
)
preview_propose_timeline_render, apply_propose_timeline_render = make_handlers(
    "video.timeline_render", "propose_timeline_render"
)
preview_propose_batch_timeline, apply_propose_batch_timeline = make_handlers(
    "video.batch_timeline", "propose_batch_timeline"
)
preview_propose_lipsync, apply_propose_lipsync = make_handlers("video.lipsync", "propose_lipsync")
preview_propose_voice_generate, apply_propose_voice_generate = make_handlers(
    "voice.generate", "propose_voice_generate"
)
preview_propose_subtitle_generate, apply_propose_subtitle_generate = make_handlers(
    "subtitle.generate", "propose_subtitle_generate"
)
preview_editor_place_asset, apply_editor_place_asset = make_handlers(
    "editor.place", "editor.place_asset"
)
preview_job_cancel, apply_job_cancel = make_handlers("job.cancel", "job.cancel")
preview_job_retry, apply_job_retry = make_handlers("job.retry", "job.retry")

# Extend via intent path (replaces hardcoded workflow hint on apply)
preview_propose_video_extend_w6p, apply_propose_video_extend_w6p = make_handlers(
    "video.extend", "propose_video_extend"
)
