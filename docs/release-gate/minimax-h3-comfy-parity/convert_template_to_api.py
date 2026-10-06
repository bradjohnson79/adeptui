"""Convert the uploaded MiniMax H3 UI template into a queueable API graph."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UI_PATH = ROOT / "46a303cbccf9_ui_template.json"
API_PATH = ROOT / "Scene5_H3_CanonicalTemplate_API.json"
PARITY_PATH = ROOT / "Scene5_H3_Parity_DirectComfy.json"

ADDEX = "studio/91b82df6-6c5a-410a-bdb8-6cd3f79753c7.jpeg"
KORRI = "studio/a42e77e0-dfe3-4ac9-85af-ab98dfc510e5.jpeg"
SEED = 2248151181

SCENE5_PROMPT = """Realistic Anime. Use <Picture 1> as Addex and <Picture 2> as Korri. Preserve the people and clothing shown in those references.

Addex from <Picture 1> is already seated on the couch, thinking.

Korri from <Picture 2> stands beside him, then sits next to him. They hold hands. Keep both people looking exactly like their reference pictures, including face, hair, body, and clothes. The room may be sci-fi; do not put them in new uniforms.

Korri from <Picture 2>: Hey babe, are you ready for some fun?

Addex from <Picture 1> smiles.

Addex from <Picture 1>: You know I am."""


def _named(node: dict) -> dict:
    named = node.get("widgets_values_named") or {}
    if named:
        return dict(named)
    values = list(node.get("widgets_values") or [])
    widgets = [
        item.get("name")
        for item in (node.get("inputs") or [])
        if isinstance(item, dict) and item.get("widget")
    ]
    return {name: values[i] for i, name in enumerate(widgets) if i < len(values)}


def convert_ui(ui: dict) -> dict:
    links = {int(item[0]): item for item in ui.get("links") or []}
    api: dict[str, dict] = {}
    skip = {"MarkdownNote", "Note"}
    for node in ui.get("nodes") or []:
        class_type = str(node.get("type") or "")
        if class_type in skip:
            continue
        node_id = str(node["id"])
        inputs: dict = {}
        named = _named(node)
        for item in node.get("inputs") or []:
            name = str(item.get("name") or "")
            link_id = item.get("link")
            if link_id is not None:
                link = links[int(link_id)]
                inputs[name] = [str(link[1]), int(link[2])]
            elif name in named:
                inputs[name] = named[name]
            elif item.get("widget") and item["widget"].get("name") in named:
                inputs[name] = named[item["widget"]["name"]]
        if class_type == "MiniMaxH3ReferenceToVideo":
            ref_images = {}
            for key in list(inputs):
                if key.startswith("ref_images."):
                    ref_images[key.split(".", 1)[1]] = inputs.pop(key)
            if ref_images:
                inputs["ref_images"] = ref_images
            for dead in ("ref_videos.ref_video_0", "ref_video_audios.ref_video_audio_0", "ref_audios.ref_audio_0"):
                inputs.pop(dead, None)
        if class_type == "SaveVideo":
            inputs.setdefault("format", "auto")
            inputs.setdefault("codec", "auto")
            inputs["format.codec"] = "auto"
        if class_type == "CLIPLoader":
            inputs.setdefault("type", "minimax")
        api[node_id] = {"class_type": class_type, "inputs": inputs}
    return api


def flatten_parity(api: dict) -> dict:
    """Effective graph: Lightning LoRA off, no EasyCache, baked 5s / 16:9@0.4MP."""
    prompt = api["138"]["inputs"]["value"]
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                "type": "minimax",
                "device": "default",
            },
        },
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "5": {
            "class_type": "MiniMaxH3ReferenceToVideo",
            "inputs": {
                "clip": ["2", 0],
                "vae": ["3", 0],
                "audio_vae": ["4", 0],
                "prompt": prompt,
                "width": 864,
                "height": 480,
                "length": 124,
                "ref_image_size": "match",
                "ref_images": {"ref_image_0": ["15", 0], "ref_image_1": ["16", 0]},
            },
        },
        "6": {"class_type": "RandomNoise", "inputs": {"noise_seed": SEED}},
        "7": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "8": {
            "class_type": "BasicScheduler",
            "inputs": {"model": ["1", 0], "scheduler": "simple", "steps": 20, "denoise": 1.0},
        },
        "9": {"class_type": "BasicGuider", "inputs": {"model": ["1", 0], "conditioning": ["5", 0]}},
        "10": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["6", 0],
                "guider": ["9", 0],
                "sampler": ["7", 0],
                "sigmas": ["8", 0],
                "latent_image": ["5", 1],
            },
        },
        "11": {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["3", 0]}},
        "12": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["10", 0], "vae": ["4", 0]}},
        "13": {"class_type": "CreateVideo", "inputs": {"images": ["11", 0], "fps": 24.0, "audio": ["12", 0], "bit_depth": 8}},
        "14": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["13", 0],
                "filename_prefix": "identity_test/h3_comfy_parity",
                "format": "auto",
                "codec": "auto",
                "format.codec": "auto",
            },
        },
        "15": {"class_type": "LoadImage", "inputs": {"image": ADDEX}},
        "16": {"class_type": "LoadImage", "inputs": {"image": KORRI}},
    }


def main() -> None:
    ui = json.loads(UI_PATH.read_text(encoding="utf-8"))
    api = convert_ui(ui)
    API_PATH.write_text(json.dumps(api, indent=2), encoding="utf-8")
    api["137"]["inputs"]["image"] = ADDEX
    api["139"]["inputs"]["image"] = KORRI
    api["138"]["inputs"]["value"] = SCENE5_PROMPT
    api["129"]["inputs"]["noise_seed"] = SEED
    api["92"]["inputs"]["filename_prefix"] = "identity_test/h3_template_ui"
    flattened = flatten_parity(api)
    flattened["5"]["inputs"]["prompt"] = SCENE5_PROMPT
    PARITY_PATH.write_text(json.dumps(flattened, indent=2), encoding="utf-8")
    (ROOT / "Scene5_H3_CanonicalTemplate_API_scene5.json").write_text(json.dumps(api, indent=2), encoding="utf-8")
    print(json.dumps({
        "api_nodes": sorted(api, key=lambda x: int(x)),
        "picture_1": flattened["15"]["inputs"]["image"],
        "picture_2": flattened["16"]["inputs"]["image"],
        "ref_image_size": flattened["5"]["inputs"]["ref_image_size"],
        "scheduler": flattened["8"]["inputs"]["scheduler"],
        "steps": flattened["8"]["inputs"]["steps"],
        "resolution": f"{flattened['5']['inputs']['width']}x{flattened['5']['inputs']['height']}",
        "length": flattened["5"]["inputs"]["length"],
        "easyCache": any(n.get("class_type") == "EasyCache" for n in flattened.values()),
        "lora": any(n.get("class_type") == "LoraLoaderModelOnly" for n in flattened.values()),
        "subject_tokens": "<Subject" in SCENE5_PROMPT,
        "picture_tokens": "<Picture 1>" in SCENE5_PROMPT and "<Picture 2>" in SCENE5_PROMPT,
    }, indent=2))


if __name__ == "__main__":
    main()
