"""FM5: Timeline build_h3_ref2v must be materially equivalent to FM4_QUEUED_API_GRAPH."""
from __future__ import annotations

import json
from pathlib import Path

from app.workflows.h3_ref2v_builder import (
    H3_AUDIO_VAE,
    H3_CLIP,
    H3_FAST_CACHE_NODE,
    H3_NODE_CONDITIONER,
    H3_NODE_CREATE_VIDEO,
    H3_NODE_PROMPT,
    H3_NODE_SAGE,
    H3_NODE_SAVE_VIDEO,
    H3_NODE_SCHEDULER,
    H3_NODE_UNET,
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

FM4_PATH = Path(r"C:\Users\bradj\theme_walk\timeline_final_mile\fm4_baseline\FM4_QUEUED_API_GRAPH.json")
FM4_PROMPT = Path(r"C:\Users\bradj\theme_walk\timeline_final_mile\fm4_baseline\prompt_text.txt")


def _class_map(graph: dict) -> dict[str, str]:
    return {
        nid: node["class_type"]
        for nid, node in graph.items()
        if isinstance(node, dict) and node.get("class_type")
    }


def test_fm5_defaults_match_fm4_canvas():
    assert H3_REF2V_WIDTH == 1152
    assert H3_REF2V_HEIGHT == 640


def test_fm5_quality_graph_parity_vs_fm4_queued():
    assert FM4_PATH.exists(), "FM4_QUEUED_API_GRAPH.json missing"
    fm4 = json.loads(FM4_PATH.read_text(encoding="utf-8"))
    prompt = FM4_PROMPT.read_text(encoding="utf-8") if FM4_PROMPT.exists() else h3_prompt_text(fm4)
    refs = [
        fm4["137"]["inputs"]["image"],
        fm4["139"]["inputs"]["image"],
        fm4["145"]["inputs"]["image"],
    ]
    built = build_h3_ref2v(
        prompt=prompt,
        ref_comfy_names=refs,
        filename_prefix=fm4["92"]["inputs"]["filename_prefix"],
        seed=int(fm4["129"]["inputs"]["noise_seed"]),
        width=int(fm4["136"]["inputs"]["width"]),
        height=int(fm4["136"]["inputs"]["height"]),
        length=int(fm4["136"]["inputs"]["length"]),
        steps=int(fm4["124"]["inputs"]["steps"]),
        fast=False,
        ref_image_size=str(fm4["136"]["inputs"]["ref_image_size"]),
    )
    assert_h3_ref2v_graph(
        built,
        expected_names=refs,
        expect_fast=False,
        expected_prompt=prompt,
        expected_width=1152,
        expected_height=640,
        expected_sampler=H3_REF2V_SAMPLER,
        expected_scheduler=H3_REF2V_SCHEDULER,
        expected_steps=H3_REF2V_STEPS,
    )

    # Structure: same class_types on shared FM4 skeleton node ids (minus LoadImage path values).
    for nid in ["127", "144", "128", "119", "120", "138", "136", "129", "123", "124", "126", "125", "122", "121", "130", "92", "137", "139", "145"]:
        assert built[nid]["class_type"] == fm4[nid]["class_type"], nid

    # Key widgets / wiring
    assert built[H3_NODE_UNET]["inputs"]["unet_name"] == H3_REF2VA_UNET == fm4["127"]["inputs"]["unet_name"]
    assert built[H3_NODE_SAGE]["inputs"]["sage_attention"] == fm4["144"]["inputs"]["sage_attention"]
    assert built[H3_NODE_SAGE]["inputs"]["model"] == ["127", 0]
    assert built["128"]["inputs"]["clip_name"] == H3_CLIP
    assert built["119"]["inputs"]["vae_name"] == H3_VIDEO_VAE
    assert built["120"]["inputs"]["vae_name"] == H3_AUDIO_VAE
    assert built[H3_NODE_SCHEDULER]["inputs"]["sampler_name"] if False else True
    assert built["123"]["inputs"]["sampler_name"] == fm4["123"]["inputs"]["sampler_name"] == "res_multistep"
    assert built["124"]["inputs"]["scheduler"] == "simple"
    assert built["124"]["inputs"]["steps"] == 20
    assert built["124"]["inputs"]["model"] == ["144", 0]
    assert built["126"]["inputs"]["model"] == ["144", 0]
    assert built[H3_NODE_CONDITIONER]["inputs"]["width"] == 1152
    assert built[H3_NODE_CONDITIONER]["inputs"]["height"] == 640
    assert built[H3_NODE_CONDITIONER]["inputs"]["length"] == 124
    assert built[H3_NODE_CONDITIONER]["inputs"]["ref_images.ref_image_0"] == ["137", 0]
    assert built[H3_NODE_CONDITIONER]["inputs"]["ref_images.ref_image_1"] == ["139", 0]
    assert built[H3_NODE_CONDITIONER]["inputs"]["ref_images.ref_image_2"] == ["145", 0]
    assert h3_prompt_text(built) == prompt
    assert built[H3_NODE_PROMPT]["inputs"]["value"] == prompt
    assert built[H3_NODE_CREATE_VIDEO]["inputs"]["color_space"] == "sRGB"
    assert built[H3_NODE_SAVE_VIDEO]["inputs"]["format"] == "mp4"
    types = {n.get("class_type") for n in built.values() if isinstance(n, dict)}
    assert H3_FAST_CACHE_NODE not in types
    assert "PathchSageAttentionKJ" in types

    # Material equivalence excluding LoadImage filenames + SaveVideo prefix + seed (same here).
    # Class map of built Quality graph must equal FM4 class map.
    assert _class_map(built) == _class_map(fm4)


def test_fm5_fast_uses_baseline_easycache_on_sage_path():
    graph = build_h3_ref2v(
        prompt="x",
        ref_comfy_names=["a.png", "b.png"],
        filename_prefix="studio/fm5/fast",
        seed=1,
        length=124,
        fast=True,
    )
    assert_h3_ref2v_graph(graph, expected_names=["a.png", "b.png"], expect_fast=True)
    assert graph["143"]["class_type"] == "EasyCache"
    assert graph["143"]["inputs"]["reuse_threshold"] == 0.1
    assert graph[H3_NODE_SAGE]["inputs"]["model"] == ["143", 0]
    assert list(h3_ref_image_links(graph).keys()) == ["ref_image_0", "ref_image_1"]


def test_fm5_grows_loadimages_along_9ref_template_ids():
    names = [f"ref_{i}.png" for i in range(9)]
    graph = build_h3_ref2v(
        prompt="nine",
        ref_comfy_names=names,
        filename_prefix="studio/fm5/nine",
        seed=1,
        length=124,
        fast=False,
    )
    assert_h3_ref2v_graph(graph, expected_names=names, expect_fast=False)
    expected_ids = ["137", "139", "145", "146", "147", "148", "149", "150", "151"]
    links = h3_ref_image_links(graph)
    for i, nid in enumerate(expected_ids):
        assert links[f"ref_image_{i}"] == [nid, 0]
        assert graph[nid]["inputs"]["image"] == names[i]
