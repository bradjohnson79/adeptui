"""M3.0 Completion Phase 1 (B4): audio cues must reach the Director timeline.

The blocker these cover: a cue could be generated, stored, and still never appear in
`scene.director_json`, so the sound path looked done while the timeline held nothing.
Placement is asserted through the public `GET .../director` contract, not the cue table,
and a fixture asset id — which names no file — must still be refused.
"""

from __future__ import annotations

import base64
import io
import os
import struct
import uuid
import wave

import pytest
from fastapi.testclient import TestClient

from app.db import Project, Scene, SessionLocal, init_db
from app.feature_flags import FeatureFlags

M29_FLAGS = [
    "STUDIO_FEATURE_DIRECTOR_TIMELINE_V1",
    "STUDIO_FEATURE_AUDIO_PRODUCTION_V1",
    "STUDIO_FEATURE_EDITING_PRODUCTION_V1",
]


def make_wav_bytes(*, seconds: float = 1.0, rate: int = 48000, freq: int = 440) -> bytes:
    """Real PCM WAV bytes (not a stub header) so duration parsing is meaningful."""
    frames = int(rate * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        samples = bytearray()
        for n in range(frames):
            # Simple triangle ramp; audible, deterministic, no numpy dependency.
            value = int(8000 * (((n * freq * 2) // rate) % 2 and 1 or -1))
            samples += struct.pack("<h", value)
        handle.writeframes(bytes(samples))
    return buf.getvalue()


@pytest.fixture()
def enable_flags(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1", "1")
    for flag in M29_FLAGS:
        monkeypatch.setenv(flag, "1")
    monkeypatch.delenv("ADEPT_M29_FIXTURE_MODE", raising=False)
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    yield
    ff.feature_flags = FeatureFlags.from_env(os.environ)


@pytest.fixture()
def project_scene(enable_flags):
    init_db()
    from app.codirector.m29.db import ensure_m29_tables

    ensure_m29_tables()
    project_id = f"proj-{uuid.uuid4().hex[:10]}"
    scene_id = f"scene-{uuid.uuid4().hex[:10]}"
    session = SessionLocal()
    session.merge(Project(id=project_id, name="B4 Audio Timeline"))
    session.merge(
        Scene(
            id=scene_id,
            project_id=project_id,
            index=0,
            name="Scene 1",
            prompt="Empty studio at dawn",
            duration_sec=6.0,
        )
    )
    session.commit()
    try:
        yield project_id, scene_id, session
    finally:
        session.close()


@pytest.fixture()
def api(enable_flags) -> TestClient:
    from app.main import app

    return TestClient(app)


def _director(api: TestClient, project_id: str, scene_id: str) -> dict:
    res = api.get(f"/api/projects/{project_id}/scenes/{scene_id}/director")
    assert res.status_code == 200, res.text
    return res.json()


def test_import_places_sfx_cue_on_director_timeline(api, project_scene):
    project_id, scene_id, _session = project_scene
    payload = base64.b64encode(make_wav_bytes(seconds=1.5)).decode("ascii")

    res = api.post(
        "/api/codirector/m29/audio/import",
        json={
            "projectId": project_id,
            "contentBase64": payload,
            "filename": "door-slam.wav",
            "kind": "sfx",
            "sceneId": scene_id,
            "startSec": 1.0,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["imported"] is True
    assert body["timelinePlaced"] is True
    assert body["fixture"] is False
    assert body["measuredDurationSec"] == pytest.approx(1.5, abs=0.01)

    director = _director(api, project_id, scene_id)
    sfx = director["sfx_clips"]
    assert len(sfx) == 1
    assert sfx[0]["asset_id"] == body["assetId"]
    assert sfx[0]["start"] == pytest.approx(1.0)
    assert sfx[0]["length"] == pytest.approx(1.5, abs=0.01)
    # Dialogue/music track untouched by an sfx import.
    assert director["audio_clips"] == []


def test_import_dialogue_lands_on_audio_track(api, project_scene):
    project_id, scene_id, _session = project_scene
    payload = base64.b64encode(make_wav_bytes(seconds=0.5)).decode("ascii")

    res = api.post(
        "/api/codirector/m29/audio/import",
        json={
            "projectId": project_id,
            "contentBase64": payload,
            "kind": "dialogue",
            "sceneId": scene_id,
        },
    )
    assert res.status_code == 200, res.text
    director = _director(api, project_id, scene_id)
    assert len(director["audio_clips"]) == 1
    assert director["sfx_clips"] == []


def test_placement_persists_across_sessions(api, project_scene):
    project_id, scene_id, session = project_scene
    payload = base64.b64encode(make_wav_bytes(seconds=0.4)).decode("ascii")
    res = api.post(
        "/api/codirector/m29/audio/import",
        json={
            "projectId": project_id,
            "contentBase64": payload,
            "kind": "sfx",
            "sceneId": scene_id,
        },
    )
    assert res.status_code == 200, res.text
    asset_id = res.json()["assetId"]

    session.close()
    fresh = SessionLocal()
    try:
        scene = fresh.get(Scene, scene_id)
        assert scene is not None
        assert asset_id in (scene.director_json or "")
    finally:
        fresh.close()

    # And through the read API after the write session is gone.
    assert _director(api, project_id, scene_id)["sfx_clips"][0]["asset_id"] == asset_id


def test_import_rejects_non_wav_bytes(api, project_scene):
    project_id, scene_id, _session = project_scene
    res = api.post(
        "/api/codirector/m29/audio/import",
        json={
            "projectId": project_id,
            "contentBase64": base64.b64encode(b"not audio at all").decode("ascii"),
            "sceneId": scene_id,
        },
    )
    assert res.status_code == 400
    assert "RIFF" in res.json()["detail"]


def test_promote_cue_moves_existing_cue_onto_timeline(api, project_scene):
    project_id, scene_id, _session = project_scene
    payload = base64.b64encode(make_wav_bytes(seconds=0.6)).decode("ascii")
    # Import without a scene: a real asset and a real cue, but nothing on the timeline.
    imported = api.post(
        "/api/codirector/m29/audio/import",
        json={"projectId": project_id, "contentBase64": payload, "kind": "sfx"},
    )
    assert imported.status_code == 200, imported.text
    cue_id = imported.json()["cueId"]
    assert imported.json()["timelinePlaced"] is False
    assert _director(api, project_id, scene_id)["sfx_clips"] == []

    promoted = api.post(
        f"/api/codirector/m29/audio/cues/{cue_id}/promote",
        json={"projectId": project_id, "sceneId": scene_id, "volume": 0.6},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["timelinePlaced"] is True

    clips = _director(api, project_id, scene_id)["sfx_clips"]
    assert len(clips) == 1
    assert clips[0]["volume"] == pytest.approx(0.6)

    cues = api.get(f"/api/codirector/m29/audio/cues?projectId={project_id}").json()["cues"]
    assert [c["status"] for c in cues if c["id"] == cue_id] == ["placed"]


def test_promote_refuses_cue_without_a_real_asset(api, project_scene, monkeypatch):
    """A fixture cue has an id but no file — promoting it would fake finished sound work."""
    project_id, scene_id, _session = project_scene
    monkeypatch.setenv("ADEPT_M29_FIXTURE_MODE", "1")

    generated = api.post(
        "/api/codirector/m29/audio/generate",
        json={
            "projectId": project_id,
            "kind": "sfx",
            "prompt": "door slam",
            "sceneId": scene_id,
        },
    )
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["fixture"] is True
    assert body["timelinePlaced"] is False
    assert _director(api, project_id, scene_id)["sfx_clips"] == []

    res = api.post(
        f"/api/codirector/m29/audio/cues/{body['cueId']}/promote",
        json={"projectId": project_id, "sceneId": scene_id},
    )
    assert res.status_code == 409
    assert "no file on disk" in res.json()["detail"]
    assert _director(api, project_id, scene_id)["sfx_clips"] == []


def test_revise_gain_updates_cue_and_timeline_clip(api, project_scene):
    project_id, scene_id, _session = project_scene
    payload = base64.b64encode(make_wav_bytes(seconds=0.3)).decode("ascii")
    imported = api.post(
        "/api/codirector/m29/audio/import",
        json={
            "projectId": project_id,
            "contentBase64": payload,
            "kind": "music",
            "sceneId": scene_id,
            "volume": 1.0,
        },
    )
    assert imported.status_code == 200, imported.text
    cue_id = imported.json()["cueId"]

    res = api.post(
        f"/api/codirector/m29/audio/cues/{cue_id}/gain",
        json={"projectId": project_id, "volume": 0.25},
    )
    assert res.status_code == 200, res.text
    assert res.json()["timelineUpdated"] is True

    clips = _director(api, project_id, scene_id)["audio_clips"]
    assert len(clips) == 1, "revising gain must not duplicate the clip"
    assert clips[0]["volume"] == pytest.approx(0.25)

    cues = api.get(f"/api/codirector/m29/audio/cues?projectId={project_id}").json()["cues"]
    cue = next(c for c in cues if c["id"] == cue_id)
    assert cue["metadata"]["volume"] == pytest.approx(0.25)


def test_audio_import_requires_the_flag(monkeypatch):
    monkeypatch.delenv("STUDIO_FEATURE_AUDIO_PRODUCTION_V1", raising=False)
    import app.feature_flags as ff
    from app.main import app

    ff.feature_flags = FeatureFlags.from_env({})
    try:
        client = TestClient(app)
        res = client.post(
            "/api/codirector/m29/audio/import",
            json={"projectId": "nope", "contentBase64": ""},
        )
        assert res.status_code == 404
    finally:
        ff.feature_flags = FeatureFlags.from_env(os.environ)
