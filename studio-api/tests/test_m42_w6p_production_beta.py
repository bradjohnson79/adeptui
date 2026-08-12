"""M42 Wave 6P — Production Beta gate tests."""

from __future__ import annotations

from app.m42_wave6p.production_gate import evaluate_m42_wave6p_gate
from app.scene_references.production_gate import evaluate_m42_w6p_scene_reference_gate


def test_wave6p_requires_scene_reference_addendum():
    scene = evaluate_m42_w6p_scene_reference_gate()
    gate = evaluate_m42_wave6p_gate()
    assert "wave6pGo" in gate
    assert "sceneReferenceAddendumGo" in gate
    assert gate["binaryOnly"] is True
    assert gate["conditionalGoForbidden"] is True
    # wave6pGo cannot be true without scene addendum
    if gate["wave6pGo"]:
        assert gate["sceneReferenceAddendumGo"] is True
        assert scene["sceneReferenceAddendumGo"] is True


def test_wave6p_flag_keys_present():
    gate = evaluate_m42_wave6p_gate()
    required = [
        "allPrerequisiteWavesPassed",
        "allProductsCertified",
        "allRuntimePathsCanonical",
        "manualBetaPassed",
        "sceneReferenceAddendumGo",
        "sceneReferencePaneOperational",
        "textToVideoReferencesOperational",
        "oneFrameReferencesOperational",
        "threeFrameReferencesOperational",
        "timelineReferencesOperational",
        "legacyDirectorLabelsRemoved",
    ]
    for k in required:
        assert k in gate["flags"]
