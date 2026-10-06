"""Tests for the Performance Retake executor and API routing."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db import Asset, Scene
from app.lipsync_tracks import LipSyncClip, LipSyncTrack, LipSyncTracks, dumps_lipsync_tracks
from app.performance_retake.contracts import (
    CharacterSheetRef,
    PerformanceRetakeError,
    PerformanceRetakeSpec,
    RetakeBeat,
    RetakeReferences,
    RetakeWindow,
    validate_spec,
)
from app.performance_retake.executor import (
    H3_SUBMIT_TIMEOUT_SEC,
    S_PERSIST,
    S_RENDER,
    S_STITCH,
    _prepare_comfy_for_h3_submit,
    execute_performance_retake,
)

ANADRIYA = "4c1c0bc8-a771-4998-b652-5d549b2a2b8d"


def _run_async(coro):
    """Run an async coroutine without pytest-asyncio."""
    return asyncio.run(coro)
KORRI = "4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed"


def _spec(**overrides) -> PerformanceRetakeSpec:
    spec = PerformanceRetakeSpec(
        projectId="p1",
        sceneId="s1",
        window=RetakeWindow(startSec=0.0, endSec=10.016),
        masterDurationSec=10.016,
        beats=[
            RetakeBeat(
                kind="dialogue",
                startSec=0.0,
                endSec=3.0,
                characterId=ANADRIYA,
                characterName="Anadriya",
                line="We've neutralized Cade. The threat is over.",
                voiceAssetId="voice-a",
            ),
            RetakeBeat(
                kind="dialogue",
                startSec=4.0,
                endSec=7.0,
                characterId=KORRI,
                characterName="Korri",
                line="We did it, sis!",
                voiceAssetId="voice-k",
            ),
            RetakeBeat(kind="silence", startSec=7.0, endSec=10.016),
        ],
        references=RetakeReferences(
            characterSheets=[
                CharacterSheetRef(characterId=ANADRIYA, assetId="sheet-a"),
                CharacterSheetRef(characterId=KORRI, assetId="sheet-k"),
            ]
        ),
    )
    for key, value in overrides.items():
        setattr(spec, key, value)
    return spec


def _make_scene(tmp_path: Path, **overrides) -> Scene:
    master = tmp_path / "master.mp4"
    master.write_bytes(b"fake-master-video-data")
    scene = Scene(
        id="s1",
        project_id="p1",
        index=8,
        name="Scene 9",
        duration_sec=10.016,
        fps=24,
        width=1152,
        height=640,
        output_path=str(master),
        seed=42,
    )
    for key, value in overrides.items():
        setattr(scene, key, value)
    return scene


def _make_asset(asset_id: str, path: Path, kind: str = "audio") -> Asset:
    return Asset(
        id=asset_id,
        project_id="p1",
        kind=kind,
        filename=path.name,
        path=str(path),
    )


class _MockDB:
    def __init__(self, scene: Scene, assets: list[Asset]):
        self._scene = scene
        self._assets = {a.id: a for a in assets}
        self.committed = 0

    def get(self, model: type, obj_id: str):
        if model is Scene and obj_id == self._scene.id:
            return self._scene
        return self._assets.get(obj_id)

    def commit(self):
        self.committed += 1


def _stage_mock(asset, *, subfolder: str = "studio"):
    staged = MagicMock()
    staged.comfy_name = f"{subfolder}/{asset.id}.bin"
    return staged


@pytest.fixture
def patched_executor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Patch all external I/O boundaries of the executor for unit tests."""
    calls: dict[str, Any] = {"ffmpeg": [], "perception": [], "comfy": []}

    monkeypatch.setattr(
        "app.performance_retake.executor.settings.comfy_input_dir",
        tmp_path / "comfy_input",
    )

    def fake_run_ffmpeg(args: list[str]) -> None:
        calls["ffmpeg"].append(list(args))
        # Materialise the most likely output file so downstream file ops succeed.
        for arg in reversed(args):
            if isinstance(arg, str) and arg.endswith((".mp4", ".wav")):
                out = Path(arg)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"x")
                break

    monkeypatch.setattr("app.performance_retake.executor.run_ffmpeg", fake_run_ffmpeg)

    async def fake_upload_queue_wait(*args, **kwargs):
        calls["comfy"].append(("queue_prompt", args, kwargs))
        return "prompt-id-1234"

    comfy_mock = AsyncMock()
    comfy_mock.queue_prompt = AsyncMock(side_effect=fake_upload_queue_wait)
    comfy_mock.wait_for_prompt = AsyncMock(return_value={"status": {"status_str": "success"}})
    monkeypatch.setattr("app.performance_retake.executor.comfy", comfy_mock)
    async def _skip_prepare(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.performance_retake.executor._prepare_comfy_for_h3_submit",
        _skip_prepare,
    )

    rendered = tmp_path / "rendered.mp4"
    rendered.write_bytes(b"rendered-video")
    monkeypatch.setattr(
        "app.performance_retake.executor.extract_output_path_from_history",
        lambda history: rendered,
    )
    monkeypatch.setattr(
        "app.performance_retake.executor._recover_h3_render",
        lambda *args, **kwargs: rendered,
    )

    def fake_run_av_perception(video_path: str, **kwargs):
        calls["perception"].append((video_path, kwargs))
        return {
            "modelId": "qwen2-5-omni",
            "summary": "Static wide shot. Two women at a console.",
            "speechSegments": [
                {"startSec": 0.0, "endSec": 3.0, "speaker": "Anadriya",
                 "text": "We've neutralized Cade. The threat is over."}
            ],
            "audioEvents": [],
            "visualEvents": [],
            "motionEvents": [],
            "characters": [],
        }

    monkeypatch.setattr("app.performance_retake.executor.run_av_perception", fake_run_av_perception)

    monkeypatch.setattr(
        "app.performance_retake.executor.stage_h3_visual_asset",
        lambda asset, **kwargs: _stage_mock(asset, subfolder=kwargs.get("subfolder", "studio")),
    )
    monkeypatch.setattr(
        "app.performance_retake.executor.stage_library_asset",
        lambda asset, **kwargs: _stage_mock(asset, subfolder=kwargs.get("subfolder", "studio")),
    )

    monkeypatch.setattr(
        "app.performance_retake.executor.frames_for_duration",
        lambda duration_sec: 243,
    )
    monkeypatch.setattr(
        "app.performance_retake.executor.build_h3_retake_graph",
        lambda **kwargs: {"mock": "graph"},
    )
    monkeypatch.setattr(
        "app.performance_retake.executor.assert_h3_retake_graph",
        lambda graph, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.performance_retake.executor.compile_performance_prompt",
        lambda spec, **kwargs: "Compiled performance prompt",
    )

    # Stable probe regardless of file contents.
    monkeypatch.setattr(
        "app.media_retake.executor._probe_video",
        lambda path: {"duration": 10.016, "fps": 24.0, "width": 1152, "height": 640},
    )

    return calls


