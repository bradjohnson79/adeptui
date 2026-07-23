from __future__ import annotations

from typing import Any, Optional


CHARACTER_SHEET_VIEWS: list[dict[str, str]] = [
    {
        "key": "front",
        "tag_suffix": "front",
        "label": "Front view",
        "prompt": (
            "character design reference sheet, full body front view, standing facing camera, "
            "neutral pose, clean studio lighting, plain light gray background, "
            "same character identity and outfit as the reference image, highly detailed, "
            "consistent face and clothing, professional character turnaround"
        ),
    },
    {
        "key": "side",
        "tag_suffix": "side",
        "label": "Side view",
        "prompt": (
            "character design reference sheet, full body side profile view, standing, "
            "clean studio lighting, plain light gray background, "
            "same character identity and outfit as the reference image, highly detailed, "
            "consistent silhouette and clothing, professional character turnaround"
        ),
    },
    {
        "key": "back",
        "tag_suffix": "back",
        "label": "Back view",
        "prompt": (
            "character design reference sheet, full body back view, standing facing away, "
            "clean studio lighting, plain light gray background, "
            "same character identity and outfit as the reference image, highly detailed, "
            "consistent hair and clothing from behind, professional character turnaround"
        ),
    },
    {
        "key": "front_closeup",
        "tag_suffix": "front_closeup",
        "label": "Front close-up",
        "prompt": (
            "clean character portrait close-up, front view face and shoulders, "
            "neutral expression, soft studio lighting, plain light gray background, "
            "same face identity as the reference image, sharp details, no text, no watermark"
        ),
    },
    {
        "key": "side_closeup",
        "tag_suffix": "side_closeup",
        "label": "Side close-up",
        "prompt": (
            "clean character portrait close-up, side profile face and shoulders, "
            "neutral expression, soft studio lighting, plain light gray background, "
            "same face identity as the reference image, sharp details, no text, no watermark"
        ),
    },
]


CAMERA_ANGLE_VIEWS: list[dict[str, str]] = [
    {
        "key": "angle_a",
        "tag_suffix": "angle_left",
        "label": "Three-quarter left",
        "prompt": (
            "same scene and same character as the reference photo, "
            "camera moved to a three-quarter angle from the left, eye-level, "
            "keep background layout and character identity fully consistent, "
            "photorealistic continuity, matched lighting"
        ),
    },
    {
        "key": "angle_b",
        "tag_suffix": "angle_low",
        "label": "Low angle",
        "prompt": (
            "same scene and same character as the reference photo, "
            "low camera angle looking slightly upward, "
            "keep background layout and character identity fully consistent, "
            "photorealistic continuity, matched lighting"
        ),
    },
    {
        "key": "angle_c",
        "tag_suffix": "angle_high",
        "label": "High angle",
        "prompt": (
            "same scene and same character as the reference photo, "
            "high camera angle looking slightly downward, "
            "keep background layout and character identity fully consistent, "
            "photorealistic continuity, matched lighting"
        ),
    },
]


def build_zimage_ref_workflow(
    *,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    clip_vision_name: str,
    reference_image: str,
    prompt: str,
    negative: str = "blurry, deformed, watermark, text, logo, extra limbs",
    width: int = 1024,
    height: int = 1024,
    seed: int = 42,
    steps: int = 8,
    cfg: float = 1.0,
    filename_prefix: str = "studio/zimg",
    use_clip_vision: bool = True,
) -> dict[str, Any]:
    """
    Z-Image Turbo + TextEncodeZImageOmni reference workflow.
    Generates one image guided by a reference still.
    """
    wf: dict[str, Any] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": unet_name, "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": clip_name, "type": "lumina2"},
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae_name},
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": reference_image},
        },
        "5": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["1", 0], "shift": 3.0},
        },
        "7": {
            "class_type": "TextEncodeZImageOmni",
            "inputs": {
                "clip": ["2", 0],
                "prompt": prompt,
                "auto_resize_images": True,
                "vae": ["3", 0],
                "image1": ["4", 0],
            },
        },
        "8": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["2", 0]},
        },
        "9": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "10": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["5", 0],
                "seed": seed if seed >= 0 else 42,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "simple",
                "positive": ["7", 0],
                "negative": ["8", 0],
                "latent_image": ["9", 0],
                "denoise": 1.0,
            },
        },
        "11": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["10", 0], "vae": ["3", 0]},
        },
        "12": {
            "class_type": "SaveImage",
            "inputs": {"images": ["11", 0], "filename_prefix": filename_prefix},
        },
    }

    if use_clip_vision and clip_vision_name:
        wf["6"] = {
            "class_type": "CLIPVisionLoader",
            "inputs": {"clip_name": clip_vision_name},
        }
        wf["7"]["inputs"]["image_encoder"] = ["6", 0]

    return wf


def views_for_tool(tool: str) -> list[dict[str, str]]:
    if tool == "character_sheet":
        return CHARACTER_SHEET_VIEWS
    if tool == "multi_angle":
        return CAMERA_ANGLE_VIEWS
    raise ValueError(f"Unknown image tool: {tool}")


def customize_angle_prompts(custom: Optional[list[str]]) -> list[dict[str, str]]:
    base = [dict(v) for v in CAMERA_ANGLE_VIEWS]
    if not custom:
        return base
    for i, text in enumerate(custom[:3]):
        if text and text.strip():
            base[i]["prompt"] = text.strip()
    return base
