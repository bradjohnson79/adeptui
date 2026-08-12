"""Foundation Phase 2 creative specialist tests."""

from __future__ import annotations

from app.codirector.foundation.contracts import Recommendation, SpecialistRequest, SpecialistResult
from app.codirector.foundation.creative.creative_director import review_specialist_bundle
from app.codirector.foundation.creative.routing import select_specialists
from app.codirector.foundation.creative.runners import run_specialist


def test_select_specialists_excludes_creative_director_and_matches_signal_words() -> None:
    selected = select_specialists(
        user_message="Revise the character dialogue and protect continuity with the previous scene.",
        intent="revise_dialogue",
        domain_profile_ids=["animation-series"],
    )
    assert "creative_director" not in selected
    assert "performance_director" in selected
    assert "continuity_supervisor" in selected


def test_run_specialist_preserves_request_knowledge_refs_and_adds_result_shape() -> None:
    request = SpecialistRequest(
        specialistId="continuity_supervisor",
        projectId="proj-creative-1",
        userMessage="Keep the existing costume and framing consistent with the approved version.",
        intent="review_continuity",
        knowledgeRefs=["pack:continuity-basics"],
        domainProfileIds=["series"],
    )

    result = run_specialist(request)

    assert result.specialistId == "continuity_supervisor"
    assert result.status == "validated"
    assert "pack:continuity-basics" in result.knowledgeRefs
    assert result.continuityFlags
    assert any("pack:continuity-basics" in rec.knowledgeRefs for rec in result.recommendations)


def test_run_specialist_consults_shared_knowledge_principles() -> None:
    request = SpecialistRequest(
        specialistId="story_architect",
        projectId="proj-creative-2",
        userMessage="Help me structure Episode 1 with a clear three-act turn for Harbor Signal.",
        intent="develop_concept",
        domainProfileIds=["series"],
    )
    result = run_specialist(request)
    assert result.status == "validated"
    assert result.knowledgeRefs, "expected shared knowledge pack ids"
    assert any("shared creative knowledge" in finding.lower() for finding in result.findings)


def test_review_specialist_bundle_detects_conflicts_and_trims_failed_results() -> None:
    findings = [
        SpecialistResult(
            specialistId="cinematography_director",
            summary="Prefer static wide compositions.",
            recommendation="Use a static wide frame for emotional distance.",
            recommendations=[Recommendation(text="Use a static wide frame.", priority="high")],
            confidence=0.9,
            status="validated",
        ),
        SpecialistResult(
            specialistId="lighting_director",
            summary="Go dark and shadow-heavy.",
            recommendation="Keep the mood dark and severe.",
            recommendations=[Recommendation(text="Keep the mood dark.", priority="medium")],
            confidence=0.75,
            status="validated",
        ),
        SpecialistResult(
            specialistId="editor",
            summary="Push handheld close coverage.",
            recommendation="Cut to handheld close-ups for intensity.",
            recommendations=[Recommendation(text="Use handheld close-ups.", priority="medium")],
            confidence=0.82,
            status="validated",
        ),
        SpecialistResult(
            specialistId="sound_director",
            summary="Incomplete result",
            recommendation="Route elsewhere.",
            confidence=0.0,
            status="failed",
        ),
    ]

    review = review_specialist_bundle(
        project_id="proj-creative-1",
        user_message="Keep this simple and aligned with the eerie vision.",
        findings=findings,
        domain_profile_ids=["horror-short"],
        vision_summary="Eerie, shadow-heavy tension.",
    )

    assert review.alignedWithVision is False
    assert review.contradictions
    assert "sound_director" in review.dropSpecialistIds
    assert "lighting_director" in review.keepSpecialistIds
    assert review.overloadRisk in {"medium", "high"}
    assert review.maxQuestions == 0
