"""Timeline resolution comes from the generator capability, not PRODUCTION_PIXELS."""

from app.director_timeline_w46.contracts import BatchBlock, DurationState, ExecutionSnapshot, TimelinePromptSegment
from app.director_timeline_w46.generation.adapters.ltx_local import LtxLocalAdapter
from app.director_timeline_w46.generation.request_builder import _resolution_for_request, build_timeline_generation_request


def test_ltx_capability_is_i2v_1280x704():
    caps = LtxLocalAdapter().capabilities
    assert caps.supportsTextToVideo is False
    assert caps.supportsImageToVideo is True
    assert caps.finalResolution == "1280x704"
    assert "512x288" not in (caps.supportedResolutions or [])
    assert "1280x720" not in (caps.supportedResolutions or [])
    assert _resolution_for_request(caps, "16:9", draft_mode=True) == "1280x704"
    assert _resolution_for_request(caps, "16:9", draft_mode=False) == "1280x704"


def test_ltx_compile_does_not_invent_draft_512x288():
    batch = BatchBlock(
        id="b1",
        sceneId="s",
        label="Hero",
        generatorId="ltx-local",
        duration=DurationState(plannedDuration=5.0),
        promptSegments=[
            TimelinePromptSegment(
                id="ps1",
                start=0,
                length=5,
                text="wide shot",
                role="primary",
                strength=1,
                anchorIds=[],
                executionStrategy="compiled",
                versionId="psv1",
            )
        ],
    )
    snap = ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="ltx-local")
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=batch,
        snapshot=snap,
        aspect_ratio="16:9",
        draft_mode=True,
    )
    assert req.resolution == "1280x704"
    assert req.providerOptions.get("draftMode") is False


def test_ltx_simple_i2v_snaps_720_to_704():
    from app.workflows.ltx_builder import build_ltx_simple_i2v

    graph = build_ltx_simple_i2v(
        checkpoint="ltx-2.3-22b-distilled-fp8.safetensors",
        positive="test",
        negative="",
        width=1280,
        height=720,
        length=113,
        fps=24,
        seed=1,
        start_image="studio/imagegen_edit_97271e7a.png",
    )
    assert graph["5"]["inputs"]["width"] == 1280
    assert graph["5"]["inputs"]["height"] == 704
