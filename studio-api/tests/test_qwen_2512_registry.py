from __future__ import annotations

from app.config import settings
from app.image_runtime.certified_registry import get_workflow, reload_registry
from app.image_runtime.contract import resolve_image_workflow
from app.image_runtime.workflow_execute import build_leaf_graph, legacy_comfy_workflow_key


def test_qwen_2512_registry_entries_present():
    reload_registry()

    txt2img = get_workflow("qwen2512.txt2img")
    concept = get_workflow("qwen2512.character_concept")
    profile = get_workflow("qwen2512.character_profile")
    legacy = get_workflow("qwen.txt2img")

    assert txt2img is not None
    assert concept is not None
    assert profile is not None
    assert legacy is not None

    assert txt2img.status == "Draft"
    assert txt2img.builder_path == (
        "app.workflows.qwen_image_2512:build_qwen_2512_txt2img_workflow"
    )
    assert txt2img.model_family == "qwen-image-2512"
    assert "UNETLoader" in txt2img.required_nodes
    assert "CheckpointLoaderSimple" not in txt2img.required_nodes

    assert concept.builder_path == (
        "app.workflows.qwen_image_2512:build_qwen_2512_character_concept_workflow"
    )
    assert profile.builder_path == concept.builder_path
    assert legacy.status == "Deferred"
    assert "CheckpointLoaderSimple" in legacy.required_nodes


def test_qwen_2512_resolve_txt2img_family():
    contract = resolve_image_workflow("txt2img", engine="qwen-image-2512", allow_draft=True)

    assert contract.workflow_key == "qwen2512.txt2img"
    assert contract.model_family == "qwen-image-2512"
    assert contract.status == "Draft"


def test_qwen_2512_build_leaf_graph_uses_split_loaders():
    contract = resolve_image_workflow("txt2img", engine="qwen2512", allow_draft=True)

    graph = build_leaf_graph(
        contract,
        settings=settings,
        prompt="stylized portrait of a pilot in rainy neon streetlight",
        width=1328,
        height=1328,
        seed=7,
        steps=50,
        cfg=4.0,
    )

    assert graph["1"]["class_type"] == "UNETLoader"
    assert graph["2"]["class_type"] == "CLIPLoader"
    assert graph["2"]["inputs"]["type"] == "qwen_image"
    assert graph["3"]["class_type"] == "VAELoader"
    assert graph["4"]["class_type"] == "ModelSamplingAuraFlow"
    assert graph["5"]["class_type"] == "CLIPTextEncode"
    assert graph["8"]["class_type"] == "KSampler"
    assert legacy_comfy_workflow_key("qwen2512.txt2img") == "image.txt2img"


def test_qwen_2512_force_character_profile_key():
    contract = resolve_image_workflow(
        "image.generate",
        engine="qwen-image-2512",
        force_workflow_key="qwen2512.character_profile",
        allow_draft=True,
    )

    assert contract.workflow_key == "qwen2512.character_profile"
    assert contract.category == "Identity"
