"""Stable shot numbers: creation identity, not track position."""

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
from app.film_timeline.continuity import fingerprint
from app.video_runtime.local_video_profiles import H3_BO_CONTINUATION_SAFE, H3_BO_FRESH_FAST, bo_execution_profile
from app.film_timeline import orchestrator
from app.film_timeline.contracts import FilmTimeline, ReferenceAsset, Segment, Shot
from app.film_timeline.retake import plan_replacement_pieces
from app.film_timeline.shot_identity import (
    allocate_shot_number,
    backfill_shot_numbers,
    creator_shot_label,
    drop_released_attempts,
    release_uncommitted_shot_numbers,
)
from app.film_timeline.store import require_film, save_film

H3 = "minimax-h3-i2v-local"


def test_backfill_numbers_once_in_composition_order_and_does_not_recalculate():
    film = FilmTimeline(
        shots=[
            Shot(
                segments=[
                    Segment(order=1, status="completed", assetId="b", durationSec=8, shotNumber=0),
                    Segment(order=0, status="completed", assetId="a", durationSec=15, shotNumber=0),
                ]
            )
        ]
    )
    assert backfill_shot_numbers(film) is True
    by_asset = {segment.assetId: segment.shotNumber for segment in film.shots[0].segments}
    assert by_asset == {"a": 1, "b": 2}
    assert film.highestShotNumber == 2
    assert backfill_shot_numbers(film) is False


def test_prepend_position_does_not_renumber_and_delete_does_not_reuse():
    film = FilmTimeline(
        highestShotNumber=3,
        shots=[
            Shot(
                segments=[
                    Segment(id="s2", order=0, status="completed", assetId="pre", durationSec=8, shotNumber=2),
                    Segment(id="s1", order=1, status="completed", assetId="first", durationSec=15, shotNumber=1),
                    Segment(id="s3", order=2, status="completed", assetId="third", durationSec=12, shotNumber=3),
                ]
            )
        ],
    )
    assert backfill_shot_numbers(film) is False
    film.shots[0].segments = [segment for segment in film.shots[0].segments if segment.id != "s2"]
    assert [segment.shotNumber for segment in film.shots[0].segments] == [1, 3]
    assert allocate_shot_number(film) == 4
    assert creator_shot_label(4) == "Shot 4"


def test_failed_attempt_releases_its_shot_number_and_the_next_continue_reuses_it():
    failed = Segment(id="bad", order=4, status="failed", assetId=None, durationSec=15, shotNumber=5)
    film = FilmTimeline(
        highestShotNumber=5,
        shots=[
            Shot(
                segments=[
                    Segment(id="s1", order=0, status="completed", assetId="a", durationSec=15, shotNumber=1),
                    Segment(id="s4", order=3, status="completed", assetId="d", durationSec=15, shotNumber=4),
                    failed,
                ]
            )
        ],
    )
    assert release_uncommitted_shot_numbers(film) is True
    assert failed.shotNumber == 0
    assert film.highestShotNumber == 4
    assert backfill_shot_numbers(film) is False
    assert failed.shotNumber == 0
    assert drop_released_attempts(film) is True
    assert allocate_shot_number(film) == 5


def test_deleting_a_finished_shot_still_does_not_reuse_its_number():
    film = FilmTimeline(
        highestShotNumber=3,
        shots=[Shot(segments=[Segment(id="s1", status="completed", assetId="a", shotNumber=1)])],
    )
    assert release_uncommitted_shot_numbers(film) is False
    assert film.highestShotNumber == 3
    assert allocate_shot_number(film) == 4


def test_retake_pieces_keep_the_parent_number():
    source = Segment(id="src", shotNumber=1, assetId="pic", durationSec=15, status="completed", timedPrompt="walks")
    film = FilmTimeline(highestShotNumber=1, shots=[Shot(segments=[source])])
    pieces = plan_replacement_pieces(source, "new", file_in=7, file_out=10, marked=3, generated_sec=3, prompt="turns")
    assert [piece.shotNumber for piece in pieces] == [1, 1, 1]
    assert [piece.compositionRole for piece in pieces] == ["source", "retake", "source"]
    assert film.highestShotNumber == 1


