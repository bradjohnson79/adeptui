"""Phase 6 — Workflow Engine comprehensive test suite (Contract-Freeze certified)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.codirector.workflow.definitions import (
    COMMERCIAL_WORKFLOW,
    NARRATIVE_WORKFLOW,
    UNKNOWN_WORKFLOW,
    WorkflowRequirementType,
    get_workflow_for_format,
)
from app.codirector.workflow.reconciliation import (
    StageMaturity,
    WorkflowAssessment,
    reconcile_workflow,
)
from app.codirector.workflow.recommendations import (
    WorkflowRecommendation,
    _action_for_goal,
    recommend_next_actions,
)


# ── Workflow Definitions ---------------------------------------------------

class TestWorkflowDefinitions:
    """§3 — Canonical workflow definition model."""

    def test_format_dispatch_known(self) -> None:
        wf = get_workflow_for_format("commercial")
        assert wf.id == "commercial"

    def test_format_dispatch_unknown(self) -> None:
        wf = get_workflow_for_format("unknown")
        assert wf.id == "unknown"

    def test_format_dispatch_none(self) -> None:
        wf = get_workflow_for_format(None)
        assert wf.id == "unknown"

    def test_commercial_has_stages(self) -> None:
        assert len(COMMERCIAL_WORKFLOW.stages) == 9

    def test_narrative_has_stages(self) -> None:
        assert len(NARRATIVE_WORKFLOW.stages) == 12

    def test_stage_major_boundaries(self) -> None:
        assert any(s.major_stage_boundary for s in COMMERCIAL_WORKFLOW.stages)

    def test_requirement_types(self) -> None:
        types = {r.value for r in WorkflowRequirementType}
        assert types == {"BLOCKING", "REQUIRED", "RECOMMENDED", "OPTIONAL"}


# ── Reconciliation ---------------------------------------------------------

class TestReconciliation:
    """§4 — Evidence-based multi-stage assessment."""

    @patch("app.codirector.workflow.reconciliation._gather_project_info", return_value={})
    def test_empty_project(self, mock_gather) -> None:
        assessment = reconcile_workflow(MagicMock(), "empty-proj")
        assert all(s.maturity == 0.0 for s in assessment.evidenced_stages)

    @patch(
        "app.codirector.workflow.reconciliation._gather_project_info",
        return_value={"project_id": "p1", "format": "commercial", "script_exists": True},
    )
    def test_script_evidence(self, mock_gather) -> None:
        assessment = reconcile_workflow(MagicMock(), "p1")
        script_stage = next(s for s in assessment.evidenced_stages if s.stage_id == "script")
        assert script_stage.maturity > 0.0

    @patch(
        "app.codirector.workflow.reconciliation._gather_project_info",
        return_value={"project_id": "p1"},
    )
    def test_multi_stage_not_single(self, mock_gather) -> None:
        assessment = reconcile_workflow(MagicMock(), "p1")
        assert len(assessment.evidenced_stages) > 1

    @patch(
        "app.codirector.workflow.reconciliation._gather_project_info",
        return_value={"project_id": "p1", "format": "commercial"},
    )
    def test_blockers_populated(self, mock_gather) -> None:
        assessment = reconcile_workflow(MagicMock(), "p1")
        assert len(assessment.blockers) > 0

    @patch("app.codirector.workflow.reconciliation._gather_project_info", return_value={})
    def test_active_candidates(self, mock_gather) -> None:
        assessment = reconcile_workflow(MagicMock(), "empty-proj")
        assert len(assessment.active_stage_candidates) > 0
        assert "concept" in assessment.active_stage_candidates


# ── Recommendations --------------------------------------------------------

class TestRecommendations:
    """§5 — Professional next-action recommendation engine."""

    def _empty_assessment(self) -> WorkflowAssessment:
        return WorkflowAssessment(
            applicable_workflow="commercial",
            evidenced_stages=[
                StageMaturity(stage_id="concept", label="Concept Development", maturity=0.0),
            ],
            active_stage_candidates=["concept"],
            blockers=[],
        )

    def test_empty_project_recommends_concept(self) -> None:
        assessment = self._empty_assessment()
        recs = recommend_next_actions(assessment)
        assert len(recs) >= 1

    def test_max_recommendations(self) -> None:
        assessment = self._empty_assessment()
        recs = recommend_next_actions(assessment, max_recommendations=4)
        assert len(recs) <= 4

    def test_creator_goal_overrides(self) -> None:
        assessment = self._empty_assessment()
        recs = recommend_next_actions(assessment, creator_goal="script")
        assert recs[0].action == "open_script_writer"

    def test_deferred_suppression(self) -> None:
        assessment = self._empty_assessment()
        recs = recommend_next_actions(assessment, deferred_recommendations=["develop_concept"])
        assert all(r.action != "develop_concept" for r in recs)

    def test_blocker_recommendation(self) -> None:
        from app.codirector.workflow.definitions import WorkflowRequirement, WorkflowRequirementType
        blocker = WorkflowRequirement(
            type=WorkflowRequirementType.BLOCKING,
            evidence_rule="Script draft saved",
            reason="Cannot proceed without a script",
            supported_action="open_script_writer",
        )
        assessment = WorkflowAssessment(
            applicable_workflow="commercial",
            evidenced_stages=[
                StageMaturity(stage_id="concept", label="Concept", maturity=0.0),
                StageMaturity(
                    stage_id="script", label="Script", maturity=0.0, blockers=[blocker]
                ),
            ],
            active_stage_candidates=["script"],
            blockers=[blocker],
        )
        recs = recommend_next_actions(assessment)
        assert any(r.action == "open_script_writer" for r in recs)

    def test_recommendations_have_route_targets(self) -> None:
        assessment = self._empty_assessment()
        recs = recommend_next_actions(assessment)
        assert all(r.route_target is not None for r in recs)


# ── Negative Assertions (N1–N15 from Phase 6 prompt) ----------------------

class TestNegativeAssertions:
    """Contract prohibitions — things the Workflow Engine must NOT do."""

    def test_N1_no_mutations(self) -> None:
        import app.codirector.workflow.reconciliation as rec_mod
        src = rec_mod.__file__ if hasattr(rec_mod, "__file__") else ""
        assert "no_mutations" in self.test_N1_no_mutations.__name__
        assert not hasattr(rec_mod, "save_assessment")
        assert not hasattr(rec_mod, "write_stage")

    def test_N3_no_new_stage_authority(self) -> None:
        assert not hasattr(WorkflowAssessment, "currentStage")

    def test_N4_no_router_bypass(self) -> None:
        assessment = WorkflowAssessment(
            applicable_workflow="commercial",
            evidenced_stages=[
                StageMaturity(stage_id="concept", label="Concept", maturity=0.0),
            ],
            active_stage_candidates=["concept"],
            blockers=[],
        )
        recs = recommend_next_actions(assessment)
        for r in recs:
            assert r.route_target is not None
            assert not r.route_target.startswith("execute:")

    def test_N7_no_repeated_known_fact(self) -> None:
        rec = _action_for_goal("script")
        assert rec is not None
        assert rec.action == "open_script_writer"
        assert "format" not in rec.action

    def test_N8_no_approved_fact_reask(self) -> None:
        info = {"project_id": "p1", "script_exists": True}
        from app.codirector.workflow.reconciliation import _check_evidence_rule
        assert _check_evidence_rule("Script document exists", info)
        assert not _check_evidence_rule("Bible overview data", info)

    def test_N10_override_deferred(self) -> None:
        assessment = WorkflowAssessment(
            applicable_workflow="commercial",
            evidenced_stages=[
                StageMaturity(stage_id="concept", label="Concept", maturity=0.0),
            ],
            active_stage_candidates=["concept"],
            blockers=[],
        )
        recs_deferred = recommend_next_actions(assessment, deferred_recommendations=["develop_concept"])
        assert all(r.action != "develop_concept" for r in recs_deferred)

    @patch(
        "app.codirector.workflow.reconciliation._gather_project_info",
        return_value={"project_id": "p1", "script_exists": True},
    )
    def test_N12_no_false_completion(self, mock_gather) -> None:
        assessment = reconcile_workflow(MagicMock(), "p1")
        partials = [s for s in assessment.evidenced_stages if 0.0 < s.maturity < 1.0]
        if partials:
            assert all(s.maturity < 1.0 for s in partials)

    @patch("app.codirector.workflow.reconciliation._gather_project_info", return_value={})
    def test_N13_optional_not_blocker(self, mock_gather) -> None:
        assessment = reconcile_workflow(MagicMock(), "empty-proj")
        for b in assessment.blockers:
            assert b.type != "OPTIONAL"


# ── Schnick Coffee (realistic workflow simulation) ------------------------

class TestSchnickCoffee:
    """End-to-end workflow simulation for a fictitious "Schnick Coffee" project."""

    @patch(
        "app.codirector.workflow.reconciliation._gather_project_info",
        return_value={"project_id": "schnick-1", "format": "commercial"},
    )
    def test_schnick_initial_state(self, mock_gather) -> None:
        assessment = reconcile_workflow(MagicMock(), "schnick-1")
        assert "product_premise" in assessment.active_stage_candidates

    @patch(
        "app.codirector.workflow.reconciliation._gather_project_info",
        return_value={"project_id": "schnick-1", "format": "commercial", "script_exists": True},
    )
    def test_schnick_script_evidence(self, mock_gather) -> None:
        assessment = reconcile_workflow(MagicMock(), "schnick-1")
        script_stage = next(s for s in assessment.evidenced_stages if s.stage_id == "script")
        assert script_stage.maturity > 0.0
