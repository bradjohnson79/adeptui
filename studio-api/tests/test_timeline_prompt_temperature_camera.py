"""Timeline prompt temperature + camera compile + reconcile-on-put tests.

No live generate. No Comfy. Follows existing director_timeline / w46 fixtures.
"""

from __future__ import annotations

from app.cinematography import camera_nl_instruction, compile_canonical_camera
from app.director_timeline import CameraClip, DirectorTimeline, PromptSegment
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    SceneTimelineMaster,
    TimelinePromptSegment,
)
from app.director_timeline_w46.generation.adapter import validate_against_capabilities
from app.director_timeline_w46.generation.adapters.minimax_h3_i2v_local import MiniMaxH3I2VLocalAdapter
from app.director_timeline_w46.generation.adapters.minimax_h3_local import MiniMaxH3LocalAdapter
from app.director_timeline_w46.generation.adapters.ltx_local import LtxLocalAdapter
from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest
from app.director_timeline_w46.generation.request_builder import build_timeline_generation_request
from app.director_timeline_w46.orchestrator import _append_timeline_validity_findings, run_preflight
from app.director_timeline_w46.reconcile import reconcile_legacy_to_master


def _master_with_batch(**kwargs) -> SceneTimelineMaster:
    master = SceneTimelineMaster(mode="video_finishing")
    master.batchBlocks.append(
        BatchBlock(
            id="bb_test_0",
            sceneId="sc_test",
            order=0,
            label="Batch 1",
            generatorId=kwargs.pop("generatorId", "minimax-h3-t2v-local"),
            duration=DurationState(plannedDuration=5.0),
            **kwargs,
        )
    )
    return master


def test_prompt_segment_temperature_is_independent_of_weight():
    seg = PromptSegment(text="walk", weight=1.8)
    assert seg.temperature == 1.0
    assert seg.weight == 1.8
    seg2 = PromptSegment(text="walk", temperature=1.4, weight=0.2)
    assert seg2.temperature == 1.4
    assert seg2.weight == 0.2


def test_prompt_segment_keeps_movement_segment_ref_aliases():
    dropped_before = PromptSegment.model_validate(
        {
            "text": "walk",
            "movementSegmentRef": {"documentId": "doc1", "segmentId": "mv1"},
            "movementSegmentRevision": 4,
        }
    )
    assert dropped_before.movement_segment_ref == {"documentId": "doc1", "segmentId": "mv1"}
    assert dropped_before.movement_segment_revision == 4
    snake = PromptSegment.model_validate(
        {"text": "walk", "movement_segment_ref": {"segmentId": "mv2"}, "movement_segment_revision": 1}
    )
    assert snake.movement_segment_ref == {"segmentId": "mv2"}


def test_w46_temperature_default_not_strength():
    seg = TimelinePromptSegment(text="x", strength=1.7)
    assert seg.temperature == 1.0
    assert seg.strength == 1.7


