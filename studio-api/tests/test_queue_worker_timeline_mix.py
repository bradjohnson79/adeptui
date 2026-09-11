"""Structure-level coverage for timeline render music/SFX mix stage."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.db import Base, Project, Scene, Job, SessionLocal, engine
from app.queue_worker import JobQueue


def _setup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Mix Stage Test"))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="S1",
            prompt="",
            duration_sec=3.0,
            director_json="",
        )
    )
    db.commit()
    return db, pid, sid


def test_render_timeline_mix_stage_skipped_when_no_stems(monkeypatch, tmp_path: Path):
    """When collect_timeline_mix_stems returns no stems, mix_stems_onto_video is not called."""
    db, pid, sid = _setup()
    try:
        job = Job(id=str(uuid.uuid4()), project_id=pid, scene_id=None, kind="render_timeline")
        db.add(job)
        db.commit()

        queue = JobQueue()
        monkeypatch.setattr(
            queue, "_build_and_run_scene", AsyncMock(return_value=tmp_path / "scene.mp4")
        )
        monkeypatch.setattr(queue, "_lipsync_scene", AsyncMock(return_value=None))
        monkeypatch.setattr(
            "app.queue_worker.stitch_videos",
            lambda outputs, final, fps: final,
        )

        collect_calls = []

        def fake_collect(*args, **kwargs):
            collect_calls.append((args, kwargs))
            return [], []

        monkeypatch.setattr("app.editor_mix.collect_timeline_mix_stems", fake_collect)

        mix_calls = []

        def fake_mix(*args, **kwargs):
            mix_calls.append((args, kwargs))
            return MagicMock(filter_complex="[aout]")

        monkeypatch.setattr("app.editor_mix.mix_stems_onto_video", fake_mix)

        async def _run():
            return await queue._render_timeline(db, job, db.get(Project, pid))

        asyncio.run(_run())

        assert len(collect_calls) == 1
        assert mix_calls == []
    finally:
        db.close()


def test_render_timeline_mix_stage_invoked_when_stems_exist(monkeypatch, tmp_path: Path):
    """When collect_timeline_mix_stems returns stems, mix_stems_onto_video runs and output is updated."""
    db, pid, sid = _setup()
    try:
        job = Job(id=str(uuid.uuid4()), project_id=pid, scene_id=None, kind="render_timeline")
        db.add(job)
        db.commit()

        queue = JobQueue()
        monkeypatch.setattr(
            queue, "_build_and_run_scene", AsyncMock(return_value=tmp_path / "scene.mp4")
        )
        monkeypatch.setattr(queue, "_lipsync_scene", AsyncMock(return_value=None))
        monkeypatch.setattr(
            "app.queue_worker.stitch_videos",
            lambda outputs, final, fps: final,
        )

        fake_stem = MagicMock()

        def fake_collect(*args, **kwargs):
            return [fake_stem], []

        monkeypatch.setattr("app.editor_mix.collect_timeline_mix_stems", fake_collect)

        mix_calls = []

        def fake_mix(*args, **kwargs):
            mix_calls.append((args, kwargs))
            return MagicMock(filter_complex="[aout]")

        monkeypatch.setattr("app.editor_mix.mix_stems_onto_video", fake_mix)

        async def _run():
            return await queue._render_timeline(db, job, db.get(Project, pid))

        asyncio.run(_run())

        db.refresh(job)
        assert len(mix_calls) == 1
        assert job.message == "Timeline render complete"
        assert job.status == "done"
    finally:
        db.close()
