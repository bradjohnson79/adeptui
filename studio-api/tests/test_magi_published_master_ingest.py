"""Published-master ingest — VIDEO/AUDIO only, no Timeline batch clips."""

from __future__ import annotations

import uuid

from app.db import Asset, SessionLocal, init_db
from app.director_timeline_w46 import store
from app.director_timeline_w46.contracts import ScenePublishState
from app.magi.published_master_ingest import ingest_published_master, is_production_artifact
from app.magi.sequence.store import get_sequence, save_sequence


def _create_project(client, name: str = "MAGI Ingest") -> str:
    res = client.post("/api/projects", json={"name": name, "global_prompt": "Test."})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _first_scene(client, project_id: str) -> dict:
    scenes = client.get(f"/api/projects/{project_id}").json()["scenes"]
    assert scenes
    return scenes[0]


def _seed_asset(project_id: str, *, tag: str = "pub-master", kind: str = "video") -> str:
    init_db()
    db = SessionLocal()
    try:
        asset_id = str(uuid.uuid4())
        db.add(
            Asset(
                id=asset_id,
                project_id=project_id,
                tag=tag,
                kind=kind,
                filename=f"{tag}.mp4",
                path="",
            )
        )
        db.commit()
        return asset_id
    finally:
        db.close()


def _publish(project_id: str, scene_id: str, asset_id: str) -> None:
    init_db()
    db = SessionLocal()
    try:
        payload = store.load_master(db, project_id, scene_id)
        assert payload.get("ok"), payload
        from app.director_timeline_w46.contracts import SceneTimelineMaster

        master_obj = SceneTimelineMaster.model_validate(payload["master"])
        master_obj.scenePublish = ScenePublishState(
            publishedAssetId=asset_id,
            publishedAt="2026-09-14T00:00:00Z",
            sourceSceneStitchAssetId=asset_id,
            lifecycleStatusSnapshot="SCENE_FINISHED",
            contentFingerprint="fp",
            version=1,
        )
        store.save_master(db, project_id, scene_id, master_obj)
    finally:
        db.close()


def _fake_probe(_path):
    return {
        "fps": 24.0,
        "duration": 30.0,
        "frames": 720,
        "width": 864,
        "height": 480,
        "hasAudio": True,
    }


def test_production_artifact_detection():
    assert is_production_artifact({"batchBlockId": "bb_1", "name": "Shot"})
    assert is_production_artifact({"name": "Scene 1 — Batch 1"})
    assert is_production_artifact({"generationId": "g1"})
    assert not is_production_artifact({"ingestRole": "published_master", "name": "Master"})
    assert not is_production_artifact({"ingestRole": "music", "name": "Score"})


def test_ingest_rejects_unpublished_scene(client):
    project_id = _create_project(client)
    scene = _first_scene(client, project_id)
    res = client.post(f"/api/magi/projects/{project_id}/scenes/{scene['id']}/ingest-published-master")
    assert res.status_code == 409, res.text
    assert res.json()["detail"]["error"]["code"] == "PUBLISHED_MASTER_REQUIRED"


def test_ingest_published_master_strips_batch_clips_and_binds_audio(client):
    project_id = _create_project(client, "12B ingest")
    scene = _first_scene(client, project_id)
    pub_id = _seed_asset(project_id, tag="Scene 12B — Quarters Interview")
    batch_id = _seed_asset(project_id, tag="Scene 1 — Batch 1")
    _publish(project_id, scene["id"], pub_id)

    seq = get_sequence(project_id)
    video_trk = next(t for t in seq["tracks"] if t["kind"] == "video")
    seq["clips"] = [
        {
            "id": "clip_korri_b1_ext",
            "trackId": video_trk["id"],
            "assetId": batch_id,
            "name": "Scene 1 — Batch 1",
            "startFrame": 0,
            "durationFrames": 120,
            "inPoint": 0,
            "outPoint": 120,
            "batchBlockId": "bb_1",
            "generationId": "gen_1",
        },
        {
            "id": "clip_12b_loose",
            "trackId": video_trk["id"],
            "assetId": pub_id,
            "name": "Scene 12B — Quarters Interview",
            "startFrame": 240,
            "durationFrames": 120,
            "inPoint": 0,
            "outPoint": 120,
        },
    ]
    save_sequence(project_id, seq)

    init_db()
    db = SessionLocal()
    try:
        result = ingest_published_master(db, project_id, scene["id"], probe=_fake_probe)
    finally:
        db.close()

    assert result["ok"] is True
    assert result["publishedAssetId"] == pub_id
    assert result["hasAudio"] is True
    assert result["durationFrames"] == 720
    clips = result["sequence"]["clips"]
    roles = {c.get("ingestRole") for c in clips}
    assert "published_master" in roles
    assert "published_master_audio" in roles
    assert not any(c.get("batchBlockId") for c in clips)
    assert not any("Batch" in str(c.get("name") or "") for c in clips)
    video = next(c for c in clips if c.get("ingestRole") == "published_master")
    audio = next(c for c in clips if c.get("ingestRole") == "published_master_audio")
    assert video["assetId"] == pub_id
    assert audio["assetId"] == pub_id
    assert video["durationFrames"] == 720
    assert audio["durationFrames"] == 720
    assert video["startFrame"] == 0


