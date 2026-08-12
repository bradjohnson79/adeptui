"""M41 Wave 4 — plan dependencies and readiness (M41-CD-63…66)."""

from __future__ import annotations

from app.codirector.plans.dependencies import compute_step_readiness, validate_dependencies
from app.codirector.plans.readiness import annotate_step_availability, build_capability_snapshot
from app.codirector.plans.schemas import ProductionPlanStep


def _step(sid: str, deps: list[str] | None = None, **kwargs) -> ProductionPlanStep:
    return ProductionPlanStep(
        stepId=sid,
        title=sid,
        dependsOn=deps or [],
        state=kwargs.get("state", "pending"),
        proposedToolId=kwargs.get("proposedToolId"),
        requiredCapabilities=kwargs.get("requiredCapabilities") or [],
        category=kwargs.get("category", "system"),
    )


def test_m41_cd_63_dependency_cycles_are_rejected() -> None:
    """M41-CD-63 Dependency cycles are rejected."""
    steps = [_step("a", ["b"]), _step("b", ["a"])]
    result = validate_dependencies(steps)
    assert result.valid is False
    assert result.cycles


def test_m41_cd_64_missing_and_self_dependencies_are_rejected() -> None:
    """M41-CD-64 Missing and self-dependencies are rejected."""
    steps = [_step("a", ["a"]), _step("b", ["missing-x"])]
    result = validate_dependencies(steps)
    assert result.valid is False
    assert result.selfDependencies
    assert result.missingDependencies


def test_m41_cd_65_step_readiness_derives_from_dependencies_and_blockers() -> None:
    """M41-CD-65 Step readiness derives from dependencies and blockers."""
    steps = annotate_step_availability([_step("a", category="research"), _step("b", ["a"], category="research")])
    ready = compute_step_readiness(steps, open_blocker_step_ids=set())
    by_id = {s.stepId: s for s in ready}
    assert by_id["a"].state == "ready"
    assert by_id["b"].state == "pending"
    blocked = compute_step_readiness(steps, open_blocker_step_ids={"a"})
    assert {s.stepId: s.state for s in blocked}["a"] == "blocked"


def test_m41_cd_66_deferred_capabilities_prevent_false_ready_state() -> None:
    """M41-CD-66 Deferred capabilities prevent false ready state."""
    from unittest.mock import MagicMock

    steps = annotate_step_availability(
        [
            _step(
                "v1",
                proposedToolId="propose_video_generate",
                requiredCapabilities=["video.generate"],
                category="video",
            ),
        ]
    )
    assert steps[0].executionAvailability == "deferred"
    snap = build_capability_snapshot(MagicMock(), "proj", steps, open_blocking=0)
    assert snap.readiness in {"deferred", "partially_ready", "unsupported"}
    assert snap.readiness != "ready"