def test_reconcile_on_put_updates_master_before_generate_would_read():
    master = _master_with_batch(
        promptSegments=[
            TimelinePromptSegment(
                legacyPromptSegmentId="leg_a",
                start=0.0,
                length=5.0,
                text="STALE PROMPT",
                temperature=1.0,
            )
        ]
    )
    tl = DirectorTimeline(
        duration_sec=5.0,
        prompt_segments=[
            PromptSegment(
                id="leg_a",
                start=0.5,
                length=4.0,
                text="Inspector current prompt",
                weight=1.9,
                temperature=1.35,
                movement_segment_ref={"segmentId": "mv_live"},
                movement_segment_revision=7,
            )
        ],
        camera_clips=[
            CameraClip(
                id="cam_1",
                start=0.0,
                length=5.0,
                motion_type="dolly_in",
                rig="dolly",
                shot_id="close_up",
                lens_id="35",
                lighting_id="golden_hour",
                focus_id="char_hero",
                focus_name="Hero",
                text="slow push toward the bottle",
            )
        ],
    )
    assert reconcile_legacy_to_master(master, tl) is True
    seg = master.batchBlocks[0].promptSegments[0]
    assert seg.text == "Inspector current prompt"
    assert seg.start == 0.5
    assert seg.length == 4.0
    assert seg.temperature == 1.35
    assert seg.strength == 1.9  # weight maps to strength for compat; not temperature
    assert seg.movementSegmentRef == {"segmentId": "mv_live"}
    assert seg.movementSegmentRevision == 7
    # weight/strength must NOT become temperature
    assert seg.temperature != seg.strength
    cams = master.batchBlocks[0].cameraInstructions
    assert len(cams) == 1
    assert cams[0].shot_id == "close_up"
    assert cams[0].lens_id == "35"
    assert cams[0].lighting_id == "golden_hour"
    assert cams[0].motion_type == "dolly_in"
    assert cams[0].text == "slow push toward the bottle"
    assert cams[0].focus_id == "char_hero"
    assert cams[0].focus_name == "Hero"

    snap = ExecutionSnapshot(batchBlockId=master.batchBlocks[0].id)
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="sc_test",
        batch=master.batchBlocks[0],
        snapshot=snap,
    )
    assert "Inspector current prompt" in req.prompt
    assert "STALE PROMPT" not in req.prompt
    assert req.temperature is None  # MiniMax supportsTemperature=False
    assert req.cameraMotion is None
    assert req.camera is not None
    assert "Camera:" in req.prompt
    assert "close up" in req.prompt.lower() or "close_up" in req.prompt.lower()


def test_weight_strength_not_compiled_as_temperature():
    master = _master_with_batch(
        promptSegments=[
            TimelinePromptSegment(
                text="hero walks in",
                strength=1.8,
                temperature=1.0,
            )
        ]
    )
    snap = ExecutionSnapshot(batchBlockId=master.batchBlocks[0].id)
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="sc_test",
        batch=master.batchBlocks[0],
        snapshot=snap,
    )
    assert req.temperature is None
    dumped = req.model_dump()
    assert dumped.get("temperature") is None
    # MiniMax adapter must not invent cfg/creativity
    adapter = MiniMaxH3LocalAdapter()
    assert adapter.capabilities.supportsTemperature is False
    assert adapter.capabilities.supportsCameraControls is False
    payload_keys = set(TimelineGenerationRequest.model_fields)
    assert "cfg" not in payload_keys
    assert "creativity" not in payload_keys


def test_minimax_payload_has_no_temperature_cfg_creativity():
    adapter = MiniMaxH3LocalAdapter()
    i2v = MiniMaxH3I2VLocalAdapter()
    ltx = LtxLocalAdapter()
    assert adapter.capabilities.supportsTemperature is False
    assert i2v.capabilities.supportsTemperature is False
    assert ltx.capabilities.supportsTemperature is False
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        prompt="a bottle on a table",
        temperature=None,
        cameraMotion=None,
        camera={"shot_id": "close_up", "lens_id": "35", "motion": "dolly_in", "text": "push in"},
    )
    result = adapter.validate(req)
    if adapter.capabilities.executable:
        assert result.ok is True
    else:
        assert result.ok is False
        assert any("not executable" in err.lower() for err in result.errors)
    dumped = req.model_dump(exclude_none=False)
    assert dumped["temperature"] is None
    assert dumped["cameraMotion"] is None
    assert "cfg" not in dumped
    assert "creativity" not in dumped
    from app.minimax_h3.contracts import AdeptMiniMaxH3Request

    keys = set(AdeptMiniMaxH3Request.model_fields)
    assert "temperature" not in keys
    assert "cfg" not in keys
    assert "creativity" not in keys


