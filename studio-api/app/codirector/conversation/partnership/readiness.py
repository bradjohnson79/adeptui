"""Artifact readiness with whyNow and SHOW_PREVIEW default for major artifacts."""

from __future__ import annotations

import re

from .ownership import resolve_ownership
from .schemas import (
    MAJOR_ARTIFACT_TYPES,
    ArtifactReadiness,
    ArtifactReadinessAssessment,
    ArtifactRecommendedAction,
    CollaborationOwnership,
    PartnershipProjectBundle,
)


def _facts_from_message(user_message: str, brief_fields: dict[str, str]) -> list[str]:
    facts: list[str] = []
    text = user_message or ""
    lowered = text.lower()
    if re.search(r"\b(protagonist|hero|main character|biologist|detective|girl|boy|woman|man)\b", lowered):
        facts.append("protagonist")
    if re.search(r"\b(conflict|versus|vs\.?|threat|enemy|disaster|protect)\b", lowered):
        facts.append("central_conflict")
    if re.search(r"\b(audience|viewer|feel|thriller|horror|drama|comedy)\b", lowered):
        facts.append("audience_promise")
    if re.search(r"\b(youtube|festival|pitch|personal|portfolio|proof of concept)\b", lowered):
        facts.append("intended_destination")
    if re.search(r"\b(world|town|city|coast|setting|planet)\b", lowered):
        facts.append("setting")
    if re.search(r"\b(theme|guilt|redemption|identity|love|fear)\b", lowered):
        facts.append("theme")
    for key, val in (brief_fields or {}).items():
        if val and key not in facts:
            facts.append(key)
    # Rich narration length heuristic
    if len(text.split()) >= 45 and "premise" not in facts:
        facts.append("premise_shape")
    return facts


def _hook_preview(user_message: str, facts: list[str]) -> str:
    text = (user_message or "").strip()
    if not text:
        return ""
    # Prefer a concise sentence from the user material
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences:
        if len(s.split()) >= 8:
            return s.strip()[:280]
    return text[:220]


