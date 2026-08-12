"""Foundation Phase 3 production helper tests."""

from __future__ import annotations

from app.codirector.foundation.production.estimates import estimate_plan_effort
from app.codirector.foundation.production.planner import build_ordered_roadmap_titles, build_production_roadmap
from app.codirector.foundation.production.readiness import annotate_step_readiness, evaluate_step_readiness


def test_build_production_roadmap_orders_titles_and_surfaces_missing_dependencies() -> None:
    steps = [
        {"stepId": "render", "title": "Render Sequence", "dependsOn": ["edit"], "category": "video", "order": 3},
        {"stepId": "edit", "title": "Edit Sequence", "dependsOn": ["boards"], "category": "editor", "order": 2},
        {"stepId": "boards", "title": "Approve Boards", "dependsOn": [], "category": "scene", "order": 1},
        {"stepId": "audio", "title": "Mix Audio", "dependsOn": ["missing-step"], "category": "audio", "order": 4},
    ]

    roadmap = build_production_roadmap({"planId": "plan-1", "steps": steps, "scriptReady": True}, None)

    assert roadmap["orderedTitles"][:3] == ["Approve Boards", "Edit Sequence", "Render Sequence"]
    assert any(blocker["stepId"] == "audio" for blocker in roadmap["blockers"])


def test_build_ordered_roadmap_titles_accepts_explicit_steps_argument() -> None:
    titles = build_ordered_roadmap_titles(
        steps=[
            {"stepId": "a", "title": "A", "dependsOn": []},
            {"stepId": "b", "title": "B", "dependsOn": ["a"]},
        ]
    )
    assert titles == ["A", "B"]


def test_evaluate_step_readiness_refuses_ready_when_dependencies_incomplete() -> None:
    steps = [
        {"stepId": "prep", "title": "Prep", "state": "pending"},
        {"stepId": "shoot", "title": "Shoot", "state": "ready", "dependsOn": ["prep"]},
    ]

    readiness = evaluate_step_readiness(steps[1], steps)

    assert readiness["ready"] is False
    assert readiness["state"] == "pending"
    assert readiness["dependsOnIncomplete"] == ["prep"]


def test_annotate_step_readiness_marks_ready_only_after_dependencies_complete() -> None:
    annotated = annotate_step_readiness(
        [
            {"stepId": "prep", "title": "Prep", "state": "completed"},
            {"stepId": "shoot", "title": "Shoot", "state": "pending", "dependsOn": ["prep"]},
        ]
    )

    by_id = {item["stepId"]: item for item in annotated}
    assert by_id["prep"]["state"] == "completed"
    assert by_id["shoot"]["state"] == "ready"
    assert by_id["shoot"]["ready"] is True


def test_estimate_plan_effort_returns_rough_counts() -> None:
    estimate = estimate_plan_effort(
        project_snapshot={"shots": 5, "assets": 4},
        steps=[
            {"stepId": "img", "title": "Generate Keyframes", "category": "image"},
            {"stepId": "edit", "title": "Review Sequence", "category": "review"},
        ],
    )

    assert estimate["estimateType"] == "rough_non_guarantee"
    assert estimate["shots"] == 5
    assert estimate["assets"] == 4
    assert estimate["batches"] >= 1
    assert estimate["reviewStages"] >= 1
