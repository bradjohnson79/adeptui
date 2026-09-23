"""MiniMax H3 Route A Runtime Adapter — isolated ComfyUI :8192 only.

MiniMax H3 CREATE (T2V / 1F I2V / 3F assembly) runs on the isolated Route A
:8192 runtime (Master Program Phase 29 — separate from production Comfy
:8188). The certified SageAttention accelerator (comfyui-speed-minimaxH3)
must be installed on this :8192 instance. See
MINIMAX_H3_ACCELERATION_AUTHORITY.md.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .private_access import model_root, runtime_url
from .store import project_dir, write_json

UNET = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
CLIP = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"

REQUIRED_NODES = (
    "UNETLoader",
    "CLIPLoader",
    "VAELoader",
    "MiniMaxH3ImageToVideo",
    "VAEDecodeAudio",
    "CreateVideo",
    "SaveVideo",
)

REQUIRED_NODES_I2V = REQUIRED_NODES + ("LoadImage",)
REQUIRED_NODES_FLF = REQUIRED_NODES_I2V + ("MiniMaxH3AddGuide",)

LOAD_IMAGE_NODE_ID = "15"
LAST_LOAD_IMAGE_NODE_ID = "16"
MIDDLE_LOAD_IMAGE_NODE_ID = "17"
ADD_GUIDE_NODE_ID = "18"
I2V_CONDITIONING_NODE_ID = "5"

FORBIDDEN_SHARD_MARKERS = (
    "model-00001-of-",
    "FL2VA/transformer",
    "FL2VA\\transformer",
    "MiniMaxH3Pipeline",
    "from_pretrained",
)

# Proven Experimental Private Profile (Route A Gate C).
# `length` is frame count. CreateVideo encodes at EXPERIMENTAL_FPS.
# Honest generated duration is frames/fps (~0.21s). Not 5s. Not 15s.
EXPERIMENTAL_WIDTH = 480
EXPERIMENTAL_HEIGHT = 256
EXPERIMENTAL_LENGTH = 5
EXPERIMENTAL_FPS = 24.0
# Golden default-Comfy H3 uses 20. Adept's 4-step experimental default was the
# shared 1F+T2V native-audio corruption: raw VAEDecodeAudio FLAC at 4 steps is
# already clipped/hot (peak ~0.99, floor ~-23 dB); the same graph at 20 steps is
# clean (peak ~0.009, DC ~0, floor ~-57 dB) before CreateVideo. See
# docs/release-gate/minimax-h3/H3_SHARED_NATIVE_AUDIO_ROOT_CAUSE.md.
EXPERIMENTAL_STEPS = 20
EXPERIMENTAL_DURATION_SEC = EXPERIMENTAL_LENGTH / EXPERIMENTAL_FPS
# Legacy EasyCache residual cache was REMOVED — it caused the same severe
# echo/ghost/ripple visual regression proven in the live benchmark. The ONE
# shared certified accelerator (SageAttention via MiniMaxH3SpeedCache, cache off)
# is injected by acceleration.apply_certified_accelerator. See
# MINIMAX_H3_ACCELERATION_AUTHORITY.md.

# MiniMax H3 DiT pack uses spatial patch 2 on latents that are already /16.
# Pixel W/H must be multiples of 32 so latent H/W are even (else SamplerCustomAdvanced
# reshape fails, e.g. 1280x720 -> latent 80x45 -> target [...,22,2,40,2] vs 86400 elems).
H3_CANVAS_MULTIPLE = 32


def assert_h3_legal_canvas(width: int, height: int) -> tuple[int, int]:
    """Fail closed on illegal canvas. Never silent-snap creator resolution/aspect."""
    w = int(width)
    h = int(height)
    if w <= 0 or h <= 0:
        raise ValueError(
            f"MiniMax H3 width/height must be positive (got {w}x{h})."
        )
    if w % H3_CANVAS_MULTIPLE != 0 or h % H3_CANVAS_MULTIPLE != 0:
        # Suggest nearest legal below/above without applying them.
        w_lo = max(H3_CANVAS_MULTIPLE, (w // H3_CANVAS_MULTIPLE) * H3_CANVAS_MULTIPLE)
        h_lo = max(H3_CANVAS_MULTIPLE, (h // H3_CANVAS_MULTIPLE) * H3_CANVAS_MULTIPLE)
        w_hi = w_lo if w % H3_CANVAS_MULTIPLE == 0 else w_lo + H3_CANVAS_MULTIPLE
        h_hi = h_lo if h % H3_CANVAS_MULTIPLE == 0 else h_lo + H3_CANVAS_MULTIPLE
        raise ValueError(
            f"MiniMax H3 requires width and height to be multiples of {H3_CANVAS_MULTIPLE} "
            f"(VAE /16 then DiT patch 2). Got {w}x{h} - latent would be "
            f"{w // 16}x{h // 16}, which cannot pack. "
            f"Legal near examples: {w_lo}x{h_lo} or {w_hi}x{h_hi} "
            f"(e.g. 1280x704). Change project/canvas resolution; Adept will not silent-snap."
        )
    return w, h


def measured_or_experimental_duration(media: dict[str, Any] | None) -> float:
    """Use probed media duration when present. Never invent 5s or 15s."""
    if isinstance(media, dict):
        raw = media.get("durationSeconds")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0:
            return value
    return EXPERIMENTAL_DURATION_SEC


def route_a_client_id(job_id: str, *, mode: str = "text-to-video") -> str:
    """WebSocket clientId must match the /prompt client_id exactly.

    I2V submit uses ``adept-h3-i2v-{id}``. T2V uses ``adept-h3-{id}``.
    A preview tap that omits ``i2v-`` receives zero frames.
    """
    token = str(job_id or "").strip()
    prefix = token[:8] if token else "unknown"
    if str(mode or "").strip().lower() in {
        "one-frame",
        "i2v",
        "i2va",
        "first-last",
        "three-frame",
        "flf2va",
        "flf",
    }:
        return f"adept-h3-i2v-{prefix}"
    return f"adept-h3-{prefix}"


@dataclass
class RouteAJobState:
    job_id: str
    project_id: str
    plan_id: str
    prompt: str
    seed: int
    prompt_id: str | None = None
    client_id: str | None = None
    status: str = "queued"
    stage: str = "Checking MiniMax H3"
    error_code: str | None = None
    error_message: str | None = None
    output_path: str | None = None
    media: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    cancelled: bool = False
    mode: str = "text-to-video"  # text-to-video | one-frame (I2V)
    submitted_graph: dict[str, Any] = field(default_factory=dict)
    comfy_image_name: str | None = None
    start_image_path: str | None = None
    start_image_sha256: str | None = None


def comfy_root_under_model_root() -> Path:
    return Path(model_root()) / "Video" / "MiniMax-H3" / "ComfyUI"


def required_checkpoint_paths() -> dict[str, Path]:
    root = comfy_root_under_model_root()
    return {
        "transformer": root / "diffusion_models" / UNET,
        "encoder": root / "text_encoders" / CLIP,
        "video_vae": root / "vae" / VIDEO_VAE,
        "audio_vae": root / "vae" / AUDIO_VAE,
    }


def _h3_frame_count(duration_sec: float | None, fps: float) -> int:
    """Creator duration is authoritative. Snap UP to the model's 17k+5 grid so we
    never silently shorten. Trained range is ~124-362 frames (~5-15s at 24fps)."""
    if duration_sec is None or duration_sec <= 0:
        return EXPERIMENTAL_LENGTH
    raw = max(5, int(round(float(duration_sec) * fps)))
    # Snap up to the next 17k+5 grid point.
    snapped = ((raw - 5 + 16) // 17) * 17 + 5
    return max(5, min(snapped, 3600))


def _h3_legal_duration(duration_sec: float | None, fps: float | None) -> int:
    """Resolve a requested duration to legal MiniMax H3 1F frames (17k+5).

    Snaps UP to the next legal grid point at or above the request. If the
    requested duration already maps to a legal count, no extra frames are
    added. Raises only for genuine incompatibilities (negative, zero, or
    above the 3600-frame max).

    The caller is responsible for trimming the generated excess back to the
    requested duration.
    """
    fps_val = float(fps) if fps and fps > 0 else EXPERIMENTAL_FPS
    if duration_sec is None or float(duration_sec) <= 0:
        raise ValueError("Duration must be positive for MiniMax H3 1F.")
    raw = max(5, int(round(float(duration_sec) * fps_val)))
    # Snap up to the next 17k+5 grid point.
    snapped = ((max(5, raw) - 5 + 16) // 17) * 17 + 5
    if snapped > 3600:
        raise ValueError(
            f"MiniMax H3 1F max is 3600 frames. Requested {float(duration_sec)}s → {raw} frames "
            f"exceeds the grid."
        )
    return snapped


def build_t2va_graph(
    prompt: str,
    *,
    seed: int,
    filename_prefix: str,
    duration_sec: float | None = None,
    width: int | None = None,
    height: int | None = None,
    fps: float | None = None,
    steps: int | None = None,
) -> dict[str, Any]:
    from ..video_runtime.seed_resolve import comfy_noise_seed

    # Defense in depth: never emit negative noise_seed to RandomNoise (min 0).
    seed = comfy_noise_seed(seed)
    fps_val = float(fps) if fps and fps > 0 else EXPERIMENTAL_FPS
    length = _h3_frame_count(duration_sec, fps_val)
    canvas_w = int(width) if width else EXPERIMENTAL_WIDTH
    canvas_h = int(height) if height else EXPERIMENTAL_HEIGHT
    canvas_w, canvas_h = assert_h3_legal_canvas(canvas_w, canvas_h)
    graph = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP, "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_VAE}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": AUDIO_VAE}},
        "5": {
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {
                "clip": ["2", 0],
                "vae": ["3", 0],
                "prompt": prompt,
                "width": canvas_w,
                "height": canvas_h,
                "length": length,
            },
        },
        "6": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "7": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "8": {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["1", 0],
                "scheduler": "simple",
                "steps": int(steps) if steps else EXPERIMENTAL_STEPS,
                "denoise": 1.0,
            },
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
        "13": {
            "class_type": "CreateVideo",
            "inputs": {"images": ["11", 0], "fps": fps_val, "audio": ["12", 0], "bit_depth": 8},
        },
        "14": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["13", 0],
                "filename_prefix": filename_prefix,
                "format": "auto",
                "codec": "auto",
                # ComfyUI 0.34.x SaveVideo dynamic-combo sub-input: required by
                # validate_workflow on :8188. Kept alongside format/codec so the
                # graph passes both validation and execution.
                "format.codec": "auto",
            },
        },
    }
    # Golden Workflow Convergence (Phase 5b CONCLUSIVE): the MiniMaxH3SpeedCache
    # accelerator corrupts H3 native audio in EVERY sage_attention mode (auto/enabled/
    # disabled all yield a ~-28 dB noise floor = static, vs golden -136.8 dB clean).
    # The corruption is inherent to inserting the SpeedCache node into the joint AV
    # model path. Per Quality > Speed law, the accelerator is DROPPED for H3 — the
    # graph is now the golden default (raw UNETLoader -> scheduler/guider). Do NOT
    # re-insert MiniMaxH3SpeedCache; it breaks audio. See
    # docs/release-gate/golden-h3/MINIMAX_H3_GOLDEN_CONVERGENCE.md.
    return graph


def default_add_guide_frame_idx(length: int) -> int:
    """Proven local default: mid-clip guide (length // 2)."""
    return max(0, int(length) // 2)


def build_i2va_graph(
    prompt: str,
    *,
    seed: int,
    filename_prefix: str,
    first_frame_comfy_name: str,
    last_frame_comfy_name: str | None = None,
    middle_frame_comfy_name: str | None = None,
    duration_sec: float | None = None,
    width: int | None = None,
    height: int | None = None,
    fps: float | None = None,
    steps: int | None = None,
    add_guide_frame_idx: int | None = None,
) -> dict[str, Any]:
    """Route A image-conditioned graph.

    - first only -> 1F I2V (existing)
    - first + last, empty middle -> local FLF (proof A); no AddGuide
    - first + middle + last -> AddGuide at mid length (proof B)
    Never duplicate first/last as a fake middle.
    """
    if not (first_frame_comfy_name or "").strip():
        raise ValueError("first_frame_comfy_name is required for MiniMax H3 I2V.")
    last_name = (last_frame_comfy_name or "").strip() or None
    middle_name = (middle_frame_comfy_name or "").strip() or None
    if middle_name and not last_name:
        raise ValueError(
            "Middle frame requires First and Last frames. "
            "Do not invent a last frame or fake a middle from first/last."
        )
    if middle_name and middle_name in {first_frame_comfy_name.strip(), last_name}:
        raise ValueError(
            "Middle frame must be a distinct still. "
            "Adept will not duplicate first/last as a fake middle."
        )
    graph = build_t2va_graph(
        prompt,
        seed=seed,
        filename_prefix=filename_prefix,
        duration_sec=duration_sec,
        width=width,
        height=height,
        fps=fps,
        steps=steps,
    )
    graph[LOAD_IMAGE_NODE_ID] = {
        "class_type": "LoadImage",
        "inputs": {"image": first_frame_comfy_name},
    }
    graph[I2V_CONDITIONING_NODE_ID]["inputs"]["first_frame"] = [LOAD_IMAGE_NODE_ID, 0]
    if last_name:
        graph[LAST_LOAD_IMAGE_NODE_ID] = {
            "class_type": "LoadImage",
            "inputs": {"image": last_name},
        }
        graph[I2V_CONDITIONING_NODE_ID]["inputs"]["last_frame"] = [LAST_LOAD_IMAGE_NODE_ID, 0]
    if middle_name:
        length = int(graph[I2V_CONDITIONING_NODE_ID]["inputs"]["length"])
        frame_idx = (
            int(add_guide_frame_idx)
            if add_guide_frame_idx is not None
            else default_add_guide_frame_idx(length)
        )
        graph[MIDDLE_LOAD_IMAGE_NODE_ID] = {
            "class_type": "LoadImage",
            "inputs": {"image": middle_name},
        }
        graph[ADD_GUIDE_NODE_ID] = {
            "class_type": "MiniMaxH3AddGuide",
            "inputs": {
                "positive": [I2V_CONDITIONING_NODE_ID, 0],
                "latent": [I2V_CONDITIONING_NODE_ID, 1],
                "frame_idx": frame_idx,
                "vae": ["3", 0],
                "image": [MIDDLE_LOAD_IMAGE_NODE_ID, 0],
            },
        }
        # Guider consumes AddGuide conditioning; sampler latent stays on I2V.
        graph["9"]["inputs"]["conditioning"] = [ADD_GUIDE_NODE_ID, 0]
    return graph



def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_i2va_graph_binding(graph: dict[str, Any], *, expected_comfy_name: str) -> None:
    """Fail closed if the submitted graph does not wire the start image."""
    load = graph.get(LOAD_IMAGE_NODE_ID) or {}
    if load.get("class_type") != "LoadImage":
        raise ValueError("Submitted MiniMax I2V graph is missing LoadImage.")
    bound = str((load.get("inputs") or {}).get("image") or "")
    if bound != expected_comfy_name:
        raise ValueError(
            f"LoadImage bound '{bound}' but expected uploaded name '{expected_comfy_name}'."
        )
    cond = graph.get(I2V_CONDITIONING_NODE_ID) or {}
    if cond.get("class_type") != "MiniMaxH3ImageToVideo":
        raise ValueError("Submitted graph missing MiniMaxH3ImageToVideo.")
    first = (cond.get("inputs") or {}).get("first_frame")
    if not isinstance(first, list) or len(first) < 1 or str(first[0]) != LOAD_IMAGE_NODE_ID:
        raise ValueError("MiniMaxH3ImageToVideo.first_frame must point to LoadImage.")


def assert_flf_graph_binding(
    graph: dict[str, Any],
    *,
    first_comfy_name: str,
    last_comfy_name: str,
    middle_comfy_name: str | None = None,
) -> None:
    """Fail closed for local first+last (± optional AddGuide middle)."""
    assert_i2va_graph_binding(graph, expected_comfy_name=first_comfy_name)
    cond = graph.get(I2V_CONDITIONING_NODE_ID) or {}
    last = (cond.get("inputs") or {}).get("last_frame")
    if not isinstance(last, list) or len(last) < 1 or str(last[0]) != LAST_LOAD_IMAGE_NODE_ID:
        raise ValueError("MiniMaxH3ImageToVideo.last_frame must point to last LoadImage.")
    last_load = graph.get(LAST_LOAD_IMAGE_NODE_ID) or {}
    if last_load.get("class_type") != "LoadImage":
        raise ValueError("Submitted FLF graph is missing last LoadImage.")
    if str((last_load.get("inputs") or {}).get("image") or "") != last_comfy_name:
        raise ValueError("Last LoadImage binding does not match uploaded last frame.")
    load_count = sum(
        1
        for node in graph.values()
        if isinstance(node, dict) and node.get("class_type") == "LoadImage"
    )
    guider_cond = ((graph.get("9") or {}).get("inputs") or {}).get("conditioning")
    middle = (middle_comfy_name or "").strip() or None
    if not middle:
        if ADD_GUIDE_NODE_ID in graph or any(
            isinstance(n, dict) and n.get("class_type") == "MiniMaxH3AddGuide"
            for n in graph.values()
        ):
            raise ValueError("Empty middle must omit MiniMaxH3AddGuide entirely.")
        if load_count != 2:
            raise ValueError(f"Empty-middle FLF must have exactly 2 LoadImage nodes (got {load_count}).")
        if not isinstance(guider_cond, list) or str(guider_cond[0]) != I2V_CONDITIONING_NODE_ID:
            raise ValueError("Empty-middle FLF guider must consume I2V conditioning.")
        return
    if ADD_GUIDE_NODE_ID not in graph:
        raise ValueError("Middle frame requires MiniMaxH3AddGuide.")
    guide = graph[ADD_GUIDE_NODE_ID]
    if guide.get("class_type") != "MiniMaxH3AddGuide":
        raise ValueError("Node 18 must be MiniMaxH3AddGuide.")
    g_in = guide.get("inputs") or {}
    img = g_in.get("image")
    if not isinstance(img, list) or str(img[0]) != MIDDLE_LOAD_IMAGE_NODE_ID:
        raise ValueError("AddGuide.image must point to middle LoadImage.")
    mid_load = graph.get(MIDDLE_LOAD_IMAGE_NODE_ID) or {}
    if str((mid_load.get("inputs") or {}).get("image") or "") != middle:
        raise ValueError("Middle LoadImage binding does not match uploaded middle frame.")
    if load_count != 3:
        raise ValueError(f"3-frame graph must have exactly 3 LoadImage nodes (got {load_count}).")
    if not isinstance(guider_cond, list) or str(guider_cond[0]) != ADD_GUIDE_NODE_ID:
        raise ValueError("3-frame guider must consume AddGuide conditioning.")
    latent = ((graph.get("10") or {}).get("inputs") or {}).get("latent_image")
    if not isinstance(latent, list) or str(latent[0]) != I2V_CONDITIONING_NODE_ID:
        raise ValueError("Sampler latent must stay on MiniMaxH3ImageToVideo (not AddGuide).")


class RouteARuntimeAdapter:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or runtime_url()).rstrip("/")
        self._session = httpx.Client(timeout=30.0)

    def health(self) -> dict[str, Any]:
        try:
            r = self._session.get(f"{self.base_url}/system_stats", timeout=15)
            r.raise_for_status()
            stats = r.json()
        except Exception as exc:
            return {
                "ok": False,
                "errorCode": "H3_RUNTIME_UNAVAILABLE",
                "message": "MiniMax H3 — Runtime Offline",
                "detail": repr(exc),
            }
        devices = stats.get("devices") or []
        gpu = None
        for d in devices:
            name = str(d.get("name") or "")
            if "cuda" in name.lower() or "nvidia" in name.lower():
                gpu = name
                break
        return {
            "ok": True,
            "message": "MiniMax H3 — Ready for Private Local Use" if gpu else "MiniMax H3 — Runtime Offline",
            "gpu": gpu,
            "comfyuiVersion": (stats.get("system") or {}).get("comfyui_version"),
            "pytorch": (stats.get("system") or {}).get("pytorch_version"),
            "system": stats.get("system"),
            "devices": devices,
        }

    def readiness(self) -> dict[str, Any]:
        health = self.health()
        if not health.get("ok"):
            return {
                **health,
                "ready": False,
                "creatorStatus": "MiniMax H3 — Runtime Offline",
                "missingFiles": [],
                "missingNodes": [],
            }

        missing_files: list[str] = []
        for role, path in required_checkpoint_paths().items():
            if not path.is_file() or path.stat().st_size <= 0:
                missing_files.append(role)

        missing_nodes: list[str] = []
        try:
            info = self._session.get(f"{self.base_url}/object_info", timeout=60).json()
            for node in REQUIRED_NODES:
                if node not in info:
                    missing_nodes.append(node)
        except Exception as exc:
            return {
                "ok": False,
                "ready": False,
                "errorCode": "H3_RUNTIME_UNAVAILABLE",
                "creatorStatus": "MiniMax H3 — Runtime Offline",
                "message": repr(exc),
                "missingFiles": missing_files,
                "missingNodes": list(REQUIRED_NODES),
            }

        ready = not missing_files and not missing_nodes and bool(health.get("gpu"))
        if missing_files or missing_nodes:
            creator = "MiniMax H3 — Missing Required Components"
        elif ready:
            creator = "MiniMax H3 — Ready for Private Local Use"
        else:
            creator = "MiniMax H3 — Runtime Offline"

        return {
            "ok": ready,
            "ready": ready,
            "creatorStatus": creator,
            "health": health,
            "missingFiles": missing_files,
            "missingNodes": missing_nodes,
            "profile": {
                "label": "Experimental Private Profile",
                "width": EXPERIMENTAL_WIDTH,
                "height": EXPERIMENTAL_HEIGHT,
                "length": EXPERIMENTAL_LENGTH,
                "steps": EXPERIMENTAL_STEPS,
                "nativeAudio": True,
                "durationRangeSec": [0.2, 15.0],
                "fps": EXPERIMENTAL_FPS,
            },
            "modelRootConfigured": True,
            # Do not expose raw checkpoint paths to creators.
        }

    def submit_t2va(
        self,
        *,
        project_id: str,
        plan_id: str,
        prompt: str,
        seed: int = 424242,
        duration_sec: float | None = None,
        width: int | None = None,
        height: int | None = None,
        fps: float | None = None,
        steps: int | None = None,
        studio_job_id: str | None = None,
    ) -> RouteAJobState:
        job_id = str(studio_job_id or uuid.uuid4())
        state = RouteAJobState(
            job_id=job_id,
            project_id=project_id,
            plan_id=plan_id,
            prompt=prompt,
            seed=seed,
            stage="Preparing local runtime",
            client_id=route_a_client_id(job_id, mode="text-to-video"),
        )
        ready = self.readiness()
        if not ready.get("ready"):
            state.status = "failed"
            state.error_code = "H3_MODEL_MISSING" if ready.get("missingFiles") else "H3_RUNTIME_UNAVAILABLE"
            state.error_message = ready.get("creatorStatus") or "MiniMax H3 is not ready."
            state.ended_at = time.time()
            self._persist_job(state)
            return state

        prefix = f"video/Adept_H3_Private_{job_id[:8]}"
        graph = build_t2va_graph(
            prompt,
            seed=seed,
            filename_prefix=prefix,
            duration_sec=duration_sec,
            width=width,
            height=height,
            fps=fps,
            steps=steps,
        )
        dumped = json.dumps(graph)
        for marker in FORBIDDEN_SHARD_MARKERS:
            if marker in dumped:
                state.status = "failed"
                state.error_code = "H3_MODEL_INCOMPATIBLE"
                state.error_message = "Diffusers-shard loaders are forbidden on Route A."
                state.ended_at = time.time()
                self._persist_job(state)
                return state

        state.stage = "Generating video and audio"
        state.status = "running"
        try:
            response = self._session.post(
                f"{self.base_url}/prompt",
                json={"prompt": graph, "client_id": state.client_id or route_a_client_id(job_id)},
                timeout=60,
            )
            body = response.json()
            if response.status_code != 200:
                state.status = "failed"
                state.error_code = "H3_JOB_FAILED"
                state.error_message = str(body)
                state.ended_at = time.time()
                self._persist_job(state)
                return state
            state.prompt_id = body.get("prompt_id")
        except Exception as exc:
            state.status = "failed"
            state.error_code = "H3_JOB_FAILED"
            state.error_message = repr(exc)
            state.ended_at = time.time()
            self._persist_job(state)
            return state

        state.submitted_graph = graph
        self._persist_job(state)
        return state

    def upload_image(self, path: Path, *, filename: str | None = None, subfolder: str = "studio") -> str:
        """Upload a start frame into the Route A Comfy input folder. Returns LoadImage name."""
        src = Path(path)
        if not src.is_file():
            raise FileNotFoundError(f"Start image not found: {src}")
        name = filename or src.name
        suffix = src.suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            raise ValueError(f"Unsupported start image format: {suffix or '(none)'}")
        data = {"subfolder": subfolder, "type": "input", "overwrite": "true"}
        with src.open("rb") as f:
            files = {"image": (name, f, "application/octet-stream")}
            response = self._session.post(
                f"{self.base_url}/upload/image",
                data=data,
                files=files,
                timeout=120,
            )
        if response.status_code != 200:
            raise RuntimeError(f"Comfy image upload failed: HTTP {response.status_code} {response.text}")
        result = response.json()
        returned = result.get("name") or name
        folder = result.get("subfolder") or subfolder
        return f"{folder}/{returned}" if folder else str(returned)

    def submit_i2va(
        self,
        *,
        project_id: str,
        plan_id: str,
        prompt: str,
        start_image_path: str | Path,
        seed: int = 424242,
        start_image_asset_id: str | None = None,
        end_image_path: str | Path | None = None,
        end_image_asset_id: str | None = None,
        middle_image_path: str | Path | None = None,
        middle_image_asset_id: str | None = None,
        duration_sec: float | None = None,
        width: int | None = None,
        height: int | None = None,
        fps: float | None = None,
        steps: int | None = None,
        studio_job_id: str | None = None,
    ) -> RouteAJobState:
        job_id = str(studio_job_id or uuid.uuid4())
        src = Path(start_image_path)
        end_src = Path(end_image_path) if end_image_path else None
        middle_src = Path(middle_image_path) if middle_image_path else None
        if middle_src and not end_src:
            state = RouteAJobState(
                job_id=job_id,
                project_id=project_id,
                plan_id=plan_id,
                prompt=prompt,
                seed=seed,
                status="failed",
                error_code="H3_FLF_FRAMES_INVALID",
                error_message="Middle frame requires First and Last frames.",
                ended_at=time.time(),
                mode="three-frame",
            )
            self._persist_job(state)
            return state
        if end_src is not None:
            mode = "three-frame" if middle_src is not None else "first-last"
        else:
            mode = "one-frame"
        state = RouteAJobState(
            job_id=job_id,
            project_id=project_id,
            plan_id=plan_id,
            prompt=prompt,
            seed=seed,
            stage="Preparing local runtime",
            mode=mode,
            start_image_path=str(src),
            client_id=route_a_client_id(job_id, mode=mode),
        )
        if not src.is_file():
            state.status = "failed"
            state.error_code = "H3_START_IMAGE_MISSING"
            state.error_message = "Add a readable starting frame before MiniMax H3 image-to-video."
            state.ended_at = time.time()
            self._persist_job(state)
            return state
        try:
            state.start_image_sha256 = file_sha256(src)
        except Exception as exc:
            state.status = "failed"
            state.error_code = "H3_START_IMAGE_UNREADABLE"
            state.error_message = f"Could not read starting frame: {exc!r}"
            state.ended_at = time.time()
            self._persist_job(state)
            return state

        ready = self.readiness()
        if not ready.get("ready"):
            state.status = "failed"
            state.error_code = "H3_MODEL_MISSING" if ready.get("missingFiles") else "H3_RUNTIME_UNAVAILABLE"
            state.error_message = ready.get("creatorStatus") or "MiniMax H3 is not ready."
            state.ended_at = time.time()
            self._persist_job(state)
            return state

        # I2V also requires LoadImage on the Route A runtime.
        try:
            info = self._session.get(f"{self.base_url}/object_info", timeout=60).json()
            if "LoadImage" not in info:
                state.status = "failed"
                state.error_code = "H3_RUNTIME_UNAVAILABLE"
                state.error_message = "MiniMax H3 runtime is missing LoadImage for image-to-video."
                state.ended_at = time.time()
                self._persist_job(state)
                return state
        except Exception as exc:
            state.status = "failed"
            state.error_code = "H3_RUNTIME_UNAVAILABLE"
            state.error_message = repr(exc)
            state.ended_at = time.time()
            self._persist_job(state)
            return state

        if end_src is not None and not end_src.is_file():
            state.status = "failed"
            state.error_code = "H3_END_IMAGE_MISSING"
            state.error_message = "Add a readable last frame before MiniMax H3 first-last / 3 Frame."
            state.ended_at = time.time()
            self._persist_job(state)
            return state
        if middle_src is not None and not middle_src.is_file():
            state.status = "failed"
            state.error_code = "H3_MIDDLE_IMAGE_MISSING"
            state.error_message = "Middle frame path is not readable."
            state.ended_at = time.time()
            self._persist_job(state)
            return state

        state.stage = "Uploading start frame"
        try:
            comfy_name = self.upload_image(
                src,
                filename=f"h3_i2v_{job_id[:8]}{src.suffix.lower() or '.png'}",
            )
        except Exception as exc:
            state.status = "failed"
            state.error_code = "H3_START_IMAGE_UPLOAD_FAILED"
            state.error_message = f"Could not upload starting frame: {exc!r}"
            state.ended_at = time.time()
            self._persist_job(state)
            return state
        state.comfy_image_name = comfy_name

        last_comfy_name = None
        middle_comfy_name = None
        if end_src is not None:
            state.stage = "Uploading last frame"
            try:
                last_comfy_name = self.upload_image(
                    end_src,
                    filename=f"h3_flf_last_{job_id[:8]}{end_src.suffix.lower() or '.png'}",
                )
            except Exception as exc:
                state.status = "failed"
                state.error_code = "H3_END_IMAGE_UPLOAD_FAILED"
                state.error_message = f"Could not upload last frame: {exc!r}"
                state.ended_at = time.time()
                self._persist_job(state)
                return state
        if middle_src is not None:
            state.stage = "Uploading middle frame"
            try:
                middle_comfy_name = self.upload_image(
                    middle_src,
                    filename=f"h3_flf_mid_{job_id[:8]}{middle_src.suffix.lower() or '.png'}",
                )
            except Exception as exc:
                state.status = "failed"
                state.error_code = "H3_MIDDLE_IMAGE_UPLOAD_FAILED"
                state.error_message = f"Could not upload middle frame: {exc!r}"
                state.ended_at = time.time()
                self._persist_job(state)
                return state
            try:
                info = self._session.get(f"{self.base_url}/object_info", timeout=60).json()
                if "MiniMaxH3AddGuide" not in info:
                    state.status = "failed"
                    state.error_code = "H3_RUNTIME_UNAVAILABLE"
                    state.error_message = "MiniMax H3 runtime is missing MiniMaxH3AddGuide for 3 Frame."
                    state.ended_at = time.time()
                    self._persist_job(state)
                    return state
            except Exception as exc:
                state.status = "failed"
                state.error_code = "H3_RUNTIME_UNAVAILABLE"
                state.error_message = repr(exc)
                state.ended_at = time.time()
                self._persist_job(state)
                return state

        # Duration must be on the 17k+5 grid. No silent snap/clamp.
        try:
            _h3_legal_duration(duration_sec, fps)
        except ValueError as exc:
            state.status = "failed"
            state.error_code = "H3_I2V_DURATION_ILLEGAL"
            state.error_message = str(exc)
            state.ended_at = time.time()
            self._persist_job(state)
            return state

        if last_comfy_name:
            prefix = f"video/Adept_H3_Private_FLF_{job_id[:8]}"
        else:
            prefix = f"video/Adept_H3_Private_I2V_{job_id[:8]}"
        try:
            graph = build_i2va_graph(
                prompt,
                seed=seed,
                filename_prefix=prefix,
                first_frame_comfy_name=comfy_name,
                last_frame_comfy_name=last_comfy_name,
                middle_frame_comfy_name=middle_comfy_name,
                duration_sec=duration_sec,
                width=width,
                height=height,
                fps=fps,
                steps=steps,
            )
            if last_comfy_name:
                assert_flf_graph_binding(
                    graph,
                    first_comfy_name=comfy_name,
                    last_comfy_name=last_comfy_name,
                    middle_comfy_name=middle_comfy_name,
                )
            else:
                assert_i2va_graph_binding(graph, expected_comfy_name=comfy_name)
        except Exception as exc:
            state.status = "failed"
            state.error_code = "H3_I2V_GRAPH_INVALID"
            state.error_message = str(exc)
            state.ended_at = time.time()
            self._persist_job(state)
            return state


        dumped = json.dumps(graph)
        for marker in FORBIDDEN_SHARD_MARKERS:
            if marker in dumped:
                state.status = "failed"
                state.error_code = "H3_MODEL_INCOMPATIBLE"
                state.error_message = "Diffusers-shard loaders are forbidden on Route A."
                state.ended_at = time.time()
                self._persist_job(state)
                return state

        # Refuse T2V-shaped graphs (no first_frame) for the I2V path.
        if "first_frame" not in dumped or LOAD_IMAGE_NODE_ID not in graph:
            state.status = "failed"
            state.error_code = "H3_I2V_GRAPH_INVALID"
            state.error_message = "I2V submit refused a graph without LoadImage/first_frame binding."
            state.ended_at = time.time()
            self._persist_job(state)
            return state

        state.submitted_graph = graph
        state.stage = "Generating video and audio"
        state.status = "running"
        try:
            response = self._session.post(
                f"{self.base_url}/prompt",
                json={
                    "prompt": graph,
                    "client_id": state.client_id or route_a_client_id(job_id, mode=state.mode),
                },
                timeout=60,
            )
            body = response.json()
            if response.status_code != 200:
                state.status = "failed"
                state.error_code = "H3_JOB_FAILED"
                state.error_message = str(body)
                state.ended_at = time.time()
                self._persist_job(state)
                return state
            state.prompt_id = body.get("prompt_id")
        except Exception as exc:
            state.status = "failed"
            state.error_code = "H3_JOB_FAILED"
            state.error_message = repr(exc)
            state.ended_at = time.time()
            self._persist_job(state)
            return state

        workflow_id = "route-a-experimental-private-i2va"
        if last_comfy_name and middle_comfy_name:
            workflow_id = "route-a-experimental-private-flf3-addguide"
        elif last_comfy_name:
            workflow_id = "route-a-experimental-private-flf2va"
        state.provenance = {
            "startImageAssetId": start_image_asset_id,
            "endImageAssetId": end_image_asset_id,
            "middleImageAssetId": middle_image_asset_id,
            "startImageSha256": state.start_image_sha256,
            "comfyImageName": comfy_name,
            "comfyLastImageName": last_comfy_name,
            "comfyMiddleImageName": middle_comfy_name,
            "firstFrameNodeId": LOAD_IMAGE_NODE_ID,
            "lastFrameNodeId": LAST_LOAD_IMAGE_NODE_ID if last_comfy_name else None,
            "middleFrameNodeId": MIDDLE_LOAD_IMAGE_NODE_ID if middle_comfy_name else None,
            "addGuideNodeId": ADD_GUIDE_NODE_ID if middle_comfy_name else None,
            "conditioningNodeId": I2V_CONDITIONING_NODE_ID,
            "workflowId": workflow_id,
            "strategy": (
                "middle-guidance-b"
                if middle_comfy_name
                else ("first-last" if last_comfy_name else "one-frame")
            ),
        }
        self._persist_job(state)
        return state

    def poll(
        self,
        state: RouteAJobState,
        *,
        timeout_sec: float = 900.0,
        on_wait: Any | None = None,
    ) -> RouteAJobState:
        """Wait for Route A Comfy completion.

        CRITICAL ordering: observe ``/history`` BEFORE ``on_wait``.
        Heartbeat / queue refresh must never block finalize. BOT B 1F hangs
        (jobs 2d6920be / 0baad7da) left Route A JSON stranded at
        status=running after Comfy history success because the loop called
        ``on_wait`` first and a blocked heartbeat prevented history observation.
        """
        if not state.prompt_id:
            state.status = "failed"
            state.error_code = "H3_JOB_FAILED"
            state.error_message = "Missing runtime job id."
            return state
        deadline = time.time() + timeout_sec
        missing_output_retries = 0
        while time.time() < deadline:
            if state.cancelled:
                state.status = "cancelled"
                state.error_code = "H3_CANCELLED"
                state.stage = "Cancelled"
                state.ended_at = time.time()
                self._persist_job(state)
                return state
            history: dict[str, Any] = {}
            try:
                # Fresh timeout per request — do not inherit a wedged client timeout.
                response = self._session.get(
                    f"{self.base_url}/history/{state.prompt_id}",
                    timeout=httpx.Timeout(15.0, connect=5.0, read=15.0, write=15.0, pool=5.0),
                )
                payload = response.json()
                if isinstance(payload, dict):
                    history = payload
            except Exception:
                history = {}

            if history and state.prompt_id in history:
                entry = history[state.prompt_id]
                status_obj = entry.get("status") or {}
                status_str = (
                    status_obj.get("status_str")
                    or (status_obj.get("completed") and "success")
                    or "unknown"
                )
                if status_str in {"error", "interrupted"} or state.cancelled:
                    if state.cancelled:
                        state.status = "cancelled"
                        state.error_code = "H3_CANCELLED"
                        state.stage = "Cancelled"
                    else:
                        state.status = "failed"
                        state.error_code = "H3_JOB_FAILED"
                        state.stage = "Failed"
                        state.error_message = self._extract_runtime_error(entry) or (
                            "interrupted"
                            if status_str == "interrupted"
                            else "MiniMax H3 runtime reported an error."
                        )
                    state.ended_at = time.time()
                    self._persist_job(state)
                    return state

                # Only finalize on explicit success/completed — never treat
                # mid-flight history rows as done.
                completed = bool(status_obj.get("completed")) or status_str == "success"
                if not completed:
                    # Keep waiting; still allow heartbeat below.
                    pass
                else:
                    # Persist Validating immediately so Adept is not silent if
                    # ffprobe/validate stalls.
                    state.stage = "Validating output"
                    state.status = "running"
                    self._persist_job(state)
                    outputs = entry.get("outputs") or {}
                    mp4 = self._find_output_mp4(outputs)
                    if not mp4:
                        mp4 = self._scan_comfy_output(state.job_id)
                    if not mp4:
                        missing_output_retries += 1
                        if missing_output_retries >= 15:
                            state.status = "failed"
                            state.error_code = "H3_OUTPUT_INVALID"
                            state.error_message = "No media file was produced."
                            state.ended_at = time.time()
                            self._persist_job(state)
                            return state
                        time.sleep(2)
                        continue
                    missing_output_retries = 0
                    mp4, colorspace_info = finalize_h3_colorspace_passthrough(mp4)
                    validation = validate_media(mp4)
                    if not validation.get("ok"):
                        state.status = "failed"
                        state.error_code = validation.get("errorCode") or "H3_OUTPUT_INVALID"
                        state.error_message = validation.get("message") or "Output failed validation."
                        state.media = validation
                        state.ended_at = time.time()
                        self._persist_job(state)
                        return state
                    state.stage = "Complete"
                    state.status = "completed"
                    state.output_path = str(mp4)
                    state.media = validation
                    is_i2v = state.mode == "one-frame" or bool(state.comfy_image_name)
                    state.provenance = {
                        **(state.provenance or {}),
                        "modelId": "minimax-h3-route-a-local",
                        "displayName": "MiniMax H3",
                        "provider": "MiniMax",
                        "deployment": "private-local",
                        "availability": "experimental",
                        "access": "owner-only",
                        "runtime": "route-a",
                        "runtimeUrlIdentity": "isolated-comfyui-8192",
                        "workflowId": (
                            "route-a-experimental-private-i2va"
                            if is_i2v
                            else "route-a-experimental-private-t2va"
                        ),
                        "nativeAudio": True,
                        "apiUsed": False,
                        "ltxUsed": False,
                        "acceleration": {
                            "accelerator": "none",
                            "residualReuse": False,
                            "sageAttention": "disabled",
                            "profile": "MiniMax H3 Golden (no accelerator — clean native A/V)",
                            "creatorLabel": "Standard",
                            "note": "SpeedCache/SageAttention dropped: corrupts H3 native audio in all modes.",
                        },
                        "colorspaceFinalization": colorspace_info,
                        "profile": "Experimental Private Profile",
                        "seed": state.seed,
                        "prompt": state.prompt,
                        "promptId": state.prompt_id,
                        "jobId": state.job_id,
                        "mode": state.mode,
                        "startImageSha256": state.start_image_sha256,
                        "comfyImageName": state.comfy_image_name,
                        "firstFrameNodeId": LOAD_IMAGE_NODE_ID if is_i2v else None,
                        "submittedGraphPersisted": bool(state.submitted_graph),
                    }
                    state.ended_at = time.time()
                    self._persist_job(state)
                    return state

            # Heartbeat AFTER history observation; never let it block forever.
            if on_wait is not None:
                import threading

                elapsed = max(0.0, time.time() - float(state.started_at or time.time()))
                holder: dict[str, BaseException | None] = {"err": None}

                def _run_wait() -> None:
                    try:
                        on_wait(elapsed)
                    except BaseException as exc:  # noqa: BLE001 — surface then continue
                        holder["err"] = exc

                t = threading.Thread(target=_run_wait, daemon=True, name="route-a-on-wait-bound")
                t.start()
                t.join(timeout=8.0)
                if t.is_alive():
                    # Wedged heartbeat — continue polling history next tick.
                    pass
                elif holder["err"] is not None and not isinstance(holder["err"], Exception):
                    raise holder["err"]
            time.sleep(2)
        state.status = "failed"
        state.error_code = "H3_JOB_FAILED"
        state.error_message = "Timed out waiting for MiniMax H3."
        state.ended_at = time.time()
        self._persist_job(state)
        return state
    def cancel(self, state: RouteAJobState) -> RouteAJobState:
        state.cancelled = True
        state.stage = "Cancelling…"
        try:
            self._session.post(f"{self.base_url}/interrupt", timeout=15)
        except Exception as exc:
            state.error_message = repr(exc)
        state.status = "cancelled"
        state.error_code = "H3_CANCELLED"
        state.ended_at = time.time()
        self._persist_job(state)
        return state

    def _find_output_mp4(self, outputs: dict[str, Any]) -> Path | None:
        for _nid, payload in outputs.items():
            if not isinstance(payload, dict):
                continue
            for key in ("gifs", "videos", "images"):
                items = payload.get(key) or []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    filename = item.get("filename")
                    subfolder = item.get("subfolder") or ""
                    if filename and str(filename).lower().endswith(".mp4"):
                        # Prefer scanning known output roots
                        found = self._resolve_output_file(str(filename), str(subfolder))
                        if found:
                            return found
        return None

    def _resolve_output_file(self, filename: str, subfolder: str) -> Path | None:
        # Route A :8192 isolated runtime output dir.
        root = Path(r"C:\AdeptFilmWorks\AIVideoStudio-h3\runtime\minimax-h3\comfyui\output")
        candidates = [root / subfolder / filename, root / filename]
        for path in candidates:
            if path.is_file():
                return path
        return None

    def _scan_comfy_output(self, job_id: str) -> Path | None:
        root = Path(r"C:\AdeptFilmWorks\AIVideoStudio-h3\runtime\minimax-h3\comfyui\output")
        if not root.is_dir():
            return None
        needle = job_id[:8]
        newest: Path | None = None
        newest_mtime = 0.0
        for path in root.rglob("*.mp4"):
            if needle in path.name and path.stat().st_mtime >= newest_mtime:
                newest = path
                newest_mtime = path.stat().st_mtime
        return newest

    def _extract_runtime_error(self, entry: dict[str, Any]) -> str | None:
        """Pull a plain-language error detail out of a ComfyUI history entry.

        ComfyUI records failures as ``execution_error`` messages inside the
        history ``status.messages`` list. Without this, the adapter reported
        ``H3_JOB_FAILED`` with a null error message, hiding the real cause
        (e.g. ``OSError: [Errno 22] Invalid argument`` during sampling on
        VRAM contention). This surfaces that detail for diagnosis while
        keeping the creator-facing surface clean.
        """
        status_obj = entry.get("status") or {}
        messages = status_obj.get("messages") or []
        for kind, payload in messages:
            if kind != "execution_error" or not isinstance(payload, dict):
                continue
            exc_message = (payload.get("exception_message") or "").strip()
            exc_type = payload.get("exception_type") or ""
            node_id = payload.get("node_id") or ""
            node_type = payload.get("node_type") or ""
            head = exc_message or "MiniMax H3 generation failed."
            if exc_type and exc_type not in head:
                head = f"{exc_type}: {head}"
            where = f" at {node_type} ({node_id})" if (node_type or node_id) else ""
            return f"{head}{where}".strip()
        return None

    def _persist_job(self, state: RouteAJobState) -> None:
        payload = {
            "jobId": state.job_id,
            "projectId": state.project_id,
            "planId": state.plan_id,
            "prompt": state.prompt,
            "seed": state.seed,
            "promptId": state.prompt_id,
            "status": state.status,
            "stage": state.stage,
            "errorCode": state.error_code,
            "errorMessage": state.error_message,
            "outputPath": state.output_path,
            "media": state.media,
            "provenance": state.provenance,
            "startedAt": state.started_at,
            "endedAt": state.ended_at,
            "cancelled": state.cancelled,
            "mode": state.mode,
            "comfyImageName": state.comfy_image_name,
            "startImagePath": state.start_image_path,
            "startImageSha256": state.start_image_sha256,
            "submittedGraph": state.submitted_graph,
        }
        write_json(project_dir(state.project_id) / "jobs" / f"{state.job_id}.json", payload)
        if state.submitted_graph:
            write_json(
                project_dir(state.project_id) / "jobs" / f"{state.job_id}.submitted-graph.json",
                state.submitted_graph,
            )


def validate_media(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        return {"ok": False, "errorCode": "H3_OUTPUT_INVALID", "message": "Output file missing."}
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        return {"ok": False, "errorCode": "H3_OUTPUT_INVALID", "message": "ffprobe is not available."}
    except Exception as exc:
        return {"ok": False, "errorCode": "H3_OUTPUT_INVALID", "message": repr(exc)}
    if proc.returncode != 0:
        return {
            "ok": False,
            "errorCode": "H3_OUTPUT_INVALID",
            "message": proc.stderr.strip() or "ffprobe failed.",
        }
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video:
        return {"ok": False, "errorCode": "H3_VIDEO_DECODE_FAILED", "message": "Missing video stream."}
    if not audio:
        return {"ok": False, "errorCode": "H3_AUDIO_DECODE_FAILED", "message": "Missing audio stream."}
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    nb_frames = int(float(video.get("nb_frames") or 0) or 0)
    if width <= 0 or height <= 0:
        return {"ok": False, "errorCode": "H3_VIDEO_DECODE_FAILED", "message": "Invalid video dimensions."}
    return {
        "ok": True,
        "path": str(path),
        "sizeBytes": path.stat().st_size,
        "container": (data.get("format") or {}).get("format_name"),
        "videoCodec": video.get("codec_name"),
        "width": width,
        "height": height,
        "frameCount": nb_frames,
        "audioCodec": audio.get("codec_name"),
        "audioSampleRate": int(float(audio.get("sample_rate") or 0) or 0),
        "audioChannels": int(audio.get("channels") or 0),
        "durationSeconds": float((data.get("format") or {}).get("duration") or 0),
        "audioNonSilent": True,  # stream present; amplitude scan optional
        "decodePass": True,
    }


# ---------------------------------------------------------------------------
# ONE shared MiniMax H3 output-finalization authority.
#
# CreateVideo + SaveVideo (format/codec auto) emit an H.264 stream with NO
# colorspace metadata (color_space/color_transfer/color_primaries/color_range
# all "unknown"). Browsers/players must then GUESS the YUV<->RGB matrix and
# shift colors on playback. Live split-diagnostic proved:
#   - raw VAEDecode frames are faithful to the source (no decode color cast)
#   - the H.264 encode uses the bt601 (smpte170m) matrix (bt601 decode matches
#     the raw RGB best; rms 2.50 vs raw vs 3.19 for bt709)
#   - the file pixels are correct; only the metadata is missing
#
# Fix: a LOSSLESS ffmpeg remux (-c copy) that tags the stream with the matrix
# the encode actually used (smpte170m / bt709 transfer / smpte170m primaries /
# tv limited range) so players recover the EXACT raw decoded RGB. No re-encode,
# no generation loss, audio + duration + AV sync preserved (verified: AV
# drift unchanged at -0.0003s). This is shared by T2V / 1F I2V / 3F assembly
# because they all complete through RouteARuntimeAdapter.poll().
# ---------------------------------------------------------------------------
H3_FINAL_COLORSPACE = "smpte170m"      # bt601 — matches the CreateVideo encode matrix
H3_FINAL_TRANSFER = "smpte170m"        # bt601 transfer
H3_FINAL_PRIMARIES = "smpte170m"       # bt601 primaries
H3_FINAL_RANGE = "tv"                  # limited range (broadcast/PC convention)


def _stream_colorspace(path: Path) -> dict[str, str]:
    """Return the video stream's colorspace tags (or 'unknown' if unset)."""
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=color_space,color_transfer,color_primaries,color_range",
             "-of", "default=noprint_wrappers=1", str(path)],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except Exception:
        return {"color_space": "unknown", "color_transfer": "unknown",
                "color_primaries": "unknown", "color_range": "unknown"}
    if proc.returncode != 0:
        return {"color_space": "unknown", "color_transfer": "unknown",
                "color_primaries": "unknown", "color_range": "unknown"}
    tags: dict[str, str] = {}
    for line in (proc.stdout or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            tags[k.strip()] = (v or "unknown").strip()
    for k in ("color_space", "color_transfer", "color_primaries", "color_range"):
        tags.setdefault(k, "unknown")
    return tags


def finalize_h3_colorspace(mp4_path: Path) -> tuple[Path, dict[str, Any]]:
    """Tag the MiniMax H3 MP4 with correct colorspace metadata (lossless remux).

    Returns (final_path, info). If the stream is already tagged, returns the
    original path unchanged (idempotent). If the remux fails, returns the
    original path (never breaks a successful render for a metadata fix).
    """
    src = Path(mp4_path)
    if not src.is_file():
        return src, {"applied": False, "reason": "source missing"}
    cs = _stream_colorspace(src)
    # Idempotent: if all four tags are already set to non-unknown values, skip.
    if all(cs.get(k) not in (None, "", "unknown") for k in
           ("color_space", "color_transfer", "color_primaries", "color_range")):
        return src, {"applied": False, "reason": "already tagged", "existing": cs}

    tmp = src.with_suffix(".colorfixed.mp4")
    if tmp.exists():
        tmp.unlink()
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", str(src),
        "-c", "copy",
        "-colorspace", H3_FINAL_COLORSPACE,
        "-color_primaries", H3_FINAL_PRIMARIES,
        "-color_trc", H3_FINAL_TRANSFER,
        "-color_range", H3_FINAL_RANGE,
        "-movflags", "+faststart",
        str(tmp),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True)
    except Exception as exc:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass
        return src, {"applied": False, "reason": f"remux failed: {exc!r}", "existing": cs}

    # Verify the remux actually injected the tags.
    new_cs = _stream_colorspace(tmp)
    if all(new_cs.get(k) not in (None, "", "unknown") for k in
            ("color_space", "color_transfer", "color_primaries", "color_range")):
        # Replace the original with the tagged version.
        backup = src.with_suffix(".uncolored.mp4")
        try:
            if backup.exists():
                backup.unlink()
            src.rename(backup)
            tmp.rename(src)
        except Exception as exc:
            # If rename fails, try to leave the tagged file in place and point to it.
            try:
                if not src.exists() and tmp.exists():
                    tmp.rename(src)
            except Exception:
                pass
            return (src if src.exists() else tmp,
                    {"applied": True, "tagged": new_cs, "previous": cs,
                     "rename_note": f"rename fallback: {exc!r}"})
        # Clean up the backup once the tagged file is in place.
        try:
            if backup.exists():
                backup.unlink()
        except Exception:
            pass
        return src, {"applied": True, "tagged": new_cs, "previous": cs}

    # Tags did not stick (some streams need a re-encode to inject VUI). Fall
    # back to the original rather than risk a re-encode here — report it so
    # the authority can be revisited. Do NOT silently ship an untagged file
    # as if it were fixed.
    try:
        if tmp.exists():
            tmp.unlink()
    except Exception:
        pass
    return src, {"applied": False, "reason": "tags did not stick after remux",
                 "existing": cs, "attempted": new_cs}


def finalize_h3_colorspace_passthrough(mp4_path: Path) -> tuple[Path, dict[str, Any]]:
    """Golden Workflow Convergence: trust the native SaveVideo colorspace.

    The default Comfy H3 SaveVideo already emits correctly-tagged bt709
    (color_space/color_transfer/color_primaries). The legacy bt601 remux
    (finalize_h3_colorspace) was built on the false premise that the encode is
    bt601/untagged and INTRODUCED the owner-observed color shift. This passthrough
    performs NO remux — it only reads the existing tags for provenance reporting.
    Returns (original_path, info). Never modifies the file.
    """
    src = Path(mp4_path)
    if not src.is_file():
        return src, {"applied": False, "remux": "removed", "reason": "source missing"}
    cs = _stream_colorspace(src)
    return src, {
        "applied": False,
        "remux": "removed",
        "policy": "trust-native-savevideo-bt709",
        "existing": cs,
    }


def import_output_to_project_library(
    *,
    project_id: str,
    source_mp4: Path,
    tag: str,
    db: Any,
) -> dict[str, Any]:
    """Copy validated MP4 into project assets and create Asset row."""
    from datetime import datetime
    import uuid as uuid_mod

    from ..config import settings
    from ..db import Asset, Project

    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found")
    asset_id = str(uuid_mod.uuid4())
    dest_dir = Path(settings.data_dir) / "assets" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{asset_id}.mp4"
    shutil.copy2(source_mp4, dest)
    asset = Asset(
        id=asset_id,
        project_id=project_id,
        tag=tag.lstrip("@").strip() or "minimax-h3",
        kind="video",
        filename=source_mp4.name,
        path=str(dest),
        comfy_name="",
    )
    db.add(asset)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(asset)
    return {
        "assetId": asset.id,
        "projectId": project_id,
        "path": str(dest),
        "tag": asset.tag,
        "kind": asset.kind,
        "filename": asset.filename,
    }
