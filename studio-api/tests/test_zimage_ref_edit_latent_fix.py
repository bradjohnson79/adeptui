"""Guard: zimage.ref_edit must not combine Omni+image with EmptyLatent (shape crash)."""

from app.workflows.image_tools import build_zimage_ref_workflow


def test_ref_edit_uses_vae_encode_not_empty_latent_with_omni_image():
    wf = build_zimage_ref_workflow(
        unet_name="z.safetensors",
        clip_name="clip.safetensors",
        vae_name="vae.safetensors",
        clip_vision_name="",
        reference_image="hero.png",
        prompt="Korri front view",
        width=1024,
        height=1024,
        use_clip_vision=False,
    )
    types = {n["class_type"] for n in wf.values()}
    assert "VAEEncode" in types
    assert "ImageScale" in types
    assert "EmptyLatentImage" not in types
    omni = next(n for n in wf.values() if n["class_type"] == "TextEncodeZImageOmni")
    assert "image1" not in omni["inputs"]
    assert "vae" not in omni["inputs"]
    sampler = next(n for n in wf.values() if n["class_type"] == "KSampler")
    assert float(sampler["inputs"]["denoise"]) < 1.0
