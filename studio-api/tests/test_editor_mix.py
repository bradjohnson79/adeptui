"""M3.2g Phase 6 — Editor final mix filter graph + endpoint wiring."""

from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


def _write_silent_wav(path: Path, *, duration_sec: float = 0.5, rate: int = 16000) -> Path:
    nframes = int(rate * duration_sec)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * nframes)
    return path


def test_collect_skips_placeholder_and_missing(tmp_path: Path):
    from app.editor_mix import collect_mix_stems

    wav = _write_silent_wav(tmp_path / "music.wav")
    editor = {
        "tracks": {
            "music": [
                {
                    "id": "m1",
                    "asset_id": "a1",
                    "start": 1.5,
                    "length": 2.0,
                    "gain": 0.5,
                }
            ],
            "sfx": [
                {"id": "s1", "placeholder": True, "label": "whoosh"},
                {"id": "s2", "asset_id": "missing", "start": 0},
            ],
            "dialogue": [],
            "ambience": [],
        }
    }

    def resolve(asset_id, output_path):
        if asset_id == "a1":
            return wav
        return None

    stems, skipped = collect_mix_stems(editor, resolve)
    assert len(stems) == 1
    assert stems[0].track == "music"
    assert stems[0].start_sec == 1.5
    assert stems[0].gain == 0.5
    assert {s["reason"] for s in skipped} == {"placeholder", "missing_file"}


def test_build_mix_plan_includes_adelay_volume_and_amix():
    from app.editor_mix import MixStem, build_mix_plan

    stems = [
        MixStem(
            track="music",
            clip_id="m1",
            path=Path("music.wav"),
            start_sec=1.25,
            length_sec=2.0,
            trim_start=0.0,
            gain=0.8,
            asset_id="a1",
        ),
        MixStem(
            track="sfx",
            clip_id="s1",
            path=Path("sfx.wav"),
            start_sec=0.0,
            length_sec=0.5,
            trim_start=0.1,
            gain=1.0,
            asset_id="a2",
        ),
    ]
    plan = build_mix_plan(stems, video_has_audio=True)
    assert "[va]" in plan.filter_complex
    assert "adelay=1250|1250" in plan.filter_complex
    assert "volume=0.800000" in plan.filter_complex
    assert "atrim=start=0.100000:end=0.600000" in plan.filter_complex
    assert "amix=inputs=3" in plan.filter_complex
    assert plan.audio_map_label == "[aout]"


def test_build_mix_plan_silent_video_no_va():
    from app.editor_mix import MixStem, build_mix_plan

    stems = [
        MixStem(
            track="dialogue",
            clip_id="d1",
            path=Path("d.wav"),
            start_sec=0.0,
            length_sec=1.0,
            trim_start=0.0,
            gain=1.0,
        )
    ]
    plan = build_mix_plan(stems, video_has_audio=False)
    assert "[0:a]" not in plan.filter_complex
    assert "amix" not in plan.filter_complex  # single stem → anull rename
    assert "[aout]" in plan.filter_complex


