"""Live SenseNova GPU smoke. Skipped unless ADEPT_SENSENOVA_LIVE=1 and Ready."""

from __future__ import annotations

import os

import pytest

from app.workflows.sensenova_u15 import (
    SENSENOVA_SMOKE_STEPS,
    build_sensenova_txt2img_workflow,
    discover_sensenova_u15,
    inspect_weights,
)


pytestmark = pytest.mark.skipif(
    os.environ.get("ADEPT_SENSENOVA_LIVE") != "1",
    reason="Set ADEPT_SENSENOVA_LIVE=1 for official-node GPU smoke",
)


def test_weights_complete_before_live_smoke() -> None:
    probe = inspect_weights()
    assert probe["installed"] is True, probe.get("missing")
    assert int(probe["completeShards"]) == 13


def test_discover_reports_weights_but_not_gpu_ready() -> None:
    disc = discover_sensenova_u15()
    assert disc.get("installed") is True, disc.get("missing")
    assert disc.get("runtimeReady") is False


def test_smoke_graph_uses_two_official_steps() -> None:
    graph = build_sensenova_txt2img_workflow(
        prompt="a single brass desk lamp on a gray table, no text",
        width=2048,
        height=2048,
        seed=15,
        steps=SENSENOVA_SMOKE_STEPS,
    )
    assert graph["2"]["inputs"]["num_steps"] == SENSENOVA_SMOKE_STEPS
    assert graph["2"]["class_type"] == "SenseNovaU1LocalTextToImage"
    assert "KSampler" not in {node["class_type"] for node in graph.values()}
