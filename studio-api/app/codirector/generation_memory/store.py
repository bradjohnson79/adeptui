"""Read/write canonicalGenerationRequest on existing execution packs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ..execution.contracts import ExecutionPlan
from ..execution.pack_store import list_packs, save_pack
from .contracts import CanonicalGenerationRequest, InheritAudit
from .schema import EXCLUDED_CAPABILITIES


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_from_pack(pack: ExecutionPlan, db: Session | None = None) -> CanonicalGenerationRequest | None:
    raw = (pack.plan_data or {}).get("canonicalGenerationRequest")
    if isinstance(raw, dict) and (raw.get("originalUserInstructions") or raw.get("requestId")):
        try:
            return CanonicalGenerationRequest.model_validate(raw)
        except Exception:
            return None
    if db is None:
        return None
    return _backfill_from_jobs(pack, db)


def _backfill_from_jobs(pack: ExecutionPlan, db: Session) -> CanonicalGenerationRequest | None:
    """Production job params only — never conversation summaries."""

    if pack.capability in EXCLUDED_CAPABILITIES:
        return None
    if not str(pack.capability or "").split(".")[0] in {"image", "video", "audio"}:
        return None
    from ...db import Job

    prompt = ""
    job_ids = [cj.job_id for cj in pack.child_jobs if cj.job_id]
    for job_id in job_ids:
        job = db.get(Job, job_id)
        if job is None:
            continue
        try:
            params = json.loads(job.params_json or "{}")
        except Exception:
            params = {}
        prompt = str(params.get("prompt") or "").strip()
        if prompt:
            break
    if not prompt:
        audio_req = _backfill_from_audio_studio(pack)
        if audio_req is not None:
            return audio_req
        return None
    first = (pack.child_jobs[0].metadata if pack.child_jobs else {}) or {}
    return CanonicalGenerationRequest(
        requestId=str(uuid4()),
        projectId=pack.project_id,
        artifactType=str(pack.capability or "image").split(".")[0] or "image",
        action=pack.capability or "image.generate",
        originalUserInstructions=prompt,
        compiledGeneratorPrompt=prompt,
        executionId=pack.execution_id,
        jobIds=job_ids,
        resultAssetIds=list(pack.result_asset_ids or []),
        aspectRatio=str(pack.plan_data.get("aspectRatio") or first.get("aspectRatio") or ""),
        width=int(pack.plan_data.get("width") or 0),
        height=int(pack.plan_data.get("height") or 0),
        route=str(pack.plan_data.get("route") or first.get("route") or ""),
        provider=str(pack.provider or pack.plan_data.get("providerKind") or first.get("providerKind") or ""),
        modelId=str(pack.model or first.get("selectedModelId") or ""),
        referenceAssetIds=[str(first["reference_asset_id"])] if first.get("reference_asset_id") else [],
        characterIds=[str(first["character_id"])] if first.get("character_id") else list(
            filter(None, [pack.character_id or ""])
        ),
        createdAt=pack.created_at or _now(),
    )


def _audio_kind_from_capability(capability: str) -> str:
    family, _, leaf = str(capability or "").partition(".")
    if family != "audio":
        return ""
    if leaf in {"sfx", "music", "ambience"}:
        return leaf
    return "sfx"


def _original_from_audio_batch(batch: dict[str, Any]) -> str:
    brief = batch.get("brief_snapshot") if isinstance(batch.get("brief_snapshot"), dict) else {}
    return str(
        batch.get("raw_prompt")
        or brief.get("prompt")
        or batch.get("prompt")
        or ""
    ).strip()


def _backfill_from_audio_studio(pack: ExecutionPlan) -> CanonicalGenerationRequest | None:
    """Audio Studio batches are first-class production work, not studio Job rows."""

    if str(pack.capability or "").split(".")[0] != "audio":
        return None
    try:
        from ...audio_studio.store import get_batch, list_batches
    except Exception:
        return None

    wanted = _audio_kind_from_capability(pack.capability)
    batches: list[dict[str, Any]] = []
    for child in pack.child_jobs:
        job_id = str(child.job_id or "").strip()
        meta = child.metadata if isinstance(child.metadata, dict) else {}
        batch_id = str(meta.get("batchId") or job_id or "").strip()
        if not batch_id:
            continue
        found = get_batch(pack.project_id, batch_id)
        if isinstance(found, dict):
            batches.append(found)
    if not batches:
        for item in list_batches(pack.project_id):
            if not isinstance(item, dict):
                continue
            kind = str(item.get("gen_kind") or item.get("category") or "").lower()
            if wanted and kind and kind != wanted:
                continue
            if _original_from_audio_batch(item):
                batches.append(item)
                break
    if not batches:
        return None
    batch = batches[0]
    original = _original_from_audio_batch(batch)
    if not original:
        return None
    compiled = str(batch.get("compiled_prompt") or batch.get("prompt") or original).strip()
    batch_id = str(batch.get("id") or "")
    assets: list[str] = []
    for cand in batch.get("candidates") or []:
        if not isinstance(cand, dict):
            continue
        aid = str(cand.get("asset_id") or cand.get("assetId") or "").strip()
        if aid:
            assets.append(aid)
    return CanonicalGenerationRequest(
        requestId=str(uuid4()),
        projectId=pack.project_id,
        artifactType="audio",
        action=pack.capability or "audio.sfx",
        originalUserInstructions=original,
        compiledGeneratorPrompt=compiled,
        executionId=pack.execution_id,
        jobIds=[batch_id] if batch_id else [cj.job_id for cj in pack.child_jobs if cj.job_id],
        resultAssetIds=assets or list(pack.result_asset_ids or []),
        createdAt=pack.created_at or _now(),
    )


def attach_canonical_request(db: Session, plan: ExecutionPlan, request: CanonicalGenerationRequest) -> ExecutionPlan:
    request.executionId = plan.execution_id
    request.jobIds = [cj.job_id for cj in plan.child_jobs if cj.job_id]
    request.resultAssetIds = list(plan.result_asset_ids or [])
    if not request.createdAt:
        request.createdAt = plan.created_at or _now()
    request.projectId = plan.project_id
    plan.plan_data = {
        **dict(plan.plan_data or {}),
        "canonicalGenerationRequest": request.model_dump(mode="json"),
    }
    return save_pack(db, plan.project_id, plan)


def snapshot_from_dispatch(
    *,
    plan: ExecutionPlan,
    ctx: dict[str, Any],
    result: dict[str, Any],
) -> CanonicalGenerationRequest:
    prior_id = ctx.get("parent_request_id") or ctx.get("canonical_request_id")
    audit_raw = ctx.get("inherit_audit") if isinstance(ctx.get("inherit_audit"), dict) else None
    original = str(
        ctx.get("canonical_original_instructions")
        or ctx.get("original_user_instructions")
        or (ctx.get("prompt") if ctx.get("canonical_resolved") else "")
        or ctx.get("user_instructions")
        or ctx.get("prompt")
        or ""
    )
    compiled = str(result.get("compiledGeneratorPrompt") or result.get("prompt") or original)
    refs: list[str] = []
    for bucket in (
        ctx.get("reference_asset_ids"),
        ctx.get("crs_asset_ids"),
        ctx.get("attachment_asset_ids"),
        result.get("reference_asset_ids"),
    ):
        for raw in bucket or []:
            value = str(raw or "").strip()
            if value and value not in refs:
                refs.append(value)
    if result.get("reference_asset_id") and str(result.get("reference_asset_id")) not in refs:
        refs.append(str(result.get("reference_asset_id")))
    chars: list[str] = []
    for bucket in (ctx.get("character_ids"), result.get("character_ids")):
        for raw in bucket or []:
            value = str(raw or "").strip()
            if value and value not in chars:
                chars.append(value)
    for raw in (ctx.get("character_id"), result.get("character_id"), plan.character_id):
        value = str(raw or "").strip()
        if value and value not in chars:
            chars.append(value)
    lock_level = str(result.get("lockLevel") or ctx.get("lock_level") or "").upper()
    unlocked = lock_level == "UNLOCKED"
    audit = result.get("fallbackAudit") if isinstance(result.get("fallbackAudit"), dict) else {}
    recorded_route = str(
        (audit.get("step") if unlocked else "")
        or result.get("route")
        or ctx.get("generation_route")
        or ""
    )
    return CanonicalGenerationRequest(
        requestId=str(ctx.get("canonical_request_id") or uuid4()),
        projectId=plan.project_id,
        conversationId=str(ctx.get("conversation_id") or ""),
        sourceMessageId=str(ctx.get("source_message_id") or ctx.get("user_turn_id") or ""),
        artifactType=str(plan.capability or ctx.get("artifact_type") or "image").split(".")[0] or "image",
        action=str(plan.capability or ctx.get("action") or "image.generate"),
        originalUserInstructions=original,
        resolvedCreativeBrief=str(ctx.get("resolved_creative_brief") or ""),
        compiledGeneratorPrompt=compiled,
        referenceAssetIds=refs,
        characterIds=list(dict.fromkeys(chars)),
        continuityConstraints=str(ctx.get("continuity_constraints") or ""),
        negativeConstraints=str(ctx.get("negative_constraints") or ""),
        qualityIntent=str(ctx.get("quality_intent") or ""),
        route=recorded_route,
        provider=str(result.get("providerKind") or ctx.get("provider_kind") or plan.provider or ""),
        modelId=str(
            result.get("selectedModelId")
            or ctx.get("model")
            or ctx.get("hosted_model_id")
            or plan.model
            or ""
        ),
        aspectRatio=str(result.get("aspectRatio") or ctx.get("aspect_ratio") or ""),
        width=int(result.get("width") or ctx.get("width") or 0),
        height=int(result.get("height") or ctx.get("height") or 0),
        executionId=plan.execution_id,
        jobIds=list(result.get("job_ids") or [cj.job_id for cj in plan.child_jobs if cj.job_id]),
        resultAssetIds=list(plan.result_asset_ids or []),
        parentRequestId=str(prior_id) if prior_id and ctx.get("canonical_resolved") else None,
        revision=int(ctx.get("canonical_revision") or 1),
        createdAt=plan.created_at or _now(),
        inheritAudit=InheritAudit.model_validate(audit_raw) if audit_raw else None,
        lockLevel=str(result.get("lockLevel") or ctx.get("lock_level") or ""),
        lockScope=str(result.get("lockScope") or ctx.get("lock_scope") or ""),
        requestedProvider=str(
            ""
            if unlocked
            else (result.get("requestedProvider") or ctx.get("requested_provider") or "")
        ),
        requestedModelId=str(
            ""
            if unlocked
            else (result.get("requestedModelId") or ctx.get("requested_model_id") or "")
        ),
        fallbackAudit=dict(result.get("fallbackAudit") or ctx.get("fallback_audit") or {}),
        visionFacts=str(ctx.get("vision_facts") or ""),
        referenceRole=str(ctx.get("reference_role") or ""),
    )


def list_generation_requests(
    db: Session,
    project_id: str,
    *,
    artifact_type: str = "",
) -> list[tuple[ExecutionPlan, CanonicalGenerationRequest]]:
    packs = list_packs(db, project_id, active_only=False)
    wanted = (artifact_type or "").strip().lower()
    out: list[tuple[ExecutionPlan, CanonicalGenerationRequest]] = []
    for pack in packs:
        if pack.capability in EXCLUDED_CAPABILITIES:
            continue
        family = str(pack.capability or "").split(".")[0]
        if family not in {"image", "video", "audio"}:
            continue
        if wanted and family != wanted:
            continue
        req = request_from_pack(pack, db)
        if req is None or not (req.originalUserInstructions or "").strip():
            continue
        out.append((pack, req))
    out.sort(key=lambda row: row[0].created_at or row[1].createdAt or "", reverse=True)
    return out


def list_image_requests(
    db: Session,
    project_id: str,
) -> list[tuple[ExecutionPlan, CanonicalGenerationRequest]]:
    return list_generation_requests(db, project_id, artifact_type="image")


def update_result_lineage(plan: ExecutionPlan) -> ExecutionPlan:
    """Refresh job/asset ids only. Never overwrite originalUserInstructions."""

    raw = dict((plan.plan_data or {}).get("canonicalGenerationRequest") or {})
    if not raw:
        return plan
    original = raw.get("originalUserInstructions")
    raw["resultAssetIds"] = list(plan.result_asset_ids or [])
    raw["jobIds"] = [cj.job_id for cj in plan.child_jobs if cj.job_id]
    if original is not None:
        raw["originalUserInstructions"] = original
    plan.plan_data = {**dict(plan.plan_data or {}), "canonicalGenerationRequest": raw}
    return plan