def test_spec_serialization_round_trip():
    """Dict → dataclasses → validate_spec reconstructs the queue-worker payload."""
    spec = _spec()
    params = {
        "projectId": spec.projectId,
        "sceneId": spec.sceneId,
        "window": {
            "startSec": spec.window.startSec,
            "endSec": spec.window.endSec,
            "scope": spec.window.scope,
            "boundarySource": spec.window.boundarySource,
        },
        "beats": [
            {
                "kind": b.kind,
                "startSec": b.startSec,
                "endSec": b.endSec,
                "characterId": b.characterId,
                "characterName": b.characterName,
                "line": b.line,
                "voiceAssetId": b.voiceAssetId,
            }
            for b in spec.beats
        ],
        "references": {
            "characterSheets": [
                {"characterId": c.characterId, "assetId": c.assetId}
                for c in spec.references.characterSheets
            ],
            "sourceVideo": spec.references.sourceVideo,
            "includeSourceAudio": spec.references.includeSourceAudio,
        },
        "masterDurationSec": spec.masterDurationSec,
        "generator": spec.generator,
        "quality": spec.quality,
        "qwenPreReview": spec.qwenPreReview,
        "qwenPostReview": spec.qwenPostReview,
        "specVersion": spec.specVersion,
    }

    window = RetakeWindow(**params["window"])
    beats = [RetakeBeat(**b) for b in params["beats"]]
    references = RetakeReferences(
        characterSheets=[
            CharacterSheetRef(**c) for c in params["references"]["characterSheets"]
        ],
        sourceVideo=params["references"]["sourceVideo"],
        includeSourceAudio=params["references"]["includeSourceAudio"],
    )
    reconstructed = PerformanceRetakeSpec(
        projectId=params["projectId"],
        sceneId=params["sceneId"],
        window=window,
        beats=beats,
        references=references,
        masterDurationSec=params["masterDurationSec"],
        generator=params["generator"],
        quality=params["quality"],
        qwenPreReview=params["qwenPreReview"],
        qwenPostReview=params["qwenPostReview"],
        specVersion=params["specVersion"],
    )
    assert validate_spec(reconstructed) is reconstructed
    assert reconstructed.projectId == spec.projectId
    assert reconstructed.window.endSec == spec.window.endSec
    assert len(reconstructed.beats) == len(spec.beats)


