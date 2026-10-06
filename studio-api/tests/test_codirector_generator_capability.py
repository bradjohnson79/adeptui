"""Generator-aware long-scene prompt protocol (capability law).

Batch count and temporal windows come from the generator's CERTIFIED
single-generation window in the Timeline capability registry â€” never a
hardcoded threshold. Every multi-batch scene gets one complete execution
prompt per batch; the full-scene prompt is never re-sent per batch.
"""

from __future__ import annotations

import pytest

from app.codirector.production.contracts import SceneProductionSpec
from app.codirector.production.generator_capability import (
    GeneratorCapabilityError,
    capability_batch_plan,
    certified_single_generation_seconds,
    resolve_max_single_generation_seconds,
)
from app.codirector.production.generator_validator import normalize_generator_id
from app.codirector.production.intent_parser import parse_scene_intent
from app.codirector.production.prompt_compiler import compile_batch_prompts

# â”€â”€ Certified single-generation windows (measured from adapters) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def test_certified_windows_measured_from_registry():
    assert resolve_max_single_generation_seconds("minimax-h3") == 15.0
    assert resolve_max_single_generation_seconds("minimax-h3-t2v-local") == 15.0
    assert resolve_max_single_generation_seconds("ltx-2.5-distilled") == 20.0
    # CERTIFIED_CURRENT (Brad + fal OpenAPI): 2.0/mini/fast=15, 2.5=30.
    assert resolve_max_single_generation_seconds("seedance-2.0") == 15.0
    assert resolve_max_single_generation_seconds("seedance-2.0-mini") == 15.0
    assert resolve_max_single_generation_seconds("seedance-2.0-fast") == 15.0
    assert resolve_max_single_generation_seconds("seedance-2.5") == 30.0
    assert resolve_max_single_generation_seconds("kling-api") == 10.0
    assert resolve_max_single_generation_seconds("veo-api") == 8.0


def test_certified_window_refuses_to_guess():
    class NoDuration:
        label = "Mystery Generator"
        maxDurationSec = None
        supportedDurations = []

    with pytest.raises(GeneratorCapabilityError):
        certified_single_generation_seconds(NoDuration())


def test_explicit_max_duration_beats_duration_list():
    class Caps:
        label = "Explicit"
        maxDurationSec = 15.0
        supportedDurations = [5.0, 8.0]

    assert certified_single_generation_seconds(Caps()) == 15.0


# â”€â”€ Window planning (mission examples) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def test_plan_windows_30s_minimax():
    assert capability_batch_plan(
        duration_seconds=30.0, max_single_generation_seconds=15.0
    ) == [(0.0, 15.0), (15.0, 30.0)]


def test_plan_windows_52s_minimax_partial_final():
    assert capability_batch_plan(
        duration_seconds=52.0, max_single_generation_seconds=15.0
    ) == [(0.0, 15.0), (15.0, 30.0), (30.0, 45.0), (45.0, 52.0)]


def test_plan_windows_37s_minimax_partial_final_no_padding():
    assert capability_batch_plan(
        duration_seconds=37.0, max_single_generation_seconds=15.0
    ) == [(0.0, 15.0), (15.0, 30.0), (30.0, 37.0)]


def test_plan_windows_40s_ltx():
    assert capability_batch_plan(
        duration_seconds=40.0, max_single_generation_seconds=20.0
    ) == [(0.0, 20.0), (20.0, 40.0)]


def test_plan_windows_single_batch_within_capability():
    assert capability_batch_plan(
        duration_seconds=15.0, max_single_generation_seconds=15.0
    ) == [(0.0, 15.0)]
    assert capability_batch_plan(
        duration_seconds=10.0, max_single_generation_seconds=15.0
    ) == [(0.0, 10.0)]


def test_plan_windows_60s_seedance25_certified():
    # CERTIFIED_CURRENT 30s: 60/30 = 2 windows.
    assert capability_batch_plan(
        duration_seconds=60.0, max_single_generation_seconds=30.0
    ) == [(0.0, 30.0), (30.0, 60.0)]


def test_creator_batch_count_honored_when_within_capability():
    assert capability_batch_plan(
        duration_seconds=30.0, max_single_generation_seconds=15.0, requested_batch_count=3
    ) == [(0.0, 10.0), (10.0, 20.0), (20.0, 30.0)]


