from __future__ import annotations

import pytest

from app.character_consistency.correction_loop import build_correction_plan
from app.character_consistency.deviation_report import (
    CharacterDeviationFinding,
    build_deviation_report,
)
from app.character_consistency.reference_roles import ReferenceRole
from app.character_consistency.seed_policy import SeedPolicy


def test_deviation_report_uses_honest_comparative_scores():
    report = build_deviation_report(
        project_id="proj-1",
        subject_id="char-1",
        subject_label="Korri",
        candidate_asset_id="asset-1",
        evaluator_key="character-consistency",
        evaluator_version="1.0",
        recipe_id="recipe-1",
        findings=[
            CharacterDeviationFinding(
                dimension=ReferenceRole.FACE,
                status="drift",
                severity="major",
                comparative_score="clear_drift",
                confidence="medium",
                expected_reference_roles=[ReferenceRole.IDENTITY, ReferenceRole.FACE],
                observed_difference="Jawline and eye spacing drifted from the approved portrait anchor.",
                correction_goal="Restore the approved face structure and eye spacing.",
                evidence_summary=["Approved hero portrait vs candidate close-up."],
            ),
            CharacterDeviationFinding(
                dimension=ReferenceRole.LIGHTING,
                status="review",
                severity="minor",
                comparative_score="minor_drift",
                confidence="low",
                expected_reference_roles=[ReferenceRole.LIGHTING],
                observed_difference="Key light direction changed enough to warrant manual review.",
                evidence_summary=["Candidate uses side light instead of the softer front key."],
            ),
        ],
    )

    assert report.overall_status == "drift"
    assert report.overall_comparative_score == "clear_drift"
    assert report.requires_human_review is True
    assert not hasattr(report, "overall_score")


def test_not_assessable_finding_must_use_not_assessable_score():
    with pytest.raises(ValueError):
        CharacterDeviationFinding(
            dimension=ReferenceRole.EARS,
            status="not_assessable",
            severity="informational",
            comparative_score="aligned",
            observed_difference="Ears were hidden behind hair and could not be compared.",
        )


def test_correction_plan_targets_actionable_findings_only():
    report = build_deviation_report(
        project_id="proj-1",
        subject_id="char-1",
        subject_label="Korri",
        candidate_asset_id="asset-2",
        evaluator_key="character-consistency",
        evaluator_version="1.0",
        findings=[
            CharacterDeviationFinding(
                dimension=ReferenceRole.HAIR,
                status="review",
                severity="minor",
                comparative_score="minor_drift",
                confidence="medium",
                expected_reference_roles=[ReferenceRole.HAIR],
                observed_difference="The ponytail silhouette is close but slightly too short.",
                correction_goal="Lengthen the approved ponytail silhouette without changing color.",
            ),
            CharacterDeviationFinding(
                dimension=ReferenceRole.ENVIRONMENT,
                status="not_assessable",
                severity="informational",
                comparative_score="not_assessable",
                observed_difference="The background is intentionally abstracted in this crop.",
            ),
        ],
    )

    plan = build_correction_plan(report)

    assert plan.next_seed_policy == SeedPolicy.REFINE
    assert len(plan.instructions) == 1
    assert plan.instructions[0].dimension == ReferenceRole.HAIR
    assert "reference" in plan.instructions[0].prompt_additions[0].lower()
    assert plan.escalation_notes
