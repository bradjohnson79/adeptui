"""Timeline V2 F2: a newly planned piece invalidates the shot's stitch.

Live cert (theme_walk/timeline_v2_full_remediation/findings_continue_shot.json):
after a third segment completed via Continue Shot the shot still carried the OLD
2-segment stitch with stitchStatus='ready', and the default monitor prefers the
stitch asset -- so the preview showed a stale composition.

Required behaviour: planning/submitting a segment (Generate or Continue) marks the
shot's stitch stale, the next stitch rebuilds it from every completed segment, and
a stitch failure never removes segments.
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from app.db import Asset, Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import MiniMaxH3I2VLocalAdapter
from app.director_timeline_w46.generation.contracts import (
    NormalizedJobStatus,
    NormalizedJobSubmission,
    TimelineGenerationResult,
)
from app.film_timeline import orchestrator
from app.film_timeline.contracts import ReferenceAsset, Segment
from app.film_timeline.stitch import stitch_shot
from app.film_timeline.store import require_film, save_film
from app.media_clip import probe_video_duration
from app.runtime_session import current_runtime_session_id

H3 = "minimax-h3-i2v-local"


@pytest.fixture()
def scene():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pid, sid = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Project(id=pid, name="Timeline stitch staleness", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene",
            prompt="prompt",
            duration_sec=15.0,
            aspect_ratio="16:9",
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


@pytest.fixture()
def h3(monkeypatch):
    """Real H3 capabilities/validate; submit never reaches Comfy."""
    adapter = MiniMaxH3I2VLocalAdapter()
    calls: list = []

    def _submit(request):
        calls.append(request)
        return NormalizedJobSubmission(
            generatorId=request.generatorId,
            providerJobId=None,
            queueJobId=f"queue-{request.batchBlockId}",
        )

    def _status(job):
        return NormalizedJobStatus(
            internalJobId=job.internalJobId,
            generatorId=job.generatorId,
            status="running",
            apiUsed=False,
        )

    monkeypatch.setattr(adapter, "submit", _submit)
    monkeypatch.setattr(adapter, "get_status", _status)
    monkeypatch.setattr(orchestrator, "_adapter", lambda generator_id: adapter)
    # No Omni / frame extraction in a unit test: continuity is not this contract.
    monkeypatch.setattr(
        "app.film_timeline.continuity.ensure_segment_continuity",
        lambda db, project_id, scene_id, shot, segment: {},
    )
    return calls


def _clip(tmp_path: Path, name: str, color: str) -> Path:
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    assert ffmpeg, "ffmpeg is required for the Timeline stitch contract"
    out = tmp_path / f"{name}.mp4"
    subprocess.check_call(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=64x64:d=1:r=24",
            "-pix_fmt",
            "yuv420p",
            str(out),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return out


def _asset(db, project_id: str, path: Path) -> str:
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id=project_id,
            tag="segment",
            kind="video",
            filename=path.name,
            path=str(path),
        )
    )
    db.commit()
    return asset_id


def _shot(db, pid: str, sid: str, shot_id: str):
    film = require_film(db, pid, sid)
    return film, next(item for item in film.shots if item.id == shot_id)


def test_continue_marks_the_stitch_stale_and_the_next_stitch_rebuilds_it(scene, h3, tmp_path):
    db, pid, sid = scene
    created = orchestrator.create_shot(db, pid, sid, name="Shot 01", duration_sec=15.0, generator_id=H3)
    shot_id = created["shot"]["id"]
    film, shot = _shot(db, pid, sid, shot_id)
    shot.state.references = [
        ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")
    ]
    first_asset = _asset(db, pid, _clip(tmp_path, "one", "red"))
    second_asset = _asset(db, pid, _clip(tmp_path, "two", "green"))
    shot.segments = [
        Segment(order=0, durationSec=1.0, requestedDurationSec=1.0, timedPrompt="one", generatorId=H3, status="completed", assetId=first_asset),
        Segment(order=1, durationSec=1.0, requestedDurationSec=1.0, timedPrompt="two", generatorId=H3, status="completed", assetId=second_asset),
    ]
    shot.state.segmentIds = [segment.id for segment in shot.segments]
    save_film(db, pid, sid, film)

    # A ready 2-segment stitch exists before Continue -- the live-cert starting point.
    stitched = stitch_shot(db, pid, sid, shot_id)
    assert stitched["ok"] is True, stitched
    film, shot = _shot(db, pid, sid, shot_id)
    old_stitch = shot.state.stitchAssetId
    assert shot.state.stitchStatus == "ready"
    assert old_stitch
    assert abs(probe_video_duration(Path(db.get(Asset, old_stitch).path)) - 2.0) < 0.35

    result = orchestrator.continue_shot(db, pid, sid, shot_id, duration_sec=3.0, timed_prompt="three")
    assert result["ok"] is True, result
    film, shot = _shot(db, pid, sid, shot_id)
    ordered = sorted(shot.segments, key=lambda item: item.order)
    assert len(ordered) == 3
    assert [segment.status for segment in ordered] == ["completed", "completed", "queued"]
    # F2: the previous composition is no longer the current shot.
    assert shot.state.stitchStatus == "stale"
    assert shot.state.stitchAssetId != old_stitch

    # Finish the new piece, then the next stitch must cover all three segments.
    third_asset = _asset(db, pid, _clip(tmp_path, "three", "blue"))
    film, shot = _shot(db, pid, sid, shot_id)
    newest = max(shot.segments, key=lambda item: item.order)
    newest.status = "completed"
    newest.assetId = third_asset
    save_film(db, pid, sid, film)

    rebuilt = stitch_shot(db, pid, sid, shot_id)
    assert rebuilt["ok"] is True, rebuilt
    film, shot = _shot(db, pid, sid, shot_id)
    assert shot.state.stitchStatus == "ready"
    assert shot.state.stitchError is None
    assert shot.state.stitchAssetId and shot.state.stitchAssetId != old_stitch
    rebuilt_asset = db.get(Asset, shot.state.stitchAssetId)
    assert rebuilt_asset is not None and Path(rebuilt_asset.path).exists()
    # Three one-second pieces -> the stitched take covers all three, not the old two.
    assert abs(probe_video_duration(Path(rebuilt_asset.path)) - 3.0) < 0.35
    assert [segment.status for segment in shot.segments] == ["completed", "completed", "completed"]


def test_new_generate_marks_the_stitch_stale(scene, h3):
    db, pid, sid = scene
    created = orchestrator.create_shot(db, pid, sid, name="Shot 01", duration_sec=15.0, generator_id=H3)
    shot_id = created["shot"]["id"]
    film, shot = _shot(db, pid, sid, shot_id)
    shot.state.references = [
        ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")
    ]
    # A leftover ready stitch from an earlier composition must not survive a new plan.
    shot.state.stitchAssetId = "stitch-from-before"
    shot.state.stitchStatus = "ready"
    save_film(db, pid, sid, film)

    generated = orchestrator.generate_shot(db, pid, sid, shot_id, timed_prompt="wide")
    assert generated["ok"] is True, generated
    film, shot = _shot(db, pid, sid, shot_id)
    assert shot.state.stitchStatus == "stale"
    assert shot.state.stitchAssetId in (None, "")
    assert len(h3) == 1


def test_stitch_failure_leaves_the_segments_in_place(scene, h3, tmp_path):
    """The existing contract F2 must not weaken: a failed stitch keeps every segment."""
    db, pid, sid = scene
    created = orchestrator.create_shot(db, pid, sid, name="Shot 01", duration_sec=15.0, generator_id=H3)
    shot_id = created["shot"]["id"]
    film, shot = _shot(db, pid, sid, shot_id)
    shot.segments = [
        Segment(order=0, durationSec=1.0, requestedDurationSec=1.0, timedPrompt="one", generatorId=H3, status="completed", assetId="asset-missing-1"),
        Segment(order=1, durationSec=1.0, requestedDurationSec=1.0, timedPrompt="two", generatorId=H3, status="completed", assetId="asset-missing-2"),
    ]
    save_film(db, pid, sid, film)

    failed = stitch_shot(db, pid, sid, shot_id)
    assert failed["ok"] is False
    assert failed["error"] == "SOURCE_ASSET_MISSING"
    film, shot = _shot(db, pid, sid, shot_id)
    assert shot.state.stitchStatus == "failed"
    assert [segment.status for segment in shot.segments] == ["completed", "completed"]


# ---------------------------------------------------------------------------
# B-F2: a stitch may never be taken (or left 'ready') while the composition can
# still change. Live state on shot_ed8c484c22a3: three completed pieces
# (15+5+5s, 1728x736) with stitchStatus='ready' pointing at asset 69ea756a --
# 20.008s / 480 frames, i.e. segments 0+1 only -- created ~15 minutes BEFORE the
# re-taken piece a4fc04cf. _maybe_stitch had re-stitched while the re-taken piece
# was active (stitchStatus was already stale from the re-take start), stitch_shot
# set 'ready' unconditionally, and the completion transition never invalidated it.
# ---------------------------------------------------------------------------


@pytest.fixture()
def h3_completable(monkeypatch):
    """Real H3 capabilities/validate; the stub job completes on demand."""

    adapter = MiniMaxH3I2VLocalAdapter()
    calls: list = []
    job = {"status": "running", "assetId": ""}

    def _submit(request):
        calls.append(request)
        return NormalizedJobSubmission(
            generatorId=request.generatorId,
            providerJobId=None,
            queueJobId=f"queue-{request.batchBlockId}",
        )

    def _status(submission):
        return NormalizedJobStatus(
            internalJobId=submission.internalJobId,
            generatorId=submission.generatorId,
            status=job["status"],
            apiUsed=False,
        )

    def _collect(submission):
        return TimelineGenerationResult(
            internalJobId=submission.internalJobId,
            generatorId=submission.generatorId,
            status="completed",
            outputAssetIds=[job["assetId"]],
        )

    monkeypatch.setattr(adapter, "submit", _submit)
    monkeypatch.setattr(adapter, "get_status", _status)
    monkeypatch.setattr(adapter, "collect_result", _collect)
    monkeypatch.setattr(orchestrator, "_adapter", lambda generator_id: adapter)
    monkeypatch.setattr(
        "app.film_timeline.continuity.ensure_segment_continuity",
        lambda db, project_id, scene_id, shot, segment: {},
    )
    return calls, job


def _completed_ids(shot) -> set:
    return {
        segment.id
        for segment in shot.segments
        if segment.status == "completed" and segment.assetId
    }


def _stitch_included(shot) -> set:
    return set(getattr(shot.state, "stitchSegmentIds", None) or [])


def _ready_two_piece_stitch(db, pid: str, sid: str, tmp_path: Path) -> tuple[str, str]:
    """The live-cert starting point: two completed pieces + a ready 2-piece stitch."""

    created = orchestrator.create_shot(db, pid, sid, name="Shot 01", duration_sec=15.0, generator_id=H3)
    shot_id = created["shot"]["id"]
    film, shot = _shot(db, pid, sid, shot_id)
    shot.state.references = [
        ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")
    ]
    first = _asset(db, pid, _clip(tmp_path, "one", "red"))
    second = _asset(db, pid, _clip(tmp_path, "two", "green"))
    shot.segments = [
        Segment(order=0, durationSec=1.0, requestedDurationSec=1.0, timedPrompt="one", generatorId=H3, status="completed", assetId=first),
        Segment(order=1, durationSec=1.0, requestedDurationSec=1.0, timedPrompt="two", generatorId=H3, status="completed", assetId=second),
    ]
    shot.state.segmentIds = [segment.id for segment in shot.segments]
    save_film(db, pid, sid, film)

    stitched = stitch_shot(db, pid, sid, shot_id)
    assert stitched["ok"] is True, stitched
    film, shot = _shot(db, pid, sid, shot_id)
    assert shot.state.stitchStatus == "ready"
    assert shot.state.stitchAssetId
    return shot_id, shot.state.stitchAssetId


def test_retake_completion_is_never_left_ready_over_the_stale_two_segment_stitch(scene, h3_completable, tmp_path):
    """B-F2 race: the re-taken piece is in flight while old stitch state exists."""

    db, pid, sid = scene
    _calls, job = h3_completable
    shot_id, old_stitch = _ready_two_piece_stitch(db, pid, sid, tmp_path)

    # Re-Take/Continue the third piece: it becomes active while the old take exists.
    continued = orchestrator.continue_shot(db, pid, sid, shot_id, duration_sec=3.0, timed_prompt="three")
    assert continued["ok"] is True, continued
    film, shot = _shot(db, pid, sid, shot_id)
    assert max(shot.segments, key=lambda item: item.order).status in {"queued", "generating"}

    # Sync while the new piece is in flight. Pre-fix this call re-stitched the two
    # completed pieces and set stitchStatus='ready' (the 69ea756a trigger).
    inflight = orchestrator.sync_shot(db, pid, sid, shot_id)
    assert inflight["ok"] is True, inflight
    film, shot = _shot(db, pid, sid, shot_id)
    assert max(shot.segments, key=lambda item: item.order).status in {"queued", "generating"}
    assert shot.state.stitchStatus != "ready", "sync stitched a partial take while a piece was in flight"

    # The re-taken piece completes through the _refresh_shot path.
    job["assetId"] = _asset(db, pid, _clip(tmp_path, "three", "blue"))
    job["status"] = "completed"
    settled = orchestrator.sync_shot(db, pid, sid, shot_id)
    assert settled["ok"] is True, settled
    film, shot = _shot(db, pid, sid, shot_id)
    completed_ids = _completed_ids(shot)
    assert len(completed_ids) == 3

    # The defect: the monitor reported a 'ready' stitch over the stale 2-piece set.
    if shot.state.stitchStatus == "ready":
        assert _stitch_included(shot) == completed_ids, "ready stitch does not cover every completed segment"

    # (d) once the run settles the stitch is ready over every completed piece.
    assert shot.state.stitchStatus == "ready", shot.state.stitchStatus
    assert _stitch_included(shot) == completed_ids
    assert shot.state.stitchAssetId and shot.state.stitchAssetId != old_stitch
    rebuilt = db.get(Asset, shot.state.stitchAssetId)
    assert rebuilt is not None and Path(rebuilt.path).exists()
    # Three one-second pieces -> the rebuilt take is not the old two-piece 20.008s take.
    assert abs(probe_video_duration(Path(rebuilt.path)) - 3.0) < 0.35

    # No infinite loop: polling a settled shot must not rebuild the stitch again.
    settled_stitch = shot.state.stitchAssetId
    for _ in range(4):
        assert orchestrator.sync_shot(db, pid, sid, shot_id)["ok"] is True
    film, shot = _shot(db, pid, sid, shot_id)
    assert shot.state.stitchStatus == "ready"
    assert shot.state.stitchAssetId == settled_stitch
    assert _stitch_included(shot) == completed_ids


def test_maybe_stitch_leaves_stitch_state_alone_while_a_piece_is_in_flight(scene, h3, tmp_path):
    """(a): no stitch may run while any segment is active/in-flight."""

    db, pid, sid = scene
    shot_id, _old_stitch = _ready_two_piece_stitch(db, pid, sid, tmp_path)
    continued = orchestrator.continue_shot(db, pid, sid, shot_id, duration_sec=3.0, timed_prompt="three")
    assert continued["ok"] is True, continued

    film, shot = _shot(db, pid, sid, shot_id)
    assert max(shot.segments, key=lambda item: item.order).status in {"queued", "generating"}
    before = (shot.state.stitchStatus, shot.state.stitchAssetId)
    assert before[0] == "stale"

    orchestrator._maybe_stitch(db, pid, sid, shot)

    film, shot = _shot(db, pid, sid, shot_id)
    assert (shot.state.stitchStatus, shot.state.stitchAssetId) == before


def test_a_ready_stitch_missing_a_completed_segment_is_rebuilt_exactly_once(scene, h3, tmp_path):
    """(c): a 'ready' stitch whose included set != the completed set is stale."""

    db, pid, sid = scene
    created = orchestrator.create_shot(db, pid, sid, name="Shot 01", duration_sec=15.0, generator_id=H3)
    shot_id = created["shot"]["id"]
    film, shot = _shot(db, pid, sid, shot_id)
    shot.segments = [
        Segment(order=0, durationSec=1.0, requestedDurationSec=1.0, timedPrompt="one", generatorId=H3, status="completed", assetId=_asset(db, pid, _clip(tmp_path, "a", "red"))),
        Segment(order=1, durationSec=1.0, requestedDurationSec=1.0, timedPrompt="two", generatorId=H3, status="completed", assetId=_asset(db, pid, _clip(tmp_path, "b", "green"))),
        Segment(order=2, durationSec=1.0, requestedDurationSec=1.0, timedPrompt="three", generatorId=H3, status="completed", assetId=_asset(db, pid, _clip(tmp_path, "c", "blue"))),
    ]
    shot.state.segmentIds = [segment.id for segment in shot.segments]
    # A legacy 'ready' stitch with no recorded coverage, presented as current.
    shot.state.stitchAssetId = "legacy-partial-stitch"
    shot.state.stitchStatus = "ready"
    film.renderSessionId = current_runtime_session_id()
    save_film(db, pid, sid, film)

    assert orchestrator.sync_shot(db, pid, sid, shot_id)["ok"] is True
    film, shot = _shot(db, pid, sid, shot_id)
    completed_ids = _completed_ids(shot)
    assert len(completed_ids) == 3
    assert shot.state.stitchAssetId != "legacy-partial-stitch", "a partial 'ready' stitch must be rebuilt"
    assert shot.state.stitchStatus == "ready"
    assert _stitch_included(shot) == completed_ids

    rebuilt_id = shot.state.stitchAssetId
    for _ in range(3):
        assert orchestrator.sync_shot(db, pid, sid, shot_id)["ok"] is True
    film, shot = _shot(db, pid, sid, shot_id)
    assert shot.state.stitchAssetId == rebuilt_id
    assert _stitch_included(shot) == completed_ids

