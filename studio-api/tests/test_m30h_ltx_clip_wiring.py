"""LTX 2.3 builders must wire CLIP via LTXAVTextEncoderLoader (not null ckpt CLIP)."""

from app.workflows.ltx_builder import build_ltx_scene_workflow, build_ltx_simple_i2v


def test_scene_workflow_uses_explicit_text_encoder_clip():
    wf = build_ltx_scene_workflow(
        checkpoint="ltx-2.3-22b-distilled-fp8.safetensors",
        positive="one character",
        negative="crowd",
        width=768,
        height=512,
        length=49,
        fps=24,
        seed=1,
        start_image="start.png",
        text_encoder="gemma_3_12B_it_fp4_mixed.safetensors",
    )
    assert wf["2"]["class_type"] == "LTXAVTextEncoderLoader"
    assert wf["10"]["inputs"]["clip"] == ["2", 0]


def test_simple_i2v_binds_start_image_and_text_encoder():
    wf = build_ltx_simple_i2v(
        checkpoint="ltx-2.3-22b-distilled-fp8.safetensors",
        positive="one character",
        negative="crowd",
        width=768,
        height=512,
        length=49,
        fps=24,
        seed=1,
        start_image="start.png",
        text_encoder="gemma_3_12B_it_fp4_mixed.safetensors",
    )
    assert wf["1b"]["class_type"] == "LTXAVTextEncoderLoader"
    assert wf["4"]["inputs"]["image"] == "start.png"
    assert wf["5"]["class_type"] == "LTXVImgToVideo"
    assert wf["5"]["inputs"]["image"] == ["4", 0]
