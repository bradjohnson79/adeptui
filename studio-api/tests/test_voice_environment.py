"""M5.2 Voice Environment unit + API contract tests."""

from __future__ import annotations

import struct
import tempfile
import wave
from pathlib import Path

import numpy as np
import pytest

from app.voice_environment.compiler import compile_dsp_plan
from app.voice_environment.processor import process_environment
from app.voice_environment.presets import SPACE_PRESETS


def _write_silent_wav(path: Path, *, seconds: float = 0.4, sr: int = 16000, speech_at: float = 0.05) -> None:
    n = int(sr * seconds)
    samples = np.zeros(n, dtype=np.float32)
    start = int(sr * speech_at)
    t = np.arange(n - start) / sr
    samples[start:] = 0.2 * np.sin(2 * np.pi * 220 * t)
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def test_compile_dsp_plan_includes_custom_prompts_and_timing_hints():
    plan = compile_dsp_plan(
        {
            "spacePreset": "cathedral",
            "distancePreset": "very_distant",
            "directionPreset": "far_right",
            "tonePreset": "warm",
            "devicePreset": "intercom",
            "wallaPreset": "command_center",
            "wallaLevel": "subtle",
            "customSpacePrompt": "large metallic corridor",
            "customDevicePrompt": "ship intercom with static",
        }
    )
    assert plan["kind"] == "deterministic_acoustic"
    assert plan["space"]["preset"] == "cathedral"
    assert plan["device"]["preset"] == "intercom"
    assert plan["customPrompts"]["space"] == "large metallic corridor"
    assert plan["timingHints"]["speechStartOffsetMs"] == 0.0
    assert plan["timingHints"]["processingLatencyMs"] > 0
    assert plan["timingHints"]["tailDurationMs"] == SPACE_PRESETS["cathedral"]["tail_ms"]


def test_environment_swap_preserves_speech_start_offset(tmp_path: Path):
    dry = tmp_path / "dry.wav"
    _write_silent_wav(dry, speech_at=0.08)
    speech_starts = []
    for space, device in (
        ("dry_booth", "direct"),
        ("intercom", "intercom"),
        ("cathedral", "direct"),
        ("stadium", "stadium_pa"),
        ("small_room", "direct"),
    ):
        plan = compile_dsp_plan(
            {
                "spacePreset": space,
                "distancePreset": "medium_close_up" if space != "stadium" else "very_distant",
                "directionPreset": "center",
                "tonePreset": "natural",
                "devicePreset": device,
                "wallaPreset": "none",
            }
        )
        out = tmp_path / f"{space}_{device}.wav"
        timing = process_environment(dry, out, tmp_path / f"{space}_room.wav", None, plan)
        speech_starts.append(timing.speechStartOffsetMs)
        assert out.exists()
        assert timing.dryDurationMs > 0
        assert timing.processedDurationMs >= timing.dryDurationMs - 1
        # Latency/tail stored separately from speech start.
        assert timing.processingLatencyMs >= 0
        assert timing.tailDurationMs >= 0

    # Speech start must remain stable across environment swaps (within detection tolerance).
    assert max(speech_starts) - min(speech_starts) < 15.0


def test_walla_stem_written_separately(tmp_path: Path):
    dry = tmp_path / "dry.wav"
    _write_silent_wav(dry)
    plan = compile_dsp_plan(
        {
            "spacePreset": "small_room",
            "distancePreset": "close_up",
            "directionPreset": "slightly_right",
            "tonePreset": "warm",
            "devicePreset": "direct",
            "wallaPreset": "light_room",
            "wallaLevel": "moderate",
        }
    )
    processed = tmp_path / "proc.wav"
    room = tmp_path / "room.wav"
    walla = tmp_path / "walla.wav"
    timing = process_environment(dry, processed, room, walla, plan)
    assert processed.exists() and room.exists() and walla.exists()
    assert timing.speechStartOffsetMs >= 0


def test_direction_and_distance_mapping_values():
    plan = compile_dsp_plan(
        {
            "spacePreset": "small_room",
            "distancePreset": "long_shot",
            "directionPreset": "far_left",
            "tonePreset": "muffled",
            "devicePreset": "walkie_talkie",
            "wallaPreset": "none",
        }
    )
    assert plan["direction"]["pan"] == pytest.approx(-0.9)
    assert plan["distance"]["gain_db"] < 0
    assert plan["tone"]["lp_hz"] == 3500
    assert plan["device"]["band_high_hz"] == 3000


