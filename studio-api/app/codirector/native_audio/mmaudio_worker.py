"""Isolated MMAudio SFX worker (run under m210b-sfx-venv).

Must be launched with cwd = MMAudio repo root (or --repo) so relative weight
paths in ModelConfig resolve correctly.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--duration", type=float, default=3.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--models-dir", default="")  # unused; weights live under repo
    ap.add_argument("--repo", default="")
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    repo = Path(args.repo) if args.repo else None
    if repo is None:
        # Default: sandbox provider checkout
        here = Path(__file__).resolve()
        # native_audio -> codirector -> app -> studio-api -> repo
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
        repo = candidate if candidate.is_dir() else Path.cwd()
    os.chdir(repo)
    sys.path.insert(0, str(repo))

    try:
        import numpy as np
        import soundfile as sf
        import torch
        from mmaudio.eval_utils import all_model_cfg, generate
        from mmaudio.model.flow_matching import FlowMatching
        from mmaudio.model.networks import get_my_mmaudio
        from mmaudio.model.utils.features_utils import FeaturesUtils
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"import_failed:{exc}"}), file=sys.stderr)
        return 2

    cfg_name = None
    for name in ("small_16k", "small_44k", "medium_44k", "large_44k"):
        if name in all_model_cfg:
            cfg_name = name
            break
    if cfg_name is None:
        print(json.dumps({"ok": False, "error": "no_model_cfg"}), file=sys.stderr)
        return 3

    model_cfg = all_model_cfg[cfg_name]
    model_cfg.download_if_needed()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device == "cuda" else torch.float32

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

    rng = torch.Generator(device=device).manual_seed(int(args.seed))
    fm = FlowMatching(min_sigma=0, inference_mode="euler", num_steps=25)

    # Duration: MMAudio uses fixed sequence configs; clamp prompt use to model window.
    # Text-only SFX generation (no video). Must stay in inference_mode because
    # FeaturesUtils.encode_* returns inference tensors.
    with torch.inference_mode():
        audio = generate(
            clip_video=None,
            sync_video=None,
            text=[str(args.prompt)],
            negative_text=[""],
            feature_utils=feature_utils,
            net=net,
            fm=fm,
            rng=rng,
            cfg_strength=4.5,
        )
    waveform = audio.float().cpu()
    # Expected shapes: [samples], [channels, samples], or [B, channels, samples]
    while waveform.dim() > 2:
        waveform = waveform[0]
    if waveform.dim() == 1:
        waveform = waveform.unsqueeze(0)
    sample_rate = 16000 if model_cfg.mode == "16k" else 44100

    # Trim/pad to requested duration when possible.
    target = int(float(args.duration) * sample_rate)
    if waveform.shape[-1] > target > 0:
        waveform = waveform[..., :target]
    arr = waveform.numpy()
    if arr.ndim == 2 and arr.shape[0] <= 8:
        arr = arr.T  # frames x channels for soundfile
    sf.write(str(out), arr.astype(np.float32), sample_rate)

    if not out.is_file() or out.stat().st_size < 1000:
        print(json.dumps({"ok": False, "error": "no_audio_written"}), file=sys.stderr)
        return 5
    print(
        json.dumps(
            {
                "ok": True,
                "path": str(out.resolve()),
                "bytes": out.stat().st_size,
                "provider": "mmaudio",
                "capability": "sfx.generate",
                "model": cfg_name,
                "sampleRate": sample_rate,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
