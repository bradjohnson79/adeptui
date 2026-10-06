"""Between-batch Preview chrome: staged Queued is live; leftover Queued is not."""

from types import SimpleNamespace

from app.director_timeline_w46.scene_render_progress import derive_scene_render_progress


def _batch(**kwargs):
    defaults = {
        "id": "b",
        "order": 0,
        "status": "Draft",
        "label": "Batch",
        "approvedClip": None,
        "generationJobs": [],
        "activeJobId": None,
        "pendingSnapshotId": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_leftover_queued_without_snapshot_is_not_live():
    master = SimpleNamespace(
        batchBlocks=[
            _batch(id="b1", order=0, status="Approved", approvedClip=SimpleNamespace(assetId="a1")),
            _batch(id="b2", order=1, status="Queued"),
        ]
    )
    derived = derive_scene_render_progress(master)
    assert derived["queueActive"] is False
    assert derived["phase"] == "idle"


def test_staged_next_batch_is_preparing():
    master = SimpleNamespace(
        batchBlocks=[
            _batch(id="b1", order=0, status="Approved", approvedClip=SimpleNamespace(assetId="a1")),
            _batch(id="b2", order=1, status="Queued", pendingSnapshotId="snap-2"),
            _batch(id="b3", order=2, status="Queued", pendingSnapshotId="snap-3"),
        ]
    )
    derived = derive_scene_render_progress(master)
    assert derived["queueActive"] is True
    assert derived["phase"] == "preparing"
    assert derived["activeBatchIndex"] == 2
    assert "Preparing" in str(derived["statusLabel"])
