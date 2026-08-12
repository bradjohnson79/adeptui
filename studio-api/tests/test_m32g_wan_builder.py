"""M3.2g WAN workflow construction regressions."""

from app.workflows.wan_builder import build_wan_flf_workflow


def test_wan_builder_loads_clip_before_unets():
    wf = build_wan_flf_workflow(
        high_noise="wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
        low_noise="wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
        vae_name="WanVideo/Wan2_1_VAE_bf16.safetensors",
        text_encoder="umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        positive="dolly in hitchhiker",
        negative="blurry",
        width=1280,
        height=704,
        length=17,
        fps=16,
        seed=1,
        start_image="studio/start.png",
    )
    keys = list(wf.keys())
    assert keys.index("3") < keys.index("1")
    assert keys.index("5") < keys.index("1")
    assert wf["3"]["inputs"]["type"] == "wan"
    assert wf["3"]["inputs"]["clip_name"] == "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
    assert wf["11"]["class_type"] == "WanImageToVideo"


def test_wan_builder_rejects_legacy_enc_default_in_config_docstring_guard():
    # Guard: production default must be the Comfy-Org fp8 scaled encoder.
    from app.config import settings

    assert "fp8" in settings.wan_text_encoder or "umt5_xxl" in settings.wan_text_encoder
    assert "enc-bf16" not in settings.wan_text_encoder
