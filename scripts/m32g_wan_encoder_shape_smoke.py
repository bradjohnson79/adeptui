"""M3.2g: shape-checked WAN text-encode smoke (no UNET).

Asserts:
  - encoder loads (Comfy CLIPLoader type=wan + authoritative file)
  - conditioning last-dim == 4096
  - tensor is non-zero / finite
  - no meta-device tensors
  - dtype/device recorded

Uses ComfyUI's own venv + load_clip so the contract matches runtime.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
ENCODER = os.environ.get(
    "STUDIO_WAN_TEXT_ENCODER", "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
)
EXPECTED_DIM = 4096
OUT = ROOT / "artifacts/m32g/hitchhiker-test-2/06-wan-readiness/wan-encoder-shape-smoke.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

COMFY_ROOT = Path(
    os.environ.get(
        "COMFYUI_ROOT",
        r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI",
    )
)
COMFY_PY = Path(
    os.environ.get(
        "COMFYUI_PYTHON",
        str(COMFY_ROOT / ".venv" / "Scripts" / "python.exe"),
    )
)
MODELS_ROOT = Path(
    os.environ.get(
        "COMFY_MODELS_ROOT",
        r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models",
    )
)

WORKER_SRC = r'''
import json, os, sys
os.environ.setdefault("CUDA_VISIBLE_DEVICES", os.environ.get("CUDA_VISIBLE_DEVICES", "0"))
comfy_root = sys.argv[1]
models_root = sys.argv[2]
encoder = sys.argv[3]
expected = int(sys.argv[4])
sys.path.insert(0, comfy_root)
os.chdir(comfy_root)

import folder_paths
# Point Comfy at Shared models (same as Desktop).
folder_paths.folder_names_and_paths["text_encoders"] = (
    [os.path.join(models_root, "text_encoders")],
    folder_paths.supported_pt_extensions,
)

import torch
from comfy.sd import CLIPType, load_clip

path = folder_paths.get_full_path_or_raise("text_encoders", encoder)
report = {"encoderPath": path, "expectedDim": expected}

clip = load_clip(ckpt_paths=[path], clip_type=CLIPType.WAN)
tokens = clip.tokenize("a hitchhiker on a rural road, dolly in, cinematic light")
cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
# cond: [1, seq, dim] or similar
t = cond
if isinstance(t, (list, tuple)):
    t = t[0]
if not torch.is_tensor(t):
    # Some paths wrap conditioning
    raise SystemExit(json.dumps({"ok": False, "error": f"unexpected cond type {type(cond)}"}))

shape = list(t.shape)
last = int(shape[-1])
is_meta = getattr(t, "is_meta", False) or str(t.device) == "meta"
finite = bool(torch.isfinite(t.float()).all().item()) if t.numel() and not is_meta else False
nonzero = bool((t.float().abs().sum() > 0).item()) if t.numel() and not is_meta else False

report.update({
    "ok": last == expected and nonzero and finite and not is_meta,
    "shape": shape,
    "lastDim": last,
    "dtype": str(t.dtype),
    "device": str(t.device),
    "isMeta": bool(is_meta),
    "finite": finite,
    "nonzero": nonzero,
    "numel": int(t.numel()),
    "pooledShape": list(pooled.shape) if torch.is_tensor(pooled) else None,
})
if last != expected:
    report["error"] = f"lastDim {last} != WAN contract {expected} (wrong encoder pairing)"
print(json.dumps(report))
'''


def post_json(url: str, body: dict, timeout: int = 120):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str, timeout: int = 60):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def comfy_api_encode_smoke() -> dict:
    """Secondary: ensure live Comfy server can CLIPLoader+encode without UNETs."""
    prompt = {
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": ENCODER, "type": "wan"},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "a hitchhiker on a rural road, dolly in, cinematic light",
                "clip": ["3", 0],
            },
        },
        "99": {"class_type": "PreviewAny", "inputs": {"source": ["5", 0]}},
    }
    out: dict = {"encoder": ENCODER}
    try:
        out["free"] = post_json(
            f"{COMFY}/free", {"unload_models": True, "free_memory": True}, timeout=180
        )
    except Exception as exc:  # noqa: BLE001
        out["free_error"] = str(exc)
    time.sleep(2)
    try:
        submit = post_json(
            f"{COMFY}/prompt", {"prompt": prompt, "client_id": str(uuid.uuid4())}
        )
        out["submit"] = submit
        pid = submit.get("prompt_id")
    except Exception as exc:  # noqa: BLE001
        out["submit_error"] = str(exc)
        out["ok"] = False
        return out
    history = None
    for _ in range(240):
        time.sleep(2)
        h = get_json(f"{COMFY}/history/{pid}")
        if pid in h:
            history = h[pid]
            st = history.get("status") or {}
            if st.get("completed") or st.get("status_str") in {"error", "success"}:
                break
    err = None
    for msg in (history or {}).get("status", {}).get("messages") or []:
        if isinstance(msg, list) and len(msg) >= 2 and msg[0] == "execution_error":
            err = msg[1]
    completed = bool((history or {}).get("status", {}).get("completed"))
    out["prompt_id"] = pid
    out["completed"] = completed
    out["execution_error"] = err
    out["ok"] = completed and not err
    return out


def local_shape_smoke() -> dict:
    if not COMFY_PY.is_file():
        return {"ok": False, "error": f"Comfy python missing: {COMFY_PY}"}
    proc = subprocess.run(
        [
            str(COMFY_PY),
            "-c",
            WORKER_SRC,
            str(COMFY_ROOT),
            str(MODELS_ROOT),
            ENCODER,
            str(EXPECTED_DIM),
        ],
        capture_output=True,
        text=True,
        cwd=str(COMFY_ROOT),
        timeout=600,
    )
    raw = (proc.stdout or "").strip().splitlines()
    last = raw[-1] if raw else ""
    try:
        payload = json.loads(last) if last.startswith("{") else {
            "ok": False,
            "error": "no json",
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
            "returncode": proc.returncode,
        }
    except json.JSONDecodeError:
        payload = {
            "ok": False,
            "error": "json decode failed",
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
            "returncode": proc.returncode,
        }
    payload["returncode"] = proc.returncode
    if proc.returncode != 0 and payload.get("ok") is not False:
        payload["ok"] = False
        payload.setdefault("stderr", proc.stderr[-2000:])
    return payload


def main() -> int:
    result = {
        "encoder": ENCODER,
        "expectedDim": EXPECTED_DIM,
        "comfy": COMFY,
        "formerFailure": {
            "error": "mat_a and mat_b shapes cannot be multiplied (154x768 and 4096x5120)",
            "producer": "CLIPTextEncode via CLIPLoader(umt5-xxl-enc-bf16, type=wan)",
            "consumer": "WAN text_embedding Linear(4096 -> 5120) inside KSamplerAdvanced",
        },
    }
    # Static contract (studio-api)
    sys.path.insert(0, str(ROOT / "studio-api"))
    from app.workflows.wan_encoder_contract import assert_wan_text_encoder_contract

    try:
        result["staticContract"] = assert_wan_text_encoder_contract(
            ENCODER,
            search_roots=[MODELS_ROOT],
            require_file_probe=True,
        )
    except Exception as exc:  # noqa: BLE001
        result["staticContract"] = {"ok": False, "error": str(exc)}
        result["ok"] = False
        result["status"] = "NOT_GREEN"
        OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"ok": False, "stage": "static", "error": str(exc)}, indent=2))
        return 2

    result["localShape"] = local_shape_smoke()
    # Only hit live Comfy if local shape passed (avoids fighting a busy GPU).
    if result["localShape"].get("ok"):
        result["comfyApiEncode"] = comfy_api_encode_smoke()
    else:
        result["comfyApiEncode"] = {"skipped": True, "reason": "local shape failed"}

    ok = bool(result["staticContract"].get("ok")) and bool(
        result["localShape"].get("ok")
    ) and bool(result.get("comfyApiEncode", {}).get("ok", False) or result.get("comfyApiEncode", {}).get("skipped"))
    # Require live Comfy encode when not skipped
    if not result.get("comfyApiEncode", {}).get("skipped"):
        ok = ok and bool(result["comfyApiEncode"].get("ok"))
    result["ok"] = ok
    result["status"] = "GREEN" if ok else "NOT_GREEN"
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": ok,
                "status": result["status"],
                "lastDim": result["localShape"].get("lastDim"),
                "shape": result["localShape"].get("shape"),
                "dtype": result["localShape"].get("dtype"),
                "device": result["localShape"].get("device"),
                "isMeta": result["localShape"].get("isMeta"),
                "comfyApiOk": result.get("comfyApiEncode", {}).get("ok"),
                "error": result["localShape"].get("error")
                or result.get("comfyApiEncode", {}).get("execution_error"),
                "evidence": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
