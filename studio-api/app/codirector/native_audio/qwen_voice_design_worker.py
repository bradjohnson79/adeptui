"""Isolated worker for Qwen3-TTS VoiceDesign (official package only)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--voice-description", default="")
    args = parser.parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Official Qwen3-TTS API surface — fail honestly if package/weights missing.
        from qwen_tts import Qwen3TTSModel  # type: ignore
    except Exception as exc:
        print(f"Qwen3-TTS package not available: {exc}", file=sys.stderr)
        return 2

    models_dir = Path(args.models_dir)
    try:
        import numpy as np
        import soundfile as sf
        import torch

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
        print(f"loading Qwen3TTSModel device={device} dtype={dtype}", flush=True)
        model = Qwen3TTSModel.from_pretrained(
            str(models_dir),
            device_map=device,
            dtype=dtype,
        )
        print("model loaded; generating voice design", flush=True)
        # VoiceDesign path: natural-language voice description + spoken text.
        if hasattr(model, "generate_voice_design"):
            audio = model.generate_voice_design(
                text=args.text,
                language="English",
                instruct=args.voice_description or args.text,
            )
        else:
            audio = model.generate(
                text=args.text,
                language="English",
                instruct=args.voice_description or "",
            )
        sample_rate = 24000
        if isinstance(audio, tuple) and len(audio) == 2 and isinstance(audio[1], int):
            wavs, sample_rate = audio
            audio = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
        elif isinstance(audio, tuple):
            audio = audio[0]
        if isinstance(audio, (list, tuple)):
            audio = audio[0]
        arr = np.asarray(audio)
        if arr.ndim > 1:
            arr = arr.reshape(-1)
        if arr.dtype != np.int16:
            peak = float(np.max(np.abs(arr))) or 1.0
            arr = (arr / peak * 0.9 * 32767.0).astype(np.int16)
        sf.write(str(out), arr, int(sample_rate), subtype="PCM_16")
        print(f"wrote {out} sr={sample_rate} samples={arr.size}", flush=True)
    except Exception as exc:
        print(f"Qwen VoiceDesign inference failed: {exc}", file=sys.stderr)
        return 3

    if not out.is_file() or out.stat().st_size < 1000:
        print("Qwen VoiceDesign produced no usable WAV", file=sys.stderr)
        return 4
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
