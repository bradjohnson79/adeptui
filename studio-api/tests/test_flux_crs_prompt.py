"""FLUX CRS single-view prompt + generic FLUX builder regression. No live generation."""

from __future__ import annotations

from app.character_identity.visual_sheet import (
    _build_candidate_routing_plan,
    _coerce_single_crs_sources,
    _compile_visual_prompt,
)
from app.image_prompting.flux.crs_single_view import FLUX_CRS_PROMPT_FAMILY


def test_legacy_model_key_keeps_explicit_qwen() -> None:
    sources = _coerce_single_crs_sources({"local": {"model": "qwen2512"}, "api": None})
    assert sources["local"][0]["family"] == "qwen2512"


def test_flux_crs_prompt_is_not_qwen_blocks() -> None:
    profile = {"name": "PatchSubject", "visual_description": "teal coat, short hair"}
    flux = _compile_visual_prompt(
        profile,
        prompt_goal="a production character reference",
        composition={},
        references=[],
        role="full_body_side_left",
        sheet_request={},
        model_family="flux",
    )
    qwen = _compile_visual_prompt(
        profile,
        prompt_goal="a production character reference",
        composition={},
        references=[],
        role="full_body_side_left",
        sheet_request={},
        model_family="qwen2512",
    )
    assert flux.prompt_family == FLUX_CRS_PROMPT_FAMILY
    assert "1. Request Intent" not in flux.prompt
    assert "exactly one person" in flux.prompt.lower()
    assert "side" in flux.prompt.lower()
    assert "four-panel" not in flux.prompt.lower()
    assert "four-view" not in flux.prompt.lower()
    assert "no turnaround sheet" in flux.prompt.lower()
    assert qwen.prompt_family == "qwen_2512_character_image_prompt"
    assert "1. Request Intent" in qwen.prompt or "Request Intent" in qwen.prompt


def test_auto_crs_extras_stay_off() -> None:
    plan = _build_candidate_routing_plan(
        candidate_count=1,
        reference_asset_id=None,
        visual_style="anime",
        generator_sources=_coerce_single_crs_sources(None),
    )
    assert len(plan) == 1
    assert plan[0]["modelFamilyPreference"] == "flux"
    assert plan[0].get("stage2Enabled") is not True


def test_generic_flux_txt2img_builder_unchanged() -> None:
    from app.workflows.flux_image import build_flux_txt2img_workflow

    graph = build_flux_txt2img_workflow(
        positive="a cat on a bench",
        negative="blur",
        width=1024,
        height=1024,
        seed=1,
        unet_name="flux1-dev.safetensors",
        clip_l_name="clip_l.safetensors",
        t5_name="t5xxl_fp16.safetensors",
        vae_name="ae.safetensors",
    )
    assert graph["1"]["class_type"] == "UNETLoader"
    assert graph["9"]["inputs"]["batch_size"] == 1
    assert "a cat on a bench" in graph["4"]["inputs"]["text"]
