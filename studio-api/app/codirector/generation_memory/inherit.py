"""Schema-driven field copy. Never dict.update a prior request into a new one."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .contracts import CanonicalGenerationRequest, InheritAudit
from .schema import (
    GENERATOR_LOCK_FIELDS,
    INHERIT_EXACT,
    LOCKED_ROUTE_LEVELS,
    OVERRIDE_IF_STATED,
    RECOMPUTE_ALWAYS_ON_RETRY,
)


def overrides_from_utterance(user_message: str) -> dict[str, Any]:
    """Map retry-utterance parses onto schema fields. Retry text only."""

    from ..conversation.foundation.image_generation_defaults import (
        parse_image_generation_overrides,
    )

    parsed = parse_image_generation_overrides(user_message or "")
    mapped: dict[str, Any] = {}
    if "route" in parsed:
        mapped["route"] = parsed["route"]
    if "provider_kind" in parsed:
        kind = str(parsed["provider_kind"] or "")
        mapped["provider"] = "fal" if kind in {"fal", "hosted", "api"} else kind
        if kind in {"fal", "hosted", "api", "kie", "wavespeed"}:
            mapped["requestedProvider"] = "fal" if kind in {"fal", "hosted", "api"} else kind
    if "explicit_provider" in parsed:
        mapped["modelId"] = parsed["explicit_provider"]
        mapped["requestedModelId"] = parsed["explicit_provider"]
        mapped["requestedProvider"] = ""
    if "aspect_ratio" in parsed:
        mapped["aspectRatio"] = parsed["aspect_ratio"]
    if "width" in parsed:
        mapped["width"] = parsed["width"]
    if "height" in parsed:
        mapped["height"] = parsed["height"]
    from ..image_route.lock import parse_route_lock

    lock = parse_route_lock(user_message or "")
    if lock.restated:
        mapped["lockLevel"] = lock.level
        mapped["lockScope"] = lock.scope
        if lock.requested_provider:
            mapped["requestedProvider"] = lock.requested_provider
        if lock.requested_model_id:
            mapped["requestedModelId"] = lock.requested_model_id
            mapped["modelId"] = lock.requested_model_id
    return mapped


def apply_typed_inheritance(
    prior: CanonicalGenerationRequest,
    *,
    overrides: dict[str, Any],
    project_id: str,
    conversation_id: str = "",
    source_message_id: str = "",
) -> tuple[CanonicalGenerationRequest, InheritAudit]:
    """Build a new request field-by-field from allowlists."""

    stated = {key: value for key, value in (overrides or {}).items() if key in OVERRIDE_IF_STATED}
    inherited: list[str] = []
    overridden: list[str] = []
    recompiled = sorted(RECOMPUTE_ALWAYS_ON_RETRY)

    prior_lock = str(prior.lockLevel or "").strip().upper()

    def _take(field: str, prior_value: Any, default: Any = None) -> Any:
        if field in stated:
            overridden.append(field)
            return stated[field]
        if (
            field in GENERATOR_LOCK_FIELDS
            and prior_lock not in LOCKED_ROUTE_LEVELS
        ):
            return default
        if field in INHERIT_EXACT or field in OVERRIDE_IF_STATED:
            inherited.append(field)
            return prior_value
        return default

    nxt = CanonicalGenerationRequest(
        requestId=str(uuid4()),
        projectId=project_id or prior.projectId,
        conversationId=conversation_id or prior.conversationId,
        sourceMessageId=source_message_id,
        artifactType=_take("artifactType", prior.artifactType, "image"),
        action=_take("action", prior.action, "image.generate"),
        originalUserInstructions=_take("originalUserInstructions", prior.originalUserInstructions, ""),
        resolvedCreativeBrief=prior.resolvedCreativeBrief,
        compiledGeneratorPrompt="",
        referenceAssetIds=list(_take("referenceAssetIds", list(prior.referenceAssetIds), [])),
        visionFacts=str(_take("visionFacts", prior.visionFacts, "") or ""),
        referenceRole=str(_take("referenceRole", prior.referenceRole, "") or ""),
        characterIds=list(_take("characterIds", list(prior.characterIds), [])),
        propIds=list(_take("propIds", list(prior.propIds), [])),
        environmentIds=list(_take("environmentIds", list(prior.environmentIds), [])),
        continuityConstraints=_take("continuityConstraints", prior.continuityConstraints, ""),
        negativeConstraints=_take("negativeConstraints", prior.negativeConstraints, ""),
        qualityIntent=_take("qualityIntent", prior.qualityIntent, ""),
        route=_take("route", prior.route, ""),
        provider=_take("provider", prior.provider, ""),
        modelId=_take("modelId", prior.modelId, ""),
        aspectRatio=_take("aspectRatio", prior.aspectRatio, ""),
        width=int(_take("width", prior.width, 0) or 0),
        height=int(_take("height", prior.height, 0) or 0),
        generationParameters={},
        workflowKey="",
        providerPayload={},
        executionId="",
        jobIds=[],
        resultAssetIds=[],
        parentRequestId=prior.requestId,
        revision=int(prior.revision or 1) + 1,
        createdAt="",
        lockLevel=str(_take("lockLevel", prior.lockLevel, "") or ""),
        lockScope=str(_take("lockScope", prior.lockScope, "") or ""),
        requestedProvider=str(_take("requestedProvider", prior.requestedProvider, "") or ""),
        requestedModelId=str(_take("requestedModelId", prior.requestedModelId, "") or ""),
        fallbackAudit={},
    )
    nxt.inheritAudit = InheritAudit(
        inherited=sorted(set(inherited)),
        overridden=sorted(set(overridden)),
        recompiled=recompiled,
    )
    return nxt, nxt.inheritAudit


def context_from_request(request: CanonicalGenerationRequest) -> dict[str, Any]:
    """Execution ctx built from a typed request. Prompt is always the original brief."""

    return {
        "prompt": request.originalUserInstructions,
        "canonical_original_instructions": request.originalUserInstructions,
        "original_user_instructions": request.originalUserInstructions,
        "canonical_resolved": True,
        "used_chat_inherit": False,
        "parent_request_id": request.parentRequestId,
        "canonical_request_id": request.requestId,
        "aspect_ratio": request.aspectRatio,
        "width": request.width,
        "height": request.height,
        "provider_kind": request.provider,
        "generation_route": request.route,
        "explicit_provider": (
            request.modelId or request.requestedModelId
            if str(request.lockLevel or "").strip().upper() in LOCKED_ROUTE_LEVELS
            else ""
        ),
        "model": request.modelId,
        "lock_level": request.lockLevel,
        "lock_scope": request.lockScope,
        "requested_provider": request.requestedProvider,
        "requested_model_id": request.requestedModelId,
        "hosted_model_id": request.modelId if request.provider in {"fal", "hosted", "api"} else "",
        "fal_image_model_id": request.modelId if request.provider in {"fal", "hosted", "api"} else "",
        "reference_asset_id": (request.referenceAssetIds[0] if request.referenceAssetIds else ""),
        "attachment_asset_ids": list(request.referenceAssetIds),
        "vision_facts": request.visionFacts,
        "reference_role": request.referenceRole,
        "resolved_creative_brief": request.resolvedCreativeBrief,
        "character_id": (request.characterIds[0] if request.characterIds else ""),
        "character_ids": list(request.characterIds),
        "artifact_type": request.artifactType,
        "action": request.action,
        "conversation_id": request.conversationId,
        "source_message_id": request.sourceMessageId,
        "continuity_constraints": request.continuityConstraints,
        "negative_constraints": request.negativeConstraints,
        "quality_intent": request.qualityIntent,
        "inherit_audit": request.inheritAudit.model_dump() if request.inheritAudit else {},
    }