@pytest.fixture()
def scene():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pid, sid = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Project(id=pid, name="Shot identity", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene",
            prompt="",
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
        return NormalizedJobStatus(internalJobId=job.internalJobId, generatorId=job.generatorId, status="running", apiUsed=False)

    monkeypatch.setattr(adapter, "submit", _submit)
    monkeypatch.setattr(adapter, "get_status", _status)
    monkeypatch.setattr(orchestrator, "_adapter", lambda generator_id: adapter)
    monkeypatch.setattr(
        "app.film_timeline.continuity.ensure_segment_continuity",
        lambda db, project_id, scene_id, shot, segment: {},
    )
    return calls


def _clip(tmp_path: Path, name: str) -> Path:
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    assert ffmpeg
    out = tmp_path / f"{name}.mp4"
    subprocess.check_call(
        [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=steelblue:s=64x64:d=1:r=24", "-pix_fmt", "yuv420p", str(out)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return out


def _asset(db, project_id: str, path: Path) -> str:
    asset_id = str(uuid.uuid4())
    db.add(Asset(id=asset_id, project_id=project_id, tag="clip", kind="video", filename=path.name, path=str(path)))
    db.commit()
    return asset_id


def test_local_models_continue_onto_the_reserved_segment(scene, monkeypatch):
    """One Timeline continuation contract for the four local video models.

    The adapter may change the conditioning. The new segment id and shot number
    are assigned before submit and are what the job carries.
    """

    db, pid, sid = scene
    calls: list = []

    def wrapped(generator_id):
        adapter = orchestrator._registry().get(generator_id)

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
        return adapter

    monkeypatch.setattr(orchestrator, "_adapter", wrapped)
    monkeypatch.setattr(
        "app.film_timeline.continuity.ensure_segment_continuity",
        lambda *args, **kwargs: {},
    )
    still = str(uuid.uuid4())
    db.add(Asset(id=still, project_id=pid, tag="tail", kind="image", filename="tail.png", path="tail.png"))
    db.commit()

    models = (
        "minimax-h3-i2v-local",
        "minimax-h3-base-optimized",
        "ltx-2.5-distilled",
        "hunyuan-video-1.5-distilled",
    )
    for generator_id in models:
        calls.clear()
        duration = 5 if "hunyuan" in generator_id else 6
        sid = str(uuid.uuid4())
        db.add(
            Scene(
                id=sid,
                project_id=pid,
                index=0,
                name=generator_id,
                prompt="",
                duration_sec=float(duration),
                aspect_ratio="16:9",
                director_json="",
            )
        )
        db.commit()
        created = orchestrator.create_shot(db, pid, sid, duration_sec=duration, generator_id=generator_id)
        shot_id = created["shot"]["id"]
        film = require_film(db, pid, sid)
        shot = next(item for item in film.shots if item.id == shot_id)
        shot.state.references = [ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")]
        save_film(db, pid, sid, film)

        first = orchestrator.generate_shot(
            db, pid, sid, shot_id, duration_sec=duration, timed_prompt="She walks in", generator_id=generator_id
        )
        assert first["ok"] is True, (generator_id, first)
        film = require_film(db, pid, sid)
        shot = next(item for item in film.shots if item.id == shot_id)
        for segment in shot.segments:
            segment.status = "completed"
            segment.assetId = segment.assetId or f"done-{segment.id}"
            segment.lastFrameAssetId = still
        save_film(db, pid, sid, film)
        prior_ids = {segment.id for segment in shot.segments}

        continued = orchestrator.continue_shot(
            db, pid, sid, shot_id, duration_sec=duration, timed_prompt="She turns", generator_id=generator_id
        )
        assert continued["ok"] is True, (generator_id, continued)
        film = require_film(db, pid, sid)
        shot = next(item for item in film.shots if item.id == shot_id)
        newest = max(shot.segments, key=lambda item: item.order)
        assert newest.id not in prior_ids
        assert newest.shotNumber == 2
        request = calls[-1]
        assert request.batchBlockId == newest.id
        assert request.generatorId == generator_id
        if generator_id.startswith("minimax-h3"):
            assert request.generationMode == "reference"
            assert request.continuityStrategy == "reference_video"
        else:
            assert request.generationMode == "image_to_video"
            assert request.startImageAssetId == still
            assert request.videoReferenceAssetId in (None, "")

        for segment in shot.segments:
            if segment.status != "completed":
                segment.status = "completed"
                segment.assetId = segment.assetId or f"done-{segment.id}"
                segment.lastFrameAssetId = still
        save_film(db, pid, sid, film)
        third = orchestrator.continue_shot(
            db, pid, sid, shot_id, duration_sec=duration, timed_prompt="She looks back", generator_id=generator_id
        )
        assert third["ok"] is True, (generator_id, third)
        film = require_film(db, pid, sid)
        shot = next(item for item in film.shots if item.id == shot_id)
        numbers = sorted({segment.shotNumber for segment in shot.segments})
        assert numbers == [1, 2, 3]
        assert len({segment.id for segment in shot.segments}) == len(shot.segments)
        assert calls[-1].batchBlockId == max(shot.segments, key=lambda item: item.order).id


def test_generate_and_continue_assign_stable_numbers_and_do_not_prompt_them(scene, h3):
    db, pid, sid = scene
    created = orchestrator.create_shot(db, pid, sid, duration_sec=20, generator_id=H3)
    shot_id = created["shot"]["id"]
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    shot.state.references = [ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")]
    save_film(db, pid, sid, film)

    first = orchestrator.generate_shot(db, pid, sid, shot_id, duration_sec=20, timed_prompt="She walks in", generator_id=H3)
    assert first["ok"] is True, first
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    planned = [segment for segment in shot.segments if segment.generationMetadata.get("planned")]
    assert len(planned) == 2
    assert {segment.shotNumber for segment in planned} == {1}
    assert film.highestShotNumber == 1
    assert all("Shot" not in (call.prompt or "") for call in h3)
    assert all(segment.timedPrompt == "She walks in" for segment in planned)

    for segment in list(shot.segments):
        segment.status = "completed"
        segment.assetId = segment.assetId or "done"
    save_film(db, pid, sid, film)

    continued = orchestrator.continue_shot(db, pid, sid, shot_id, duration_sec=8, timed_prompt="She turns")
    assert continued["ok"] is True, continued
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    newest = max(shot.segments, key=lambda item: item.order)
    assert newest.shotNumber == 2
    assert newest.timedPrompt == "She turns"
    assert "#Shot" not in (h3[-1].prompt or "")
    assert "Shot 2" not in (h3[-1].prompt or "")


def test_import_then_delete_then_reload(scene, tmp_path):
    db, pid, sid = scene
    created = orchestrator.create_shot(db, pid, sid, duration_sec=4, generator_id=H3)
    shot_id = created["shot"]["id"]
    path = _clip(tmp_path, "lib")
    numbers = []
    for _ in range(3):
        asset_id = _asset(db, pid, path)
        imported = orchestrator.import_library_video(db, pid, sid, shot_id, asset_id=asset_id)
        assert imported["ok"] is True, imported
        film = require_film(db, pid, sid)
        shot = next(item for item in film.shots if item.id == shot_id)
        numbers.append(max(segment.shotNumber for segment in shot.segments))
    assert numbers == [1, 2, 3]

    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    middle = next(segment for segment in shot.segments if segment.shotNumber == 2)
    removed = orchestrator.delete_segment(db, pid, sid, shot_id, middle.id)
    assert removed["ok"] is True

    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    assert sorted(segment.shotNumber for segment in shot.segments) == [1, 3]
    assert film.highestShotNumber == 3

    again = orchestrator.import_library_video(db, pid, sid, shot_id, asset_id=_asset(db, pid, path))
    assert again["ok"] is True
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    assert sorted(segment.shotNumber for segment in shot.segments) == [1, 3, 4]


def test_partial_retake_does_not_allocate(scene, h3, tmp_path):
    db, pid, sid = scene
    created = orchestrator.create_shot(db, pid, sid, duration_sec=10, generator_id=H3)
    shot_id = created["shot"]["id"]
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    shot.state.references = [ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")]
    asset_id = _asset(db, pid, _clip(tmp_path, "take"))
    shot.segments = [
        Segment(
            order=0,
            durationSec=10,
            requestedDurationSec=10,
            status="completed",
            assetId=asset_id,
            timedPrompt="walks",
            generatorId=H3,
            shotNumber=1,
        )
    ]
    film.highestShotNumber = 1
    save_film(db, pid, sid, film)

    result = orchestrator.retake_shot(db, pid, sid, shot_id, mark_in=2, mark_out=5, timed_prompt="turns")
    assert result.get("ok") is True, result
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    assert film.highestShotNumber == 1
    assert {segment.shotNumber for segment in shot.segments} == {1}


def _retake_adapter(monkeypatch, job: dict):
    calls: list = []

    def wrapped(generator_id):
        adapter = orchestrator._registry().get(generator_id)

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
            asset_id = str(job.get("assetId") or "")
            return TimelineGenerationResult(
                internalJobId=submission.internalJobId,
                generatorId=submission.generatorId,
                status="completed",
                outputAssetIds=[asset_id] if asset_id else [],
            )

        monkeypatch.setattr(adapter, "submit", _submit)
        monkeypatch.setattr(adapter, "get_status", _status)
        monkeypatch.setattr(adapter, "collect_result", _collect)
        return adapter

    monkeypatch.setattr(orchestrator, "_adapter", wrapped)
    monkeypatch.setattr(
        "app.film_timeline.continuity.ensure_segment_continuity",
        lambda *args, **kwargs: {},
    )
    return calls


def _three_shots(db, pid, sid, generator_id: str, *, canvas: dict | None = None, duration: int = 15):
    created = orchestrator.create_shot(db, pid, sid, duration_sec=duration, generator_id=generator_id)
    shot_id = created["shot"]["id"]
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    shot.state.references = [ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")]
    assets = [f"asset-{generator_id}-{number}" for number in (1, 2, 3)]
    segments = []
    for order, (number, asset_id) in enumerate(zip((1, 2, 3), assets, strict=True)):
        segment = Segment(
            order=order,
            durationSec=duration,
            requestedDurationSec=duration,
            status="completed",
            assetId=asset_id,
            timedPrompt=f"shot {number}",
            generatorId=generator_id,
            shotNumber=number,
            lastFrameAssetId="still-frame",
        )
        segment.generationMetadata["continuity"] = {
            "fingerprint": fingerprint(asset_id),
            "seam": {"status": "ok"},
        }
        if canvas and number == 2:
            segment.generationMetadata["legalCanvas"] = dict(canvas)
        segments.append(segment)
    shot.segments = segments
    film.highestShotNumber = 3
    film.generatorId = generator_id
    save_film(db, pid, sid, film)
    return shot_id, assets


def test_whole_shot_retake_keeps_identity_until_the_new_picture_commits(scene, monkeypatch):
    db, pid, sid = scene
    scene_row = db.get(Scene, sid)
    scene_row.aspect_ratio = "21:9"
    db.commit()
    still = str(uuid.uuid4())
    db.add(Asset(id=still, project_id=pid, tag="tail", kind="image", filename="tail.png", path="tail.png"))
    db.commit()
    job = {"status": "running", "assetId": ""}
    calls = _retake_adapter(monkeypatch, job)
    generator_id = "minimax-h3-base-optimized"
    shot_id, assets = _three_shots(
        db, pid, sid, generator_id, canvas={"width": 1728, "height": 736, "megapixels": 1.2}
    )
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    for segment in shot.segments:
        segment.lastFrameAssetId = still
    save_film(db, pid, sid, film)
    target_id = shot.segments[1].id

    started = orchestrator.retake_shot(db, pid, sid, shot_id, mark_in=15, mark_out=30, timed_prompt="shot 2")
    assert started.get("ok") is True, started
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    assert [segment.id for segment in shot.segments][1] == target_id
    assert [segment.shotNumber for segment in shot.segments] == [1, 2, 3]
    assert len(shot.segments) == 3
    middle = shot.segments[1]
    assert middle.assetId == assets[1]
    assert middle.status in {"queued", "generating"}
    assert film.highestShotNumber == 3
    request = calls[-1]
    assert request.generatorId == generator_id
    assert request.batchBlockId == target_id
    assert request.duration == 15
    assert request.resolution == "1728x736"
    assert request.videoReferenceAssetId == assets[0]
    assert request.videoReferenceAssetId != assets[1]
    assert bo_execution_profile(has_ending_clip=True) == {
        "profile": H3_BO_CONTINUATION_SAFE,
        "sageAttention": "disabled",
    }
    assert shot.segments[2].generationMetadata["continuity"]["seam"]["status"] == "ok"
    assert shot.segments[0].assetId == assets[0]

    class _Queue:
        async def cancel_and_halt(self, job_id):
            return {"ok": True, "confirmedStopped": True}

    monkeypatch.setattr("app.queue_worker.job_queue", _Queue())
    import asyncio

    cancelled = asyncio.run(orchestrator.cancel_shot(db, pid, sid, shot_id))
    assert cancelled.get("ok") is True, cancelled
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    assert len(shot.segments) == 3
    assert shot.segments[1].id == target_id
    assert shot.segments[1].shotNumber == 2
    assert shot.segments[1].assetId == assets[1]
    assert shot.segments[1].status == "completed"
    assert film.highestShotNumber == 3
    assert shot.segments[2].generationMetadata["continuity"]["seam"]["status"] == "ok"

    again = orchestrator.retake_shot(db, pid, sid, shot_id, mark_in=15, mark_out=30, timed_prompt="shot 2")
    assert again.get("ok") is True, again
    job["status"] = "failed"
    failed = orchestrator.sync_shot(db, pid, sid, shot_id)
    assert failed.get("ok") is True, failed
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    assert shot.segments[1].id == target_id
    assert shot.segments[1].assetId == assets[1]
    assert shot.segments[1].status == "completed"
    assert shot.segments[1].shotNumber == 2
    assert len(shot.segments) == 3
    assert shot.segments[2].generationMetadata["continuity"]["seam"]["status"] == "ok"

    third = orchestrator.retake_shot(db, pid, sid, shot_id, mark_in=15, mark_out=30, timed_prompt="shot 2")
    assert third.get("ok") is True, third
    job["status"] = "completed"
    job["assetId"] = "asset-new"
    done = orchestrator.sync_shot(db, pid, sid, shot_id)
    assert done.get("ok") is True, done
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    assert len(shot.segments) == 3
    assert [segment.id for segment in shot.segments][1] == target_id
    assert [segment.shotNumber for segment in shot.segments] == [1, 2, 3]
    assert shot.segments[0].assetId == assets[0]
    assert shot.segments[1].assetId == "asset-new"
    assert shot.segments[2].assetId == assets[2]
    seam = shot.segments[2].generationMetadata["continuity"]["seam"]
    assert seam["status"] == "stale"
    assert shot.segments[2].generationMetadata["continuity"]["seamStale"] is True
    assert shot.segments[0].generationMetadata["continuity"]["seam"]["status"] == "ok"


def test_fresh_and_shared_model_retakes_keep_their_conditioning(scene, monkeypatch):
    db, pid, sid = scene
    still = str(uuid.uuid4())
    db.add(Asset(id=still, project_id=pid, tag="tail", kind="image", filename="tail.png", path="tail.png"))
    db.commit()
    job = {"status": "running", "assetId": ""}
    calls = _retake_adapter(monkeypatch, job)

    fresh_id = "minimax-h3-base-optimized"
    created = orchestrator.create_shot(db, pid, sid, duration_sec=15, generator_id=fresh_id)
    shot_id = created["shot"]["id"]
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    shot.state.references = [ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")]
    only = Segment(
        order=0,
        durationSec=15,
        requestedDurationSec=15,
        status="completed",
        assetId="fresh-asset",
        timedPrompt="opens",
        generatorId=fresh_id,
        shotNumber=1,
    )
    only.generationMetadata["legalCanvas"] = {"width": 1728, "height": 736}
    shot.segments = [only]
    film.highestShotNumber = 1
    film.generatorId = fresh_id
    save_film(db, pid, sid, film)
    scene_row = db.get(Scene, sid)
    scene_row.aspect_ratio = "21:9"
    db.commit()
    fresh = orchestrator.retake_shot(db, pid, sid, shot_id, mark_in=0, mark_out=15)
    assert fresh.get("ok") is True, fresh
    request = calls[-1]
    assert request.generatorId == fresh_id
    assert request.videoReferenceAssetId in (None, "")
    assert request.batchBlockId == only.id
    assert bo_execution_profile(has_ending_clip=False)["profile"] == H3_BO_FRESH_FAST
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    assert shot.segments[0].assetId == "fresh-asset"
    assert shot.segments[0].shotNumber == 1
    assert len(shot.segments) == 1

    for generator_id in ("minimax-h3-i2v-local", "ltx-2.5-distilled", "hunyuan-video-1.5-distilled"):
        calls.clear()
        sid = str(uuid.uuid4())
        db.add(
            Scene(
                id=sid,
                project_id=pid,
                index=1,
                name=generator_id,
                prompt="",
                duration_sec=15,
                aspect_ratio="16:9",
                director_json="",
            )
        )
        db.commit()
        duration = 5 if "hunyuan" in generator_id else 6
        shot_id, assets = _three_shots(db, pid, sid, generator_id, duration=duration)
        film = require_film(db, pid, sid)
        shot = next(item for item in film.shots if item.id == shot_id)
        for segment in shot.segments:
            segment.lastFrameAssetId = still
        save_film(db, pid, sid, film)
        started = orchestrator.retake_shot(db, pid, sid, shot_id, mark_in=duration, mark_out=duration * 2)
        assert started.get("ok") is True, (generator_id, started)
        request = calls[-1]
        assert request.generatorId == generator_id
        assert request.batchBlockId == shot.segments[1].id
        film = require_film(db, pid, sid)
        shot = next(item for item in film.shots if item.id == shot_id)
        assert len(shot.segments) == 3
        assert shot.segments[1].assetId == assets[1]
        assert shot.segments[1].shotNumber == 2
        if generator_id.startswith("minimax-h3"):
            assert request.videoReferenceAssetId == assets[0]
            assert request.continuityStrategy == "reference_video"
        else:
            assert request.startImageAssetId == still
            assert request.videoReferenceAssetId in (None, "")
            assert request.generationMode == "image_to_video"
