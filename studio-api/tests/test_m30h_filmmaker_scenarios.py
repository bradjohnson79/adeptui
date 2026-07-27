"""M3.0h filmmaker scenario unit coverage — diversity, freeze, scale, MIL music-off."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from app.codirector.intelligence.specialist_runner import SpecialistRunner
from app.codirector.intelligence.schemas import ContextPackage
from app.codirector.intelligence.specialist_registry import SpecialistRegistry
from app.codirector.model_intelligence.compiler import compile_intent
from app.codirector.model_intelligence.schemas import NormalizedGenerationIntent

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "scripts" / "m30h_filmmaker_scenarios.py"


def _load_harness():
    spec = importlib.util.spec_from_file_location("m30h_filmmaker_scenarios", HARNESS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_heuristic_findings_are_brief_specific():
    runner = SpecialistRunner()
    reg = SpecialistRegistry()
    story = next(s for s in reg.all() if s.id in ("storyteller", "director") or "story" in s.id.lower())
    # pick first available
    definition = reg.all()[0]
    pkg = ContextPackage(
        projectId="m30h-test",
        userMessageDelimited="Create a 30-second commercial introducing a new electric vehicle.",
        facts=[],
        capabilities={},
        activeScope={},
        contextHash="t",
    )
    # Prefer sound-producer / storyteller if present for domain assertions
    definitions = reg.all()
    definition = next(
        (d for d in definitions if d.id in ("sound-producer", "storyteller", "director")),
        definitions[0],
    )
    a = runner._heuristic_finding(
        definition,
        pkg,
        "Create a 30-second commercial introducing a new electric vehicle.",
    )
    b = runner._heuristic_finding(
        definition,
        pkg,
        "Create a suspense sequence with no dialogue. Ambient sound only. No music.",
    )
    assert a.summary != b.summary
    joined_a = (a.summary + a.recommendation + " ".join(a.requirements)).lower()
    joined_b = (b.summary + b.recommendation + " ".join(b.requirements)).lower()
    assert "electric" in joined_a or "commercial" in joined_a
    assert "music" in joined_b or "ambient" in joined_b or "dialogue" in joined_b


def test_harness_diversity_and_freeze():
    h = _load_harness()
    digests = h.specialist_digests("Create a dramatic dialogue scene between two estranged sisters.")
    div = h.assert_diversity(digests, "Create a dramatic dialogue scene between two estranged sisters.")
    assert div["pass"] is True
    shots = h.build_shot_list("dramatic sisters", scene_count=2, shots_per_scene=3)
    review = h.director_review_cycle(shots, "More emotional final shot")
    assert review["approval"]["shotOrderApproved"] is True
    assert review["freeze"]["freezeHash"]
    assert review["freezeIntactAfterEditor"] is True
    assert review["rejectedNotInEditor"] is True


def test_harness_s3_mil_music_off():
    h = _load_harness()
    mil = h.mil_music_off_compile()
    assert mil["pass"] is True
    assert mil["generate_audio"] is False


def test_harness_scale_integrity_bounds():
    h = _load_harness()
    payload = h.run_scale()
    assert payload["status"] == "PASS"
    assert payload["integrity"]["sceneCount"] == 12
    assert 85 <= payload["integrity"]["shotCount"] <= 120
    assert payload["rendering"] is False


def test_compile_intent_seedance_no_music():
    intent = NormalizedGenerationIntent(
        userPrompt="Suspense. No dialogue. No music. Ambient only.",
        mode="text_to_video",
        mediaType="video",
        forceModelId="fal_seedance",
    )
    result = compile_intent(intent, model_id="fal_seedance")
    assert result.parameters.get("generate_audio") is False


def test_run_all_scenarios_offline(tmp_path, monkeypatch):
    h = _load_harness()
    monkeypatch.setattr(h, "OUT", tmp_path)
    codes = []
    for spec in h.SCENARIOS:
        codes.append(h.run_scenario(spec)["status"])
    codes.append(h.run_scale()["status"])
    assert codes.count("PASS") == len(codes)
