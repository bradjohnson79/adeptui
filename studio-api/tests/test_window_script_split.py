"""Master owns Timed Prompt text.

An empty later window receives one stored slice before submit. A window that
already has story text is not rewritten. Submit does not slice again.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    ExecutionSnapshot,
    TimelinePromptSegment,
)
from app.director_timeline_w46.generation.request_builder import (
    build_timeline_generation_request,
)
from app.director_timeline_w46.generation.window_script import (
    assign_later_window_scripts,
    h3_spoken_lock,
    scrub_observation_line,
    slice_story_for_window,
)
from app.workflows.h3_ref2v_builder import build_h3_ref2v, h3_prompt_text


FULL_45 = (
    "Korri stands at the barista bar and smiles at the camera.\n\n"
    'KORRI\n"Welcome to Schnick coffee."\n\n'
    "The phone camera pans to Cade at the table.\n\n"
    'CADE\n"Do I really have to read this?"\n\n'
    "The camera pans back to Korri.\n\n"
    'KORRI\n"Stop it, you doofus."\n\n'
    "Korri puts her hand over the camera and the scene ends."
)


def _batch(order: int, text: str, length: float) -> BatchBlock:
    segments = []
    if text:
        segments.append(TimelinePromptSegment(text=text, start=0.0, length=length))
    return BatchBlock(
        id=f"bb-{order}",
        sceneId="s",
        order=order,
        label=f"Window {order + 1}",
        generatorId="minimax-h3",
        duration=DurationState(plannedDuration=15.0),
        promptSegments=segments,
    )


def test_slice_keeps_the_ending_off_the_first_window():
    first = slice_story_for_window(FULL_45, 0, 3)
    last = slice_story_for_window(FULL_45, 2, 3)
    assert "scene ends" not in first
    assert "Welcome to Schnick" in first
    assert "scene ends" in last
    assert "Welcome to Schnick" not in last


def test_empty_later_windows_receive_one_stored_slice():
    root = _batch(0, FULL_45, 45.0)
    later = [_batch(1, "", 15.0), _batch(2, "", 15.0)]
    master = SimpleNamespace(batchBlocks=[root, *later])
    assert assign_later_window_scripts(master) is True
    assert root.promptSegments[0].text == FULL_45
    assert "Do I really have to read this?" in later[0].promptSegments[0].text
    assert "Welcome to Schnick" not in later[0].promptSegments[0].text
    assert "scene ends" in later[1].promptSegments[0].text
    assert "CONTINUATION" not in later[0].promptSegments[0].text
    assert "WINDOW SCOPE" not in later[1].promptSegments[0].text
    assert assign_later_window_scripts(master) is False
    assert later[1].promptSegments[0].text == slice_story_for_window(FULL_45, 2, 3)


def test_copied_full_script_on_a_later_window_stays_as_written():
    root = _batch(0, FULL_45, 45.0)
    copied = _batch(1, FULL_45, 15.0)
    blank = _batch(2, "", 15.0)
    master = SimpleNamespace(batchBlocks=[root, copied, blank])
    assert assign_later_window_scripts(master) is True
    assert copied.promptSegments[0].text == FULL_45
    assert root.promptSegments[0].text == FULL_45
    assert "scene ends" in blank.promptSegments[0].text
    assert "CONTINUATION" not in copied.promptSegments[0].text
    assert "WINDOW SCOPE" not in root.promptSegments[0].text


def test_root_delivery_reads_the_stored_prompt():
    root = _batch(0, FULL_45, 45.0)
    master = SimpleNamespace(batchBlocks=[root, _batch(1, "", 15.0), _batch(2, "", 15.0)])
    assign_later_window_scripts(master)
    stored = root.promptSegments[0].text
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=root,
        snapshot=ExecutionSnapshot(batchBlockId="bb-0", selectedGenerator="minimax-h3"),
    )
    assert stored in req.prompt
    assert "scene ends" in req.prompt
    assert "Welcome to Schnick" in req.prompt
    assert "WINDOW SCOPE" not in req.prompt
    assert "CONTINUATION" not in req.prompt
    assert "Spoken dialogue language: English" in req.prompt
    assert "Do not speak Chinese" in req.prompt


def test_empty_later_window_fails_closed():
    import pytest

    with pytest.raises(ValueError, match="BATCH_PROMPT_REQUIRED"):
        build_timeline_generation_request(
            project_id="p",
            scene_id="s",
            batch=_batch(2, "", 15.0),
            snapshot=ExecutionSnapshot(batchBlockId="bb-2", selectedGenerator="minimax-h3"),
        )


def test_hollow_continuation_stub_fails_closed():
    """A continuation line with no story is not a prompt. Submit does not heal it."""
    import pytest

    stub = (
        "[CONTINUATION window 3 | scene time 30s-45s] "
        "Continue from the prior window. Do not restart the scene from 0s."
    )
    with pytest.raises(ValueError, match="BATCH_PROMPT_REQUIRED"):
        build_timeline_generation_request(
            project_id="p",
            scene_id="s",
            batch=_batch(2, stub, 15.0),
            snapshot=ExecutionSnapshot(batchBlockId="bb-2", selectedGenerator="minimax-h3"),
        )


def test_rematerialize_keeps_the_authored_prompt_on_its_window():
    """Splitting a scene into windows does not rewrite the Timed Prompt."""
    from app.director_timeline_w46.contracts import SceneTimelineMaster
    from app.director_timeline_w46.execution_window_materialize import (
        rematerialize_batch_blocks_from_plan,
    )

    master = SceneTimelineMaster(
        version=1,
        mode="video_finishing",
        batchBlocks=[_batch(0, FULL_45, 45.0)],
        executionSnapshots={},
        migratedFromDirectorJson=True,
    )
    result = rematerialize_batch_blocks_from_plan(
        master,
        windows=[
            {"start": 0.0, "end": 15.0},
            {"start": 15.0, "end": 30.0},
            {"start": 30.0, "end": 45.0},
        ],
        generator_id="minimax-h3",
        scene_id="s",
        duration_seconds=45.0,
        force=True,
    )
    assert result.get("ok") is True
    assert len(master.batchBlocks) == 3
    assert master.batchBlocks[0].promptSegments[0].text == FULL_45
    assert "Do I really have to read this?" in master.batchBlocks[1].promptSegments[0].text
    assert "scene ends" in master.batchBlocks[2].promptSegments[0].text
    assert "CONTINUATION" not in master.batchBlocks[1].promptSegments[0].text
    assert "WINDOW SCOPE" not in master.batchBlocks[0].promptSegments[0].text

    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=master.batchBlocks[0],
        snapshot=ExecutionSnapshot(
            batchBlockId=master.batchBlocks[0].id,
            selectedGenerator="minimax-h3",
        ),
    )
    assert FULL_45 in req.prompt or "Welcome to Schnick" in req.prompt
    assert "scene ends" in req.prompt
    assert req.duration == 15.0
    assert int((req.providerOptions or {}).get("legalFrameCount") or 0) == 362
    assert "Spoken dialogue language: English" in req.prompt
    assert "WINDOW SCOPE" not in req.prompt


def test_scene_duration_binds_one_window_per_generator_clip():
    """60s is 4 windows. 75s is 5. The Timed Prompt stays on the window that holds it."""
    from app.director_timeline_w46.contracts import SceneTimelineMaster
    from app.director_timeline_w46.execution_window_materialize import (
        rematerialize_batch_blocks_from_plan,
    )

    def windows_for(total: float, size: float = 15.0) -> list[dict[str, float]]:
        count = int(__import__("math").ceil(total / size))
        return [
            {"start": i * size, "end": min(total, (i + 1) * size)}
            for i in range(count)
        ]

    for total, expected in ((60.0, 4), (75.0, 5)):
        master = SceneTimelineMaster(
            version=1,
            mode="video_finishing",
            batchBlocks=[_batch(0, FULL_45, total)],
            executionSnapshots={},
            migratedFromDirectorJson=True,
        )
        result = rematerialize_batch_blocks_from_plan(
            master,
            windows=windows_for(total),
            generator_id="minimax-h3",
            scene_id="s",
            duration_seconds=total,
            force=True,
        )
        assert result.get("ok") is True
        assert len(master.batchBlocks) == expected
        assert master.batchBlocks[0].promptSegments[0].text == FULL_45
        assert "scene ends" in master.batchBlocks[-1].promptSegments[0].text
        assert "CONTINUATION" not in master.batchBlocks[1].promptSegments[0].text


def test_ltx_25_binds_20_second_windows():
    """LTX 2.5 follows the same scene-length rule. Each window is 20 seconds."""
    from app.codirector.production.execution_windows import plan_execution_windows

    sixty = plan_execution_windows(duration_seconds=60, generator_id="ltx-2.5-distilled")
    assert [(w.start, w.end) for w in sixty] == [(0.0, 20.0), (20.0, 40.0), (40.0, 60.0)]
    seventy_five = plan_execution_windows(duration_seconds=75, generator_id="ltx-2.5-distilled")
    assert len(seventy_five) == 4
    assert seventy_five[0].length == 20.0
    assert seventy_five[-1].end == 75.0

    root = _batch(0, FULL_45, 60.0)
    root.generatorId = "ltx-2.5-distilled"
    root.duration.plannedDuration = 20.0
    second = _batch(1, "", 20.0)
    second.generatorId = "ltx-2.5-distilled"
    second.duration.plannedDuration = 20.0
    third = _batch(2, "", 20.0)
    third.generatorId = "ltx-2.5-distilled"
    third.duration.plannedDuration = 20.0
    assert assign_later_window_scripts(SimpleNamespace(batchBlocks=[root, second, third])) is True
    assert root.promptSegments[0].text == FULL_45
    assert "scene ends" in third.promptSegments[0].text
    assert "CONTINUATION" not in second.promptSegments[0].text
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=root,
        snapshot=ExecutionSnapshot(batchBlockId=root.id, selectedGenerator="ltx-2.5-distilled"),
    )
    assert req.duration == 20.0
    assert "scene ends" in req.prompt
    assert "Welcome to Schnick" in req.prompt
    assert "WINDOW SCOPE" not in req.prompt


def test_retake_of_a_60s_scene_stays_in_window_one():
    from app.director_timeline_w46.generation.retake_context_package import (
        build_retake_context_package,
    )

    batch = _batch(0, FULL_45, 60.0)
    batch.duration.plannedDuration = 15.0
    delta = "Korri looks into the lens and smiles."
    pkg = build_retake_context_package(
        batch=batch,
        range_rep={"start": 1.0, "length": 3.0, "prompt": delta},
        supports_reference_to_video=True,
    )
    assert "scene ends" not in pkg["compiledPrompt"]
    assert delta in pkg["compiledPrompt"]
    assert batch.promptSegments[0].text == FULL_45


def test_retake_of_a_45s_window_does_not_send_the_ending(monkeypatch):
    """Re-Take stays inside the marked window. It must not replay the whole scene."""
    from app.director_timeline_w46.generation import request_builder as rb
    from app.director_timeline_w46.generation.retake_context_package import (
        build_retake_context_package,
    )

    batch = _batch(0, FULL_45, 45.0)
    delta = "Korri looks into the lens and smiles."
    pkg = build_retake_context_package(
        batch=batch,
        range_rep={"start": 1.0, "length": 3.0, "prompt": delta},
        supports_reference_to_video=True,
    )
    compiled = pkg["compiledPrompt"]
    assert "scene ends" not in compiled
    assert delta in compiled
    assert "[TARGET BEAT" in compiled
    assert "[USER DELTA]" in compiled

    monkeypatch.setattr(
        rb,
        "_batch_windows_for_prompt",
        lambda project_id, scene_id: [(0.0, 15.0), (15.0, 30.0), (30.0, 45.0)],
    )
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=batch,
        snapshot=ExecutionSnapshot(
            batchBlockId=batch.id,
            selectedGenerator="minimax-h3",
            continuityState={
                "rangeReplacement": {"start": 1.0, "length": 3.0, "prompt": delta},
            },
        ),
    )
    assert req.duration == 3.0
    assert "scene ends" not in req.prompt
    assert delta in req.prompt
    assert "Spoken dialogue language: English" in req.prompt
    assert batch.promptSegments[0].text == FULL_45


def test_chinese_omni_observation_never_enters_a_prompt():
    assert scrub_observation_line("她微笑着说话") == ""
    assert "咖啡" not in scrub_observation_line("Korri smiles 咖啡 and waves")
    assert h3_spoken_lock(None, "Hello there") .startswith("Spoken dialogue language: English")
    assert "English" in h3_spoken_lock("en", "Hello")
    assert h3_spoken_lock(None, "她说你好") == ""


def test_comfy_h3_graph_copies_prompt_and_has_no_language_widget():
    prompt = "Korri speaks English only.\n\nSpoken dialogue language: English."
    graph = build_h3_ref2v(
        prompt=prompt,
        ref_comfy_names=["studio/korri.png"],
        filename_prefix="studio/h3",
        seed=1,
        length=362,
    )
    assert h3_prompt_text(graph) == prompt
    _node_id, cond = next(
        (nid, node)
        for nid, node in graph.items()
        if isinstance(node, dict) and node.get("class_type") == "MiniMaxH3ReferenceToVideo"
    )
    assert "language" not in cond["inputs"]
    assert cond["inputs"]["length"] == 362


def test_empty_later_window_receives_the_scene_pictures():
    from app.director_timeline_w46.generation.window_script import (
        carry_root_references_to_empty_windows,
    )

    root = _batch(0, "Korri at the bar.", 15.0)
    root.promptSegments[0].referenceBindingIds = ["bind-korri"]
    root.references = [
        {"kind": "image", "role": "character", "assetId": "asset-korri", "label": "Korri"}
    ]
    second = _batch(1, "Cade answers.", 15.0)
    second.promptSegments[0].referenceBindingIds = []
    second.references = []
    assert carry_root_references_to_empty_windows(SimpleNamespace(batchBlocks=[root, second])) is True
    assert second.promptSegments[0].referenceBindingIds == ["bind-korri"]
    assert second.references[0]["assetId"] == "asset-korri"


def test_later_window_keeps_its_own_pictures():
    from app.director_timeline_w46.generation.window_script import (
        carry_root_references_to_empty_windows,
    )

    root = _batch(0, "Korri at the bar.", 15.0)
    root.promptSegments[0].referenceBindingIds = ["bind-korri"]
    root.references = [
        {"kind": "image", "role": "character", "assetId": "asset-korri", "label": "Korri"}
    ]
    second = _batch(1, "A different room.", 15.0)
    second.promptSegments[0].referenceBindingIds = ["bind-cade"]
    second.references = [
        {"kind": "image", "role": "character", "assetId": "asset-cade", "label": "Cade"}
    ]
    assert carry_root_references_to_empty_windows(SimpleNamespace(batchBlocks=[root, second])) is False
    assert second.promptSegments[0].referenceBindingIds == ["bind-cade"]
    assert second.references[0]["assetId"] == "asset-cade"


def test_machine_window_notes_are_removed_and_the_creator_line_stays():
    from app.director_timeline_w46.generation.request_builder import (
        strip_codirector_continuity_from_script,
    )

    raw = (
        "[CONTINUATION window 2 | scene time 15s-30s] Continue from the prior window. "
        "Do not restart the scene from 0s.\n\n"
        "KORRI\n"
        '"Has coffee ever given you that feeling?"\n\n'
        "WINDOW SCOPE\n"
        "This batch renders ONLY the segment from 15s to 30s of the scene. "
        "Do not restart the scene from 0s. Do not retell the opening.\n"
        "(This scene continues across 2 sequential batches; this is batch 2.)"
    )
    cleaned = strip_codirector_continuity_from_script(raw)
    assert "CONTINUATION" not in cleaned
    assert "WINDOW SCOPE" not in cleaned
    assert "sequential batches" not in cleaned
    assert "KORRI" in cleaned
    assert "Has coffee ever given you that feeling?" in cleaned


def test_request_builder_does_not_invent_a_window_interval():
    """Creator text is submitted as stored. Submit does not add a window scope."""
    sentence = (
        "A red ceramic mug sits on a wooden table in warm daylight. "
        "The camera holds still."
    )
    req = build_timeline_generation_request(
        project_id="p",
        scene_id="s",
        batch=_batch(1, sentence, 15.0),
        snapshot=ExecutionSnapshot(batchBlockId="bb-1", selectedGenerator="minimax-h3"),
    )
    assert "WINDOW SCOPE" not in req.prompt
    assert "wooden table" in req.prompt
    assert sentence in req.prompt
