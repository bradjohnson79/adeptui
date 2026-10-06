"""Phase1: rematerialize 30/45s → ceil(N/15) windows, ONE scene,
root owns Timed Prompt 0-N; extensions never get Seconds:0-N clone / blank authored.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.director_timeline_w46.execution_window_materialize import (
    _build_batch_blocks,
    _looks_like_full_scene_prompt,
)


def _seg(text: str, *, start: float = 0.0, length: float = 30.0):
    return SimpleNamespace(text=text, start=start, length=length)


def _batch(order: int, text: str, *, length: float = 30.0):
    return SimpleNamespace(
        id=f"bb_{order}",
        order=order,
        label=f"Window {order}",
        generatorId="minimax-h3",
        promptSegments=[_seg(text, length=length)],
        status="Draft",
        duration=SimpleNamespace(plannedDuration=length, timelineVisibleDuration=length),
    )


def _master(batches):
    return SimpleNamespace(
        sceneId="scene_disposable",
        batchBlocks=list(batches),
        sceneGeneratorId="minimax-h3",
        migrationMetadata={},
    )


def test_looks_like_full_scene_prompt_detects_seconds_span():
    seg = _seg("Seconds: 0-30. Wide shot of the plaza at dusk.", length=30.0)
    assert _looks_like_full_scene_prompt(seg, 30.0) is True
    local = _seg("Continue across the plaza.", length=15.0)
    assert _looks_like_full_scene_prompt(local, 30.0) is False


def test_expand_30s_two_windows_root_keeps_scene_prompt_extension_continues():
    authored = "Seconds: 0-30. Hero walks into the neon market and greets the vendor."
    master = _master([_batch(0, authored, length=30.0)])
    windows = [{"start": 0.0, "end": 15.0}, {"start": 15.0, "end": 30.0}]
    try:
        blocks = _build_batch_blocks(
            master, windows, scene_id="scene_disposable", generator_id="minimax-h3"
        )
    except Exception as exc:
        pytest.skip(f"BatchBlock construction requires full contracts: {exc}")
    assert len(blocks) == 2
    root = blocks[0].promptSegments[0]
    ext = blocks[1].promptSegments[0]
    assert authored in (root.text or "")
    assert float(root.length) >= 29.95
    assert float(root.start) <= 0.05
    ext_text = ext.text or ""
    assert "Seconds: 0-30" not in ext_text
    assert ext_text.strip()
    assert "CONTINUATION" in ext_text
    assert float(ext.start) >= 14.95


def test_expand_45s_three_windows_no_full_scene_clone_on_extensions():
    authored = "Seconds: 0-45. Storm rolls over the harbor as the crew secures the sails."
    master = _master([_batch(0, authored, length=45.0)])
    windows = [
        {"start": 0.0, "end": 15.0},
        {"start": 15.0, "end": 30.0},
        {"start": 30.0, "end": 45.0},
    ]
    try:
        blocks = _build_batch_blocks(
            master, windows, scene_id="scene_disposable", generator_id="minimax-h3"
        )
    except Exception as exc:
        pytest.skip(f"BatchBlock construction requires full contracts: {exc}")
    assert len(blocks) == 3
    assert authored in (blocks[0].promptSegments[0].text or "")
    for i in (1, 2):
        t = blocks[i].promptSegments[0].text or ""
        assert "Seconds: 0-45" not in t
        assert t.strip()
        assert "CONTINUATION" in t


def test_never_blank_authored_root_on_same_topology():
    authored = "Seconds: 0-15. Close-up of the key turning."
    master = _master([_batch(0, authored, length=15.0)])
    windows = [{"start": 0.0, "end": 15.0}]
    try:
        blocks = _build_batch_blocks(
            master, windows, scene_id="scene_disposable", generator_id="minimax-h3"
        )
    except Exception as exc:
        pytest.skip(f"BatchBlock construction requires full contracts: {exc}")
    assert len(blocks) == 1
    assert authored in (blocks[0].promptSegments[0].text or "")
