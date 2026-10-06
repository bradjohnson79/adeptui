"""The H1 owner stores a slice on an empty later window. Submit only reads Master."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    SceneTimelineMaster,
    TimelinePromptSegment,
)
from app.director_timeline_w46.execution_window_materialize import (
    rematerialize_batch_blocks_from_plan,
)
from app.director_timeline_w46.generation.request_builder import (
    build_timeline_generation_request,
)
from app.director_timeline_w46.generation.window_script import (
    assign_later_window_scripts,
    batch_prompt_ready,
)


def _batch(order: int, text: str, planned: float, *, seg_len: float | None = None) -> BatchBlock:
    length = planned if seg_len is None else seg_len
    segments = []
    if text is not None:
        segments.append(TimelinePromptSegment(text=text, start=0.0, length=length))
    return BatchBlock(
        id=f"bb-{order}",
        sceneId="scene-fresh",
        order=order,
        label=f"Window {order + 1}",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=planned),
        promptSegments=segments,
    )


FULL = (
    "Opening. The host greets the camera at the bar.\n\n"
    "Middle. The camera pans to the guest at the table.\n\n"
    "Ending. The host splashes the lens and the scene cuts to black."
)


def _fresh(duration: float, windows: list[tuple[float, float]]) -> SceneTimelineMaster:
    master = SceneTimelineMaster(
        version=1,
        mode="video_finishing",
        batchBlocks=[_batch(0, FULL, duration, seg_len=duration)],
        executionSnapshots={},
        migratedFromDirectorJson=True,
    )
    result = rematerialize_batch_blocks_from_plan(
        master,
        windows=[{"start": start, "end": end} for start, end in windows],
        generator_id="minimax-h3",
        scene_id="scene-fresh",
        duration_seconds=duration,
        force=True,
    )
    assert result.get("ok") is True
    return master


def test_45s_scene_keeps_the_authored_prompt_on_the_root():
    master = _fresh(45.0, [(0.0, 15.0), (15.0, 30.0), (30.0, 45.0)])
    assert master.batchBlocks[0].promptSegments[0].text == FULL
    assert master.batchBlocks[1].promptSegments[0].text.startswith("Middle.")
    assert master.batchBlocks[2].promptSegments[0].text.startswith("Ending.")
    assert "CONTINUATION" not in master.batchBlocks[1].promptSegments[0].text
    assert "WINDOW SCOPE" not in master.batchBlocks[2].promptSegments[0].text
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="scene-fresh",
        batch=master.batchBlocks[0],
        snapshot=ExecutionSnapshot(
            batchBlockId=master.batchBlocks[0].id,
            selectedGenerator="minimax-h3",
        ),
    )
    assert FULL in req.prompt
    assert "WINDOW SCOPE" not in req.prompt


def test_60s_script_stays_on_the_window_that_holds_it():
    script = (
        "Opening. The host greets the camera at the bar.\n\n"
        "The camera pans to the guest at the table.\n\n"
        "The host returns with the thermos.\n\n"
        "Ending. The host splashes the lens and the scene cuts to black."
    )
    master = SceneTimelineMaster(
        version=1,
        mode="video_finishing",
        batchBlocks=[_batch(0, script, 60.0, seg_len=60.0)],
        executionSnapshots={},
        migratedFromDirectorJson=True,
    )
    result = rematerialize_batch_blocks_from_plan(
        master,
        windows=[
            {"start": 0.0, "end": 15.0},
            {"start": 15.0, "end": 30.0},
            {"start": 30.0, "end": 45.0},
            {"start": 45.0, "end": 60.0},
        ],
        generator_id="minimax-h3",
        scene_id="scene-fresh",
        duration_seconds=60.0,
        force=True,
    )
    assert result.get("ok") is True
    assert len(master.batchBlocks) == 4
    assert master.batchBlocks[0].promptSegments[0].text == script
    assert master.batchBlocks[3].promptSegments[0].text.startswith("Ending.")
    assert "CONTINUATION" not in master.batchBlocks[1].promptSegments[0].text
    assert "WINDOW SCOPE" not in master.batchBlocks[3].promptSegments[0].text


def test_contained_prompt_stays_on_its_window():
    root = _batch(0, "Opening only.", 15.0)
    guest = _batch(1, "The guest reads the paper.", 15.0)
    guest.promptSegments[0].start = 15.0
    blank = _batch(2, "", 15.0)
    master = SimpleNamespace(batchBlocks=[root, guest, blank])
    assign_later_window_scripts(master)
    assert guest.promptSegments[0].text == "The guest reads the paper."
    assert float(guest.promptSegments[0].start) == 15.0
    assert "Opening only." in root.promptSegments[0].text
    assert blank.promptSegments[0].text == "Opening only."
    assert "CONTINUATION" not in blank.promptSegments[0].text


def test_partial_final_window_does_not_invent_a_prompt():
    master = _fresh(38.0, [(0.0, 15.0), (15.0, 30.0), (30.0, 38.0)])
    assert len(master.batchBlocks) == 3
    assert master.batchBlocks[2].duration.plannedDuration == pytest.approx(8.0)
    assert master.batchBlocks[0].promptSegments[0].text == FULL
    last = master.batchBlocks[2].promptSegments[0].text
    assert "30s to 38s" not in last
    assert "CONTINUATION" not in last
    assert last.startswith("Ending.")
    assert "Opening." not in last


def test_empty_extension_is_not_ready_and_submit_does_not_heal_it():
    stub = _batch(
        1,
        "[CONTINUATION window 2 | scene time 15s-30s] Continue from the prior window.",
        15.0,
    )
    assert batch_prompt_ready(stub) is False
    with pytest.raises(ValueError, match="BATCH_PROMPT_REQUIRED"):
        build_timeline_generation_request(
            project_id="p",
            scene_id="scene-fresh",
            batch=stub,
            snapshot=ExecutionSnapshot(batchBlockId=stub.id, selectedGenerator="minimax-h3"),
        )


def test_seedance_delivery_is_the_stored_slice(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("request_builder must not slice the story")

    monkeypatch.setattr(
        "app.director_timeline_w46.generation.window_script.slice_story_for_window",
        boom,
    )
    stored = "Middle. The camera pans to the guest at the table."
    batch = _batch(1, stored, 15.0)
    batch.generatorId = "seedance-2.0-mini"
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="scene-fresh",
        batch=batch,
        snapshot=ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="seedance-2.0-mini"),
    )
    assert req.prompt == stored
    assert "CONTINUATION" not in req.prompt
    assert "WINDOW SCOPE" not in req.prompt


def test_request_builder_does_not_reslice(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("request_builder must not slice the story")

    monkeypatch.setattr(
        "app.director_timeline_w46.generation.window_script.slice_story_for_window",
        boom,
    )
    batch = _batch(0, "Opening. The host greets the camera.", 15.0)
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="scene-fresh",
        batch=batch,
        snapshot=ExecutionSnapshot(batchBlockId=batch.id, selectedGenerator="minimax-h3"),
    )
    assert "Opening." in req.prompt


def test_second_assign_does_not_move_the_script():
    master = _fresh(45.0, [(0.0, 15.0), (15.0, 30.0), (30.0, 45.0)])
    before = [block.promptSegments[0].text for block in master.batchBlocks]
    assert assign_later_window_scripts(master) is False
    after = [block.promptSegments[0].text for block in master.batchBlocks]
    assert after == before
    assert "Opening." in before[0]
    assert "Ending." in before[0]
    assert before[1].startswith("Middle.")
    assert before[2].startswith("Ending.")
