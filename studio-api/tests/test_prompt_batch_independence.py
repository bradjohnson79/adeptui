"""Timed Prompt lane is the derived window projection of batch-owned prompts.

12B law (Timeline batch architecture): every batch owns its own complete
window-scoped execution prompt. The visible Timed Prompt lane shows one
window-scoped entry per batch (Scene 12B shows 0-15 and 15-30). A multi-batch
scene must never collapse into a single full-scene Timed Prompt (the "one
scene / one prompt" rewrite caused the Take N regression), and a single-batch
scene never subdivides its Timed Prompt except via explicit temporal regions.
"""

from __future__ import annotations

import pytest

from app.codirector.production.prompt_compiler import compile_generator_prompt
from app.codirector.production.timed_regions import parse_explicit_timed_regions
from app.director_timeline_w46.migration_reconcile import project_prompts_to_legacy
from app.director_timeline_w46.contracts import SceneTimelineMaster

from app.db import SessionLocal

from tests.test_scene_production_persistence import (
    _approve_environment,
    _create_project,
    _load_master,
    _prepare,
    _seed_character,
)


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _timed(master: SceneTimelineMaster) -> list[dict]:
    return project_prompts_to_legacy(master)


def test_explicit_timed_regions_need_two_or_more() -> None:
    assert parse_explicit_timed_regions("30 seconds, 2 batches") == []
    regions = parse_explicit_timed_regions(
        "0-10: character waits by door\n10-20: character runs\n20-30: explosion"
    )
    assert len(regions) == 3
    assert regions[0].start == 0
    assert regions[2].end == 30
    assert "explosion" in regions[2].text


def test_every_batch_owns_its_window_prompt(client, db_session) -> None:
    cases = (
        ("Ten One", "10 seconds, 1 batch", 10.0, 1),
        ("Thirty Two", "30 seconds, 2 batches", 30.0, 2),
        ("Thirty Three", "30 seconds, 3 batches", 30.0, 2),  # P2+: creator N-batches non-authoritative; H3→2×15
    )
    for name, runtime, duration, batches in cases:
        project_id = _create_project(client, name)
        _approve_environment(client, project_id, "Salt Flats", "salt_flats")
        prepared = _prepare(
            db_session,
            project_id,
            "Create a Timeline scene using the Salt Flats environment reference sheet as the setting. "
            f"A slow aerial drift over the white flats. No characters. {runtime}, MiniMax H3, 21:9, 1.0 MP.",
        )
        assert prepared.ok, prepared.error
        assert prepared.spec.batch_count == batches
        assert prepared.spec.duration_seconds == pytest.approx(duration)
        master = _load_master(db_session, project_id, prepared.scene_id)
        production = [
            b
            for b in master.batchBlocks
            if (b.migrationMetadata or {}).get("sourceProductionRequestId")
        ]
        assert len(production) == batches
        timed = _timed(master)
        assert len(timed) == batches, f"{runtime}: expected {batches} window prompt(s), got {len(timed)}"
        # One window-scoped entry per batch; windows tile the scene.
        assert timed[0]["start"] == pytest.approx(0.0)
        assert timed[-1]["start"] + timed[-1]["length"] == pytest.approx(duration)
        for entry in timed:
            assert entry["text"].strip(), "every batch owns its own non-empty prompt"
        if batches > 1:
            assert timed[0]["text"] != timed[-1]["text"], "Batch N owns BatchPrompt[N]"
        # Master segments are batch-local windows, never the full scene recipe.
        for batch in production:
            for seg in batch.promptSegments:
                assert seg.start == pytest.approx(0.0)
                assert float(seg.length) <= duration / batches + 1e-6


def test_explicit_regions_single_batch_create_lane_regions(client, db_session) -> None:
    project_id = _create_project(client, "Explicit Regions Single")
    _approve_environment(client, project_id, "Salt Flats", "salt_flats")
    prepared = _prepare(
        db_session,
        project_id,
        "Create a Timeline scene using the Salt Flats environment reference sheet as the setting. "
        "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.\n"
        "0-4: character waits by door\n"
        "4-10: explosion",
    )
    assert prepared.ok, prepared.error
    assert prepared.spec.batch_count == 1
    master = _load_master(db_session, project_id, prepared.scene_id)
    production = [
        b
        for b in master.batchBlocks
        if (b.migrationMetadata or {}).get("sourceProductionRequestId")
    ]
    assert len(production) == 1
    timed = _timed(master)
    assert len(timed) == 2
    texts = " ".join(item["text"] for item in timed).lower()
    assert "waits" in texts and "explosion" in texts


def test_compile_single_scene_prompt_not_joined_windows() -> None:
    from app.codirector.production.intent_parser import parse_scene_intent
    from app.codirector.production.contracts import (
        CameraPlan,
        DirectorSceneIntent,
        ResolvedReference,
        SceneBeat,
        SceneIntentEnvironment,
    )

    spec = parse_scene_intent(
        "Build a Timeline scene. 30 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP.",
        project_id="proj",
    )
    spec.director_intent = DirectorSceneIntent(
        scene_type="establishing",
        environment=SceneIntentEnvironment(name="Salt Flats", tag="#SaltFlats", verified=True),
        scene_beats=[SceneBeat(index=0, kind="establish", description="Aerial drift over the flats.")],
        action_text="Aerial drift over the flats.",
        camera_plan=CameraPlan(shot_type="wide", movement="aerial drift"),
    )
    spec.duration_seconds = 30.0
    spec.batch_count = 2
    spec.generator_id = "minimax-h3"
    refs = [
        ResolvedReference(
            status="found",
            query="Salt Flats",
            expected_type="environment",
            display_name="Salt Flats",
            asset_type="environment",
            canonical_tag="#SaltFlats",
            verification="found",
        )
    ]
    prompt = compile_generator_prompt(spec, refs)
    assert "story seconds" not in prompt
    assert "#SaltFlats" in prompt
