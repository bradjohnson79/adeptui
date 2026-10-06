"""Bounded Timeline Re-take â€” range mark, selected generator, Adept-side compose."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import orchestrator, service, store
from app.director_timeline_w46.contracts import (
    ApprovedClip,
    BatchBlock,
    CandidateVersion,
    DurationState,
    ExecutionSnapshot,
    GenerationJobRef,
    SceneTimelineMaster,
    TimelinePromptSegment,
)
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.director_timeline_w46.range_replacement import compose_range_media


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Range Retake", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="corridor walk",
            duration_sec=5.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def _color_video(path: Path, color: str, seconds: float) -> None:
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        pytest.skip("ffmpeg required")
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=64x64:d={seconds}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not path.is_file():
        pytest.skip(f"ffmpeg color video failed: {(proc.stderr or '')[:200]}")


def test_compose_keeps_before_and_after(tmp_path):
    source = tmp_path / "source.mp4"
    generated = tmp_path / "gen.mp4"
    dest = tmp_path / "out.mp4"
    _color_video(source, "red", 3.0)
    _color_video(generated, "blue", 1.0)
    result = compose_range_media(
        source_path=source,
        generated_path=generated,
        dest_path=dest,
        start=1.0,
        length=1.0,
        source_duration=3.0,
    )
    assert result["ok"] is True
    assert dest.is_file()
    assert result["pieceCount"] == 3
    assert result["duration"] >= 2.5


def test_request_builder_uses_range_prompt_and_duration():
    """Range retake inherits ESTABLISHED + TARGET BEAT + USER DELTA (no wipe)."""
    batch = BatchBlock(
        id="bb1",
        sceneId="s",
        generatorId="ltx-local",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[
            TimelinePromptSegment(id="ps1", start=0, length=5, text="FULL BATCH PROMPT THAT MUST NOT WIN"),
        ],
    )
    snap = ExecutionSnapshot(
        batchBlockId="bb1",
        continuityState={
            "rangeReplacement": {
                "start": 1.2,
                "length": 2.0,
                "prompt": "LIVE-RANGE-REPLACEMENT-PROMPT",
                "startImageAssetId": "cut-in-frame",
            },
            "userCorrection": {
                "delta": "LIVE-RANGE-REPLACEMENT-PROMPT",
                "prompt": "LIVE-RANGE-REPLACEMENT-PROMPT",
                "start": 1.2,
                "length": 2.0,
            },
        },
    )
    req = build_timeline_generation_request(project_id="p", scene_id="s", batch=batch, snapshot=snap)
    # FULL BATCH establishment MAY appear; USER DELTA must appear; compiled contains both.
    assert "LIVE-RANGE-REPLACEMENT-PROMPT" in (req.prompt or "")
    assert "FULL BATCH" in (req.prompt or "")
    assert "[ESTABLISHED SCENE" in (req.prompt or "")
    assert "[USER DELTA]" in (req.prompt or "")
    assert req.duration == 2.0
    assert req.startImageAssetId == "cut-in-frame"
    assert req.providerOptions.get("rangeReplacement", {}).get("length") == 2.0
    pkg = req.providerOptions.get("retakeContextPackage") or {}
    assert pkg.get("userDelta") == "LIVE-RANGE-REPLACEMENT-PROMPT"
    assert "FULL BATCH" in (pkg.get("authoredPrompt") or "")
    assert (pkg.get("userCorrection") or {}).get("delta") == "LIVE-RANGE-REPLACEMENT-PROMPT"
    dbg = pkg.get("debug") or {}
    assert dbg.get("userDelta") == "LIVE-RANGE-REPLACEMENT-PROMPT"
    assert "LIVE-RANGE-REPLACEMENT-PROMPT" in (dbg.get("compiledPrompt") or "")
    assert "LIVE-RANGE-REPLACEMENT-PROMPT" in (dbg.get("generatorRequestPrompt") or "")


def test_retake_range_refuses_without_generated_take(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    service.patch_batch(db, pid, sid, batch_id, {"generatorId": "ltx-local"})
    out = orchestrator.retake_range(
        db, pid, sid, batch_id, start=1.0, length=1.5, prompt="replace the stumble"
    )
    assert out["ok"] is False
    assert out["error"] == "GENERATED_TAKE_REQUIRED"


def test_retake_range_refuses_hosted_without_spend(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = master.batchBlocks[0]
    batch.generatorId = "kling-api"
    batch.approvedClip = ApprovedClip(assetId="asset-approved", executionSnapshotId="snap-a")
    store.save_master(db, pid, sid, master)

    class _Hosted:
        label = "Kling"
        locality = "hosted"
        executable = True
        inPaintStrategies = ["complete_batch_retake", "range_replacement"]
        supportsImageToVideo = True
        disabledReason = ""
        readiness = "Ready"

    with patch.object(orchestrator, "get_generator", return_value=_Hosted()):
        out = orchestrator.retake_range(
            db, pid, sid, batch_id, start=0.0, length=1.5, prompt="replace the stumble"
        )
    assert out["ok"] is False
    assert out["error"] == "API_CREDIT_CONFIRMATION_REQUIRED"


def test_retake_range_refuses_empty_prompt(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    out = orchestrator.retake_range(db, pid, sid, batch_id, start=1.0, length=1.5, prompt="   ")
    assert out["ok"] is False
    assert out["error"] == "REPLACEMENT_PROMPT_REQUIRED"


def test_retake_range_submits_selected_generator_not_minimax(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = master.batchBlocks[0]
    batch.generatorId = "ltx-local"
    # GENERATED take only — no approvedClip (Chief dual mission B)
    batch.candidateVersions = [
        CandidateVersion(
            executionSnapshotId="snap-a",
            assetId="asset-generated",
            label="Take A",
            takeId="take_gen_a",
        )
    ]
    batch.status = "CandidateReady"
    batch.approvedClip = None
    store.save_master(db, pid, sid, master)

    captured = {}

    def fake_submit(db, project_id, scene_id, bid, **kwargs):
        captured.update(kwargs)
        captured["batch_id"] = bid
        return {"ok": True, "generatorId": "ltx-local", "mock": False}

    class _LocalReady:
        label = "LTX Local"
        locality = "local"
        executable = True
        inPaintStrategies = ["complete_batch_retake", "range_replacement"]
        supportsImageToVideo = True
        disabledReason = ""
        readiness = "Ready"

    with patch.object(orchestrator, "get_generator", return_value=_LocalReady()):
        with patch.object(orchestrator, "submit_batch_generation", side_effect=fake_submit):
            with patch.object(orchestrator, "add_repair_range", return_value={"ok": True, "ranges": [{"id": "rr_1"}]}):
                out = orchestrator.retake_range(
                    db, pid, sid, batch_id, start=0.0, length=2.0, prompt="LIVE-RANGE-MARK"
                )
    assert out["ok"] is True, out
    assert captured["batch_id"] == batch_id
    rr = captured["continuity"]["rangeReplacement"]
    assert rr["prompt"] == "LIVE-RANGE-MARK"
    assert rr["length"] == 2.0
    assert rr["sourceAssetId"] == "asset-generated"
    assert captured["continuity"]["reTakeReason"] == "range_replacement"


def test_retake_failure_keeps_playable_approved_take(db_scene):
    from app.director_timeline_w46.generation.watcher import _mark_job_failed

    db, pid, sid = db_scene
    service.workspace(db, pid, sid)
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = master.batchBlocks[0]
    batch.status = "Generating"
    batch.approvedClip = ApprovedClip(assetId="asset-keep", executionSnapshotId="snap-a", candidateId="cand-a")
    batch.generationJobs = [
        GenerationJobRef(executionSnapshotId="snap-retake", status="running", generatorId="minimax-h3"),
    ]
    store.save_master(db, pid, sid, master)

    _mark_job_failed(db, pid, sid, batch.id, "snap-retake", "RETAKE_FAIL", "missing voices")

    live = SceneTimelineMaster.model_validate(store.load_master(db, pid, sid)["master"])
    kept = live.batchBlocks[0]
    assert kept.status == "Approved"
    assert kept.approvedClip is not None
    assert kept.approvedClip.assetId == "asset-keep"
    assert kept.generationJobs[0].status == "failed"


def test_timeline_capable_generators_list_range_replacement():
    from app.production_control.generator_authority import timeline_generator_snapshot

    rows = {row.id: row for row in timeline_generator_snapshot()}
    assert "ltx-local" in rows
    assert "range_replacement" in rows["ltx-local"].inPaintStrategies
    for row in rows.values():
        if row.supportsTimelineGeneration:
            assert "range_replacement" in row.inPaintStrategies, row.id
        if not row.supportsTimelineGeneration:
            assert "range_replacement" not in row.inPaintStrategies, row.id



def test_retake_range_allows_candidate_ready_without_approved_clip(db_scene):
    """Retake eligibility uses current generated take — Approve is not required."""
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = master.batchBlocks[0]
    batch.generatorId = "ltx-local"
    batch.status = "CandidateReady"
    batch.approvedClip = None
    batch.candidateVersions = [
        CandidateVersion(
            executionSnapshotId="snap-cand",
            assetId="asset-candidate-ready",
            label="Take A",
        )
    ]
    batch.activeTakeId = batch.candidateVersions[0].takeId
    batch.currentTakeId = batch.candidateVersions[0].takeId
    batch.currentTakeAssetId = "asset-candidate-ready"
    store.save_master(db, pid, sid, master)

    captured = {}

    def fake_submit(db, project_id, scene_id, bid, **kwargs):
        captured.update(kwargs)
        captured["batch_id"] = bid
        return {"ok": True, "generatorId": "ltx-local", "mock": False}

    class _Local:
        label = "LTX"
        locality = "local"
        executable = True
        inPaintStrategies = ["complete_batch_retake", "range_replacement"]
        supportsImageToVideo = True
        disabledReason = ""
        readiness = "Ready"

    with patch.object(orchestrator, "get_generator", return_value=_Local()):
        with patch.object(orchestrator, "submit_batch_generation", side_effect=fake_submit):
            with patch.object(
                orchestrator, "add_repair_range", return_value={"ok": True, "ranges": [{"id": "rr_cand"}]}
            ):
                out = orchestrator.retake_range(
                    db, pid, sid, batch_id, start=0.0, length=1.5, prompt="fix candidate take"
                )
    assert out["ok"] is True, out
    assert captured["continuity"]["rangeReplacement"]["sourceAssetId"] == "asset-candidate-ready"


def test_workspace_generation_progress_shape(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    assert ws.get("ok") is True
    gp = ws.get("generationProgress")
    assert isinstance(gp, dict)
    for key in (
        "currentBatchIndex",
        "totalBatches",
        "currentBatchId",
        "batchStatus",
        "batchProgress",
        "sceneStatus",
        "message",
    ):
        assert key in gp, key
    assert gp["totalBatches"] >= 1
    assert gp["currentBatchIndex"] >= 1
    assert gp["sceneStatus"] in {
        "idle",
        "queued",
        "generating",
        "blocked_continuity",
        "partial_failed",
        "complete",
        "cancelled",
    }
    assert 0.0 <= float(gp["batchProgress"]) <= 1.0
    assert isinstance(gp["message"], str)


def test_retake_inheritance_local_beat_not_full_dump_and_debug_fields():
    from app.director_timeline_w46.generation.retake_context_package import (
        build_retake_context_package,
    )
    from app.director_timeline_w46.contracts import PromptNameBinding

    established = "\n\n".join(
        [
            "Semi-realistic anime scene with cinematic anime lighting.",
            "Anadriya and Korri are sitting on the couch inside Anadriya's Quarters.",
            "[SHOT 1: Wide 2 Shot]\nIntro beat with interviewer.",
            '[SHOT 2: Close Up on Korri]\nKorri says abrasively:\n"Renkoka obviously!"',
            '[SHOT 3: Over the Shoulder on Anadriya]\nAnadriya snaps and says\n"Korri!"',
            "[SHOT 4: Wide]\nClosing beat on the couch.",
        ]
    )
    batch = BatchBlock(
        id="bb_quarters",
        sceneId="6a7a8a8b-71a1-41e2-8900-871c1b3d71db",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=15.0),
        promptSegments=[
            TimelinePromptSegment(
                id="ps1",
                start=0,
                length=15,
                text=established,
                referenceBindingIds=[
                    "b034058d-0014-4f1c-877d-5fa0c4458d9c",
                    "16ce0150-ba8b-4b85-8bbd-0af56902b737",
                ],
                referenceNameBindings=[
                    PromptNameBinding(
                        binding_id="b034058d-0014-4f1c-877d-5fa0c4458d9c",
                        prompt_name="Anadriya",
                        type="character",
                        tag="@Anadriya",
                    ),
                    PromptNameBinding(
                        binding_id="16ce0150-ba8b-4b85-8bbd-0af56902b737",
                        prompt_name="Korri",
                        type="character",
                        tag="@Korri",
                    ),
                ],
            )
        ],
        candidateVersions=[
            CandidateVersion(
                executionSnapshotId="snap-q",
                assetId="asset-quarters",
                label="Take A",
                takeId="take_bc2f52901b0a",
            )
        ],
        currentTakeId="take_bc2f52901b0a",
        currentTakeAssetId="asset-quarters",
    )
    delta = 'Korri says the line, not Anadriya: "Renkoka obviously!"'
    pkg = build_retake_context_package(
        batch=batch,
        range_rep={"start": 3.0, "length": 4.0, "prompt": delta, "sourceAssetId": "asset-quarters"},
        user_correction={"delta": delta, "prompt": delta, "start": 3.0, "length": 4.0},
        project_style="cinematic_anime",
        style_phrase="cinematic anime",
        supports_image_to_video=False,
    )
    assert established in (pkg["establishedScene"] or "")
    assert pkg["userDelta"] == delta
    assert delta in pkg["compiledPrompt"]
    assert "[ESTABLISHED SCENE" in pkg["compiledPrompt"]
    assert "[TARGET BEAT" in pkg["compiledPrompt"]
    assert "[USER DELTA]" in pkg["compiledPrompt"]
    # local beat must not be a silent full-scene dump when shots can narrow
    assert pkg["localBeat"]
    assert pkg["localBeat"] != established or pkg["localBeatMeta"]["method"] in {
        "nearest_segment",
        "paragraph_cluster",
    }
    if pkg["localBeatMeta"]["method"] == "shot_window":
        assert len(pkg["localBeat"]) < len(established)
    assert pkg["authoredPrompt"] == established
    assert pkg["userCorrection"]["delta"] == delta
    assert pkg["currentTake"]["currentTakeId"] == "take_bc2f52901b0a"
    assert pkg["currentTake"]["currentTakeAssetId"] == "asset-quarters"
    assert pkg["debug"]["userDelta"] == delta
    assert delta in pkg["debug"]["compiledPrompt"]
    assert delta in pkg["debug"]["generatorRequestPrompt"]
    assert pkg["boundaryContinuity"]["supportsImageToVideo"] is False
    assert "NOT faked" in (pkg["boundaryContinuity"].get("honesty") or "")
    # Speaker: Korri must bind for "Korri says..." owner prose / delta
    cues = (pkg.get("speakers") or {}).get("cues") or []
    korri_hits = [
        c
        for c in cues
        if "korri" in str(c.get("speakerName") or "").lower()
        or c.get("speakerBindingId") == "16ce0150-ba8b-4b85-8bbd-0af56902b737"
    ]
    assert korri_hits, f"expected Korri speaker cue, got {cues!r} / {pkg.get('speakers')}"


def test_request_builder_h3_range_retake_does_not_fake_i2v():
    batch = BatchBlock(
        id="bb_h3",
        sceneId="s",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=15.0),
        promptSegments=[
            TimelinePromptSegment(
                id="ps1",
                start=0,
                length=15,
                text="ESTABLISHED Quarters interview setup with Anadriya and Korri on the couch.",
            )
        ],
    )
    snap = ExecutionSnapshot(
        batchBlockId="bb_h3",
        continuityState={
            "rangeReplacement": {
                "start": 2.0,
                "length": 3.0,
                "prompt": "USER-DELTA-KORRI-LINE",
            }
        },
    )
    req = build_timeline_generation_request(project_id="p", scene_id="s", batch=batch, snapshot=snap)
    assert "USER-DELTA-KORRI-LINE" in (req.prompt or "")
    assert "ESTABLISHED Quarters" in (req.prompt or "")
    assert req.duration == 3.0
    pkg = req.providerOptions.get("retakeContextPackage") or {}
    assert "ESTABLISHED Quarters" in (pkg.get("authoredPrompt") or "")
    assert "USER-DELTA-KORRI-LINE" not in (pkg.get("authoredPrompt") or "")
    assert (pkg.get("userCorrection") or {}).get("delta") == "USER-DELTA-KORRI-LINE"
    assert (pkg.get("debug") or {}).get("generatorRequestPrompt") == req.prompt


def test_h3_local_beat_primary_shot_drops_overlapping_shot3():
    """~3-7s range overlapping Shot2 CU Korri + Shot3 Anadriya -> primary Shot2 only."""
    from app.director_timeline_w46.generation.retake_context_package import extract_local_beat

    established = """Semi-realistic anime scene with cinematic anime lighting.

