"""M2.10 readiness integrity tests (no discovery)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "config/capabilities/adept-ui-v1.0-native.json"
ENV_DOC = ROOT / "docs/codirector/m2.10-native-environment-baseline.md"
CLOSURE = ROOT / "docs/codirector/m2.9-closure-and-m2.10-readiness.md"
CHECKPOINT3 = ROOT / "docs/codirector/m2.10-preflight-checkpoint-3.md"
FLAGS = ROOT / "studio-api/app/feature_flags.py"


@pytest.fixture(scope="module")
def baseline() -> dict:
    assert BASELINE.is_file(), f"missing baseline: {BASELINE}"
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def test_baseline_loads_schema(baseline: dict) -> None:
    assert baseline["baselineId"] == "adept-ui-v1.0-native"
    assert baseline["schemaVersion"] == 1
    assert isinstance(baseline["capabilities"], list)
    assert baseline["counts"]["capabilities"] == len(baseline["capabilities"])


def test_duplicate_capability_ids_rejected(baseline: dict) -> None:
    ids = [c["capabilityId"] for c in baseline["capabilities"]]
    assert len(ids) == len(set(ids))


def test_source_classification_preserved(baseline: dict) -> None:
    for cap in baseline["capabilities"]:
        assert cap["source"] == "native"
        assert cap["status"] in {"accepted", "conditional", "unavailable"}
    assert baseline["providerKinds"].get("addon") == []


def test_mock_only_cannot_be_accepted(baseline: dict) -> None:
    for cap in baseline["capabilities"]:
        blob = " ".join(cap.get("knownLimitations") or []).lower()
        if "mock-only" in blob or "mock only" in blob or "fixture-only" in blob:
            assert cap["status"] != "accepted", cap["capabilityId"]


def test_addon_cannot_silently_override_native(baseline: dict) -> None:
    for cap in baseline["capabilities"]:
        assert cap["source"] != "addon"
    for cap in baseline["capabilities"]:
        if cap["status"] == "accepted":
            assert cap["source"] == "native"


def test_approval_stages_distinct(baseline: dict) -> None:
    by_id = {c["capabilityId"]: c for c in baseline["capabilities"]}
    propose = by_id["codirector.bible.propose"]
    approve = by_id["codirector.bible.approve"]
    validate = by_id["codirector.vision.validate"]
    assert propose["approvalRequired"] is True
    assert approve["approvalRequired"] is True
    assert validate["validationMode"] == "m2.5_owns_lifecycle"
    assert propose["capabilityId"] != validate["capabilityId"]
    assert approve["capabilityId"] != validate["capabilityId"]


def test_env_baseline_excludes_secret_values() -> None:
    text = ENV_DOC.read_text(encoding="utf-8")
    assert "secret" in text.lower()
    assert "names only" in text.lower()
    assert not re.search(
        r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"\s]{8,}",
        text,
    )


def test_feature_flags_gate_exposure_default_off() -> None:
    flags = FLAGS.read_text(encoding="utf-8")
    for name in (
        "image_production_v1",
        "frame_production_v1",
        "video_production_v1",
        "director_timeline_v1",
        "lipsync_production_v1",
        "audio_production_v1",
        "editing_production_v1",
        "render_production_v1",
        "codirector_production_control_v1",
        "model_radar_v1",
        "sandbox_runtime_v1",
        "production_executive_v1",
    ):
        assert f"{name}: bool = False" in flags


def test_milestone_context_honest(baseline: dict) -> None:
    ctx = baseline["milestoneContext"]
    assert "Accepted" in ctx["m271"]
    assert "CONDITIONALLY" in ctx["m28"].upper()
    assert "NOT ACCEPTED" in ctx["m29"].upper()
    assert "not started" in ctx["m210"].lower()
    assert "not started" in ctx["m30"].lower()


def test_section_audit_has_no_false_connected_claims(baseline: dict) -> None:
    sections = baseline["sectionAuditClassification"]
    for name, klass in sections.items():
        assert klass != "CONNECTED", name


def test_closure_and_checkpoint3_exist_and_not_ready() -> None:
    closure = CLOSURE.read_text(encoding="utf-8")
    cp3 = CHECKPOINT3.read_text(encoding="utf-8")
    assert "NOT READY FOR M2.10" in closure
    assert "NOT READY FOR M2.10" in cp3
    assert "does not start m2.10 discovery" in closure.lower()