def test_render_endpoint_queues_editor_mix(client, monkeypatch: pytest.MonkeyPatch):
    from app.routers import api

    enqueue = AsyncMock()
    monkeypatch.setattr(api.job_queue, "enqueue", enqueue)

    created = client.post("/api/projects", json={"name": "Editor Mix Test"})
    assert created.status_code == 200, created.text
    pid = created.json()["id"]

    res = client.post(
        f"/api/projects/{pid}/render",
        json={"kind": "editor_mix", "primary_video_path": "C:/tmp/primary.mp4"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kind"] == "editor_mix"
    assert body["status"] == "queued"
    params = json.loads(body.get("params_json") or "{}")
    assert params.get("primary_video_path") == "C:/tmp/primary.mp4"
    enqueue.assert_awaited_once()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
def test_mix_editor_onto_video_with_synthetic_media(tmp_path: Path):
    """Integration: silent MP4 + timed WAV → AAC audio present in output."""
    from app.editor_mix import mix_editor_onto_video

    wav = _write_silent_wav(tmp_path / "bed.wav", duration_sec=1.0)
    # Tiny silent video (no audio stream)
    video = tmp_path / "silent.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:d=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
        capture_output=True,
    )
    editor = {
        "tracks": {
            "music": [
                {
                    "id": "m1",
                    "output_path": str(wav),
                    "start": 0.2,
                    "length": 0.8,
                    "volume": 0.9,
                }
            ],
            "sfx": [{"id": "ph", "placeholder": True}],
            "dialogue": [],
            "ambience": [],
        }
    }

    def resolve(asset_id, output_path):
        if output_path and Path(output_path).is_file():
            return Path(output_path)
        return None

    out = tmp_path / "mix.mp4"
    result = mix_editor_onto_video(
        primary_video=video,
        editor_data=editor,
        out_path=out,
        resolve_path=resolve,
        video_has_audio=False,
    )
    assert out.is_file()
    assert out.stat().st_size > 0
    assert len(result.stems_used) == 1
    assert result.skipped[0]["reason"] == "placeholder"
    assert "adelay=200|200" in result.filter_complex

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0
    assert "audio" in probe.stdout.lower()


def test_mix_stems_onto_video_passthrough_when_no_stems(tmp_path: Path):
    from app.editor_mix import mix_stems_onto_video

    primary = tmp_path / "primary.mp4"
    primary.write_bytes(b"fake video bytes")
    out = tmp_path / "out.mp4"
    result = mix_stems_onto_video(primary_video=primary, stems=[], out_path=out)
    assert out.read_bytes() == b"fake video bytes"
    assert result.prompt_meta["passthrough"] is True


def test_collect_timeline_mix_stems_maps_volume_and_skips_muted(tmp_path: Path, monkeypatch):
    from app.editor_mix import collect_timeline_mix_stems

    music = _write_silent_wav(tmp_path / "music.wav", duration_sec=2.0)
    sfx = _write_silent_wav(tmp_path / "sfx.wav", duration_sec=1.0)

    def resolve(asset_id, output_path):
        mapping = {"music-asset": music, "sfx-asset": sfx}
        return mapping.get(asset_id)

    # Monkeypatch probe_duration to avoid real ffprobe in unit test
    monkeypatch.setattr("app.editor_mix.probe_duration", lambda path: 3.0)

    class FakeScene:
        id = "scene-1"
        duration_sec = 5.0
        prompt = ""
        director_json = json.dumps(
            {
                "media_mode": "video",
                "duration_sec": 5.0,
                "audio_clips": [
                    {
                        "id": "a1",
                        "asset_id": "music-asset",
                        "start": 0.5,
                        "length": 2.0,
                        "volume": 0.4,
                        "muted": False,
                    }
                ],
                "sfx_clips": [
                    {
                        "id": "s2",
                        "asset_id": "sfx-asset",
                        "start": 1.0,
                        "length": 1.0,
                        "volume": 0.7,
                        "muted": False,
                    },
                    {
                        "id": "s3",
                        "asset_id": "sfx-asset",
                        "start": 2.0,
                        "length": 1.0,
                        "volume": 0.5,
                        "muted": True,  # should be skipped
                    },
                ],
            }
        )

    stems, skipped = collect_timeline_mix_stems(
        db=None,
        project=None,
        scenes=[FakeScene()],
        scene_outputs=[tmp_path / "scene0.mp4"],
        resolve_path=resolve,
    )
    assert len(stems) == 2
    assert {s.clip_id for s in stems} == {"a1", "s2"}
    assert {s.track for s in stems} == {"music", "sfx"}
    assert any(s.gain == 0.4 and s.track == "music" for s in stems)
    assert any(s.gain == 0.7 and s.track == "sfx" for s in stems)
    assert any(s["clip_id"] == "s3" and s["reason"] == "muted_or_zero_gain" for s in skipped)


def test_collect_timeline_mix_stems_cumulative_offsets_and_clamp(tmp_path: Path, monkeypatch):
    from app.editor_mix import collect_timeline_mix_stems

    music = _write_silent_wav(tmp_path / "music.wav", duration_sec=2.0)

    def resolve(asset_id, output_path):
        return {"music-asset": music}.get(asset_id)

    monkeypatch.setattr("app.editor_mix.probe_duration", lambda path: 4.0)

    class FakeScene:
        def __init__(self, sid, start, volume, muted=False):
            self.id = sid
            self.duration_sec = 5.0
            self.prompt = ""
            self.director_json = json.dumps(
                {
                    "media_mode": "video",
                    "duration_sec": 5.0,
                    "audio_clips": [
                        {
                            "id": sid,
                            "asset_id": "music-asset",
                            "start": start,
                            "length": 2.0,
                            "volume": volume,
                            "muted": muted,
                        }
                    ],
                    "sfx_clips": [],
                }
            )

    scenes = [FakeScene("a", 0.5, 1.5), FakeScene("b", 0.25, 0.0)]  # 0.0 volume should be skipped
    s0 = tmp_path / "s0.mp4"
    s1 = tmp_path / "s1.mp4"
    s0.write_bytes(b"")
    s1.write_bytes(b"")
    stems, skipped = collect_timeline_mix_stems(
        db=None,
        project=None,
        scenes=scenes,
        scene_outputs=[s0, s1],
        resolve_path=resolve,
    )
    assert len(stems) == 1
    assert stems[0].clip_id == "a"
    assert stems[0].start_sec == 0.5
    assert stems[0].gain == 1.0  # clamped to 1.0
    assert any(s["clip_id"] == "b" and s["reason"] == "muted_or_zero_gain" for s in skipped)


def test_collect_timeline_mix_stems_filter_complex_04_07(tmp_path: Path, monkeypatch):
    """Filter_complex proof for 0.4 music and 0.7 sfx with cumulative offset."""
    from app.editor_mix import collect_timeline_mix_stems

    music = _write_silent_wav(tmp_path / "music.wav", duration_sec=2.0)
    sfx = _write_silent_wav(tmp_path / "sfx.wav", duration_sec=1.0)

    def resolve(asset_id, output_path):
        return {"music-asset": music, "sfx-asset": sfx}.get(asset_id)

    monkeypatch.setattr("app.editor_mix.probe_duration", lambda path: 5.0)

    def make_scene(sid: str, music_id: str, sfx_id: str):
        class FakeScene:
            id = sid
            duration_sec = 5.0
            prompt = ""
            director_json = json.dumps(
                {
                    "media_mode": "video",
                    "duration_sec": 5.0,
                    "audio_clips": [
                        {
                            "id": music_id,
                            "asset_id": "music-asset",
                            "start": 1.0,
                            "length": 2.0,
                            "volume": 0.4,
                            "muted": False,
                        }
                    ],
                    "sfx_clips": [
                        {
                            "id": sfx_id,
                            "asset_id": "sfx-asset",
                            "start": 0.5,
                            "length": 1.0,
                            "volume": 0.7,
                            "muted": False,
                        }
                    ],
                }
            )
        return FakeScene()

    s0 = tmp_path / "s0.mp4"
    s1 = tmp_path / "s1.mp4"
    s0.write_bytes(b"")
    s1.write_bytes(b"")
    stems, _ = collect_timeline_mix_stems(
        db=None,
        project=None,
        scenes=[make_scene("scene-0", "m0", "s0"), make_scene("scene-1", "m1", "s1")],
        scene_outputs=[s0, s1],
        resolve_path=resolve,
    )
    # Second scene is offset by first scene duration (5.0)
    music_stem = next(s for s in stems if s.clip_id == "m1")
    sfx_stem = next(s for s in stems if s.clip_id == "s1")
    assert music_stem.start_sec == 6.0  # 5.0 + 1.0
    assert sfx_stem.start_sec == 5.5  # 5.0 + 0.5
    assert music_stem.gain == 0.4
    assert sfx_stem.gain == 0.7

    from app.editor_mix import build_mix_plan

    plan = build_mix_plan(stems, video_has_audio=True)
    assert "volume=0.400000" in plan.filter_complex
    assert "volume=0.700000" in plan.filter_complex
    assert "adelay=6000|6000" in plan.filter_complex
    assert "adelay=5500|5500" in plan.filter_complex
    assert "amix=inputs=5" in plan.filter_complex


def test_mix_stems_onto_video_reuses_ffmpeg_command(monkeypatch, tmp_path: Path):
    from app.editor_mix import MixStem, mix_stems_onto_video

    primary = tmp_path / "primary.mp4"
    primary.write_bytes(b"video")
    stem = _write_silent_wav(tmp_path / "stem.wav", duration_sec=0.5)
    out = tmp_path / "out.mp4"

    captured: list[list[str]] = []
    monkeypatch.setattr("app.editor_mix.probe_has_audio", lambda path: True)

    def fake_run_ffmpeg(args):
        captured.append(args)

    monkeypatch.setattr("app.editor_mix.run_ffmpeg", fake_run_ffmpeg)

    stems = [
        MixStem(
            track="music",
            clip_id="m1",
            path=stem,
            start_sec=0.0,
            length_sec=0.5,
            trim_start=0.0,
            gain=0.6,
        )
    ]
    result = mix_stems_onto_video(primary_video=primary, stems=stems, out_path=out)
    assert len(captured) == 1
    args = captured[0]
    assert "-filter_complex" in args
    assert "-c:v" in args
    assert "copy" in args
    assert "-c:a" in args
    assert "aac" in args
    assert result.filter_complex == args[args.index("-filter_complex") + 1]