def test_camera_compile_canonical_and_minimax_prompt():
    master = _master_with_batch()
    master.batchBlocks[0].cameraInstructions = []
    from app.director_timeline_w46.contracts import BatchClip

    master.batchBlocks[0].cameraInstructions.append(
        BatchClip(
            kind="camera",
            motion_type="dolly_in",
            rig="dolly",
            shot_id="close_up",
            lens_id="35",
            lighting_id="golden_hour",
            text="slow push toward the bottle",
        )
    )
    master.batchBlocks[0].promptSegments.append(
        TimelinePromptSegment(text="glass bottle condensation", temperature=1.0)
    )
    camera = compile_canonical_camera(batch=master.batchBlocks[0])
    assert camera is not None
    assert camera["shot_id"] == "close_up"
    assert camera["lens_id"] == "35"
    assert camera["motion"] == "dolly_in"
    nl = camera_nl_instruction(camera)
    assert "Camera:" in nl
    assert "close up" in nl.lower()
    assert "35mm" in nl
    snap = ExecutionSnapshot(batchBlockId=master.batchBlocks[0].id)
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="sc_test",
        batch=master.batchBlocks[0],
        snapshot=snap,
    )
    assert req.camera is not None
    assert req.cameraMotion is None
    assert "Camera:" in req.prompt
    assert "slow push toward the bottle" in req.prompt
    assert "glass bottle condensation" in req.prompt


def test_preflight_empty_required_prompt_video_finishing():
    master = _master_with_batch()
    findings = run_preflight(master)
    codes = {f["code"] for f in findings}
    assert "empty_prompt" in codes


def test_preflight_missing_prompt_image_planning_is_warning_only():
    master = _master_with_batch()
    master.mode = "image_planning"
    findings = run_preflight(master)
    empty_errors = [f for f in findings if f["code"] == "empty_prompt"]
    missing = [f for f in findings if f["code"] == "missing_prompt"]
    assert empty_errors == []
    assert missing
    assert missing[0]["severity"] == "warning"


def test_preflight_focus_deleted_character():
    master = _master_with_batch(
        promptSegments=[TimelinePromptSegment(text="hero walks", temperature=1.0)]
    )
    tl = DirectorTimeline(
        duration_sec=5.0,
        camera_clips=[
            CameraClip(start=0.0, length=2.0, focus_id="char_deleted", focus_name="Deleted"),
        ],
    )
    findings: list = []
    _append_timeline_validity_findings(
        findings, master, tl, known_character_ids={"char_alive"}
    )
    codes = {f.code for f in findings}
    assert "focus_deleted_character" in codes


def test_preflight_clip_outside_duration_and_invalid_length():
    master = _master_with_batch(
        promptSegments=[TimelinePromptSegment(text="ok", start=0.0, length=5.0)]
    )
    tl = DirectorTimeline(
        duration_sec=5.0,
        prompt_segments=[
            PromptSegment(id="out", start=4.0, length=3.0, text="extends past end"),
            PromptSegment(id="bad", start=0.0, length=0.0, text="zero"),
        ],
    )
    findings: list = []
    _append_timeline_validity_findings(findings, master, tl, known_character_ids=set())
    codes = {f.code for f in findings}
    assert "clip_outside_duration" in codes
    assert "invalid_length" in codes


def test_preflight_temperature_unsupported_is_tight():
    master = _master_with_batch(
        promptSegments=[TimelinePromptSegment(text="hero walks", temperature=1.5)]
    )
    findings = run_preflight(master)
    codes = {f["code"] for f in findings}
    assert "temperature_unsupported" in codes
    # default 1.0 is not a mismatch
    master.batchBlocks[0].promptSegments[0].temperature = 1.0
    findings2 = run_preflight(master)
    codes2 = {f["code"] for f in findings2}
    assert "temperature_unsupported" not in codes2


def test_validate_refuses_temperature_when_unsupported():
    caps = MiniMaxH3LocalAdapter.capabilities
    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId="minimax-h3-t2v-local",
        prompt="x",
        temperature=1.4,
    )
    result = validate_against_capabilities(caps, req)
    assert result.ok is False
    assert any("Temperature" in e for e in result.errors)

