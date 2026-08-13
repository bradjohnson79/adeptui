"""Illustrious XL live smoke — real ComfyUI generations through the production builder.

This is the certification evidence-gathering step (Build Law #31). It uses the
exact ``build_txt2img_workflow`` builder that the ``illustrious.txt2img`` contract
routes to (via ``build_leaf_graph``), executing real GPU inference through
ComfyUI and capturing lineage + PNG artifacts. It does NOT bypass the builder —
it exercises the same graph the production path would build once Certified.

Outputs:
- artifacts/illustrious-smoke/*.png  (4 real generations)
- artifacts/illustrious-smoke/lineage.json  (model/checkpoint/seed/prompt per image)
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "studio-api"))

from app.comfy_client import comfy  # type: ignore
from app.config import settings  # type: ignore
from app.imagegen_workflows import build_txt2img_workflow  # type: ignore

OUT = REPO / "artifacts" / "illustrious-smoke"
OUT.mkdir(parents=True, exist_ok=True)

CHECKPOINT = settings.imagegen_illustrious_checkpoint
STEPS = settings.imagegen_illustrious_steps
CFG = settings.imagegen_illustrious_cfg

SMOKES = [
    {
        "label": "anime_character",
        "prompt": (
            "anime character, full body, a young warrior girl with silver hair, "
            "determined expression, detailed anime illustration, cel shading, "
            "clean line art, vibrant colors, studio quality"
        ),
        "negative": "blurry, low quality, watermark, text, deformed, extra limbs, bad anatomy",
        "width": 832,
        "height": 1216,
        "seed": 1001,
    },
    {
        "label": "animated_fantasy_character",
        "prompt": (
            "animated fantasy character, a forest spirit with glowing eyes and "
            "leafy cloak, stylized animation, expressive, rich background, "
            "cinematic anime lighting, high detail"
        ),
        "negative": "blurry, low quality, watermark, text, deformed, ugly",
        "width": 1024,
        "height": 1024,
        "seed": 2002,
    },
    {
        "label": "realistic_anime_character",
        "prompt": (
            "realistic anime illustration of a samurai, full body, anime character "
            "identity with clean stylized line work, cinematic materials, realistic "
            "lighting, believable fabrics and skin, atmospheric depth, the character "
            "remains visibly anime, not photoreal"
        ),
        "negative": "blurry, low quality, watermark, photoreal face, live-action recast, deformed",
        "width": 1024,
        "height": 1024,
        "seed": 3003,
    },
    {
        "label": "adept_chronicles_realistic_anime",
        "prompt": (
            "Adept Chronicles realistic anime style, a cinematic full-body shot of an "
            "anime heroine in a futuristic city, anime proportions and expressive eyes, "
            "realistic cinematic lighting, grounded materials, atmospheric environment, "
            "clean professional rendering, the character stays visibly anime/stylized"
        ),
        "negative": "blurry, low quality, watermark, fully photoreal, live-action actor, deformed, extra fingers",
        "width": 1280,
        "height": 720,
        "seed": 4004,
    },
]


async def _resilient_wait(prompt_id: str, timeout_sec: float = 900.0) -> dict:
    """Poll ComfyUI queue+history with a long per-request timeout.

    ComfyUI's /history can be slow to respond while a large checkpoint is
    loading, so we use a 120s per-request timeout (vs the default 30s) and
    poll every 3s. Raises if the prompt is absent from both queue and history
    after the deadline (i.e. it was rejected/removed without execution).
    """
    import httpx

    deadline = time.time() + timeout_sec
    base = settings.comfy_url.rstrip("/")
    last_queue = None
    while time.time() < deadline:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                qr = await client.get(f"{base}/queue")
                if qr.status_code == 200:
                    q = qr.json()
                    last_queue = q
                    running = q.get("queue_running") or []
                    pending = q.get("queue_pending") or []
                    in_queue = any(
                        (item.get("prompt") or [None, None])[1] == prompt_id
                        for item in (running + pending)
                    )
                    if in_queue:
                        await asyncio.sleep(3.0)
                        continue
        except Exception:
            pass
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                hr = await client.get(f"{base}/history/{prompt_id}")
                if hr.status_code == 200:
                    hist = hr.json()
                    if prompt_id in hist:
                        entry = hist[prompt_id]
                        st = entry.get("status") or {}
                        # ComfyUI status payload: {status: null, completed: true,
                        # status_str: "success", messages: [...]}. Treat completion
                        # (or any non-empty status_str) as terminal.
                        if st.get("completed") or st.get("status_str"):
                            return entry
        except Exception:
            pass
        await asyncio.sleep(3.0)
    raise RuntimeError(
        f"prompt {prompt_id} did not complete within {timeout_sec}s "
        f"(last_queue={last_queue})"
    )


async def run_one(spec: dict) -> dict:
    label = spec["label"]
    print(f"[illustrious-smoke] building graph for {label} ...", flush=True)
    wf = build_txt2img_workflow(
        checkpoint=CHECKPOINT,
        positive=spec["prompt"],
        negative=spec["negative"],
        width=spec["width"],
        height=spec["height"],
        seed=spec["seed"],
        steps=STEPS,
        cfg=CFG,
        filename_prefix=f"studio/illustrious_smoke_{label}",
    )
    # workflow_key=None skips the registry queueable gate (cert evidence step);
    # validate=True still confirms required node types exist in ComfyUI.
    t0 = time.time()
    prompt_id = await comfy.queue_prompt(wf, workflow_key=None, validate=True)
    print(f"[illustrious-smoke] {label} queued prompt_id={prompt_id}; waiting ...", flush=True)
    history = await _resilient_wait(prompt_id, timeout_sec=900.0)
    elapsed = round(time.time() - t0, 1)
    st = history.get("status") or {}
    status_str = st.get("status_str")
    if status_str and status_str != "success":
        raise RuntimeError(f"{label}: ComfyUI execution failed: {status_str} messages={st.get('messages')}")
    files = comfy.find_output_files(history)
    if not files:
        raise RuntimeError(f"{label}: no output files produced (status_str={status_str})")
    # Copy the first output into artifacts.
    saved = []
    for f in files:
        dest = OUT / f"{label}_{f.name}"
        dest.write_bytes(f.read_bytes())
        saved.append(str(dest))
    lineage = {
        "label": label,
        "model": "illustrious",
        "modelFamily": "illustrious",
        "checkpoint": CHECKPOINT,
        "workflowKey": "illustrious.txt2img",
        "builder": "build_txt2img_workflow",
        "seed": spec["seed"],
        "steps": STEPS,
        "cfg": CFG,
        "width": spec["width"],
        "height": spec["height"],
        "prompt": spec["prompt"],
        "negative": spec["negative"],
        "comfy_prompt_id": prompt_id,
        "elapsed_sec": elapsed,
        "outputs": saved,
    }
    print(f"[illustrious-smoke] {label} DONE in {elapsed}s -> {saved[0]}", flush=True)
    return lineage


async def main() -> None:
    # Preflight: confirm ComfyUI lists the Illustrious checkpoint.
    info = await comfy.object_info("CheckpointLoaderSimple")
    ckpts = info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
    if CHECKPOINT not in ckpts:
        raise RuntimeError(f"ComfyUI does not list checkpoint '{CHECKPOINT}' under CheckpointLoaderSimple")
    print(f"[illustrious-smoke] preflight OK: '{CHECKPOINT}' recognized by ComfyUI", flush=True)

    lineage_records = []
    for spec in SMOKES:
        rec = await run_one(spec)
        lineage_records.append(rec)

    (OUT / "lineage.json").write_text(json.dumps(lineage_records, indent=2), encoding="utf-8")
    print(f"[illustrious-smoke] ALL DONE — {len(lineage_records)} generations, lineage -> {OUT / 'lineage.json'}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