def test_resolve_seed_falls_back_when_scene_seed_missing(tmp_path: Path):
    """Regression: scenes with seed=None/-1 must randomize, not crash.

    Live failure f1785fa8: comfy_noise_seed() called with no args raised
    TypeError (missing 'requested'), failing the whole pipeline.
    """
    from app.performance_retake.executor import _resolve_seed

    for bad in (None, -1):
        scene = _make_scene(tmp_path, seed=bad)
        resolved = _resolve_seed(scene)
        assert isinstance(resolved, int)
        assert 0 <= resolved <= 2**63 - 1

    scene = _make_scene(tmp_path, seed=42)
    assert _resolve_seed(scene) == 42


def test_whole_shot_razor_skips_ffmpeg_cut(patched_executor, tmp_path: Path):
    spec = _spec(window=RetakeWindow(startSec=0.0, endSec=10.016, scope="whole_shot"))
    scene = _make_scene(tmp_path)
    voice_a = tmp_path / "voice-a.wav"
    voice_k = tmp_path / "voice-k.wav"
    sheet_a = tmp_path / "sheet-a.png"
    sheet_k = tmp_path / "sheet-k.png"
    for p in (voice_a, voice_k, sheet_a, sheet_k):
        p.write_bytes(b"x")
    assets = [
        _make_asset("voice-a", voice_a),
        _make_asset("voice-k", voice_k),
        _make_asset("sheet-a", sheet_a, kind="image"),
        _make_asset("sheet-k", sheet_k, kind="image"),
    ]
    db = _MockDB(scene, assets)

    result = _run_async(execute_performance_retake(db, spec, job_id="job-1234", log=lambda _: None))

    assert result["ok"] is True
    ffmpeg_calls = patched_executor["ffmpeg"]
    cut_calls = [c for c in ffmpeg_calls if "-ss" in c and "window" in " ".join(c)]
    assert not cut_calls, "whole_shot should not run an ffmpeg window cut"


