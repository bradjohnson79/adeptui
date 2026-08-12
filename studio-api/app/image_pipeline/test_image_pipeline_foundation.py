from __future__ import annotations

from app.image_pipeline.candidates import recommend_candidate
from app.image_pipeline.contracts import (
    EvaluationFinding,
    ImageCandidate,
    ImageCandidateEvaluation,
    ImageCandidateGroup,
    ProductionImageRequest,
)
from app.image_pipeline.creative_direction import build_creative_direction
from app.image_pipeline.orchestrator import prepare_plan
from app.image_pipeline.repair import reject_regression
from app.image_pipeline.router import choose_model_route
from app.image_pipeline.shot_intelligence import interpret_shot
from app.image_pipeline.staging_risk import recommend_staging
from app.image_pipeline import store


def test_shot_intelligence_detects_reveal_and_subject_count() -> None:
    shot = interpret_shot("A wide reveal of three characters entering a haunted warehouse at night.")
    assert shot.shotSize == "wide"
    assert shot.subjectCount == 3
    assert shot.wantsReveal is True
    assert shot.wantsHorror is True


def test_creative_direction_packet_fields_are_filled() -> None:
    shot = interpret_shot("A tense close up of a detective noticing a hidden clue.")
    packet = build_creative_direction("A tense close up of a detective noticing a hidden clue.", shot, "neo-noir")
    assert packet.scenePurposeClass in {"reveal", "suspense"}
    assert packet.lens
    assert packet.lighting
    assert packet.visualLanguageProfileId == "neo-noir"
    assert packet.creatorSummary


def test_staging_risk_triggers_posecraft_for_three_character_complex_shot() -> None:
    shot = interpret_shot("Three characters argue while running down a narrow hallway in a chaotic action scene.")
    packet = build_creative_direction("Three characters argue while running down a narrow hallway in a chaotic action scene.", shot)
    result = recommend_staging(shot, packet, project_policy="Ask")
    assert result["recommendation"] == "poseCraft"
    assert any("Multiple characters" in reason for reason in result["reasons"])


def test_prepare_plan_sets_local_readiness_without_fake_api() -> None:
    plan = prepare_plan(
        ProductionImageRequest(
            projectId="proj-1",
            prompt="A playful medium shot of a kid inventor showing off a homemade robot.",
            purpose="character moment",
            qualityProfile="enhanced",
            deploymentPreference="best-match",
        )
    )
    assert plan.readiness in {"ready", "warning"}
    assert plan.modelRoute.deploymentTarget == "local"
    assert plan.previewSummary


def test_candidate_recommendation_returns_creator_readable_explanation() -> None:
    group = ImageCandidateGroup(projectId="proj-1", planId="plan-1", requestedCount=2)
    group.candidates = [
        ImageCandidate(groupId=group.groupId, projectId="proj-1", planId="plan-1", label="Candidate A", status="draft"),
        ImageCandidate(
            groupId=group.groupId,
            projectId="proj-1",
            planId="plan-1",
            label="Candidate B",
            status="ready",
            evaluation=ImageCandidateEvaluation(candidateId="x", overallStatus="pass", summary="Solid", recommendedNextStep="Use it"),
        ),
    ]
    winner, explanation = recommend_candidate(group)
    assert winner is not None
    assert winner.label == "Candidate B"
    assert "best next pick" in explanation


def test_repair_regression_rejection_detects_new_failures() -> None:
    parent = ImageCandidateEvaluation(
        candidateId="parent",
        overallStatus="warning",
        findings=[EvaluationFinding(code="mood_soft", status="warning", message="Mood needs more contrast.")],
        summary="okay",
    )
    child = ImageCandidateEvaluation(
        candidateId="child",
        overallStatus="fail",
        findings=[EvaluationFinding(code="identity_break", status="fail", message="Character identity drifted.")],
        summary="bad",
    )
    result = reject_regression(parent, child)
    assert result["rejected"] is True
    assert "identity_break" in result["newFailureCodes"]


def test_router_does_not_auto_select_paid_api_without_approval() -> None:
    route = choose_model_route(
        quality_profile="cinematic",
        deployment_preference="api",
        allow_api_deployment=False,
    )
    assert route.requiresApproval is True
    assert route.readiness == "blocked"
    assert route.providerKind == "api"


def test_creative_direction_never_sets_deployment_preference() -> None:
    shot = interpret_shot("An intimate close up of two friends sharing a secret.")
    packet = build_creative_direction("An intimate close up of two friends sharing a secret.", shot)
    assert "deploymentPreference" not in packet.model_dump(mode="json")


def test_codirector_prepare_plan_handler_persists_plan(tmp_path, monkeypatch) -> None:
    from app.codirector.tools.definitions import ToolContext
    from app.codirector.tools.handlers import image_pipeline_tools

    monkeypatch.setattr(store, "_root", lambda: tmp_path)
    ctx = ToolContext(db=None, project_id="proj-handler")
    result = image_pipeline_tools.apply_prepare_plan(
        ctx,
        {
            "prompt": "A playful medium shot of a kid inventor showing off a homemade robot.",
            "purpose": "character moment",
            "qualityProfile": "enhanced",
            "deploymentPreference": "local",
        },
    )

    saved = store.load_plan("proj-handler", result["planId"])
    assert saved is not None
    assert saved.request.prompt.startswith("A playful medium shot")
    assert saved.previewSummary

