from __future__ import annotations

from pathlib import Path
from typing import Any

QWEN_EDIT_2509_FAMILY = "qwen_edit_2509"
QWEN_EDIT_2509_EDIT_KEY = "qwen_edit_2509.edit"
QWEN_EDIT_2509_CRS_KEY = "qwen_edit_2509.crs_single_view"
QWEN_EDIT_2509_DEFAULT_ROOT = r"D:\01_Models\Qwen\Qwen-Image-Edit-2509"
QWEN_EDIT_2509_PIPELINE = "QwenImageEditPlusPipeline"
QWEN_EDIT_2509_HF_REPO = "Qwen/Qwen-Image-Edit-2509"
QWEN_EDIT_2509_LICENSE = "Apache-2.0"

QWEN_EDIT_2509_DEFAULT_UNET = "qwen_image_edit_2509_fp8_e4m3fn.safetensors"
QWEN_EDIT_2509_DEFAULT_CLIP = "qwen_2.5_vl_7b_fp8_scaled.safetensors"
QWEN_EDIT_2509_DEFAULT_VAE = "qwen_image_vae.safetensors"

QWEN_EDIT_2509_DEFAULT_SIZE = 1024
QWEN_EDIT_2509_CHARACTER_ANGLE_SIZE = 768
QWEN_EDIT_2509_DEFAULT_STEPS = 8
QWEN_EDIT_2509_DEFAULT_CFG = 1.0
QWEN_EDIT_2509_DEFAULT_SAMPLER = "euler"
QWEN_EDIT_2509_DEFAULT_SCHEDULER = "simple"
QWEN_EDIT_2509_DEFAULT_SHIFT = 3.0
QWEN_EDIT_2509_DEFAULT_WEIGHT_DTYPE = "fp8_e4m3fn"
QWEN_EDIT_2509_STANDARD_NEGATIVE = (
    "blurry, low quality, deformed anatomy, extra fingers, extra limbs, "
    "watermark, logo, collage, contact sheet, four panel"
)

REQUIRED_COMFY_NODES = (
    "UNETLoader",
    "CLIPLoader",
    "VAELoader",
    "LoadImage",
    "TextEncodeQwenImageEditPlus",
    "EmptyLatentImage",
    "KSampler",
    "VAEDecode",
    "SaveImage",
    "ModelSamplingAuraFlow",
)

TRANSFORMER_SHARDS = (
    "diffusion_pytorch_model-00001-of-00005.safetensors",
    "diffusion_pytorch_model-00002-of-00005.safetensors",
    "diffusion_pytorch_model-00003-of-00005.safetensors",
    "diffusion_pytorch_model-00004-of-00005.safetensors",
    "diffusion_pytorch_model-00005-of-00005.safetensors",
)
TEXT_ENCODER_SHARDS = (
    "model-00001-of-00004.safetensors",
    "model-00002-of-00004.safetensors",
    "model-00003-of-00004.safetensors",
    "model-00004-of-00004.safetensors",
)


def _normalize_dimension(value: int, *, fallback: int) -> int:
    if value <= 0:
        value = fallback
    return max(16, int(round(value / 8.0) * 8))


def _normalize_seed(seed: int) -> int:
    return seed if seed >= 0 else 42


def comfy_filename(value: str | None, *, fallback: str) -> str:
    """Comfy combo filenames only — never an absolute D: / HF folder path."""
    raw = str(value or "").strip()
    if raw:
        name = Path(raw.replace("/", "\\")).name.strip()
        if name and name not in {".", ".."} and ":" not in name:
            return name
    return fallback


def _setting(name: str, fallback: str) -> str:
    try:
        from ..config import settings

        raw = str(getattr(settings, name, "") or "").strip()
    except Exception:
        raw = ""
    return comfy_filename(raw, fallback=fallback)


def configured_root() -> Path:
    try:
        from ..config import settings

        raw = str(getattr(settings, "qwen_image_edit_2509_root", "") or "").strip()
    except Exception:
        raw = ""
    return Path(raw or QWEN_EDIT_2509_DEFAULT_ROOT).expanduser()


