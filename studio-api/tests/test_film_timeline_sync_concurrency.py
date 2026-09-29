"""Timeline V2 F1: overlapping sync is single-flight, idempotent and 500-free.

Live cert (theme_walk/timeline_v2_full_remediation/ui_cert_continue_shot_live.json):
POST /api/film-timeline/projects/{p}/scenes/{s}/shots/{id}/sync answered HTTP 500
eleven times while the UI auto-synced every 4s during a live generation, and the
same endpoint answered 200 after the run settled.

Root cause (reproduced below): sync_shot -> _refresh_shot ->
ensure_segment_continuity inserts frame Asset rows (db.flush) and then runs the
Qwen2.5-Omni tail review while that SQLite write transaction is still open
(measured 22-25s on this workstation). An overlapping sync then calls
store.save_film -> "UPDATE scenes SET director_json = ?" and, past the driver's
5s busy timeout, raises OperationalError: database is locked. post_sync only
handles FilmTimelineError, so it became a 500. The same overlap double-submitted
the next planned segment because both calls read the film before either committed.
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid

import pytest
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import MiniMaxH3I2VLocalAdapter
from app.director_timeline_w46.generation.contracts import NormalizedJobStatus, NormalizedJobSubmission
from app.film_timeline import orchestrator, store
from app.film_timeline.contracts import FilmTimeline, ReferenceAsset
from app.film_timeline.store import require_film, save_film

H3 = "minimax-h3-i2v-local"


@pytest.fixture()
def scene():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pid, sid = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Project(id=pid, name="Timeline sync concurrency", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene",
            prompt="prompt",
            duration_sec=20.0,
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
    calls_lock = threading.Lock()

    def _submit(request):
        with calls_lock:
            calls.append(request)
        return NormalizedJobSubmission(
            generatorId=request.generatorId,
            providerJobId=None,
            queueJobId=f"queue-{request.batchBlockId}",
        )

    def _status(job):
        # The stub never reaches Comfy, so report a live job: a concurrent sync
        # must not mark the segment failed for a missing queue row.
        return NormalizedJobStatus(
            internalJobId=job.internalJobId,
            generatorId=job.generatorId,
            status="running",
            apiUsed=False,
        )

    monkeypatch.setattr(adapter, "submit", _submit)
    monkeypatch.setattr(adapter, "get_status", _status)
    monkeypatch.setattr(orchestrator, "_adapter", lambda generator_id: adapter)
    # Frame extraction / Omni review is not this contract and would take ~25s.
    monkeypatch.setattr(
        "app.film_timeline.continuity.ensure_segment_continuity",
        lambda db, project_id, scene_id, shot, segment: {},
    )
    return calls


def _planned_tail_shot(db, pid: str, sid: str) -> str:
    """A shot whose first piece is done and whose next piece is planned, unsubmitted."""

    created = orchestrator.create_shot(db, pid, sid, name="Shot 01", duration_sec=20.0, generator_id=H3)
    shot_id = created["shot"]["id"]
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    shot.state.references = [
        ReferenceAsset(type="character", assetId="asset-char", label="Cade", tag="@Cade")
    ]
    save_film(db, pid, sid, film)

    first = orchestrator.generate_shot(db, pid, sid, shot_id, timed_prompt="wide")
    assert first["ok"] is True, first
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    # 20s on H3 plans [15, 5]: piece 0 is submitted, piece 1 stays empty + planned.
    assert [(segment.order, segment.status) for segment in shot.segments] == [(0, "queued"), (1, "empty")]
    shot.segments[0].status = "completed"
    shot.segments[0].assetId = "asset-0"
    save_film(db, pid, sid, film)
    return shot_id


def test_overlapping_sync_submits_the_planned_segment_exactly_once(scene, h3):
    db, pid, sid = scene
    shot_id = _planned_tail_shot(db, pid, sid)
    assert len(h3) == 1  # the Generate submit

    workers = 8
    barrier = threading.Barrier(workers)
    errors: list = []
    results: list = []

    def worker():
        session = SessionLocal()
        try:
            barrier.wait(timeout=30)
            results.append(orchestrator.sync_shot(session, pid, sid, shot_id))
        except Exception as exc:  # pragma: no cover - the pre-fix failure
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=180)

    assert errors == []
    assert len(results) == workers
    # Exactly ONE submission for the planned tail piece, regardless of overlap.
    assert len(h3) == 2, [result.get("segment", {}).get("id") for result in results]

    verify = SessionLocal()
    try:
        film = require_film(verify, pid, sid)
    finally:
        verify.close()
    shot = next(item for item in film.shots if item.id == shot_id)
    ordered = sorted(shot.segments, key=lambda item: item.order)
    assert [segment.order for segment in ordered] == [0, 1]
    assert ordered[0].status == "completed" and ordered[0].assetId == "asset-0"
    # A later overlapping sync may already have observed the stub job as running.
    assert ordered[1].status in {"queued", "generating"}
    assert ordered[1].generationMetadata.get("requestKey")
    assert [shot.state.segmentIds] == [[segment.id for segment in shot.segments]]


def _hold_scene_write_lock(sid: str, hold_sec: float, lock_held: threading.Event, release: threading.Event, errors: list):
    """A concurrent writer holds the SQLite write lock (what the F1 root cause does)."""

    conn = sqlite3.connect(str(settings.data_dir / "studio.db"), timeout=5.0, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE scenes SET director_json = director_json WHERE id = ?", (sid,))
        lock_held.set()
        release.wait(timeout=60)
        conn.commit()
    except Exception as exc:  # pragma: no cover
        errors.append(exc)
    finally:
        conn.close()


def test_overlapping_sync_stays_single_flight_while_another_writer_holds_the_lock(scene, h3):
    """The reproduced F1 mechanism, deterministic.

    Pre-fix every sync read the same un-committed film (the first commit was
    blocked by the held write lock), so the planned segment was submitted eight
    times and every sync died with OperationalError: database is locked -> 500.
    """

    db, pid, sid = scene
    shot_id = _planned_tail_shot(db, pid, sid)
    assert len(h3) == 1

    hold_sec = 6.5  # longer than the sqlite3 driver's 5s busy timeout
    lock_held = threading.Event()
    release = threading.Event()
    holder_errors: list = []
    holder = threading.Thread(
        target=_hold_scene_write_lock,
        args=(sid, hold_sec, lock_held, release, holder_errors),
        daemon=True,
    )
    holder.start()
    assert lock_held.wait(timeout=15)
    releaser = threading.Timer(hold_sec, release.set)
    releaser.start()

    workers = 8
    barrier = threading.Barrier(workers)
    errors: list = []
    results: list = []
    elapsed: list = []

    def worker():
        session = SessionLocal()
        try:
            barrier.wait(timeout=30)
            started = time.monotonic()
            results.append(orchestrator.sync_shot(session, pid, sid, shot_id))
            elapsed.append(time.monotonic() - started)
        except Exception as exc:  # pragma: no cover - the pre-fix failure
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=300)
    release.set()
    holder.join(timeout=30)
    releaser.cancel()

    assert holder_errors == []
    # Pre-fix: OperationalError "database is locked" here, surfaced as HTTP 500.
    assert errors == []
    assert len(results) == workers
    # Still exactly ONE submission for the planned tail piece.
    assert len(h3) == 2
    # The first sync really waited out the other writer's write lock.
    assert elapsed and max(elapsed) >= 5.0, elapsed


class _SceneStub:
    def __init__(self) -> None:
        self.director_json = "{}"


class _LockedCommitDb:
    """Minimal Session double whose commit raises 'database is locked' N times."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.commits = 0
        self.rollbacks = 0
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    def rollback(self) -> None:
        self.rollbacks += 1

    def commit(self) -> None:
        self.commits += 1
        if self.commits <= self.failures:
            raise OperationalError("UPDATE scenes", {}, sqlite3.OperationalError("database is locked"))


def test_save_film_retries_a_locked_write_and_writes_the_payload(monkeypatch):
    scene = _SceneStub()
    monkeypatch.setattr(store, "get_scene", lambda db, project_id, scene_id: scene)
    monkeypatch.setattr(store, "_SAVE_LOCK_BACKOFF_SEC", 0.0)
    db = _LockedCommitDb(failures=2)

    store.save_film(db, "project-1", "scene-1", FilmTimeline())

    assert db.commits == 3
    assert db.rollbacks == 2
    # The retry really writes: it is not a silent success.
    assert "filmTimeline" in scene.director_json


def test_save_film_raises_when_the_database_stays_locked(monkeypatch):
    scene = _SceneStub()
    monkeypatch.setattr(store, "get_scene", lambda db, project_id, scene_id: scene)
    monkeypatch.setattr(store, "_SAVE_LOCK_BACKOFF_SEC", 0.0)
    monkeypatch.setattr(store, "_SAVE_LOCK_ATTEMPTS", 3)
    db = _LockedCommitDb(failures=99)

    with pytest.raises(OperationalError):
        store.save_film(db, "project-1", "scene-1", FilmTimeline())

    assert db.commits == 3
    assert db.rollbacks == 3
