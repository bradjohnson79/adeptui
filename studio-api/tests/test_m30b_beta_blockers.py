"""M3.0b beta blockers B1-B3 regression tests.

B1: image/video generate must not mint an asset id for an artifact that does not exist.
B2: provider health must serialise `unifiedExperienceEnabled` so the M2.14 shell can render.
B3: `audio/process` must apply the ops the HTTP contract accepts, instead of silently
    falling through to a stream copy and still reporting `processed`.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import uuid
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import Asset, Project, SessionLocal, init_db
from app.feature_flags import FeatureFlags

M29_FLAGS = [
    "STUDIO_FEATURE_IMAGE_PRODUCTION_V1",
    "STUDIO_FEATURE_FRAME_PRODUCTION_V1",
    "STUDIO_FEATURE_VIDEO_PRODUCTION_V1",
    "STUDIO_FEATURE_DIRECTOR_TIMELINE_V1",
    "STUDIO_FEATURE_AUDIO_PRODUCTION_V1",
    "STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1",
]

PROJECT_ID = "proj-m30b"


@pytest.fixture()
def production_env(monkeypatch: pytest.MonkeyPatch):
    """M2.9 flags on, fixture/E2E paths off — the shape a beta user would hit."""
    monkeypatch.delenv("ADEPT_M29_FIXTURE_MODE", raising=False)
    monkeypatch.delenv("STUDIO_E2E", raising=False)
    for flag in M29_FLAGS:
        monkeypatch.setenv(flag, "1")
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    yield
    ff.feature_flags = FeatureFlags.from_env(os.environ)


@pytest.fixture()
def db(production_env):
    init_db()
    from app.codirector.m29.db import ensure_m29_tables

    ensure_m29_tables()
    session = SessionLocal()
    session.merge(Project(id=PROJECT_ID, name="M3.0b blockers"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    from app.main import app

    return TestClient(app)


@pytest.fixture()
def no_providers(monkeypatch: pytest.MonkeyPatch):
    """No generative provider is reachable — the state every M3.0b run was measured in."""
    from app.codirector.m29 import providers

    monkeypatch.setattr(providers, "comfy_available", lambda: False)
    monkeypatch.setattr(providers, "fal_key_present", lambda db=None: False)


def _version_count(db, project_id: str = PROJECT_ID) -> int:
    return int(
        db.execute(
            text("SELECT COUNT(*) FROM m29_asset_versions WHERE project_id = :pid"),
            {"pid": project_id},
        ).scalar()
        or 0
    )


# ---------------------------------------------------------------------------
# B1 - no phantom asset ids
# ---------------------------------------------------------------------------


def test_image_generate_without_provider_reports_provider_missing(db, no_providers):
    from app.codirector.m29.image.service import ImageService

    before = _version_count(db)
    out = ImageService.generate(db, project_id=PROJECT_ID, prompt="honest still")

    assert out["fixture"] is False
    assert out["providerMissing"] is True
    assert out["awaitingProvider"] is True
    assert out["assetId"] is None
    assert out["versionId"] is None
    assert out["status"] == "queued"
    assert out["jobId"]
    db.expire_all()
    assert _version_count(db) == before, "no asset version may be minted without an artifact"


def test_video_generate_without_provider_reports_provider_missing(db, no_providers):
    from app.codirector.m29.video.service import VideoService

    before = _version_count(db)
    out = VideoService.generate(db, project_id=PROJECT_ID, prompt="honest dolly")

    assert out["fixture"] is False
    assert out["providerMissing"] is True
    assert out["awaitingProvider"] is True
    assert out["assetId"] is None
    assert out["versionId"] is None
    assert out["status"] == "queued"
    db.expire_all()
    assert _version_count(db) == before


def test_image_generate_with_provider_still_withholds_asset_id(db, monkeypatch):
    """Even when Comfy is reachable, the queued response predates the artifact."""
    from app.codirector.m29 import providers
    from app.codirector.m29.image import service as image_service

    monkeypatch.setattr(providers, "comfy_available", lambda: True)
    monkeypatch.setattr(
        image_service,
        "enqueue_executive_job",
        lambda *a, **k: type("Job", (), {"id": "job-fake"})(),
    )
    out = image_service.ImageService.generate(db, project_id=PROJECT_ID, prompt="queued")

    assert out["providerMissing"] is False
    assert out["assetId"] is None
    assert out["status"] == "queued"


def test_generate_api_never_returns_a_fabricated_asset(client, db, no_providers):
    for path, body in (
        ("/api/codirector/m29/image/generate", {"projectId": PROJECT_ID, "prompt": "api still"}),
        (
            "/api/codirector/m29/video/generate",
            {"projectId": PROJECT_ID, "prompt": "api shot", "mode": "text_to_video"},
        ),
    ):
        res = client.post(path, json=body)
        assert res.status_code == 200, res.text
        out = res.json()
        assert out["fixture"] is False, path
        assert out["providerMissing"] is True, path
        assert out.get("assetId") is None, path
        assert db.get(Asset, out.get("assetId") or "missing") is None, path


def test_fixture_mode_still_produces_a_recorded_asset(db, monkeypatch):
    """The fixture path is env-gated and keeps working — honesty, not removal."""
    monkeypatch.setenv("ADEPT_M29_FIXTURE_MODE", "1")
    import app.feature_flags as ff

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    from app.codirector.m29.image.service import ImageService

    out = ImageService.generate(db, project_id=PROJECT_ID, prompt="fixture still")
    assert out["fixture"] is True
    assert out["assetId"]
    assert out["versionId"]


# ---------------------------------------------------------------------------
# B2 - unifiedExperienceEnabled reaches the UI
# ---------------------------------------------------------------------------


def test_provider_health_to_dict_serialises_unified_experience_flag():
    from app.codirector.providers.base import ProviderHealthResult

    health = ProviderHealthResult(
        provider_id="ollama",
        display_name="Ollama",
        status="Ready",
        reachable=True,
        endpoint="http://localhost:11434",
        selected_model="gemma",
        model_available=True,
    )
    payload = health.to_dict()
    for key in (
        "unifiedExperienceEnabled",
        "virtualEnvironmentStudioEnabled",
        "audioProductionEnabled",
        "directorTimelineEnabled",
    ):
        assert key in payload, key
        assert payload[key] is False

    health.unified_experience_enabled = True
    assert health.to_dict()["unifiedExperienceEnabled"] is True


def test_get_health_reads_unified_experience_from_the_feature_flag(monkeypatch):
    monkeypatch.setenv("STUDIO_FEATURE_CODIRECTOR_UNIFIED_EXPERIENCE_V1", "1")
    import app.feature_flags as ff
    from app.codirector import service as codirector_service

    ff.feature_flags = FeatureFlags.from_env(os.environ)
    monkeypatch.setattr(codirector_service, "feature_flags", ff.feature_flags)
    try:
        # An unknown provider id takes the degraded branch: no network, flags still applied.
        health = asyncio.run(codirector_service.get_health("not-a-provider"))
        assert health.to_dict()["unifiedExperienceEnabled"] is True
    finally:
        ff.feature_flags = FeatureFlags.from_env(os.environ)


# ---------------------------------------------------------------------------
# B3 - mix revise does real work
# ---------------------------------------------------------------------------


def test_audio_ops_accept_both_contract_and_executor_shapes():
    from app.codirector.m29.providers import normalize_audio_ops, validate_audio_ops

    assert normalize_audio_ops([{"op": "normalize"}]) == ["normalize"]
    assert normalize_audio_ops(["Normalize"]) == ["normalize"]
    assert validate_audio_ops([{"op": "cleanup"}, "loudnorm"]) == ["cleanup", "loudnorm"]
    with pytest.raises(ValueError):
        validate_audio_ops([{"op": "reverse-time"}])
    with pytest.raises(ValueError):
        validate_audio_ops([{}])


def test_audio_process_rejects_invalid_ops_with_422(client):
    res = client.post(
        "/api/codirector/m29/audio/process",
        json={"projectId": PROJECT_ID, "assetId": "asset-x", "ops": [{"op": "reverse-time"}]},
    )
    assert res.status_code == 422, res.text


def test_audio_process_accepts_dict_ops_and_echoes_them(client):
    res = client.post(
        "/api/codirector/m29/audio/process",
        json={"projectId": PROJECT_ID, "assetId": "asset-x", "ops": [{"op": "normalize"}]},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["appliedOps"] == ["normalize"]
    assert body["status"] == "queued"


def _register_wav(db, path: Path, *, sample_rate: int = 44100, seconds: float = 3.0) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x10" * frames)
    asset_id = str(uuid.uuid4())
    db.add(
        Asset(
            id=asset_id,
            project_id=PROJECT_ID,
            tag="m30b_stem",
            kind="audio",
            filename=path.name,
            path=str(path),
        )
    )
    db.commit()
    return asset_id


def test_dict_ops_reach_the_loudnorm_branch(db, tmp_path, monkeypatch):
    """Executor invocation is asserted directly, so the test runs without ffmpeg."""
    from app.codirector.m29 import providers
    from app import media_ops

    asset_id = _register_wav(db, tmp_path / "stem.wav")
    calls: list[list[str]] = []

    def fake_run_ffmpeg(args: list[str]) -> None:
        calls.append(list(args))
        Path(args[-1]).write_bytes(b"RIFF")

    monkeypatch.setattr(providers, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(media_ops, "run_ffmpeg", fake_run_ffmpeg)

    out = providers.process_audio_ffmpeg(
        db, project_id=PROJECT_ID, payload={"assetId": asset_id, "ops": [{"op": "normalize"}]}
    )

    assert calls, "the executor must run ffmpeg, not fall through silently"
    assert "loudnorm=I=-16:TP=-1.5:LRA=11" in calls[0]
    assert "48000" in calls[0]
    assert out["loudnormApplied"] is True
    assert out["appliedOps"] == ["normalize"]
    assert out["status"] == "processed"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_dict_ops_change_the_output_sample_rate(db, tmp_path):
    from app.codirector.m29 import providers

    asset_id = _register_wav(db, tmp_path / "real-stem.wav")
    out = providers.process_audio_ffmpeg(
        db, project_id=PROJECT_ID, payload={"assetId": asset_id, "ops": [{"op": "normalize"}]}
    )
    with wave.open(out["outputPath"], "rb") as wav:
        assert wav.getframerate() == 48000
    assert out["loudnormApplied"] is True
