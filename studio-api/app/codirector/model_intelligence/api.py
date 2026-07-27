"""Model Intelligence Layer HTTP API."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import get_db
from .compiler import compile_intent, normalize_audio_from_text
from .docs_sync import propose_pack_update, register_source
from .evaluator import evaluate_result
from .experience import record_experience
from .loader import validate_all
from .preflight import run_preflight
from .provenance import summarize_pack_provenance
from .registry import list_registry_rows
from .resolver import try_resolve
from .revision import propose_revision
from .schemas import (
    AudioIntent,
    EvaluationResult,
    NormalizedGenerationIntent,
    PreflightStatus,
)
from .selector import recommend

router = APIRouter(prefix="/model-intelligence", tags=["model-intelligence"])


class CompileBody(BaseModel):
    userPrompt: str = ""
    negativePromptHint: str = ""
    modelId: Optional[str] = None
    engineId: Optional[str] = None
    mode: str = "image_to_video"
    mediaType: str = "video"
    durationSec: Optional[float] = None
    hasSourceImage: bool = False
    referenceCount: int = 0
    forceModelId: Optional[str] = None
    preserveExactWording: bool = False
    audioIntent: Optional[AudioIntent] = None
    mustInclude: list[str] = Field(default_factory=list)
    mustAvoid: list[str] = Field(default_factory=list)
    userOverrides: dict[str, Any] = Field(default_factory=dict)
    runtimeModelVersion: Optional[str] = None
    biblePackage: Optional[dict[str, Any]] = None
    projectId: Optional[str] = None
    sceneId: Optional[str] = None


def _intent_from_body(body: CompileBody) -> NormalizedGenerationIntent:
    audio = body.audioIntent or normalize_audio_from_text(body.userPrompt)
    return NormalizedGenerationIntent(
        userPrompt=body.userPrompt,
        negativePromptHint=body.negativePromptHint,
        mode=body.mode,
        mediaType=body.mediaType,
        durationSec=body.durationSec,
        hasSourceImage=body.hasSourceImage,
        referenceCount=body.referenceCount,
        forceModelId=body.forceModelId,
        preserveExactWording=body.preserveExactWording,
        audioIntent=audio,
        mustInclude=body.mustInclude,
        mustAvoid=body.mustAvoid,
        userOverrides=body.userOverrides,
        projectContext={"projectId": body.projectId} if body.projectId else {},
        sceneContext={"sceneId": body.sceneId} if body.sceneId else {},
    )


@router.get("/packs")
def list_packs() -> dict[str, Any]:
    return {"packs": list_registry_rows(), "validation": validate_all()}


@router.get("/packs/{model_id}")
def get_pack(model_id: str) -> dict[str, Any]:
    pack, err = try_resolve(model_id=model_id, allow_non_active=True)
    if pack is None:
        raise HTTPException(404, err or "pack not found")
    manifest = pack["manifest"]
    return {
        "manifest": manifest.model_dump(mode="json"),
        "capabilities": pack.get("capabilities"),
        "audioBehavior": pack.get("audio_behavior"),
        "limitations": pack.get("limitations"),
        "provenance": summarize_pack_provenance(pack),
        "resolveWarnings": pack.get("resolveWarnings") or [],
    }


@router.post("/validate")
def validate_packs() -> dict[str, Any]:
    return validate_all()


@router.post("/recommend")
def recommend_model(body: CompileBody) -> dict[str, Any]:
    intent = _intent_from_body(body)
    rec = recommend(intent)
    return rec.model_dump(mode="json")


@router.post("/compile")
def compile_prompt(body: CompileBody) -> dict[str, Any]:
    intent = _intent_from_body(body)
    result = compile_intent(
        intent,
        model_id=body.modelId,
        engine_id=body.engineId,
        runtime_model_version=body.runtimeModelVersion,
        bible_package=body.biblePackage,
    )
    return result.model_dump(mode="json")


@router.post("/preflight")
def preflight(body: CompileBody, paidPath: bool = False) -> dict[str, Any]:
    intent = _intent_from_body(body)
    result = run_preflight(
        intent,
        model_id=body.modelId,
        engine_id=body.engineId,
        runtime_model_version=body.runtimeModelVersion,
        bible_package=body.biblePackage,
        paid_path=paidPath,
    )
    return result.model_dump(mode="json")


class EvaluateBody(BaseModel):
    modelId: str
    userPrompt: str = ""
    artifactPath: Optional[str] = None
    generationStatus: str = "done"
    parameters: dict[str, Any] = Field(default_factory=dict)
    audioProbe: Optional[dict[str, Any]] = None
    audioIntent: Optional[AudioIntent] = None


@router.post("/evaluate")
def evaluate(body: EvaluateBody) -> dict[str, Any]:
    intent = NormalizedGenerationIntent(
        userPrompt=body.userPrompt,
        audioIntent=body.audioIntent or normalize_audio_from_text(body.userPrompt),
    )
    result = evaluate_result(
        intent=intent,
        model_id=body.modelId,
        artifact_path=body.artifactPath,
        generation_status=body.generationStatus,
        parameters=body.parameters,
        audio_probe=body.audioProbe,
    )
    revision = propose_revision(intent=intent, evaluation=result, compile_parameters=body.parameters)
    return {"evaluation": result.model_dump(mode="json"), "revision": revision.model_dump(mode="json")}


class ExperienceBody(BaseModel):
    modelId: str
    modelVersion: str = ""
    providerId: str = ""
    knowledgePackVersion: str = ""
    projectId: Optional[str] = None
    sceneId: Optional[str] = None
    requestType: str = ""
    compiledRuleIds: list[str] = Field(default_factory=list)
    parameterSummary: dict[str, Any] = Field(default_factory=dict)
    generationStatus: str = ""
    failureCodes: list[str] = Field(default_factory=list)


@router.post("/experience")
def post_experience(body: ExperienceBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    rec = record_experience(
        db,
        model_id=body.modelId,
        model_version=body.modelVersion,
        provider_id=body.providerId,
        knowledge_pack_version=body.knowledgePackVersion,
        project_id=body.projectId,
        scene_id=body.sceneId,
        request_type=body.requestType,
        compiled_rule_ids=body.compiledRuleIds,
        parameter_summary=body.parameterSummary,
        generation_status=body.generationStatus,
        failure_codes=body.failureCodes,
    )
    return rec.model_dump(mode="json")


class DocsProposalBody(BaseModel):
    modelId: str
    currentVersion: str
    proposedVersion: str
    diffSummary: str
    sourceUrls: list[str] = Field(default_factory=list)


@router.post("/docs/propose-update")
def docs_propose(body: DocsProposalBody) -> dict[str, Any]:
    return propose_pack_update(
        model_id=body.modelId,
        current_version=body.currentVersion,
        proposed_version=body.proposedVersion,
        diff_summary=body.diffSummary,
        source_urls=body.sourceUrls,
    )


@router.post("/docs/register-source")
def docs_register(modelId: str, url: str, label: str = "") -> dict[str, Any]:
    return register_source(model_id=modelId, url=url, label=label)


@router.get("/filmmaker-summary")
def filmmaker_summary(
    userPrompt: str,
    modelId: Optional[str] = None,
    engineId: Optional[str] = None,
) -> dict[str, Any]:
    """Default filmmaker-friendly presentation (no provider jargon overload)."""
    body = CompileBody(userPrompt=userPrompt, modelId=modelId, engineId=engineId)
    intent = _intent_from_body(body)
    rec = recommend(intent)
    chosen = modelId or rec.recommendedModel
    compiled = compile_intent(intent, model_id=chosen, engine_id=engineId)
    pf = run_preflight(intent, model_id=chosen, engine_id=engineId)
    return {
        "recommendedModel": rec.recommendedModel,
        "why": rec.explanation,
        "confidence": rec.confidence,
        "audioPlan": compiled.audioPlanSummary,
        "knownLimitations": compiled.limitations,
        "preflight": pf.status.value,
        "warnings": compiled.warnings[:5],
        "advanced": {
            "compiledPrompt": compiled.compiledPrompt,
            "negativePrompt": compiled.negativePrompt,
            "parameters": compiled.parameters,
            "appliedRules": [r.model_dump(mode="json") for r in compiled.appliedRules],
            "knowledgePackVersion": compiled.knowledgePackVersion,
            "alternatives": rec.alternatives,
        },
    }


# Re-export for tests
__all__ = ["router", "PreflightStatus", "EvaluationResult"]
