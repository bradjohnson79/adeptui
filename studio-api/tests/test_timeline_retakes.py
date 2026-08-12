"""Timeline Re-take take registry — baseline, alternate, no ghost takes."""

from __future__ import annotations

import pytest

from app.timeline_retakes import store


@pytest.fixture()
def retake_tmp(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(store.settings, "data_dir", data)
    return data


def test_baseline_and_alternate_preserve_take1(retake_tmp):
    shot = store.ensure_baseline_take(
        "proj-fs",
        shot_id="shot-1",
        scene_id="scene-1",
        asset_id="asset-1",
        job_id="job-1",
        prompt="bottle push-in",
    )
    t1 = shot["takes"][0]["takeId"]
    shot2 = store.add_alternate_take(
        "proj-fs",
        shot_id="shot-1",
        source_take_id=t1,
        asset_id="asset-2",
        job_id="job-2",
        prompt="bottle push-in",
        delta_instruction="slower push-in, stronger condensation",
        activate=True,
    )
    assert len(shot2["takes"]) == 2
    assert shot2["takes"][0]["takeId"] == t1
    assert shot2["takes"][1]["retake"] is True
    assert shot2["takes"][1]["sourceTakeId"] == t1
    assert shot2["takes"][1]["provenance"]["apiUsed"] is False
    assert shot2["takes"][1]["provenance"]["ltxUsed"] is False
    assert shot2["activeTakeId"] == shot2["takes"][1]["takeId"]
    # Switch back to Take 1
    shot3 = store.set_active_take("proj-fs", "shot-1", t1)
    assert shot3["activeTakeId"] == t1
    assert len(shot3["takes"]) == 2
    assert any(h.get("reversible") for h in shot3["editHistory"])


def test_cancelled_provenance_rejected(retake_tmp):
    shot = store.ensure_baseline_take(
        "proj-fs2",
        shot_id="shot-1",
        scene_id="scene-1",
        asset_id="a",
        job_id="j",
        prompt="p",
    )
    t1 = shot["takes"][0]["takeId"]
    with pytest.raises(ValueError, match="Cancelled"):
        store.add_alternate_take(
            "proj-fs2",
            shot_id="shot-1",
            source_take_id=t1,
            asset_id=None,
            job_id="cancelled-job",
            prompt="p",
            delta_instruction="x",
            provenance={"status": "cancelled"},
        )
