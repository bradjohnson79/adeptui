"""MAGI Upscale sound profiles. Temp media only — no project database writes."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from app.codirector.tools.definitions import ToolContext
from app.codirector.tools.handlers import magi
from app.db import SessionLocal, init_db
from app.magi.sound_enhancement import (
    analyze_source,
    attach_soundtrack,
    probe_audio,
    profile_catalog,
    recommend,
    side_to_mid_ratio,
    sound_profile_from_intent,
)


def _run(args: list[str]) -> None:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-y", *args], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout)[-800:])


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _picture(path: Path, *, audio: str | None, seconds: float = 4.0) -> None:
    cmd = [
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=320x180:r=24:d={seconds}",
    ]
    if audio:
        cmd += ["-i", audio, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", str(path)]
    else:
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(path)]
    _run(cmd)


def test_recommend_rules_follow_the_analysis():
    balanced = {
        "hasAudio": True,
        "channels": 2,
        "dialogue": True,
        "music": True,
        "sfx": True,
        "noise": "clean",
        "speechDominance": False,
        "clippingRisk": False,
        "stereoWidth": "normal",
    }
    speech = {**balanced, "sfx": False, "speechDominance": True}
    noisy = {**balanced, "noise": "noisy", "sfx": False, "music": False, "speechDominance": True}
    surround = {**balanced, "channels": 6}
    assert recommend(balanced)["profile"] == "cinematic_stereo"
    assert recommend(speech)["profile"] == "dialogue_enhance"
    assert recommend(noisy)["profile"] == "clean_restore"
    assert recommend(surround)["profile"] == "preserve_original"
    assert recommend({"hasAudio": False})["profile"] == "preserve_original"


def test_intent_maps_onto_existing_profiles():
    assert sound_profile_from_intent("Upscale this to 2K and use the recommended sound enhancement.") == "recommended"
    assert sound_profile_from_intent("Upscale to 4K but preserve the original audio.") == "preserve_original"
    assert sound_profile_from_intent("Use 5.1 cinema sound on the upscale.") == "cinema_51"
    assert sound_profile_from_intent("Use 7.1 cinema sound.") == "cinema_71"


def test_finish_plan_selects_sound_profile_without_refusing_cinema_upmix():
    init_db()
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id="unused-project", scene_id=None)
        recommended = magi._finish_plan(ctx, {"intent": "Upscale this to 2K and use the recommended sound enhancement."})
        preserve = magi._finish_plan(ctx, {"intent": "Upscale to 4K but preserve the original audio."})
        cinema = magi._finish_plan(ctx, {"intent": "Use 5.1 cinema sound on the upscale."})
        eq = magi._finish_plan(ctx, {"intent": "Add EQ and interpolate to 60 fps."})
    finally:
        db.close()
    assert recommended["upscale"]["target"] == "2K"
    assert recommended["upscale"]["soundProfile"] == "recommended"
    assert recommended["requestedUnsupported"] is False
    assert preserve["upscale"]["target"] == "4K"
    assert preserve["upscale"]["soundProfile"] == "preserve_original"
    assert cinema["upscale"]["soundProfile"] == "cinema_51"
    assert cinema["upscale"]["enabled"] is True
    assert cinema["requestedUnsupported"] is False
    assert eq["requestedUnsupported"] is True


def test_profiles_probe_real_channel_layouts(tmp_path: Path):
    mix = tmp_path / "mix.m4a"
    _run(
        [
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=80:sample_rate=48000:duration=4",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=48000:duration=4",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=8000:sample_rate=48000:duration=4",
            "-filter_complex",
            "[0:a]volume=0.22[low];[1:a]volume=0.4[mid];[2:a]volume=0.16[high];"
            "[low][mid][high]amix=inputs=3:normalize=0,pan=stereo|c0=c0|c1=0.72*c0",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(mix),
        ]
    )
    source = tmp_path / "source.mp4"
    _picture(source, audio=str(mix))
    source_hash = _hash(source)
    analysis = analyze_source(source)
    rec = recommend(analysis)
    assert analysis["hasAudio"] is True
    assert analysis["channels"] == 2
    assert analysis["sampleRate"] == 48000
    assert analysis["dialogue"] is True
    assert analysis["music"] is True
    assert analysis["sfx"] is True
    assert rec["profile"] in {"cinematic_stereo", "dialogue_enhance"}
    assert rec["reason"]

    picture = tmp_path / "picture.mp4"
    _picture(picture, audio=None)
    catalog = {row["id"]: row for row in profile_catalog()}
    report = {"recommendation": rec, "analysis": analysis, "profiles": {}}
    duration = float(analysis["duration"] or 4)
    for profile in (
        "preserve_original",
        "cinematic_stereo",
        "dialogue_enhance",
        "wide_stereo",
        "clean_restore",
        "cinema_51",
        "cinema_71",
        "headphone_spatial",
    ):
        dest = tmp_path / f"{profile}.mp4"
        if not catalog[profile]["available"]:
            report["profiles"][profile] = {"available": False}
            continue
        sound = attach_soundtrack(picture, source, dest, profile, analysis, duration=duration)
        probed = probe_audio(dest)
        report["profiles"][profile] = {"sound": sound, "probe": probed}
        assert abs(probed["duration"] - duration) < 0.35
        if profile == "preserve_original":
            assert sound["mode"] == "copy"
            assert probed["channels"] == 2
        elif profile == "cinema_51":
            assert probed["channels"] == 6
        elif profile == "cinema_71":
            assert probed["channels"] == 8
        else:
            assert probed["channels"] == 2
        from app.magi.sound_enhancement import peak_db

        peak = peak_db(dest)
        assert peak is None or peak <= -0.1
    wide = side_to_mid_ratio(tmp_path / "wide_stereo.mp4")
    assert wide < 2.5
    assert _hash(source) == source_hash
    (tmp_path / "sound-report.json").write_text(json.dumps(report, default=str), encoding="utf-8")


def test_clean_restore_on_a_noisy_speech_clip(tmp_path: Path):
    noisy = tmp_path / "noisy.m4a"
    _run(
        [
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=48000:duration=4",
            "-f",
            "lavfi",
            "-i",
            "anoisesrc=color=white:sample_rate=48000:duration=4",
            "-filter_complex",
            "[0:a]volume=0.08[speech];[1:a]volume=0.35[noise];[speech][noise]amix=inputs=2:normalize=0,pan=stereo|c0=c0|c1=c0",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(noisy),
        ]
    )
    source = tmp_path / "noisy.mp4"
    _picture(source, audio=str(noisy))
    analysis = analyze_source(source)
    choice = recommend(analysis)
    picture = tmp_path / "picture.mp4"
    _picture(picture, audio=None)
    dest = tmp_path / "clean.mp4"
    sound = attach_soundtrack(picture, source, dest, "clean_restore", analysis, duration=float(analysis["duration"] or 4))
    probed = probe_audio(dest)
    assert choice["profile"] == "clean_restore"
    assert sound["mode"] == "processed"
    assert probed["channels"] == 2


def test_silent_picture_has_no_audio_profile(tmp_path: Path):
    source = tmp_path / "silent.mp4"
    _picture(source, audio=None, seconds=2)
    analysis = analyze_source(source)
    assert analysis["hasAudio"] is False
    assert recommend(analysis)["profile"] == "preserve_original"
