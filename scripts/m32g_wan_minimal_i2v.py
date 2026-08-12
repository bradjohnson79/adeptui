"""Smallest valid WAN 2.2 I2V after encoder shape smoke GREEN.

Constraints (user guidance):
  - low frame count, modest resolution
  - one prompt, one start frame
  - authoritative umt5 fp8 encoder (4096-d)
  - no projection adapters
  - no unnecessary post-processing
  - single diagnostic prompt (clear Comfy queue first)
"""
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
OUT = ROOT / "artifacts/m32g/hitchhiker-test-2/07-wan-generation"
OUT.mkdir(parents=True, exist_ok=True)

START = ROOT / (
    "data/projects/d1683511-1cc7-4d3d-8cb7-00f48cc36aa9/assets/"
    "imagegen_generate_281adb03.png"
)
ENCODER = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
VAE = r"WanVideo\Wan2_1_VAE_bf16.safetensors"
UNET_HIGH = "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"
UNET_LOW = "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"

# Minimal playable band (4n+1)
WIDTH, HEIGHT, LENGTH, FPS = 640, 368, 9, 16
STEPS_HIGH, STEPS_LOW = 2, 2
PROMPT = "A hitchhiker beside a rural highway, slow dolly-in, golden hour, cinematic"


def call(method: str, url: str, body: dict | None = None, timeout: int = 180):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def upload_image(path: Path) -> str:
    boundary = f"----Boundary{uuid.uuid4().hex}"
    file_bytes = path.read_bytes()
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'
            ).encode(),
            f"Content-Type: {ctype}\r\n\r\n".encode(),
            file_bytes,
            b"\r\n",
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="overwrite"\r\n\r\n',
            b"true\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    req = urllib.request.Request(
        f"{COMFY}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    name = payload.get("name") or path.name
    sub = payload.get("subfolder") or ""
    return f"{sub}/{name}" if sub else name


def build_workflow(start_name: str) -> dict:
    total = STEPS_HIGH + STEPS_LOW
    return {
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": ENCODER, "type": "wan"},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": PROMPT, "clip": ["3", 0]},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "blurry, static, text, watermark, deformed",
                "clip": ["3", 0],
            },
        },
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "9": {"class_type": "LoadImage", "inputs": {"image": start_name}},
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": UNET_HIGH, "weight_dtype": "default"},
        },
        "2": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": UNET_LOW, "weight_dtype": "default"},
        },
        "7": {
            "class_type": "ModelSamplingSD3",
            "inputs": {"model": ["1", 0], "shift": 8.0},
        },
        "8": {
            "class_type": "ModelSamplingSD3",
            "inputs": {"model": ["2", 0], "shift": 8.0},
        },
        "11": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["5", 0],
                "negative": ["6", 0],
                "vae": ["4", 0],
                "width": WIDTH,
                "height": HEIGHT,
                "length": LENGTH,
                "batch_size": 1,
                "start_image": ["9", 0],
            },
        },
        "12": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["7", 0],
                "add_noise": "enable",
                "noise_seed": 42,
                "steps": total,
                "cfg": 3.5,
                "sampler_name": "uni_pc",
                "scheduler": "simple",
                "positive": ["11", 0],
                "negative": ["11", 1],
                "latent_image": ["11", 2],
                "start_at_step": 0,
                "end_at_step": STEPS_HIGH,
                "return_with_leftover_noise": "enable",
            },
        },
        "13": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["8", 0],
                "add_noise": "disable",
                "noise_seed": 42,
                "steps": total,
                "cfg": 3.5,
                "sampler_name": "uni_pc",
                "scheduler": "simple",
                "positive": ["11", 0],
                "negative": ["11", 1],
                "latent_image": ["12", 0],
                "start_at_step": STEPS_HIGH,
                "end_at_step": 10000,
                "return_with_leftover_noise": "disable",
            },
        },
        "14": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["13", 0], "vae": ["4", 0]},
        },
        "15": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["14", 0],
                "frame_rate": FPS,
                "loop_count": 0,
                "filename_prefix": "studio/m32g_wan_minimal",
                "format": "video/h264-mp4",
                "pingpong": False,
                "save_output": True,
            },
        },
    }


def ffprobe(path: Path) -> dict:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=codec_type,codec_name,width,height,nb_frames,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return json.loads(proc.stdout or "{}")


