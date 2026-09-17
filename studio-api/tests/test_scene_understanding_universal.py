"""Universal Scene Intelligence — Layer B understanding + Layer C compilation laws.

Covers the CO-DIRECTOR UNIVERSAL SCENE INTELLIGENCE CONVERGENCE mission:

- Samples A–F universality (deterministic fallback path, no LLM)
- LLM understanding path via stub llm_fn (valid + garbage + reuse)
- Scene 3 regression fixture breakdown (fallback path)
- Compiler laws: runtime separation, canonical tag stability, no alias leakage,
  batch-scoped prompts, reveal-gate scoping
- Parser laws: "Character reference of X", explicit @/#/% tags, "X as the setting",
  multi-batch validator semantics
- Retry law: follow-up reuses validated references + original request context
- Binding dedupe: check-first attach never duplicates a binding
"""

from __future__ import annotations

import json
import re

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.codirector.production.contracts import ResolvedReference
from app.codirector.production.generator_validator import (
    per_batch_duration,
    validate_scene_spec_against_generator,
)
from app.codirector.production.errors import GeneratorValidationError
from app.codirector.production.intent_parser import merge_reference_queries, parse_scene_intent
from app.codirector.production.prompt_compiler import (
    compile_batch_prompts,
    compile_generator_prompt,
    extract_prompt_section,
)
from app.codirector.production.scene_breakdown import build_director_scene_intent
from app.codirector.production.scene_understanding import (
    _main_subject,
    extract_scene_understanding,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _ref(
    name: str,
    tag: str,
    asset_type: str,
    *,
    is_global: bool = False,
) -> ResolvedReference:
    return ResolvedReference(
        status="found",
        query=name,
        display_name=name,
        asset_type=asset_type,
        asset_id=re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
        canonical_tag=tag,
        identity_tag=tag.lstrip("@#%"),
        verification="global_found" if is_global else "found",
        is_global=is_global,
        approved_sheet=True,
    )


def _build(message: str, refs: list[ResolvedReference], **kwargs):
    spec = parse_scene_intent(message, project_id="proj")
    intent = build_director_scene_intent(spec, refs, allow_llm=False, **kwargs)
    spec.director_intent = intent
    return spec, intent


def _compile(message: str, refs: list[ResolvedReference]) -> str:
    spec = parse_scene_intent(message, project_id="proj")
    intent = build_director_scene_intent(spec, refs, allow_llm=False)
    spec.director_intent = intent
    return compile_generator_prompt(spec, refs)


# --- Sample requests (universal, non-franchise) ----------------------------

SAMPLE_A = """
Create a Timeline scene using the Neon Harbor environment reference sheet as the setting.
Slow lateral pan across the rain-soaked docks at night, neon signs reflecting in the water.
Establishing shot, 10 seconds, 21:9, 1.0 megapixels, MiniMax H3, single batch.
"""

SAMPLE_B = """
Build a Timeline scene with the Character reference of Mara Voss inside the Derelict Station environment reference sheet.
CAMERA: slow push-in down the dark corridor.
Mara stays hidden in shadow until the emergency lights snap on at the end.
Do not reveal Mara before the lights come on.
Menacing quiet. 10 seconds, one batch, MiniMax H3, 21:9, 1.0 MP.
"""

SAMPLE_C = """
Create a Timeline scene in the Rooftop Garden environment with the Character reference of Ilsa Ren
and the Character reference of Dae-Ho Kim.
Ilsa stands by the railing. Dae-Ho approaches and stops beside her.
ILSA: "We should not be up here."
DAE-HO: "Neither should the courier."
Minimal movement, calm delivery. 10 seconds, MiniMax H3, 21:9, 1.0 MP, 1 batch.
"""

SAMPLE_D = """
Make a Timeline scene in the Canyon Crossing environment using the Supply Sled prop reference sheet
and the Winch Tower prop reference sheet.
The winch tower hauls the supply sled up the cliff face. The sled swings, scrapes rock,
and slams onto the ledge. The Winch Tower is 40 meters tall and the sled is 2 meters long.
12 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.
"""

SAMPLE_E = """
Create a Timeline scene in the Salt Flats environment with the Character reference of The Courier.
A ring of blue energy tears open in the air with a flash. Smoke rolls out.
The Courier steps out of the portal only after the smoke clears.
Do not show The Courier before the portal fully opens.
10 seconds, MiniMax H3, 21:9, 1.0 megapixels, single batch.
"""

SAMPLE_F = """
Build a Timeline scene in the Flooded Arcade environment with the Character reference of Jun Park.
Wide establishing shot of the drowned concourse. Jun wades in from the left.
He stops, listens. A sign crashes down behind him. He turns toward the sound.
Then he keeps moving deeper into the arcade and exits frame right.
End on the empty rippling water. 20 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP.
"""

SCENE3_REQUEST = """For Scene 3, I would like to create a Timeline prompt for the Character reference of Cade O'Connor, and using the Venture Corridor Scene environment reference sheet as the setting. Here is the prompt for the scene: Cinematic high-quality semi-realistic anime sci-fi scene. Preserve Cade's exact armor, proportions, helmet, red illuminated circuitry, and red eyes from Image 1. Preserve the Venture Corridor architecture and visual design from Image 2. CAMERA: Begin with a slow, ominous forward dolly through the Venture Corridor toward a sealed metal door. Keep the camera centered on the door and continuously move closer throughout the sequence. ACTION: The sealed door suddenly buckles inward as an enormous punching dent violently appears from the opposite side. Cade is NOT yet visible. Hold for one second. A second brutal impact strikes from behind the door, creating another deep punching dent and further deforming the metal. Silence. The damaged center of the door gradually begins glowing red-hot. The metal reaches an intense red-orange temperature. Suddenly, a concentrated red energy beam blasts through from the opposite side, violently blowing a large jagged hole through the door. Hot fragments and sparks burst into the corridor. Thick white steam and smoke pour through the opening and temporarily obscure everything beyond it. Continue the slow dolly toward the destroyed doorway. Through the dense white steam, two glowing red eyes become visible first. Then faint red lights from Cade's armor appear through the haze, gradually revealing his enormous silhouette. Cade steps through the mangled doorway. He is imposing, calm and completely focused. He does not rush. Steam rolls around his black armor as he walks directly toward the approaching camera. His red eyes and red suit circuitry glow through the haze. His movement is deliberate, heavy and intimidating. Cade keeps his masked face aimed straight ahead and says in a deep, controlled, slightly synthetic/robotic male voice: CADE: "Where is the Adept?" After speaking, Cade continues advancing toward camera with unwavering focus. MOOD: Menacing, ominous, restrained power. Cade should feel like an unstoppable weapon entering the Venture rather than an enraged brute. IMPORTANT CONTINUITY: Do not reveal Cade before the laser blast. The first two door impacts originate from Cade on the unseen opposite side. Cade remains fully masked for the entire shot. No additional characters. No handheld weapons. No costume changes. No extra dialogue. No subtitles or on-screen text. Maintain the same Venture corridor throughout the shot. Maintain Cade's exact red-era armor design throughout. The scene will be 30 seconds long with 2 batches. 21:9, 1.0 MegaPixels using MiniMax H3."""


def _scene3_refs() -> list[ResolvedReference]:
    return [
        _ref("Cade O'Connor", "@CadeOConnor", "character"),
        _ref("Venture Corridor Scene", "#VentureCorridorScene", "environment", is_global=True),
    ]


# ---------------------------------------------------------------------------
# Sample A — environment-only establishing
# ---------------------------------------------------------------------------

def test_sample_a_environment_only_establishing() -> None:
    refs = [_ref("Neon Harbor", "#NeonHarbor", "environment")]
    spec, intent = _build(SAMPLE_A, refs)
    assert intent.environment.tag == "#NeonHarbor"
    assert intent.environment.verified
    assert intent.subjects == []
    assert intent.dialogue == []
    assert intent.scene_beats, "establishing scene still needs beats"
    assert intent.scene_type in {"establishing", "cinematic", "action"}
    prompt = compile_generator_prompt(spec, refs)
    assert "#NeonHarbor" in prompt
    subjects_section = extract_prompt_section(prompt, "SUBJECTS")
    assert "@" not in subjects_section and "%" not in subjects_section
    action = extract_prompt_section(prompt, "ACTION").lower()
    assert "neon" in action or "dock" in action or "harbor" in action
    assert "minimax" not in action and "21:9" not in action and "megapixel" not in action


# ---------------------------------------------------------------------------
# Sample B — character + environment suspense reveal
# ---------------------------------------------------------------------------

def test_sample_b_suspense_reveal_gating() -> None:
    refs = [
        _ref("Mara Voss", "@MaraVoss", "character"),
        _ref("Derelict Station", "#DerelictStation", "environment"),
    ]
    spec, intent = _build(SAMPLE_B, refs)
    assert intent.environment.tag == "#DerelictStation"
    assert {s.tag for s in intent.subjects} == {"@MaraVoss"}
    assert intent.reveals, "reveal gate must be extracted"
    reveal = intent.reveals[0]
    assert reveal.subject_tag == "@MaraVoss"
    assert "light" in (reveal.hidden_until or "").lower()
    assert intent.dialogue == []
    prompt = compile_generator_prompt(spec, refs)
    action = extract_prompt_section(prompt, "ACTION")
    assert re.search(r"hidden until|not reveal|remains? hidden", action, re.I)
    assert "@MaraVoss" in prompt
    continuity = extract_prompt_section(prompt, "CONTINUITY / REFERENCE PRESERVATION")
    assert "lights" in continuity.lower() or "hidden" in continuity.lower()


# ---------------------------------------------------------------------------
# Sample C — dialogue scene
# ---------------------------------------------------------------------------

def test_sample_c_dialogue_extraction_and_attribution() -> None:
    refs = [
        _ref("Ilsa Ren", "@IlsaRen", "character"),
        _ref("Dae-Ho Kim", "@DaeHoKim", "character"),
        _ref("Rooftop Garden", "#RooftopGarden", "environment"),
    ]
    spec, intent = _build(SAMPLE_C, refs)
    assert {s.tag for s in intent.subjects} == {"@IlsaRen", "@DaeHoKim"}
    assert len(intent.dialogue) == 2
    by_speaker = {line.speaker: line for line in intent.dialogue}
    assert by_speaker["Ilsa Ren"].line == "We should not be up here."
    assert by_speaker["Dae-Ho Kim"].line == "Neither should the courier."
    assert by_speaker["Ilsa Ren"].speaker_tag == "@IlsaRen"
    assert by_speaker["Dae-Ho Kim"].speaker_tag == "@DaeHoKim"
    assert intent.scene_type == "dialogue"
    prompt = compile_generator_prompt(spec, refs)
    action = extract_prompt_section(prompt, "ACTION")
    # Exact lines preserved verbatim, never paraphrased.
    assert '"We should not be up here."' in action
    assert '"Neither should the courier."' in action
    # Dialogue is attributed, and non-dialogue action stays separate.
    assert "railing" in action.lower()
    assert "approach" in action.lower()


# ---------------------------------------------------------------------------
# Sample D — prop-driven physical action
# ---------------------------------------------------------------------------

def test_sample_d_prop_action_and_scale() -> None:
    refs = [
        _ref("Supply Sled", "%SupplySled", "prop"),
        _ref("Winch Tower", "%WinchTower", "prop"),
        _ref("Canyon Crossing", "#CanyonCrossing", "environment"),
    ]
    spec, intent = _build(SAMPLE_D, refs)
    assert {s.tag for s in intent.subjects} == {"%SupplySled", "%WinchTower"}
    assert intent.environment.tag == "#CanyonCrossing"
    prompt = compile_generator_prompt(spec, refs)
    action = extract_prompt_section(prompt, "ACTION").lower()
    assert "hauls" in action or "winch" in action
    assert "slams" in action or "swings" in action
    spatial = extract_prompt_section(prompt, "SPATIAL RELATIONSHIPS").lower()
    assert "40 meters" in spatial or "40 m" in spatial
    assert "2 meters" in spatial or "2 m" in spatial
    assert "%SupplySled" in prompt and "%WinchTower" in prompt


# ---------------------------------------------------------------------------
# Sample E — VFX reveal
# ---------------------------------------------------------------------------

def test_sample_e_vfx_reveal() -> None:
    refs = [
        _ref("The Courier", "@TheCourier", "character"),
        _ref("Salt Flats", "#SaltFlats", "environment"),
    ]
    spec, intent = _build(SAMPLE_E, refs)
    assert intent.reveals, "portal reveal gate must be extracted"
    reveal = intent.reveals[0]
    assert reveal.subject_tag == "@TheCourier"
    assert "portal" in (reveal.hidden_until or "").lower()
    vfx_beats = [b for b in intent.scene_beats if b.vfx]
    assert vfx_beats, "energy/portal beat must carry VFX markup"
    prompt = compile_generator_prompt(spec, refs)
    action = extract_prompt_section(prompt, "ACTION")
    assert "portal" in action.lower()
    assert re.search(r"hidden until|not show|remains? hidden", action, re.I)


# ---------------------------------------------------------------------------
# Sample F — multi-beat cinematic with explicit end state
# ---------------------------------------------------------------------------

def test_sample_f_multi_beat_order_and_end_state() -> None:
    refs = [
        _ref("Jun Park", "@JunPark", "character"),
        _ref("Flooded Arcade", "#FloodedArcade", "environment"),
    ]
    spec, intent = _build(SAMPLE_F, refs)
    descriptions = [b.description.lower() for b in intent.scene_beats]
    assert len(intent.scene_beats) >= 5
    blob = " ".join(descriptions)
    assert "wades" in blob
    assert "crashes" in blob
    assert "exits" in blob or "exit" in blob
    # Order: wading precedes the sign crash which precedes the exit.
    wade_idx = next(i for i, d in enumerate(descriptions) if "wades" in d)
    crash_idx = next(i for i, d in enumerate(descriptions) if "crashes" in d)
    exit_idx = next(i for i, d in enumerate(descriptions) if "exits" in d or "exit" in d)
    assert wade_idx < crash_idx < exit_idx
    assert intent.end_state and "water" in intent.end_state.lower()
    # Multi-batch: 20s across 2 batches validates (10s per batch <= 15s H3 cap).
    assert spec.batch_count == 2
    assert per_batch_duration(spec) == 10.0
    validate_scene_spec_against_generator(spec)
    prompts = compile_batch_prompts(spec, refs)
    assert len(prompts) == 2
    assert "0–10" in prompts[0] and "10–20" in prompts[1]
    # Batch 1 carries the early beats; batch 2 carries the exit.
    assert "wades" in prompts[0].lower()
    assert "exits" in prompts[1].lower() or "exit" in prompts[1].lower()


# ---------------------------------------------------------------------------
# Scene 3 regression fixture — deterministic fallback breakdown
# ---------------------------------------------------------------------------

def test_scene3_fallback_breakdown_full() -> None:
    refs = _scene3_refs()
    spec, intent = _build(SCENE3_REQUEST, refs)

    # References + tags
    assert intent.environment.tag == "#VentureCorridorScene"
    assert {s.tag for s in intent.subjects} == {"@CadeOConnor"}

    # Beats: ordered door-breach sequence before the reveal.
    kinds = [b.kind for b in intent.scene_beats]
    assert len(intent.scene_beats) >= 10
    descriptions = [b.description.lower() for b in intent.scene_beats]
    buckle = next(i for i, d in enumerate(descriptions) if "buckles" in d)
    beam = next(i for i, d in enumerate(descriptions) if "energy beam" in d)
    eyes = next(i for i, d in enumerate(descriptions) if "red eyes" in d)
    steps = next(i for i, d in enumerate(descriptions) if "steps through" in d)
    assert buckle < beam < eyes < steps
    assert "impact" in kinds and "pause" in kinds and "reveal" in kinds
    hold = next(b for b in intent.scene_beats if b.hold_seconds)
    assert hold.hold_seconds == 1.0

    # Reveal gating survives with staged order.
    assert intent.reveals
    reveal = intent.reveals[0]
    assert reveal.subject_tag == "@CadeOConnor"
    assert "laser" in (reveal.hidden_until or "").lower()
    assert reveal.hidden_until_beat is not None
    assert any("eyes" in part.lower() for part in reveal.reveal_order)

    # Dialogue: exact line, speaker resolved, delivery voice extracted.
    assert len(intent.dialogue) == 1
    line = intent.dialogue[0]
    assert line.speaker_tag == "@CadeOConnor"
    assert line.line == "Where is the Adept?"
    assert "voice" in (line.delivery or "").lower()
    assert "synthetic" in (line.delivery or "").lower()
    # Dialogue lands late in the scene, not at the top.
    assert line.beat_index is not None and line.beat_index >= steps - 1

    # Exclusions + subtitle policy.
    exclusions = " ".join(intent.exclusions).lower()
    assert "no additional characters" in exclusions
    assert "no handheld weapons" in exclusions
    assert intent.subtitle_policy == "none"

    # Camera intelligence.
    assert "dolly" in intent.camera_plan.movement.lower()
    assert "door" in (intent.camera_plan.target or "").lower()
    assert intent.camera_plan.evolution

    # Mood.
    assert "menacing" in intent.mood.lower()


def test_scene3_prompt_runtime_separation_and_tags() -> None:
    refs = _scene3_refs()
    spec, intent = _build(SCENE3_REQUEST, refs)
    prompts = compile_batch_prompts(spec, refs)
    assert len(prompts) == 2
    for prompt in prompts:
        action = extract_prompt_section(prompt, "ACTION")
        # Runtime metadata never leaks into ACTION prose.
        for token in ("30 seconds", "21:9", "megapixel", "MiniMax", "H3", "batch"):
            assert token.lower() not in action.lower(), token
        # No instruction copy.
        assert "I would like" not in action
        assert "Timeline prompt" not in action
        # Canonical tags stable; no suffix drift; no Image1/R2V tokens.
        assert "@CadeOConnor" in prompt
        assert "#VentureCorridorScene" in prompt
        assert not re.search(r"@CadeOConnor\d", prompt)
        assert not re.search(r"#VentureCorridorScene\d", prompt)
        assert "Image1" not in prompt and "Image2" not in prompt and "[R2V]" not in prompt
        # Spaced ordinals from creator prose ("from Image 1") never leak either.
        assert not re.search(r"\bImage\s*\d+\b", prompt)
    # Batch windows split the scene: breach in batch 1, dialogue in batch 2.
    action1 = extract_prompt_section(prompts[0], "ACTION")
    action2 = extract_prompt_section(prompts[1], "ACTION")
    assert "buckles" in action1.lower()
    assert '"Where is the Adept?"' in action2
    assert "0–15" in prompts[0] and "15–30" in prompts[1]
    # Validator accepts 30s across 2 batches on H3 (15s per batch).
    validate_scene_spec_against_generator(spec)


def test_compiler_rewrites_image_ordinals_to_canonical_tags() -> None:
    """LLM-extracted continuity may quote creator prose ("from Image 1").
    Layer C must rewrite those ordinals to canonical tags — never leak them."""
    refs = _scene3_refs()
    spec, intent = _build(SCENE3_REQUEST, refs)
    intent.continuity_rules = [
        "Preserve Cade's exact armor, proportions, helmet, red illuminated circuitry, and red eyes from Image 1",
        "Preserve the Venture Corridor architecture and visual design from Image 2",
        "Maintain the same Venture corridor throughout the shot",
    ]
    spec.director_intent = intent
    prompt = compile_generator_prompt(spec, refs)
    assert not re.search(r"\bImage\s*\d+\b", prompt)
    continuity = extract_prompt_section(prompt, "CONTINUITY / REFERENCE PRESERVATION")
    # Creative content survives; the ordinal becomes the canonical tag.
    assert "red illuminated circuitry" in continuity
    assert "@CadeOConnor" in continuity
    assert "#VentureCorridorScene" in continuity
    assert "Maintain the same Venture corridor throughout the shot" in continuity


def test_compiler_drops_meta_settings_exclusions_and_runtime_tokens() -> None:
    """LLM-extracted exclusions may quote meta-instructions ("Ignore runtime
    settings (20 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP)"). Runtime
    metadata must not survive in ANY prompt section — constraint sections are
    cinematic prohibitions only."""
    refs = _scene3_refs()
    spec, intent = _build(SCENE3_REQUEST, refs)
    intent.exclusions = [
        "No additional characters",
        "Ignore runtime settings (30 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP)",
        "No runtime/execution settings",
        "No generator names",
        "No aspect ratios",
        "No",
        "No batch counts",
    ]
    spec.director_intent = intent
    prompt = compile_generator_prompt(spec, refs)
    negative = extract_prompt_section(prompt, "NEGATIVE / EXCLUSION CONSTRAINTS")
    assert "No additional characters" in negative
    # Meta-settings lines and degenerate fragments are gone entirely.
    assert "runtime" not in negative.lower()
    assert "generator names" not in negative.lower()
    assert "aspect ratios" not in negative.lower()
    assert "batch counts" not in negative.lower()
    # Runtime metadata appears in NO section of the compiled prompt.
    assert not re.search(
        r"\b\d+(?:\.\d+)?\s*seconds?\b|21:9|16:9|megapixels?|\b\d(?:\.\d+)?\s*MP\b|\bminimax\b|\bh3\b|\b\d+\s+batches?\b",
        prompt,
        re.I,
    ), prompt


def test_megapixels_mp_abbreviation_parses() -> None:
    """Creators write "1.0 MP" — the runtime field must capture it."""
    spec = parse_scene_intent(
        "Create a Timeline scene using the Neon Harbor environment reference sheet. "
        "Slow pan. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.",
        project_id="proj",
    )
    assert spec.megapixels == 1.0


def test_llm_beat_coverage_backfill_restores_dropped_events() -> None:
    """An LLM rewrite that silently drops a staged event (the FIRST of two
    door impacts, the one-second hold) must be caught by the beat-coverage
    backstop: cardinality per event class + paraphrase-tolerant coverage."""
    llm_payload = {
        "scene_type": "multi_beat_cinematic",
        "mood": "menacing",
        "environment_name": "Venture Corridor Scene",
        "assets": [
            {"name": "Cade O'Connor", "hinted_type": "character"},
            {"name": "Venture Corridor Scene", "hinted_type": "environment"},
        ],
        # NOTE: the first impact and the hold are deliberately ABSENT — the
        # model jumped straight to the "second" impact.
        "beats": [
            {"kind": "establish", "description": "The camera performs a slow, ominous forward dolly through the Venture Corridor toward a sealed metal door."},
            {"kind": "impact", "description": "A second brutal impact strikes from behind the door, creating another deep punching dent and further deforming the metal."},
            {"kind": "pause", "description": "Silence."},
            {"kind": "escalation", "description": "The damaged center of the door gradually begins glowing red-hot."},
            {"kind": "impact", "description": "A concentrated red energy beam blasts through, blowing a jagged hole; hot fragments and sparks burst into the corridor; thick white steam pours through the opening."},
            {"kind": "reveal", "description": "Through the dense steam, two glowing red eyes become visible first, then Cade's enormous silhouette."},
            {"kind": "approach", "description": "Cade steps through the mangled doorway and advances toward camera."},
        ],
        "reveals": [{"subject": "Cade O'Connor", "hidden_until": "the laser blast", "reveal_order": ["glowing red eyes", "silhouette"], "condition": ""}],
        "dialogue": [{"speaker": "Cade", "line": "Where is the Adept?", "delivery": "", "voice_characteristics": "", "filtering": "", "after_beat": None}],
        "camera": {"shot_type": "tracking", "movement": "slow forward dolly", "framing": "", "target": "the sealed door", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": ["No additional characters"],
        "subtitle_policy": "none",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _reason = extract_scene_understanding(
        SCENE3_REQUEST, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    descriptions = [beat.description.lower() for beat in understanding.beats]
    # First impact restored — and ordered BEFORE the second impact.
    first = next(i for i, d in enumerate(descriptions) if "buckles" in d)
    second = next(i for i, d in enumerate(descriptions) if "second brutal impact" in d)
    assert first < second
    # The one-second hold is restored as a hold beat between the impacts.
    holds = [b for b in understanding.beats if b.kind == "hold" and b.hold_seconds == 1.0]
    assert holds, descriptions
    hold_index = understanding.beats.index(holds[0])
    assert first < hold_index < second


def test_gate_dedup_preserves_merged_hold_beat() -> None:
    """Live Scene 3 flake regression: when the LLM merges the one-second hold
    and the visibility gate into ONE beat, the reveal-gate dedup in the
    breakdown must strip only the gate clause — dropping the whole beat loses
    the staged hold from the compiled ACTION."""
    llm_payload = {
        "scene_type": "multi_beat_cinematic",
        "mood": "menacing",
        "environment_name": "Venture Corridor Scene",
        "assets": [
            {"name": "Cade O'Connor", "hinted_type": "character"},
            {"name": "Venture Corridor Scene", "hinted_type": "environment"},
        ],
        "beats": [
            {"kind": "establish", "description": "The camera performs a slow, ominous forward dolly through the Venture Corridor toward a sealed metal door."},
            {"kind": "impact", "description": "The sealed door suddenly buckles inward as an enormous punching dent violently appears from the opposite side."},
            # The merged beat: a real staged hold PLUS a restated gate.
            {"kind": "hold", "hold_seconds": 1.0, "description": "The shot holds for one second on the dented door. Cade O'Connor is not yet visible."},
            {"kind": "impact", "description": "A second brutal impact strikes from behind the door, creating another deep punching dent and further deforming the metal."},
            {"kind": "reveal", "description": "Through the dense steam, two glowing red eyes become visible first, then Cade's enormous silhouette."},
            {"kind": "approach", "description": "Cade steps through the mangled doorway and advances toward camera."},
        ],
        "reveals": [{"subject": "Cade O'Connor", "hidden_until": "the laser blast", "reveal_order": ["glowing red eyes", "silhouette"], "condition": ""}],
        "dialogue": [{"speaker": "Cade", "line": "Where is the Adept?", "delivery": "", "voice_characteristics": "", "filtering": "", "after_beat": None}],
        "camera": {"shot_type": "tracking", "movement": "slow forward dolly", "framing": "", "target": "the sealed door", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": ["No additional characters"],
        "subtitle_policy": "none",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _reason = extract_scene_understanding(
        SCENE3_REQUEST, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    refs = [
        _ref("Cade O'Connor", "@CadeOConnor", "character"),
        _ref("Venture Corridor Scene", "#VentureCorridorScene", "environment"),
    ]
    spec = parse_scene_intent(SCENE3_REQUEST, project_id="proj")
    intent = build_director_scene_intent(
        spec, refs, understanding=understanding, understanding_source="llm"
    )
    spec.director_intent = intent
    hold_beats = [b for b in intent.scene_beats if b.hold_seconds == 1.0]
    assert hold_beats, [b.description for b in intent.scene_beats]
    assert "not yet visible" not in hold_beats[0].description.lower()
    assert "holds for one second" in hold_beats[0].description.lower()
    prompt = compile_generator_prompt(spec, refs)
    assert re.search(r"holds? for (?:one|1|a) second", prompt, re.I), prompt
    # The gate is still stated — exactly once, by the reveal constraint.
    assert len(re.findall(r"remains hidden until", prompt, re.I)) == 1


def test_hold_seconds_verbalized_when_llm_paraphrases_duration() -> None:
    """A timed hold is cinematic structure: when the LLM sets hold_seconds but
    paraphrases the beat without duration language, the description must be
    normalized to state the duration — otherwise the compiled prompt silently
    loses the staged one-second hold (live Scene 3 flake, peer round 3)."""
    llm_payload = {
        "scene_type": "suspense",
        "mood": "menacing",
        "environment_name": "Derelict Station",
        "assets": [],
        "beats": [
            {"kind": "establish", "description": "The camera pushes down the dark corridor."},
            # hold_seconds set, but the prose carries no duration language.
            {"kind": "hold", "hold_seconds": 1.0, "description": "The scene holds on the battered door."},
            {"kind": "impact", "description": "The door bursts inward."},
        ],
        "reveals": [],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "push-in", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        "Build a scene in Timeline in the Derelict Station environment reference sheet. "
        "Slow push-in. Hold for one second on the battered door. The door bursts inward. "
        "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.",
        llm_fn=lambda _s, _u: json.dumps(llm_payload),
    )
    assert source == "llm"
    hold = next(b for b in understanding.beats if b.hold_seconds == 1.0)
    assert re.search(r"holds? for one second", hold.description, re.I), hold.description


def test_backfill_stages_all_events_when_llm_omits_every_beat() -> None:
    """Total beat omission must not compile an empty ACTION: when the LLM
    returns scene metadata with zero beats, every salient on-screen event is
    staged from the source."""
    llm_payload = {
        "scene_type": "suspense",
        "mood": "menacing",
        "environment_name": "Derelict Station",
        "assets": [],
        "beats": [],
        "reveals": [],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "push-in", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    message = (
        "Build a scene in Timeline in the Derelict Station environment reference sheet. "
        "Mara crosses the dark corridor. A siren wakes behind her. She runs for the airlock. "
        "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP."
    )
    understanding, source, _ = extract_scene_understanding(
        message, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    descriptions = " ".join(b.description.lower() for b in understanding.beats)
    assert "crosses the dark corridor" in descriptions
    assert "siren" in descriptions
    assert "airlock" in descriptions


def test_fallback_cinematicizes_reveal_and_show_imperatives() -> None:
    """"Reveal Mara slowly." / "Show the doorway first." are Layer A
    imperatives; Layer B must restage them declaratively, not copy them."""
    message = (
        "Build a scene in Timeline in the Derelict Station environment reference sheet "
        "with the Character reference of Mara Voss. Reveal Mara slowly. "
        "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP."
    )
    spec, intent = _build(
        message,
        [
            _ref("Mara Voss", "@MaraVoss", "character"),
            _ref("Derelict Station", "#DerelictStation", "environment"),
        ],
    )
    action = intent.action_text
    assert "The shot reveals Mara slowly." in action
    assert "Reveal Mara slowly." not in action.replace("The shot reveals Mara slowly.", "")


def test_gate_dedup_keeps_sibling_clauses_of_merged_beat() -> None:
    """Clause-level gate strip: only the clause carrying the visibility gate
    is removed; sibling staged events in the same sentence survive."""
    llm_payload = {
        "scene_type": "suspense",
        "mood": "menacing",
        "environment_name": "Venture Corridor Scene",
        "assets": [{"name": "Cade O'Connor", "hinted_type": "character"}],
        "beats": [
            {"kind": "establish", "description": "The camera dollies toward a sealed metal door."},
            {
                "kind": "hold",
                "hold_seconds": 1.0,
                "description": "The shot holds for one second and the camera pushes closer while Cade O'Connor remains hidden.",
            },
            {"kind": "reveal", "description": "Two glowing red eyes become visible through the steam."},
        ],
        "reveals": [{"subject": "Cade O'Connor", "hidden_until": "the blast", "reveal_order": [], "condition": ""}],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "dolly", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        SCENE3_REQUEST, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    refs = [
        _ref("Cade O'Connor", "@CadeOConnor", "character"),
        _ref("Venture Corridor Scene", "#VentureCorridorScene", "environment"),
    ]
    spec = parse_scene_intent(SCENE3_REQUEST, project_id="proj")
    intent = build_director_scene_intent(
        spec, refs, understanding=understanding, understanding_source="llm"
    )
    hold = next((b for b in intent.scene_beats if b.hold_seconds == 1.0), None)
    assert hold is not None, [b.description for b in intent.scene_beats]
    assert "holds for one second" in hold.description.lower()
    assert "pushes closer" in hold.description.lower(), "sibling camera clause must survive"
    assert "remains hidden" not in hold.description.lower(), "gate clause must be stripped"


def test_repetition_cardinality_same_beat_cannot_cover_two_stagings() -> None:
    """Two similarly worded source impacts must not both map to ONE LLM beat:
    a beat realizes a staged repetition only when it explicitly signals
    multiplicity ("two impacts", "twice"). Otherwise the second staging is
    backfilled as its own beat (peer round-4 blocker)."""
    message = (
        "Build a scene in Timeline in the Derelict Station environment reference sheet. "
        "The cargo door buckles inward from a massive impact. "
        "The cargo door buckles inward again, harder. "
        "Mara stumbles backward. "
        "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP."
    )
    # The LLM merged BOTH staged impacts into a single beat with no
    # multiplicity language.
    llm_payload = {
        "scene_type": "suspense",
        "mood": "tense",
        "environment_name": "Derelict Station",
        "assets": [],
        "beats": [
            {"kind": "impact", "description": "The cargo door buckles inward from a massive impact."},
            {"kind": "action", "description": "Mara stumbles backward."},
        ],
        "reveals": [],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        message, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    buckling = [b for b in understanding.beats if "buckles" in b.description.lower()]
    assert len(buckling) == 2, [b.description for b in understanding.beats]
    assert "again" in buckling[1].description.lower()

    # But an explicit-multiplicity merge ("buckles twice") legitimately
    # covers both stagings — no duplicate backfill.
    llm_payload["beats"] = [
        {"kind": "impact", "description": "The cargo door buckles inward twice from massive impacts."},
        {"kind": "action", "description": "Mara stumbles backward."},
    ]
    understanding2, _, _ = extract_scene_understanding(
        message, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    buckling2 = [b for b in understanding2.beats if "buckles" in b.description.lower()]
    assert len(buckling2) == 1, [b.description for b in understanding2.beats]


def test_repetition_cardinality_identical_vocabulary_stagings() -> None:
    """The exact peer round-5 repro: two staged impacts with IDENTICAL
    distinctive vocabularies ("the door buckles inward" / "the door buckles
    inward again") sharing one plain beat — the beat stages the event once,
    so the second staging must be backfilled as its own beat."""
    message = (
        "Build a scene in Timeline in the Derelict Station environment reference sheet. "
        "The cargo door buckles inward. "
        "The cargo door buckles inward again. "
        "Mara stumbles backward. "
        "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP."
    )
    llm_payload = {
        "scene_type": "suspense",
        "mood": "tense",
        "environment_name": "Derelict Station",
        "assets": [],
        "beats": [
            {"kind": "impact", "description": "The cargo door buckles inward."},
            {"kind": "action", "description": "Mara stumbles backward."},
        ],
        "reveals": [],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        message, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    buckling = [b for b in understanding.beats if "buckles" in b.description.lower()]
    assert len(buckling) == 2, [b.description for b in understanding.beats]
    assert "again" in buckling[1].description.lower()
    # Order preserved: the plain buckling precedes the "again" staging.
    assert "again" not in buckling[0].description.lower()


def test_consequence_clause_backfill_restores_dropped_result_event() -> None:
    """A trailing consequence clause (", sending a wave across the arcade")
    stages its own on-screen event. When the LLM keeps the cause but drops
    the consequence, the clause is re-staged with its actor right after the
    covering beat (live Sample D flake)."""
    message = (
        "Create a Timeline scene in the Flooded Arcade environment reference sheet with the "
        "Winch Tower prop reference sheet. "
        "The winch tower groans and tips sideways into the water, sending a wave across the arcade. "
        "The tower is over 12 meters tall. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP."
    )
    llm_payload = {
        "scene_type": "action",
        "mood": "heavy",
        "environment_name": "Flooded Arcade",
        "assets": [{"name": "Winch Tower", "hinted_type": "prop"}],
        "beats": [
            # The cause survived; the wave consequence was dropped.
            {"kind": "action", "description": "The winch tower, standing over 12 meters tall, groans and tips sideways into the water of the flooded arcade."},
        ],
        "reveals": [],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        message, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    descriptions = [b.description for b in understanding.beats]
    wave = next((b for b in understanding.beats if "wave" in b.description.lower()), None)
    assert wave is not None, descriptions
    assert "sends a wave across the arcade" in wave.description.lower()
    assert "winch tower" in wave.description.lower(), "consequence keeps its actor"
    # The consequence lands after the cause.
    cause_index = next(i for i, b in enumerate(understanding.beats) if "groans" in b.description.lower())
    assert understanding.beats.index(wave) == cause_index + 1


def test_consequence_backfill_never_duplicates_parent_sentence() -> None:
    """Peer round-6 blocker (live Scene 3 duplicate): when the LLM paraphrases
    the cause and drops the consequence detail, the backfill must re-stage
    ONLY the consequence with its actor — never the whole parent sentence,
    which duplicates the already-staged cause. The parent here leads with an
    adverb + indefinite article ("Suddenly, a concentrated red energy
    beam…"), the exact shape that broke subject extraction live."""
    message = (
        "Build a Timeline scene in the Venture Corridor environment reference sheet. "
        "Suddenly, a concentrated red energy beam blasts through from the opposite side, "
        "violently blowing a large jagged hole through the door. "
        "Hot fragments and sparks burst into the corridor. "
        "30 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP."
    )
    llm_payload = {
        "scene_type": "action",
        "mood": "violent",
        "environment_name": "Venture Corridor",
        "assets": [],
        "beats": [
            # Paraphrase that drops "large jagged hole".
            {"kind": "impact", "description": "A concentrated red energy beam blasts through the door."},
            {"kind": "impact", "description": "Hot fragments and sparks burst into the corridor."},
        ],
        "reveals": [],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        message, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    descriptions = [b.description for b in understanding.beats]
    hole = next((b for b in understanding.beats if "jagged hole" in b.description.lower()), None)
    assert hole is not None, descriptions
    assert "blows a large jagged hole through the door" in hole.description.lower()
    assert "energy beam" in hole.description.lower(), "consequence keeps its actor"
    # The cause is staged exactly once — no whole-sentence re-stage duplicate.
    beam_beats = [b for b in understanding.beats if "energy beam" in b.description.lower()]
    assert len(beam_beats) == 2, descriptions  # cause beat + consequence beat
    assert not any("blasts through from the opposite side" in b.description.lower() and "blowing" in b.description.lower() for b in understanding.beats), descriptions


def test_main_subject_handles_plurals_adverbs_and_past_tense() -> None:
    """Peer round-6 probes: plural -s subjects ("the twin towers groan"),
    leading adverbs ("Suddenly, …"), and past-tense verbs ("blasted") must
    all yield the full subject noun phrase."""
    assert _main_subject("The twin towers groan under the strain, sending a wave.") == "The twin towers"
    assert _main_subject("Suddenly, a concentrated red energy beam blasts through, blowing a hole.") == "a concentrated red energy beam"
    assert _main_subject("The beam blasted through the door, blowing a hole.") == "The beam"
    assert _main_subject("Hot fragments and sparks burst into the corridor, forcing Mara back.") == "Hot fragments and sparks"
    assert _main_subject("The winch tower groans and tips sideways, sending a wave.") == "The winch tower"
    assert _main_subject("The battered door buckles inward, hurling splinters.") == "The battered door"


def test_repetition_cardinality_multiplicity_count_limits_coverage() -> None:
    """Peer round-6 blocker: multiplicity is count-aware, not boolean — a
    "buckles twice" beat stages exactly TWO impacts, so a third staged impact
    must still be backfilled."""
    message = (
        "Build a scene in Timeline in the Derelict Station environment reference sheet. "
        "The cargo door buckles inward. "
        "The cargo door buckles inward again. "
        "The cargo door buckles inward a third time. "
        "Mara stumbles backward. "
        "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP."
    )
    llm_payload = {
        "scene_type": "suspense",
        "mood": "tense",
        "environment_name": "Derelict Station",
        "assets": [],
        "beats": [
            {"kind": "impact", "description": "The cargo door buckles inward twice."},
            {"kind": "action", "description": "Mara stumbles backward."},
        ],
        "reveals": [],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        message, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    buckling = [b for b in understanding.beats if "buckles" in b.description.lower()]
    # One merged "twice" beat + one backfilled third staging.
    assert len(buckling) == 2, [b.description for b in understanding.beats]
    assert any("twice" in b.description.lower() for b in buckling)
    assert any("third" in b.description.lower() for b in buckling)


def test_repetition_cardinality_unclassed_repeated_action() -> None:
    """Peer round-6 blocker: repetition cardinality is not limited to the
    cinematic event classes — ANY repeated on-screen action ("Mara raises
    her hand" three times) must survive as three stagings."""
    message = (
        "Build a scene in Timeline in the Derelict Station environment reference sheet. "
        "Mara raises her hand. "
        "Mara raises her hand again. "
        "Mara raises her hand a third time. "
        "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP."
    )
    llm_payload = {
        "scene_type": "drama",
        "mood": "quiet",
        "environment_name": "Derelict Station",
        "assets": [],
        "beats": [
            {"kind": "action", "description": "Mara raises her hand."},
        ],
        "reveals": [],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        message, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    raises = [b for b in understanding.beats if "raises" in b.description.lower()]
    assert len(raises) == 3, [b.description for b in understanding.beats]


def test_repetition_cardinality_sequence_language_merged_beat_not_split() -> None:
    """Peer round-6 blocker: a merged beat that genuinely stages BOTH impacts
    with sequence language ("buckles inward hard, then buckles inward
    harder") must NOT be forced to backfill a duplicate — the beat's prose
    stages the shared vocabulary twice, so its capacity is two."""
    message = (
        "Build a scene in Timeline in the Derelict Station environment reference sheet. "
        "The cargo door buckles inward. "
        "The cargo door buckles inward again, harder. "
        "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP."
    )
    llm_payload = {
        "scene_type": "suspense",
        "mood": "tense",
        "environment_name": "Derelict Station",
        "assets": [],
        "beats": [
            {"kind": "impact", "description": "The cargo door buckles inward hard, then buckles inward harder."},
        ],
        "reveals": [],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        message, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    buckling = [b for b in understanding.beats if "buckles" in b.description.lower()]
    assert len(buckling) == 1, [b.description for b in understanding.beats]


def test_consequence_realization_tolerates_paraphrase() -> None:
    """Peer round-6 blocker: realization is paraphrase-tolerant — an LLM beat
    that preserves the consequence with near-synonyms ("huge jagged opening"
    for "large jagged hole") must NOT trigger a duplicate backfill."""
    message = (
        "Build a Timeline scene in the Venture Corridor environment reference sheet. "
        "Suddenly, a concentrated red energy beam blasts through from the opposite side, "
        "violently blowing a large jagged hole through the door. "
        "30 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP."
    )
    llm_payload = {
        "scene_type": "action",
        "mood": "violent",
        "environment_name": "Venture Corridor",
        "assets": [],
        "beats": [
            {"kind": "impact", "description": "A concentrated red energy beam blasts a huge jagged opening through the door."},
        ],
        "reveals": [],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        message, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    beam_beats = [b for b in understanding.beats if "energy beam" in b.description.lower()]
    assert len(beam_beats) == 1, [b.description for b in understanding.beats]


def test_main_subject_round7_grammar_shapes() -> None:
    """Peer round-7 probes: participial-adjective plurals ("The battered
    doors slammed shut"), -ly adverbs after past-tense verbs ("collapsed
    violently"), leading prepositional phrases ("Without warning, …"),
    comma appositives with numbers, and verbless fragments (no fabricated
    subject)."""
    assert _main_subject("The battered doors slammed shut, hurling splinters.") == "The battered doors"
    assert _main_subject("The towers collapsed violently, sending dust everywhere.") == "The towers"
    assert _main_subject("Without warning, the winch tower tips sideways, sending a wave.") == "the winch tower"
    assert _main_subject("The tower, standing 12 meters tall, groans loudly.") == "The tower"
    assert _main_subject("As the alarm sounds, Mara runs for the exit, knocking crates aside.") == "Mara runs for the exit" or _main_subject("As the alarm sounds, Mara runs for the exit, knocking crates aside.") == "Mara"
    # Verbless fragment: no actor recoverable — must NOT fabricate one.
    assert _main_subject("A blinding flash of light, sending sparks.") == ""


def test_llm_near_duplicate_beats_deduped() -> None:
    """Peer round-7 LIVE blocker: the LLM emitted the Scene 3 beam beat twice
    differing only by the leading "Suddenly, " — both survived into the
    compiled ACTION. LLM beats that are identical after leading-adverb
    normalization must be deduped (first occurrence wins)."""
    message = (
        "Build a Timeline scene in the Venture Corridor environment reference sheet. "
        "Suddenly, a concentrated red energy beam blasts through from the opposite side, "
        "violently blowing a large jagged hole through the door. "
        "Hot fragments and sparks burst into the corridor. "
        "30 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP."
    )
    beam_a = "Suddenly, a concentrated red energy beam blasts through from the opposite side, violently blowing a large jagged hole through the door."
    beam_b = "A concentrated red energy beam blasts through from the opposite side, violently blowing a large jagged hole through the door."
    llm_payload = {
        "scene_type": "action",
        "mood": "violent",
        "environment_name": "Venture Corridor",
        "assets": [],
        "beats": [
            {"kind": "impact", "description": beam_a},
            {"kind": "impact", "description": beam_b},
            {"kind": "impact", "description": "Hot fragments and sparks burst into the corridor."},
        ],
        "reveals": [],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        message, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    beam_beats = [b for b in understanding.beats if "energy beam" in b.description.lower()]
    assert len(beam_beats) == 1, [b.description for b in understanding.beats]


def test_multiplicity_scoped_to_cluster_vocabulary() -> None:
    """Peer round-7 blocker: multiplicity language is action-scoped — "the
    door buckles while Mara raises her hand twice" claims two RAISES, not two
    buckles. Three staged buckles must all survive (backfilled), while the
    two raises are legitimately covered by the merged beat."""
    message = (
        "Build a scene in Timeline in the Derelict Station environment reference sheet. "
        "The door buckles inward. "
        "The door buckles inward again. "
        "The door buckles inward a third time. "
        "Mara raises her hand. "
        "Mara raises her hand again. "
        "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP."
    )
    llm_payload = {
        "scene_type": "suspense",
        "mood": "tense",
        "environment_name": "Derelict Station",
        "assets": [],
        "beats": [
            {"kind": "action", "description": "The door buckles while Mara raises her hand twice."},
        ],
        "reveals": [],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        message, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    descriptions = [b.description.lower() for b in understanding.beats]
    # All three staged buckles survive (the merged beat lacked "inward", so
    # the backfill re-stages each with its full detail).
    assert sum("inward" in d for d in descriptions) == 3, descriptions
    # The two raises are covered by the merged beat's "twice" — no backfill.
    assert sum("raises" in d for d in descriptions) == 1, descriptions


def test_consequence_realization_synonyms_bidirectional() -> None:
    """Peer round-7 blocker: synonym matching must work in BOTH directions —
    a source clause "huge jagged opening through the hatch" is realized by a
    beat saying "large jagged hole through the door"."""
    message = (
        "Build a Timeline scene in the Venture Corridor environment reference sheet. "
        "Suddenly, a concentrated red energy beam blasts through from the opposite side, "
        "violently blowing a huge jagged opening through the hatch. "
        "30 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP."
    )
    llm_payload = {
        "scene_type": "action",
        "mood": "violent",
        "environment_name": "Venture Corridor",
        "assets": [],
        "beats": [
            {"kind": "impact", "description": "A concentrated red energy beam blasts a large jagged hole through the door."},
        ],
        "reveals": [],
        "dialogue": [],
        "camera": {"shot_type": "", "movement": "", "framing": "", "target": "", "evolution": ""},
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        message, llm_fn=lambda _s, _u: json.dumps(llm_payload)
    )
    assert source == "llm"
    beam_beats = [b for b in understanding.beats if "energy beam" in b.description.lower()]
    assert len(beam_beats) == 1, [b.description for b in understanding.beats]


def test_camera_fields_strip_reference_declaration_language() -> None:
    """"Signal Kite prop reference sheet" is request chrome; the camera plan
    must carry asset names only (live Sample F leak regression)."""
    llm_payload = {
        "scene_type": "action",
        "mood": "expansive",
        "environment_name": "Canyon Crossing",
        "assets": [],
        "beats": [{"kind": "action", "description": "Jun launches the kite."}],
        "reveals": [],
        "dialogue": [],
        "camera": {
            "shot_type": "medium to wide",
            "movement": "rising with the kite",
            "framing": "starts on Jun",
            "target": "Jun Park then Signal Kite prop reference sheet then Canyon Crossing environment reference sheet",
            "evolution": "ground level to aerial",
        },
        "spatial": [],
        "continuity": [],
        "exclusions": [],
        "subtitle_policy": "",
        "opening_state": "",
        "end_state": "",
    }
    understanding, source, _ = extract_scene_understanding(
        "Build a scene in Timeline in the Canyon Crossing environment reference sheet with the "
        "Character reference of Jun Park and the Signal Kite prop reference sheet. Jun launches "
        "the kite. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.",
        llm_fn=lambda _s, _u: json.dumps(llm_payload),
    )
    assert source == "llm"
    assert understanding.camera.target == "Jun Park then Signal Kite then Canyon Crossing"
    assert "reference" not in understanding.camera.target.lower()


def test_fallback_cinematicizes_imperative_beats() -> None:
    """Deterministic path: creator imperatives become declarative staging —
    ACTION must not carry the instruction sentence verbatim."""
    message = (
        "Create a Timeline scene using the Neon Harbor environment reference sheet as the setting. "
        "ACTION: Rain falls on the docks. Hold for one second. A neon sign flickers awake. "
        "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP."
    )
    spec, intent = _build(message, [_ref("Neon Harbor", "#NeonHarbor", "environment")])
    action = intent.action_text
    assert "The shot holds for one second." in action
    assert "Hold for one second." not in action.replace("The shot holds for one second.", "")
    # Declarative event prose survives; instruction framing does not.
    assert "Rain falls on the docks." in action
    assert "reference sheet" not in action.lower()


def test_scene3_action_is_synthesized_not_copied() -> None:
    refs = _scene3_refs()
    spec, intent = _build(SCENE3_REQUEST, refs)
    assert intent.action_text
    assert intent.action_text != spec.source_user_prompt
    # The creator's instruction wrapper is gone; on-screen events remain.
    assert "For Scene 3" not in intent.action_text
    assert "I would like to create" not in intent.action_text
    assert "buckles" in intent.action_text.lower()
    assert "Where is the Adept?" in intent.action_text


# ---------------------------------------------------------------------------
# LLM path — stub llm_fn
# ---------------------------------------------------------------------------

_LLM_JSON = {
    "scene_type": "suspense_reveal",
    "purpose": "test",
    "mood": "tense",
    "environment_name": "Derelict Station",
    "assets": [{"name": "Mara Voss", "hinted_type": "character"}],
    "beats": [
        {"kind": "establish", "description": "The derelict corridor stretches into darkness.", "subjects": [], "camera": "slow push-in", "hold_seconds": None, "vfx": ""},
        {"kind": "reveal", "description": "Emergency lights snap on, revealing Mara Voss.", "subjects": ["Mara Voss"], "camera": "", "hold_seconds": None, "vfx": ""},
    ],
    "reveals": [{"subject": "Mara Voss", "hidden_until": "the emergency lights snap on", "reveal_order": ["silhouette", "full figure"], "condition": "do not reveal early"}],
    "dialogue": [],
    "camera": {"shot_type": "medium", "movement": "slow push-in", "framing": "medium", "target": "the corridor", "evolution": ""},
    "spatial": [],
    "continuity": ["same corridor throughout"],
    "exclusions": ["no extra characters"],
    "subtitle_policy": "none",
    "opening_state": "The derelict corridor stretches into darkness.",
    "end_state": "Mara Voss revealed.",
}


def test_llm_understanding_path_used_when_available() -> None:
    calls: list[tuple[str, str]] = []

    def stub_llm(system_prompt: str, user_prompt: str) -> str:
        calls.append((system_prompt, user_prompt))
        return json.dumps(_LLM_JSON)

    understanding, source, fallback_reason = extract_scene_understanding(
        SAMPLE_B, llm_fn=stub_llm, allow_llm=True
    )
    assert source == "llm"
    assert fallback_reason == ""
    assert len(calls) == 1
    assert understanding.scene_type == "suspense_reveal"
    assert understanding.reveals[0].subject == "Mara Voss"

    refs = [
        _ref("Mara Voss", "@MaraVoss", "character"),
        _ref("Derelict Station", "#DerelictStation", "environment"),
    ]
    spec = parse_scene_intent(SAMPLE_B, project_id="proj")
    intent = build_director_scene_intent(spec, refs, llm_fn=stub_llm, allow_llm=True)
    assert intent.understanding_source == "llm"
    assert intent.reveals[0].hidden_until == "the emergency lights snap on"
    assert intent.reveals[0].reveal_order == ["silhouette", "full figure"]
    assert intent.scene_beats[0].description == "The derelict corridor stretches into darkness."


def test_llm_garbage_falls_back_with_reason() -> None:
    def bad_llm(system_prompt: str, user_prompt: str) -> str:
        return "I cannot help with that."

    understanding, source, fallback_reason = extract_scene_understanding(
        SAMPLE_B, llm_fn=bad_llm, allow_llm=True
    )
    assert source == "fallback"
    assert fallback_reason
    # Fallback still produces a real breakdown.
    assert understanding.beats
    assert understanding.reveals


def test_llm_exception_falls_back() -> None:
    def exploding_llm(system_prompt: str, user_prompt: str) -> str:
        raise RuntimeError("provider offline")

    understanding, source, fallback_reason = extract_scene_understanding(
        SAMPLE_A, llm_fn=exploding_llm, allow_llm=True
    )
    assert source == "fallback"
    assert "provider offline" in fallback_reason
    assert understanding.beats


def test_precomputed_understanding_is_reused_not_reextracted() -> None:
    calls = 0

    def counting_llm(system_prompt: str, user_prompt: str) -> str:
        nonlocal calls
        calls += 1
        return json.dumps(_LLM_JSON)

    understanding, _, _ = extract_scene_understanding(SAMPLE_B, llm_fn=counting_llm, allow_llm=True)
    assert calls == 1
    refs = [
        _ref("Mara Voss", "@MaraVoss", "character"),
        _ref("Derelict Station", "#DerelictStation", "environment"),
    ]
    spec = parse_scene_intent(SAMPLE_B, project_id="proj")
    intent = build_director_scene_intent(
        spec, refs, understanding=understanding, understanding_source="llm", llm_fn=counting_llm
    )
    assert calls == 1, "understanding must be reused, not re-extracted"
    assert intent.understanding_source == "llm"


def test_compile_is_deterministic_layer_b_to_c() -> None:
    """The compiler never re-runs understanding: it reuses spec.director_intent."""
    refs = [
        _ref("Mara Voss", "@MaraVoss", "character"),
        _ref("Derelict Station", "#DerelictStation", "environment"),
    ]
    spec, intent = _build(SAMPLE_B, refs)
    first = compile_generator_prompt(spec, refs)
    second = compile_generator_prompt(spec, refs)
    assert first == second


# ---------------------------------------------------------------------------
# Parser laws
# ---------------------------------------------------------------------------

def test_parser_character_reference_of_pattern() -> None:
    spec = parse_scene_intent(SCENE3_REQUEST, project_id="proj")
    queries = {(q.query, q.expected_type) for q in spec.reference_queries}
    assert ("Cade O'Connor", "character") in queries
    assert ("Venture Corridor Scene", "environment") in queries


def test_parser_explicit_tags_and_setting() -> None:
    message = (
        "Create a Timeline scene with @MaraVoss and %SupplySled in #NeonHarbor. "
        "Use the Old Mill as the setting. 10 seconds, MiniMax H3, 21:9, 1.0 MP."
    )
    spec = parse_scene_intent(message, project_id="proj")
    by_name = {q.query: q.expected_type for q in spec.reference_queries}
    # Explicit tags de-camelCase into display-name queries.
    assert by_name.get("Mara Voss") == "character"
    assert by_name.get("Supply Sled") == "prop"
    assert by_name.get("Neon Harbor") == "environment"
    assert by_name.get("Old Mill") == "environment"


def test_parser_multi_batch_and_runtime_fields() -> None:
    spec = parse_scene_intent(SCENE3_REQUEST, project_id="proj")
    assert spec.duration_seconds == 30
    assert spec.batch_count == 2
    assert spec.aspect_ratio == "21:9"
    assert spec.megapixels == 1.0
    assert spec.generator_id == "minimax-h3"
    # Raw source preserved (newlines intact for section parsing).
    assert spec.source_user_prompt.strip().startswith("For Scene 3")


def test_validator_multibatch_semantics() -> None:
    spec = parse_scene_intent(SCENE3_REQUEST, project_id="proj")
    validate_scene_spec_against_generator(spec)  # 30s / 2 batches = 15s OK
    spec.batch_count = 1
    with pytest.raises(GeneratorValidationError):
        validate_scene_spec_against_generator(spec)  # 30s single batch rejected
    spec.batch_count = 3
    validate_scene_spec_against_generator(spec)  # 10s per batch OK


def test_merge_reference_queries_from_understanding() -> None:
    spec = parse_scene_intent(SAMPLE_A, project_id="proj")
    before = len(spec.reference_queries)
    merge_reference_queries(spec, [("Harbor Lighthouse", "prop"), ("Neon Harbor", "environment")])
    names = {q.query for q in spec.reference_queries}
    assert "Harbor Lighthouse" in names
    # Duplicate of an existing query is not added twice.
    assert len([q for q in spec.reference_queries if q.query == "Neon Harbor"]) == 1
    assert len(spec.reference_queries) == before + 1


def test_understanding_asset_mentions_require_corroboration() -> None:
    """Scenery descriptions must never become reference queries (fail-closed
    against chasing 'distant mountains' as an Environment Reference Sheet)."""
    from app.codirector.production.orchestrator import _corroborated_asset_mentions

    class _Asset:
        def __init__(self, name: str, hinted_type: str = ""):
            self.name = name
            self.hinted_type = hinted_type

    class _Understanding:
        assets = [
            _Asset("distant mountains", "environment"),  # scenery — not a reference
            _Asset("thick fog", "environment"),  # weather — not a reference
            _Asset("Mara Voss", "character"),  # proper noun in source
            _Asset("Salt Flats", "environment"),  # invoked as the setting
            _Asset("harbor lighthouse", "prop"),  # lowercase, but reference language
            _Asset("Mountains", "environment"),  # sentence-start capital only
        ]

    source = (
        "Build a scene in Timeline using the Salt Flats environment reference sheet as the setting, "
        "with the Character reference of Mara Voss. "
        "A slow aerial drift over the white flats at dawn, distant mountains on the horizon. "
        "Mountains frame the shot. Thick fog rolls in, thick fog everywhere. "
        "She checks the harbor lighthouse reference sheet before shooting."
    )
    merged = _corroborated_asset_mentions(_Understanding(), source)
    names = {name for name, _ in merged}
    assert "Mara Voss" in names
    assert "Salt Flats" in names
    assert "harbor lighthouse" in names  # corroborated by "reference sheet" window
    assert "distant mountains" not in names
    assert "thick fog" not in names
    assert "Mountains" not in names  # sentence-start capital is not a proper-noun invocation


# ---------------------------------------------------------------------------
# Retry law — follow-up reuses validated references + original context
# ---------------------------------------------------------------------------

@pytest.fixture()
def retry_db():
    import app.db as db_module
    import app.scene_references.models as _sr_models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db_module.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(db_module.Project(id="proj-retry", name="Retry Test"))
    session.commit()
    yield session
    session.close()


def _retry_refs() -> list[ResolvedReference]:
    return [
        _ref("Mara Voss", "@MaraVoss", "character"),
        _ref("Derelict Station", "#DerelictStation", "environment"),
    ]


def test_retry_reuses_context_and_references(retry_db, monkeypatch) -> None:
    from app.codirector.production import orchestrator as orch

    captured: list[dict] = []

    monkeypatch.setattr(
        orch,
        "resolve_project_references",
        lambda db, project_id, queries: [
            _ref(q.query, "@MaraVoss" if "mara" in q.query.lower() else "#DerelictStation", q.expected_type or "character")
            for q in queries
        ],
    )

    def fake_builder(db, spec, references, compiled_prompt, batch_prompts=None):
        captured.append(
            {
                "spec": spec,
                "references": list(references),
                "batch_prompts": list(batch_prompts or []),
            }
        )
        return ("scene-1", "shot-1", 0, "Shot 1")

    monkeypatch.setattr(orch, "create_or_update_shot_from_spec", fake_builder)

    first = orch.prepare_production_request(
        retry_db, project_id="proj-retry", message=SAMPLE_B, scene_id="scene-1", allow_llm=False
    )
    assert first.ok, first.error
    assert captured[0]["spec"].duration_seconds == 10

    # Follow-up edit: no references restated, no duration restated.
    revision = orch.prepare_production_request(
        retry_db,
        project_id="proj-retry",
        message="Actually make the corridor flicker with red emergency light instead.",
        allow_llm=False,
    )
    assert revision.ok, revision.error
    revised_spec = captured[1]["spec"]
    # References inherited from the validated first pass.
    assert {r.display_name for r in captured[1]["references"]} == {"Mara Voss", "Derelict Station"}
    # Duration + generator inherited.
    assert revised_spec.duration_seconds == 10
    assert revised_spec.generator_id == "minimax-h3"
    # Understanding input combines the ORIGINAL request with the revision.
    assert "Mara" in revised_spec.source_user_prompt
    assert "red emergency light" in revised_spec.source_user_prompt
    # Same scene/shot identity retained (no blank restart).
    assert revised_spec.scene_id == "scene-1"
    assert revised_spec.shot_id == "shot-1"


def test_retry_does_not_duplicate_bindings(retry_db) -> None:
    import app.db as db_module
    from app.codirector.production.timeline_builder import _attach_reference
    from app.scene_references import repository as ref_repo

    retry_db.add(
        db_module.Asset(
            id="asset-mara",
            project_id="proj-retry",
            tag="mara",
            kind="image",
            filename="mara-voss.png",
            path="mara-voss.png",
        )
    )
    retry_db.commit()

    ref = _ref("Mara Voss", "@MaraVoss", "character")
    ref.asset_id = "asset-mara"
    first = _attach_reference(retry_db, project_id="proj-retry", scene_id="scene-1", ref=ref)
    second = _attach_reference(retry_db, project_id="proj-retry", scene_id="scene-1", ref=ref)
    assert first["binding_id"] == second["binding_id"]
    bindings = ref_repo.list_bindings(retry_db, "proj-retry", scope_type="scene", scope_id="scene-1")
    assert len(bindings) == 1
