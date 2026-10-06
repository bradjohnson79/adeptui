"""SD 1.5 CRS control route — availability, not AUTO preference."""

from __future__ import annotations

import json
from pathlib import Path

from app.character_identity.four_view_sheet import is_single_image_four_view
from app.config import settings
from app.image_core.capability import generate_workflow_key, normalize_family, sd15_crs_capability
from app.image_product.recommend import recommend_image_family
from app.image_runtime.certified_registry import get_workflow, reload_registry
from app.image_runtime.contract import _normalize_family, resolve_image_workflow
from app.imagegen_workflows import (
    build_local_generator_models,
    build_sd15_control_workflow,
    build_txt2img_workflow,
)
from app.setup.catalog import get_component
from app.setup.paths import suggested_install_path


def test_sd15_aliases_normalize():
    assert normalize_family("sd1.5") == "sd15"
    assert normalize_family("stable-diffusion-1.5") == "sd15"
    assert _normalize_family("sd15", None) == "sd15"
    assert _normalize_family(None, "stable_diffusion_15") == "sd15"


def test_sd15_registry_entries_are_draft_not_certified():
    reload_registry()
    txt = get_workflow("sd15.txt2img")
    ctrl = get_workflow("crs.sd15.control")
    assert txt is not None
    assert ctrl is not None
    assert txt.status == "Draft"
    assert ctrl.status == "Draft"
    assert txt.model_family == "sd15"
    assert ctrl.model_family == "sd15"
    assert ctrl.capabilities.get("supportsControlNet") is True
    pose = get_workflow("control.pose")
    assert pose is not None
    assert pose.status == "Deferred"


def test_resolve_sd15_txt2img_allow_draft():
    reload_registry()
    c = resolve_image_workflow("txt2img", engine="sd15", allow_draft=True)
    assert c.workflow_key == "sd15.txt2img"
    assert c.model_family == "sd15"


def test_resolve_crs_sd15_control_force_key():
    reload_registry()
    c = resolve_image_workflow(
        "txt2img",
        engine="sd15",
        allow_draft=True,
        force_workflow_key="crs.sd15.control",
    )
    assert c.workflow_key == "crs.sd15.control"
    assert c.capabilities.get("supportsControlNet") is True


def test_checkpoint_for_model_sd15():
    from app.queue_worker import JobQueue

    worker = JobQueue.__new__(JobQueue)
    assert worker._checkpoint_for_model("sd15") == settings.imagegen_sd15_checkpoint
    assert worker._checkpoint_for_model("SD1.5") == settings.imagegen_sd15_checkpoint
    assert worker._checkpoint_for_model("illustrious") == settings.imagegen_illustrious_checkpoint
    assert worker._checkpoint_for_model("qwen2512") == settings.qwen_image_2512_unet


def test_sd15_txt2img_builder_is_single_image():
    graph = build_txt2img_workflow(
        checkpoint=settings.imagegen_sd15_checkpoint,
        positive="one isolated mannequin",
        negative="collage",
        width=512,
        height=768,
        seed=1,
        steps=20,
        cfg=7.0,
        filename_prefix="studio/sd15_test",
    )
    saves = [n for n in graph.values() if n.get("class_type") == "SaveImage"]
    latents = [n for n in graph.values() if n.get("class_type") == "EmptyLatentImage"]
    assert len(saves) == 1
    assert latents[0]["inputs"]["batch_size"] == 1
    assert latents[0]["inputs"]["width"] == 512
    assert latents[0]["inputs"]["height"] == 768


def test_sd15_control_builder_optional_openpose():
    plain = build_sd15_control_workflow(
        checkpoint=settings.imagegen_sd15_checkpoint,
        positive="one isolated mannequin facing camera",
        negative="collage, four panel",
        width=512,
        height=768,
        seed=2,
    )
    assert "OpenposePreprocessor" not in {n.get("class_type") for n in plain.values()}
    assert sum(1 for n in plain.values() if n.get("class_type") == "SaveImage") == 1

    controlled = build_sd15_control_workflow(
        checkpoint=settings.imagegen_sd15_checkpoint,
        positive="one isolated mannequin facing camera",
        negative="collage, four panel",
        width=512,
        height=768,
        seed=2,
        control_image="adept_sd15_pose_source.png",
        controlnet_name=settings.imagegen_sd15_openpose,
    )
    types = {n.get("class_type") for n in controlled.values()}
    assert "OpenposePreprocessor" in types
    assert "ControlNetLoader" in types
    assert "ControlNetApplyAdvanced" in types
    assert sum(1 for n in controlled.values() if n.get("class_type") == "SaveImage") == 1
    assert controlled["4"]["inputs"]["batch_size"] == 1


