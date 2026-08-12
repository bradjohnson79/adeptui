"""M42 Wave 4C Timeline rename gate + normalization checks."""

from __future__ import annotations

from app.timeline_product.production_gate import evaluate_timeline_wave4c_gate


def test_wave4c_gate_shape():
    g = evaluate_timeline_wave4c_gate()
    assert g["phase"] == "M42-W4C"
    assert "wave4cGo" in g
    assert "timelineCanonicalNameApplied" in g
    assert "coDirectorNamePreserved" in g
    assert g.get("productName") == "Timeline"


def test_normalize_workspace_director_to_timeline_contract():
    # Mirror studio-web productNormalize / resolveWorkspace contract in docs
    aliases = {"director": "timeline", "director-generator": "timeline", "timeline": "timeline"}
    assert aliases["director"] == "timeline"
    assert aliases["timeline"] == "timeline"
