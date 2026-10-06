"""qwen2512.atlas dual-condition graph — two LoadImage + Plus encoder."""

import json

from app.image_runtime.workflow_execute import build_leaf_graph
from app.workflows.qwen_image_2512_atlas import atlas_graph_roles


class _Settings:
    qwen_image_2512_unet = "u.safetensors"
    qwen_image_2512_clip = "c.safetensors"
    qwen_image_2512_vae = "v.safetensors"
    qwen_image_2512_size = 1024
    qwen_image_2512_steps = 8
    qwen_image_2512_cfg = 1.0
    qwen_image_2512_sampler = "euler"
    qwen_image_2512_scheduler = "simple"
    qwen_image_2512_shift = 1.73
    imagegen_default_steps = 20
    imagegen_default_cfg = 1.0


def test_build_leaf_graph_atlas_wires_source_and_guide() -> None:
    graph = build_leaf_graph(
        {"workflowKey": "qwen2512.atlas"},
        settings=_Settings(),
        prompt="roofless atlas",
        source_image="source.png",
        guide_image="guide.png",
        atlas_slot_order="guide_source",
    )
    roles = atlas_graph_roles(graph)
    assert roles["loadImageCount"] == 2
    assert roles["usesTextEncodeQwenImageEditPlus"] is True
    assert roles["hasImage1"] and roles["hasImage2"]
    assert roles["negativeEncodeMode"] == "text_only"
    assert graph["5"]["inputs"]["image"] == "guide.png"
    assert graph["6"]["inputs"]["image"] == "source.png"
    assert graph["8"]["class_type"] == "CLIPTextEncode"
    assert graph["9"]["inputs"]["width"] == 1024
    assert graph["10"]["inputs"]["steps"] == 28


def test_build_leaf_graph_atlas_source_guide_order() -> None:
    graph = build_leaf_graph(
        {"workflowKey": "qwen2512.atlas"},
        settings=_Settings(),
        prompt="roofless atlas",
        source_image="source.png",
        guide_image="guide.png",
        atlas_slot_order="source_guide",
    )
    assert graph["5"]["inputs"]["image"] == "source.png"
    assert graph["6"]["inputs"]["image"] == "guide.png"


def test_build_leaf_graph_atlas_direct_is_one_image_edit() -> None:
    from app.workflows.qwen_image_2512_atlas import atlas_direct_graph_roles

    graph = build_leaf_graph(
        {"workflowKey": "qwen2512.atlas_direct"},
        settings=_Settings(),
        prompt="roofless atlas",
        source_image="source.png",
        guide_image="guide.png",
    )
    roles = atlas_direct_graph_roles(graph)
    assert roles["loadImageCount"] == 1
    assert roles["usesTextEncodeQwenImageEdit"] is True
    assert roles["usesTextEncodeQwenImageEditPlus"] is False
    assert roles["hasVAEEncode"] is False
    assert roles["hasControlNet"] is False
    assert graph["5"]["inputs"]["image"] == "source.png"
    assert graph["6"]["class_type"] == "TextEncodeQwenImageEdit"
    assert graph["7"]["class_type"] == "TextEncodeQwenImageEdit"
    assert graph["6"]["inputs"]["image"] == ["5", 0]
    assert graph["8"]["inputs"]["width"] == 1024
    assert graph["9"]["inputs"]["steps"] == 28
    assert "guide.png" not in json.dumps(graph)


def test_atlas_can_still_build_dual_image_negative() -> None:
    from app.workflows.qwen_image_2512_atlas import build_qwen_2512_atlas_workflow

    graph = build_qwen_2512_atlas_workflow(
        unet_name="u.safetensors",
        clip_name="c.safetensors",
        vae_name="v.safetensors",
        positive="roofless atlas",
        source_image="source.png",
        guide_image="guide.png",
        negative_encode="dual_image",
    )
    assert graph["8"]["class_type"] == "TextEncodeQwenImageEditPlus"
    assert atlas_graph_roles(graph)["negativeEncodeMode"] == "dual_image"
