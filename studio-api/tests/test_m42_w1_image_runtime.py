"""M42 Wave 1 — image runtime architecture contract tests."""

from __future__ import annotations

from app.image_runtime.certified_registry import get_workflow, list_workflows, draft_keys
from app.image_runtime.contract import resolve_image_workflow
from app.image_runtime.intent import ImageIntent
from app.image_runtime.output_gate import validate_image_output
from app.image_runtime.production_gate import evaluate_image_gate
from app.image_runtime.provenance import ImageProvenance
from app.image_runtime.reference_assets import REFERENCE_TYPES, ReferenceAsset
from app.image_runtime.identities import identity_registry_snapshot
from app.workflow_runtime import resolve_workflow, list_registry_domains


def test_draft_registry_loads():
    keys = draft_keys()
    assert "zimage.txt2img" in keys
    assert "zimage.ref_edit" in keys
    # Wave 2 may promote required keys to Certified — status must be a known enum value
    assert get_workflow("zimage.txt2img").status in {
        "Draft",
        "Built",
        "SmokeTested",
        "Certified",
    }
    assert all(w.category for w in list_workflows())


def test_resolve_image_txt2img_draft():
    c = resolve_image_workflow("txt2img", engine="zimage", allow_draft=True)
    assert c.workflow_key == "zimage.txt2img"
    assert c.modality == "image"
    assert c.category == "Generation"
    d = c.to_dict()
    assert d["provenancePolicy"]["schema"] == "ImageProvenance"


def test_unified_resolver_image_domain():
    assert "image" in list_registry_domains()
    c = resolve_workflow("txt2img", modality="image", engine="zimage")
    assert c.workflow_key == "zimage.txt2img"


def test_certified_resolve_wave2_allows_certified():
    """Wave 1 rejected Certified-only resolve; Wave 2 allows when live-certified."""
    c = resolve_image_workflow("txt2img", engine="zimage", allow_draft=False)
    assert c.workflow_key == "zimage.txt2img"
    assert c.status == "Certified"


def test_image_intent_runtime_block_has_no_bible():
    intent = ImageIntent(
        projectId="p1",
        operation="image.generate",
        prompt="still",
        creativeContextDigest="abc",
        referenceIds=["ref-1"],
    )
    block = intent.to_image_runtime_block({"workflowKey": "zimage.txt2img", "category": "Generation"})
    assert "bible" not in block
    assert "story" not in block
    assert block["reference_ids"] == ["ref-1"]
    assert block["creative_context_digest"] == "abc"


def test_reference_and_provenance_schemas():
    assert len(REFERENCE_TYPES) == 10
    ref = ReferenceAsset(type="character", projectId="p", sourceImages=["a.png"])
    assert ref.referenceId
    prov = ImageProvenance(workflow="zimage.txt2img", prompt="x", seed=1)
    assert prov.to_dict()["workflow"] == "zimage.txt2img"


def test_identity_registry_draft_not_enforced():
    snap = identity_registry_snapshot()
    assert snap["enforced"] is False
    assert snap["enforcementWave"] == "M42-W5"


def test_output_gate_missing_file():
    result = validate_image_output("/nonexistent/m42-w1-missing.png")
    assert result.ok is False
    assert result.checks["exists"] is False


def test_wave1_gate_shape():
    gate = evaluate_image_gate()
    assert gate["phase"] == "M42-W1"
    assert gate["imageProductionCertified"] is False
    assert "wave1Go" in gate
    # Wave 2 clears wave1ArchitectureOnly on production-gate.json
    assert "wave1ArchitectureOnly" in gate
