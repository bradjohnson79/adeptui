"""LTX 2.5 builder tests — topology, node selection, no silent fallback.

Verifies that the rewritten ltx_25_builder produces workflows matching
the verified official Lightricks LTX 2.5 topology, with no nonexistent
LTXV2* nodes and no silent fallback to LTX 2.3 builders.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.workflows.ltx_25_builder import _snap_ltx_25_spatial, build_ltx_25_i2v, build_ltx_25_t2v


class FakeSettings:
    ltx_2_5_checkpoint = "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors"
    ltx_2_5_video_vae = "ltx-2.5-video-vae-bf16.safetensors"
    ltx_2_5_audio_vae = "ltx-2.5-audio-vae-bf16.safetensors"
    ltx_2_5_text_encoder = "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"


SETTINGS = FakeSettings()
EXEC_ID = "test-exec-001"
PROMPT = "a cinematic scene of a forest at sunset"
NEGATIVE = "blurry, low quality"
WIDTH = 1280
HEIGHT = 720
SNAPPED_HEIGHT = 704
DURATION = 5.0
FPS = 24
SEED = 42


def _nodes(wf: dict[str, Any]) -> dict[str, str]:
    return {nid: node["class_type"] for nid, node in wf.items()}


def _node(wf: dict[str, Any], class_type: str) -> dict[str, Any] | None:
    for node in wf.values():
        if node["class_type"] == class_type:
            return node
    return None


def _assert_node_count(wf: dict[str, Any], class_type: str, expected: int) -> None:
    count = sum(1 for node in wf.values() if node["class_type"] == class_type)
    assert count == expected, f"Expected {expected} {class_type} nodes, got {count}"


def test_snap_720p_to_patch_aligned():
    assert _snap_ltx_25_spatial(1280, 720) == (1280, 704)
    assert _snap_ltx_25_spatial(1280, 704) == (1280, 704)


class TestNoInventedNodes:
    def test_no_ltxv2_text_to_video(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        classes = set(_nodes(wf).values())
        assert "LTXV2TextToVideo" not in classes

    def test_no_ltxv2_img_to_video(self):
        wf = build_ltx_25_i2v(SETTINGS, EXEC_ID, PROMPT, start_image_path="test.png")
        classes = set(_nodes(wf).values())
        assert "LTXV2ImgToVideo" not in classes

    def test_no_ltxv2_first_last_frame(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        classes = set(_nodes(wf).values())
        assert "LTXV2FirstLastFrameToVideo" not in classes

    def test_no_checkpoint_loader_simple(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        classes = set(_nodes(wf).values())
        assert "CheckpointLoaderSimple" not in classes

    def test_no_vhs_video_combine(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        classes = set(_nodes(wf).values())
        assert "VHS_VideoCombine" not in classes

    def test_no_ltxav_text_encoder_loader(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        classes = set(_nodes(wf).values())
        assert "LTXAVTextEncoderLoader" not in classes

    def test_no_cfg_guider(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        classes = set(_nodes(wf).values())
        assert "CFGGuider" not in classes

    def test_no_sampler_custom_advanced(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        classes = set(_nodes(wf).values())
        assert "SamplerCustomAdvanced" not in classes

    def test_no_basic_scheduler(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        classes = set(_nodes(wf).values())
        assert "BasicScheduler" not in classes


class TestT2VTopology:
    def test_uses_unet_loader(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        n = _node(wf, "UNETLoader")
        assert n is not None
        assert n["inputs"]["unet_name"] == SETTINGS.ltx_2_5_checkpoint
        assert n["inputs"]["weight_dtype"] == "default"

    def test_uses_vae_loader(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT, generate_audio=False)
        _assert_node_count(wf, "VAELoader", 1)
        n = _node(wf, "VAELoader")
        assert n["inputs"]["vae_name"] == SETTINGS.ltx_2_5_video_vae

    def test_uses_clip_loader_with_ltxv_type(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        n = _node(wf, "CLIPLoader")
        assert n is not None
        assert n["inputs"]["clip_name"] == SETTINGS.ltx_2_5_text_encoder
        assert n["inputs"]["type"] == "ltxv"

    def test_uses_clip_text_encode(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        _assert_node_count(wf, "CLIPTextEncode", 2)

    def test_uses_ltxv_conditioning(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        n = _node(wf, "LTXVConditioning")
        assert n is not None
        assert n["inputs"]["frame_rate"] == float(FPS)

    def test_base_sampler_handles_dimensions(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT, generate_audio=False)
        n = _node(wf, "LTXVBaseSampler")
        assert n is not None
        assert n["inputs"]["width"] == WIDTH
        assert n["inputs"]["height"] == SNAPPED_HEIGHT

    def test_uses_model_sampling_ltxv(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        n = _node(wf, "ModelSamplingLTXV")
        assert n is not None
        assert n["inputs"]["max_shift"] == pytest.approx(2.05)
        assert n["inputs"]["base_shift"] == pytest.approx(0.95)

    def test_uses_ltxv_scheduler(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        n = _node(wf, "LTXVScheduler")
        assert n is not None
        assert n["inputs"]["max_shift"] == pytest.approx(2.05)
        assert n["inputs"]["base_shift"] == pytest.approx(0.95)

    def test_uses_random_noise(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT, seed=SEED)
        n = _node(wf, "RandomNoise")
        assert n is not None
        assert n["inputs"]["noise_seed"] == SEED

    def test_uses_k_sampler_select(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        n = _node(wf, "KSamplerSelect")
        assert n is not None
        assert n["inputs"]["sampler_name"] == "euler"

    def test_uses_stg_guider_node(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        n = _node(wf, "STGGuiderNode")
        assert n is not None
        assert n["inputs"]["cfg"] == pytest.approx(3.0)
        assert n["inputs"]["stg"] == pytest.approx(1.0)

    def test_uses_ltxv_base_sampler(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        n = _node(wf, "LTXVBaseSampler")
        assert n is not None
        assert n["inputs"]["width"] == WIDTH
        assert n["inputs"]["height"] == SNAPPED_HEIGHT

    def test_uses_ltxv_tiled_vae_decode(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        _assert_node_count(wf, "LTXVTiledVAEDecode", 1)

    def test_uses_create_video(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        _assert_node_count(wf, "CreateVideo", 1)

    def test_uses_save_video(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        n = _node(wf, "SaveVideo")
        assert n is not None
        assert n["inputs"]["format"] == "mp4"

    def test_fast_mode_8_steps(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT, fast_mode=True)
        n = _node(wf, "LTXVScheduler")
        assert n["inputs"]["steps"] == 8

    def test_quality_mode_40_steps(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT, fast_mode=False)
        n = _node(wf, "LTXVScheduler")
        assert n["inputs"]["steps"] == 40

    def test_frame_count_multiple_of_8_plus_1(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT, length_seconds=5.0, fps=24)
        n = _node(wf, "LTXVBaseSampler")
        total_frames = n["inputs"]["num_frames"]
        # 5 * 24 = 120, should round up to 1 + multiple of 8 = 121
        assert total_frames == 121
        assert (total_frames - 1) % 8 == 0

    def test_negative_prompt_empty_defaults_to_empty_string(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        encode_nodes = [n for n in wf.values() if n["class_type"] == "CLIPTextEncode"]
        neg_node = encode_nodes[1]
        assert neg_node["inputs"]["text"] == ""


class TestT2VAudio:
    def test_audio_off_no_audio_vae(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT, generate_audio=False)
        _assert_node_count(wf, "VAELoader", 1)  # video VAE only
        assert _node(wf, "LTXVSeparateAVLatent") is None

    def test_audio_on_adds_audio_vae(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT, generate_audio=True)
        _assert_node_count(wf, "VAELoader", 2)  # video + audio VAE

    def test_audio_on_adds_audio_vae_loader(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT, generate_audio=True)
        _assert_node_count(wf, "VAELoader", 2)

    def test_audio_on_no_separate_decode(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT, generate_audio=True)
        assert _node(wf, "LTXVSeparateAVLatent") is None
        assert _node(wf, "LTXVAudioVAEDecode") is None

    def test_audio_off_create_video_no_audio_input(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT, generate_audio=False)
        n = _node(wf, "CreateVideo")
        assert n is not None
        assert "audio" not in n["inputs"]

    def test_audio_off_tiled_decode_from_base_sampler_directly(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT, generate_audio=False)
        n = _node(wf, "LTXVTiledVAEDecode")
        src = n["inputs"]["latents"]
        sampler_node = _node(wf, "LTXVBaseSampler")
        assert src == [list(wf.keys())[list(wf.values()).index(sampler_node)], 0], \
            "No-audio path feeds base sampler output directly to tiled decode"


class TestI2VTopology:
    START_IMAGE = "test_input.png"

    def test_uses_load_image(self):
        wf = build_ltx_25_i2v(SETTINGS, EXEC_ID, PROMPT, start_image_path=self.START_IMAGE)
        _assert_node_count(wf, "LoadImage", 1)
        n = _node(wf, "LoadImage")
        assert n["inputs"]["image"] == self.START_IMAGE

    def test_uses_ltxv_img_to_video(self):
        wf = build_ltx_25_i2v(SETTINGS, EXEC_ID, PROMPT, start_image_path=self.START_IMAGE)
        n = _node(wf, "LTXVImgToVideo")
        assert n is not None
        assert n["inputs"]["width"] == WIDTH
        assert n["inputs"]["height"] == SNAPPED_HEIGHT
        assert n["inputs"]["strength"] == pytest.approx(0.95)

    def test_base_sampler_receives_last_frame_images(self):
        wf = build_ltx_25_i2v(SETTINGS, EXEC_ID, PROMPT, start_image_path=self.START_IMAGE)
        sampler = _node(wf, "LTXVBaseSampler")
        img_id = [nid for nid, n in wf.items() if n["class_type"] == "LoadImage"][0]
        assert sampler["inputs"]["optional_cond_images"] == [img_id, 0]
        assert sampler["inputs"]["optional_cond_indices"] == "0"
        assert sampler["inputs"]["strength"] == pytest.approx(0.95)

    def test_i2v_stg_guider_wired_from_ltxv_img_to_video(self):
        wf = build_ltx_25_i2v(SETTINGS, EXEC_ID, PROMPT, start_image_path=self.START_IMAGE)
        guider = _node(wf, "STGGuiderNode")
        assert guider is not None
        # Guider's positive should come from LTXVImgToVideo output 0
        img_node = _node(wf, "LTXVImgToVideo")
        assert guider["inputs"]["positive"] == [list(wf.keys())[list(wf.values()).index(img_node)], 0]

    def test_i2v_accepts_empty_start_image(self):
        wf = build_ltx_25_i2v(SETTINGS, EXEC_ID, PROMPT, start_image_path="")
        n = _node(wf, "LoadImage")
        assert n is not None
        assert n["inputs"]["image"] == ""

    def test_i2v_audio_on(self):
        wf = build_ltx_25_i2v(SETTINGS, EXEC_ID, PROMPT,
                              start_image_path=self.START_IMAGE, generate_audio=True)
        _assert_node_count(wf, "VAELoader", 2)
        assert _node(wf, "LTXVAudioVAEDecode") is None

    def test_i2v_audio_off(self):
        wf = build_ltx_25_i2v(SETTINGS, EXEC_ID, PROMPT,
                              start_image_path=self.START_IMAGE, generate_audio=False)
        _assert_node_count(wf, "VAELoader", 1)
        assert _node(wf, "LTXVAudioVAEDecode") is None


class TestInt8Persistence:
    def test_t2v_uses_int8_checkpoint_by_default(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        n = _node(wf, "UNETLoader")
        assert "int8" in n["inputs"]["unet_name"].lower()

    def test_i2v_uses_int8_checkpoint_by_default(self):
        wf = build_ltx_25_i2v(SETTINGS, EXEC_ID, PROMPT, start_image_path="test.png")
        n = _node(wf, "UNETLoader")
        assert "int8" in n["inputs"]["unet_name"].lower()

    def test_clip_loader_uses_int8_encoder_by_default(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        n = _node(wf, "CLIPLoader")
        assert "int8" in n["inputs"]["clip_name"].lower()


class TestBf16Fallback:
    class Bf16Settings:
        ltx_2_5_checkpoint = "ltx-2.5-22b-distilled-transformer-bf16.safetensors"
        ltx_2_5_video_vae = "ltx-2.5-video-vae-bf16.safetensors"
        ltx_2_5_audio_vae = "ltx-2.5-audio-vae-bf16.safetensors"
        ltx_2_5_text_encoder = "gemma4-12b-with-proj-ltx-2.5-bf16.safetensors"

    def test_t2v_bf16_checkpoint(self):
        wf = build_ltx_25_t2v(self.Bf16Settings(), EXEC_ID, PROMPT)
        n = _node(wf, "UNETLoader")
        assert "bf16" in n["inputs"]["unet_name"].lower()

    def test_t2v_bf16_clip_encoder(self):
        wf = build_ltx_25_t2v(self.Bf16Settings(), EXEC_ID, PROMPT)
        n = _node(wf, "CLIPLoader")
        assert n["inputs"]["clip_name"] == self.Bf16Settings.ltx_2_5_text_encoder


class TestStructuralIntegrity:
    def test_all_links_resolve(self):
        """Every link target (list with [node_id, slot]) must reference a node that exists."""
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        node_ids = set(wf.keys())
        for node_id, node in wf.items():
            for key, value in node["inputs"].items():
                if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                    assert value[0] in node_ids, (
                        f"Node {node_id} ({node['class_type']}) input '{key}' "
                        f"links to {value[0]} which does not exist"
                    )

    def test_no_orphan_nodes(self):
        """Every node except SaveVideo (output) and standalone audio VAE loader must be referenced."""
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        node_ids = set(wf.keys())
        referenced: set[str] = set()
        for node_id, node in wf.items():
            for key, value in node["inputs"].items():
                if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                    referenced.add(value[0])
        save_id = [nid for nid, n in wf.items() if n["class_type"] == "SaveVideo"][0]
        avae_id = [nid for nid, n in wf.items() if n["class_type"] == "VAELoader" and "audio" in str(n["inputs"].get("vae_name", "")).lower()]
        exempt = {save_id, *(avae_id[:1])}
        unreferenced = (node_ids - referenced) - exempt
        assert not unreferenced, f"Unreferenced nodes: {unreferenced}"

    def test_stg_guider_output_connected_to_base_sampler(self):
        wf = build_ltx_25_t2v(SETTINGS, EXEC_ID, PROMPT)
        sampler = _node(wf, "LTXVBaseSampler")
        guider_id = [nid for nid, n in wf.items() if n["class_type"] == "STGGuiderNode"][0]
        assert sampler["inputs"]["guider"] == [guider_id, 0]

    def test_no_fallback_to_ltx_builder(self):
        """Confirm ltx_25_builder does not reference any ltx_builder internals."""
        import inspect
        from app.workflows import ltx_25_builder
        source = inspect.getsource(ltx_25_builder)
        # Check we're not importing or referencing the LTX 2.3 builder
        assert "ltx_builder" not in source
        assert "LTXDirector" not in source
        assert "build_ltx_scene_workflow" not in source
        assert "build_ltx_simple_i2v" not in source