def find_output_mp4(history: dict) -> Path | None:
    outputs = history.get("outputs") or {}
    for node_out in outputs.values():
        for key in ("gifs", "videos", "images"):
            for item in node_out.get(key) or []:
                if not isinstance(item, dict):
                    continue
                filename = item.get("filename") or ""
                if not filename.lower().endswith((".mp4", ".webm", ".gif")):
                    continue
                sub = item.get("subfolder") or ""
                # Comfy output root guess
                for base in (
                    Path(os.environ.get("COMFY_OUTPUT", "")) if os.environ.get("COMFY_OUTPUT") else None,
                    Path(
                        r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\output"
                    ),
                    Path(
                        r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\output"
                    ),
                ):
                    if not base:
                        continue
                    cand = base / sub / filename if sub else base / filename
                    if cand.is_file():
                        return cand
    return None


def main() -> int:
    result: dict = {
        "mode": "minimal_i2v",
        "encoder": ENCODER,
        "width": WIDTH,
        "height": HEIGHT,
        "length": LENGTH,
        "prompt": PROMPT,
        "startImage": str(START),
    }
    if not START.is_file():
        result["ok"] = False
        result["error"] = f"missing start image {START}"
        (OUT / "wan-minimal-i2v.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 2

    # Hygiene: one diagnostic only
    try:
        call("POST", f"{COMFY}/interrupt", {})
    except Exception:
        pass
    call("POST", f"{COMFY}/queue", {"clear": True})
    call("POST", f"{COMFY}/free", {"unload_models": True, "free_memory": True})
    time.sleep(2)
    q = call("GET", f"{COMFY}/queue")
    result["queueBefore"] = {
        "running": len(q.get("queue_running") or []),
        "pending": len(q.get("queue_pending") or []),
    }

    start_name = upload_image(START)
    result["comfyStartImage"] = start_name
    wf = build_workflow(start_name)
    (OUT / "wan-minimal-workflow.json").write_text(json.dumps(wf, indent=2), encoding="utf-8")

    submit = call(
        "POST",
        f"{COMFY}/prompt",
        {"prompt": wf, "client_id": str(uuid.uuid4())},
    )
    pid = submit.get("prompt_id")
    result["promptId"] = pid
    result["submit"] = submit
    print("submitted", pid, flush=True)

    history = None
    for i in range(900):
        time.sleep(5)
        q = call("GET", f"{COMFY}/queue")
        running = q.get("queue_running") or []
        pending = q.get("queue_pending") or []
        owned = any(pid in str(x) for x in running + pending)
        print(
            i,
            "running",
            len(running),
            "pending",
            len(pending),
            "owned",
            owned,
            flush=True,
        )
        h = call("GET", f"{COMFY}/history/{pid}")
        if pid in h:
            history = h[pid]
            st = history.get("status") or {}
            if st.get("completed") or st.get("status_str") in {"error", "success"}:
                break
        # Stall detector: not owned and not in history after grace
        if i >= 6 and not owned and pid not in h:
            result["error"] = "prompt not claimed by Comfy worker (queue orphan)"
            break

    err = None
    for msg in (history or {}).get("status", {}).get("messages") or []:
        if isinstance(msg, list) and len(msg) >= 2 and msg[0] == "execution_error":
            err = msg[1]
    result["execution_error"] = err
    result["history_status"] = (history or {}).get("status")
    (OUT / "wan-minimal-history.json").write_text(
        json.dumps(history or {}, indent=2)[:500000], encoding="utf-8"
    )

    mp4 = find_output_mp4(history or {}) if history else None
    if mp4:
        dest = OUT / "wan-minimal-first.mp4"
        dest.write_bytes(mp4.read_bytes())
        result["mp4Source"] = str(mp4)
        result["mp4"] = str(dest)
        result["probe"] = ffprobe(dest)
        streams = (result["probe"].get("streams") or [])
        has_video = any(s.get("codec_type") == "video" for s in streams)
        dur = float((result["probe"].get("format") or {}).get("duration") or 0)
        result["ok"] = dest.stat().st_size > 10_000 and has_video and dur > 0.2
    else:
        result["ok"] = False
        if err:
            result["error"] = (err or {}).get("exception_message") or str(err)

    (OUT / "wan-minimal-i2v.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": result.get("ok"),
                "promptId": pid,
                "mp4": result.get("mp4"),
                "error": result.get("error")
                or ((err or {}).get("exception_message") if err else None),
            },
            indent=2,
        )
    )
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
