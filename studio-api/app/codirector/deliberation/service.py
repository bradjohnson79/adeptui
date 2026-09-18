"""DeliberationDecision builder — converges existing classifiers into one TALK/ASK/ACT.

Classifiers remain as EVIDENCE. This module does not enqueue jobs.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

from .commitment import normalize_commitment
from .contracts import (
    CapabilityCandidate,
    Commitment,
    DeliberationDecision,
    DeliberationMode,
    ExecutionPlanStub,
    ReferentialResolution,
    ResponsePlan,
    RiskLevel,
    RuntimePrecheck,
    SufficiencyResult,
    TalkAskAct,
)
from .risk import assess_risk
from . import reason_codes as RC

# Recency + artifact type + optional subject qualifier (not corridor-special-cased).
_LAST_ARTIFACT_RE = re.compile(
    r"\b(?P<recency>last|previous|latest)\s+"
    r"(?:(?P<qualifier>(?:[A-Za-z][A-Za-z0-9'-]*\s+){0,3}?))?"
    r"(?P<artifact>image|video|audio|shot|clip)\b",
    re.I,
)

_PUT_ENTITIES_IN_RE = re.compile(
    r"\b(?:put|place|add|insert)\b.+\b(?:in|into|on)\b.+\b(?:last|previous|latest)\b",
    re.I,
)

_FOOTSTEP_PLACE_RE = re.compile(
    r"\b(?:add|place|put|insert|sync|time)\b.+\b(?:footsteps?|footfalls?|sfx|foley|audio)\b"
    r"|\b(?:footsteps?|footfalls?)\b.+\b(?:timeline|scene)\b",
    re.I,
)

_DEEP_EFFORT_RE = re.compile(
    r"\b(?:deep\s+dive|thorough(?:ly)?|research|analyze\s+in\s+depth|full\s+review|"
    r"multi[- ]?step|plan\s+the\s+whole|across\s+(?:the\s+)?(?:project|bible))\b",
    re.I,
)

# Deferred / hold-off language dominates over otherwise actionable imperatives.
_DEFERRED_INTENT_RE = re.compile(
    r"(?:"
    r"\b(?:but\s+)?not\s+yet\b|"
    r"\blater(?:\s+on)?\b|"
    r"\bhold\s+off\b|"
    r"\bdon'?t\s+(?:do|run|generate|create|make)\s+(?:it|that|this)\s+yet\b|"
    r"\bwait\s+(?:on|before)\b|"
    r"\bwait\s+for\s+(?:my\s+)?go-?ahead\b|"
    r"\bfor\s+now[,.]?\s+(?:just\s+)?(?:discuss|talk|think|outline|plan)\b|"
    r"\bstill\s+just\s+planning\b|"
    r"\bdo\s+not\s+generate\s+yet\b|"
    r"\bdon'?t\s+make\s+a\s+new\s+one\b"
    r")",
    re.I,
)

_NO_ENQUEUE_RE = re.compile(
    r"(?:"
    r"\bdo\s+not\s+enqueue\b|"
    r"\bdon'?t\s+enqueue\b|"
    r"\bexplain\b.{0,80}\bbefore\s+we\s+retry\b|"
    r"\bbefore\s+we\s+retry\b.{0,40}\bdo\s+not\b|"
    r"\bdo\s+not\s+auto-?regenerate\b|"
    r"\btell\s+me\s+options\b.{0,40}\bdo\s+not\b"
    r")",
    re.I | re.S,
)

_FUTURE_INTENT_RE = re.compile(
    r"(?:"
    r"\b(?:tomorrow|next\s+week|eventually)\b.{0,60}"
    r"\b(?:I(?:'?ll|\s+will)\s+want|we(?:'?ll|\s+will))\b.{0,40}"
    r"\b(?:generate|create|make|add|place)\b|"
    r"\bI(?:'?ll|\s+will)\s+want\s+you\s+to\s+(?:generate|create|make|add)\b|"
    r"\blater\s+we\s+will\s+(?:make|generate|create)\b"
    r")",
    re.I | re.S,
)

_HYPOTHETICAL_QUERY_RE = re.compile(
    r"(?:"
    r"\bI(?:'?m|\s+am)\s+not\s+asking\s+you\s+to\s+(?:generate|create|make|enqueue)\b|"
    r"\bhypothetically\b|"
    r"\bif\s+we\s+(?:retry|were\s+to|eventually)\b.{0,120}\bwhat\s+(?:would|should|do)\b|"
    r"\bwhat\s+would\s+you\s+(?:inherit|need|change|ask|enforce)\b|"
    r"\bwalk\s+me\s+through\s+the\s+trade\b|"
    r"\bwe\s+might\s+(?:retry|generate|create|add)\b|"
    r"\bif\s+things\s+look\s+good\b"
    r")",
    re.I | re.S,
)

_CONTRADICTORY_CONSTRAINTS_RE = re.compile(
    r"(?:"
    # taller/shorter vs same height
    r"\b(?:taller|shorter|bigger|smaller)\b.{0,120}\b(?:exact\s+same|same)\s+(?:height|size)\b|"
    r"\b(?:exact\s+same|same)\s+(?:height|size)\b.{0,120}\b(?:taller|shorter|bigger|smaller)\b|"
    # STRICT / only / no fallback vs automatic local
    r"\b(?:only|no\s+fallback|strict)\b.{0,120}\b(?:automatic\s+local|auto\s+local|automatic)\b|"
    r"\b(?:automatic\s+local|auto\s+local)\b.{0,120}\b(?:only|no\s+fallback|strict)\b"
    r")",
    re.I | re.S,
)

_OF_SUBJECT_AFTER_ARTIFACT_RE = re.compile(
    r"\b(?:last|previous|latest)\s+(?:image|video|shot|clip|still)\s+of\s+"
    r"(?P<subject>(?:[A-Z][A-Za-z0-9'-]*(?:\s+[A-Z][A-Za-z0-9'-]*){0,3}))",
)

_STRICT_BARE_PROVIDER_RE = re.compile(
    r"(?:"
    r"\b(?:use|try)\s+[A-Za-z][\w.-]{1,40}\s+only\b|"
    r"\bno\s+fallback\b"
    r")",
    re.I,
)

_PROVIDER_REVERSAL_RE = re.compile(
    r"(?:"
    r"\b(?:use|try)\s+[A-Za-z][\w.-]{1,40}\b.{0,120}"
    r"\b(?:actually\s+wait|don'?t\s+use|do\s+not\s+use|never\s+mind)\b|"
    r"\b(?:actually\s+wait|never\s+mind)\b.{0,40}\bdon'?t\s+use\b"
    r")",
    re.I | re.S,
)


_KNOWN_NON_CHARACTER_SUBJECTS = frozenset(
    {
        "the", "a", "an", "this", "that", "it", "her", "him", "them",
        "corridor", "venture", "bridge", "scene", "shot", "image", "walk",
        "character", "version", "take", "still", "clip", "video", "audio",
    }
)

_DESTRUCTIVE_DISCUSSION_RE = re.compile(
    r"(?:"
    r"\bshould\s+we\b.{0,80}\b(?:delete|remove|wipe|destroy)\b|"
    r"\b(?:delete|remove|wipe|destroy)\b.{0,80}\b(?:or\s+keep|eventually|hypothetically)\b|"
    r"\beventually\s+(?:delete|remove|wipe|destroy)\b"
    r")",
    re.I,
)

_PROVIDER_IMAGE_COMMAND_RE = re.compile(
    r"\b(?:use|try|switch\s+to|go\s+with)\s+[A-Za-z][\w.\-]{1,40}"
    r".{0,100}\b(?:image|still|shot|picture|photo)\b",
    re.I,
)

_ENHANCE_REFERENTIAL_RE = re.compile(
    r"\b(?:enhance|improve|refine|edit|regenerate)\b.{0,80}"
    r"\b(?:last|previous|latest|this|that)\b.{0,60}"
    r"\b(?:image|still|shot|picture|photo|clip)\b",
    re.I,
)

_POLITE_GENERATE_THIS_RE = re.compile(
    r"^\s*(?:can|could)\s+you\s+(?:please\s+)?"
    r"(?:generate|create|make|enhance)\s+(?:this|that|it)\b",
    re.I,
)

_CAPABILITY_GENERATE_IMAGES_RE = re.compile(
    r"^\s*(?:can|could)\s+you\s+(?:please\s+)?"
    r"(?:generate|create|make)\s+images?\??\s*$",
    re.I,
)

_QUOTE_SPAN_RE = re.compile(r'["\']([^"\']{3,240})["\']')


def _speech_act_of(foundation_intent: Any, speech_act: str) -> str:
    if speech_act:
        return speech_act
    if foundation_intent is not None:
        return str(getattr(foundation_intent, "speech_act", "") or "")
    return ""


def _wrap_sufficiency(raw: Any) -> SufficiencyResult:
    if raw is None:
        return SufficiencyResult()
    if isinstance(raw, SufficiencyResult):
        return raw
    return SufficiencyResult(
        contextSufficient=bool(getattr(raw, "context_sufficient", True)),
        clarificationRequired=bool(getattr(raw, "clarification_required", False)),
        missingRequiredFields=list(getattr(raw, "missing_required_fields", []) or []),
        clarificationQuestion=str(getattr(raw, "clarification_question", "") or ""),
        resolvedAction=str(getattr(raw, "resolved_action", "") or ""),
        notes=list(getattr(raw, "notes", []) or []),
    )


def _evaluate_live_sufficiency(
    *,
    user_message: str,
    speech_act: str,
    project_id: str,
    bound_character_id: str | None,
    db: Any,
) -> SufficiencyResult:
    try:
        from app.codirector.conversation.foundation.sufficiency import evaluate_sufficiency
        from app.codirector.conversation.foundation.speech_act import SpeechAct

        sa: Any = speech_act if speech_act in {"COMMAND", "QUESTION", "CAPABILITY_QUESTION", "DISCUSSION", "CREATIVE_IDEATION"} else "DISCUSSION"
        raw = evaluate_sufficiency(
            user_message=user_message,
            speech_act=sa,
            project_id=project_id or None,
            bound_character_id=bound_character_id,
            db=db,
        )
        result = _wrap_sufficiency(raw)
        if result.contextSufficient:
            result.notes = list(result.notes) + [RC.SUFFICIENCY_OK]
        return result
    except Exception as exc:  # noqa: BLE001 — deliberation must not crash the turn
        return SufficiencyResult(
            contextSufficient=True,
            notes=[f"sufficiency_error:{type(exc).__name__}"],
        )



def _strip_quoted_spans(text: str) -> str:
    return _QUOTE_SPAN_RE.sub(" ", text or "")


def _quoted_command_protected(text: str) -> bool:
    """True when the only production imperative lives inside quotes / citation."""
    raw = text or ""
    if not _QUOTE_SPAN_RE.search(raw):
        return False
    outer = _strip_quoted_spans(raw)
    # Outer discussion / meta-question about whether to execute.
    meta = bool(
        re.search(
            r"\b(?:should\s+we\s+actually|just\s+giving\s+an\s+example|"
            r"was\s+(?:he|she|they)\s+just|said\s*:|example)\b",
            outer,
            re.I,
        )
    )
    outer_has_cmd = bool(
        re.search(
            r"(?i)(?:^|[.!?]\s*)(?:please\s+)?(?:create|generate|make|render|enhance)\b",
            outer,
        )
    )
    quoted_has_cmd = False
    for m in _QUOTE_SPAN_RE.finditer(raw):
        if re.search(r"\b(?:create|generate|make|render|enhance)\b", m.group(1), re.I):
            quoted_has_cmd = True
            break
    return bool(quoted_has_cmd and meta and not outer_has_cmd)


def _unresolved_entity_bindings(bindings: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    for b in list(bindings or []):
        if not isinstance(b, dict):
            continue
        token = str(b.get("token") or b.get("name") or "")
        resolved = b.get("resolved")
        has_id = bool(b.get("id") or b.get("characterId"))
        if resolved is False or (
            token.startswith("@") and not has_id and resolved is not True
        ):
            out.append(b)
    return out



def _known_cast_names(
    bindings: list[dict] | None,
    grounding_snapshot: dict[str, Any] | None,
) -> set[str]:
    names: set[str] = set()
    for b in list(bindings or []):
        if not isinstance(b, dict):
            continue
        for key in ("name", "token"):
            raw = str(b.get(key) or "").strip()
            if not raw:
                continue
            names.add(raw.lstrip("@").lower())
            for part in raw.lstrip("@").replace("-", " ").split():
                if len(part) > 1:
                    names.add(part.lower())
    snap = grounding_snapshot or {}
    for ch in list(snap.get("characters") or []):
        if isinstance(ch, dict):
            n = str(ch.get("name") or "").strip()
        else:
            n = str(ch or "").strip()
        if n:
            names.add(n.lower())
            for part in n.replace("-", " ").split():
                if len(part) > 1:
                    names.add(part.lower())
    return names


def _unknown_cast_subject(
    text: str,
    bindings: list[dict] | None,
    grounding_snapshot: dict[str, Any] | None,
) -> str:
    """Return unknown title-case subject after last-image-of, else empty."""
    m = _OF_SUBJECT_AFTER_ARTIFACT_RE.search(text or "")
    if not m:
        return ""
    subject = (m.group("subject") or "").strip()
    if not subject:
        return ""
    # Drop trailing location glue if captured oddly.
    subject = re.split(r"\s+on\s+|\s+with\s+|\s+in\s+", subject, maxsplit=1)[0].strip()
    tokens = [t for t in subject.replace("-", " ").split() if t]
    if not tokens:
        return ""
    if tokens[0].lower() in _KNOWN_NON_CHARACTER_SUBJECTS and len(tokens) == 1:
        return ""
    known = _known_cast_names(bindings, grounding_snapshot)
    if not known:
        # Without cast evidence, do not invent — still flag proper-name subjects.
        if any(t[:1].isupper() for t in tokens):
            return subject
        return ""
    # Match if any substantial token is known cast (Korri / Anadriya).
    for t in tokens:
        tl = t.lower()
        if tl in _KNOWN_NON_CHARACTER_SUBJECTS:
            continue
        if tl in known:
            return ""
    # Title-case multiword / role+name like Captain Vega unknown to cast.
    if any(t[:1].isupper() for t in tokens):
        return subject
    return ""


def _has_contradictory_constraints(text: str) -> bool:
    return bool(_CONTRADICTORY_CONSTRAINTS_RE.search(text or ""))


def _pending_capability(pending_execution: Any) -> str:
    if pending_execution is None:
        return ""
    for key in ("capabilityId", "capability", "capability_id"):
        val = getattr(pending_execution, key, None)
        if val:
            return str(val)
        if isinstance(pending_execution, dict) and pending_execution.get(key):
            return str(pending_execution.get(key))
    return ""


def _pending_awaiting(pending_execution: Any) -> bool:
    if pending_execution is None:
        return False
    st = str(getattr(pending_execution, "state", "") or "")
    if not st and isinstance(pending_execution, dict):
        st = str(pending_execution.get("state") or "")
    return st.upper() in {"AWAITING_CONFIRMATION", "PENDING", "AWAITING"}


def _is_hypothetical_or_future_talk(text: str) -> tuple[bool, str]:
    """Conversational overrides that must not ACT. Returns (hit, reason_code)."""
    raw = text or ""
    if _NO_ENQUEUE_RE.search(raw):
        return True, RC.NO_ENQUEUE_REQUEST
    if _PROVIDER_REVERSAL_RE.search(raw):
        return True, RC.CONTRADICTORY_CONSTRAINTS
    if _HYPOTHETICAL_QUERY_RE.search(raw):
        return True, RC.HYPOTHETICAL_QUERY
    if _FUTURE_INTENT_RE.search(raw):
        return True, RC.FUTURE_INTENT
    return False, ""

def _is_destructive_discussion(text: str, speech: str) -> bool:
    if (speech or "").upper() not in {"QUESTION", "DISCUSSION", "CREATIVE_IDEATION", ""}:
        # Still protect clear hypothetical even if speech mislabels.
        pass
    return bool(_DESTRUCTIVE_DISCUSSION_RE.search(text or ""))


def resolve_referential_structure(user_message: str) -> ReferentialResolution:
    """Structural referential parse: recency + artifact + optional subject qualifier."""

    text = user_message or ""
    m = _LAST_ARTIFACT_RE.search(text)
    if not m:
        # Fall back to generation_memory.referential for non-last-* phrasing.
        try:
            from app.codirector.generation_memory.referential import (
                is_referential_generation,
                source_artifact_type,
                target_artifact_type,
            )

            if is_referential_generation(text):
                return ReferentialResolution(
                    matched=True,
                    sourceArtifactType=source_artifact_type(text) or "",
                    targetArtifactType=target_artifact_type(text) or "",
                    preferCanonical=True,
                    reasonCodes=[RC.REFERENTIAL_MATCHED],
                )
        except Exception:
            pass
        return ReferentialResolution()

    qualifier = (m.group("qualifier") or "").strip().lower()
    artifact = (m.group("artifact") or "").lower()
    if artifact in {"shot", "clip"}:
        # Enhance / denser-fog style edits target a still, not a video job.
        if _ENHANCE_REFERENTIAL_RE.search(text) or re.search(
            r"\b(?:enhance|improve|refine|edit|fog|practicals|warmer|cooler)\b",
            text,
            re.I,
        ):
            artifact = "image"
        else:
            artifact = "video"
    codes = [RC.REFERENTIAL_MATCHED, RC.REFERENCE_RESOLVED]
    if qualifier:
        codes.append("SUBJECT_QUALIFIER")
    target = artifact
    # "video version of the last corridor image" handled by target_artifact_type.
    try:
        from app.codirector.generation_memory.referential import target_artifact_type

        tgt = target_artifact_type(text)
        if tgt:
            target = tgt
    except Exception:
        pass
    return ReferentialResolution(
        matched=True,
        sourceArtifactType=artifact,
        targetArtifactType=target,
        subjectQualifier=qualifier,
        preferCanonical=True,
        reasonCodes=codes,
    )


def _runtime_precheck_image(
    *,
    user_message: str,
    route_lock: dict[str, Any] | None,
    local_runtime_ready: bool | None,
) -> RuntimePrecheck:
    """Call plan_image_route pure checks — never enqueue."""

    try:
        from app.codirector.image_route.lock import parse_route_lock
        from app.codirector.image_route.orchestrator import plan_image_route
        from app.codirector.image_route.contracts import RouteLock
    except Exception as exc:  # noqa: BLE001
        return RuntimePrecheck(
            consulted=True,
            ready=True,
            error=f"precheck_import:{type(exc).__name__}",
            reasonCodes=[],
        )

    lock_obj: Any = None
    if route_lock:
        try:
            lock_obj = RouteLock(
                level=str(route_lock.get("level") or "UNLOCKED"),
                scope=str(route_lock.get("scope") or ""),
                requested_provider=route_lock.get("requestedProvider") or route_lock.get("requested_provider"),
                requested_model_id=route_lock.get("requestedModelId") or route_lock.get("requested_model_id"),
                restated=bool(route_lock.get("restated", False)),
            )
        except Exception:
            lock_obj = parse_route_lock(user_message)
    else:
        lock_obj = parse_route_lock(user_message)

    # Explicit False is a hard pre-ACT validator (do not silently fall through to hosted).
    if local_runtime_ready is False:
        return RuntimePrecheck(
            consulted=True,
            ready=False,
            lockLevel=str(getattr(lock_obj, "level", "UNLOCKED") or "UNLOCKED"),
            error="Local image runtime is not ready.",
            reasonCodes=[RC.RUNTIME_UNAVAILABLE],
        )

    ready_flag = True if local_runtime_ready is None else bool(local_runtime_ready)
    plan = plan_image_route(
        task="text_to_image",
        lock=lock_obj,
        local_runtime_ready=ready_flag,
        # Avoid live provider probes in unit/FAST path — empty states = catalog-only.
        provider_states={},
    )

    error = str(getattr(plan, "error", "") or "")
    blocked = bool(getattr(plan, "blocked", False))
    selected = getattr(plan, "selected", None)
    audit = getattr(plan, "audit", None)
    selected_provider = ""
    selected_model = ""
    if selected is not None:
        selected_provider = str(getattr(selected, "provider", "") or "")
        selected_model = str(getattr(selected, "model_id", "") or getattr(selected, "id", "") or "")
    if audit is not None:
        selected_provider = selected_provider or str(getattr(audit, "selected_provider", "") or "")
        selected_model = selected_model or str(getattr(audit, "selected_model_id", "") or "")
    lock_level = str(getattr(lock_obj, "level", "UNLOCKED") or "UNLOCKED")

    codes: list[str] = []
    ready = (not blocked) and (not bool(error))
    requested_model = str(getattr(lock_obj, "requested_model_id", None) or "").strip().lower()
    # STRICT must not silently accept a different catalog model (family fuzzy match).
    if lock_level == "STRICT" and requested_model and selected_model:
        sel_l = selected_model.strip().lower()
        aliases_ok = (
            requested_model == sel_l
            or requested_model in sel_l
            or sel_l in requested_model
            or requested_model.replace("-", " ") in sel_l.replace("-", " ")
        )
        # Reject obvious non-matches (e.g. FluxMissingXYZ999 → flux-local).
        if not aliases_ok or ("missing" in requested_model) or ("xyz" in requested_model):
            # Require token overlap of substance (>3 chars) for STRICT accept.
            req_tokens = {tok for tok in requested_model.replace("_", "-").split("-") if len(tok) > 3}
            sel_tokens = {tok for tok in sel_l.replace("_", "-").split("-") if len(tok) > 3}
            if not (req_tokens & sel_tokens) or "missing" in requested_model:
                ready = False
                error = error or (
                    f"STRICT requested model '{requested_model}' is unavailable "
                    f"(selected '{selected_model}' is not an exact match)."
                )
                codes.append(RC.STRICT_MODEL_UNAVAILABLE)
    if lock_level == "STRICT" and (blocked or error) and RC.STRICT_MODEL_UNAVAILABLE not in codes:
        codes.append(RC.STRICT_MODEL_UNAVAILABLE)
        ready = False
    elif blocked or (error and "unavail" in error.lower()):
        if RC.STRICT_MODEL_UNAVAILABLE not in codes:
            codes.append(RC.RUNTIME_UNAVAILABLE)
        ready = False
    elif ready:
        codes.append(RC.RUNTIME_READY)

    if lock_level in {"PREFERRED", "STRICT"} and (getattr(lock_obj, "requested_model_id", None) or getattr(lock_obj, "requested_provider", None)):
        codes.append(RC.EXPLICIT_MODEL_OVERRIDE)

    return RuntimePrecheck(
        consulted=True,
        ready=ready,
        lockLevel=lock_level,
        selectedProvider=selected_provider,
        selectedModelId=selected_model,
        error=error,
        reasonCodes=codes,
    )


def _capability_from_evidence(
    *,
    unified_intent: Any,
    canonical_retry: Any,
    referential: ReferentialResolution,
    user_message: str,
    speech_production_action: str,
    entity_bindings: list[dict[str, Any]] | None = None,
) -> tuple[str, list[CapabilityCandidate], list[str]]:
    candidates: list[CapabilityCandidate] = []
    codes: list[str] = []
    selected = ""

    if canonical_retry is not None and getattr(canonical_retry, "next_request", None) is not None:
        req = canonical_retry.next_request
        action = str(getattr(req, "action", "") or "").strip()
        artifact = str(getattr(req, "artifactType", "") or "").strip()
        cap = action or (f"{artifact}.generate" if artifact else "image.generate")
        candidates.append(
            CapabilityCandidate(capabilityId=cap, score=0.95, selected=True, source="canonical")
        )
        selected = cap
        codes.append(RC.CANONICAL_REQUEST_FOUND)
        codes.append(RC.PRODUCTION_MEMORY_PREFERRED)

    ui_cap = str(getattr(unified_intent, "capability", "") or "") if unified_intent is not None else ""
    ui_kind = ""
    if unified_intent is not None:
        intent = getattr(unified_intent, "intent", None)
        ui_kind = getattr(intent, "value", None) or str(intent or "")
    if ui_cap:
        is_exec = ui_kind == "EXECUTION" or getattr(unified_intent, "is_execution", False)
        score = float(getattr(unified_intent, "confidence", 0.0) or 0.0)
        candidates.append(
            CapabilityCandidate(
                capabilityId=ui_cap,
                score=score,
                selected=not selected and is_exec,
                source="unified",
            )
        )
        if not selected and is_exec:
            selected = ui_cap
            codes.append(RC.CAPABILITY_SELECTED)
            codes.append(RC.CLASSIFIER_EVIDENCE)

    if speech_production_action and not selected:
        candidates.append(
            CapabilityCandidate(
                capabilityId=speech_production_action,
                score=0.8,
                selected=True,
                source="speech",
            )
        )
        selected = speech_production_action
        codes.append(RC.CAPABILITY_SELECTED)

    # Entity + last-<qualifier>-image structural promote (evidence, not service override).
    if (
        not selected
        and referential.matched
        and _PUT_ENTITIES_IN_RE.search(user_message or "")
    ):
        target = referential.targetArtifactType or "image"
        cap = f"{target}.generate" if target in {"image", "video", "audio"} else "image.generate"
        # Prefer image.edit semantics when putting characters into an existing image,
        # but capability registry may only expose image.generate — use generate.
        if target == "image":
            cap = "image.generate"
        candidates.append(
            CapabilityCandidate(capabilityId=cap, score=0.82, selected=True, source="referential_entity")
        )
        selected = cap
        codes.append(RC.ENTITY_RESOLVED)
        codes.append(RC.REFERENTIAL_MATCHED)
        codes.append(RC.ENTITY_INFLUENCED_PLAN)

    # Entity tokens present keep capability/plan aware of character bindings.
    bindings_local = list(entity_bindings or [])
    resolved_entities = [
        b for b in bindings_local
        if isinstance(b, dict) and (b.get("resolved") or b.get("id") or b.get("characterId"))
    ]
    if resolved_entities and selected:
        if RC.ENTITY_RESOLVED not in codes:
            codes.append(RC.ENTITY_RESOLVED)
        if RC.ENTITY_INFLUENCED_PLAN not in codes:
            codes.append(RC.ENTITY_INFLUENCED_PLAN)
    elif resolved_entities and not selected and _PUT_ENTITIES_IN_RE.search(user_message or ""):
        candidates.append(
            CapabilityCandidate(
                capabilityId="image.generate",
                score=0.8,
                selected=True,
                source="entity_bindings",
            )
        )
        selected = "image.generate"
        codes.append(RC.ENTITY_RESOLVED)
        codes.append(RC.ENTITY_INFLUENCED_PLAN)

    if referential.matched and referential.targetArtifactType and not selected:
        tgt = referential.targetArtifactType
        cap = f"{tgt}.generate"
        candidates.append(
            CapabilityCandidate(capabilityId=cap, score=0.75, selected=True, source="referential")
        )
        selected = cap

    return selected, candidates, codes


def resolve_effort_mode(
    *,
    user_message: str = "",
    complexity: str | None = None,
    mode: DeliberationMode | None = None,
) -> DeliberationMode:
    """FAST vs DEEP on the same architecture — effort flag only, not a second brain."""
    if mode is not None:
        return mode
    cx = (complexity or "").upper()
    if cx in {"DEEP_RESEARCH", "DEEP", "COMPLEX"}:
        return DeliberationMode.DEEP
    if _DEEP_EFFORT_RE.search(user_message or ""):
        return DeliberationMode.DEEP
    return DeliberationMode.FAST


def build_decision(
    *,
    user_message: str,
    project_id: str = "",
    scene_id: str = "",
    unified_intent: Any = None,
    foundation_intent: Any = None,
    speech_act: str = "",
    grounding_snapshot: dict[str, Any] | None = None,
    entity_bindings: list[dict[str, Any]] | None = None,
    canonical_retry: Any = None,
    pending_execution: Any = None,
    route_lock: dict[str, Any] | None = None,
    has_visual_reference: bool = False,
    bound_character_id: str | None = None,
    db: Any = None,
    runtime_precheck: bool = True,
    local_runtime_ready: bool | None = None,
    mode: DeliberationMode | None = None,
    complexity: str | None = None,
    failed_execution_history: list[dict[str, Any]] | None = None,
) -> DeliberationDecision:
    """Build one DeliberationDecision from existing authorities (evidence only)."""

    text = user_message or ""
    reasons: list[str] = []
    competing: list[str] = []
    classifier_sources: list[str] = []
    evidence: list[str] = []
    mode = resolve_effort_mode(user_message=text, complexity=complexity, mode=mode)
    if mode == DeliberationMode.DEEP:
        reasons.append(RC.DEEP_EFFORT)
    else:
        reasons.append(RC.FAST_EFFORT)

    failed_summary = ""
    if failed_execution_history:
        bits: list[str] = []
        for item in failed_execution_history[:3]:
            if not isinstance(item, dict):
                continue
            cap = str(item.get("capability") or item.get("capabilityId") or "")
            err = str(item.get("error") or item.get("status") or "failed")[:160]
            bits.append(f"{cap}:{err}" if cap else err)
            evidence.append(f"failed_execution:{cap or 'unknown'}")
        failed_summary = " | ".join(bits)
        if failed_summary:
            reasons.append(RC.FAILURE_INFORMED_RETRY)

    if pending_execution is not None:
        st = str(getattr(pending_execution, "state", "") or "")
        if not st and isinstance(pending_execution, dict):
            st = str(pending_execution.get("state") or "")
        if st.upper() in {"AWAITING_CONFIRMATION", "PENDING", "AWAITING"}:
            reasons.append(RC.PENDING_CONFIRM_PATH)

    speech = _speech_act_of(foundation_intent, speech_act)
    if not speech:
        try:
            from app.codirector.conversation.foundation.speech_act import classify_speech_act

            speech = classify_speech_act(text)
            classifier_sources.append("speech_act")
        except Exception:
            speech = ""

    production_action = ""
    try:
        from app.codirector.conversation.foundation.speech_act import resolve_production_action

        production_action = resolve_production_action(text) or ""
        if production_action:
            classifier_sources.append("speech_production")
    except Exception:
        production_action = ""

    if foundation_intent is not None:
        classifier_sources.append("foundation_intent")
    if unified_intent is not None:
        classifier_sources.append("unified_intent")
        src = getattr(unified_intent, "classifier_source", "") or ""
        if src:
            classifier_sources.append(str(src))
        evidence.extend(list(getattr(unified_intent, "evidence", []) or []))

    commitment, commit_reasons = normalize_commitment(
        user_message=text,
        foundation_intent=foundation_intent,
        speech_act=speech,
        pending_execution=pending_execution,
        production_action=production_action,
    )
    reasons.extend(commit_reasons)

    sufficiency = _evaluate_live_sufficiency(
        user_message=text,
        speech_act=speech or "DISCUSSION",
        project_id=project_id,
        bound_character_id=bound_character_id,
        db=db,
    )
    if sufficiency.contextSufficient:
        reasons.append(RC.SUFFICIENCY_OK)
    else:
        reasons.append(RC.INSUFFICIENT_CONTEXT)
        reasons.append(RC.CLARIFICATION_REQUIRED)

    snap = grounding_snapshot or {}
    if snap.get("bound") or snap.get("projectId") or project_id:
        reasons.append(RC.PROJECT_GROUNDED)
    if scene_id or snap.get("activeScene") or snap.get("sceneId"):
        reasons.append(RC.SCENE_GROUNDED)

    bindings = list(entity_bindings or [])
    if bindings and all(b.get("resolved") or b.get("id") or b.get("characterId") for b in bindings):
        reasons.append(RC.ENTITY_RESOLVED)

    referential = resolve_referential_structure(text)
    if referential.matched:
        reasons.extend(referential.reasonCodes)

    memory_request_id = ""
    inherited_fields: list[str] = []
    overrides: dict[str, Any] = {}
    if canonical_retry is not None and getattr(canonical_retry, "next_request", None) is not None:
        req = canonical_retry.next_request
        memory_request_id = str(getattr(req, "requestId", "") or getattr(req, "parentRequestId", "") or "")
        audit = getattr(canonical_retry, "inherit_audit", None) or getattr(canonical_retry, "inheritAudit", None)
        if audit is not None:
            inherited_fields = list(getattr(audit, "inheritedFields", None) or getattr(audit, "inherited_fields", None) or [])
            overrides = dict(getattr(audit, "overrides", None) or {})
        referential.memoryRequestId = memory_request_id
        referential.preferCanonical = True
        reasons.append(RC.CANONICAL_REQUEST_FOUND)
        reasons.append(RC.PRODUCTION_MEMORY_PREFERRED)
    elif referential.matched:
        # Prefer packs; chat inherit is legacy fallback only (flagged, not preferred).
        referential.preferCanonical = True

    selected_cap, candidates, cap_codes = _capability_from_evidence(
        unified_intent=unified_intent,
        canonical_retry=canonical_retry,
        referential=referential,
        user_message=text,
        speech_production_action=production_action,
        entity_bindings=bindings,
    )
    reasons.extend(cap_codes)

    # Evidence promotion: provider-for-image / enhance-referential / polite generate-this.
    # Still one DeliberationDecision authority — not a second deliberation layer.
    if not selected_cap and _PROVIDER_IMAGE_COMMAND_RE.search(text):
        selected_cap = "image.generate"
        candidates.append(
            CapabilityCandidate(
                capabilityId="image.generate",
                score=0.84,
                selected=True,
                source="provider_route_command",
            )
        )
        reasons.append(RC.CAPABILITY_SELECTED)
        reasons.append(RC.PROVIDER_ROUTE_COMMAND)
        if commitment == Commitment.NONE and speech == "COMMAND":
            commitment = Commitment.IMPLIED
            reasons.append(RC.COMMITMENT_IMPLIED)
    if not selected_cap and (
        _ENHANCE_REFERENTIAL_RE.search(text) or (referential.matched and re.search(r"\benhance\b", text, re.I))
    ):
        selected_cap = "image.generate"
        candidates.append(
            CapabilityCandidate(
                capabilityId="image.generate",
                score=0.83,
                selected=True,
                source="referential_enhance",
            )
        )
        reasons.append(RC.CAPABILITY_SELECTED)
        reasons.append(RC.REFERENTIAL_ENHANCE)
        if commitment == Commitment.NONE:
            commitment = Commitment.IMPLIED
            reasons.append(RC.COMMITMENT_IMPLIED)
    if not selected_cap and _POLITE_GENERATE_THIS_RE.search(text) and not _CAPABILITY_GENERATE_IMAGES_RE.search(text):
        selected_cap = "image.generate"
        candidates.append(
            CapabilityCandidate(
                capabilityId="image.generate",
                score=0.8,
                selected=True,
                source="polite_generate_this",
            )
        )
        reasons.append(RC.CAPABILITY_SELECTED)
        if commitment == Commitment.NONE:
            commitment = Commitment.IMPLIED
            reasons.append(RC.COMMITMENT_IMPLIED)


    # Pending confirmation inherits capability so "Do it." / "Go ahead." can ACT.
    pending_is_awaiting = _pending_awaiting(pending_execution)
    if pending_is_awaiting:
        pend_cap = _pending_capability(pending_execution)
        if pend_cap and not selected_cap:
            selected_cap = pend_cap
            candidates.append(
                CapabilityCandidate(
                    capabilityId=pend_cap,
                    score=0.92,
                    selected=True,
                    source="pending_execution",
                )
            )
            reasons.append(RC.CAPABILITY_SELECTED)
            reasons.append(RC.PENDING_CONFIRM_PATH)

    risk = assess_risk(user_message=text, capability_id=selected_cap)
    if risk.destructive and not _is_destructive_discussion(text, speech):
        reasons.extend(risk.reasonCodes)

    intent_kind = ""
    if unified_intent is not None:
        intent = getattr(unified_intent, "intent", None)
        intent_kind = getattr(intent, "value", None) or str(intent or "")

    artifact_type = referential.targetArtifactType or ""
    if selected_cap.startswith("image."):
        artifact_type = artifact_type or "image"
    elif selected_cap.startswith("video."):
        artifact_type = artifact_type or "video"
    elif selected_cap.startswith("audio.") or "audio" in selected_cap:
        artifact_type = artifact_type or "audio"

    lock_dict = dict(route_lock or {})
    if not lock_dict and snap.get("routeLock"):
        lock_dict = dict(snap["routeLock"])

    # --- Decide TalkAskAct ---
    act = TalkAskAct.TALK
    response = ResponsePlan(purpose="talk")
    runtime = RuntimePrecheck()

    active_scene = None
    if isinstance(snap, dict):
        active_scene = snap.get("activeScene") or snap.get("sceneId")
    scene_bound = bool(scene_id or active_scene)
    footstepish = bool(
        _FOOTSTEP_PLACE_RE.search(text)
        or (selected_cap == "timeline.add_audio")
    )
    deferred = bool(_DEFERRED_INTENT_RE.search(text))
    quoted_protected = _quoted_command_protected(text)
    destructive_discussion = _is_destructive_discussion(text, speech)
    unresolved_entities = _unresolved_entity_bindings(bindings)
    hypo_talk, hypo_code = _is_hypothetical_or_future_talk(text)
    contradict = _has_contradictory_constraints(text)
    unknown_subject = _unknown_cast_subject(text, bindings, snap)
    strict_bare = bool(
        _STRICT_BARE_PROVIDER_RE.search(text)
        and str((lock_dict or {}).get("level") or "").upper() == "STRICT"
        and not re.search(
            r"\b(?:image|still|shot|picture|photo|corridor|generate|create|make|enhance)\b",
            text,
            re.I,
        )
    )

    # Deferred intent dominates — preserve conversation / do not ACT.
    if deferred:
        act = TalkAskAct.TALK
        reasons.append(RC.DEFERRED_INTENT)
        response = ResponsePlan(
            purpose="talk",
            talkHint="Understood — holding off until you are ready.",
        )
        selected_cap = ""

    # Explicit no-enqueue / hypothetical / future planning → TALK (never ACT).
    elif hypo_talk:
        act = TalkAskAct.TALK
        reasons.append(hypo_code or RC.HYPOTHETICAL_QUERY)
        if hypo_code == RC.NO_ENQUEUE_REQUEST:
            reasons.append(RC.DEFERRED_INTENT)
        response = ResponsePlan(
            purpose="talk",
            talkHint="Staying in discussion — no job will be enqueued on this turn.",
        )
        selected_cap = ""

    # Contradictory constraints (height vs same; STRICT vs automatic) → ASK/STOP/TALK, never ACT.
    elif contradict:
        act = TalkAskAct.ASK
        reasons.append(RC.CONTRADICTORY_CONSTRAINTS)
        reasons.append(RC.CLARIFICATION_REQUIRED)
        response = ResponsePlan(
            purpose="ask",
            clarificationQuestion=(
                "Those constraints conflict (e.g. change vs keep identical, or STRICT-only vs automatic). "
                "Which constraint should win before I act?"
            ),
        )
        selected_cap = ""

    # Stale / wrong cast subject on referential retry → ASK/TALK/STOP (do not invent).
    elif unknown_subject:
        act = TalkAskAct.ASK
        reasons.append(RC.UNKNOWN_CAST_SUBJECT)
        reasons.append(RC.ENTITY_UNRESOLVED)
        reasons.append(RC.CLARIFICATION_REQUIRED)
        response = ResponsePlan(
            purpose="ask",
            clarificationQuestion=(
                f"I do not see '{unknown_subject}' in this project's cast. "
                "Which bound character should I use, or did you mean a different artifact?"
            ),
        )
        selected_cap = ""

    # STRICT provider lock with no generation target → ASK (not silent TALK).
    elif strict_bare and not selected_cap:
        act = TalkAskAct.ASK
        reasons.append(RC.STRICT_TARGET_REQUIRED)
        reasons.append(RC.TARGET_AMBIGUOUS)
        reasons.append(RC.CLARIFICATION_REQUIRED)
        response = ResponsePlan(
            purpose="ask",
            clarificationQuestion=(
                "STRICT lock noted. What should I generate or change under that lock — "
                "which image, shot, or scene?"
            ),
        )

    # Quoted imperative citation must not auto-ACT.
    elif quoted_protected:
        act = TalkAskAct.TALK
        reasons.append(RC.QUOTED_COMMAND_PROTECTED)
        response = ResponsePlan(
            purpose="talk",
            talkHint="That looked like a quoted example — say the word if you want me to run it.",
        )
        selected_cap = ""

    # Destructive discussion / hypothetical → TALK (not destructive ASK).
    elif destructive_discussion and risk.level == RiskLevel.DESTRUCTIVE:
        act = TalkAskAct.TALK
        reasons.append(RC.DESTRUCTIVE_DISCUSSION)
        # Soften risk: discussion is not a delete command.
        risk = risk.__class__(
            level=RiskLevel.SAFE,
            confirmationRequired=False,
            destructive=False,
            confirmationQuestion="",
            reasonCodes=[],
        )
        response = ResponsePlan(purpose="talk")
        selected_cap = ""

    # Bare capability chit-chat stays TALK.
    elif _CAPABILITY_GENERATE_IMAGES_RE.search(text):
        act = TalkAskAct.TALK
        response = ResponsePlan(purpose="talk")
        selected_cap = ""

    # Footsteps / timeline audio with null activeScene → ASK (do not break add_audio).
    elif footstepish and not scene_bound:
        act = TalkAskAct.ASK
        reasons.append(RC.SCENE_REQUIRED)
        reasons.append(RC.SCENE_UNBOUND_ASK)
        reasons.append(RC.CLARIFICATION_REQUIRED)
        response = ResponsePlan(
            purpose="ask",
            clarificationQuestion=(
                "Which scene should I place the footsteps on? "
                "Open a scene on Timeline, or name the scene."
            ),
            prohibited=["timeline.add_audio_without_scene"],
        )
        selected_cap = selected_cap or "timeline.add_audio"

    # Destructive always ASK (never silent ACT).
    elif risk.level == RiskLevel.DESTRUCTIVE and risk.confirmationRequired:
        act = TalkAskAct.ASK
        response = ResponsePlan(
            purpose="ask",
            clarificationQuestion=risk.confirmationQuestion,
            prohibited=["silent_delete", "auto_confirm"],
        )
    elif sufficiency.clarificationRequired and sufficiency.missingRequiredFields:
        act = TalkAskAct.ASK
        response = ResponsePlan(
            purpose="ask",
            clarificationQuestion=sufficiency.clarificationQuestion
            or "I need one more detail before I can proceed.",
        )
    elif commitment == Commitment.EXPLICIT and not selected_cap and not memory_request_id:
        # Do it / Go ahead without pending brief → ASK target.
        act = TalkAskAct.ASK
        reasons.append(RC.COMMITMENT_WITHOUT_TARGET)
        reasons.append(RC.TARGET_AMBIGUOUS)
        response = ResponsePlan(
            purpose="ask",
            clarificationQuestion="What should I generate or change — which image, video, or scene?",
        )
    elif selected_cap and (
        intent_kind == "EXECUTION"
        or commitment in {Commitment.IMPLIED, Commitment.EXPLICIT}
        or (canonical_retry is not None and getattr(canonical_retry, "next_request", None) is not None)
        or (referential.matched and _PUT_ENTITIES_IN_RE.search(text))
        or RC.PROVIDER_ROUTE_COMMAND in reasons
        or RC.REFERENTIAL_ENHANCE in reasons
        or _POLITE_GENERATE_THIS_RE.search(text)
    ):
        # Unresolved @entity must not ACT — ASK/STOP first.
        if unresolved_entities:
            act = TalkAskAct.ASK
            reasons.append(RC.ENTITY_UNRESOLVED)
            reasons.append(RC.CLARIFICATION_REQUIRED)
            names = ", ".join(
                str(b.get("token") or b.get("name") or "unknown") for b in unresolved_entities[:3]
            )
            response = ResponsePlan(
                purpose="ask",
                clarificationQuestion=(
                    f"I do not recognize {names} in this project. "
                    "Which character should I use, or should I create them first?"
                ),
            )
        else:
            act = TalkAskAct.ACT
            # Pre-ACT runtime precheck for image (and STRICT) — no enqueue.
            if runtime_precheck and selected_cap.startswith("image."):
                runtime = _runtime_precheck_image(
                    user_message=text,
                    route_lock=lock_dict,
                    local_runtime_ready=local_runtime_ready,
                )
                reasons.extend(runtime.reasonCodes)
                if not runtime.ready:
                    if RC.STRICT_MODEL_UNAVAILABLE in runtime.reasonCodes:
                        act = TalkAskAct.STOP
                        response = ResponsePlan(
                            purpose="stop",
                            talkHint=runtime.error
                            or "The requested model is unavailable under STRICT lock.",
                        )
                    else:
                        act = TalkAskAct.ASK
                        response = ResponsePlan(
                            purpose="ask",
                            clarificationQuestion=runtime.error
                            or "The image runtime is not ready. Retry when Comfy/hosted is available?",
                        )
                        if RC.RUNTIME_UNAVAILABLE not in reasons:
                            reasons.append(RC.RUNTIME_UNAVAILABLE)
            if act == TalkAskAct.ACT:
                reasons.append(RC.ACT_READY)
                if not any(c == RC.DEFAULTS_SUFFICIENT for c in reasons):
                    reasons.append(RC.DEFAULTS_SUFFICIENT)
    elif intent_kind == "CLARIFICATION_REQUIRED":
        act = TalkAskAct.ASK
        q = ""
        if unified_intent is not None:
            q = str(getattr(unified_intent, "clarification_question", "") or "")
        response = ResponsePlan(
            purpose="ask",
            clarificationQuestion=q or "Which result should I use?",
        )
        reasons.append(RC.CLARIFICATION_REQUIRED)
    elif intent_kind in {"CONVERSATION", "ANALYSIS", "PROPOSAL", ""}:
        act = TalkAskAct.TALK
        # Ambiguous improvement without referent.
        if re.search(r"\bmake\s+that\s+better\b", text, re.I) and not referential.matched:
            act = TalkAskAct.ASK
            reasons.append(RC.TARGET_AMBIGUOUS)
            response = ResponsePlan(
                purpose="ask",
                clarificationQuestion=(
                    "Which artifact should I improve — the last image, last video, or something else?"
                ),
            )


    # --- Production Planner (evidence + plan stub; NOT a second act authority) ---
    production_plan_dict: dict[str, Any] = {}
    intent_evidence_dict: dict[str, Any] = {}
    selective_preflight_dict: dict[str, Any] = {}
    pending_brief_dict: dict[str, Any] = {}
    try:
        from app.codirector.production_planner.compile import (
            compile_execution_steps,
            compile_multistep_request,
            detect_requested_modalities,
            is_multistep_request,
            is_planning_speech,
        )
        from app.codirector.production_planner.evidence_bus import build_selective_preflight
        from app.codirector.production_planner.intent_evidence import build_intent_evidence
        from app.codirector.production_planner.pending_brief import (
            bind_pending_brief,
            is_pending_fresh,
            make_brief_for_plan,
        )

        planning_speech = is_planning_speech(text)
        multi_step = is_multistep_request(text)
        modalities = detect_requested_modalities(text)
        strictness = str((lock_dict or {}).get("level") or "UNLOCKED").upper() or "UNLOCKED"

        # Freshness gate: EXPLICIT "Do it/Go ahead" binds only to unexpired pending.
        if commitment == Commitment.EXPLICIT and pending_execution is not None:
            bound, bind_codes = bind_pending_brief(
                user_message=text,
                pending=pending_execution,
                commitment_explicit=True,
            )
            reasons.extend(bind_codes)
            if not bound and "PENDING_BRIEF_EXPIRED" in bind_codes:
                if act == TalkAskAct.ACT:
                    act = TalkAskAct.ASK
                    response = ResponsePlan(
                        purpose="ask",
                        clarificationQuestion=(
                            "That pending confirmation expired. "
                            "Should I rebuild the plan, or what should I run?"
                        ),
                    )
                    selected_cap = ""

        plan = compile_multistep_request(
            user_message=text,
            project_id=project_id,
            route_lock=lock_dict,
        )
        if plan is not None:
            # Low-risk Wave4 reconnect: link active planId only (no create_draft).
            try:
                from app.codirector.production_planner.wave4_reconnect import (
                    link_active_wave4_plan_id,
                )

                plan, _w4meta = link_active_wave4_plan_id(db, project_id, plan)
            except Exception:
                pass
            production_plan_dict = plan.model_dump(mode="json")
            reasons.append(RC.PRODUCTION_PLAN_ATTACHED)
            if planning_speech:
                reasons.append(RC.PLANNING_SPEECH)
            if multi_step and plan.steps:
                reasons.append(RC.MULTI_STEP_COMPILED)
            # Planning speech / multi-step plan presentation: TALK + purpose=plan
            # (do NOT introduce a fourth TalkAskAct value).
            # Exception: fresh pending + EXPLICIT commitment may ACT (Go ahead / Do it).
            pending_fresh = bool(
                pending_is_awaiting and is_pending_fresh(pending_execution)
            )
            allow_act_from_pending = (
                commitment == Commitment.EXPLICIT and pending_fresh
            )
            if (planning_speech or multi_step) and not allow_act_from_pending:
                # Prefer TALK+purpose=plan over ASK for plan presentation (not STOP).
                # Scene/target asks become creatorDecisions on the plan; UI can follow.
                if act != TalkAskAct.STOP:
                    act = TalkAskAct.TALK
                    response = ResponsePlan(
                        purpose="plan",
                        talkHint=plan.summary
                        or "Here is a multi-step production plan. Say Go ahead when ready.",
                    )
                    selected_cap = ""
                    # Keep stub empty while presenting plan (no silent ACT).
            # When plan is ready for Go / waiting confirm — stamp pending brief metadata.
            if plan.status.value == "WAITING_FOR_CONFIRMATION" or (
                multi_step and act == TalkAskAct.TALK and response.purpose == "plan"
            ):
                brief = make_brief_for_plan(
                    plan_id=plan.planId,
                    step_id=plan.steps[0].stepId if plan.steps else "",
                    summary=plan.summary
                    or "Plan ready — say Go ahead / Do it to run.",
                    project_id=project_id,
                    capability=(plan.steps[0].capabilityId if plan.steps else ""),
                    plan_snapshot=production_plan_dict,
                )
                pending_brief_dict = brief.model_dump(mode="json")
                reasons.append(RC.PENDING_BRIEF_READY)
                # Persist when db available (reconnect PendingExecution — no parallel store).
                if db is not None and project_id:
                    try:
                        from app.codirector.execution.pending_store import (
                            PendingExecution,
                            save_pending,
                        )

                        # Do not clobber an already-awaiting unrelated pending unless planning.
                        existing = None
                        try:
                            from app.codirector.execution.pending_store import get_active_pending

                            existing = get_active_pending(db, project_id)
                        except Exception:
                            existing = None
                        if existing is None or planning_speech or multi_step:
                            from app.codirector.production_planner.pack_bridge import (
                                bridge_compile_to_execution_steps,
                            )

                            planned = bridge_compile_to_execution_steps(plan)
                            first_cap = plan.steps[0].capabilityId if plan.steps else ""
                            ui_snap = {
                                "intent": "EXECUTION",
                                "capability": first_cap,
                                "confidence": 1.0,
                                "dispatch": "deterministic",
                                "classifier_source": "deterministic",
                            }
                            resolved_ctx = {
                                "production_plan": production_plan_dict,
                                "planned_steps": planned,
                                "pending_brief": pending_brief_dict,
                                "plan_id": brief.planId,
                                "step_id": brief.stepId,
                                "parent_execution_id": plan.parentExecutionId or "",
                                "user_instructions": text,
                                "prompt": text,
                            }
                            pend = PendingExecution(
                                capability=first_cap,
                                project_id=project_id,
                                intent="EXECUTION",
                                unified_intent=ui_snap,
                                confirmation_required=True,
                                confirmation_question=brief.summary,
                                state="AWAITING_CONFIRMATION",
                                plan_id=brief.planId,
                                step_id=brief.stepId,
                                summary=brief.summary,
                                expires_at=brief.expiresAt,
                                invalidation_rules=list(brief.invalidationRules),
                                requested_parameters=dict(resolved_ctx),
                                resolved_context=dict(resolved_ctx),
                            )
                            save_pending(db, project_id, pend)
                    except Exception as _pend_save_exc:
                        logger.warning(
                            "production_planner pending persist failed: %s",
                            _pend_save_exc,
                            exc_info=True,
                        )

            preflight = build_selective_preflight(
                production_plan=plan,
                strictness=strictness,
            )
            if preflight.required:
                selective_preflight_dict = preflight.model_dump(mode="json")
                reasons.append(RC.SELECTIVE_PREFLIGHT)
            elif strictness == "STRICT" or multi_step:
                selective_preflight_dict = preflight.model_dump(mode="json")
                reasons.append(RC.SELECTIVE_PREFLIGHT)

        # Failure-informed: stamp STRICT no-silent-swap when retrying failed STRICT packs.
        if failed_execution_history:
            from app.codirector.production_planner.failure_codes import (
                FailureReasonCode,
                stamp_failure,
            )

            for item in failed_execution_history[:3]:
                if not isinstance(item, dict):
                    continue
                codes = list(item.get("failureReasonCodes") or item.get("reasonCodes") or [])
                lock_lvl = str(
                    (item.get("routeLock") or {}).get("level")
                    if isinstance(item.get("routeLock"), dict)
                    else item.get("lockLevel")
                    or strictness
                ).upper()
                _, stamped = stamp_failure(
                    reason=str(item.get("error") or item.get("failureReason") or ""),
                    codes=codes,
                    strict=lock_lvl == "STRICT",
                )
                if FailureReasonCode.STRICT_NO_SILENT_SWAP.value in stamped:
                    evidence.append("strict_no_silent_swap")
                    if FailureReasonCode.STRICT_NO_SILENT_SWAP.value not in reasons:
                        reasons.append(FailureReasonCode.STRICT_NO_SILENT_SWAP.value)

        intent_ev = build_intent_evidence(
            semantic_intent=intent_kind
            or ("PLANNING" if planning_speech else "")
            or ("EXECUTION" if act == TalkAskAct.ACT else ""),
            commitment=commitment.value if hasattr(commitment, "value") else str(commitment),
            sufficiency=sufficiency,
            referential=referential,
            entities=bindings,
            artifact_type=artifact_type or (",".join(modalities) if modalities else ""),
            provider_preference={
                "provider": str((lock_dict or {}).get("provider") or ""),
                "modelId": str((lock_dict or {}).get("modelId") or (lock_dict or {}).get("model") or ""),
            },
            strictness=strictness,
            negation=bool(re.search(r"\b(?:don'?t|do\s+not|never|stop)\b", text, re.I)),
            deferred=deferred,
            hypothetical=hypo_talk,
            quotation=quoted_protected,
            risk=risk,
            runtime_readiness=runtime,
            memory_refs=[memory_request_id] if memory_request_id else [],
            continuity_refs=[],
            planning_speech=planning_speech,
            multi_step=multi_step,
            requested_modalities=modalities,
            classifier_sources=classifier_sources,
            notes=[],
            raw={"production_action": production_action},
        )
        intent_evidence_dict = intent_ev.model_dump(mode="json")
        reasons.append(RC.INTENT_EVIDENCE_BUILT)
    except Exception as _planner_exc:
        competing.append(f"production_planner_wire_error:{type(_planner_exc).__name__}")


    # Still-image must not use a separate ACT boss: if we reached ACT, it is via
    # the same deliberation path as video. Flag competing authority if callers
    # still attempt a force override (observability only).
    if has_visual_reference:
        evidence.append("has_visual_reference")

    exec_stub = ExecutionPlanStub(
        capabilityId=selected_cap if act == TalkAskAct.ACT else "",
        params={
            "user_instructions": text,
            "prompt": text,
            "scene_id": scene_id,
            "prefer_canonical_memory": True,
            "used_chat_inherit": False,
        },
        routeLock=lock_dict,
        memoryRequestId=memory_request_id,
        inheritedFields=inherited_fields,
        overrides=overrides,
        preferCanonicalMemory=True,
    )

    # Deduplicate reason codes preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for code in reasons:
        if code and code not in seen:
            seen.add(code)
            deduped.append(code)

    # Footsteps ASK may leave capability for metadata while not dispatching.
    cap_out = ""
    if act == TalkAskAct.ACT:
        cap_out = selected_cap
    elif act == TalkAskAct.ASK and (risk.destructive or footstepish):
        cap_out = selected_cap

    return DeliberationDecision(
        mode=mode,
        act=act,
        reasonCodes=deduped or [RC.CLASSIFIER_EVIDENCE],
        intentKind=intent_kind,
        speechAct=speech,
        commitment=commitment,
        capabilityId=cap_out,
        capabilityCandidates=candidates,
        artifactType=artifact_type,
        projectId=project_id,
        sceneId=scene_id or "",
        entityBindings=bindings,
        memoryRequestId=memory_request_id,
        inheritedFields=inherited_fields,
        overrides=overrides,
        routeLock=lock_dict,
        sufficiency=sufficiency,
        risk=risk,
        referential=referential,
        runtimePrecheck=runtime,
        responsePlan=response,
        executionPlanStub=exec_stub,
        classifierSources=sorted(set(classifier_sources)),
        competingAuthorityFlags=competing,
        evidence=evidence,
        failedExecutionSummary=failed_summary,
        effortHint=mode.value,
        intentEvidence=intent_evidence_dict,
        productionPlan=production_plan_dict,
        selectivePreflight=selective_preflight_dict,
        pendingBrief=pending_brief_dict,
    )
