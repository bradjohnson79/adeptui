"""SenseNova U1.5 official Comfy builders (v3 nodes, not KSampler).

Graphs emit Adept API-prompt dicts for:
  SenseNovaU1LocalLoader
  SenseNovaU1LocalTextToImage
  SenseNovaU1LocalImageEdit
  LoadImage / SaveImage
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

SENSENOVA_FAMILY = "sensenova"
SENSENOVA_DEFAULT_MODEL_ROOT = r"D:\01_Models\SenseNova\U1.5-8B-MoT"
SENSENOVA_DEFAULT_HF_ID = "sensenova/SenseNova-U1.5-8B-MoT"
SENSENOVA_DEVICE = "cuda"
SENSENOVA_DTYPE = "bfloat16"
# Official default is "full" (entire checkpoint on GPU). U1.5-8B-MoT is
# ~47 GB on disk and does not fit a 32 GB card, and from_pretrained in
# "full" exhausted host RAM (~65 GB) before any CUDA alloc. "fast" is the
# official single-GPU offload mode (still CUDA, not CPU).
SENSENOVA_VRAM_MODE = "fast"
SENSENOVA_DEFAULT_STEPS = 50
SENSENOVA_SMOKE_STEPS = 2
SENSENOVA_CFG = 4.0
SENSENOVA_SHIFT = 3.0

# Official T2I combo values from ComfyUI-SenseNova-U1 local_pipeline.py
T2I_RESOLUTION_BY_RATIO: dict[str, str] = {
    "1:1": "2048x2048|1:1",
    "16:9": "2720x1536|16:9",
    "9:16": "1536x2720|9:16",
    "3:2": "2496x1664|3:2",
    "2:3": "1664x2496|2:3",
    "4:3": "2368x1760|4:3",
    "3:4": "1760x2368|3:4",
    "2:1": "2880x1440|2:1",
    "1:2": "1440x2880|1:2",
}

CRS_RESOLUTION = T2I_RESOLUTION_BY_RATIO["16:9"]
ERS_WIDTH = 2720
ERS_HEIGHT = 1536

REQUIRED_NODES: tuple[str, ...] = (
    "SenseNovaU1LocalLoader",
    "SenseNovaU1LocalTextToImage",
    "SenseNovaU1LocalImageEdit",
    "SaveImage",
)

REQUIRED_CONFIG_MARKERS: tuple[str, ...] = (
    "config.json",
    "configuration.json",
    "model_index.json",
)

# Official Hub layout for sensenova/SenseNova-U1.5-8B-MoT (23 files, ~46.78 GB).
# Partial shards must never report Ready — that is a false default / fake-success risk.
EXPECTED_WEIGHT_FILES: dict[str, int] = {
    "config.json": 1_000,
    "model.safetensors.index.json": 1_000,
    "model-00001-of-00013.safetensors": 105_413_672,
    "model-00002-of-00013.safetensors": 162_434_760,
    "model-00003-of-00013.safetensors": 7_120_064_448,
    "model-00004-of-00013.safetensors": 4_630_728_192,
    "model-00005-of-00013.safetensors": 4_630_728_248,
    "model-00006-of-00013.safetensors": 4_630_728_296,
    "model-00007-of-00013.safetensors": 4_630_728_296,
    "model-00008-of-00013.safetensors": 4_630_728_296,
    "model-00009-of-00013.safetensors": 4_630_728_296,
    "model-00010-of-00013.safetensors": 4_630_728_296,
    "model-00011-of-00013.safetensors": 4_630_728_296,
    "model-00012-of-00013.safetensors": 4_244_835_448,
    "model-00013-of-00013.safetensors": 1_543_578_408,
    "tokenizer_config.json": 1_000,
    "special_tokens_map.json": 1_000,
    "vocab.json": 1_000,
}


def resolve_model_path(explicit: str | None = None) -> str:
    raw = (explicit or "").strip()
    if raw:
        return raw
    root = Path(SENSENOVA_DEFAULT_MODEL_ROOT)
    if root.is_dir() and any((root / name).is_file() for name in REQUIRED_CONFIG_MARKERS):
        return str(root)
    if root.is_dir() and any(root.glob("*.safetensors")):
        return str(root)
    return SENSENOVA_DEFAULT_HF_ID


SENSENOVA_ALIASES = frozenset(
    {"sensenova", "sensenova_u15", "sensenova-u15", "sensenova-u15-local", "sensenova_u1"}
)


def is_sensenova_family(value: str | None) -> bool:
    key = str(value or "").strip().lower()
    if key in SENSENOVA_ALIASES:
        return True
    return key.startswith("sensenova")


def inspect_weights(root: Path | None = None) -> dict[str, Any]:
    path = Path(root or SENSENOVA_DEFAULT_MODEL_ROOT)
    missing: list[str] = []
    if not path.is_dir():
        return {
            "installed": False,
            "root": str(path),
            "missing": ["root"],
            "runtimeReady": False,
            "completeShards": 0,
            "expectedShards": 13,
        }
    has_config = any((path / name).is_file() for name in REQUIRED_CONFIG_MARKERS)
    if not has_config:
        missing.append("config.json")
    present_shards = 0
    for name, min_bytes in EXPECTED_WEIGHT_FILES.items():
        target = path / name
        if not target.is_file():
            missing.append(name)
            continue
        size = target.stat().st_size
        if size < min_bytes:
            missing.append(f"{name}:truncated:{size}")
            continue
        if name.endswith(".safetensors") and name.startswith("model-"):
            present_shards += 1
    complete = not missing
    return {
        "installed": complete,
        "root": str(path),
        "missing": missing,
        # Disk completeness is not GPU/runtime readiness. SenseNova's loader
        # can occupy host RAM without ever placing tensors on CUDA.
        "weightsComplete": complete,
        "runtimeReady": False,
        "modelPath": str(path) if complete else "",
        "completeShards": present_shards,
        "expectedShards": 13,
    }


def resolution_option(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return CRS_RESOLUTION
    ratio = width / float(height)
    if abs(ratio - 1.0) < 0.08:
        return T2I_RESOLUTION_BY_RATIO["1:1"]
    if abs(ratio - 16 / 9) < 0.12:
        return T2I_RESOLUTION_BY_RATIO["16:9"]
    if abs(ratio - 9 / 16) < 0.12:
        return T2I_RESOLUTION_BY_RATIO["9:16"]
    if abs(ratio - 3 / 2) < 0.12:
        return T2I_RESOLUTION_BY_RATIO["3:2"]
    if abs(ratio - 2 / 3) < 0.12:
        return T2I_RESOLUTION_BY_RATIO["2:3"]
    if ratio >= 1.7:
        return T2I_RESOLUTION_BY_RATIO["16:9"]
    return CRS_RESOLUTION


def _loader_node(
    *,
    model_path: str,
    device: str = SENSENOVA_DEVICE,
    dtype: str = SENSENOVA_DTYPE,
    vram_mode: str = SENSENOVA_VRAM_MODE,
) -> dict[str, Any]:
    return {
        "class_type": "SenseNovaU1LocalLoader",
        "inputs": {
            "model_path": model_path,
            "sensenova_u1_src": "",
            "device": device,
            "dtype": dtype,
            "attn_backend": "auto",
            "device_map": "none",
            "max_memory": "",
            "vram_mode": vram_mode,
            "gguf_checkpoint": "",
        },
    }


def _save_node(images: list[Any], filename_prefix: str) -> dict[str, Any]:
    return {
        "class_type": "SaveImage",
        "inputs": {
            "images": images,
            "filename_prefix": filename_prefix or "studio/sensenova",
        },
    }


def build_sensenova_txt2img_workflow(
    *,
    prompt: str,
    width: int = 2720,
    height: int = 1536,
    seed: int = 42,
    steps: int = SENSENOVA_DEFAULT_STEPS,
    cfg: float = SENSENOVA_CFG,
    filename_prefix: str = "studio/sensenova_t2i",
    model_path: str | None = None,
    negative: str = "",
    vram_mode: str = SENSENOVA_VRAM_MODE,
    **_unused: Any,
) -> dict[str, Any]:
    text = prompt.strip()
    if negative.strip():
        text = f"{text}\nAvoid: {negative.strip()}".strip()
    return {
        "1": _loader_node(model_path=resolve_model_path(model_path), vram_mode=vram_mode),
        "2": {
            "class_type": "SenseNovaU1LocalTextToImage",
            "inputs": {
                "u1_model": ["1", 0],
                "prompt": text,
                "resolution": resolution_option(width, height),
                "cfg_scale": float(cfg),
                "cfg_norm": "none",
                "timestep_shift": SENSENOVA_SHIFT,
                "cfg_interval_start": 0.0,
                "cfg_interval_end": 1.0,
                "num_steps": max(1, int(steps)),
                "batch_size": 1,
                "seed": int(seed) if seed >= 0 else 42,
                "think_mode": False,
            },
        },
        "3": _save_node(["2", 0], filename_prefix),
    }


def build_sensenova_edit_workflow(
    *,
    prompt: str,
    image_name: str,
    width: int = ERS_WIDTH,
    height: int = ERS_HEIGHT,
    seed: int = 42,
    steps: int = SENSENOVA_DEFAULT_STEPS,
    cfg: float = SENSENOVA_CFG,
    filename_prefix: str = "studio/sensenova_edit",
    model_path: str | None = None,
    auto_size: bool = False,
    negative: str = "",
    **_unused: Any,
) -> dict[str, Any]:
    if not str(image_name or "").strip():
        raise RuntimeError("SenseNova edit/reference requires a source image")
    text = prompt.strip()
    if negative.strip():
        text = f"{text}\nAvoid: {negative.strip()}".strip()
    return {
        "1": _loader_node(model_path=resolve_model_path(model_path)),
        "2": {
            "class_type": "LoadImage",
            "inputs": {"image": image_name},
        },
        "3": {
            "class_type": "SenseNovaU1LocalImageEdit",
            "inputs": {
                "u1_model": ["1", 0],
                "image": ["2", 0],
                "prompt": text,
                "auto_size": bool(auto_size),
                "width": int(width or ERS_WIDTH),
                "height": int(height or ERS_HEIGHT),
                "target_megapixels": 4.194304,
                "cfg_scale": float(cfg),
                "img_cfg_scale": 1.0,
                "cfg_norm": "none",
                "timestep_shift": SENSENOVA_SHIFT,
                "cfg_interval_start": 0.0,
                "cfg_interval_end": 1.0,
                "num_steps": max(1, int(steps)),
                "batch_size": 1,
                "seed": int(seed) if seed >= 0 else 42,
                "think_mode": False,
            },
        },
        "4": _save_node(["3", 0], filename_prefix),
    }


def build_sensenova_crs_workflow(
    *,
    prompt: str,
    image_name: str | None = None,
    width: int = 2720,
    height: int = 1536,
    seed: int = 42,
    steps: int = SENSENOVA_DEFAULT_STEPS,
    cfg: float = SENSENOVA_CFG,
    filename_prefix: str = "studio/sensenova_crs",
    model_path: str | None = None,
    negative: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    ref = str(image_name or kwargs.get("reference_image") or kwargs.get("source_image") or "").strip()
    if ref:
        return build_sensenova_edit_workflow(
            prompt=prompt,
            image_name=ref,
            width=width,
            height=height,
            seed=seed,
            steps=steps,
            cfg=cfg,
            filename_prefix=filename_prefix,
            model_path=model_path,
            auto_size=False,
            negative=negative,
        )
    return build_sensenova_txt2img_workflow(
        prompt=prompt,
        width=width,
        height=height,
        seed=seed,
        steps=steps,
        cfg=cfg,
        filename_prefix=filename_prefix,
        model_path=model_path,
        negative=negative,
    )


def build_sensenova_ers_workflow(
    *,
    prompt: str,
    image_name: str,
    width: int = ERS_WIDTH,
    height: int = ERS_HEIGHT,
    seed: int = 42,
    steps: int = SENSENOVA_DEFAULT_STEPS,
    cfg: float = SENSENOVA_CFG,
    filename_prefix: str = "studio/sensenova_ers",
    model_path: str | None = None,
    negative: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    return build_sensenova_edit_workflow(
        prompt=prompt,
        image_name=image_name or str(kwargs.get("reference_image") or kwargs.get("source_image") or ""),
        width=width,
        height=height,
        seed=seed,
        steps=steps,
        cfg=cfg,
        filename_prefix=filename_prefix,
        model_path=model_path,
        auto_size=False,
        negative=negative,
    )


def discover_sensenova_u15() -> dict[str, Any]:
    """Honest runtime probe: weights on D: plus official node types when Comfy is up."""
    weights = inspect_weights()
    nodes_ok = False
    missing_nodes: list[str] = []
    try:
        from ..source_manager.install_jobs.requirements import _live_node_types

        live = _live_node_types() or set()
        missing_nodes = [name for name in REQUIRED_NODES if name != "SaveImage" and name not in live]
        nodes_ok = not missing_nodes
    except Exception:
        nodes_ok = False
        missing_nodes = list(REQUIRED_NODES[:3])
    ready = False
    return {
        "installed": bool(weights.get("installed")),
        "nodesReady": nodes_ok,
        "weightsComplete": bool(weights.get("weightsComplete") or weights.get("installed")),
        "runtimeReady": ready,
        "root": weights.get("root"),
        "modelPath": weights.get("modelPath") or resolve_model_path(),
        "missing": list(weights.get("missing") or []) + ([f"node:{n}" for n in missing_nodes] if missing_nodes else []),
        "family": SENSENOVA_FAMILY,
        "label": "SenseNova U1.5" if ready else "SenseNova U1.5 — Not Ready",
    }


def build_sensenova_workflow(
    kind: Literal["txt2img", "edit", "reference", "crs", "ers"],
    **kwargs: Any,
) -> dict[str, Any]:
    if kind in {"edit", "reference"}:
        return build_sensenova_edit_workflow(**kwargs)
    if kind == "ers":
        return build_sensenova_ers_workflow(**kwargs)
    if kind == "crs":
        return build_sensenova_crs_workflow(**kwargs)
    return build_sensenova_txt2img_workflow(**kwargs)
