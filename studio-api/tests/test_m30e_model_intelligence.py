"""M3.0e Model Intelligence Layer — MI-01..MI-12 and core regressions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from app.codirector.model_intelligence.compiler import compile_intent, normalize_audio_from_text
from app.codirector.model_intelligence.evaluator import evaluate_result
from app.codirector.model_intelligence.loader import PackLoadError, load_pack_dir, validate_all
from app.codirector.model_intelligence.preflight import run_preflight
from app.codirector.model_intelligence.revision import propose_revision
from app.codirector.model_intelligence.schemas import (
    AudioChannelPolicy,
    AudioIntent,
    AudioMode,
    NormalizedGenerationIntent,
    PreflightStatus,
)
from app.codirector.model_intelligence.selector import recommend


PACKS = Path(__file__).resolve().parents[1] / "app" / "codirector" / "model_intelligence" / "packs"


def test_packs_validate():
    result = validate_all()
    assert not result["failed"], result["failed"]
    assert "ltx_2_3" in result["ok"]
    assert "fal_seedance" in result["ok"]
    assert "z_image" in result["ok"]


def test_malformed_pack_fail_closed(tmp_path):
    bad = tmp_path / "bad_model"
    bad.mkdir()
    (bad / "manifest.yaml").write_text("schemaVersion: 1\n", encoding="utf-8")
    with pytest.raises(PackLoadError):
        load_pack_dir(bad)


def test_unsafe_yaml_rejected(tmp_path):
    d = tmp_path / "ltx_2_3"
    d.mkdir()
    for name in (
        "manifest.yaml",
        "capabilities.yaml",
        "parameters.yaml",
        "prompt_rules.yaml",
        "audio_behavior.yaml",
        "limitations.yaml",
        "workarounds.yaml",
        "evaluation_rules.yaml",
        "provenance.yaml",
    ):
        (d / "examples").mkdir(exist_ok=True)
        content = "ok: true\n"
        if name == "manifest.yaml":
            content = (
                "schemaVersion: 1\nmodelId: ltx_2_3\nproviderId: comfy.local\n"
                "engineId: ltx\ndisplayName: X\nmodelVersion: '2.3'\n"
                "knowledgePackVersion: '1.0.0'\nstatus: ACTIVE\n"
                "runtimeStatus: experimental\nmedia: [video]\nmodes: [image_to_video]\n"
            )
        if name == "prompt_rules.yaml":
            content = "positiveAppend: []\nnegativeBase: []\n!!python/object:os.system ['echo hi']\n"
        (d / name).write_text(content, encoding="utf-8")
    with pytest.raises(PackLoadError):
        load_pack_dir(d)


def test_mi01_ltx_no_background_music():
    intent = NormalizedGenerationIntent(
        userPrompt="I2V shot. No background music. No score. Preserve only intended dialogue.",
        mode="image_to_video",
        mediaType="video",
        hasSourceImage=True,
        audioIntent=normalize_audio_from_text(
            "No background music. No score. Preserve only intended dialogue."
        ),
    )
    assert intent.audioIntent.music == AudioChannelPolicy.PROHIBITED
    out = compile_intent(intent, model_id="ltx_2_3")
    assert out.status == "ok"
    assert out.parameters.get("audioStrategy") == "external_audio_pipeline"
    assert any(r.ruleId == "audio.music_prohibited" for r in out.appliedRules)
    assert "BEST_EFFORT" in " ".join(out.limitations) or any(
        "BEST_EFFORT" in w or "external" in w.lower() for w in out.warnings + out.limitations
    )
    assert "background music" in out.negativePrompt.lower()


def test_mi02_ltx_with_intended_music():
    intent = NormalizedGenerationIntent(
        userPrompt="Add a warm background music score under the scene",
        mode="image_to_video",
        hasSourceImage=True,
        audioIntent=AudioIntent(
            audioMode=AudioMode.MUSIC_ONLY,
            music=AudioChannelPolicy.REQUIRED,
        ),
    )
    out = compile_intent(intent, model_id="ltx_2_3")
    assert not any(r.ruleId == "audio.generate_audio_false" for r in out.appliedRules)
    assert any("music" in r.ruleId for r in out.appliedRules)


def test_mi03_silent_cinematic_shot():
    intent = NormalizedGenerationIntent(
        userPrompt="Silent cinematic shot, no generated audio at all",
        mode="image_to_video",
        hasSourceImage=True,
    )
    intent.audioIntent = normalize_audio_from_text(intent.userPrompt)
    out = compile_intent(intent, model_id="fal_seedance")
    assert out.parameters.get("generate_audio") is False
    assert any(r.ruleId == "audio.none" for r in out.appliedRules)


def test_mi04_dialogue_preservation():
    intent = NormalizedGenerationIntent(
        userPrompt="Animate this plate; do not generate new dialogue — we will remux production dialogue",
        mode="image_to_video",
        hasSourceImage=True,
        audioIntent=AudioIntent(
            audioMode=AudioMode.EXTERNAL_AUDIO_PIPELINE,
            music=AudioChannelPolicy.PROHIBITED,
            dialogue=AudioChannelPolicy.PROHIBITED,
        ),
    )
    out = compile_intent(intent, model_id="fal_seedance")
    assert out.parameters.get("generate_audio") is False
    assert "dialogue" in out.negativePrompt.lower()


def test_mi05_unsupported_request_preflight_blocks():
    intent = NormalizedGenerationIntent(
        userPrompt="Generate a still image",
        mode="text_to_image",
        mediaType="image",
        forceModelId="seedream",
    )
    pf = run_preflight(intent, model_id="seedream")
    assert pf.status == PreflightStatus.BLOCKED
    assert pf.errors


def test_mi06_wrong_model_version():
    intent = NormalizedGenerationIntent(
        userPrompt="No music I2V",
        mode="image_to_video",
        hasSourceImage=True,
        audioIntent=AudioIntent(music=AudioChannelPolicy.PROHIBITED),
    )
    out = compile_intent(intent, model_id="ltx_2_3", runtime_model_version="9.9.9")
    assert out.warnings
    assert out.confidence < 0.7
    assert any("does not match" in w.lower() or "mismatch" in w.lower() for w in out.warnings)


def test_mi07_production_bible_conflict():
    intent = NormalizedGenerationIntent(
        userPrompt="Change wardrobe to neon armor",
        mode="image_to_video",
        hasSourceImage=True,
    )
    bible = {"conflicts": ["Wardrobe conflict with approved canon coat"], "styleConstraints": []}
    out = compile_intent(intent, model_id="fal_seedance", bible_package=bible)
    assert any("Bible conflict" in w for w in out.warnings)
    pf = run_preflight(intent, model_id="fal_seedance", bible_package=bible)
    assert pf.status in (PreflightStatus.APPROVAL_REQUIRED, PreflightStatus.READY_WITH_WARNINGS)


def test_mi08_missing_knowledge_pack():
    intent = NormalizedGenerationIntent(userPrompt="hello", mode="image_to_video", hasSourceImage=True)
    out = compile_intent(intent, model_id="totally_unknown_model_xyz")
    assert out.status == "MODEL_KNOWLEDGE_UNAVAILABLE"
    assert out.confidence == 0.0


def test_mi09_example_contamination():
    intent = NormalizedGenerationIntent(
        userPrompt="Rainy street at dusk. EXAMPLE ONLY: laboratory observation room with sample character",
        mode="image_to_video",
        hasSourceImage=True,
        audioIntent=AudioIntent(music=AudioChannelPolicy.PROHIBITED),
    )
    out = compile_intent(intent, model_id="ltx_2_3")
    assert "laboratory observation room" not in out.compiledPrompt.lower()
    assert any(r.ruleId == "safety.no_example_leak" for r in out.appliedRules)


def test_mi10_user_override_force_model():
    intent = NormalizedGenerationIntent(
        userPrompt="No music motion",
        mode="image_to_video",
        hasSourceImage=True,
        forceModelId="wan_2_2",
        audioIntent=AudioIntent(music=AudioChannelPolicy.PROHIBITED),
        userOverrides={"unsupportedFancyControl": True, "seed": 42},
    )
    rec = recommend(intent)
    assert rec.recommendedModel == "wan_2_2"
    out = compile_intent(intent, model_id="wan_2_2")
    assert out.overrideDispositions.get("unsupportedFancyControl").value == "rejected"
    assert out.parameters.get("seed") == 42


def test_mi11_paid_provider_preflight():
    intent = NormalizedGenerationIntent(
        userPrompt="I2V no music",
        mode="image_to_video",
        hasSourceImage=True,
        audioIntent=AudioIntent(music=AudioChannelPolicy.PROHIBITED),
    )
    pf = run_preflight(intent, model_id="fal_seedance", paid_path=True, duplicate_guard_ok=True)
    assert pf.status in (
        PreflightStatus.READY,
        PreflightStatus.READY_WITH_WARNINGS,
        PreflightStatus.APPROVAL_REQUIRED,
    )
    assert pf.compile is not None
    assert pf.compile.parameters.get("generate_audio") is False

    blocked = run_preflight(
        intent,
        model_id="fal_seedance",
        paid_path=True,
        duplicate_guard_ok=False,
    )
    assert blocked.status == PreflightStatus.BLOCKED


def test_mi11_i2v_without_image_blocked():
    intent = NormalizedGenerationIntent(
        userPrompt="I2V",
        mode="image_to_video",
        hasSourceImage=False,
    )
    pf = run_preflight(intent, model_id="fal_seedance")
    assert pf.status == PreflightStatus.BLOCKED


def test_mi12_revision_intelligence():
    intent = NormalizedGenerationIntent(
        userPrompt="no music",
        audioIntent=AudioIntent(music=AudioChannelPolicy.PROHIBITED),
    )
    evaluation = evaluate_result(
        intent=intent,
        model_id="fal_seedance",
        artifact_path=__file__,
        generation_status="done",
        parameters={"generate_audio": True},
        audio_probe={"probableMusic": True, "checked": True},
    )
    assert evaluation.band == "REJECT"
    plan = propose_revision(intent=intent, evaluation=evaluation, attempt=1)
    assert plan.preventPaidLoop is True
    assert any(a.get("action") == "strengthen_music_exclusion" for a in plan.actions)
    stop = propose_revision(intent=intent, evaluation=evaluation, attempt=2)
    assert any(a.get("action") == "stop" for a in stop.actions)


def test_fal_seedance_music_prohibited_sets_generate_audio_false():
    intent = NormalizedGenerationIntent(
        userPrompt="No background music",
        mode="image_to_video",
        hasSourceImage=True,
        audioIntent=AudioIntent(music=AudioChannelPolicy.PROHIBITED),
    )
    out = compile_intent(intent, model_id="fal_seedance")
    assert out.parameters.get("generate_audio") is False


def test_selector_prefers_production_ready_for_video():
    intent = NormalizedGenerationIntent(
        userPrompt="Cinematic I2V no music",
        mode="image_to_video",
        mediaType="video",
        hasSourceImage=True,
        audioIntent=AudioIntent(music=AudioChannelPolicy.PROHIBITED),
    )
    rec = recommend(intent)
    assert rec.recommendedModel
    assert rec.explanation
    assert rec.scores


def test_api_filmmaker_summary(client):
    res = client.get(
        "/api/codirector/model-intelligence/filmmaker-summary",
        params={"userPrompt": "No background music I2V shot", "modelId": "ltx_2_3"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "recommendedModel" in body or body.get("audioPlan")
    assert "advanced" in body
    assert "compiledPrompt" in body["advanced"]