def configured_unet() -> str:
    return _setting("qwen_image_edit_2509_unet", QWEN_EDIT_2509_DEFAULT_UNET)


def configured_clip() -> str:
    return _setting("qwen_image_edit_2509_clip", QWEN_EDIT_2509_DEFAULT_CLIP)


def configured_vae() -> str:
    return _setting("qwen_image_edit_2509_vae", QWEN_EDIT_2509_DEFAULT_VAE)


def unet_weight_dtype(unet_name: str | None = None) -> str:
    """Keep fp8 Qwen Edit weights on the fp8 compute path (same as Qwen 2512)."""
    name = (unet_name or configured_unet() or "").lower()
    if "fp8_e5m2" in name:
        return "fp8_e5m2"
    if "fp8" in name:
        return QWEN_EDIT_2509_DEFAULT_WEIGHT_DTYPE
    return "default"


def inspect_weights(root: Path | None = None) -> dict[str, Any]:
    """Installed-on-disk inspection. Does not imply Runtime Ready or Certified."""
    path = Path(root or configured_root())
    index = path / "model_index.json"
    pipeline = ""
    missing: list[str] = []
    if not path.is_dir():
        return {
            "installed": False,
            "root": str(path),
            "pipelineClass": "",
            "missing": ["root"],
            "license": QWEN_EDIT_2509_LICENSE,
            "hfRepo": QWEN_EDIT_2509_HF_REPO,
        }
    if not index.is_file():
        missing.append("model_index.json")
    else:
        try:
            import json

            payload = json.loads(index.read_text(encoding="utf-8"))
            pipeline = str(
                payload.get("_class_name") or payload.get("class_name") or ""
            ).strip()
            if pipeline != QWEN_EDIT_2509_PIPELINE:
                missing.append(f"pipeline:{pipeline or 'unknown'}")
        except Exception:
            missing.append("model_index.json:unreadable")
    for name in TRANSFORMER_SHARDS:
        if not (path / "transformer" / name).is_file():
            missing.append(f"transformer/{name}")
    for name in TEXT_ENCODER_SHARDS:
        if not (path / "text_encoder" / name).is_file():
            missing.append(f"text_encoder/{name}")
    if not (path / "vae" / "diffusion_pytorch_model.safetensors").is_file():
        missing.append("vae/diffusion_pytorch_model.safetensors")
    return {
        "installed": not missing,
        "root": str(path),
        "pipelineClass": pipeline,
        "missing": missing,
        "license": QWEN_EDIT_2509_LICENSE,
        "hfRepo": QWEN_EDIT_2509_HF_REPO,
    }


def _combo_choices(info: dict[str, Any], node: str, field: str) -> list[str]:
    raw = (((info.get(node) or {}).get("input") or {}).get("required") or {}).get(field)
    if isinstance(raw, dict) and isinstance(raw.get("value"), list):
        return [str(x) for x in raw["value"]]
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, list):
            return [str(x) for x in first]
    return []


