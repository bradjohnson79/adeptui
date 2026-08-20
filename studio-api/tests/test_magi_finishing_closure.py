"""MAGI finishing closure — capabilities, jobs, finishing state, catalog, smoke."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from app.magi.jobs import ACTIVE, enqueue_job, find_active_duplicate
from app.magi.media import cleanup_dir, disk_preflight, magi_temp_root, new_temp_dir
from app.magi.realesrgan_runtime import CREATOR_UNAVAILABLE, COMPONENT_ID
from app.magi.sequence.store import empty_sequence, get_sequence, save_sequence
from app.magi.sequence.validation import parse_sequence
from app.magi.upscaling import ENGINE_GPU, apply_upscale, capabilities, upscale_frame
from app.setup.catalog import get_component


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _make_clip(path: Path, *, seconds: float = 1.0, audio: bool = True, size: str = "320x180") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=red:s={size}:d={seconds}",
    ]
    if audio:
        cmd.extend(["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"])
        cmd.extend(["-shortest"])
    cmd.extend(["-pix_fmt", "yuv420p", str(path)])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    assert proc.returncode == 0 and path.is_file(), proc.stderr[-400:]
    return path


def test_audio_duration_uses_clip_span_not_empty_timeline():
    from app.magi.audio_generate import _duration_for_range
    from app.magi.sequence.store import empty_sequence, save_sequence

    project_id = f"audio-dur-{uuid.uuid4().hex[:8]}"
    seq = empty_sequence(project_id)
    seq["durationFrames"] = 24 * 60
    seq["clips"] = [
        {
            "id": "clip_a",
            "trackId": seq["tracks"][0]["id"],
            "assetId": "asset-a",
            "name": "Short",
            "startFrame": 0,
            "durationFrames": 72,
            "inPoint": 0,
            "outPoint": 72,
        }
    ]
    save_sequence(project_id, seq)
    assert _duration_for_range(project_id, {"range": "entire"}) == 3.0
    assert _duration_for_range(project_id, {"range": "clip", "clipId": "clip_a"}) == 3.0


def test_catalog_has_magi_gpu_upscale():
    component = get_component(COMPONENT_ID)
    assert component.name == "MAGI GPU Upscaling"
    assert component.required is False
    assert component.category == "MAGI Finishing"
    assert component.verifier == "realesrgan_ncnn"
    assert component.installer == "realesrgan_ncnn"
    assert "ffmpeg" in component.dependencies


def test_capabilities_gpu_available_matches_readiness(monkeypatch):
    from app.magi import realesrgan_runtime

    monkeypatch.setattr(
        realesrgan_runtime,
        "readiness",
        lambda: {
            "realesrganReady": False,
            "device": None,
            "version": "test",
        },
    )
    caps = capabilities()
    gpu = next(engine for engine in caps["engines"] if engine["id"] == ENGINE_GPU)
    ffmpeg = next(engine for engine in caps["engines"] if engine["id"] == "ffmpeg-scale")
    assert caps["realesrganReady"] is False
    assert gpu["available"] is False
    assert ffmpeg["available"] is True
    assert caps["creatorMessage"] == CREATOR_UNAVAILABLE
    assert caps["autoRouting"] is False


def test_gpu_upscale_fails_honestly_when_not_ready(tmp_path, monkeypatch):
    from app.magi import realesrgan_runtime

    monkeypatch.setattr(realesrgan_runtime, "readiness", lambda: {"realesrganReady": False})
    src = tmp_path / "in.png"
    src.write_bytes(b"not-a-real-image")
    dest = tmp_path / "out.png"
    with pytest.raises(RuntimeError, match="unavailable"):
        upscale_frame(str(src), str(dest), engine=ENGINE_GPU, model="realesrgan-x4plus")
    assert not dest.exists()


def test_apply_upscale_is_defined():
    assert callable(apply_upscale)


def test_disk_preflight_fails_when_short(monkeypatch):
    from app.magi import media as magi_media

    monkeypatch.setattr(magi_media, "free_disk_bytes", lambda path=None: 10)
    with pytest.raises(RuntimeError, match="Not enough disk space"):
        disk_preflight(need_bytes=5_000_000_000, label="GPU upscaling")


def test_temp_cleanup_removes_tree():
    work = new_temp_dir("cleanup_test")
    (work / "frame.png").write_bytes(b"x")
    assert work.is_dir()
    cleanup_dir(work)
    assert not work.exists()
    assert magi_temp_root().is_dir()


def test_finishing_schema_roundtrip():
    project_id = f"finishing-{uuid.uuid4().hex[:8]}"
    seq = empty_sequence(project_id)
    seq["finishing"] = {
        "clipGrades": {"clip_1": {"presetId": "noir", "params": {"contrast": 0.3}}},
        "upscale": {"enabled": True, "engine": "ffmpeg-scale", "model": "lanczos", "target": "1920x1080"},
        "audio": {"range": "entire", "lastJobIds": []},
        "render": {"profile": "final"},
    }
    saved = save_sequence(project_id, seq)
    parsed = parse_sequence(saved)
    assert parsed.finishing["clipGrades"]["clip_1"]["presetId"] == "noir"
    reloaded = get_sequence(project_id)
    assert reloaded["finishing"]["upscale"]["engine"] == "ffmpeg-scale"


def test_duplicate_job_guard(client):
    from app.db import SessionLocal, init_db

    init_db()
    res = client.post("/api/projects", json={"name": "MAGI Dup Jobs", "global_prompt": "Test."})
    assert res.status_code == 200, res.text
    project_id = res.json()["id"]
    db = SessionLocal()
    try:
        first = enqueue_job(
            db,
            project_id=project_id,
            kind="magi_upscale",
            params={"fingerprint": "same-upscale"},
            message="Queued MAGI upscale",
        )
        second = find_active_duplicate(db, project_id, "magi_upscale", "same-upscale")
        assert second is not None
        assert second.id == first.id
        assert first.status in ACTIVE
    finally:
        db.close()


def test_codirector_magi_mutation_tools_bound():
    from app.codirector.tools.definitions import TOOL_IDS
    from app.codirector.tools.registry import mutation_handler

    for tool_id in ("magi.color.apply", "magi.upscale", "magi.audio.generate", "magi.render"):
        assert tool_id in TOOL_IDS
        handler = mutation_handler(tool_id)
        assert handler.preview is not None
        assert handler.apply is not None


def test_smoke_color_presets_and_upscale_capabilities(client):
    presets = client.get("/api/magi/color/presets")
    assert presets.status_code == 200, presets.text
    ids = {item["id"] for item in presets.json()["presets"]}
    assert "noir" in ids
    assert "cinematic_warm" in ids
    caps = client.get("/api/magi/upscale/capabilities")
    assert caps.status_code == 200, caps.text
    body = caps.json()
    assert "realesrganReady" in body
    engines = {engine["id"]: engine for engine in body["engines"]}
    assert engines["ffmpeg-scale"]["available"] is True
    assert engines["realesrgan-ncnn-vulkan"]["available"] is bool(body["realesrganReady"])
    if not body["realesrganReady"]:
        assert body["creatorMessage"] == CREATOR_UNAVAILABLE


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not on PATH")
def test_ffmpeg_color_preserves_audio(tmp_path):
    from app.magi.color_grading import apply_color_grade
    from app.magi.media import probe_media

    src = _make_clip(tmp_path / "src.mp4", seconds=1.0, audio=True)
    dest = tmp_path / "graded.mp4"
    apply_color_grade(str(src), str(dest), {"contrast": 0.2, "saturation": -1.0})
    probe = probe_media(dest)
    assert probe["hasAudio"] is True
    assert probe["duration"] > 0.4


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not on PATH")
def test_ffmpeg_upscale_and_audio_less_mux(tmp_path):
    from app.magi.media import probe_media

    silent = _make_clip(tmp_path / "silent.mp4", seconds=1.0, audio=False, size="320x180")
    dest = tmp_path / "up.mp4"
    upscale_frame(str(silent), str(dest), engine="ffmpeg-scale", model="lanczos", target_width=640, target_height=360)
    probe = probe_media(dest)
    assert probe["width"] == 640
    assert probe["height"] == 360
    assert probe["hasAudio"] is False


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not on PATH")
def test_color_apply_registers_derived_asset(client, tmp_path):
    from app.db import Asset, SessionLocal, init_db

    init_db()
    created = client.post("/api/projects", json={"name": "MAGI Color Asset", "global_prompt": "Test."})
    assert created.status_code == 200, created.text
    project_id = created.json()["id"]
    clip = _make_clip(tmp_path / "grade_src.mp4", seconds=1.0, audio=True)
    db = SessionLocal()
    try:
        asset_id = str(uuid.uuid4())
        db.add(
            Asset(
                id=asset_id,
                project_id=project_id,
                tag="source",
                kind="video",
                filename=clip.name,
                path=str(clip),
            )
        )
        db.commit()
    finally:
        db.close()
    seq = empty_sequence(project_id)
    seq["clips"] = [
        {
            "id": "clip_grade_1",
            "trackId": seq["tracks"][0]["id"],
            "assetId": asset_id,
            "name": "Source",
            "startFrame": 0,
            "durationFrames": 24,
            "inPoint": 0,
            "outPoint": 24,
        }
    ]
    save_sequence(project_id, seq)
    applied = client.post(
        f"/api/magi/projects/{project_id}/color/apply",
        json={"assetId": asset_id, "presetId": "noir", "clipId": "clip_grade_1", "params": {}},
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body.get("ok") is True
    assert body.get("sourcePreserved") is True
    assert body.get("output_asset_id")
    reloaded = get_sequence(project_id)
    assert reloaded["finishing"]["clipGrades"]["clip_grade_1"]["presetId"] == "noir"


def test_gpu_apply_endpoint_fails_honestly(client, monkeypatch):
    from app.magi import realesrgan_runtime

    monkeypatch.setattr(realesrgan_runtime, "readiness", lambda: {"realesrganReady": False})
    created = client.post("/api/projects", json={"name": "MAGI GPU Fail", "global_prompt": "Test."})
    project_id = created.json()["id"]
    res = client.post(
        f"/api/magi/projects/{project_id}/upscale/apply",
        json={
            "assetId": str(uuid.uuid4()),
            "engine": ENGINE_GPU,
            "model": "realesrgan-x4plus",
            "target_resolution": "1920x1080",
        },
    )
    assert res.status_code in {400, 409}
    payload = res.json()
    detail = payload.get("detail") or payload
    error = detail.get("error") or {}
    assert "unavailable" in str(error.get("message") or payload).lower()


def test_picture_clips_exclude_audio_tracks():
    from app.magi.final_render import picture_clips

    seq = empty_sequence("pic-filter")
    video_id = next(t["id"] for t in seq["tracks"] if t["kind"] == "video")
    audio_id = next(t["id"] for t in seq["tracks"] if t["kind"] == "audio")
    seq["clips"] = [
        {
            "id": "v1",
            "trackId": video_id,
            "assetId": "asset-video",
            "name": "Picture",
            "startFrame": 0,
            "durationFrames": 48,
            "inPoint": 0,
            "outPoint": 48,
        },
        {
            "id": "a2",
            "trackId": audio_id,
            "assetId": "asset-music",
            "name": "Music",
            "startFrame": 0,
            "durationFrames": 48,
            "inPoint": 0,
            "outPoint": 48,
        },
    ]
    selected = picture_clips(seq)
    assert [c["id"] for c in selected] == ["v1"]