Anadriya and Korri are sitting on the couch inside Anadriya's Quarters. There is a documentary film crew with them and a male interviewer behind the camera.

[SHOT 1: Wide 2 Shot on Anadriya and Korri]
Intro beat with interviewer out of shot.

[SHOT 2: Full Close Up on Korri]
Korri says abrasively:
"Renkoka obviously!"

[SHOT 3: Over the Shoulder shot on Anadriya.]
Anadriya snaps and says
"Korri!"

[SHOT 4: Over the Shoulder Shot on Korri]
Korri replies with a smile.

[SHOT 5: Wide 2 shot on both Anadriya and Korri]
Closing wide beat.

[SHOT 6: Full Close Up on Anadriya]
Anadriya looks annoyed."""
    batch = BatchBlock(
        id="bb_h3_beat",
        sceneId="s",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=15.0),
        promptSegments=[
            TimelinePromptSegment(id="ps1", start=0, length=15, text=established),
        ],
    )
    delta = 'Full close-up on Korri. Korri says the line, not Anadriya. Film crew OUT OF FRAME.'
    beat = extract_local_beat(
        established=established,
        batch=batch,
        range_start=3.0,
        range_length=4.0,
        user_delta=delta,
    )
    assert beat["method"] == "primary_shot" or "primary_shot" in str(beat["method"])
    assert beat["isFullDump"] is False
    assert beat["primaryShotHeader"] and "SHOT 2" in beat["primaryShotHeader"].upper()
    assert "Full Close Up on Korri" in (beat["primaryShotHeader"] or "") or "Korri" in (beat["text"] or "")
    dropped = " ".join(beat.get("droppedOverlappingShots") or []).upper()
    assert "SHOT 3" in dropped or "SHOT3" in dropped.replace(" ", "")
    assert "Anadriya snaps" not in (beat["text"] or "")
    assert "[SHOT 3" not in (beat["text"] or "")
    assert "[SHOT 2" in (beat["text"] or "") or "Full Close Up on Korri" in (beat["text"] or "")
    assert beat.get("rangeTooWideHint") is True


def test_h3_visual_lock_and_established_setup_strips_shots():
    """Compiled prompt carries HARD CONSTRAINTS; establishedSetup strips [SHOT] + crew-present."""
    from app.director_timeline_w46.generation.retake_context_package import (
        build_retake_context_package,
        established_setup_only,
    )

    established = """Semi-realistic anime scene with cinematic anime lighting.