def test_comfy_submission_omits_unregistered_workflow_key(patched_executor, tmp_path: Path):
    """Regression: queue_prompt must not pass workflow_key='performance.retake'.

    Live failure 6a03497f: the readiness registry has no H3 model components
    (production H3 Route A bypasses it), so the unregistered key raised
    KeyError('performance.retake') before submission. Node-type validation
    still runs inside queue_prompt via assert_graph_runnable.
    """
    spec = _spec(window=RetakeWindow(startSec=0.0, endSec=10.016, scope="whole_shot"))
    scene = _make_scene(tmp_path)
    voice_a = tmp_path / "voice-a.wav"
    voice_k = tmp_path / "voice-k.wav"
    sheet_a = tmp_path / "sheet-a.png"
    sheet_k = tmp_path / "sheet-k.png"
    for p in (voice_a, voice_k, sheet_a, sheet_k):
        p.write_bytes(b"x")
    assets = [
        _make_asset("voice-a", voice_a),
        _make_asset("voice-k", voice_k),
        _make_asset("sheet-a", sheet_a, kind="image"),
        _make_asset("sheet-k", sheet_k, kind="image"),
    ]
    db = _MockDB(scene, assets)

    result = _run_async(execute_performance_retake(db, spec, job_id="job-1234", log=lambda _: None))

    assert result["ok"] is True
    queue_calls = [c for c in patched_executor["comfy"] if c[0] == "queue_prompt"]
    assert queue_calls, "executor must submit the graph to Comfy"
    for _, _args, kwargs in queue_calls:
        assert not kwargs.get("workflow_key"), (
            "workflow_key must be omitted — 'performance.retake' is not in the "
            "readiness registry and raises KeyError before submission"
        )
        assert float(kwargs.get("timeout_sec") or 0) >= H3_SUBMIT_TIMEOUT_SEC, (
            "live failure 7db0b365: default 60s POST /prompt timed out "
            "(httpx.ReadTimeout); H3 submit must use H3_SUBMIT_TIMEOUT_SEC"
        )


def test_recover_h3_render_rejects_latentsync_fallback(tmp_path: Path, monkeypatch):
    """Regression 35f215b9: do not persist a stale latentsync_* clip as the H3 render."""
    from app.performance_retake.executor import _recover_h3_render

    stale = tmp_path / "latentsync_old_out.mp4"
    stale.write_bytes(b"tiny-wrong")
    good = tmp_path / "proj_perfretake_job1_00001_.mp4"
    good.write_bytes(b"real-h3")

    monkeypatch.setattr(
        "app.performance_retake.executor.comfy.find_output_files",
        lambda history: [stale, good],
    )
    monkeypatch.setattr(
        "app.performance_retake.executor.extract_output_path_from_history",
        lambda history: stale,
    )
    monkeypatch.setattr(
        "app.performance_retake.executor._try_probe",
        lambda path: {
            "width": 346 if "latentsync" in path.name else 1152,
            "height": 256 if "latentsync" in path.name else 640,
            "duration": 1.28 if "latentsync" in path.name else 10.125,
        },
    )
    recovered = _recover_h3_render(
        {},
        filename_prefix="studio/proj_perfretake_job1",
        expected_width=1152,
        expected_height=640,
        min_duration_sec=10.016,
        log=lambda _: None,
    )
    assert recovered == good


def test_prepare_comfy_skips_free_when_queue_busy(monkeypatch):
    logs: list[str] = []
    monkeypatch.setattr(
        "app.codirector.video_intelligence.gpu_lease.wait_for_free_vram",
        lambda **kwargs: {"ok": True, "freeVramGb": 20.0, "waitedSec": 0.1},
    )
    monkeypatch.setattr(
        "app.codirector.video_intelligence.gpu_lease.comfy_generation_active",
        lambda: {"active": True, "running": 1, "pending": 0},
    )
    freed = {"n": 0}

    async def _free(**kwargs):
        freed["n"] += 1
        return {"ok": True}

    monkeypatch.setattr("app.performance_retake.executor.comfy.free_memory", _free)
    _run_async(_prepare_comfy_for_h3_submit(logs.append))
    assert freed["n"] == 0
    assert any("skipping /free" in line for line in logs)


