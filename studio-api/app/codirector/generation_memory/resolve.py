"""Resolve referential retry from pack memory. Canonical request is sole authority."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from .contracts import CanonicalGenerationRequest, ResolvedRetry
from .inherit import apply_typed_inheritance, context_from_request, overrides_from_utterance
from .referential import (
    image_index_hint,
    is_referential_generation,
    named_hints,
    names_excluded_surface,
    requested_artifact_type,
    source_artifact_type,
    target_artifact_type,
)
from .store import list_generation_requests

NO_PRIOR_ASK = (
    "I don't have a previous picture request to reuse. Tell me what to generate, or paste the prompt."
)
NO_PRIOR_BY_ARTIFACT = {
    "image": NO_PRIOR_ASK,
    "video": "I don't have a previous video request to reuse. Tell me what to generate, or paste the prompt.",
    "audio": "I don't have a previous audio request to reuse. Tell me what to generate, or paste the prompt.",
}
WHICH_IMAGE_ASK = "Which picture should I reuse — the latest one, or a specific one?"


def _pack_status(pack: Any) -> str:
    value = getattr(pack, "status", "")
    return str(getattr(value, "value", value) or "").lower()


def _select_prior(
    rows: list[tuple[Any, CanonicalGenerationRequest]],
    user_message: str,
    *,
    selected_execution_id: str = "",
    selected_asset_id: str = "",
) -> tuple[CanonicalGenerationRequest | None, str]:
    if selected_execution_id:
        for pack, req in rows:
            if pack.execution_id == selected_execution_id:
                return req, ""
    if selected_asset_id:
        matches = [
            req
            for _pack, req in rows
            if selected_asset_id in (req.resultAssetIds or [])
        ]
        if len(matches) == 1:
            return matches[0], ""
        if len(matches) > 1:
            return None, WHICH_IMAGE_ASK

    hints = named_hints(user_message)
    pool = rows
    if hints:
        hinted = [
            (pack, req)
            for pack, req in rows
            if any(
                re.search(rf"\b{re.escape(h)}\b", req.originalUserInstructions or "", re.I)
                for h in hints
            )
        ]
        if not hinted:
            return None, WHICH_IMAGE_ASK
        pool = hinted

    index = image_index_hint(user_message)
    if index is not None:
        if index < 1 or index > len(pool):
            return None, WHICH_IMAGE_ASK
        return pool[index - 1][1], ""

    in_progress = [
        (pack, req)
        for pack, req in pool
        if _pack_status(pack) in {"queued", "preparing", "running", "preview"}
    ]
    if len(in_progress) == 1 and not hints:
        return in_progress[0][1], ""

    if not pool:
        return None, NO_PRIOR_ASK
    return pool[0][1], ""


_TARGET_ACTIONS = {
    "image": "image.generate",
    "video": "video.generate",
    "audio": "audio.sfx",
}


def _overrides_for_retry(
    prior: CanonicalGenerationRequest,
    user_message: str,
    *,
    target: str,
) -> dict[str, Any]:
    overrides = overrides_from_utterance(user_message)
    prior_family = str(prior.artifactType or "").split(".")[0]
    if target and target != prior_family:
        overrides["artifactType"] = target
        overrides["action"] = _TARGET_ACTIONS.get(target, f"{target}.generate")
        if target == "video":
            refs = list(
                dict.fromkeys(
                    [*(prior.resultAssetIds or []), *(prior.referenceAssetIds or [])]
                )
            )
            if refs:
                overrides["referenceAssetIds"] = refs
    return overrides


def resolve_canonical_retry(
    db: Session,
    project_id: str,
    user_message: str,
    *,
    conversation_id: str = "",
    source_message_id: str = "",
    selected_execution_id: str = "",
    selected_asset_id: str = "",
) -> ResolvedRetry | None:
    """Deterministic resolver. No embeddings, no chat reconstruction."""

    if names_excluded_surface(user_message):
        return None
    if not is_referential_generation(user_message):
        return None
    if not project_id:
        return ResolvedRetry(clarification=NO_PRIOR_ASK)

    source = source_artifact_type(user_message)
    target = target_artifact_type(user_message)
    rows = list_generation_requests(
        db,
        project_id,
        artifact_type=source,
    )
    if not rows:
        return ResolvedRetry(clarification=NO_PRIOR_BY_ARTIFACT.get(source or target or "image", NO_PRIOR_ASK))

    prior, clarification = _select_prior(
        rows,
        user_message,
        selected_execution_id=selected_execution_id,
        selected_asset_id=selected_asset_id,
    )
    if clarification or prior is None:
        return ResolvedRetry(prior=prior, clarification=clarification or WHICH_IMAGE_ASK)

    nxt, audit = apply_typed_inheritance(
        prior,
        overrides=_overrides_for_retry(prior, user_message, target=target),
        project_id=project_id,
        conversation_id=conversation_id,
        source_message_id=source_message_id,
    )
    return ResolvedRetry(
        prior=prior,
        next_request=nxt,
        audit=audit,
        used_chat_inherit=False,
        clarification="",
    )


def apply_canonical_retry_to_context(
    ctx: dict[str, Any],
    resolved: ResolvedRetry,
    *,
    retry_utterance: str = "",
) -> dict[str, Any]:
    """Apply a typed next request onto execution ctx. Field-by-field, no request merge."""

    request = resolved.next_request
    if request is None:
        return ctx
    built = context_from_request(request)
    for key, value in built.items():
        ctx[key] = value
    ctx["user_instructions"] = retry_utterance or ""
    ctx["used_chat_inherit"] = False
    ctx["canonical_revision"] = request.revision
    ctx["explicit_provider"] = request.modelId or ""
    return ctx
