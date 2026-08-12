"""Integration smoke for foundation pipeline (Domain → Knowledge → Specialists → Creative Director)."""

from __future__ import annotations

from app.codirector.foundation.pipeline import (
    merge_findings_for_synthesis,
    resolve_domain_profile_ids,
    run_foundation_creative_pass,
    should_run_foundation_creative,
)


def test_should_run_for_creative_intents():
    assert should_run_foundation_creative("create_character") is True
    assert should_run_foundation_creative("answer_question") is False


def test_run_foundation_creative_pass_includes_director_review():
    findings, review, knowledge_refs = run_foundation_creative_pass(
        project_id="proj-foundation",
        user_message="Help me develop the premise and lead character for Episode 1 of a web series.",
        intent_kind="develop_concept",
        domain_profile_ids=resolve_domain_profile_ids(primary_slug="series", subtype_slug="web_series"),
    )
    assert findings
    assert review is not None
    assert review.maxQuestions <= 1
    assert "creative_director" not in {item.specialistId for item in findings}
    # Knowledge framework consulted when available
    assert isinstance(knowledge_refs, list)


def test_merge_findings_dedupes():
    from app.codirector.foundation.contracts import SpecialistResult

    a = SpecialistResult(specialistId="story_architect", summary="a", recommendation="r1")
    b = SpecialistResult(specialistId="story_architect", summary="b", recommendation="r2")
    c = SpecialistResult(specialistId="character_architect", summary="c", recommendation="r3")
    merged = merge_findings_for_synthesis([a], [b, c])
    assert len(merged) == 2
    assert {item.specialistId for item in merged} == {"story_architect", "character_architect"}
