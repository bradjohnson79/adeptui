"""M42 Wave 4B — MAGI Editor Foundation tests."""

from __future__ import annotations

from app.magi.readiness import (
    deferred_surfaces,
    korri_policy,
    magi_actions_catalog,
    production_surfaces,
    readiness_payload,
)
from app.magi.production_gate import evaluate_magi_wave4b_gate


def test_production_surfaces_include_shell_and_image_path():
    ids = {s["id"] for s in production_surfaces()}
    assert "magi_shell" in ids
    assert "magi_command" in ids
    assert "certified_image_edit_path" in ids
    assert all(s["status"] == "Certified" for s in production_surfaces())


def test_deferred_surfaces_honest_non_executable():
    deferred = deferred_surfaces()
    assert deferred
    for s in deferred:
        assert s["status"] in {"Draft", "Deferred", "Blocked"}
        assert s.get("executable") is False
    ids = {s["id"] for s in deferred}
    assert "timeline" in ids
    assert "video_inpainting" in ids
    assert "multimodal_recipes" in ids


def test_korri_presentation_only():
    k = korri_policy()
    assert k["role"] == "presentation-only"
    assert k["notCoDirector"] is True
    assert k["notRuntimeAgent"] is True
    assert "QueueWorker" in k["forbidden"]
    assert "UnifiedResolver" in k["forbidden"]
    assert "hero_banner" in k["allowed"]


def test_magi_actions_mix_certified_and_deferred():
    actions = magi_actions_catalog()
    cert = [a for a in actions if a["status"] == "Certified"]
    blockedish = [a for a in actions if a["status"] in {"Draft", "Deferred", "Blocked"}]
    assert cert
    assert blockedish
    assert all(a.get("operation") for a in cert)


def test_readiness_payload_no_fake_execution():
    payload = readiness_payload()
    assert payload["productName"] == "Adept UI MAGI Editor"
    assert payload["noFakeExecution"] is True
    assert payload["korri"]["role"] == "presentation-only"


def test_refuse_deferred_execute_endpoint_logic():
    from app.magi.api import refuse_deferred_execute

    result = refuse_deferred_execute("video_inpainting")
    assert result["executed"] is False
    assert result["ok"] is False
    assert result["status"] == "Blocked"


def test_wave4b_gate_requires_artifacts():
    gate = evaluate_magi_wave4b_gate()
    assert "wave4bGo" in gate
    assert "missingRequirements" in gate
    assert gate.get("productName") == "Adept UI MAGI Editor"