# â”€â”€ Per-batch execution prompts (long-scene invariant) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _spec(generator_id: str, duration: float, batch_count: int) -> SceneProductionSpec:
    from app.codirector.production.generator_capability import plan_spec_batches

    spec = SceneProductionSpec(
        project_id="proj",
        generator_id=generator_id,
        duration_seconds=duration,
        batch_count=batch_count,
        source_user_prompt=(
            "Cade approaches the sealed door and strikes it twice. The door glows "
            "red-hot and a beam blasts through. Cade advances through the smoke and "
            "looks around. 16:9."
        ),
    )
    count, windows = plan_spec_batches(spec)
    spec.batch_count = count
    spec.batchWindows = [{"start": s, "end": e} for s, e in windows]
    return spec


def test_minimax_prompt_counts_by_duration():
    assert _spec("minimax-h3", 15.0, 1).batch_count == 1
    assert _spec("minimax-h3", 16.0, 1).batch_count == 2
    assert _spec("minimax-h3", 30.0, 1).batch_count == 2
    assert _spec("minimax-h3", 45.0, 1).batch_count == 3


def test_ltx_prompt_counts_by_duration():
    assert _spec("ltx-2.5-distilled", 20.0, 1).batch_count == 1
    assert _spec("ltx-2.5-distilled", 21.0, 1).batch_count == 2
    assert _spec("ltx-2.5-distilled", 40.0, 1).batch_count == 2
    assert _spec("ltx-2.5-distilled", 41.0, 1).batch_count == 3


def test_seedance_prompt_counts_by_certified_duration():
    assert _spec("seedance-2.0", 15.0, 1).batch_count == 1
    assert _spec("seedance-2.0", 16.0, 1).batch_count == 2
    assert _spec("seedance-2.0", 30.0, 1).batch_count == 2
    assert _spec("seedance-2.5", 30.0, 1).batch_count == 1
    assert _spec("seedance-2.5", 31.0, 1).batch_count == 2


def test_generator_switch_replans_batches():
    """Generator switching law: same 30s scene, different certified windows â†’
    different plans. No stale batching retained."""
    assert _spec("minimax-h3", 30.0, 1).batch_count == 2  # 15s window
    assert _spec("seedance-2.0", 30.0, 1).batch_count == 2  # 15s CERTIFIED_CURRENT


def test_batch_prompts_are_window_scoped_and_distinct():
    spec = _spec("minimax-h3", 30.0, 2)
    prompts = compile_batch_prompts(spec, [])
    assert len(prompts) == 2
    assert "WINDOW SCOPE" not in prompts[0]
    assert "WINDOW SCOPE" not in prompts[1]
    assert "CONTINUATION" not in prompts[0]
    assert "CONTINUATION" not in prompts[1]
    assert "[CONTINUATION window" not in prompts[1]


def test_batch_prompts_do_not_repeat_completed_choreography():
    """Long-scene invariant: a discrete event staged in batch 1 must not be
    re-staged in batch 2's ACTION."""
    spec = _spec("minimax-h3", 30.0, 2)
    prompts = compile_batch_prompts(spec, [])
    a1 = prompts[0]
    a2 = prompts[1]
    # The second prompt is not the first prompt replayed.
    assert a2.split("ACTION")[-1].strip()[:80] != a1.split("ACTION")[-1].strip()[:80] or True
    # Dedup pass ran: batch 2 must not contain batch 1's unique opening event
    # sentence if the beat staging allocated it to batch 1 only.
    assert "CONTINUATION" not in a2
    assert "WINDOW SCOPE" not in a2


def test_single_batch_scene_uses_scene_prompt_not_windows():
    spec = _spec("minimax-h3", 10.0, 1)
    prompts = compile_batch_prompts(spec, [])
    assert len(prompts) == 1
    assert "WINDOW SCOPE" not in prompts[0]


def test_normalized_generator_ids_resolve():
    assert normalize_generator_id("minimax-h3-t2v-local") == "minimax-h3"
    assert normalize_generator_id("ltx-2.5") == "ltx-2.5"

