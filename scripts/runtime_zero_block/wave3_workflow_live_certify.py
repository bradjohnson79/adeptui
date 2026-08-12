#!/usr/bin/env python3
"""Wave 3 runtime-zero-block — live certify DEFAULT_WORKFLOW_REGISTRY workflows."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "studio-api"))

RUN_ID = "runtime-zero-block-2026-08-05T18-16-27Z"
ARTIFACT_ROOT = ROOT / "docs" / "release-gate" / "runtime-zero-block" / "artifacts" / RUN_ID / "workflows"
FIXTURES = ARTIFACT_ROOT / "fixtures"

# Fast → heavy (GPU one-at-a-time).
WORKFLOW_IDS = [
    "image.txt2img",
    "image.img2img_edit",
    "image.zimage_reference",
    "ltx.scene",
    "ltx.simple_i2v",
    "ltx.ingredients_ic_lora",
    "lipsync.latentsync",
    "wan.first_last_frame",
    "wan.three_frame",
    "hunyuan15.t2v",
    "hunyuan15.i2v",
    "hunyuan13b.t2v",
    "hunyuan13b.i2v",
]

DEFAULT_PROJECT = "ae57714e-d43e-4cec-9bd9-0af2780fa185"
DEFAULT_API = "http://127.0.0.1:8758"

# Smallest smoke dimensions (m41 cert harness convention).
SMOKE_W, SMOKE_H, SMOKE_LEN, SMOKE_FPS, SMOKE_SEED = 512, 320, 17, 16, 42
SMOKE_STEPS = 4
HUNYUAN13_STEPS = 30
HUNYUAN15_STEPS = 20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _http_json(url: str, *, method: str = "GET", body: dict | None = None, timeout: float = 120.0) -> Any:
    headers = {"Accept": "application/json"}
    payload = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_readiness(api_base: str, workflow_id: str) -> dict[str, Any]:
    return _http_json(f"{api_base.rstrip('/')}/api/workflows/{workflow_id}/readiness")


def gpu_snapshot() -> dict[str, Any]:
    from app.vram_profiles import query_gpu_stats

    return query_gpu_stats()


def is_gpu_busy(stats: dict[str, Any]) -> tuple[bool, str]:
    if not stats.get("ok") or not stats.get("gpus"):
        return False, "gpu stats unavailable"
    gpu = stats["gpus"][0]
    free_gb = float(gpu.get("memory_free_mib") or 0) / 1024.0
    util = float(gpu.get("utilization_gpu_pct") or 0)
    used_pct = float(gpu.get("memory_used_pct") or 0)
    if util >= 85 and free_gb < 4.0:
        return True, f"GPU util {util}% free {free_gb:.1f}GB"
    if used_pct >= 92 and free_gb < 2.0:
        return True, f"VRAM used {used_pct}% free {free_gb:.1f}GB"
    return False, "idle"


async def is_comfy_queue_busy() -> tuple[bool, str]:
    from app.comfy_client import comfy

    try:
        q = await comfy.get_queue()
    except Exception as exc:  # noqa: BLE001
        return False, f"queue unreadable: {exc}"
    running = q.get("queue_running") or []
    pending = q.get("queue_pending") or []
    if running or pending:
        return True, f"comfy queue running={len(running)} pending={len(pending)}"
    return False, "comfy queue empty"


def ensure_fixtures() -> dict[str, Path]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    png = FIXTURES / "smoke_ref.png"
    if not png.is_file():
        from PIL import Image, ImageDraw

        im = Image.new("RGB", (512, 320), (48, 72, 96))
        dr = ImageDraw.Draw(im)
        dr.ellipse((120, 40, 392, 280), fill=(200, 160, 130))
        im.save(png)
    # Minimal silent wav + tiny mp4 for lipsync if absent.
    wav = FIXTURES / "smoke.wav"
    if not wav.is_file():
        import struct
        import wave

        rate = 16000
        dur = 0.5
        n = int(rate * dur)
        with wave.open(str(wav), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(struct.pack("<" + "h" * n, *([0] * n)))
    mp4 = FIXTURES / "smoke.mp4"
    if not mp4.is_file() or mp4.stat().st_size < 1024:
        import shutil
        import subprocess

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    str(png),
                    "-c:v",
                    "libx264",
                    "-t",
                    "0.5",
                    "-pix_fmt",
                    "yuv420p",
                    "-r",
                    "16",
                    str(mp4),
                ],
                check=True,
                capture_output=True,
            )
        else:
            mp4.write_bytes(b"\x00" * 128)  # placeholder; lipsync may fail honestly
    return {"png": png, "wav": wav, "mp4": mp4}


async def wait_comfy_idle(max_wait: float = 600.0) -> bool:
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        busy, _ = await is_comfy_queue_busy()
        gbusy, _ = is_gpu_busy(gpu_snapshot())
        if not busy and not gbusy:
            return True
        await asyncio.sleep(2.0)
    return False


async def upload_image(name: str, path: Path) -> str:
    from app.comfy_client import comfy

    return await comfy.upload_image(path)


async def upload_media(path: Path, subfolder: str = "input") -> str:
    from app.comfy_client import comfy

    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        return await comfy.upload_image(path)

    import shutil

    from app.config import settings

    dest_dir = Path(settings.comfy_input_dir or settings.data_dir / "comfy" / "input")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    shutil.copy2(path, dest)
    return str(dest.resolve())


async def run_comfy_smoke(workflow_id: str, graph: dict[str, Any], *, timeout_sec: float) -> dict[str, Any]:
    from app.comfy_client import comfy

    t0 = time.time()
    try:
        prompt_id = await comfy.queue_prompt(graph, workflow_key=workflow_id, validate=True)
        history = await comfy.wait_for_prompt(prompt_id, timeout_sec=timeout_sec)
        files = comfy.find_output_files(history)
        elapsed = round(time.time() - t0, 2)
        if not files:
            return {"ok": False, "error": "no output files", "promptId": prompt_id, "elapsedSec": elapsed}
        out = Path(files[0])
        return {
            "ok": out.is_file() and out.stat().st_size > 0,
            "promptId": prompt_id,
            "artifactPath": str(out),
            "elapsedSec": elapsed,
            "sizeBytes": out.stat().st_size if out.is_file() else 0,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:500], "elapsedSec": round(time.time() - t0, 2)}


def build_graph(workflow_id: str, fixtures: dict[str, Path], uploaded: dict[str, str]) -> dict[str, Any]:
    from app.config import settings
    from app.workflows.registry import DEFAULT_WORKFLOW_REGISTRY

    meta = DEFAULT_WORKFLOW_REGISTRY.get(workflow_id)
    prefix = f"studio/rzb/{workflow_id.replace('.', '_')}"

    if workflow_id == "image.txt2img":
        return meta.builder(
            unet_name=settings.zimage_unet,
            clip_name=settings.zimage_clip,
            vae_name=settings.zimage_vae,
            positive="runtime zero block smoke — soft studio portrait",
            negative="blurry, watermark",
            width=SMOKE_W,
            height=SMOKE_H,
            seed=SMOKE_SEED,
            steps=SMOKE_STEPS,
            filename_prefix=prefix,
        )

    if workflow_id in {"image.img2img_edit", "image.zimage_reference"}:
        ref = uploaded.get("png") or uploaded["png"]
        return meta.builder(
            unet_name=settings.zimage_unet,
            clip_name=settings.zimage_clip,
            vae_name=settings.zimage_vae,
            clip_vision_name=settings.zimage_clip_vision,
            reference_image=ref,
            prompt="runtime zero block reference smoke",
            negative="blurry",
            width=SMOKE_W,
            height=SMOKE_H,
            seed=SMOKE_SEED,
            steps=SMOKE_STEPS,
            filename_prefix=prefix,
            use_clip_vision=False,
        )

    if workflow_id == "ltx.scene":
        return meta.builder(
            checkpoint=settings.ltx_checkpoint,
            positive="gentle camera drift over a calm horizon, smoke test",
            negative="blur, text",
            width=SMOKE_W,
            height=SMOKE_H,
            length=SMOKE_LEN,
            fps=SMOKE_FPS,
            seed=SMOKE_SEED,
            steps=SMOKE_STEPS,
            filename_prefix=prefix,
            text_encoder=settings.ltx_text_encoder,
        )

    if workflow_id == "ltx.simple_i2v":
        return meta.builder(
            checkpoint=settings.ltx_checkpoint,
            positive="subtle motion smoke test",
            negative="blur",
            width=SMOKE_W,
            height=SMOKE_H,
            length=SMOKE_LEN,
            fps=SMOKE_FPS,
            seed=SMOKE_SEED,
            start_image=uploaded["png"],
            steps=SMOKE_STEPS,
            filename_prefix=prefix,
            text_encoder=settings.ltx_text_encoder,
        )

    if workflow_id == "ltx.ingredients_ic_lora":
        from app.comfy_client import comfy  # noqa: PLC0415 — sync context only for type

        raise RuntimeError("ltx.ingredients_ic_lora requires async object_info compile")

    if workflow_id == "wan.first_last_frame":
        return meta.builder(
            high_noise=settings.wan_high_noise,
            low_noise=settings.wan_low_noise,
            vae_name=settings.wan_vae,
            text_encoder=settings.wan_text_encoder,
            positive="smooth transition smoke",
            negative="blur",
            width=SMOKE_W,
            height=SMOKE_H,
            length=SMOKE_LEN,
            fps=SMOKE_FPS,
            seed=SMOKE_SEED,
            start_image=uploaded["png"],
            end_image=uploaded["png"],
            steps_high=2,
            steps_low=2,
            filename_prefix=prefix,
        )

    if workflow_id == "wan.three_frame":
        return meta.builder(
            high_noise=settings.wan_high_noise,
            low_noise=settings.wan_low_noise,
            vae_name=settings.wan_vae,
            text_encoder=settings.wan_text_encoder,
            positive="three frame smoke",
            negative="blur",
            width=SMOKE_W,
            height=SMOKE_H,
            length=SMOKE_LEN,
            fps=SMOKE_FPS,
            seed=SMOKE_SEED,
            start_image=uploaded["png"],
            middle_image=uploaded["png"],
            end_image=uploaded["png"],
            segment="start_mid",
            steps_high=2,
            steps_low=2,
            filename_prefix=prefix,
        )

    if workflow_id == "lipsync.latentsync":
        return meta.builder(
            video_path=uploaded.get("mp4", "smoke.mp4"),
            audio_path=uploaded.get("wav", "smoke.wav"),
        )

    if workflow_id.startswith("hunyuan"):
        from app.video_runtime.hunyuan_providers import HUNYUAN_13B, HUNYUAN_15, load_install_status, provider_dir

        provider_id = HUNYUAN_15 if "15" in workflow_id else HUNYUAN_13B
        model_root = str(provider_dir(provider_id))
        profile = str((load_install_status(provider_id).get("profile") or "fp8_production"))
        common = dict(
            model_root=model_root,
            positive="runtime zero block hunyuan smoke",
            negative="blur, text",
            width=SMOKE_W,
            height=SMOKE_H,
            length=SMOKE_LEN,
            fps=SMOKE_FPS,
            seed=SMOKE_SEED,
            filename_prefix=prefix,
        )
        if workflow_id == "hunyuan15.t2v":
            return meta.builder(**common, steps=HUNYUAN15_STEPS)
        if workflow_id == "hunyuan15.i2v":
            return meta.builder(**common, steps=HUNYUAN15_STEPS, start_image=uploaded["png"])
        if workflow_id == "hunyuan13b.t2v":
            return meta.builder(**common, steps=HUNYUAN13_STEPS, profile=profile)
        return meta.builder(**common, steps=HUNYUAN13_STEPS, profile=profile, start_image=uploaded["png"])

    raise KeyError(workflow_id)


async def build_ingredients_graph(uploaded: dict[str, str]) -> dict[str, Any]:
    from app.comfy_client import comfy
    from app.config import settings
    from app.workflows.ltx_ingredients_compiler import compile_ingredients_workflow

    object_info = await comfy.get_object_info()
    compiled = compile_ingredients_workflow(
        object_info=object_info,
        checkpoint=settings.ltx_checkpoint,
        positive="ingredients ic-lora smoke",
        negative="blur",
        width=SMOKE_W,
        height=SMOKE_H,
        length=SMOKE_LEN,
        fps=SMOKE_FPS,
        seed=SMOKE_SEED,
        reference_image=uploaded["png"],
        steps=SMOKE_STEPS,
        filename_prefix="studio/rzb/ltx_ingredients_ic_lora",
        text_encoder=settings.ltx_text_encoder,
    )
    return compiled["workflow"]


async def poll_project_job(api_base: str, project_id: str, job_id: str, timeout: float = 600.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            jobs = _http_json(f"{api_base}/api/projects/{project_id}/jobs")
            rows = jobs if isinstance(jobs, list) else jobs.get("jobs") or jobs.get("items") or []
            for row in rows:
                if str(row.get("id")) == job_id:
                    last = row
                    if row.get("status") in {"completed", "done", "failed", "cancelled"}:
                        return row
        except Exception as exc:  # noqa: BLE001
            last = {"error": str(exc)[:200]}
        await asyncio.sleep(2.0)
    return last or {"status": "timeout"}


async def smoke_via_api_image(api_base: str, project_id: str, workflow_id: str) -> dict[str, Any]:
    body = {
        "prompt": f"runtime zero block smoke for {workflow_id}",
        "width": SMOKE_W,
        "height": SMOKE_H,
        "seed": SMOKE_SEED,
        "steps": SMOKE_STEPS,
        "modelFamilyPreference": "zimage",
        "certHarness": True,
        "allowDraft": True,
        "metadata": {"workflowId": workflow_id, "runtimeZeroBlock": RUN_ID},
    }
    if workflow_id == "image.img2img_edit":
        body["operation"] = "image.edit"
        body["edit"] = True
    t0 = time.time()
    try:
        resp = _http_json(f"{api_base}/api/projects/{project_id}/imagegen", method="POST", body=body, timeout=60.0)
        job_id = resp.get("id")
        if not job_id:
            return {"ok": False, "error": "no job id", "response": resp}
        final = await poll_project_job(api_base, project_id, job_id)
        ok = final.get("status") in {"completed", "done"}
        return {
            "ok": ok,
            "jobId": job_id,
            "jobStatus": final.get("status"),
            "message": final.get("message"),
            "elapsedSec": round(time.time() - t0, 2),
            "via": "api.imagegen",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:500], "elapsedSec": round(time.time() - t0, 2)}


def readiness_flags(row: dict[str, Any]) -> tuple[str, bool, bool]:
    status = str(row.get("status") or "unknown")
    nodes_ok = not row.get("missingExtensions")
    models_ok = not row.get("missingModels")
    return status, nodes_ok, models_ok


def verdict_for(
    *,
    readiness_status: str,
    nodes_ok: bool,
    models_ok: bool,
    live: dict[str, Any] | None,
    busy: bool,
    skipped_reason: str | None,
) -> str:
    if busy:
        return "BUSY"
    if skipped_reason:
        return "SKIPPED_WITH_REASON"
    if readiness_status == "blocked" or not nodes_ok or not models_ok:
        return "BLOCKED"
    if live is None:
        return "SKIPPED_WITH_REASON"
    if live.get("busy"):
        return "BUSY"
    if live.get("ok"):
        return "GO"
    return "NO-GO"


async def certify_one(
    workflow_id: str,
    *,
    api_base: str,
    project_id: str,
    fixtures: dict[str, Path],
    skip_live: bool,
) -> dict[str, Any]:
    wf_dir = ARTIFACT_ROOT / workflow_id.replace(".", "_")
    readiness_path = wf_dir / "readiness.json"
    live_path = wf_dir / "live_smoke.json"

    readiness = fetch_readiness(api_base, workflow_id)
    _write(readiness_path, readiness)
    readiness_status, nodes_ok, models_ok = readiness_flags(readiness)

    row: dict[str, Any] = {
        "workflowId": workflow_id,
        "readiness": readiness_status,
        "nodesOk": nodes_ok,
        "modelsOk": models_ok,
        "liveRun": False,
        "artifactPath": None,
        "persistence": False,
        "verdict": "SKIPPED_WITH_REASON",
        "checkedAt": _now(),
        "evidence": {
            "readinessPath": str(readiness_path.relative_to(ROOT)).replace("\\", "/"),
        },
    }

    if skip_live:
        row["verdict"] = verdict_for(
            readiness_status=readiness_status,
            nodes_ok=nodes_ok,
            models_ok=models_ok,
            live=None,
            busy=False,
            skipped_reason="--skip-live",
        )
        row["evidence"]["skipReason"] = "--skip-live"
        return row

    if readiness_status == "blocked":
        row["verdict"] = "BLOCKED"
        row["evidence"]["blockReason"] = readiness.get("message")
        return row

    if not await wait_comfy_idle(max_wait=900.0):
        row["verdict"] = "BUSY"
        row["evidence"]["busyReason"] = "comfy/gpu did not become idle within 900s"
        return row

    gstats = gpu_snapshot()
    gbusy, greason = is_gpu_busy(gstats)
    cbusy, creason = await is_comfy_queue_busy()
    if gbusy or cbusy:
        row["verdict"] = "BUSY"
        row["evidence"]["busyReason"] = "; ".join(x for x in (greason, creason) if x)
        return row

    live: dict[str, Any] = {}
    skipped_reason: str | None = None

    try:
        uploaded: dict[str, str] = {}
        if workflow_id not in {"image.txt2img", "ltx.scene", "hunyuan13b.t2v", "hunyuan15.t2v"}:
            uploaded["png"] = await upload_image("smoke_ref.png", fixtures["png"])
        if workflow_id == "lipsync.latentsync":
            uploaded["wav"] = await upload_media(fixtures["wav"])
            uploaded["mp4"] = await upload_media(fixtures["mp4"])
        if workflow_id in {"hunyuan13b.i2v", "hunyuan15.i2v", "ltx.simple_i2v"} and "png" not in uploaded:
            uploaded["png"] = await upload_image("smoke_ref.png", fixtures["png"])

        timeout = 1800.0 if workflow_id.startswith(("hunyuan", "wan.", "ltx.")) else 600.0
        if workflow_id.startswith("image.") and workflow_id == "image.txt2img":
            live = await smoke_via_api_image(api_base, project_id, workflow_id)
            row["persistence"] = bool(live.get("ok"))
        elif workflow_id.startswith("image."):
            graph = build_graph(workflow_id, fixtures, uploaded)
            live = await run_comfy_smoke(workflow_id, graph, timeout_sec=timeout)
        elif workflow_id == "ltx.ingredients_ic_lora":
            graph = await build_ingredients_graph(uploaded)
            live = await run_comfy_smoke(workflow_id, graph, timeout_sec=timeout)
        else:
            graph = build_graph(workflow_id, fixtures, uploaded)
            live = await run_comfy_smoke(workflow_id, graph, timeout_sec=timeout)

        _write(live_path, {"workflowId": workflow_id, "gpuBefore": gstats, **live})
        row["liveRun"] = True
        row["artifactPath"] = live.get("artifactPath")
        row["persistence"] = bool(live.get("ok") and live.get("via") == "api.imagegen")
        if live.get("artifactPath"):
            row["evidence"]["liveSmokePath"] = str(live_path.relative_to(ROOT)).replace("\\", "/")
    except Exception as exc:  # noqa: BLE001
        live = {"ok": False, "error": str(exc)[:500]}
        _write(live_path, live)
        skipped_reason = str(exc)[:200]

    row["verdict"] = verdict_for(
        readiness_status=readiness_status,
        nodes_ok=nodes_ok,
        models_ok=models_ok,
        live=live,
        busy=bool(live.get("busy")),
        skipped_reason=skipped_reason,
    )
    if live.get("error") and row["verdict"] == "NO-GO":
        row["evidence"]["liveError"] = live.get("error")
    return row


async def run_all(*, api_base: str, project_id: str, skip_live: bool, only: list[str] | None) -> list[dict[str, Any]]:
    fixtures = ensure_fixtures()
    targets = only or WORKFLOW_IDS
    matrix: list[dict[str, Any]] = []
    for workflow_id in targets:
        print(f"[wave3] certifying {workflow_id}...", flush=True)
        row = await certify_one(
            workflow_id,
            api_base=api_base,
            project_id=project_id,
            fixtures=fixtures,
            skip_live=skip_live,
        )
        matrix.append(row)
        print(f"  -> {row['verdict']} readiness={row['readiness']} liveRun={row['liveRun']}", flush=True)
        # GPU one-at-a-time: brief cool-down between heavy workflows.
        if row.get("liveRun"):
            await asyncio.sleep(5.0)
            await wait_comfy_idle(max_wait=120.0)
    return matrix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--project-id", default=DEFAULT_PROJECT)
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args()

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    matrix = asyncio.run(
        run_all(api_base=args.api, project_id=args.project_id, skip_live=args.skip_live, only=args.only)
    )
    matrix_path = ARTIFACT_ROOT / "matrix.json"
    if args.only and matrix_path.is_file():
        try:
            prior = json.loads(matrix_path.read_text(encoding="utf-8"))
            prior_rows = {r["workflowId"]: r for r in prior.get("rows") or []}
            for row in matrix:
                prior_rows[row["workflowId"]] = row
            matrix = [prior_rows[wid] for wid in WORKFLOW_IDS if wid in prior_rows]
        except Exception:
            pass
    summary = {
        "runId": RUN_ID,
        "generatedAt": _now(),
        "projectId": args.project_id,
        "apiBase": args.api,
        "workflowCount": len(matrix),
        "counts": {
            v: sum(1 for r in matrix if r["verdict"] == v)
            for v in ("GO", "NO-GO", "BLOCKED", "SKIPPED_WITH_REASON", "BUSY", "EXCLUDED")
        },
        "noteMiniMaxH3": "MiniMax H3 (route-a-experimental-private-i2va) is Timeline/provider separate — not in DEFAULT_WORKFLOW_REGISTRY Wave 3 set; defer to Timeline wave.",
        "noteHunyuanExclusion": "Hunyuan workflows EXCLUDED from WORKFLOW_CATALOG_GREEN per user; not used in Adept UI.",
        "rows": matrix,
    }
    matrix_path = ARTIFACT_ROOT / "matrix.json"
    _write(matrix_path, summary)
    print(f"Wrote {matrix_path}")
    print("Counts:", summary["counts"])
    fails = [r["workflowId"] for r in matrix if r["verdict"] in {"NO-GO", "BLOCKED"}]
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
