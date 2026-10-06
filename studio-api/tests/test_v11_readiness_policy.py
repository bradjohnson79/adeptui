"""v1.1 Production Readiness policy — one authority for Status and Capability Registry."""

from __future__ import annotations

from app.readiness.v11_policy import (
    POLICY_VERSION,
    SCORE_SEMANTICS,
    VIDEOCHAT3_CAPABILITY_ID,
    ReadinessClass,
    V11Requirement,
    classify_capability,
    classify_status_check,
    infer_from_criticality,
    videochat3_v11_decision,
    worst_class,
)
from app.setup.catalog import BY_ID


def test_policy_version_and_score_semantics() -> None:
    assert POLICY_VERSION == "v1.1"
    assert SCORE_SEMANTICS == "Adept Platform Production Readiness"


def test_videochat3_remains_catalog_required_but_continuity_review_only() -> None:
    assert BY_ID["videochat3_4b"].required is True
    decision = videochat3_v11_decision()
    assert decision["capabilityId"] == VIDEOCHAT3_CAPABILITY_ID
    assert decision["role"] == "continuity_review_only"
    assert decision["catalogRequiredRemains"] == "true"
    assignment = classify_capability(VIDEOCHAT3_CAPABILITY_ID)
    assert assignment.readiness_class == ReadinessClass.ADVISORY_REVIEW_DEGRADED
    assert assignment.v11_requirement == V11Requirement.CONTINUITY_REVIEW
    assert "generation still works" in assignment.production_effect.lower()


def test_videochat3_is_not_scored_by_component_name() -> None:
    from app.readiness import v11_policy as policy

    source = policy.__file__
    assert source
    text = open(source, encoding="utf-8").read()
    assert "if capability_id == \"videochat3" not in text
    assert "special-case" in text.lower() or "Do not special-case" in text or "not scoring keys" in text


def test_core_production_capabilities_are_production_critical() -> None:
    assert classify_capability("comfyui.health").readiness_class == ReadinessClass.PRODUCTION_CRITICAL
    assert classify_capability("models.video.ready").readiness_class == ReadinessClass.PRODUCTION_CRITICAL
    assert classify_capability("project.create").readiness_class == ReadinessClass.PRODUCTION_CRITICAL
    assert classify_capability("storage.database").readiness_class == ReadinessClass.PLATFORM_CRITICAL
    assert classify_capability("models.image.krea2.ready").readiness_class == ReadinessClass.OPTIONAL
    assert classify_capability("references.ic_lora.ready").readiness_class == ReadinessClass.OPTIONAL
    assert classify_capability("references.ic_lora.ready").v11_requirement == V11Requirement.OPTIONAL


def test_ic_lora_is_not_a_hard_dependency_of_reference_weighting() -> None:
    from app.capabilities.registry import BY_ID

    weighting = BY_ID["references.weighting"]
    assert "references.ic_lora.ready" not in weighting.dependencies
    assert "references.timeline_bindings" in weighting.dependencies


def test_status_check_policy_covers_creator_paths() -> None:
    for check_id in (
        "create.path",
        "timeline.generator_truth",
        "timeline.context_binding",
        "posecraft.identity_nav",
        "codirector.grounded_routing",
        "runtime.authority",
    ):
        assert classify_status_check(check_id) is not None
    assert classify_status_check("capabilities.registry").readiness_class == ReadinessClass.ADVISORY_REVIEW_DEGRADED


def test_worst_class_and_criticality_fallback() -> None:
    assert worst_class(["optional", "advisory_review_degraded", "production_critical"]) == ReadinessClass.PRODUCTION_CRITICAL
    assert infer_from_criticality("critical") == ReadinessClass.PRODUCTION_CRITICAL
    assert infer_from_criticality("high") == ReadinessClass.WORKFLOW_DEGRADED
