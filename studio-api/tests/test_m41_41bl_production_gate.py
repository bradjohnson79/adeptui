"""M41 4.1B-L — production gate set inclusion tests."""

from __future__ import annotations

from app.video_runtime.production_gate import (
    enabled_cloud_keys,
    evaluate_gate,
    reload_production_gate,
    required_cloud_keys,
    required_local_keys,
)


def test_required_local_set_is_release_stable():
    reload_production_gate()
    keys = required_local_keys()
    assert "ltx.simple_i2v" in keys
    assert "wan.three_frame" in keys
    assert "director.batch_timeline" in keys
    assert "fal.seedance" not in keys


def test_cloud_required_set_fixed_enabled_empty_by_default():
    reload_production_gate()
    assert "fal.seedance" in required_cloud_keys()
    # Default release: cloud not enabled for production advertise
    assert enabled_cloud_keys() == []


def test_evaluate_gate_exposes_set_fields():
    reload_production_gate()
    g = evaluate_gate()
    assert "requiredLocalProductionWorkflowKeys" in g
    assert "missingRequiredLocalKeys" in g
    assert "localGateSatisfied" in g
    assert "cloudGateSatisfied" in g
    assert "wave6ConsumerContractPassed" in g
    assert g["phase"] == "M41-4.1B-L"