def test_timing_hints_never_fold_latency_into_speech_start():
    plan = compile_dsp_plan(
        {
            "spacePreset": "cathedral",
            "distancePreset": "very_distant",
            "directionPreset": "center",
            "tonePreset": "natural",
            "devicePreset": "stadium_pa",
            "wallaPreset": "none",
        }
    )
    hints = plan["timingHints"]
    assert hints["speechStartOffsetMs"] == 0.0
    assert hints["processingLatencyMs"] > 0
    assert hints["tailDurationMs"] > 0
    # Latency and tail are separate fields — not subtracted from speech start.
    assert hints["speechStartOffsetMs"] != hints["processingLatencyMs"]


class _FakeRow:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_prepare_timeline_keeps_spoken_start_dry_aligned():
    from app.voice_environment.service import prepare_timeline

    speech_start = 80.0
    latency = 42.0
    tail = 1200.0
    render = _FakeRow(
        id="render-1",
        project_id="proj-1",
        character_id="char-1",
        performance_record_id="rec-1",
        performance_take_id="take-1",
        environment_profile_id="prof-1",
        dry_audio_asset_id="dry-a",
        processed_audio_asset_id="proc-a",
        room_tone_asset_id="room-a",
        walla_asset_id=None,
        speech_start_offset_ms=speech_start,
        processing_latency_ms=latency,
        tail_duration_ms=tail,
        dry_duration_ms=400.0,
        processed_duration_ms=1600.0,
    )
    profile = _FakeRow(
        scene_id="scene-1",
        distance_preset="close_up",
        direction_preset="center",
        device_preset="direct",
    )

    class _Db:
        def get(self, model, key):
            name = getattr(model, "__name__", str(model))
            if "Render" in name:
                return render
            if "Profile" in name:
                return profile
            return None

    payload = prepare_timeline(_Db(), "render-1", scene_id="scene-1", use_processed=True)
    clip = payload["clip"]
    handoff = payload["handoff"]
    assert clip["startMs"] == 0
    assert clip["speechStartOffsetMs"] == speech_start
    assert clip["processingLatencyMs"] == int(latency)
    assert clip["tailDurationMs"] == int(tail)
    assert clip["dryAudioAssetId"] == "dry-a"
    assert clip["assetId"] == "proc-a"
    assert handoff["timing"]["speechStartOffsetMs"] == speech_start
    assert handoff["timing"]["processingLatencyMs"] == latency
    # Spoken start must not absorb processing latency.
    assert clip["speechStartOffsetMs"] != latency


def test_prepare_lipsync_uses_dry_timing_only():
    from app.voice_environment.service import prepare_lipsync

    render = _FakeRow(
        id="render-2",
        project_id="proj-1",
        character_id="char-1",
        performance_record_id="rec-1",
        performance_take_id="take-1",
        environment_profile_id="prof-1",
        dry_audio_asset_id="dry-b",
        processed_audio_asset_id="proc-b",
        room_tone_asset_id="room-b",
        walla_asset_id="walla-b",
        speech_start_offset_ms=95.0,
        processing_latency_ms=55.0,
        tail_duration_ms=900.0,
        dry_duration_ms=500.0,
        processed_duration_ms=1400.0,
    )

    class _Db:
        def get(self, model, key):
            name = getattr(model, "__name__", str(model))
            if "Render" in name:
                return render
            return None

        def commit(self):
            return None

    payload = prepare_lipsync(_Db(), "render-2", scene_id=None)
    handoff = payload["handoff"]
    assert handoff["useDryTiming"] is True
    assert handoff["dryAudioAssetId"] == "dry-b"
    assert handoff["timing"]["speechStartOffsetMs"] == 95.0
    assert handoff["timing"]["tailDurationMs"] == 900.0
    # Lip Sync must not use processed asset as timing source.
    assert "processedAudioAssetId" not in handoff or handoff.get("processedAudioAssetId") != handoff["dryAudioAssetId"]


def test_open_audio_studio_payload_includes_stems_and_timing():
    from app.voice_environment.service import open_audio_studio_payload

    render = _FakeRow(
        id="render-3",
        project_id="proj-1",
        character_id="char-1",
        environment_profile_id="prof-1",
        dry_audio_asset_id="dry-c",
        processed_audio_asset_id="proc-c",
        room_tone_asset_id="room-c",
        walla_asset_id="walla-c",
        speech_start_offset_ms=70.0,
        processing_latency_ms=20.0,
        tail_duration_ms=400.0,
        dry_duration_ms=300.0,
        processed_duration_ms=700.0,
        approved=True,
    )

    class _Db:
        def get(self, model, key):
            return render

    payload = open_audio_studio_payload(_Db(), "render-3")
    handoff = payload["handoff"]
    assert payload["workspace"] == "audiostudio"
    assert handoff["dryAudioAssetId"] == "dry-c"
    assert handoff["processedAudioAssetId"] == "proc-c"
    assert handoff["roomToneAssetId"] == "room-c"
    assert handoff["wallaAssetId"] == "walla-c"
    assert handoff["timing"]["speechStartOffsetMs"] == 70.0
