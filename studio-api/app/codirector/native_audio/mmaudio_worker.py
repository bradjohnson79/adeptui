"""Isolated MMAudio SFX worker (run under m210b-sfx-venv).

Must be launched with cwd = MMAudio repo root (or --repo) so relative weight
paths in ModelConfig resolve correctly.

One-shot CLI remains the fallback. `--serve` keeps the model + encoders warm
and accepts JSONL jobs on stdin so take 2 / next SFX skip full reload.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def _resolve_repo(repo_arg: str) -> Path:
    if repo_arg:
        return Path(repo_arg)
    here = Path(__file__).resolve()
    root = here.parents[4]
    candidate = (
        root
        / "data"
        / "m210b-sandbox"
        / "providers"
        / "m2101-sfx-031"
        / "src"
        / "MMAudio"
    )
    return candidate if candidate.is_dir() else Path.cwd()


def _energy_crop(arr: Any, sample_rate: int, duration: float, np: Any, event_count: int | None = None) -> Any:
    """Keep a duration-length window from the MMAudio ~8s emit.

    ORDER14: when eventCount is present and > 1, duration is an event canvas —
    do NOT treat it as trim-only to a single peak (leading window preserves
    multi-event spacing). eventCount == 1 (or unset) keeps peak energy crop.
    """
    target = int(float(duration) * int(sample_rate))
    if target <= 0:
        return arr
    frames = arr.shape[0]
    if frames <= target:
        return arr
    try:
        ec = int(event_count) if event_count is not None else None
    except (TypeError, ValueError):
        ec = None
    if ec is not None and ec > 1:
        # Multi-event: leading trim — honor full duration canvas, not single peak.
        return arr[:target]
    mono = arr.mean(axis=1) if getattr(arr, "ndim", 1) == 2 else arr
    energy = np.square(mono.astype("float64"))
    csum = np.cumsum(energy)
    window = csum[target - 1 :].copy()
    if window.size > 1:
        window[1:] = csum[target:] - csum[:-target]
    start = int(np.argmax(window))
    return arr[start : start + target]


def _enable_safe_accelerators(torch: Any, device: str) -> dict[str, Any]:
    flags = {
        "bf16": device == "cuda",
        "inferenceMode": True,
        "tf32": False,
        "cudnnBenchmark": False,
        "torchCompile": False,
        "flashAttentionForced": False,
    }
    if device == "cuda":
        try:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            flags["tf32"] = True
        except Exception:
            pass
        try:
            torch.backends.cudnn.benchmark = True
            flags["cudnnBenchmark"] = True
        except Exception:
            pass
    return flags


def _load_stack(repo: Path) -> dict[str, Any]:
    os.chdir(repo)
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    import numpy as np
    import soundfile as sf
    import torch
    from mmaudio.eval_utils import all_model_cfg, generate
    from mmaudio.model.flow_matching import FlowMatching
    from mmaudio.model.networks import get_my_mmaudio
    from mmaudio.model.utils.features_utils import FeaturesUtils

    cfg_name = None
    for name in ("small_16k", "small_44k", "medium_44k", "large_44k"):
        if name in all_model_cfg:
            cfg_name = name
            break
    if cfg_name is None:
        raise RuntimeError("no_model_cfg")

    model_cfg = all_model_cfg[cfg_name]
    model_cfg.download_if_needed()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    accel = _enable_safe_accelerators(torch, device)

    net = get_my_mmaudio(model_cfg.model_name).to(device, dtype).eval()
    weights = torch.load(model_cfg.model_path, map_location=device, weights_only=True)
    net.load_weights(weights)
    net.update_seq_lengths(
        model_cfg.seq_cfg.latent_seq_len,
        model_cfg.seq_cfg.clip_seq_len,
        model_cfg.seq_cfg.sync_seq_len,
    )

    feature_utils = FeaturesUtils(
        tod_vae_ckpt=model_cfg.vae_path,
        synchformer_ckpt=model_cfg.synchformer_ckpt,
        enable_conditions=True,
        mode=model_cfg.mode,
        bigvgan_vocoder_ckpt=model_cfg.bigvgan_16k_path,
        need_vae_encoder=False,
    )
    feature_utils = feature_utils.to(device, dtype).eval()
    sample_rate = 16000 if model_cfg.mode == "16k" else 44100
    return {
        "np": np,
        "sf": sf,
        "torch": torch,
        "generate": generate,
        "FlowMatching": FlowMatching,
        "net": net,
        "feature_utils": feature_utils,
        "device": device,
        "dtype": str(dtype),
        "model": cfg_name,
        "sample_rate": sample_rate,
        "accelerators": accel,
    }


def _run_job(stack: dict[str, Any], *, prompt: str, negative: str, duration: float, seed: int, out: Path, cfg_strength: float, event_count: int | None = None) -> dict[str, Any]:
    torch = stack["torch"]
    np = stack["np"]
    sf = stack["sf"]
    generate = stack["generate"]
    FlowMatching = stack["FlowMatching"]
    device = stack["device"]
    out.parent.mkdir(parents=True, exist_ok=True)

    infer_started = time.perf_counter()
    rng = torch.Generator(device=device).manual_seed(int(seed))
    fm = FlowMatching(min_sigma=0, inference_mode="euler", num_steps=25)
    neg = str(negative or "").strip()
    with torch.inference_mode():
        audio = generate(
            clip_video=None,
            sync_video=None,
            text=[str(prompt)],
            negative_text=[neg],
            feature_utils=stack["feature_utils"],
            net=stack["net"],
            fm=fm,
            rng=rng,
            cfg_strength=float(cfg_strength or 4.5),
        )
    infer_ms = int((time.perf_counter() - infer_started) * 1000)

    save_started = time.perf_counter()
    waveform = audio.float().cpu()
    while waveform.dim() > 2:
        waveform = waveform[0]
    if waveform.dim() == 1:
        waveform = waveform.unsqueeze(0)
    arr = waveform.numpy()
    if arr.ndim == 2 and arr.shape[0] <= 8:
        arr = arr.T
    arr = _energy_crop(arr, stack["sample_rate"], duration, np, event_count=event_count)
    sf.write(str(out), arr.astype(np.float32), stack["sample_rate"])
    save_ms = int((time.perf_counter() - save_started) * 1000)

    if not out.is_file() or out.stat().st_size < 1000:
        raise RuntimeError("no_audio_written")
    return {
        "ok": True,
        "path": str(out.resolve()),
        "bytes": out.stat().st_size,
        "provider": "mmaudio",
        "capability": "sfx.generate",
        "model": stack["model"],
        "sampleRate": stack["sample_rate"],
        "device": device,
        "inferenceMs": infer_ms,
        "saveMs": save_ms,
        "cfgStrength": float(cfg_strength or 4.5),
        "negativeUsed": bool(neg),
        "crop": "energy",
        "accelerators": stack["accelerators"],
    }


def _serve(repo: Path) -> int:
    load_started = time.perf_counter()
    try:
        stack = _load_stack(repo)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"type": "error", "message": f"load_failed:{exc}"}), flush=True)
        return 3
    load_ms = int((time.perf_counter() - load_started) * 1000)
    print(
        json.dumps(
            {
                "type": "ready",
                "device": stack["device"],
                "model": stack["model"],
                "loadMs": load_ms,
                "accelerators": stack["accelerators"],
                "warm": True,
            }
        ),
        flush=True,
    )
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            job = json.loads(line)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"type": "error", "message": f"invalid job: {exc}"}), flush=True)
            continue
        cmd = str(job.get("cmd") or "")
        if cmd == "ping":
            print(json.dumps({"type": "pong", "id": job.get("id"), "device": stack["device"]}), flush=True)
            continue
        if cmd == "unload":
            print(json.dumps({"type": "unloaded", "device": stack["device"]}), flush=True)
            return 0
        job_id = str(job.get("id") or "")
        started = time.perf_counter()
        try:
            result = _run_job(
                stack,
                prompt=str(job.get("prompt") or ""),
                negative=str(job.get("negative") or ""),
                duration=float(job.get("duration") or 3.0),
                seed=int(job.get("seed") or 42),
                out=Path(str(job.get("out") or "")),
                cfg_strength=float(job.get("cfg_strength") or 4.5),
                event_count=(int(job["event_count"]) if job.get("event_count") is not None else None),
            )
            result.update(
                {
                    "type": "done",
                    "id": job_id,
                    "warm": True,
                    "totalMs": int((time.perf_counter() - started) * 1000),
                }
            )
            print(json.dumps(result), flush=True)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"type": "error", "id": job_id, "message": str(exc)}), flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="")
    ap.add_argument("--duration", type=float, default=3.0)
    ap.add_argument("--out", default="")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--models-dir", default="")
    ap.add_argument("--repo", default="")
    ap.add_argument("--negative", default="")
    ap.add_argument("--event-count", type=int, default=None)
    ap.add_argument("--cfg-strength", type=float, default=4.5)
    ap.add_argument("--serve", action="store_true")
    args = ap.parse_args()

    repo = _resolve_repo(args.repo)
    if args.serve:
        return _serve(repo)
    if not str(args.prompt).strip() or not str(args.out).strip():
        print(json.dumps({"ok": False, "error": "prompt_and_out_required"}), file=sys.stderr)
        return 2

    try:
        stack = _load_stack(repo)
        result = _run_job(
            stack,
            prompt=str(args.prompt),
            negative=str(args.negative or ""),
            duration=float(args.duration),
            seed=int(args.seed),
            out=Path(args.out),
            cfg_strength=float(args.cfg_strength),
            event_count=(int(args.event_count) if getattr(args, "event_count", None) is not None else None),
        )
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