def test_trim_command_uses_exact_window_length(patched_executor, tmp_path: Path):
    from app.performance_retake.executor import _trim_video

    src = tmp_path / "src.mp4"
    dest = tmp_path / "dest.mp4"
    src.write_bytes(b"x")
    _trim_video(src, dest, 10.016, 24.0)
    trim_calls = [c for c in patched_executor["ffmpeg"] if "-t" in c]
    assert trim_calls, "Expected a duration trim ffmpeg call with -t"
    t_index = trim_calls[0].index("-t")
    assert trim_calls[0][t_index + 1] == "10.016"
    assert "libx264" in trim_calls[0]


def test_whole_shot_skips_trim_when_h3_duration_matches(patched_executor, tmp_path: Path):
    spec = _spec(window=RetakeWindow(startSec=0.0, endSec=10.016, scope="whole_shot"))
    scene = _make_scene(tmp_path)
    for name in ("voice-a", "voice-k", "sheet-a", "sheet-k"):
        (tmp_path / f"{name}.bin").write_bytes(b"x")
    assets = [
        _make_asset("voice-a", tmp_path / "voice-a.bin"),
        _make_asset("voice-k", tmp_path / "voice-k.bin"),
        _make_asset("sheet-a", tmp_path / "sheet-a.bin", kind="image"),
        _make_asset("sheet-k", tmp_path / "sheet-k.bin", kind="image"),
    ]
    # Fixture probe returns 10.016s / 1152x640, matching the window.
    result = _run_async(
        execute_performance_retake(_MockDB(scene, assets), spec, job_id="job-1234", log=lambda _: None)
    )
    assert result["ok"] is True
    duration_trims = [
        c for c in patched_executor["ffmpeg"]
        if "-t" in c and "10.016" in c and "libx264" in c
    ]
    assert not duration_trims, "matching whole_shot H3 duration must skip re-encode trim"


def test_provenance_sidecar_contents(patched_executor, tmp_path: Path):
    spec = _spec(generator="minimax-h3-r2v-local", quality="quality")
    scene = _make_scene(tmp_path)
    for name in ("voice-a", "voice-k", "sheet-a", "sheet-k"):
        (tmp_path / name).write_bytes(b"x") if not name.endswith(".png") else None
    voice_a = tmp_path / "voice-a"
    voice_k = tmp_path / "voice-k"
    sheet_a = tmp_path / "sheet-a.png"
    sheet_k = tmp_path / "sheet-k.png"
    for p in (voice_a, voice_k, sheet_a, sheet_k):
        if not p.exists():
            p.write_bytes(b"x")
    db = _MockDB(scene, [
        _make_asset("voice-a", voice_a),
        _make_asset("voice-k", voice_k),
        _make_asset("sheet-a", sheet_a, kind="image"),
        _make_asset("sheet-k", sheet_k, kind="image"),
    ])

    result = _run_async(execute_performance_retake(db, spec, job_id="job-1234", log=lambda _: None))

    sidecar_path = Path(result["sidecarPath"])
    assert sidecar_path.exists()
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["producer"] == "performance_retake"
    assert sidecar["specVersion"] == 1
    assert sidecar["generator"] == "minimax-h3-r2v-local"
    assert "spec" in sidecar
    assert sidecar["spec"]["projectId"] == "p1"
    assert "masterSha256" in sidecar
    assert "outputSha256" in sidecar
    assert sidecar["masterSha256"] == hashlib.sha256(b"fake-master-video-data").hexdigest()


def test_master_sha_mismatch_raises(patched_executor, tmp_path: Path, monkeypatch):
    spec = _spec()
    scene = _make_scene(tmp_path)
    for name in ("voice-a", "voice-k"):
        (tmp_path / name).write_bytes(b"x")
    sheet_a = tmp_path / "sheet-a.png"
    sheet_k = tmp_path / "sheet-k.png"
    for p in (sheet_a, sheet_k):
        p.write_bytes(b"x")
    db = _MockDB(scene, [
        _make_asset("voice-a", tmp_path / "voice-a"),
        _make_asset("voice-k", tmp_path / "voice-k"),
        _make_asset("sheet-a", sheet_a, kind="image"),
        _make_asset("sheet-k", sheet_k, kind="image"),
    ])

    call_count = {"n": 0}

    def alternating_sha256(path: Path) -> str:
        call_count["n"] += 1
        return f"hash-{call_count['n']}"

    monkeypatch.setattr("app.performance_retake.executor._sha256", alternating_sha256)

    with pytest.raises(PerformanceRetakeError, match=f"{S_PERSIST}.*mutated"):
        _run_async(execute_performance_retake(db, spec, job_id="job-1234", log=lambda _: None))


