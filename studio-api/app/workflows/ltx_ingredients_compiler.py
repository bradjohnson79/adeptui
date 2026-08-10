"""Compile LTX 2.3 Ingredients IC-LoRA ComfyUI workflows from discovered nodes."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from ..references.ic_lora_status import find_ingredients_file, ingredients_status
from ..references.models import (
    INGREDIENTS_FILENAME,
    INGREDIENTS_MODEL_ID,
    ReferenceError,
    WORKFLOW_KEY,
    WORKFLOW_VERSION,
    resolve_strength,
)

PREFERRED_LOADER = "LTXICLoRALoaderModelOnly"
PREFERRED_GUIDE = "LTXAddVideoICLoRAGuide"
ALT_LOADER = "LoraLoaderModelOnly"
ALT_PARAMS = "GetICLoRAParameters"
ALT_GUIDE = "LTXVAddGuide"

STRATEGY_LTXVIDEO = "ltxvideo"
STRATEGY_CORE_GUIDE = "core_guide"


def probe_ic_lora_nodes(object_info: dict[str, Any] | None) -> dict[str, Any]:
    info = object_info or {}
    names = set(info.keys())
    available = {
        name: name in names
        for name in (
            PREFERRED_LOADER,
            PREFERRED_GUIDE,
            ALT_LOADER,
            ALT_PARAMS,
            ALT_GUIDE,
            "ImagePrepForICLora",
            "LoadImage",
            "VHS_LoadVideo",
        )
    }
    if PREFERRED_LOADER in names and PREFERRED_GUIDE in names:
        return {
            "strategy": STRATEGY_LTXVIDEO,
            "loader": PREFERRED_LOADER,
            "guide": PREFERRED_GUIDE,
            "params": None,
            "available": True,
            "available_nodes": available,
            "nodes": [PREFERRED_LOADER, PREFERRED_GUIDE, "LoadImage"],
        }
    if ALT_LOADER in names and ALT_PARAMS in names and ALT_GUIDE in names:
        return {
            "strategy": STRATEGY_CORE_GUIDE,
            "loader": ALT_LOADER,
            "guide": ALT_GUIDE,
            "params": ALT_PARAMS,
            "available": True,
            "available_nodes": available,
            "nodes": [ALT_LOADER, ALT_PARAMS, ALT_GUIDE, "LoadImage"],
        }
    return {
        "strategy": None,
        "loader": None,
        "guide": None,
        "params": None,
        "available": False,
        "available_nodes": available,
        "nodes": [],
        "missing": [
            n
            for n in (PREFERRED_LOADER, PREFERRED_GUIDE, ALT_LOADER, ALT_PARAMS, ALT_GUIDE)
            if n not in names
        ],
    }


def compile_reference_prompt(
    *,
    sheet_description: str = "",
    action_prompt: str = "",
    panels: list[dict[str, Any]] | None = None,
    reference_prompt: str = "",
    source_labels: list[str] | None = None,
) -> str:
    lines: list[str] = []
    if panels:
        for panel in panels:
            role = panel.get("role") or "other"
            subject = panel.get("subject_name") or panel.get("label") or role
            lines.append(f"- {subject} ({role})")
    desc = (reference_prompt or sheet_description or "").strip()
    if not desc and lines:
        desc = "\n".join(lines)
    if not desc and source_labels:
        desc = ", ".join(str(x) for x in source_labels if x)
    action = (action_prompt or "").strip()
    return (
        f"Reference sheet: {desc or 'composite visual ingredients'}\n"
        f"Generated video: {action or 'cinematic shot using the reference sheet subjects'}"
    )


def sanitize_workflow_debug(workflow: dict[str, Any]) -> dict[str, Any]:
    """Strip absolute local paths / tokens from a debug dump."""
    cleaned = copy.deepcopy(workflow)

    def scrub(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: scrub(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [scrub(v) for v in obj]
        if isinstance(obj, str):
            if re.match(r"^[A-Za-z]:\\", obj) or obj.startswith("/home/") or obj.startswith("/Users/"):
                return obj.replace("\\", "/").split("/")[-1]
            if re.search(r"(hf_|HF_)[A-Za-z0-9]+", obj) or "Bearer " in obj:
                return "<redacted>"
            return obj
        return obj

    return scrub(cleaned)


# Back-compat alias
sanitize_workflow = sanitize_workflow_debug


def wants_ingredients_ic_lora(
    params: dict[str, Any] | None = None,
    director_json: dict[str, Any] | str | None = None,
) -> bool:
    """True when job/scene opts into Ingredients IC-LoRA (disabled → normal LTX path)."""
    params = params or {}
    if params.get("ingredients_ic_lora") is False:
        return False
    method = str(params.get("reference_method") or params.get("ic_lora_method") or "").strip().lower()
    if method in ("none", "disabled"):
        return False
    if method in ("ingredients_ic_lora", "ic_lora_ingredients", "ingredients"):
        return True
    if params.get("ingredients_ic_lora") is True:
        return True

    doc = director_json
    if isinstance(doc, str) and doc.strip():
        try:
            doc = json.loads(doc)
        except Exception:
            doc = None
    if isinstance(doc, dict):
        if str(doc.get("reference_method") or "").strip().lower() == "ingredients_ic_lora":
            return True
        ref = doc.get("reference") or doc.get("ic_lora") or {}
        if isinstance(ref, dict):
            m = str(ref.get("method") or ref.get("reference_method") or "").strip().lower()
            if m in ("ingredients_ic_lora", "ic_lora_ingredients", "ingredients"):
                return True
            if ref.get("enabled") is True and ref.get("model_id") == INGREDIENTS_MODEL_ID:
                return True
    return False


def compile_ingredients_workflow(
    *,
    object_info: dict[str, Any] | None,
    checkpoint: str,
    width: int,
    height: int,
    length: int,
    fps: int,
    seed: int,
    negative: str = "",
    # Preferred queue_worker kwargs
    positive: str | None = None,
    reference_image: str | None = None,
    reference_video: str | None = None,
    lora_name: str | None = None,
    strength_preset: str | None = "balanced",
    strength: float | None = None,
    steps: int = 8,
    cfg: float = 1.0,
    filename_prefix: str = "studio/ltx_ingredients",
    reference_prompt: str = "",
    source_labels: list[str] | None = None,
    # Sibling / alternate kwargs
    positive_action: str | None = None,
    reference_image_name: str | None = None,
    strength_value: float | None = None,
    sheet_description: str = "",
    panels: list[dict[str, Any]] | None = None,
    configured_model_path: str | None = None,
    skip_model_check: bool = False,
    text_encoder: str | None = None,
) -> dict[str, Any]:
    probe = probe_ic_lora_nodes(object_info)
    if not probe.get("available") or not probe.get("strategy"):
        raise ReferenceError(
            "ic_lora_nodes_missing",
            "Required ComfyUI IC-LoRA nodes are missing for Ingredients reference generation.",
            {"available": probe.get("available_nodes"), "missing": probe.get("missing")},
        )

    action = (positive if positive is not None else positive_action) or ""
    image_name = reference_image or reference_image_name or ""
    strength_in = strength if strength is not None else strength_value
    if not image_name:
        raise ReferenceError("reference_sheet_missing", "Reference sheet image was not uploaded to ComfyUI.")

    resolved_lora = lora_name
    if not resolved_lora:
        if not skip_model_check:
            status = ingredients_status(configured_model_path)
            if status.get("status") == "authorization_required":
                raise ReferenceError(
                    "ic_lora_authorization_required",
                    status.get("message") or "Authorization required",
                )
            if status.get("status") != "ready":
                raise ReferenceError(
                    status.get("issue_code") or "ic_lora_model_missing",
                    status.get("message") or "Ingredients IC-LoRA model is not installed.",
                )
            found = find_ingredients_file(configured_model_path)
            if not found:
                raise ReferenceError("ic_lora_model_missing", "Ingredients IC-LoRA file not found on disk.")
            resolved_lora = found.name
        else:
            resolved_lora = INGREDIENTS_FILENAME

    preset, strength_f = resolve_strength(strength_preset, strength_in)
    # LTXAddVideoICLoRAGuide clamps strength to 1.0; keep full value on loader / alternate guide
    guide_strength_ltx = min(1.0, float(strength_f))

    prompt = compile_reference_prompt(
        sheet_description=sheet_description,
        action_prompt=action,
        panels=panels,
        reference_prompt=reference_prompt,
        source_labels=source_labels,
    )
    negative = negative or "worst quality, inconsistent motion, blurry, jittery, distorted"

    n_ckpt, n_clip, n_load, n_pos, n_neg = "1", "1b", "2", "3", "4"
    n_empty, n_lora, n_params, n_guide = "5", "6", "7", "8"
    n_noise, n_samp, n_sched = "9", "10", "11"
    n_guider, n_custom, n_dec = "12", "13", "14"
    n_vid, n_save = "15", "16"
    n_vhs = "17"

    # LTX 2.3 distilled checkpoints expose CLIP=None via CheckpointLoaderSimple;
    # text encoding must come from LTXAVTextEncoderLoader (same as ltx.simple_i2v).
    te_name = text_encoder or "gemma_3_12B_it_fp4_mixed.safetensors"
    wf: dict[str, Any] = {
        n_ckpt: {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        n_clip: {
            "class_type": "LTXAVTextEncoderLoader",
            "inputs": {
                "text_encoder": te_name,
                "ckpt_name": checkpoint,
                "device": "default",
            },
        },
        n_pos: {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": [n_clip, 0]},
        },
        n_neg: {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": [n_clip, 0]},
        },
        n_empty: {
            "class_type": "EmptyLTXVLatentVideo",
            "inputs": {
                "width": width,
                "height": height,
                "length": max(9, int(length)),
                "batch_size": 1,
            },
        },
        n_load: {
            "class_type": "LoadImage",
            "inputs": {"image": image_name},
        },
    }

    guide_image: Any = [n_load, 0]
    if reference_video and probe.get("available_nodes", {}).get("VHS_LoadVideo"):
        wf[n_vhs] = {
            "class_type": "VHS_LoadVideo",
            "inputs": {
                "video": reference_video,
                "force_rate": float(fps),
                "custom_width": width,
                "custom_height": height,
                "frame_load_cap": 0,
                "skip_first_frames": 0,
                "select_every_nth": 1,
            },
        }
        guide_image = [n_vhs, 0]

    strategy = probe["strategy"]
    if strategy == STRATEGY_LTXVIDEO:
        wf[n_lora] = {
            "class_type": PREFERRED_LOADER,
            "inputs": {
                "model": [n_ckpt, 0],
                "lora_name": resolved_lora,
                "strength_model": float(strength_f),
            },
        }
        wf[n_guide] = {
            "class_type": PREFERRED_GUIDE,
            "inputs": {
                "positive": [n_pos, 0],
                "negative": [n_neg, 0],
                "vae": [n_ckpt, 2],
                "latent": [n_empty, 0],
                "image": guide_image,
                "frame_idx": 0,
                "strength": guide_strength_ltx,
                "latent_downscale_factor": [n_lora, 1],
                "crop": "disabled",
                "use_tiled_encode": False,
                "tile_size": 256,
                "tile_overlap": 64,
            },
        }
        model_out: Any = [n_lora, 0]
    else:
        wf[n_lora] = {
            "class_type": ALT_LOADER,
            "inputs": {
                "model": [n_ckpt, 0],
                "lora_name": resolved_lora,
                "strength_model": float(strength_f),
            },
        }
        wf[n_params] = {
            "class_type": ALT_PARAMS,
            "inputs": {"iclora_model": [n_lora, 0]},
        }
        wf[n_guide] = {
            "class_type": ALT_GUIDE,
            "inputs": {
                "positive": [n_pos, 0],
                "negative": [n_neg, 0],
                "vae": [n_ckpt, 2],
                "latent": [n_empty, 0],
                "image": guide_image,
                "frame_idx": 0,
                "strength": float(strength_f),
                "iclora_parameters": [n_params, 0],
            },
        }
        model_out = [n_lora, 0]

    wf[n_noise] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed if seed >= 0 else 0}}
    wf[n_samp] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
    wf[n_sched] = {
        "class_type": "BasicScheduler",
        "inputs": {"model": model_out, "scheduler": "normal", "steps": steps, "denoise": 1.0},
    }
    wf[n_guider] = {
        "class_type": "CFGGuider",
        "inputs": {
            "model": model_out,
            "positive": [n_guide, 0],
            "negative": [n_guide, 1],
            "cfg": cfg,
        },
    }
    wf[n_custom] = {
        "class_type": "SamplerCustomAdvanced",
        "inputs": {
            "noise": [n_noise, 0],
            "guider": [n_guider, 0],
            "sampler": [n_samp, 0],
            "sigmas": [n_sched, 0],
            "latent_image": [n_guide, 2],
        },
    }
    wf[n_dec] = {"class_type": "VAEDecode", "inputs": {"samples": [n_custom, 0], "vae": [n_ckpt, 2]}}
    wf[n_vid] = {"class_type": "CreateVideo", "inputs": {"images": [n_dec, 0], "fps": float(fps)}}
    wf[n_save] = {
        "class_type": "SaveVideo",
        "inputs": {
            "video": [n_vid, 0],
            "filename_prefix": filename_prefix,
            "format": "mp4",
            "codec": "h264",
        },
    }

    provenance = {
        "ic_lora_model_id": INGREDIENTS_MODEL_ID,
        "ic_lora_model_version": "0.9",
        "ic_lora_filename": resolved_lora,
        "workflow_id": WORKFLOW_KEY,
        "workflow_key": WORKFLOW_KEY,
        "workflow_version": WORKFLOW_VERSION,
        "strategy": strategy,
        "strength_preset": preset,
        "strength": strength_f,
        "strength_value": strength_f,
        "reference_image": image_name,
        "reference_video": reference_video,
        "checkpoint": checkpoint,
        "compiled_prompt": prompt,
        "width": width,
        "height": height,
        "length": max(9, int(length)),
        "fps": fps,
        "seed": seed,
        "steps": steps,
        "cfg": cfg,
    }
    return {
        "workflow": wf,
        "strategy": strategy,
        "sanitized_debug": sanitize_workflow_debug(wf),
        "provenance": provenance,
        "prompt": prompt,
        "lora_name": resolved_lora,
        "strength": strength_f,
        "strength_preset": preset,
        "workflow_key": WORKFLOW_KEY,
        "workflow_version": WORKFLOW_VERSION,
    }
