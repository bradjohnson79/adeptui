"""Systems P5 — generator switch mints new SceneTake; old stk_ not live VCM key."""

from __future__ import annotations

from app.director_timeline_w46.contracts import BatchBlock, DurationState, SceneTake, SceneTimelineMaster
from app.director_timeline_w46.scene_takes import (
    begin_execution_revision,
    enforce_execution_boundary_if_topology_changed,
    window_execution_fingerprint,
)
from app.codirector.verified_continuity_memory import resolve_continuity_keys_from_batch


def _batch(bid: str, order: int) -> BatchBlock:
    return BatchBlock(
        id=bid,
        sceneId="sc1",
        order=order,
        status="Draft",
        duration=DurationState(plannedDuration=15.0),
    )


def test_fingerprint_tracks_generator_and_batch_ids():
    a = SceneTimelineMaster(sceneGeneratorId="minimax-h3", batchBlocks=[_batch("b0", 0), _batch("b1", 1)])
    b = SceneTimelineMaster(sceneGeneratorId="ltx-2.5", batchBlocks=[_batch("b0", 0), _batch("b1", 1)])
    c = SceneTimelineMaster(sceneGeneratorId="minimax-h3", batchBlocks=[_batch("b0", 0), _batch("b2", 1)])
    assert window_execution_fingerprint(a) != window_execution_fingerprint(b)
    assert window_execution_fingerprint(a) != window_execution_fingerprint(c)
    assert window_execution_fingerprint(a) == window_execution_fingerprint(
        SceneTimelineMaster(sceneGeneratorId="minimax-h3", batchBlocks=[_batch("b0", 0), _batch("b1", 1)])
    )


def test_generator_switch_mints_new_stk_and_severs_vcm_key():
    old = SceneTake(id="stk_olddeadbeef", label="A", letterIndex=1, status="ready")
    master = SceneTimelineMaster(
        sceneGeneratorId="minimax-h3",
        batchBlocks=[_batch("b0", 0)],
        sceneTakes=[old],
        currentSceneTakeId=old.id,
        activeSceneTakeId=None,
    )
    prev = master.model_copy(deep=True)
    master.sceneGeneratorId = "ltx-2.5"
    for b in master.batchBlocks:
        b.generatorId = "ltx-2.5"
    minted = enforce_execution_boundary_if_topology_changed(prev, master, reason="generator_switch")
    assert minted is not None
    assert minted.id != old.id
    assert minted.id.startswith("stk_")
    assert master.currentSceneTakeId == minted.id
    assert master.activeSceneTakeId is None
    assert (minted.generationSnapshot or {}).get("supersedesSceneTakeId") == old.id
    assert (minted.generationSnapshot or {}).get("invalidatesContinuityChain") is True
    keys = resolve_continuity_keys_from_batch(
        project_id="p1", scene_id="sc1", master=master, batch=master.batchBlocks[0]
    )
    assert keys["take_id"] == minted.id
    assert keys["take_id"] != old.id


def test_unchanged_topology_does_not_mint():
    old = SceneTake(id="stk_keep", label="A", letterIndex=1, status="ready")
    master = SceneTimelineMaster(
        sceneGeneratorId="minimax-h3",
        batchBlocks=[_batch("b0", 0)],
        sceneTakes=[old],
        currentSceneTakeId=old.id,
    )
    prev = master.model_copy(deep=True)
    master.turboLora = True  # non-topology
    assert enforce_execution_boundary_if_topology_changed(prev, master, reason="noop") is None
    assert master.currentSceneTakeId == old.id


def test_begin_execution_revision_direct():
    master = SceneTimelineMaster(
        sceneGeneratorId="minimax-h3",
        batchBlocks=[_batch("b0", 0)],
        sceneTakes=[SceneTake(id="stk_a", label="A", letterIndex=1, status="ready")],
        currentSceneTakeId="stk_a",
    )
    t = begin_execution_revision(master, reason="generator_switch")
    assert master.currentSceneTakeId == t.id
    assert len(master.sceneTakes) == 2

def test_cd_handoff_flags_match_mint_contract():
    """CD build_generator_switch_handoff requiresNewSceneTake → Systems mint path."""
    from app.codirector.production.orchestrator import build_generator_switch_handoff

    handoff = build_generator_switch_handoff(
        previous_generator_id="minimax-h3",
        new_generator_id="ltx-2.5",
        duration_seconds=30.0,
        previous_windows=[{"start": 0.0, "end": 15.0}, {"start": 15.0, "end": 30.0}],
    )
    assert handoff["requiresNewSceneTake"] is True
    assert handoff["requiresRevisionBump"] is True
    old = SceneTake(id="stk_oldchain", label="A", letterIndex=1, status="ready")
    master = SceneTimelineMaster(
        sceneGeneratorId="ltx-2.5",
        batchBlocks=[_batch("b0", 0)],
        sceneTakes=[old],
        currentSceneTakeId=old.id,
    )
    prev = SceneTimelineMaster(
        sceneGeneratorId="minimax-h3",
        batchBlocks=[_batch("b0", 0)],
        sceneTakes=[old],
        currentSceneTakeId=old.id,
    )
    minted = begin_execution_revision(master, reason=str(handoff["reason"]))
    assert minted.id != old.id
    assert master.currentSceneTakeId == minted.id
    assert master.activeSceneTakeId is None
    keys = resolve_continuity_keys_from_batch(
        project_id="p1", scene_id="sc1", master=master, batch=master.batchBlocks[0]
    )
    assert keys["take_id"] == minted.id
