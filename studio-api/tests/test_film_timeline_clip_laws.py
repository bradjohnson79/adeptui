"""Film Timeline clip deletion and same-lane overlap."""

from __future__ import annotations

import uuid

import pytest

from app.db import Base, Project, Scene, SessionLocal, engine
from app.film_timeline.contracts import Segment
from app.film_timeline.insertion import add_to_timeline, delete_clip, update_clip
from app.film_timeline.orchestrator import create_shot, delete_segment, delete_timed_prompt
from app.film_timeline.store import require_film


@pytest.fixture()
def scene():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pid, sid = str(uuid.uuid4()), str(uuid.uuid4())
    db.add(Project(id=pid, name="Timeline clip laws", description=""))
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


def test_same_lane_overlap_rejects_and_touching_edges_are_kept(scene):
    db, pid, sid = scene
    first = add_to_timeline(db, pid, sid, media_type="video", asset_id="asset-a", start_time=0, duration_sec=5, label="A")
    edge = add_to_timeline(db, pid, sid, media_type="video", asset_id="asset-b", start_time=5, duration_sec=5, label="B")
    overlap = add_to_timeline(db, pid, sid, media_type="video", asset_id="asset-c", start_time=4.9, duration_sec=5, label="C")
    assert first["ok"] is True
    assert edge["ok"] is True
    assert overlap["ok"] is False
    assert overlap["error"] == "LANE_OVERLAP"
    reloaded = require_film(db, pid, sid)
    assert [clip.label for clip in reloaded.videoClips] == ["A", "B"]

    voice = add_to_timeline(
        db, pid, sid, media_type="audio", asset_id="voice-a", target_track_type="voice", start_time=0, duration_sec=5, label="Voice"
    )
    voice_overlap = add_to_timeline(
        db, pid, sid, media_type="audio", asset_id="voice-b", target_track_type="voice", start_time=4, duration_sec=4, label="Voice 2"
    )
    music = add_to_timeline(
        db, pid, sid, media_type="audio", asset_id="music-a", target_track_type="music", start_time=0, duration_sec=5, label="Music"
    )
    assert voice["ok"] is True
    assert voice_overlap["ok"] is False
    assert music["ok"] is True

    moved = update_clip(db, pid, sid, edge["clip"]["id"], {"startSec": 4.0})
    assert moved["ok"] is False
    reloaded = require_film(db, pid, sid)
    kept = next(clip for clip in reloaded.videoClips if clip.id == edge["clip"]["id"])
    assert kept.startSec == 5


def test_delete_removes_only_the_selected_item_and_persists(scene):
    db, pid, sid = scene
    created = create_shot(db, pid, sid, timed_prompt="Walk to the door")
    shot_id = created["shot"]["id"]
    film = require_film(db, pid, sid)
    shot = next(item for item in film.shots if item.id == shot_id)
    keep = Segment(timedPrompt="keep this prompt", assetId="seg-keep", durationSec=5, generationMetadata={"continuity": {"enabled": True}})
    drop = Segment(timedPrompt="delete this prompt", assetId="seg-drop", durationSec=5, generationMetadata={"continuity": {"enabled": True}})
    shot.segments = [keep, drop]
    shot.state.segmentIds = [keep.id, drop.id]
    shot.state.stitchSegmentIds = [keep.id, drop.id]
    shot.state.stitchStatus = "ready"
    from app.film_timeline.store import save_film

    save_film(db, pid, sid, film)

    video = add_to_timeline(db, pid, sid, media_type="video", asset_id="placed-video", start_time=0, duration_sec=3, label="Placed")
    other_video = add_to_timeline(db, pid, sid, media_type="video", asset_id="other-video", start_time=3, duration_sec=2, label="Other")
    audio = add_to_timeline(db, pid, sid, media_type="audio", asset_id="audio-1", target_track_type="voice", start_time=0, duration_sec=3, label="Line")
    sfx = add_to_timeline(db, pid, sid, media_type="sfx", asset_id="sfx-1", start_time=0, duration_sec=1, label="Hit")
    assert delete_clip(db, pid, sid, video["clip"]["id"])["ok"] is True
    assert delete_clip(db, pid, sid, audio["clip"]["id"])["ok"] is True
    assert delete_clip(db, pid, sid, sfx["clip"]["id"])["ok"] is True
    prompt = delete_timed_prompt(db, pid, sid, shot_id, segment_id=drop.id)
    assert prompt["ok"] is True
    removed = delete_segment(db, pid, sid, shot_id, drop.id)
    assert removed["ok"] is True

    reloaded = require_film(db, pid, sid)
    shot = next(item for item in reloaded.shots if item.id == shot_id)
    assert [clip.label for clip in reloaded.videoClips] == ["Other"]
    assert reloaded.audio == []
    assert reloaded.sfx == []
    assert shot.timedPrompt == ""
    assert [item.id for item in shot.segments] == [keep.id]
    assert shot.segments[0].timedPrompt == "keep this prompt"
    assert shot.segments[0].generationMetadata["continuity"]["enabled"] is True
    assert shot.state.stitchStatus == "stale"
