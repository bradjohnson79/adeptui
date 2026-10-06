"""Phase N / FM5: build_h3_ref2v emits the FM4 Comfy baseline field set."""
from __future__ import annotations

import json
from pathlib import Path

from app.workflows.h3_ref2v_builder import (
    H3_AUDIO_VAE,
    H3_CLIP,
    H3_FAST_CACHE_NODE,
    H3_NODE_CLIP,
    H3_NODE_CONDITIONER,
    H3_NODE_UNET,
    H3_NODE_VIDEO_VAE,
    H3_NODE_AUDIO_VAE,
    H3_REF2VA_UNET,
    H3_REF2V_HEIGHT,
    H3_REF2V_SAMPLER,
    H3_REF2V_SCHEDULER,
    H3_REF2V_STEPS,
    H3_REF2V_WIDTH,
    H3_VIDEO_VAE,
    assert_h3_ref2v_graph,
    build_h3_ref2v,
    h3_prompt_text,
    h3_ref_image_links,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "phase_n_acceptance_fixture.json").read_text(encoding="utf-8")
)


def test_builder_defaults_are_fm4_baseline_1152x640():
    assert H3_REF2V_WIDTH == 1152
    assert H3_REF2V_HEIGHT == 640


def test_quality_graph_matches_fm4_field_set():
    prompt = FIXTURE["timedPrompt"]
    names = ["studio/a42e77e0-dfe3-4ac9-85af-ab98dfc510e5.jpeg"]
    graph = build_h3_ref2v(
        prompt=prompt,
        ref_comfy_names=names,
        filename_prefix="studio/phase_n/h3_ref2v",
        seed=1,
        length=int(FIXTURE["duration"]["legalFrameCount"]),
        width=864,
        height=480,
        fast=False,
    )
    assert_h3_ref2v_graph(
        graph,
        expected_names=names,
        expect_fast=False,
        expected_prompt=prompt,
        expected_width=864,
        expected_height=480,
        expected_sampler=H3_REF2V_SAMPLER,
        expected_scheduler=H3_REF2V_SCHEDULER,
        expected_steps=H3_REF2V_STEPS,
        expected_denoise=1.0,
        expected_ref_image_size="match",
    )
    cond = graph[H3_NODE_CONDITIONER]["inputs"]
    assert h3_prompt_text(graph) == prompt
    assert cond["width"] == 864
    assert cond["height"] == 480
    assert cond["ref_image_size"] == "match"
    assert list(h3_ref_image_links(graph).keys()) == ["ref_image_0"]
    assert "ref_images.ref_image_0" in cond
    assert graph[H3_NODE_UNET]["inputs"]["unet_name"] == H3_REF2VA_UNET
    assert graph[H3_NODE_CLIP]["inputs"]["clip_name"] == H3_CLIP
    assert graph[H3_NODE_VIDEO_VAE]["inputs"]["vae_name"] == H3_VIDEO_VAE
    assert graph[H3_NODE_AUDIO_VAE]["inputs"]["vae_name"] == H3_AUDIO_VAE
    types = {node.get("class_type") for node in graph.values() if isinstance(node, dict)}
    assert H3_FAST_CACHE_NODE not in types
    assert "PathchSageAttentionKJ" in types
    assert "PrimitiveStringMultiline" in types
    assert "ResolutionSelector" not in types
    assert "LoraLoader" not in types


def test_fast_graph_injects_easycache_only():
    names = ["studio/korri.jpeg"]
    graph = build_h3_ref2v(
        prompt=FIXTURE["timedPrompt"],
        ref_comfy_names=names,
        filename_prefix="studio/phase_n/h3_fast",
        seed=2,
        length=294,
        width=864,
        height=480,
        fast=True,
    )
    assert_h3_ref2v_graph(
        graph,
        expected_names=names,
        expect_fast=True,
        expected_prompt=FIXTURE["timedPrompt"],
        expected_width=864,
        expected_height=480,
    )
    assert any(
        isinstance(node, dict) and node.get("class_type") == H3_FAST_CACHE_NODE
        for node in graph.values()
    )


def test_loadimage_order_is_creator_order_no_pad():
    names = ["studio/first.jpeg", "studio/second.jpeg"]
    graph = build_h3_ref2v(
        prompt="<subject 1> is Korri.\n<subject 2> is Addex.",
        ref_comfy_names=names,
        filename_prefix="studio/phase_n/order",
        seed=3,
        fast=False,
    )
    assert_h3_ref2v_graph(graph, expected_names=names, expect_fast=False)
    refs = h3_ref_image_links(graph)
    assert list(refs.keys()) == ["ref_image_0", "ref_image_1"]
    assert graph[refs["ref_image_0"][0]]["inputs"]["image"] == "studio/first.jpeg"
    assert graph[refs["ref_image_1"][0]]["inputs"]["image"] == "studio/second.jpeg"


def test_prompt_written_verbatim_including_style_sentence():
    prompt = FIXTURE["timedPrompt"]
    graph = build_h3_ref2v(
        prompt=prompt,
        ref_comfy_names=["studio/korri.jpeg"],
        filename_prefix="studio/phase_n/prompt",
        seed=4,
        fast=False,
    )
    assert h3_prompt_text(graph) == prompt
    assert FIXTURE["styleSentence"] in h3_prompt_text(graph)
    assert "<Picture" not in h3_prompt_text(graph)