def assess_artifact_readiness(
    bundle: PartnershipProjectBundle,
    *,
    user_message: str,
    brief_fields: dict[str, str] | None = None,
    creative_stage: str = "EMERGENCE",
    user_authorized_draft: bool = False,
) -> list[ArtifactReadinessAssessment]:
    facts = _facts_from_message(user_message, brief_fields or {})
    word_count = len((user_message or "").split())
    assessments: list[ArtifactReadinessAssessment] = []

    # Premature: one undeveloped sentence → WAIT
    if word_count < 12 and len(facts) < 2:
        return [
            ArtifactReadinessAssessment(
                artifact_type="story_template",
                readiness=ArtifactReadiness.NOT_READY,
                why_now="The idea is still arriving—listening and documenting matters more than drafting yet.",
                supporting_facts=facts,
                missing_inputs=["protagonist", "central_conflict", "premise_shape"],
                ownership_mode=resolve_ownership(bundle.collaboration, "story_template"),
                recommended_action=ArtifactRecommendedAction.WAIT,
                confidence=0.2,
            )
        ]

    # Story template
    needed_template = ["protagonist", "central_conflict", "premise_shape", "setting"]
    have_t = [f for f in needed_template if f in facts or f in (brief_fields or {})]
    missing_t = [f for f in needed_template if f not in have_t]
    ownership_t = resolve_ownership(bundle.collaboration, "story_template")
    ready_t = len(have_t) >= 3 and word_count >= 28
    partial_t = len(have_t) >= 2 and word_count >= 22
    hook = _hook_preview(user_message, facts)
    if ready_t or partial_t:
        action = ArtifactRecommendedAction.SHOW_PREVIEW
        if user_authorized_draft and ownership_t != CollaborationOwnership.USER_LEADS:
            action = ArtifactRecommendedAction.CREATE_DRAFT
        assessments.append(
            ArtifactReadinessAssessment(
                artifact_type="story_template",
                readiness=ArtifactReadiness.READY if ready_t else ArtifactReadiness.PARTIAL,
                why_now=(
                    f"You now have {', '.join(have_t[:4]) or 'a clear premise shape'}. "
                    "That is enough for a first-pass story template, even while some fields stay open."
                ),
                supporting_facts=have_t,
                missing_inputs=missing_t,
                ownership_mode=ownership_t,
                recommended_action=action,
                confidence=min(0.95, 0.45 + 0.12 * len(have_t)),
                preview_hook=hook,
            )
        )
    elif creative_stage == "EMERGENCE" and word_count < 25:
        assessments.append(
            ArtifactReadinessAssessment(
                artifact_type="story_template",
                readiness=ArtifactReadiness.NOT_READY,
                why_now="Still early—no artifact pressure while the idea emerges.",
                supporting_facts=facts,
                missing_inputs=missing_t,
                ownership_mode=ownership_t,
                recommended_action=ArtifactRecommendedAction.WAIT,
                confidence=0.3,
            )
        )

    # Pitch readiness
    needed_pitch = ["protagonist", "central_conflict", "audience_promise", "intended_destination", "premise_shape"]
    have_p = [f for f in needed_pitch if f in facts]
    # Also treat destination from vision
    if bundle.vision.primary_destination.value != "UNDECIDED" and "intended_destination" not in have_p:
        have_p.append("intended_destination")
    missing_p = [f for f in needed_pitch if f not in have_p]
    ownership_p = resolve_ownership(bundle.collaboration, "pitch_summary")
    ready_p = (len(have_p) >= 3 and word_count >= 40) or (
        len(have_p) >= 4 and word_count >= 28 and creative_stage in {"FORMATION", "EVALUATION", "PRODUCTION", "EXPLORATION"}
    )
    if ready_p:
        action_p = ArtifactRecommendedAction.SHOW_PREVIEW
        if user_authorized_draft and ownership_p != CollaborationOwnership.USER_LEADS:
            action_p = ArtifactRecommendedAction.CREATE_DRAFT
        assessments.append(
            ArtifactReadinessAssessment(
                artifact_type="pitch_summary",
                readiness=ArtifactReadiness.READY,
                why_now=(
                    f"You now have {', '.join(have_p[:4])}. "
                    "That is enough for a preliminary pitch, even though the ending may remain open."
                ),
                supporting_facts=have_p,
                missing_inputs=missing_p,
                ownership_mode=ownership_p,
                recommended_action=action_p,
                confidence=min(0.92, 0.5 + 0.1 * len(have_p)),
                preview_hook=hook,
            )
        )
    elif "pitch" in (user_message or "").lower() and word_count >= 20:
        assessments.append(
            ArtifactReadinessAssessment(
                artifact_type="pitch_summary",
                readiness=ArtifactReadiness.PARTIAL,
                why_now="You asked about pitching—here is a hook preview while we gather a few more anchors.",
                supporting_facts=have_p,
                missing_inputs=missing_p,
                ownership_mode=ownership_p,
                recommended_action=ArtifactRecommendedAction.SHOW_PREVIEW,
                confidence=0.55,
                preview_hook=hook,
            )
        )

    # Treatment — only when explicitly relevant or formation+
    if "treatment" in (user_message or "").lower() or creative_stage in {"FORMATION", "EVALUATION"}:
        ownership_tr = resolve_ownership(bundle.collaboration, "treatment")
        if len(facts) >= 3 and word_count >= 40:
            assessments.append(
                ArtifactReadinessAssessment(
                    artifact_type="treatment",
                    readiness=ArtifactReadiness.PARTIAL if len(facts) < 5 else ArtifactReadiness.READY,
                    why_now="Story shape is forming—ready to preview a treatment structure without locking it.",
                    supporting_facts=facts[:6],
                    missing_inputs=["act_structure", "ending"] if "ending" not in (user_message or "").lower() else [],
                    ownership_mode=ownership_tr,
                    recommended_action=ArtifactRecommendedAction.SHOW_PREVIEW,
                    confidence=0.6,
                    preview_hook=hook,
                )
            )

    bundle.last_readiness = assessments
    return assessments


def major_offer_requires_preview(assessment: ArtifactReadinessAssessment) -> bool:
    return (
        assessment.artifact_type in MAJOR_ARTIFACT_TYPES
        and assessment.recommended_action
        in {
            ArtifactRecommendedAction.SHOW_PREVIEW,
            ArtifactRecommendedAction.PROPOSE_DRAFT,
            ArtifactRecommendedAction.CREATE_DRAFT,
        }
        and assessment.readiness in {ArtifactReadiness.READY, ArtifactReadiness.PARTIAL}
    )
