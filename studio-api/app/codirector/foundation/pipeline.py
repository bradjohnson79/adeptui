"""Primary integration helper: Domain → Knowledge → foundation specialists → Creative Director.

Conversation Core remains the gateway. For creative intents, IntelligenceService uses this
foundation path as the sole specialist stack (legacy M2.4 runner is skipped).
"""

from __future__ import annotations

from typing import Any, Optional

from .contracts import CreativeDirectorReview, SpecialistRequest, SpecialistResult
from .creative import review_specialist_bundle, run_specialist, select_specialists
from .domains.registry import resolve_profiles

try:
    from .knowledge import query_knowledge
except Exception:  # noqa: BLE001
    query_knowledge = None  # type: ignore[assignment]


# CDX-090: foundation specialists are deterministic keyword heuristics. The
# intelligence_progress event emitted while running the foundation pass must
# say so (service layer consumes this label) instead of "Consulting creative
# foundation", so creators are not misled into believing LLM specialist
# analysis occurred. Findings themselves carry source="heuristic" (see
# foundation/creative/runners.py).
FOUNDATION_PROGRESS_LABEL = "Heuristic creative review"


_CREATIVE_INTENTS = frozenset(
    {
        "develop_concept",
        "write_story",
        "revise_story",
        "create_character",
        "revise_character",
        "design_location",
        "plan_scene",
        "write_scene",
        "revise_dialogue",
        "create_shot_list",
        "create_storyboard",
        "review_continuity",
        "assemble_sequence",
        "plan_audio",
        "production_intelligence",
        "unknown",
    }
)


def resolve_domain_profile_ids(
    *,
    primary_slug: str | None,
    subtype_slug: str | None = None,
    traits: Any = None,
) -> list[str]:
    profiles = resolve_profiles(primary_slug or "custom", subtype_slug=subtype_slug, traits=traits)
    return [profile.profileId for profile in profiles]


def should_run_foundation_creative(intent_kind: str | None) -> bool:
    if not intent_kind:
        return False
    return intent_kind in _CREATIVE_INTENTS


def run_foundation_creative_pass(
    *,
    project_id: str,
    user_message: str,
    intent_kind: str | None = None,
    domain_profile_ids: list[str] | None = None,
    creative_stage: str | None = None,
    creative_substate: str | None = None,
    vision_summary: str = "",
) -> tuple[list[SpecialistResult], Optional[CreativeDirectorReview], list[str]]:
    """Select and run foundation specialists, then Creative Director review.

    Returns (findings, review, knowledge_refs).
    """

    domain_ids = list(domain_profile_ids or [])
    knowledge_refs: list[str] = []
    if query_knowledge is not None:
        try:
            hits = query_knowledge(intent=user_message, limit=6)
            for hit in hits:
                pack_id = getattr(hit, "packId", None) or (hit.get("packId") if isinstance(hit, dict) else None)
                if pack_id and pack_id not in knowledge_refs:
                    knowledge_refs.append(str(pack_id))
        except Exception:  # noqa: BLE001
            knowledge_refs = []

    specialist_ids = select_specialists(
        user_message,
        intent=intent_kind,
        domain_profile_ids=domain_ids,
    )
    findings: list[SpecialistResult] = []
    for specialist_id in specialist_ids:
        request = SpecialistRequest(
            specialistId=specialist_id,
            projectId=project_id,
            userMessage=user_message,
            intent=intent_kind,
            knowledgeRefs=list(knowledge_refs),
            domainProfileIds=domain_ids,
            creativeStage=creative_stage,
            creativeSubstate=creative_substate,
        )
        findings.append(run_specialist(request))

    review: CreativeDirectorReview | None = None
    if findings:
        review = review_specialist_bundle(
            project_id,
            user_message,
            findings,
            domain_ids,
            vision_summary=vision_summary,
        )
        if review.dropSpecialistIds:
            drop = set(review.dropSpecialistIds)
            findings = [item for item in findings if item.specialistId not in drop]
        if review.prioritizedRecommendations and findings:
            lead = findings[0]
            lead.recommendation = review.prioritizedRecommendations[0]
            if len(review.prioritizedRecommendations) > 1:
                lead.findings = list(dict.fromkeys([*lead.findings, *review.prioritizedRecommendations[1:3]]))

    return findings, review, knowledge_refs


def merge_findings_for_synthesis(
    existing: list[Any],
    foundation: list[SpecialistResult],
) -> list[Any]:
    """Merge foundation SpecialistResults into the synthesis finding list."""

    merged = list(existing or [])
    seen = {getattr(item, "specialistId", None) for item in merged}
    for finding in foundation:
        if finding.specialistId in seen:
            continue
        merged.append(finding)
        seen.add(finding.specialistId)
    return merged