def test_preflight_focus_fail_closed_when_catalog_down():
    master = _master_with_batch(
        promptSegments=[TimelinePromptSegment(text="hero walks", temperature=1.0)]
    )
    tl = DirectorTimeline(
        duration_sec=5.0,
        camera_clips=[CameraClip(start=0.0, length=2.0, focus_id="char_maybe")],
    )
    findings: list = []
    _append_timeline_validity_findings(findings, master, tl, known_character_ids=None)
    assert any(f.code == "focus_deleted_character" for f in findings)


def test_preflight_environment_focus_is_valid():
    master = _master_with_batch(
        promptSegments=[TimelinePromptSegment(text="hero walks", temperature=1.0)]
    )
    tl = DirectorTimeline(
        duration_sec=5.0,
        camera_clips=[CameraClip(start=0.0, length=2.0, focus_id="environment")],
    )
    findings: list = []
    _append_timeline_validity_findings(findings, master, tl, known_character_ids=None)
    assert all(f.code != "focus_deleted_character" for f in findings)


def test_scene_prompt_prepends_and_dedupes():
    from app.director_timeline_w46.generation.adapters.minimax_h3_local import minimax_built_payload

    snap = ExecutionSnapshot(batchBlockId="bb_sp")
    differ = BatchBlock(
        id="bb_sp",
        sceneId="sc_test",
        generatorId="minimax-h3-t2v-local",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="Korri sits at the counter")],
    )
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="sc_test",
        batch=differ,
        snapshot=snap,
        scene_prompt="E2E timed prompt seed",
    )
    assert req.prompt.startswith("E2E timed prompt seed\nKorri sits at the counter")
    assert req.temperature is None
    assert req.cameraMotion is None

    same = BatchBlock(
        id="bb_sp2",
        sceneId="sc_test",
        generatorId="minimax-h3-t2v-local",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="E2E timed prompt seed")],
    )
    tl = DirectorTimeline(
        duration_sec=5.0,
        camera_clips=[
            CameraClip(id="cam_schnick", start=0.0, length=2.0, motion_type="dolly_in", rig="dolly")
        ],
    )
    req2 = build_timeline_generation_request(
        project_id="p",
        scene_id="sc_test",
        batch=same,
        snapshot=ExecutionSnapshot(batchBlockId=same.id),
        director_timeline=tl,
        window_start=0.0,
        scene_prompt="E2E timed prompt seed",
    )
    # Schnick cert lock: equal scene+timed stays single line + camera NL.
    assert req2.prompt == "E2E timed prompt seed\nCamera: dolly in on dolly"
    assert req2.prompt.count("E2E timed prompt seed") == 1
    assert req2.temperature is None
    assert req2.cameraMotion is None
    payload = minimax_built_payload(req2)
    for banned in ("temperature", "cfg", "creativity", "cameraMotion"):
        assert banned not in payload
    assert payload["prompt"] == "E2E timed prompt seed\nCamera: dolly in on dolly"


def test_preflight_scene_prompt_satisfies_video_finishing():
    master = _master_with_batch()
    findings = run_preflight(master, scene_prompt="E2E timed prompt seed")
    assert not any(f["code"] in {"empty_prompt", "missing_prompt"} for f in findings)
    findings_empty = run_preflight(master, scene_prompt="")
    assert any(f["code"] == "empty_prompt" and f["severity"] == "error" for f in findings_empty)


def test_preflight_image_planning_scene_prompt_clears_warning():
    master = _master_with_batch()
    master.mode = "image_planning"
    findings = run_preflight(master, scene_prompt="")
    assert any(f["code"] == "missing_prompt" and f["severity"] == "warning" for f in findings)
    findings_ok = run_preflight(master, scene_prompt="Scene base")
    assert not any(f["code"] in {"empty_prompt", "missing_prompt"} for f in findings_ok)



