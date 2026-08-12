"""Isolated ACE-Step music worker script (run under m210b-ace-venv).

Usage:
  python ace_step_worker.py --prompt "..." --duration 15 --out path.wav
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def _emit(payload: dict) -> None:
    print(json.dumps(payload), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--duration", type=float, default=15.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--checkpoint_dir", default="")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--device_id", type=int, default=0)
    ap.add_argument("--infer_step", type=int, default=18)
    ap.add_argument("--cpu_offload", type=int, default=-1, help="-1=auto, 0=off, 1=on")
    args = ap.parse_args()

    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.device_id)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    _emit({"phase": "boot", "msg": "Importing torch / ACE-Step"})

    # torchaudio>=2.9 routes save() through torchcodec (broken on this Windows env).
    # Patch save to write via soundfile so ACE-Step can finish after diffusion.
    import soundfile as sf
    import torch
    import torchaudio

    cuda = bool(torch.cuda.is_available())
    device_count = int(torch.cuda.device_count()) if cuda else 0
    if cuda:
        # Prefer GPU residency for Adept Audio Studio; CPU offload kept as fallback only.
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.set_float32_matmul_precision("high")
        torch.cuda.set_device(0)
        selected_device = "cuda:0"
        device_name = torch.cuda.get_device_name(0)
        bf16 = bool(getattr(torch.cuda, "is_bf16_supported", lambda: False)())
        dtype = "bfloat16" if bf16 else "float16"
        # Explicit Adept rule: when CUDA is available, never silent-offload to CPU.
        cpu_offload = False if args.cpu_offload != 1 else True
    else:
        selected_device = "cpu"
        device_name = "cpu"
        dtype = "float32"
        cpu_offload = True if args.cpu_offload < 0 else bool(args.cpu_offload)

    _emit(
        {
            "phase": "device",
            "cuda_available": cuda,
            "cuda": cuda,
            "device_count": device_count,
            "selected_device": selected_device,
            "device": device_name,
            "dtype": dtype,
            "cpu_offload": cpu_offload,
            "infer_step": int(args.infer_step),
            "duration": float(args.duration),
            "torch_version": torch.__version__,
        }
    )

    def _save_wav(path, tensor, sample_rate=48000, **kwargs):  # noqa: ANN001
        _ = kwargs
        arr = tensor.detach().cpu().float().numpy()
        if arr.ndim == 2 and arr.shape[0] <= 8:
            arr = arr.T  # channels-first -> frames x channels
        sf.write(str(path), arr, int(sample_rate))

    torchaudio.save = _save_wav  # type: ignore[method-assign]

    from acestep.pipeline_ace_step import ACEStepPipeline

    _emit(
        {
            "phase": "load_model",
            "msg": "Loading ACE-Step pipeline",
            "selected_device": selected_device,
            "cpu_offload": cpu_offload,
        }
    )
    pipe = ACEStepPipeline(
        checkpoint_dir=args.checkpoint_dir or "",
        dtype=dtype,
        torch_compile=False,
        cpu_offload=cpu_offload,
        overlapped_decode=False,
    )
    # Best-effort confirmation of model residency after load.
    model_device = selected_device
    try:
        for attr in ("ace_step", "model", "transformer", "unet", "diffusion_model"):
            mod = getattr(pipe, attr, None)
            if mod is None:
                continue
            params = list(getattr(mod, "parameters", lambda: [])())
            if params:
                model_device = str(params[0].device)
                break
    except Exception:
        pass
    _emit(
        {
            "phase": "model_device",
            "selected_device": selected_device,
            "model_device": model_device,
            "cpu_offload": cpu_offload,
            "cuda_available": cuda,
        }
    )
    # Instrumental ambient: empty lyrics keeps music-only role.
    lyrics = "[Instrumental]"
    infer_step = max(8, min(60, int(args.infer_step or 18)))
    _emit(
        {
            "phase": "generate",
            "msg": "Running diffusion",
            "infer_step": infer_step,
            "selected_device": selected_device,
            "cpu_offload": cpu_offload,
        }
    )
    result = pipe(
        audio_duration=float(args.duration),
        prompt=str(args.prompt),
        lyrics=lyrics,
        infer_step=infer_step,
        guidance_scale=15.0,
        scheduler_type="euler",
        cfg_type="apg",
        omega_scale=10.0,
        manual_seeds=str(args.seed),
        guidance_interval=0.5,
        guidance_interval_decay=0.0,
        min_guidance_scale=3.0,
        use_erg_tag=True,
        use_erg_lyric=False,
        use_erg_diffusion=True,
        oss_steps="",
        guidance_scale_text=0.0,
        guidance_scale_lyric=0.0,
        save_path=str(out),
    )
    # Pipeline may write its own path; ensure expected out exists.
    written = Path(str(result)) if result and Path(str(result)).is_file() else out
    if not written.is_file():
        # Search sibling outputs
        cands = list(out.parent.glob("*.wav")) + list(out.parent.glob("*.flac"))
        if not cands:
            print(json.dumps({"ok": False, "error": "no_audio_written"}), file=sys.stderr)
            return 2
        written = max(cands, key=lambda p: p.stat().st_mtime)
        if written.resolve() != out.resolve():
            import shutil

            shutil.copy2(written, out)
            written = out
    meta = {
        "ok": True,
        "path": str(out.resolve()),
        "bytes": out.stat().st_size,
        "provider": "ace-step",
        "capability": "music.generate",
        "cuda_available": cuda,
        "cuda": cuda,
        "device_count": device_count,
        "selected_device": selected_device,
        "device": device_name,
        "model_device": model_device,
        "dtype": dtype,
        "cpu_offload": cpu_offload,
        "infer_step": infer_step,
        "elapsedSec": round(time.time() - t0, 2),
    }
    print(json.dumps(meta), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