def test_post_review_unavailable_is_flagged_not_faked(patched_executor, tmp_path: Path, monkeypatch):
    spec = _spec(qwenPostReview=True)
    scene = _make_scene(tmp_path)
    for name in ("voice-a", "voice-k"):
        (tmp_path / name).write_bytes(b"x")
    sheet_a = tmp_path / "sheet-a.png"
    sheet_k = tmp_path / "sheet-k.png"
    for p in (sheet_a, sheet_k):
        p.write_bytes(b"x")
    db = _MockDB(scene, [
        _make_asset("voice-a", tmp_path / "voice-a"),
        _make_asset("voice-k", tmp_path / "voice-k"),
        _make_asset("sheet-a", sheet_a, kind="image"),
        _make_asset("sheet-k", sheet_k, kind="image"),
    ])

    def failing_perception(video_path: str, **kwargs):
        if "final" in str(video_path).lower() or "perfretake" in str(video_path).lower():
            raise RuntimeError("worker offline")
        return {
            "modelId": "qwen2-5-omni",
            "summary": "observation",
            "speechSegments": [],
            "audioEvents": [],
            "visualEvents": [],
            "motionEvents": [],
            "characters": [],
        }

    monkeypatch.setattr("app.performance_retake.executor.run_av_perception", failing_perception)

    result = _run_async(execute_performance_retake(db, spec, job_id="job-1234", log=lambda _: None))

    assert result["ok"] is True
    post = result["qwenPostReview"]
    assert post["available"] is False
    assert post.get("postReview") == "unavailable"
    assert "worker offline" in post.get("reason", "")


def test_sub_window_runs_splice(patched_executor, tmp_path: Path):
    spec = _spec(
        window=RetakeWindow(startSec=2.0, endSec=8.0, scope="sub_window"),
        masterDurationSec=10.016,
    )
    # Adjust beats to fit sub-window.
    spec.beats = [
        RetakeBeat(
            kind="dialogue",
            startSec=2.0,
            endSec=5.0,
            characterId=ANADRIYA,
            characterName="Anadriya",
            line="Line.",
            voiceAssetId="voice-a",
        ),
        RetakeBeat(kind="silence", startSec=5.0, endSec=8.0),
    ]
    scene = _make_scene(tmp_path)
    for name in ("voice-a",):
        (tmp_path / name).write_bytes(b"x")
    sheet_a = tmp_path / "sheet-a.png"
    sheet_k = tmp_path / "sheet-k.png"
    for p in (sheet_a, sheet_k):
        p.write_bytes(b"x")
    db = _MockDB(scene, [
        _make_asset("voice-a", tmp_path / "voice-a"),
        _make_asset("sheet-a", sheet_a, kind="image"),
        _make_asset("sheet-k", sheet_k, kind="image"),
    ])

    result = _run_async(execute_performance_retake(db, spec, job_id="job-1234", log=lambda _: None))

    assert result["ok"] is True
    concat_calls = [
        c for c in patched_executor["ffmpeg"] if "concat" in c
    ]
    assert concat_calls, "sub_window should run a concat demuxer splice"


# ---------------------------------------------------------------------------
# API-level routing tests
# ---------------------------------------------------------------------------

def _track_payload(character_id: str = "char-korri") -> dict:
    track = LipSyncTrack(
        slot=1,
        enabled=True,
        audio_asset_id="audio-1",
        character_id=character_id,
        clips=[
            LipSyncClip(
                id="clip-1",
                start=1.0,
                length=2.0,
                audio_asset_id="audio-1",
                character_id=character_id,
                label="We did it, sis!",
            )
        ],
    )
    return json.loads(dumps_lipsync_tracks(LipSyncTracks(tracks=[track])))


