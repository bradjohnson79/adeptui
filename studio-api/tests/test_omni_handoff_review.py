"""Timeline Omni handoff review is a sampled still package, not a full-clip decode."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.codirector.video_intelligence.clip_extract import (
    continuity_sample_times,
    extract_continuity_frames,
)
from app.codirector.video_intelligence.worker_client import (
    compose_handoff_summary,
    run_av_perception_pair,
)
from app.director_timeline_w46.generation.window_handoff import (
    HANDOFF_REVIEW_FRAMES,
    HANDOFF_REVIEW_HEIGHT,
    HANDOFF_REVIEW_QUESTION,
    _one_omni_pass,
    _stamp_semantic,
)


def _color_clip(path: Path, color: str) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=320x180:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def test_o1_sample_times_cover_the_window_without_a_full_decode():
    stamps = continuity_sample_times(15.0, 8)
    assert len(stamps) == 8
    assert stamps[0] == 0.0
    assert stamps[-1] > 14.0
    assert stamps == sorted(stamps)


def test_o2_frames_are_taken_from_the_requested_take(tmp_path: Path):
    take = tmp_path / "take-a.mp4"
    other = tmp_path / "take-b.mp4"
    _color_clip(take, "blue")
    _color_clip(other, "red")
    before = take.stat().st_size
    proxy = tmp_path / "proxy"
    paths, stamps = extract_continuity_frames(str(take), str(proxy), duration_sec=2.0, count=6, height=360)
    assert len(paths) == 6
    assert len(stamps) == 6
    assert all(Path(path).is_file() for path in paths)
    assert all(str(take.resolve()) not in path for path in paths)
    assert other.name not in " ".join(paths)
    assert take.stat().st_size == before


def test_o2_proxy_refuses_to_sit_beside_the_take(tmp_path: Path):
    take = tmp_path / "take.mp4"
    take.write_bytes(b"not-a-movie")
    with pytest.raises(RuntimeError, match="REVIEW_PROXY_MUST_NOT_SIT_BESIDE_TAKE"):
        extract_continuity_frames(str(take), str(tmp_path), duration_sec=2.0, count=6, height=360)


def test_o3_other_take_is_not_the_ffmpeg_input(tmp_path: Path, monkeypatch):
    take_a = tmp_path / "a.mp4"
    take_b = tmp_path / "b.mp4"
    take_a.write_bytes(b"a")
    take_b.write_bytes(b"b")
    seen: list[str] = []

    def fake_run(cmd, **_kwargs):
        if "-i" in cmd:
            seen.append(cmd[cmd.index("-i") + 1])
        dest = Path(cmd[-1])
        dest.write_bytes(b"\xff\xd8\xff" + b"x" * 64)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("app.codirector.video_intelligence.clip_extract.subprocess.run", fake_run)
    monkeypatch.setattr("app.codirector.video_intelligence.clip_extract.ffmpeg_bin", lambda: "ffmpeg")
    extract_continuity_frames(str(take_a), str(tmp_path / "proxy"), duration_sec=15.0, count=8, height=480)
    assert seen
    assert all(item == str(take_a) for item in seen)
    assert str(take_b) not in seen


def test_o4_o6_one_worker_samples_frames_and_skips_audio(tmp_path: Path, monkeypatch):
    take = tmp_path / "take.mp4"
    take.write_bytes(b"mp4")
    calls = {"av": 0, "proc": 0}

    def boom(*_a, **_k):
        calls["av"] += 1
        raise AssertionError("full clip extract")

    monkeypatch.setattr("app.codirector.video_intelligence.worker_client.extract_av_clip", boom)
    monkeypatch.setattr(
        "app.codirector.video_intelligence.worker_client.extract_continuity_frames",
        lambda video, dest, **_k: ([str(Path(dest) / "frame_00.jpg")], [0.0]),
    )

    def fake_run(cmd, **_kwargs):
        calls["proc"] += 1
        out = Path(cmd[cmd.index("--out") + 1])
        out.write_text(
            json.dumps(
                {
                    "ok": True,
                    "summary": "She sits, then turns.",
                    "actionCompleted": ["sit"],
                    "actionInProgress": ["turn"],
                    "mustContinue": ["the turn"],
                    "mustNotRepeat": ["the sit"],
                    "equipmentFlags": [],
                    "reviewInput": {"kind": "frames", "audio": False},
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("app.codirector.video_intelligence.worker_client.subprocess.run", fake_run)
    monkeypatch.setattr(
        "app.codirector.video_intelligence.worker_client.perception_mode",
        lambda: "stub",
    )
    monkeypatch.setattr("app.codirector.video_intelligence.worker_client.stub_allowed", lambda: True)
    payload = run_av_perception_pair(
        str(take),
        question="q",
        question_b="",
        frame_count=8,
        frame_height=480,
        duration_sec=15.0,
        source_asset_id="asset-current",
    )
    assert calls["av"] == 0
    assert calls["proc"] == 1
    assert payload["reviewPackage"]["audio"] is False
    assert payload["reviewPackage"]["sourceAssetId"] == "asset-current"
    assert payload["reviewPackage"]["frameCount"] == 1
    assert "Continue: the turn" in payload["summary"]
    assert "Do not repeat: the sit" in payload["summary"]


def test_o6_prompt_echo_is_not_an_equipment_finding():
    from app.codirector.video_intelligence.worker_client import _drop_equipment_echo

    assert _drop_equipment_echo(["crew", "a boom microphone", "crew, a boom microphone"]) == []
    assert _drop_equipment_echo(["boom pole crossing the left side of the table"]) == [
        "boom pole crossing the left side of the table"
    ]


def test_o5_summary_is_the_canonical_continuity_state():
    text = compose_handoff_summary(
        {
            "summary": "She reaches the door.",
            "mustContinue": ["open it"],
            "mustNotRepeat": ["the walk"],
            "subjectState": "at the door",
        }
    )
    assert "open it" in text
    assert "the walk" in text
    assert len(text) <= 500

    class Bridge:
        continuityState = {}

    bridge = Bridge()
    _stamp_semantic(bridge, {"observed": {"summary": text}}, {"observed": {"summary": "No crew in frame."}})
    assert set(bridge.continuityState) == {"semanticContinuity", "equipmentState"}
    assert bridge.continuityState["semanticContinuity"] == text


def test_o7_omni_does_not_run_until_memory_is_safe(monkeypatch):
    from app.codirector.video_intelligence import gpu_lease
    from app.director_timeline_w46.generation import window_handoff

    gpu_lease.reset_handoff_state()
    master = type("M", (), {"batchBlocks": [], "sceneTakes": [], "activeSceneTakeId": ""})()

    class Batch:
        id = "bb_a"
        order = 0
        references = []
        sceneId = "s1"

    batch = Batch()
    nxt = type("B", (), {"id": "bb_b", "order": 1, "references": []})()
    master.batchBlocks = [batch, nxt]
    monkeypatch.setattr(window_handoff, "_recheck_wait", lambda: None)
    monkeypatch.setattr(
        window_handoff,
        "probe_handoff_memory",
        lambda: {"ok": False, "reason": "GENERATOR_STILL_RESIDENT", "consumed": False},
    )
    monkeypatch.setattr(window_handoff, "release_generator_once", lambda key: {"ok": True, "comfyFreeRequested": True})
    monkeypatch.setattr(
        "app.codirector.video_intelligence.worker_client.run_av_perception_pair",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("Omni loaded before memory was safe")),
    )
    monkeypatch.setattr(
        "app.director_timeline_w46.continuity.prepare_outgoing_bridge",
        lambda *_a, **_k: None,
    )
    result = window_handoff.run_completion_reviews(
        None,
        project_id="p",
        scene_id="s1",
        asset_id="asset",
        batch=batch,
        master=master,
    )
    assert result["readyForNext"] is False
    assert result["reason"] == "GENERATOR_STILL_RESIDENT"


def test_o8_handoff_asks_for_sampled_frames_on_this_asset(monkeypatch):
    seen: dict = {}

    def pair(video, **kwargs):
        seen["video"] = video
        seen.update(kwargs)
        return {
            "ok": True,
            "summary": "Continue: the glance. Do not repeat: the entrance.",
            "equipmentFlags": [],
            "availability": "ready",
        }

    monkeypatch.setattr(
        "app.codirector.video_intelligence.worker_client.run_av_perception_pair",
        pair,
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service._asset_path",
        lambda *_a, **_k: "current-take.mp4",
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.service._batch_video_path",
        lambda *_a, **_k: "other-take.mp4",
    )

    class Batch:
        id = "bb"
        references = []
        duration = type("D", (), {"generatedDuration": 15.0, "plannedDuration": 15.0})()

    class Master:
        pass

    continuity, equipment = _one_omni_pass(
        None,
        project_id="p",
        scene_id="s",
        asset_id="asset-current",
        batch=Batch(),
        master=Master(),
    )
    assert seen["video"] == "current-take.mp4"
    assert seen["frame_count"] == HANDOFF_REVIEW_FRAMES
    assert seen["frame_height"] == HANDOFF_REVIEW_HEIGHT
    assert seen["question"] == HANDOFF_REVIEW_QUESTION
    assert seen["question_b"] == ""
    assert seen["source_asset_id"] == "asset-current"
    assert continuity["observed"]["summary"]
    assert equipment["observed"]["availability"] == "ready"
