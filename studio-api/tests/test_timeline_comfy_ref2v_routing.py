"""Timeline MiniMax H3 <-> Comfy Ref2V routing cert.

Owner contract (2026-09-09):
1. Timed Prompt -> compile_h3_prompt -> MiniMaxH3ReferenceToVideo.prompt
2. pictureIndex order -> LoadImage -> ref_image_(N-1)
3. Plain-copy CRS (no silent Front remap / no *_h3id by default) — covered in
   test_h3_identity_still + test_timeline_character_identity_bind; re-asserted lightly
4. Quality = no EasyCache; Lightning LoRA absent from Adept H3 graph
5. Owner dialect <subject N> is Name. (no wardrobe essay / orphan Picture binding)
"""

from __future__ import annotations

from pathlib import Path

from app.director_timeline_w46.generation.r2v import R2VSlot, compile_h3_prompt, map_canonical_r2v
from app.video_runtime.comfy_asset_stage import stage_h3_visual_asset
from app.workflows.h3_ref2v_builder import (
    H3_NODE_CONDITIONER,
    assert_h3_ref2v_graph,
    build_h3_ref2v,
    h3_prompt_text,
    h3_ref_image_links,
)


def test_routing_timed_prompt_to_h3_conditioner_prompt():
    authored = "Addex is seated. Korri sits beside him."
    prompt, _ = compile_h3_prompt(
        authored,
        [
            R2VSlot(role="character", assetId="korri-crs", label="Korri", pictureIndex=1),
            R2VSlot(role="character", assetId="addex-crs", label="Addex", pictureIndex=2),
        ],
        style_key="realistic_anime",
    )
    graph = build_h3_ref2v(
        prompt=prompt,
        ref_comfy_names=["studio/korri.jpeg", "studio/addex.jpeg"],
        filename_prefix="studio/test/h3_ref2v",
        seed=1,
        fast=False,
    )
    cond = graph[H3_NODE_CONDITIONER]
    assert cond["class_type"] == "MiniMaxH3ReferenceToVideo"
    assert h3_prompt_text(graph) == authored
    assert prompt == authored
    assert "CHARACTER IDENTITY" not in prompt
    assert "subject_definitions:" not in prompt
    assert not prompt.rstrip().endswith("<Picture 1> <Picture 2>")


def test_routing_picture_index_to_ref_image_sockets():
    names = ["studio/korri.jpeg", "studio/addex.jpeg"]
    graph = build_h3_ref2v(
        prompt="<subject 1> is Korri.\n\n<subject 2> is Addex.\n\nThey sit.",
        ref_comfy_names=names,
        filename_prefix="studio/test/h3_ref2v",
        seed=1,
        fast=False,
    )
    refs = h3_ref_image_links(graph)
    assert list(refs.keys()) == ["ref_image_0", "ref_image_1"]
    for index, name in enumerate(names):
        node_id, _ = refs[f"ref_image_{index}"]
        assert graph[node_id]["class_type"] == "LoadImage"
        assert graph[node_id]["inputs"]["image"] == name
    assert_h3_ref2v_graph(graph, expected_names=names, expect_fast=False)


def test_routing_quality_has_no_easycache_or_lora():
    graph = build_h3_ref2v(
        prompt="<subject 1> is Korri.\n\nScene.",
        ref_comfy_names=["studio/korri.jpeg"],
        filename_prefix="studio/test/h3_ref2v",
        seed=1,
        fast=False,
    )
    assert_h3_ref2v_graph(graph, expected_names=["studio/korri.jpeg"], expect_fast=False)
    types = {n.get("class_type") for n in graph.values() if isinstance(n, dict)}
    assert "EasyCache" not in types
    assert "LazyCache" not in types
    assert "LoraLoaderModelOnly" not in types
    assert "LoraLoader" not in types


def test_routing_map_canonical_sets_prompt_prefix_for_h3():
    payload = map_canonical_r2v(
        slots=[
            R2VSlot(role="character", assetId="korri-crs", label="Korri"),
            R2VSlot(role="character", assetId="addex-crs", label="Addex"),
        ],
        generator_id="minimax-h3",
        mapped_start=None,
        authored_prompt="They sit together on the couch.",
        style_key="realistic_anime",
    )
    assert payload.promptPrefix == "They sit together on the couch."
    chars = [s for s in payload.slots if s.role == "character"]
    assert [s.pictureIndex for s in chars] == [1, 2]


def test_routing_subject_n_matches_loadimage_socket_order():
    """subject N binds to ref_image_(N-1) when queue sorts by pictureIndex."""
    # Simulate queue_worker: sort by pictureIndex, stage names in that order
    slots = [
        R2VSlot(role="character", assetId="addex-crs", label="Addex", pictureIndex=2),
        R2VSlot(role="character", assetId="korri-crs", label="Korri", pictureIndex=1),
    ]
    visual = sorted(slots, key=lambda s: int(s.pictureIndex or 0))
    names = [f"studio/{s.assetId}.jpeg" for s in visual]
    prompt, _ = compile_h3_prompt("They sit.", slots)
    graph = build_h3_ref2v(
        prompt=prompt,
        ref_comfy_names=names,
        filename_prefix="studio/test/h3_ref2v",
        seed=1,
        fast=False,
    )
    assert names == ["studio/korri-crs.jpeg", "studio/addex-crs.jpeg"]
    assert prompt == "They sit."
    refs = h3_ref_image_links(graph)
    n0 = refs["ref_image_0"][0]
    n1 = refs["ref_image_1"][0]
    assert graph[n0]["inputs"]["image"] == "studio/korri-crs.jpeg"
    assert graph[n1]["inputs"]["image"] == "studio/addex-crs.jpeg"


def test_routing_character_stage_plain_copy_not_h3id(tmp_path: Path):
    src = tmp_path / "crs.jpeg"
    payload = b"CRS-BYTES-PLAIN-COPY-ROUTING"
    src.write_bytes(payload)
    input_dir = tmp_path / "comfy_input"
    input_dir.mkdir()

    class _Asset:
        id = "asset-crs-routing"
        path = str(src)
        kind = "image"

    staged = stage_h3_visual_asset(_Asset(), role="character", input_dir=input_dir)
    assert "_h3id" not in staged.comfy_name
    assert Path(staged.staged_path).read_bytes() == payload
    assert staged.ledger.get("plainCopy") is True
    assert staged.ledger.get("uploaded") == "library_file"
