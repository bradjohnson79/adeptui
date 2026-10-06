"""ORDER 14 — sound_prompt_compiler tests (door/soft/footsteps + intent contract v1.2)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.audio_studio.sound_prompt_compiler import (  # noqa: E402
    OWNER_REFINE_OPS,
    _footstep_count,
    compile_from_intent,
    compile_sound_prompt,
    mutate_sfx_intent,
)


def test_heavy_steel_bold_vs_soft_wooden_discrimination():
    bold = compile_sound_prompt(
        "Heavy steel door slam, close.",
        duration_seconds=2.5,
        intensity="bold",
    )
    soft = compile_sound_prompt(
        "Soft wooden door close.",
        duration_seconds=2.5,
        intensity="soft",
    )
    bp = bold.compiled_prompt.lower()
    sp = soft.compiled_prompt.lower()

    assert bold.physicalEvent == "door_slam"
    assert soft.physicalEvent == "door_slam"
    assert bold.intensity_key in ("bold", "huge")
    assert soft.intensity_key in ("soft", "subtle")

    # Bold steel language
    assert "steel" in bp or "metallic" in bp or "metal" in bp
    assert "latch" in bp
    assert "after" in bp  # latch AFTER mass impact
    assert "knock" in bp  # negatives / anti-knock phrase
    assert "whoosh" in ",".join(bold.negatives).lower() or "whoosh" in bp

    # Soft wooden ≠ slam/crash/metal boom
    assert "wood" in sp
    assert "soft" in sp or "gentle" in sp or "settle" in sp
    assert "not a slam" in sp or "slam" in ",".join(soft.negatives).lower()
    assert "crash" not in sp.split("avoid:")[0] or "not a crash" in sp
    # bodies must diverge
    assert bp != sp
    assert "thick steel" in bp or "heavy steel" in bp or "metallic boom" in bp or "mass impact" in bp
    assert "settle" in sp or "hinge" in sp or "gentle latch" in sp


def test_door_slam_negatives_expanded():
    r = compile_sound_prompt("Heavy steel door slam, close.", intensity="bold")
    neg = {n.lower() for n in r.negatives}
    for must in ("knock", "knuckle", "whoosh", "plastic click", "footsteps", "wind"):
        assert any(must in n for n in neg), f"missing negative {must}"


def test_footsteps_duration_maps_to_event_count():
    a = compile_sound_prompt("footsteps in a hallway", duration_seconds=3, event="footsteps")
    b = compile_sound_prompt("footsteps in a hallway", duration_seconds=5, event="footsteps")
    assert a.physicalEvent == "footsteps"
    assert a.temporal.eventCount == _footstep_count(3)
    assert b.temporal.eventCount == _footstep_count(5)
    assert a.temporal.eventCount == 5  # round(3*1.8)=5
    assert b.temporal.eventCount == 9  # round(5*1.8)=9
    assert a.temporal.eventCount != b.temporal.eventCount
    assert f"{a.temporal.eventCount} distinct footsteps over 3" in a.compiled_prompt
    assert f"{b.temporal.eventCount} distinct footsteps over 5" in b.compiled_prompt


def test_to_dict_contract_fields_and_compiled_prompt():
    r = compile_sound_prompt("Heavy steel door slam, close.", duration_seconds=2.5, intensity="bold")
    d = r.to_dict()
    for k in ("physicalEvent", "material", "context", "temporal", "negatives", "refinementOps"):
        assert k in d
    assert set(d["temporal"].keys()) == {"eventCount", "pace", "durationSec"}
    assert d["compiled_prompt"]
    assert d["compiledPrompt"] == d["compiled_prompt"]
    assert d["temporal"]["eventCount"] == 1


def test_mutate_too_soft_means_louder():
    intent = compile_sound_prompt("door slam", intensity="normal").as_intent()
    patched = mutate_sfx_intent(intent, "too_soft")
    assert patched["intensity_key"] in ("bold", "huge")
    assert "too_soft" in patched["refinementOps"]


def test_mutate_too_loud_means_softer():
    intent = compile_sound_prompt("door slam", intensity="bold").as_intent()
    patched = mutate_sfx_intent(intent, "too_loud")
    assert patched["intensity_key"] in ("normal", "soft", "subtle")


def test_mutate_duration_ops():
    intent = compile_sound_prompt("footsteps", duration_seconds=3, event="footsteps").as_intent()
    longer = mutate_sfx_intent(intent, "too_short")
    shorter = mutate_sfx_intent(intent, "too_long")
    assert longer["temporal"]["durationSec"] > 3
    assert shorter["temporal"]["durationSec"] < 3
    assert longer["temporal"]["eventCount"] == _footstep_count(longer["temporal"]["durationSec"])
    assert shorter["temporal"]["eventCount"] == _footstep_count(shorter["temporal"]["durationSec"])


def test_mutate_wrong_material_and_wrong_sound():
    intent = compile_sound_prompt("Heavy steel door slam", intensity="bold").as_intent()
    m = mutate_sfx_intent(intent, "wrong_material", materialHint="wood")
    assert m["material"] == "wood"
    s = mutate_sfx_intent(intent, "wrong_sound", physicalEventHint="footsteps")
    assert s["physicalEvent"] == "footsteps"


def test_mutate_impacts_reverb_aggressive_subtle_regen():
    intent = compile_sound_prompt("footsteps", duration_seconds=4, event="footsteps").as_intent()
    more = mutate_sfx_intent(intent, "more_impacts")
    fewer = mutate_sfx_intent(intent, "fewer_impacts")
    assert more["temporal"]["eventCount"] > intent["temporal"]["eventCount"]
    assert fewer["temporal"]["eventCount"] < intent["temporal"]["eventCount"]

    rev = mutate_sfx_intent(intent, "more_reverb")
    assert "reverb" in (rev.get("context") or "").lower()
    dry = mutate_sfx_intent(intent, "less_reverb")
    assert "reverb" in ",".join(dry["negatives"]).lower() or "dry" in (dry.get("context") or "").lower()

    agg = mutate_sfx_intent({**intent, "intensity_key": "normal"}, "more_aggressive")
    assert agg["intensity_key"] in ("bold", "huge")
    sub = mutate_sfx_intent({**intent, "intensity_key": "normal"}, "more_subtle")
    assert sub["intensity_key"] in ("soft", "subtle")

    sim = mutate_sfx_intent(intent, "regenerate_similar")
    assert "regenerate_similar" in sim["refinementOps"]
    assert sim["temporal"]["eventCount"] == intent["temporal"]["eventCount"]


def test_mutate_aliases_more_material_less_ambience():
    intent = compile_sound_prompt("door slam", intensity="bold").as_intent()
    mm = mutate_sfx_intent(intent, "more_material", materialHint="brushed steel")
    assert "steel" in (mm.get("material") or "").lower() or "brushed" in (mm.get("material") or "").lower()
    la = mutate_sfx_intent(intent, "less_ambience")
    joined = ",".join(la["negatives"]).lower()
    assert "ambience" in joined


def test_full_owner_op_set_covered():
    # every owner op (excluding aliases counted separately) must mutate without crash
    base = compile_sound_prompt("Soft wooden door close.", duration_seconds=2.5, intensity="soft").as_intent()
    required = {
        "too_soft", "too_loud", "too_short", "too_long",
        "wrong_material", "wrong_sound",
        "more_impacts", "fewer_impacts",
        "more_reverb", "less_reverb",
        "more_aggressive", "more_subtle",
        "regenerate_similar",
        "more_material", "less_ambience",
    }
    assert required <= OWNER_REFINE_OPS
    for op in sorted(required):
        out = mutate_sfx_intent(base, op, materialHint="oak", physicalEventHint="door_slam")
        assert op in out["refinementOps"]


def test_compile_from_intent_roundtrip_after_mutate():
    r0 = compile_sound_prompt("Heavy steel door slam, close.", duration_seconds=2.5, intensity="normal")
    intent = mutate_sfx_intent(r0, "too_soft")
    r1 = compile_from_intent(intent)
    assert r1.intensity_key in ("bold", "huge")
    assert "too_soft" in r1.refinementOps
    d = r1.to_dict()
    assert d["compiledPrompt"]


def test_soft_close_not_equal_slam_body():
    slam = compile_sound_prompt("Heavy steel door slam, close.", intensity="bold")
    soft = compile_sound_prompt("Soft wooden door close.", intensity="subtle")
    assert "not a slam" in soft.compiled_prompt.lower() or "slam" in {n.lower() for n in soft.negatives}
    assert "mass impact" in slam.compiled_prompt.lower() or "metallic" in slam.compiled_prompt.lower()


@pytest.mark.parametrize("dur,expected", [(3, 5), (5, 9), (1, 3), (10, 12)])
def test_footstep_count_formula(dur, expected):
    assert _footstep_count(dur) == expected
