"""Canonical volume/mute command for Director Timeline audio/SFX clips."""

from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.db import Asset, Base, Project, Scene, SessionLocal, engine
from app.director_timeline import parse_director_timeline
from app.director_timeline_w46.audio_volume import set_timeline_audio_volume


def _scene_with_audio():
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    db.add(Project(id=pid, name="Volume Test"))
    director = {
        "media_mode": "video",
        "duration_sec": 5.0,
        "image_clips": [],
        "video_clips": [],
        "prompt_segments": [],
        "audio_clips": [
            {"id": "a1", "asset_id": "music", "start": 0.0, "length": 5.0, "volume": 1.0, "muted": False}
        ],
        "sfx_clips": [
            {"id": "s1", "asset_id": "sfx", "start": 1.0, "length": 2.0, "volume": 1.0, "muted": True},
            {"id": "s2", "asset_id": "sfx", "start": 0.0, "length": 1.0, "volume": 0.5, "muted": False},
        ],
    }
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="V",
            prompt="",
            duration_sec=5.0,
            director_json=json.dumps(director),
        )
    )
    db.commit()
    return db, pid, sid


def test_clip_targeted_volume_percent_and_mute_preserves_volume():
    db, pid, sid = _scene_with_audio()
    try:
        result = set_timeline_audio_volume(
            db, pid, sid, clip_id="a1", volume_percent=40.0, muted=True
        )
        assert result["ok"] is True
        assert result["changed"] is True
        updated = {c["id"]: c for c in result["updatedClips"]}
        assert updated["a1"]["volume"] == 0.4
        assert updated["a1"]["muted"] is True

        scene = db.get(Scene, sid)
        tl = parse_director_timeline(scene.director_json)
        assert tl.audio_clips[0].volume == 0.4
        assert tl.audio_clips[0].muted is True
    finally:
        db.close()


def test_track_targeted_applies_to_all_clips_and_clamps():
    db, pid, sid = _scene_with_audio()
    try:
        result = set_timeline_audio_volume(db, pid, sid, track="sfx", volume_percent=150.0)
        assert result["ok"] is True
        assert result["changed"] is True
        updated = {c["id"]: c for c in result["updatedClips"]}
        assert updated["s1"]["volume"] == 1.0  # clamped
        assert updated["s1"]["muted"] is False  # volume change unmutes (canonical rule)
        assert updated["s2"]["volume"] == 1.0  # clamped
        assert updated["s2"]["muted"] is False  # untouched
    finally:
        db.close()


def test_volume_change_while_muted_unmutes_clip_targeted():
    """Canonical rule: moving volume on a muted clip unmutes it (mirrors UI)."""
    db, pid, sid = _scene_with_audio()
    try:
        result = set_timeline_audio_volume(db, pid, sid, clip_id="s1", volume_percent=30.0)
        assert result["ok"] is True
        assert result["changed"] is True
        updated = {c["id"]: c for c in result["updatedClips"]}
        assert updated["s1"]["volume"] == 0.3
        assert updated["s1"]["muted"] is False

        scene = db.get(Scene, sid)
        tl = parse_director_timeline(scene.director_json)
        assert tl.sfx_clips[0].volume == 0.3
        assert tl.sfx_clips[0].muted is False
    finally:
        db.close()


def test_explicit_mute_true_with_volume_in_same_call_wins():
    """An explicit muted= in the same call overrides the unmute-on-volume rule."""
    db, pid, sid = _scene_with_audio()
    try:
        result = set_timeline_audio_volume(db, pid, sid, clip_id="s1", volume_percent=30.0, muted=True)
        assert result["ok"] is True
        assert result["changed"] is True
        updated = {c["id"]: c for c in result["updatedClips"]}
        assert updated["s1"]["volume"] == 0.3
        assert updated["s1"]["muted"] is True
    finally:
        db.close()


def test_mute_toggle_does_not_rewrite_volume():
    db, pid, sid = _scene_with_audio()
    try:
        result = set_timeline_audio_volume(db, pid, sid, clip_id="s2", muted=True)
        assert result["ok"] is True
        assert result["changed"] is True
        scene = db.get(Scene, sid)
        tl = parse_director_timeline(scene.director_json)
        assert tl.sfx_clips[1].muted is True
        assert tl.sfx_clips[1].volume == 0.5
    finally:
        db.close()


def test_unmute_existing_keeps_volume():
    db, pid, sid = _scene_with_audio()
    try:
        result = set_timeline_audio_volume(db, pid, sid, clip_id="s1", muted=False)
        assert result["ok"] is True
        assert result["changed"] is True
        scene = db.get(Scene, sid)
        tl = parse_director_timeline(scene.director_json)
        assert tl.sfx_clips[0].muted is False
        assert tl.sfx_clips[0].volume == 1.0
    finally:
        db.close()


def test_no_change_when_values_match():
    db, pid, sid = _scene_with_audio()
    try:
        result = set_timeline_audio_volume(db, pid, sid, clip_id="a1", volume_percent=100.0, muted=False)
        assert result["ok"] is True
        assert result["changed"] is False
    finally:
        db.close()


def test_missing_clip_returns_not_found():
    db, pid, sid = _scene_with_audio()
    try:
        result = set_timeline_audio_volume(db, pid, sid, clip_id="nope")
        assert result["ok"] is False
        assert result["error"] == "CLIP_NOT_FOUND"
    finally:
        db.close()


def test_track_required_when_clip_id_omitted():
    db, pid, sid = _scene_with_audio()
    try:
        result = set_timeline_audio_volume(db, pid, sid, volume_percent=50.0)
        assert result["ok"] is False
        assert result["error"] == "TRACK_REQUIRED"
    finally:
        db.close()
