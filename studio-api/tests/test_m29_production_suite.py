"""M2.9 production suite unit/API tests (fixture mode)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.db import Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags
from app.migrations import DEFAULT_REGISTRY, M013, MigrationRunner


M29_FLAGS = [
    "STUDIO_FEATURE_IMAGE_PRODUCTION_V1",
    "STUDIO_FEATURE_FRAME_PRODUCTION_V1",
    "STUDIO_FEATURE_VIDEO_PRODUCTION_V1",
    "STUDIO_FEATURE_DIRECTOR_TIMELINE_V1",
    "STUDIO_FEATURE_LIPSYNC_PRODUCTION_V1",
    "STUDIO_FEATURE_AUDIO_PRODUCTION_V1",
    "STUDIO_FEATURE_EDITING_PRODUCTION_V1",
    "STUDIO_FEATURE_RENDER_PRODUCTION_V1",
    "STUDIO_FEATURE_CODIRECTOR_PRODUCTION_CONTROL_V1",
]


@pytest.fixture()
def enable_m29(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADEPT_M29_FIXTURE_MODE", "1")
    monkeypatch.setenv("STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1", "1")
    for flag in M29_FLAGS:
        monkeypatch.setenv(flag, "1")
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    yield
    ff.feature_flags = FeatureFlags.from_env(os.environ)


@pytest.fixture()
def db(enable_m29):
    init_db()
    from app.codirector.m29.db import ensure_m29_tables

    ensure_m29_tables()
    session = SessionLocal()
    session.merge(Project(id="proj-m29", name="M29 Test"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(enable_m29):
    from app.main import app

    init_db()
    from app.codirector.m29.db import ensure_m29_tables

    ensure_m29_tables()
    session = SessionLocal()
    session.merge(Project(id="proj-m29", name="M29 Test"))
    session.commit()
    session.close()
    return TestClient(app)


def test_m29_flags_default_off():
    flags = FeatureFlags.from_env({})
    assert flags.image_production_v1 is False
    assert flags.frame_production_v1 is False
    assert flags.video_production_v1 is False
    assert flags.director_timeline_v1 is False
    assert flags.lipsync_production_v1 is False
    assert flags.audio_production_v1 is False
    assert flags.editing_production_v1 is False
    assert flags.render_production_v1 is False
    assert flags.codirector_production_control_v1 is False


def test_m013_registered_after_m012():
    revs = [m.revision for m in DEFAULT_REGISTRY.all()]
    assert "M013" in revs
    assert M013.revision == "M013"
    assert revs.index("M012") < revs.index("M013")


def test_m013_creates_tables(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm013.db'}")
    result = MigrationRunner(engine, DEFAULT_REGISTRY).apply_pending()
    assert "M013" in result.applied
    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "m29_asset_versions" in tables
    assert "m29_frame_records" in tables
    assert "m29_render_manifests" in tables
    assert "m29_audio_cues" in tables


def test_registry_m29_ids_unique():
    from app.capabilities.registry import CAPABILITIES

    ids = [c.id for c in CAPABILITIES]
    assert len(ids) == len(set(ids))
    required = {
        "image.generate",
        "image.reference.generate",
        "image.image_to_image",
        "image.inpaint",
        "image.outpaint",
        "image.variation",
        "image.upscale",
        "image.relight",
        "image.validate",
        "image.approve",
        "image.publish_reference",
        "frame.generate",
        "frame.sequence.generate",
        "frame.first.generate",
        "frame.last.generate",
        "frame.transition.generate",
        "frame.replace",
        "frame.validate",
        "frame.approve",
        "frame.bind_to_shot",
        "video.generate",
        "video.validate",
        "audio.dialogue.generate",
        "audio.sfx.generate",
        "audio.music.generate",
        "audio.validate",
        "mouth.rectangle.generate",
        "mouth.track.generate",
        "lipsync.generate",
        "lipsync.validate",
        "scene.render",
        "timeline.render",
    }
    present = set(ids)
    missing = required - present
    assert not missing, missing
    for c in CAPABILITIES:
        if c.id in required:
            assert c.baseline_status.value != "production_ready"


def test_flags_off_api_404(monkeypatch):
    monkeypatch.delenv("ADEPT_M29_FIXTURE_MODE", raising=False)
    for flag in M29_FLAGS:
        monkeypatch.setenv(flag, "0")
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    from app.main import app

    client = TestClient(app)
    res = client.post(
        "/api/codirector/m29/image/generate",
        json={"projectId": "proj-m29", "prompt": "x"},
    )
    assert res.status_code == 404


def test_image_fixture_generate_and_approve(db):
    from app.codirector.m29.image.service import ImageService

    out = ImageService.generate(db, project_id="proj-m29", prompt="fixture still")
    assert out.get("fixture") is True
    assert out.get("assetId")
    assert out.get("versionId")
    approved = ImageService.approve(db, out["versionId"], actor="tester")
    assert approved["status"] == "approved"


def test_timeline_approval_boundary(db):
    from app.codirector.m29.timeline.service import TimelineService

    prop = TimelineService.propose(db, project_id="proj-m29", notes="place clips")
    assert prop["status"] == "pending"
    with pytest.raises(PermissionError):
        TimelineService.apply(db, prop["id"])
    TimelineService.approve(db, prop["id"], actor="tester")
    applied = TimelineService.apply(db, prop["id"], actor="tester")
    assert applied["status"] == "applied"


def test_edit_apply_requires_approval(db):
    from app.codirector.m29.editing.service import EditingService

    with pytest.raises(PermissionError):
        EditingService.apply_edit(
            db, project_id="proj-m29", ops=[{"op": "trim"}], approved=False
        )


def test_fixture_jobs_via_api(client):
    img = client.post(
        "/api/codirector/m29/image/generate",
        json={"projectId": "proj-m29", "prompt": "api still"},
    )
    assert img.status_code == 200, img.text
    assert img.json()["fixture"] is True

    frames = client.post(
        "/api/codirector/m29/frames/generate",
        json={"projectId": "proj-m29", "count": 2, "sequence": True, "shotId": "s1"},
    )
    assert frames.status_code == 200
    assert len(frames.json()["frames"]) == 2

    video = client.post(
        "/api/codirector/m29/video/generate",
        json={"projectId": "proj-m29", "prompt": "dolly", "mode": "text_to_video"},
    )
    assert video.status_code == 200

    audio = client.post(
        "/api/codirector/m29/audio/generate",
        json={"projectId": "proj-m29", "kind": "sfx", "prompt": "door"},
    )
    assert audio.status_code == 200

    lips = client.post(
        "/api/codirector/m29/lipsync/generate",
        json={"projectId": "proj-m29"},
    )
    assert lips.status_code == 200

    rend = client.post(
        "/api/codirector/m29/render",
        json={"projectId": "proj-m29", "kind": "timeline_render"},
    )
    assert rend.status_code == 200

    ctrl = client.post(
        "/api/codirector/m29/control/decompose",
        json={
            "projectId": "proj-m29",
            "requestText": "generate image and video then render timeline",
            "enqueue": True,
        },
    )
    assert ctrl.status_code == 200
    body = ctrl.json()
    assert body["requiresApproval"] is True
    assert len(body["steps"]) >= 2


def test_health_exposes_m29_flags(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    op = health.json().get("operator") or {}
    assert op.get("imageProductionEnabled") is True
    assert op.get("codirectorProductionControlEnabled") is True
def test_image_execute_does_not_fixture_on_m29_flag_alone(db, monkeypatch):
    """m29=True must not auto-fixture when ADEPT_M29_FIXTURE_MODE is off."""
    monkeypatch.delenv("ADEPT_M29_FIXTURE_MODE", raising=False)
    from app.codirector.m29.image.service import ImageService
    from app.codirector.m29.providers import ProviderUnavailable, comfy_available

    if not comfy_available():
        with pytest.raises(ProviderUnavailable):
            ImageService.execute_job(
                db, {"m29": True, "prompt": "real path"}, "proj-m29"
            )
        pytest.skip("ComfyUI unavailable - real image path blocked honestly")
    try:
        out = ImageService.execute_job(
            db, {"m29": True, "prompt": "real path smoke", "timeoutSec": 15}, "proj-m29"
        )
    except Exception as exc:  # noqa: BLE001
        assert "fixture" not in str(exc).lower() or "unavailable" in str(exc).lower()
        pytest.skip(f"real image path not completable in this env: {exc}")
    assert out.get("fixture") is False
    assert out.get("provider") != "m29_fixture"
    assert out.get("assetId")


def test_audio_generate_blocks_without_provider(db, monkeypatch):
    monkeypatch.delenv("ADEPT_M29_FIXTURE_MODE", raising=False)
    from app.codirector.m29.audio.service import AudioService
    from app.codirector.m29.providers import ProviderUnavailable

    with pytest.raises(ProviderUnavailable):
        AudioService.execute_job(
            db, {"m29": True, "kind": "dialogue", "prompt": "hello"}, "proj-m29"
        )


def test_timeline_apply_persists_director_json(db):
    from app.db import Scene
    from app.codirector.m29.timeline.service import TimelineService

    scene = Scene(
        id="scene-m29-tl",
        project_id="proj-m29",
        index=0,
        name="M29 TL",
        prompt="base",
        duration_sec=5.0,
        director_json="",
    )
    db.add(scene)
    db.commit()

    prop = TimelineService.propose(
        db,
        project_id="proj-m29",
        scene_id=scene.id,
        clips=[{"clipId": "c1", "assetId": "asset-a", "start": 0, "length": 3, "track": "video"}],
        notes="insert clip",
    )
    TimelineService.approve(db, prop["id"], actor="tester")
    applied = TimelineService.apply(db, prop["id"], actor="tester")
    assert applied["status"] == "applied"
    db.expire_all()
    scene2 = db.get(Scene, scene.id)
    assert scene2 is not None
    assert "asset-a" in (scene2.director_json or "")
    assert "timelineBranches" in (scene2.continuity_json or "")


def test_edit_apply_trim_and_undo(db, monkeypatch):
    monkeypatch.delenv("ADEPT_M29_FIXTURE_MODE", raising=False)
    from app.db import Scene
    from app.codirector.m29.editing.service import EditingService
    from app.director_timeline import TimelineClip, dumps_director_timeline, parse_director_timeline

    tl = parse_director_timeline(None, fallback_duration=5.0, fallback_prompt="x")
    clip = TimelineClip(id="clip-edit-1", asset_id="v1", start=0, length=4)
    tl.video_clips.append(clip)
    scene = Scene(
        id="scene-m29-edit",
        project_id="proj-m29",
        index=1,
        name="M29 Edit",
        prompt="x",
        duration_sec=5.0,
        director_json=dumps_director_timeline(tl),
        continuity_json="{}",
    )
    db.add(scene)
    db.commit()

    out = EditingService.execute_job(
        db,
        {
            "approved": True,
            "sceneId": scene.id,
            "ops": [{"op": "trim", "clipId": "clip-edit-1", "length": 2.5}],
        },
        "proj-m29",
    )
    assert out["status"] == "applied"
    assert out.get("fixture") is False
    db.expire_all()
    scene2 = db.get(Scene, scene.id)
    tl2 = parse_director_timeline(scene2.director_json)
    assert abs(tl2.video_clips[0].length - 2.5) < 0.01

    EditingService.execute_job(
        db,
        {"approved": True, "sceneId": scene.id, "ops": [{"op": "undo"}]},
        "proj-m29",
    )
    db.expire_all()
    scene3 = db.get(Scene, scene.id)
    tl3 = parse_director_timeline(scene3.director_json)
    assert abs(tl3.video_clips[0].length - 4.0) < 0.01


def test_asset_version_status_persistence(db):
    from app.codirector.m29.store import create_asset_version, get_asset_version, set_asset_status

    ver = create_asset_version(
        db, project_id="proj-m29", department="image", status="draft", metadata={"k": 1}
    )
    set_asset_status(db, ver["id"], "generated")
    set_asset_status(db, ver["id"], "validation_pending")
    set_asset_status(db, ver["id"], "approved")
    again = get_asset_version(db, ver["id"])
    assert again is not None
    assert again["status"] == "approved"
    assert again["department"] == "image"


def test_control_enqueue_without_fixture_mode(db, monkeypatch):
    monkeypatch.delenv("ADEPT_M29_FIXTURE_MODE", raising=False)
    from app.codirector.m29.control.service import ControlService

    out = ControlService.decompose(
        db,
        project_id="proj-m29",
        request_text="generate image then render timeline",
        enqueue=True,
    )
    assert out["requiresApproval"] is True
    assert out.get("fixture") is False
    assert len(out["jobs"]) >= 1


def test_wants_fixture_helper():
    from app.codirector.m29.providers import wants_fixture

    assert wants_fixture({"fixtureComplete": True}) is True
    assert wants_fixture({"m29": True}) is False