Anadriya and Korri are sitting on the couch inside Anadriya's Quarters. There is a documentary film crew with them and a male interviewer behind the camera. Anadriya and Korri are being interviewed by the film crew.

[SHOT 1: Wide 2 Shot on Anadriya and Korri]
Wide open.

[SHOT 2: Full Close Up on Korri]
Korri says abrasively:
"Renkoka obviously!"

[SHOT 3: Over the Shoulder shot on Anadriya.]
Anadriya snaps and says
"Korri!"

[SHOT 4: Over the Shoulder Shot on Korri]
Korri replies.

[SHOT 5: Wide 2 shot on both]
Embarrassed whisper.

[SHOT 6: Full Close Up on Anadriya]
Closing CU."""
    batch = BatchBlock(
        id="bb_h3_vl",
        sceneId="s",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=15.0),
        promptSegments=[TimelinePromptSegment(id="ps1", start=0, length=15, text=established)],
        candidateVersions=[
            CandidateVersion(
                executionSnapshotId="snap-vl",
                assetId="asset-vl",
                label="Take A",
                takeId="take_vl",
            )
        ],
        currentTakeId="take_vl",
        currentTakeAssetId="asset-vl",
    )
    delta = 'Full CU on Korri whole duration. Crew OUT OF FRAME. Korri says the line, not Anadriya.'
    setup = established_setup_only(established)
    assert "[SHOT" not in setup
    assert "couch" in setup.lower()
    assert "out of frame" in setup.lower()

    pkg = build_retake_context_package(
        batch=batch,
        range_rep={"start": 3.0, "length": 4.0, "prompt": delta, "sourceAssetId": "asset-vl"},
        user_correction={"delta": delta, "prompt": delta, "start": 3.0, "length": 4.0},
        supports_image_to_video=False,
    )
    cp = pkg["compiledPrompt"]
    assert "HARD CONSTRAINTS" in cp
    assert ("ENTIRE TARGET BEAT" in cp or "whole TARGET BEAT" in cp or "TARGET BEAT duration" in cp)
    assert "OUT OF FRAME" in cp
    assert "[ESTABLISHED SCENE" in cp
    assert "[TARGET BEAT" in cp
    assert "[USER DELTA]" in cp
    assert "[SHOT" not in (pkg.get("establishedSetup") or "")
    # Delivery ESTABLISHED must not reopen on Wide 2 Shot list (PREV may carry Shot1 as context only)
    estab_section = cp.split("[PREV BEAT", 1)[0] if "[PREV BEAT" in cp else cp.split("[TARGET BEAT", 1)[0]
    assert "[SHOT 1" not in estab_section
    assert "[SHOT 2" not in estab_section
    assert "[ESTABLISHED SCENE" in estab_section
    # PREV is context only — may include Shot1 header but must not be generation scope
    if "[PREV BEAT" in cp:
        prev_section = cp.split("[PREV BEAT", 1)[1].split("[TARGET BEAT", 1)[0]
        assert "do not regenerate" in cp.lower()
    assert pkg["boundaryContinuity"]["supportsImageToVideo"] is False
    assert pkg["boundaryContinuity"]["i2vAttached"] is False
    honesty = pkg["boundaryContinuity"].get("honesty") or ""
    assert "NOT faked" in honesty or "not faked" in honesty.lower()
    meta = pkg.get("localBeatMeta") or {}
    assert meta.get("method") and "primary_shot" in str(meta.get("method"))
    assert meta.get("isFullDump") is False
    dbg = pkg.get("debug") or {}
    assert dbg.get("localBeatMethod") and "primary_shot" in str(dbg.get("localBeatMethod"))
    assert dbg.get("primaryShotHeader")
    dropped = " ".join(dbg.get("droppedOverlappingShots") or []).upper()
    assert "SHOT 3" in dropped
    # TARGET / PREV / NEXT labels
    assert "[PREV BEAT" in cp
    assert "[NEXT BEAT" in cp
    assert "do not regenerate" in cp.lower()
    # HARD CONSTRAINTS + effective H3 exclusions
    assert "HARD CONSTRAINTS" in cp
    assert "T1 > T2 > T3 > T4" in cp or "T1>T2>T3>T4" in cp
    assert pkg.get("hardConstraints") and "OUT OF FRAME" in pkg["hardConstraints"]
    excl = pkg.get("effectiveH3Exclusions") or []
    assert any("film crew" in str(x).lower() for x in excl)
    assert any("interviewer" in str(x).lower() for x in excl)
    assert "Effective H3 exclusions" in cp
    # Prove dump aliases
    assert dbg.get("actualH3BoundPrompt") == cp
    assert dbg.get("compiledPrompt") == cp
    assert dbg.get("generatorRequestPrompt") == cp
    assert dbg.get("userDelta") == delta
    assert dbg.get("targetBeat")
    assert dbg.get("hardConstraints")
    assert dbg.get("nextBeatExcluded")
    assert dbg.get("prevBeatContext")
    # NEXT excluded contains Shot3 when primary is Shot2
    nxt = pkg.get("nextBeatExcluded") or {}
    nxt_blob = f"{nxt.get('label') or ''} {nxt.get('text') or ''}".upper()
    assert "SHOT 3" in nxt_blob or nxt.get("containsShot3") is True
    assert (nxt.get("doNotRegenerate") is True)
    # Crew-present prose must NOT remain in generator-bound prompt (contradiction)
    bound = pkg.get("actualH3BoundPrompt") or cp
    assert "being interviewed by the film crew" not in bound.lower()
    assert "there is a documentary film crew with them" not in bound.lower()
    # Overlap warning UX surface
    ow = pkg.get("overlapWarning") or {}
    assert ow.get("spansMultipleShots") is True
    assert any("SHOT 3" in str(x).upper() for x in (ow.get("droppedShots") or []))
    assert ow.get("rangeTooWideHint") is True
    assert ow.get("message")
    assert dbg.get("rootCauseHints")


def test_h3_supports_i2v_false_boundary_honesty():
    from app.director_timeline_w46.generation.retake_context_package import build_retake_context_package

    batch = BatchBlock(
        id="bb_h3_i2v",
        sceneId="s",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=15.0),
        promptSegments=[
            TimelinePromptSegment(
                id="ps1",
                start=0,
                length=15,
                text="Quarters interview. Film crew present.\n\n[SHOT 1: Wide]\nOpen.\n\n[SHOT 2: Full Close Up on Korri]\nKorri line.\n\n[SHOT 3: OTS Anadriya]\nAnadriya reacts.",
            )
        ],
    )
    pkg = build_retake_context_package(
        batch=batch,
        range_rep={"start": 3.0, "length": 4.0, "prompt": "Full CU Korri; crew out"},
        supports_image_to_video=False,
    )
    bc = pkg["boundaryContinuity"]
    assert bc["i2vAttached"] is False
    assert bc["supportsImageToVideo"] is False
    assert "NOT faked" in (bc.get("honesty") or "")

