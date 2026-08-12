"""Regression: WAN 2.2 encoder must be 4096-d UMT5; reject legacy 768 path."""

from pathlib import Path

import pytest

from app.workflows.wan_encoder_contract import (
    WAN_AUTHORITATIVE_TEXT_ENCODER,
    WAN_TEXT_EMBEDDING_DIM,
    WanEncoderContractError,
    assert_conditioning_last_dim,
    assert_wan_text_encoder_contract,
)
from app.workflows.wan_builder import build_wan_flf_workflow


def test_authoritative_encoder_passes_filename_contract():
    report = assert_wan_text_encoder_contract(WAN_AUTHORITATIVE_TEXT_ENCODER)
    assert report["ok"] is True
    assert report["expectedEmbeddingDim"] == 4096


def test_legacy_enc_bf16_rejected():
    with pytest.raises(WanEncoderContractError, match="768|Rejected|enc-bf16"):
        assert_wan_text_encoder_contract("umt5-xxl-enc-bf16.safetensors")


def test_builder_rejects_legacy_encoder_before_unet_nodes():
    with pytest.raises(WanEncoderContractError):
        build_wan_flf_workflow(
            high_noise="wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
            low_noise="wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
            vae_name="WanVideo/Wan2_1_VAE_bf16.safetensors",
            text_encoder="umt5-xxl-enc-bf16.safetensors",
            positive="x",
            negative="y",
            width=640,
            height=368,
            length=9,
            fps=16,
            seed=1,
            start_image="studio/start.png",
        )


def test_conditioning_last_dim_must_be_4096():
    assert_conditioning_last_dim(WAN_TEXT_EMBEDDING_DIM)
    with pytest.raises(WanEncoderContractError, match="768"):
        assert_conditioning_last_dim(768)


def test_key_layout_rejects_legacy_blocks_prefix(tmp_path: Path):
    # Minimal fake safetensors header with legacy blocks.* keys
    import json
    import struct

    meta = {
        "blocks.0.attn.q.weight": {
            "dtype": "BF16",
            "shape": [4096, 4096],
            "data_offsets": [0, 2],
        },
        "__metadata__": {"format": "pt"},
    }
    header = json.dumps(meta).encode("utf-8")
    blob = struct.pack("<Q", len(header)) + header + b"\x00\x00"
    path = tmp_path / "fake-legacy.safetensors"
    path.write_bytes(blob)

    from app.workflows.wan_encoder_contract import encoder_key_layout_ok

    ok, detail = encoder_key_layout_ok(path)
    assert ok is False
    assert detail["hasLegacyBlocksPrefix"] is True
