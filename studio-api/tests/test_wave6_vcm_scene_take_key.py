"""WAVE 6 — VCM key prefers SceneTake stk_ over per-batch take_*."""

from __future__ import annotations

from types import SimpleNamespace

from app.codirector.verified_continuity_memory import resolve_continuity_keys_from_batch


def test_vcm_key_prefers_scene_take_stk_over_batch_candidate():
    batch0 = SimpleNamespace(currentTakeId="take_aaa", activeTakeId="take_aaa", order=0)
    batch1 = SimpleNamespace(currentTakeId="take_bbb", activeTakeId="take_bbb", order=1)
    master = SimpleNamespace(
        revision=1,
        activeSceneTakeId="stk_385b2e1d32a1",
        currentSceneTakeId="stk_385b2e1d32a1",
    )
    k0 = resolve_continuity_keys_from_batch(
        project_id="p", scene_id="s", batch=batch0, master=master
    )
    k1 = resolve_continuity_keys_from_batch(
        project_id="p", scene_id="s", batch=batch1, master=master
    )
    assert k0["take_id"] == "stk_385b2e1d32a1"
    assert k1["take_id"] == "stk_385b2e1d32a1"
    assert k0["batch_index"] == 0
    assert k1["batch_index"] == 1


def test_vcm_key_falls_back_to_batch_when_no_scene_take():
    batch = SimpleNamespace(currentTakeId="take_only", activeTakeId=None, order=0)
    master = SimpleNamespace(revision=2, activeSceneTakeId=None, currentSceneTakeId=None)
    k = resolve_continuity_keys_from_batch(
        project_id="p", scene_id="s", batch=batch, master=master
    )
    assert k["take_id"] == "take_only"
