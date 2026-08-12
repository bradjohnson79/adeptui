"""Adept-owned Comfy workflow builders for HunyuanVideo 13B via Kijai HyVideo nodes.

Migrated from obsolete HunyuanVideo13BLoader/Sampler/ImgToVideo class names to the
live HyVideo* family exported by ComfyUI-HunyuanVideoWrapper.
"""

from __future__ import annotations

from typing import Any, Optional

from .hunyuan15_builder import (
    HUNYUAN13B_T2V_FP8,
    HUNYUAN13B_T2V_FULL,
    build_hunyuan15_i2v,
    build_hunyuan15_t2v,
)


def build_hunyuan13b_t2v(
    *,
    model_root: str,
    positive: str,
    negative: str = "",
    width: int = 1280,
    height: int = 720,
    length: int = 129,
    fps: int = 24,
    seed: int = 0,
    steps: int = 50,
    cfg: float = 6.0,
    profile: str = "fp8_production",
    filename_prefix: str = "studio/hunyuan13b_t2v",
) -> dict[str, Any]:
    """Text-to-video for HunyuanVideo 13B through the shared HyVideo runtime."""
    graph = build_hunyuan15_t2v(
        model_root=model_root,
        positive=positive,
        negative=negative,
        width=width,
        height=height,
        length=length,
        fps=fps,
        seed=seed,
        steps=steps,
        cfg=cfg,
        filename_prefix=filename_prefix,
        diffusion_model=HUNYUAN13B_T2V_FP8 if profile.startswith("fp8") else HUNYUAN13B_T2V_FULL,
    )
    # Prefer FP8 quantization for the production profile when the loader supports it.
    for node in graph.values():
        if node.get("class_type") == "HyVideoModelLoader" and profile.startswith("fp8"):
            node["inputs"]["quantization"] = "fp8_e4m3fn"
            node["inputs"]["base_precision"] = "bf16"
    return graph


def build_hunyuan13b_i2v(
    *,
    model_root: str,
    positive: str,
    negative: str = "",
    start_image: Optional[str] = None,
    width: int = 1280,
    height: int = 720,
    length: int = 129,
    fps: int = 24,
    seed: int = 0,
    steps: int = 50,
    cfg: float = 6.0,
    profile: str = "fp8_production",
    filename_prefix: str = "studio/hunyuan13b_i2v",
) -> dict[str, Any]:
    graph = build_hunyuan15_i2v(
        model_root=model_root,
        positive=positive,
        negative=negative,
        start_image=start_image,
        width=width,
        height=height,
        length=length,
        fps=fps,
        seed=seed,
        steps=steps,
        cfg=cfg,
        filename_prefix=filename_prefix,
        # 13B catalog exposes t2v weights only; i2v graph uses the fp8 t2v checkpoint.
        diffusion_model=HUNYUAN13B_T2V_FP8 if profile.startswith("fp8") else HUNYUAN13B_T2V_FULL,
    )
    for node in graph.values():
        if node.get("class_type") == "HyVideoModelLoader" and profile.startswith("fp8"):
            node["inputs"]["quantization"] = "fp8_e4m3fn"
            node["inputs"]["base_precision"] = "bf16"
    return graph