def _setup_scene(client, character_id: str = "char-korri", duration_sec: float = 10.0):
    created = client.post("/api/projects", json={"name": "Performance Retake Test"})
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
            "director_json": json.dumps(
                {
                    "prompt_segments": [],
                    "audio_clips": [],
                    "sfx_clips": [],
                    "lipsync": tracks_payload,
                }
            ),
        },
    )
    assert patch.status_code == 200, patch.text
    return pid, sid


def test_default_mode_enqueues_performance_retake(client):
    pid, sid = _setup_scene(client)
    res = client.post(
        f"/api/projects/{pid}/scenes/{sid}/lipsync-tracks/apply",
        json={
            "retake": {
                "references": {
                    "characterSheets": [
                        {"characterId": "char-korri", "assetId": "sheet-k"}
                    ]
                }
            }
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kind"] == "performance_retake"
    params = json.loads(body["params_json"])
    assert params["projectId"] == pid
    assert params["sceneId"] == sid
    assert params["window"]["scope"] == "whole_shot"


def test_legacy_mode_returns_410_without_env_flag(client, monkeypatch):
    monkeypatch.delenv("ADEPT_LEGACY_LIPSYNC", raising=False)
    pid, sid = _setup_scene(client)
    res = client.post(
        f"/api/projects/{pid}/scenes/{sid}/lipsync-tracks/apply",
        json={"mode": "legacy"},
    )
    assert res.status_code == 410
    assert "Performance Retake" in res.text


def test_legacy_mode_allowed_with_env_flag(client, monkeypatch):
    monkeypatch.setenv("ADEPT_LEGACY_LIPSYNC", "1")
    pid, sid = _setup_scene(client)
    res = client.post(
        f"/api/projects/{pid}/scenes/{sid}/lipsync-tracks/apply",
        json={"mode": "legacy"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["kind"] == "dual_lipsync"


def test_explicit_retake_body_enqueues_performance_retake(client):
    pid, sid = _setup_scene(client)
    res = client.post(
        f"/api/projects/{pid}/scenes/{sid}/lipsync-tracks/apply",
        json={
            "retake": {
                "window": {"startSec": 0.0, "endSec": 10.0, "scope": "whole_shot"},
                "beats": [
                    {
                        "kind": "dialogue",
                        "startSec": 0.0,
                        "endSec": 3.0,
                        "characterId": ANADRIYA,
                        "characterName": "Anadriya",
                        "line": "Line one.",
                        "voiceAssetId": "voice-a",
                    },
                    {"kind": "silence", "startSec": 3.0, "endSec": 10.0},
                ],
                "references": {
                    "characterSheets": [
                        {"characterId": ANADRIYA, "assetId": "sheet-a"}
                    ]
                },
            }
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kind"] == "performance_retake"
    params = json.loads(body["params_json"])
    assert len(params["beats"]) == 2
    assert params["beats"][0]["line"] == "Line one."


def test_retake_validation_failure_returns_400(client):
    pid, sid = _setup_scene(client)
    # Beat escapes window.
    res = client.post(
        f"/api/projects/{pid}/scenes/{sid}/lipsync-tracks/apply",
        json={
            "retake": {
                "window": {"startSec": 0.0, "endSec": 5.0, "scope": "whole_shot"},
                "beats": [
                    {
                        "kind": "dialogue",
                        "startSec": 0.0,
                        "endSec": 6.0,
                        "characterId": ANADRIYA,
                        "characterName": "Anadriya",
                        "line": "Too long.",
                        "voiceAssetId": "voice-a",
                    }
                ],
                "references": {
                    "characterSheets": [
                        {"characterId": ANADRIYA, "assetId": "sheet-a"}
                    ]
                },
            }
        },
    )
    assert res.status_code == 400
