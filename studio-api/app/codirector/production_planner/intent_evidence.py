"""IntentEvidence — classifier evidence bus packet for deliberation.

Classifiers publish IntentEvidence only. They must never emit final ACT.
DeliberationDecision remains the sole TalkAskAct authority.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

INTENT_EVIDENCE_VERSION: Literal["cd-intent-evidence-v1"] = "cd-intent-evidence-v1"


class IntentEvidence(BaseModel):
    """Semantic evidence packet aggregated before TalkAskAct is decided."""

    schemaVersion: Literal["cd-intent-evidence-v1"] = INTENT_EVIDENCE_VERSION

    # Core semantic / commitment
    semanticIntent: str = ""  # e.g. EXECUTION / CONVERSATION / PLANNING
    commitment: str = "NONE"  # NONE | IMPLIED | EXPLICIT (mirrors deliberation Commitment)
    sufficiency: dict[str, Any] = Field(default_factory=dict)
    referential: dict[str, Any] = Field(default_factory=dict)
    entities: list[dict[str, Any]] = Field(default_factory=list)

    artifactType: str = ""  # image | video | audio | mixed | ""
    providerPreference: dict[str, Any] = Field(default_factory=dict)
    strictness: str = "UNLOCKED"  # UNLOCKED | PREFERRED | STRICT

    negation: bool = False
    deferred: bool = False
    hypothetical: bool = False
    quotation: bool = False

    risk: dict[str, Any] = Field(default_factory=dict)
    runtimeReadiness: dict[str, Any] = Field(default_factory=dict)

    memoryRefs: list[str] = Field(default_factory=list)  # canonical request ids
    continuityRefs: list[str] = Field(default_factory=list)  # packet / timeline refs

    # Multi-step / planning signals (evidence only)
    planningSpeech: bool = False
    multiStep: bool = False
    requestedModalities: list[str] = Field(default_factory=list)

    classifierSources: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


def build_intent_evidence(
    *,
    semantic_intent: str = "",
    commitment: str = "NONE",
    sufficiency: Any = None,
    referential: Any = None,
    entities: Optional[list[dict[str, Any]]] = None,
    artifact_type: str = "",
    provider_preference: Optional[dict[str, Any]] = None,
    strictness: str = "UNLOCKED",
    negation: bool = False,
    deferred: bool = False,
    hypothetical: bool = False,
    quotation: bool = False,
    risk: Any = None,
    runtime_readiness: Any = None,
    memory_refs: Optional[list[str]] = None,
    continuity_refs: Optional[list[str]] = None,
    planning_speech: bool = False,
    multi_step: bool = False,
    requested_modalities: Optional[list[str]] = None,
    classifier_sources: Optional[list[str]] = None,
    notes: Optional[list[str]] = None,
    raw: Optional[dict[str, Any]] = None,
) -> IntentEvidence:
    """Factory: coerce partial classifier outputs into a typed IntentEvidence packet."""

    def _as_dict(obj: Any) -> dict[str, Any]:
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return dict(obj)
        if hasattr(obj, "model_dump"):
            try:
                return dict(obj.model_dump(mode="json"))
            except Exception:
                return dict(obj.model_dump())
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
        return {"value": str(obj)}

    return IntentEvidence(
        semanticIntent=semantic_intent or "",
        commitment=str(commitment or "NONE"),
        sufficiency=_as_dict(sufficiency),
        referential=_as_dict(referential),
        entities=list(entities or []),
        artifactType=artifact_type or "",
        providerPreference=dict(provider_preference or {}),
        strictness=str(strictness or "UNLOCKED"),
        negation=bool(negation),
        deferred=bool(deferred),
        hypothetical=bool(hypothetical),
        quotation=bool(quotation),
        risk=_as_dict(risk),
        runtimeReadiness=_as_dict(runtime_readiness),
        memoryRefs=[str(x) for x in (memory_refs or []) if x],
        continuityRefs=[str(x) for x in (continuity_refs or []) if x],
        planningSpeech=bool(planning_speech),
        multiStep=bool(multi_step),
        requestedModalities=[str(x) for x in (requested_modalities or []) if x],
        classifierSources=list(classifier_sources or []),
        notes=list(notes or []),
        raw=dict(raw or {}),
    )
