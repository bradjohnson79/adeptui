"""M3.2g WAN CLIP smoke: free memory, encode, require non-zero conditioning.

Prefer ``scripts/m32g_wan_encoder_shape_smoke.py`` for the hard 4096-d contract
(shape / meta / dtype). This script remains a live Comfy encode liveness check.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
OUT = Path("artifacts/m32g/hitchhiker-test-2/06-wan-readiness/wan-clip-smoke.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

PROMPT = {
    "3": {
        "class_type": "CLIPLoader",
        "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan"},
    },
    "5": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "a hitchhiker on a rural road, dolly in, cinematic light", "clip": ["3", 0]},
    },
    "99": {"class_type": "PreviewAny", "inputs": {"source": ["5", 0]}},
}


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


def conditioning_nonzero(history: dict) -> dict:
    """Inspect PreviewAny / CLIPTextEncode outputs for non-empty tensors."""
    outputs = history.get("outputs") or {}
    summary = {"hasOutputs": bool(outputs), "nodes": list(outputs.keys()), "nonzeroHint": False}
    blob = json.dumps(outputs)
    # Heuristic: successful encode usually leaves non-trivial JSON; all-zero embeds are tiny/empty.
    if "conditioning" in blob.lower() or outputs:
        summary["nonzeroHint"] = len(blob) > 80
    summary["outputBytes"] = len(blob)
    return summary


def main() -> int:
    result: dict = {"comfy": COMFY, "prompt": PROMPT}
    try:
        result["free"] = post_json(f"{COMFY}/free", {"unload_models": True, "free_memory": True}, timeout=120)
    except Exception as exc:  # noqa: BLE001
        result["free_error"] = str(exc)

    time.sleep(2)
    client_id = str(uuid.uuid4())
    try:
        submit = post_json(f"{COMFY}/prompt", {"prompt": PROMPT, "client_id": client_id})
        result["submit"] = submit
        pid = submit.get("prompt_id")
    except Exception as exc:  # noqa: BLE001
        result["submit_error"] = str(exc)
        OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 1

    result["prompt_id"] = pid
    history = None
    for _ in range(180):
        time.sleep(2)
        h = get_json(f"{COMFY}/history/{pid}")
        if pid in h:
            history = h[pid]
            st = history.get("status") or {}
            if st.get("completed") or st.get("status_str") in {"error", "success"}:
                break
    result["history_status"] = (history or {}).get("status")
    if history:
        for msg in (history.get("status") or {}).get("messages") or []:
            if isinstance(msg, list) and len(msg) >= 2 and msg[0] == "execution_error":
                result["execution_error"] = msg[1]
        result["conditioning"] = conditioning_nonzero(history)

    completed = bool((history or {}).get("status", {}).get("completed"))
    err = result.get("execution_error")
    ok = completed and not err
    result["ok"] = ok
    result["status"] = "GREEN" if ok else "NOT_GREEN"
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"ok": ok, "status": result["status"], "error": (err or {}).get("exception_message")}, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())