def probe_comfy_runtime(object_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Runtime Ready is separate from Installed. Never Certified from this probe."""
    info = object_info
    if info is None:
        try:
            import urllib.request

            with urllib.request.urlopen("http://127.0.0.1:8188/object_info", timeout=4) as resp:
                import json

                info = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {
                "nodesPresent": False,
                "componentFilesVisible": False,
                "runtimeReady": False,
                "recoverRequired": True,
                "reason": f"Comfy object_info unavailable: {exc}",
                "missingNodes": list(REQUIRED_COMFY_NODES),
            }
    missing_nodes = [name for name in REQUIRED_COMFY_NODES if name not in info]
    hosted = "QwenImageEditApi" in info
    unet = configured_unet()
    clip = configured_clip()
    vae = configured_vae()
    unets = _combo_choices(info, "UNETLoader", "unet_name")
    clips = _combo_choices(info, "CLIPLoader", "clip_name")
    vaes = _combo_choices(info, "VAELoader", "vae_name")
    visible = unet in unets and clip in clips and vae in vaes
    runtime_ready = not missing_nodes and visible
    missing_files = [
        label
        for label, present in (
            (f"unet={unet}", unet in unets),
            (f"clip={clip}", clip in clips),
            (f"vae={vae}", vae in vaes),
        )
        if not present
    ]
    if runtime_ready:
        reason = "UNET/CLIP/VAE filenames visible to Comfy"
    elif missing_nodes:
        reason = "Comfy is missing required nodes: " + ", ".join(missing_nodes)
    else:
        reason = "Qwen Image Edit 2509 files are not visible to Comfy: " + ", ".join(missing_files)
    return {
        "nodesPresent": not missing_nodes,
        "missingNodes": missing_nodes,
        "missingFiles": missing_files,
        "componentFilesVisible": visible,
        "unetName": unet,
        "clipName": clip,
        "vaeName": vae,
        "hostedEditApiPresent": hosted,
        "runtimeReady": runtime_ready,
        "recoverRequired": not runtime_ready,
        "reason": reason,
    }


def discover_qwen_edit_2509(object_info: dict[str, Any] | None = None) -> dict[str, Any]:
    weights = inspect_weights()
    runtime = probe_comfy_runtime(object_info)
    installed = bool(weights.get("installed"))
    runtime_ready = bool(installed and runtime.get("runtimeReady"))
    return {
        "modelFamily": QWEN_EDIT_2509_FAMILY,
        "installed": installed,
        "runtimeReady": runtime_ready,
        "statusHint": "Draft",
        "certified": False,
        "classification": "i2i_edit",
        "t2iOnly": False,
        "identityRole": "IDENTITY_REFERENCE",
        "roles": [
            "identity_preserving_edit",
            "character_view_change",
            "crs_single_view",
        ],
        "defaultEditCanvas": "identity_reference_not_whole_crs",
        "license": QWEN_EDIT_2509_LICENSE,
        "hfRepo": QWEN_EDIT_2509_HF_REPO,
        "weights": weights,
        "runtime": runtime,
        "recoverRequired": bool(runtime.get("recoverRequired")) or not runtime_ready,
        "reason": compose_discover_reason(
            installed=installed,
            runtime_ready=runtime_ready,
            runtime=runtime,
        ),
    }


def compose_discover_reason(
    *,
    installed: bool,
    runtime_ready: bool,
    runtime: dict[str, Any],
) -> str:
    """Surface the actual failed predicate. Never collapse Comfy-down to a UNET sentence."""
    if runtime_ready:
        return "Runtime Ready"
    if not installed:
        return "Qwen Image Edit 2509 weights not found"
    return str(runtime.get("reason") or "Qwen Image Edit 2509 is installed but not Runtime Ready.")


def build_qwen_edit_2509_i2i_workflow(
    *,
    image_name: str,
    positive: str,
    negative: str = QWEN_EDIT_2509_STANDARD_NEGATIVE,
    model_path: str | None = None,
    unet_name: str | None = None,
    clip_name: str | None = None,
    vae_name: str | None = None,
    width: int = QWEN_EDIT_2509_DEFAULT_SIZE,
    height: int = QWEN_EDIT_2509_DEFAULT_SIZE,
    seed: int = 42,
    steps: int = QWEN_EDIT_2509_DEFAULT_STEPS,
    cfg: float = QWEN_EDIT_2509_DEFAULT_CFG,
    sampler_name: str = QWEN_EDIT_2509_DEFAULT_SAMPLER,
    scheduler: str = QWEN_EDIT_2509_DEFAULT_SCHEDULER,
    model_shift: float = QWEN_EDIT_2509_DEFAULT_SHIFT,
    filename_prefix: str = "studio/qwen_edit_2509",
    identity_role: str = "IDENTITY_REFERENCE",
    scene_image: str | None = None,
    scene_role: str = "SCENE_REFERENCE",
) -> dict[str, Any]:
    """Draft local I2I graph using live Comfy nodes (no hosted QwenImageEditApi).

    Same Qwen Image family load pattern as 2512: UNETLoader + CLIPLoader(type=qwen_image)
    + VAELoader. TextEncodeQwenImageEditPlus conditions the identity crop as image1.
    EmptyLatentImage is the sampler canvas. Never DiffusersLoader (broken on sharded HF).
    """
    _ = identity_role
    _ = scene_role
    _ = model_path
    unet = comfy_filename(unet_name, fallback=configured_unet())
    clip = comfy_filename(clip_name, fallback=configured_clip())
    vae = comfy_filename(vae_name, fallback=configured_vae())
    scene = str(scene_image or "").strip() or None
    pos_inputs: dict[str, Any] = {
        "clip": ["2", 0],
        "prompt": positive,
        "vae": ["3", 0],
        "image1": ["5", 0],
    }
    neg_inputs: dict[str, Any] = {
        "clip": ["2", 0],
        "prompt": negative or QWEN_EDIT_2509_STANDARD_NEGATIVE,
        "vae": ["3", 0],
        "image1": ["5", 0],
    }
    graph: dict[str, Any] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": unet,
                "weight_dtype": unet_weight_dtype(unet),
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": clip,
                "type": "qwen_image",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": vae,
            },
        },
        "4": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["1", 0], "shift": float(model_shift)},
        },
        "5": {
            "class_type": "LoadImage",
            "inputs": {"image": image_name},
        },
    }
    if scene:
        # CIS / CC multi-ref: image1=IDENTITY_REFERENCE, image2=SCENE_REFERENCE
        graph["12"] = {
            "class_type": "LoadImage",
            "inputs": {"image": scene},
        }
        pos_inputs["image2"] = ["12", 0]
        neg_inputs["image2"] = ["12", 0]
    graph["6"] = {
        "class_type": "TextEncodeQwenImageEditPlus",
        "inputs": pos_inputs,
    }
    graph["7"] = {
        "class_type": "TextEncodeQwenImageEditPlus",
        "inputs": neg_inputs,
    }
    graph["8"] = {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "width": _normalize_dimension(width, fallback=QWEN_EDIT_2509_DEFAULT_SIZE),
            "height": _normalize_dimension(height, fallback=QWEN_EDIT_2509_DEFAULT_SIZE),
            "batch_size": 1,
        },
    }
    graph["9"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": ["4", 0],
            "seed": _normalize_seed(seed),
            "steps": max(4, int(steps)),
            "cfg": float(cfg),
            "sampler_name": sampler_name or QWEN_EDIT_2509_DEFAULT_SAMPLER,
            "scheduler": scheduler or QWEN_EDIT_2509_DEFAULT_SCHEDULER,
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["8", 0],
            "denoise": 1.0,
        },
    }
    graph["10"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["9", 0], "vae": ["3", 0]},
    }
    graph["11"] = {
        "class_type": "SaveImage",
        "inputs": {"images": ["10", 0], "filename_prefix": filename_prefix},
    }
    return graph


def graph_contract(graph: dict[str, Any]) -> dict[str, Any]:
    types = [str((node or {}).get("class_type") or "") for node in graph.values()]
    save = [t for t in types if t == "SaveImage"]
    latent_sources = []
    for node in graph.values():
        if str((node or {}).get("class_type") or "") == "KSampler":
            latent_sources.append((node.get("inputs") or {}).get("latent_image"))
    return {
        "saveImageCount": len(save),
        "usesHostedEditApi": "QwenImageEditApi" in types,
        "usesTextEncodeQwenImageEditPlus": "TextEncodeQwenImageEditPlus" in types,
        "usesDiffusersLoader": "DiffusersLoader" in types,
        "usesUnetLoader": "UNETLoader" in types,
        "usesLayeredLatent": "EmptyQwenImageLayeredLatentImage" in types,
        "latentFromEmpty": any(
            isinstance(ref, list) and str(graph.get(str(ref[0]), {}).get("class_type")) == "EmptyLatentImage"
            for ref in latent_sources
        ),
        "t2iOnly": False,
        "identityInput": "image1",
        "hasImage2": any(
            "image2" in ((node or {}).get("inputs") or {})
            for node in graph.values()
            if str((node or {}).get("class_type") or "") == "TextEncodeQwenImageEditPlus"
        ),
        "loadImageCount": sum(
            1
            for node in graph.values()
            if str((node or {}).get("class_type") or "") == "LoadImage"
        ),
    }
