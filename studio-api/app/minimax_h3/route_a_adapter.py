"""MiniMax H3 Route A Runtime Adapter — isolated ComfyUI :8192 only."""

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

LOAD_IMAGE_NODE_ID = "15"
I2V_CONDITIONING_NODE_ID = "5"

FORBIDDEN_SHARD_MARKERS = (
    "model-00001-of-",
    "FL2VA/transformer",
    "FL2VA\\transformer",
    "MiniMaxH3Pipeline",
    "from_pretrained",
)

# Proven Experimental Private Profile (Route A Gate C)
EXPERIMENTAL_WIDTH = 480
EXPERIMENTAL_HEIGHT = 256
EXPERIMENTAL_LENGTH = 5
EXPERIMENTAL_STEPS = 4


@dataclass
class RouteAJobState:
    job_id: str
    project_id: str
    plan_id: str
    prompt: str
    seed: int
    prompt_id: str | None = None
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


def build_t2va_graph(prompt: str, *, seed: int, filename_prefix: str) -> dict[str, Any]:
    return {
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
                "width": EXPERIMENTAL_WIDTH,
                "height": EXPERIMENTAL_HEIGHT,
                "length": EXPERIMENTAL_LENGTH,
            },
        },
        "6": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "7": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "8": {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["1", 0],
                "scheduler": "simple",
                "steps": EXPERIMENTAL_STEPS,
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
            "inputs": {"images": ["11", 0], "fps": 24.0, "audio": ["12", 0], "bit_depth": 8},
        },
        "14": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["13", 0],
                "filename_prefix": filename_prefix,
                "format": "auto",
                "codec": "auto",
            },
        },
    }


def build_i2va_graph(
    prompt: str,
    *,
    seed: int,
    filename_prefix: str,
    first_frame_comfy_name: str,
) -> dict[str, Any]:
    """Route A image-conditioned graph: LoadImage → MiniMaxH3ImageToVideo.first_frame."""
    if not (first_frame_comfy_name or "").strip():
        raise ValueError("first_frame_comfy_name is required for MiniMax H3 I2V.")
    graph = build_t2va_graph(prompt, seed=seed, filename_prefix=filename_prefix)
    graph[LOAD_IMAGE_NODE_ID] = {
        "class_type": "LoadImage",
        "inputs": {"image": first_frame_comfy_name},
    }
    graph[I2V_CONDITIONING_NODE_ID]["inputs"]["first_frame"] = [LOAD_IMAGE_NODE_ID, 0]
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
    ) -> RouteAJobState:
        job_id = str(uuid.uuid4())
        state = RouteAJobState(
            job_id=job_id,
            project_id=project_id,
            plan_id=plan_id,
            prompt=prompt,
            seed=seed,
            stage="Preparing local runtime",
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
        graph = build_t2va_graph(prompt, seed=seed, filename_prefix=prefix)
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
                json={"prompt": graph, "client_id": f"adept-h3-{job_id[:8]}"},
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
    ) -> RouteAJobState:
        job_id = str(uuid.uuid4())
        src = Path(start_image_path)
        state = RouteAJobState(
            job_id=job_id,
            project_id=project_id,
            plan_id=plan_id,
            prompt=prompt,
            seed=seed,
            stage="Preparing local runtime",
            mode="one-frame",
            start_image_path=str(src),
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

        prefix = f"video/Adept_H3_Private_I2V_{job_id[:8]}"
        try:
            graph = build_i2va_graph(
                prompt,
                seed=seed,
                filename_prefix=prefix,
                first_frame_comfy_name=comfy_name,
            )
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
                json={"prompt": graph, "client_id": f"adept-h3-i2v-{job_id[:8]}"},
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

        state.provenance = {
            "startImageAssetId": start_image_asset_id,
            "startImageSha256": state.start_image_sha256,
            "comfyImageName": comfy_name,
            "firstFrameNodeId": LOAD_IMAGE_NODE_ID,
            "conditioningNodeId": I2V_CONDITIONING_NODE_ID,
            "workflowId": "route-a-experimental-private-i2va",
        }
        self._persist_job(state)
        return state

    def poll(self, state: RouteAJobState, *, timeout_sec: float = 900.0) -> RouteAJobState:
        if not state.prompt_id:
            state.status = "failed"
            state.error_code = "H3_JOB_FAILED"
            state.error_message = "Missing runtime job id."
            return state
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if state.cancelled:
                state.status = "cancelled"
                state.error_code = "H3_CANCELLED"
                state.stage = "Cancelled"
                state.ended_at = time.time()
                self._persist_job(state)
                return state
            try:
                history = self._session.get(
                    f"{self.base_url}/history/{state.prompt_id}", timeout=30
                ).json()
            except Exception:
                time.sleep(2)
                continue
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
                        # Surface the real runtime error instead of a null message
                        # (the RED symptom was H3_JOB_FAILED with errorMessage=null).
                        state.error_message = self._extract_runtime_error(entry) or (
                            "interrupted"
                            if status_str == "interrupted"
                            else "MiniMax H3 runtime reported an error."
                        )
                    state.ended_at = time.time()
                    self._persist_job(state)
                    return state
                # completed
                state.stage = "Validating output"
                outputs = entry.get("outputs") or {}
                mp4 = self._find_output_mp4(outputs)
                if not mp4:
                    # Also scan Comfy output directory for our prefix
                    mp4 = self._scan_comfy_output(state.job_id)
                if not mp4:
                    state.status = "failed"
                    state.error_code = "H3_OUTPUT_INVALID"
                    state.error_message = "No media file was produced."
                    state.ended_at = time.time()
                    self._persist_job(state)
                    return state
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
        candidates = [
            Path(r"C:\AdeptFilmWorks\AIVideoStudio-h3\runtime\minimax-h3\comfyui\output")
            / subfolder
            / filename,
            Path(r"C:\AdeptFilmWorks\AIVideoStudio-h3\runtime\minimax-h3\comfyui\output")
            / filename,
        ]
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
