"""Queue one real Qwen-Image-2512 ComfyUI txt2img smoke (no mock)."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from app.workflows.qwen_image_2512 import build_qwen_2512_txt2img_workflow

ART = Path(__file__).resolve().parents[1] / "artifacts" / "m42" / "w43-qwen-2512" / "runtime"
COMFY = "http://127.0.0.1:8188"


def _get(path: str):
    return json.load(urllib.request.urlopen(f"{COMFY}{path}", timeout=60))


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    unets = _get("/object_info/UNETLoader")["UNETLoader"]["input"]["required"]["unet_name"][0]
    clips = _get("/object_info/CLIPLoader")["CLIPLoader"]["input"]["required"]["clip_name"][0]
    vaes = _get("/object_info/VAELoader")["VAELoader"]["input"]["required"]["vae_name"][0]
    unet = next((u for u in unets if "qwen_image_2512" in u.lower()), None)
    clip = next((c for c in clips if "qwen_2.5_vl" in c.lower()), None)
    vae = next((v for v in vaes if "qwen_image_vae" in v.lower()), None)
    probe = {"unet": unet, "clip": clip, "vae": vae}
    (ART / "qwen_2512_model_probe_live.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
    print("PROBE", probe)
    if not all([unet, clip, vae]):
        print("models not visible to Comfy — restart ComfyUI after install")
        return 2

    wf = build_qwen_2512_txt2img_workflow(
        unet_name=unet,
        clip_name=clip,
        vae_name=vae,
        positive=(
            "A simple studio portrait of a young woman with black twin ponytails and purple eyes, "
            "soft light, plain gray background"
        ),
        negative="blurry, watermark, text, logo",
        width=1024,
        height=1024,
        seed=42,
        steps=8,
        cfg=4.0,
        filename_prefix="studio/qwen2512_smoke",
    )
    req = urllib.request.Request(
        f"{COMFY}/prompt",
        data=json.dumps({"prompt": wf, "client_id": "adept-qwen2512-smoke"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        res = json.load(urllib.request.urlopen(req, timeout=120))
    except Exception as exc:
        (ART / "qwen_2512_queue_attempt.json").write_text(
            json.dumps({"ok": False, "error": str(exc), "mock": False}, indent=2),
            encoding="utf-8",
        )
        print("QUEUE FAIL", exc)
        return 3

    prompt_id = res.get("prompt_id")
    print("QUEUED", prompt_id)
    (ART / "qwen_2512_queue_attempt.json").write_text(
        json.dumps({"ok": True, "prompt_id": prompt_id, "mock": False}, indent=2),
        encoding="utf-8",
    )

    hist = None
    deadline = time.time() + 900
    while time.time() < deadline:
        h = _get(f"/history/{prompt_id}")
        if prompt_id in h:
            hist = h[prompt_id]
            break
        time.sleep(2)
    if not hist:
        print("timeout waiting for history")
        return 4

    (ART / "qwen_2512_history.json").write_text(json.dumps(hist, indent=2)[:200000], encoding="utf-8")
    images = []
    for _node, out in (hist.get("outputs") or {}).items():
        images.extend(out.get("images") or [])
    print("IMAGES", images)
    (ART / "qwen_2512_outputs.json").write_text(
        json.dumps({"images": images, "mock": False}, indent=2),
        encoding="utf-8",
    )
    if not images:
        return 5

    im = images[0]
    q = urllib.parse.urlencode(
        {
            "filename": im.get("filename") or "",
            "subfolder": im.get("subfolder") or "",
            "type": im.get("type") or "output",
        }
    )
    data = urllib.request.urlopen(f"{COMFY}/view?{q}", timeout=120).read()
    out_path = ART / "qwen_2512_smoke.png"
    out_path.write_bytes(data)
    print("WROTE", out_path, len(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