def test_ingest_idempotent_when_already_current(client):
    project_id = _create_project(client, "Idempotent ingest")
    scene = _first_scene(client, project_id)
    pub_id = _seed_asset(project_id)
    _publish(project_id, scene["id"], pub_id)
    init_db()
    db = SessionLocal()
    try:
        first = ingest_published_master(db, project_id, scene["id"], probe=_fake_probe)
        second = ingest_published_master(db, project_id, scene["id"], probe=_fake_probe)
    finally:
        db.close()
    assert first["ok"] and second["ok"]
    assert second.get("idempotent") is True
    assert len(first["sequence"]["clips"]) == len(second["sequence"]["clips"])


def test_ingest_aligns_when_url_scene_unpublished_but_sequence_bound(client):
    project_id = _create_project(client, "Align ingest")
    published_scene = _first_scene(client, project_id)
    other = client.post(
        f"/api/projects/{project_id}/scenes",
        json={"name": "Unpublished", "prompt": "Later."},
    )
    assert other.status_code == 200, other.text
    unpublished_id = other.json()["id"]
    pub_id = _seed_asset(project_id)
    _publish(project_id, published_scene["id"], pub_id)

    init_db()
    db = SessionLocal()
    try:
        first = ingest_published_master(db, project_id, published_scene["id"], probe=_fake_probe)
        aligned = ingest_published_master(db, project_id, unpublished_id, probe=_fake_probe)
    finally:
        db.close()

    assert first["ok"] is True
    assert aligned["ok"] is True
    assert aligned.get("alignedSceneId") == published_scene["id"]
    assert aligned["publishedAssetId"] == pub_id
    res = client.post(
        f"/api/magi/projects/{project_id}/scenes/{unpublished_id}/ingest-published-master"
    )
    assert res.status_code == 200, res.text
    assert res.json()["publishedAssetId"] == pub_id


def test_ingest_preserves_music_and_sfx_finishing_clips(client):
    project_id = _create_project(client, "Keep MAGI stems")
    scene = _first_scene(client, project_id)
    pub_id = _seed_asset(project_id)
    music_id = _seed_asset(project_id, tag="music-cue", kind="audio")
    sfx_id = _seed_asset(project_id, tag="room-tone", kind="audio")
    _publish(project_id, scene["id"], pub_id)
    init_db()
    db = SessionLocal()
    try:
        first = ingest_published_master(db, project_id, scene["id"], probe=_fake_probe)
        seq = first["sequence"]
        music_trk = next(t for t in seq["tracks"] if t["kind"] == "music")
        sfx_trk = next(t for t in seq["tracks"] if t["kind"] == "sfx")
        seq["clips"] = list(seq["clips"]) + [
            {
                "id": "clip_music_keep",
                "trackId": music_trk["id"],
                "assetId": music_id,
                "name": "Music — MAGI",
                "startFrame": 0,
                "durationFrames": 720,
                "inPoint": 0,
                "outPoint": 720,
                "ingestRole": "music",
                "sceneId": scene["id"],
            },
            {
                "id": "clip_sfx_keep",
                "trackId": sfx_trk["id"],
                "assetId": sfx_id,
                "name": "Sfx — MAGI",
                "startFrame": 0,
                "durationFrames": 144,
                "inPoint": 0,
                "outPoint": 144,
                "ingestRole": "sfx",
                "sceneId": scene["id"],
            },
        ]
        seq["clips"].append(
            {
                "id": "clip_batch_drop",
                "trackId": next(t["id"] for t in seq["tracks"] if t["kind"] == "video"),
                "assetId": pub_id,
                "name": "Batch 2 candidate",
                "startFrame": 0,
                "durationFrames": 48,
                "inPoint": 0,
                "outPoint": 48,
                "batchBlockId": "batch-2",
            }
        )
        save_sequence(project_id, seq)
        again = ingest_published_master(db, project_id, scene["id"], probe=_fake_probe)
    finally:
        db.close()

    assert again["ok"] is True
    roles = {c.get("ingestRole") for c in again["sequence"]["clips"]}
    assert "music" in roles
    assert "sfx" in roles
    assert any(c.get("assetId") == music_id for c in again["sequence"]["clips"])
    assert any(c.get("assetId") == sfx_id for c in again["sequence"]["clips"])
    assert not any(c.get("batchBlockId") for c in again["sequence"]["clips"])


def test_ingest_http_accepts_published_scene(client):
    project_id = _create_project(client, "HTTP ingest")
    scene = _first_scene(client, project_id)
    pub_id = _seed_asset(project_id)
    _publish(project_id, scene["id"], pub_id)
    res = client.post(f"/api/magi/projects/{project_id}/scenes/{scene['id']}/ingest-published-master")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ok"] is True
    assert data["publishedAssetId"] == pub_id
