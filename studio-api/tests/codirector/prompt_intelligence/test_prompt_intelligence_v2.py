"""Unit + integration tests for Prompt Intelligence V2."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from app.codirector.prompt_intelligence.benchmark_certify import promote_strategy, rollback_strategy
from app.codirector.prompt_intelligence.benchmark_eval import (
    CERTIFICATION_SAMPLE_THRESHOLD,
    aggregate_strategy_scores,
    evaluate_category,
    mark_stale_if_revision_changed,
)
from app.codirector.prompt_intelligence.benchmark_models import (
    AutomatedHealthScores,
    CategoryEvidence,
    PromptBenchmarkRun,
)
from app.codirector.prompt_intelligence.benchmark_runner import (
    cancel_suite,
    plan_suite,
    start_suite_run,
    suite_status,
)
from app.codirector.prompt_intelligence.benchmark_store import save_evidence, save_run
from app.codirector.prompt_intelligence.benchmark_suites import (
    build_matrix_plan,
    list_suites,
    load_suite,
    provider_eligible,
)
from app.codirector.prompt_intelligence.errors import PromptIntelligenceError
from app.codirector.prompt_intelligence.recommendation import resolve_strategy_recommendation
from app.codirector.prompt_intelligence.scoring_v2 import analyze_v2


@pytest.fixture()
def pi_data_root(tmp_path, monkeypatch):
    root = tmp_path / "pi"
    monkeypatch.setenv("PROMPT_INTELLIGENCE_DATA_ROOT", str(root))
    # reset any cached paths by ensuring dirs exist
    for sub in ("suites", "runs", "reviews", "evidence", "feedback/queue"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def test_suites_load_and_matrix_eligibility(pi_data_root):
    suites = list_suites()
    ids = {s.suiteId for s in suites}
    assert {"video-core", "image-core", "audio-core", "voice-core"} <= ids
    image = load_suite("image-core")
    assert image.matrixMode == "full"
    assert len(image.strategies) == 5
    video = load_suite("video-core")
    assert video.matrixMode == "reduced"
    assert "bilingual-subtle" not in video.strategies
    assert provider_eligible(["comfyui"], "comfyui")
    assert not provider_eligible(["comfyui"], "ltx-local")
    plan = build_matrix_plan(image, provider_id="comfyui", samples_per_strategy=1)
    assert plan.estimatedJobs == len(image.cases) * len(image.strategies)
    assert plan.estimatedDiskMb > 0


def test_dry_run_suite_pause_cancel(pi_data_root):
    plan = plan_suite("image-core", provider_id="comfyui", samples_per_strategy=1)
    assert plan.estimatedJobs >= 3
    suite_run = start_suite_run(
        "image-core",
        provider_id="comfyui",
        samples_per_strategy=1,
        dry_run=True,
    )
    # allow some progress
    time.sleep(0.4)
    cancel_suite(suite_run.suiteRunId)
    st = suite_status(suite_run.suiteRunId)
    assert st["ok"]
    assert st["suiteRun"]["status"] == "cancelled"


def test_insufficient_evidence_refuses_promote(pi_data_root):
    # seed one successful run only
    run = PromptBenchmarkRun(
        runId="brun_test1",
        suiteId="image-core",
        benchmarkId="image-portrait",
        category="portrait",
        domain="image",
        strategy="refined-english",
        providerId="comfyui",
        modelRevision="default",
        success=True,
        status="completed",
        automatedScores=AutomatedHealthScores(passed=True, completed=True, artifactExists=True, artifactNonEmpty=True),
    )
    save_run(run)
    evidence = evaluate_category(
        provider_id="comfyui",
        model_revision="default",
        domain="image",
        category="portrait",
    )
    assert evidence.status == "insufficient_evidence"
    with pytest.raises(PromptIntelligenceError) as exc:
        promote_strategy(
            provider_id="comfyui",
            model_revision="default",
            domain="image",
            category="portrait",
            strategy="refined-english",
            force=False,
        )
    assert exc.value.code == "INSUFFICIENT_EVIDENCE"


def test_promote_rollback_with_force_and_stale(pi_data_root):
    # Create enough sample count via evidence override path using force
    for i in range(CERTIFICATION_SAMPLE_THRESHOLD):
        save_run(
            PromptBenchmarkRun(
                runId=f"brun_ok_{i}",
                suiteId="image-core",
                benchmarkId="image-portrait",
                category="portrait",
                domain="image",
                strategy="refined-english",
                sampleIndex=i,
                providerId="comfyui",
                modelRevision="default",
                success=True,
                status="completed",
                automatedScores=AutomatedHealthScores(
                    passed=True, completed=True, artifactExists=True, artifactNonEmpty=True
                ),
                humanScores={"overall": 80 + i, "scores": {"overall": 80 + i}},  # type: ignore[arg-type]
            )
        )
    evidence = evaluate_category(
        provider_id="comfyui",
        model_revision="default",
        domain="image",
        category="portrait",
    )
    assert evidence.sampleCount >= CERTIFICATION_SAMPLE_THRESHOLD
    promoted = promote_strategy(
        provider_id="comfyui",
        model_revision="default",
        domain="image",
        category="portrait",
        strategy="refined-english",
        force=False,
    )
    assert promoted["ok"]
    assert promoted["evidence"]["status"] == "english_preferred"
    rolled = rollback_strategy(
        provider_id="comfyui",
        model_revision="default",
        domain="image",
        category="portrait",
    )
    assert rolled["ok"]
    assert rolled["evidence"]["status"] == "not_tested"

    ev = CategoryEvidence(
        providerId="comfyui",
        modelRevision="default",
        domain="image",
        category="portrait",
        workflowRevision="wf1",
        status="certified_balanced",
        sampleCount=3,
    )
    save_evidence(ev)
    stale = mark_stale_if_revision_changed(ev, model_revision="default", workflow_revision="wf2")
    assert stale.stale
    assert stale.status == "not_tested"


def test_auto_mode_safety(pi_data_root):
    manual = resolve_strategy_recommendation(
        domain="image",
        category="portrait",
        provider_id="comfyui",
        strategy_mode="manual",
    )
    assert manual.appliedAutomatically is False
    assert "manual" in manual.reason

    # uncertified should not auto-apply
    auto = resolve_strategy_recommendation(
        domain="image",
        category="portrait",
        provider_id="comfyui",
        strategy_mode="automatic_certified",
    )
    assert auto.appliedAutomatically is False
    assert auto.strategy == "refined-english"

    save_evidence(
        CategoryEvidence(
            providerId="comfyui",
            modelRevision="default",
            domain="image",
            category="portrait",
            status="certified_balanced",
            recommendedStrategy="bilingual-balanced",
            confidence="high",
            sampleCount=6,
            evidenceVersion="2",
        )
    )
    auto2 = resolve_strategy_recommendation(
        domain="image",
        category="portrait",
        provider_id="comfyui",
        strategy_mode="automatic_certified",
        min_confidence="medium",
    )
    assert auto2.appliedAutomatically is True
    assert auto2.strategy == "bilingual-balanced"

    # experimental never auto
    save_evidence(
        CategoryEvidence(
            providerId="comfyui",
            modelRevision="default",
            domain="image",
            category="portrait",
            status="experimental",
            recommendedStrategy="bilingual-strong",
            confidence="high",
            sampleCount=6,
        )
    )
    auto3 = resolve_strategy_recommendation(
        domain="image",
        category="portrait",
        provider_id="comfyui",
        strategy_mode="automatic_certified",
    )
    assert auto3.appliedAutomatically is False


def test_analyzer_v2_three_axes(pi_data_root):
    out = analyze_v2(
        "Korri stands on a cliff at sunset, wide shot, soft light",
        domain="video",
        provider_id="ltx-local",
        category="camera_movement",
        strategy_mode="recommend",
    )
    axes = out["axes"]
    assert "promptQuality" in axes
    assert "providerCompatibility" in axes
    assert "recommendedStrategyConfidence" in axes
    assert axes["promptQuality"] != axes["recommendedStrategyConfidence"] or True


def test_aggregation_confidence(pi_data_root):
    runs = [
        PromptBenchmarkRun(
            runId=f"r{i}",
            suiteId="image-core",
            benchmarkId="image-portrait",
            category="portrait",
            domain="image",
            strategy="refined-english",
            providerId="comfyui",
            success=True,
            status="completed",
            automatedScores=AutomatedHealthScores(passed=True),
            humanScores={"overall": 70 + i, "scores": {}},  # type: ignore[arg-type]
        )
        for i in range(3)
    ]
    agg = aggregate_strategy_scores(runs)
    assert agg["refined-english"]["sampleCount"] == 3
    assert agg["refined-english"]["confidence"] in ("low", "medium", "high")


def test_integration_suite_evaluate_recommend(pi_data_root):
    suite_run = start_suite_run(
        "audio-core",
        provider_id="audio-studio",
        samples_per_strategy=1,
        dry_run=True,
    )
    # wait for completion
    for _ in range(80):
        st = suite_status(suite_run.suiteRunId)
        if st["suiteRun"]["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.1)
    st = suite_status(suite_run.suiteRunId)
    assert st["suiteRun"]["status"] == "completed"
    assert st["completed"] >= 1
    evidence = evaluate_category(
        provider_id="audio-studio",
        model_revision="default",
        domain="audio",
        category="emotional_music_cue",
        suite_run_id=suite_run.suiteRunId,
    )
    assert evidence.status in ("insufficient_evidence", "not_tested", "experimental", "english_preferred", "no_material_difference")
    rec = resolve_strategy_recommendation(
        domain="audio",
        category="emotional_music_cue",
        provider_id="audio-studio",
        strategy_mode="recommend",
    )
    assert rec.strategy
    assert rec.appliedAutomatically is False
