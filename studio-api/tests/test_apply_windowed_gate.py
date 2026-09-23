"""Endpoint tests for the windowed media retake apply path and speaker gate fix."""

from __future__ import annotations

import json

import pytest

from app.lipsync_tracks import LipSyncClip, LipSyncTrack, LipSyncTracks, dumps_lipsync_tracks


def _track_payload(
    *,
    enabled: bool = True,
    audio_asset_id: str = "audio-1",
    character_id: str | None = None,
    clips: list[dict] | None = None,
) -> dict:
    track = LipSyncTrack(
        slot=1,
        enabled=enabled,
        audio_asset_id=audio_asset_id,
        character_id=character_id,
        clips=[
            LipSyncClip(
                id="clip-1",
                start=1.0,
                length=2.0,
                audio_asset_id=audio_asset_id,
                character_id=character_id,
            )
        ],
    )
    return json.loads(dumps_lipsync_tracks(LipSyncTracks(tracks=[track])))


def _setup_scene(client, *, character_id: str | None = None, duration_sec: float = 10.0):
    created = client.post("/api/projects", json={"name": "Windowed Retake Test"})
    assert created.status_code == 200, created.text
    pid = created.json()["id"]

    list_resp = client.get(f"/api/projects/{pid}/scenes")
    assert list_resp.status_code == 200
    sid = list_resp.json()[0]["id"]

    tracks_payload = _track_payload(character_id=character_id)
    patch = client.patch(
        f"/api/projects/{pid}/scenes/{sid}",
        json={
            "duration_sec": duration_sec,
            "lipsync_tracks_json": json.dumps(tracks_payload),
            "director_json": json.dumps({"prompt_segments": [], "audio_clips": [], "sfx_clips": [], "lipsync": tracks_payload}),
        },
    )
    assert patch.status_code == 200, patch.text
    return pid, sid


def test_scene_column_track_without_character_returns_speaker_required(client):
    pid, sid = _setup_scene(client, character_id=None)
    res = client.post(f"/api/projects/{pid}/scenes/{sid}/lipsync-tracks/apply")
    assert res.status_code == 400
    assert "LIPSYNC_SPEAKER_REQUIRED" in res.text or "Assign a character" in res.text


def test_bound_track_windowed_enqueues_media_retake(client, monkeypatch):
    monkeypatch.setenv("ADEPT_LEGACY_LIPSYNC", "1")
    pid, sid = _setup_scene(client, character_id="char-korri")
    res = client.post(
        f"/api/projects/{pid}/scenes/{sid}/lipsync-tracks/apply",
        json={"mode": "windowed"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kind"] == "media_retake"
    message = json.loads(body.get("message") or "{}")
    assert message["mode"] == "windowed"
    assert message["scene_id"] == sid


def test_legacy_modes_are_410_without_the_legacy_flag(client):
    pid, sid = _setup_scene(client, character_id="char-korri")
    for mode in ("legacy", "windowed"):
        res = client.post(
            f"/api/projects/{pid}/scenes/{sid}/lipsync-tracks/apply",
            json={"mode": mode},
        )
        assert res.status_code == 410, res.text
        assert "Performance Retake" in res.text


def test_bound_track_no_body_defaults_to_performance_retake(client):
    """Default mode is now performance_retake; without a retake body the
    derived spec has no character sheets, so validation fails with 400 —
    never a silent legacy fallback."""
    pid, sid = _setup_scene(client, character_id="char-korri")
    res = client.post(f"/api/projects/{pid}/scenes/{sid}/lipsync-tracks/apply")
    assert res.status_code == 400, res.text
    assert "character sheet" in res.text


def test_windowed_room_tone_outside_scene_duration_returns_400(client, monkeypatch):
    monkeypatch.setenv("ADEPT_LEGACY_LIPSYNC", "1")
    pid, sid = _setup_scene(client, character_id="char-korri", duration_sec=10.0)
    res = client.post(
        f"/api/projects/{pid}/scenes/{sid}/lipsync-tracks/apply",
        json={"mode": "windowed", "roomToneStart": 8.0, "roomToneEnd": 12.0},
    )
    assert res.status_code == 400


def test_bogus_mode_returns_400(client):
    pid, sid = _setup_scene(client, character_id="char-korri")
    res = client.post(
        f"/api/projects/{pid}/scenes/{sid}/lipsync-tracks/apply",
        json={"mode": "bogus"},
    )
    assert res.status_code == 400