def test_pane_image_used_where_supported(monkeypatch):
    from app.director_timeline_w46.contracts import TimelineVisualAnchor
    from app.director_timeline_w46.generation import request_builder as rb

    monkeypatch.setattr(
        rb,
        "_load_scene_pane_bindings",
        lambda project_id, scene_id: [
            {
                "bindingId": "b-pane-img",
                "assetId": "pane-img-1",
                "kind": "image",
                "referenceType": "image",
                "mediaKind": "image",
            }
        ],
    )
    snap = ExecutionSnapshot(batchBlockId="bb_pane_i2v")
    i2v = BatchBlock(
        id="bb_pane_i2v",
        sceneId="sc_test",
        generatorId="minimax-h3-i2v-local",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="hero walks")],
    )
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="sc_test",
        batch=i2v,
        snapshot=snap,
        scene_prompt="Scene base",
    )
    assert req.startImageAssetId == "pane-img-1"
    assert req.generationMode == "image_to_video"
    assert "pane-img-1" not in (req.referenceAssetIds or [])

    seed = BatchBlock(
        id="bb_pane_seed",
        sceneId="sc_test",
        generatorId="seedance-api",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="hero walks")],
        sourceAnchors=[TimelineVisualAnchor(kind="image", assetId="start-1", label="start")],
    )
    req2 = build_timeline_generation_request(
        project_id="p",
        scene_id="sc_test",
        batch=seed,
        snapshot=ExecutionSnapshot(batchBlockId=seed.id),
        scene_prompt="Scene base",
    )
    assert req2.startImageAssetId == "start-1"
    assert "pane-img-1" in (req2.referenceAssetIds or [])


def test_pane_audio_skipped(monkeypatch):
    from app.director_timeline_w46.generation import request_builder as rb

    monkeypatch.setattr(
        rb,
        "_load_scene_pane_bindings",
        lambda project_id, scene_id: [
            {
                "bindingId": "b-pane-aud",
                "assetId": "pane-aud-1",
                "kind": "audio",
                "referenceType": "audio",
                "mediaKind": "audio",
            }
        ],
    )
    batch = BatchBlock(
        id="bb_pane_aud",
        sceneId="sc_test",
        generatorId="seedance-api",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="hero walks")],
    )
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="sc_test",
        batch=batch,
        snapshot=ExecutionSnapshot(batchBlockId=batch.id),
        scene_prompt="Scene base",
    )
    assert "pane-aud-1" not in (req.referenceAssetIds or [])
    assert req.startImageAssetId is None
    assert req.videoReferenceAssetId is None


def test_minimax_t2v_gets_no_pane_images(monkeypatch):
    from app.director_timeline_w46.generation import request_builder as rb

    monkeypatch.setattr(
        rb,
        "_load_scene_pane_bindings",
        lambda project_id, scene_id: [
            {
                "bindingId": "b-pane-img",
                "assetId": "pane-img-1",
                "kind": "image",
                "referenceType": "image",
                "mediaKind": "image",
            }
        ],
    )
    batch = BatchBlock(
        id="bb_pane_mm",
        sceneId="sc_test",
        generatorId="minimax-h3-t2v-local",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[TimelinePromptSegment(text="hero walks")],
        references=[
            {"kind": "image", "role": "image_reference", "assetId": "clip-img-1", "consumed": True},
        ],
    )
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="sc_test",
        batch=batch,
        snapshot=ExecutionSnapshot(batchBlockId=batch.id),
        scene_prompt="Scene base",
    )
    assert req.startImageAssetId is None
    assert req.generationMode == "text_to_video"
    assert "pane-img-1" not in (req.referenceAssetIds or [])
    # Clip / batch.references stay; pane images are not added when max=0.
    assert "clip-img-1" in (req.referenceAssetIds or [])
