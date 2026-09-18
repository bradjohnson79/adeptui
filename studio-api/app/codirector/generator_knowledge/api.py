"""HTTP surface for Production-Control-keyed generator prompt compile preview."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..model_intelligence.compiler import normalize_audio_from_text
from ..model_intelligence.schemas import NormalizedGenerationIntent
from .compiler import UNAVAILABLE_MESSAGE, compile_for_generator
from .resolver import canonical_profile_id, try_resolve_profile

router = APIRouter(prefix="/generator-knowledge", tags=["generator-knowledge"])


class CompilePreviewBody(BaseModel):
    generatorId: str = ""
    userPrompt: str = ""
    negativePromptHint: str = ""
    mode: str = "image_to_video"
    mediaType: str = "video"
    durationSec: Optional[float] = None
    hasSourceImage: bool = False
    projectId: Optional[str] = None
    sceneId: Optional[str] = None
    mustInclude: list[str] = Field(default_factory=list)
    mustAvoid: list[str] = Field(default_factory=list)
    preserveExactWording: bool = False
    projectContext: dict[str, Any] = Field(default_factory=dict)



@router.get("/resolve")
def resolve_preview(generatorId: str = "") -> dict[str, Any]:
    profile, err = try_resolve_profile(generatorId)
    if profile is None:
        return {
            "ok": False,
            "status": "GENERATOR_KNOWLEDGE_UNAVAILABLE",
            "message": UNAVAILABLE_MESSAGE,
            "generatorId": generatorId,
            "profileId": canonical_profile_id(generatorId),
            "error": err,
        }
    payload = profile.model_dump(mode="json")
    return {
        "ok": True,
        "status": "ok",
        "generatorId": generatorId,
        "profileId": profile.profileId,
        "dialect": profile.prompt.dialect,
        "capability": payload["capability"],
        "prompt": payload["prompt"],
        "workflow": payload["workflow"],
        "profile": payload,
    }


@router.post("/compile-preview")
def compile_preview(body: CompilePreviewBody) -> dict[str, Any]:
    generator_id = (body.generatorId or "").strip()
    profile, err = try_resolve_profile(generator_id)
    if profile is None:
        return {
            "ok": False,
            "status": "GENERATOR_KNOWLEDGE_UNAVAILABLE",
            "message": UNAVAILABLE_MESSAGE,
            "generatorId": generator_id,
            "profileId": canonical_profile_id(generator_id),
            "error": err,
            "compiledPrompt": "",
            "negativePrompt": "",
            "dialect": None,
            "warnings": [UNAVAILABLE_MESSAGE] + ([err] if err else []),
        }

    ctx = dict(body.projectContext or {})
    if body.projectId:
        ctx.setdefault("projectId", body.projectId)
    intent = NormalizedGenerationIntent(
        userPrompt=body.userPrompt,
        negativePromptHint=body.negativePromptHint,
        mode=body.mode,
        mediaType=body.mediaType,
        durationSec=body.durationSec,
        hasSourceImage=body.hasSourceImage,
        preserveExactWording=body.preserveExactWording,
        audioIntent=normalize_audio_from_text(body.userPrompt),
        mustInclude=body.mustInclude,
        mustAvoid=body.mustAvoid,
        projectContext=ctx,
        sceneContext={"sceneId": body.sceneId} if body.sceneId else {},
    )
    result = compile_for_generator(generator_id, intent)
    unavailable = result.status in (
        "GENERATOR_KNOWLEDGE_UNAVAILABLE",
        "MODEL_KNOWLEDGE_UNAVAILABLE",
    )
    payload = result.model_dump(mode="json")
    return {
        "ok": not unavailable,
        "status": result.status if not unavailable else "GENERATOR_KNOWLEDGE_UNAVAILABLE",
        "message": None if not unavailable else UNAVAILABLE_MESSAGE,
        "generatorId": generator_id,
        "profileId": profile.profileId,
        "dialect": profile.prompt.dialect,
        "compiledPrompt": result.compiledPrompt if not unavailable else "",
        "negativePrompt": result.negativePrompt,
        "warnings": result.warnings,
        "appliedRules": payload.get("appliedRules") or [],
        "parameters": result.parameters,
        "limitations": result.limitations,
        "confidence": result.confidence,
        "compile": payload,
    }