def test_crs_sd15_control_json_loads_and_is_single_output():
    path = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "image-workflows"
        / "graphs"
        / "crs.sd15.control.json"
    )
    graph = json.loads(path.read_text(encoding="utf-8"))
    assert graph["4"]["inputs"]["batch_size"] == 1
    saves = [n for n in graph.values() if n.get("class_type") == "SaveImage"]
    assert len(saves) == 1
    assert graph["4"]["inputs"]["width"] == 512
    assert graph["4"]["inputs"]["height"] == 768
    required = {
        "CheckpointLoaderSimple",
        "ControlNetLoader",
        "ControlNetApplyAdvanced",
        "OpenposePreprocessor",
        "KSampler",
        "VAEDecode",
        "SaveImage",
    }
    types = {n.get("class_type") for n in graph.values()}
    assert required <= types


def test_crs_single_view_is_not_four_panel():
    params = {
        "taskType": "CRS_SINGLE_VIEW",
        "view": "FRONT",
        "character_count": 1,
        "extras": False,
        "layout": "single_subject",
        "purpose": "character_sheet",
    }
    assert is_single_image_four_view(params) is False


def test_auto_recommend_never_picks_sd15():
    rec = recommend_image_family(prompt="portrait of a person", purpose="character_sheet")
    assert rec["recommendedFamily"] != "sd15"
    assert rec["executionFamily"] != "sd15"
    explicit = recommend_image_family(
        prompt="pose control",
        purpose="crs_single_view",
        model_family_preference="sd15",
    )
    assert explicit["recommendedFamily"] == "sd15"
    assert explicit["executionFamily"] == "sd15"


def test_sd15_not_in_certified_beauty_dropdown():
    reload_registry()
    roster = build_local_generator_models()
    ids = [row.get("id") for row in roster]
    assert "sd15" not in ids
    assert "auto" in ids


def test_sd15_capability_snapshot_not_preferred():
    snap = sd15_crs_capability(available=True)
    assert snap["provider"] == "sd15"
    assert snap["available"] is True
    assert snap["preferred"] is False
    assert snap["autoPreferred"] is False
    assert "pose_control" in snap["roles"]
    assert "crs_single_view" in snap["roles"]
    assert generate_workflow_key("sd15") == "sd15.txt2img"


def test_compile_sd15_crs_single_view_is_not_four_panel():
    from app.image_product.compile import compile_image_request

    compiled = compile_image_request(
        "sd15-crs-disposable",
        {
            "prompt": "a single generic adult mannequin standing facing camera",
            "negative": "collage, four panel, character sheet",
            "model": "sd15",
            "modelFamilyPreference": "sd15",
            "lockModelFamily": True,
            "source": "local",
            "forceWorkflowKey": "crs.sd15.control",
            "allowDraft": True,
            "width": 512,
            "height": 768,
            "taskType": "CRS_SINGLE_VIEW",
            "view": "FRONT",
            "character_count": 1,
            "extras": False,
            "layout": "single_subject",
            "purpose": "crs_single_view",
        },
    )
    runtime = compiled["imageRuntime"]
    intent = compiled["imageIntent"]
    meta = intent.get("metadata") or {}
    assert runtime.get("workflowKey") == "crs.sd15.control"
    assert intent.get("enginePreference") == "sd15"
    assert compiled.get("allowDraft") is True
    assert meta.get("taskType") == "CRS_SINGLE_VIEW"
    assert meta.get("view") == "FRONT"
    assert meta.get("layout") == "single_subject"
    assert is_single_image_four_view({**intent, **meta}) is False


def test_sd15_setup_paths_use_owner_root():
    assert get_component("sd15_local").id == "sd15_local"
    assert get_component("sd15_controlnet").id == "sd15_controlnet"
    assert suggested_install_path("sd15_local").replace("/", "\\").endswith("StableDiffusion15")
    assert "ControlNet" in suggested_install_path("sd15_controlnet")
    assert "SD15" in suggested_install_path("sd15_controlnet")
