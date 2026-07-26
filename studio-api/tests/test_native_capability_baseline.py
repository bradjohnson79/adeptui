"""Readiness tests for Adept UI v1.0 native capability baseline (M2.10 preflight)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "config/capabilities/adept-ui-v1.0-native.json"
ENV_DOC = ROOT / "docs/codirector/m2.10-native-environment-baseline.md"


@pytest.fixture(scope="module")
def baseline() -> dict:
    assert BASELINE.is_file(), f"missing baseline: {BASELINE}"
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def test_baseline_loads(baseline: dict) -> None:
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


def test_mock_only_cannot_be_accepted(baseline: dict) -> None:
    for cap in baseline["capabilities"]:
        blob = " ".join(cap.get("knownLimitations") or []).lower()
        if "mock-only" in blob or "mock only" in blob:
            assert cap["status"] != "accepted", cap["capabilityId"]


def test_addon_source_not_present_in_native_baseline(baseline: dict) -> None:
    for cap in baseline["capabilities"]:
        assert cap["source"] != "addon"
    assert baseline["providerKinds"].get("addon") == []


def test_approval_stages_remain_distinct(baseline: dict) -> None:
    by_id = {c["capabilityId"]: c for c in baseline["capabilities"]}
    propose = by_id["codirector.bible.propose"]
    approve = by_id["codirector.bible.approve"]
    validate = by_id["codirector.vision.validate"]
    assert propose["approvalRequired"] is True
    assert approve["approvalRequired"] is True
    assert validate["validationMode"] == "m2.5_owns_lifecycle"
    assert "apply_canon" in propose["jobHandlerIds"]
    assert approve["capabilityId"] != validate["capabilityId"]


def test_environment_baseline_excludes_secret_values() -> None:
    text = ENV_DOC.read_text(encoding="utf-8")
    assert "secret" in text.lower()
    assert not re.search(
        r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}",
        text,
    )


def test_feature_flags_default_documented() -> None:
    flags = (ROOT / "studio-api/app/feature_flags.py").read_text(encoding="utf-8")
    assert "production_executive_v1: bool = False" in flags
    assert "vision_validation_v1: bool = False" in flags
    env = ENV_DOC.read_text(encoding="utf-8")
    assert "default off" in env.lower()


def test_accepted_caps_have_evidence(baseline: dict) -> None:
    for cap in baseline["capabilities"]:
        if cap["status"] == "accepted":
            assert cap["acceptanceEvidence"], cap["capabilityId"]
