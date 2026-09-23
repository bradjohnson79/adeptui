"""Isolated worker for Qwen3-TTS Base voice cloning (official package only).

`--serve` keeps the clone model warm and accepts JSONL jobs on stdin so
Voice Studio does not reload 1.7B for every sample. One-shot CLI remains
available. Creator transcript is optional — the recording is the voice
reference; Qwen may take ref_text=None.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def _to_int16(audio: Any, np: Any) -> tuple[Any, int]:
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
    return arr, int(sample_rate)


def _write_wav(path: Path, arr: Any, sample_rate: int) -> None:
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), arr, int(sample_rate), subtype="PCM_16")


def _load_model(models_dir: Path, *, require_cuda: bool):
    import torch
    from qwen_tts import Qwen3TTSModel  # type: ignore

    if require_cuda and not torch.cuda.is_available():
        raise RuntimeError("Qwen3-TTS Voice Clone needs a CUDA GPU. CPU was not used.")
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    if require_cuda and not device.startswith("cuda"):
        raise RuntimeError("Qwen3-TTS Voice Clone needs a CUDA GPU. CPU was not used.")
    dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
    print(f"loading Qwen3TTSModel device={device} dtype={dtype}", flush=True)
    model = Qwen3TTSModel.from_pretrained(str(models_dir), device_map=device, dtype=dtype)
    print("model loaded; generating voice clone", flush=True)
    return model, device


def _synthesize(model: Any, *, text: str, ref_audio: str, ref_text: str, seed: int | None, prompt_cache: dict[str, Any] | None = None) -> Any:
    import torch

    if seed is not None:
        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(seed))
    transcript = (ref_text or "").strip() or None
    # ICL needs a transcript of the recording. Voice Studio no longer asks the
    # creator for one. Use the recording as a speaker embedding instead.
    x_vector_only = transcript is None
    cache_key = f"{ref_audio}|{transcript or ''}|{int(x_vector_only)}"
    prompt = None
    if prompt_cache is not None and cache_key in prompt_cache:
        prompt = prompt_cache[cache_key]
    elif hasattr(model, "create_voice_clone_prompt"):
        prompt = model.create_voice_clone_prompt(
            ref_audio=ref_audio,
            ref_text=transcript,
            x_vector_only_mode=x_vector_only,
        )
        if prompt_cache is not None:
            prompt_cache[cache_key] = prompt
    if hasattr(model, "generate_voice_clone"):
        if prompt is not None:
            return model.generate_voice_clone(
                text=text,
                language="English",
                voice_clone_prompt=prompt,
            )
        return model.generate_voice_clone(
            text=text,
            language="English",
            ref_audio=ref_audio,
            ref_text=transcript,
            x_vector_only_mode=x_vector_only,
        )
    return model.generate(
        text=text,
        language="English",
        ref_audio=ref_audio,
        ref_text=transcript or "",
    )


def _serve(models_dir: Path) -> int:
    try:
        import numpy as np
    except Exception as exc:
        print(json.dumps({"type": "error", "message": f"numpy unavailable: {exc}"}), flush=True)
        return 2
    try:
        model, device = _load_model(models_dir, require_cuda=True)
    except Exception as exc:
        print(json.dumps({"type": "error", "message": str(exc)}), flush=True)
        return 3
    print(json.dumps({"type": "ready", "device": device, "streaming": False}), flush=True)
    prompt_cache: dict[str, Any] = {}
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            job = json.loads(line)
        except Exception as exc:
            print(json.dumps({"type": "error", "message": f"invalid job: {exc}"}), flush=True)
            continue
        if job.get("cmd") == "ping":
            print(json.dumps({"type": "pong", "id": job.get("id"), "device": device}), flush=True)
            continue
        job_id = str(job.get("id") or "")
        out = Path(str(job.get("output") or ""))
        ref = Path(str(job.get("reference_audio") or ""))
        started = time.perf_counter()
        try:
            if not ref.is_file():
                raise RuntimeError(f"Reference audio missing: {ref}")
            audio = _synthesize(
                model,
                text=str(job.get("text") or ""),
                ref_audio=str(ref),
                ref_text=str(job.get("reference_transcript") or ""),
                seed=job.get("seed"),
                prompt_cache=prompt_cache,
            )
            arr, sr = _to_int16(audio, np)
            _write_wav(out, arr, sr)
            if not out.is_file() or out.stat().st_size < 1000:
                raise RuntimeError("Qwen VoiceClone produced no usable WAV")
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            print(
                json.dumps(
                    {
                        "type": "done",
                        "id": job_id,
                        "path": str(out),
                        "sr": sr,
                        "samples": int(arr.size),
                        "first_audio_ms": elapsed_ms,
                        "complete_ms": elapsed_ms,
                        "streaming": False,
                        "device": device,
                    }
                ),
                flush=True,
            )
        except Exception as exc:
            print(json.dumps({"type": "error", "id": job_id, "message": str(exc)}), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models-dir", required=True)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--text", default="")
    parser.add_argument("--reference-audio", default="")
    parser.add_argument("--reference-transcript", default="")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    models_dir = Path(args.models_dir)

    if args.serve:
        try:
            from qwen_tts import Qwen3TTSModel  # noqa: F401
        except Exception as exc:
            print(json.dumps({"type": "error", "message": f"Qwen3-TTS package not available: {exc}"}), flush=True)
            return 2
        return _serve(models_dir)

    if not args.output or not args.text or not args.reference_audio:
        print("Qwen VoiceClone one-shot requires --output, --text, and --reference-audio", file=sys.stderr)
        return 2
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    ref = Path(args.reference_audio)
    if not ref.is_file():
        print(f"Reference audio missing: {ref}", file=sys.stderr)
        return 2
    try:
        from qwen_tts import Qwen3TTSModel  # noqa: F401
    except Exception as exc:
        print(f"Qwen3-TTS package not available: {exc}", file=sys.stderr)
        return 2
    try:
        import numpy as np

        model, _device = _load_model(models_dir, require_cuda=True)
        audio = _synthesize(
            model,
            text=args.text,
            ref_audio=str(ref),
            ref_text=args.reference_transcript,
            seed=args.seed,
        )
        arr, sample_rate = _to_int16(audio, np)
        _write_wav(out, arr, sample_rate)
        print(f"wrote {out} sr={sample_rate} samples={arr.size}", flush=True)
    except Exception as exc:
        print(f"Qwen VoiceClone inference failed: {exc}", file=sys.stderr)
        return 3
    if not out.is_file() or out.stat().st_size < 1000:
        print("Qwen VoiceClone produced no usable WAV", file=sys.stderr)
        return 4
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
