"""Standalone IndexTTS2 worker entrypoint.

This script is executed by the isolated runtime python environment, not by the
main Adept API environment. Keep dependencies minimal until runtime import time.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

PROVIDER_ID = "index-tts2-local"
REQUIRED_MODEL_FILES = (
    "config.yaml",
    "bpe.model",
    "gpt.pth",
    "s2mel.pth",
    "wav2vec2bert_stats.pt",
    "feat1.pt",
    "feat2.pt",
)
REQUIRED_MODEL_DIRS = ("qwen0.6bemo4-merge",)
REQUIRED_AUX_MODEL_FILES = (
    "hf_cache/semantic_codec_model.safetensors",
    "hf_cache/campplus_cn_common.bin",
    "hf_cache/bigvgan/config.json",
    "hf_cache/bigvgan/bigvgan_generator.pt",
)
REQUIRED_AUX_MODEL_DIRS = ("hf_cache/w2v-bert-2.0",)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _missing_model_resources(model_dir: Path) -> list[str] | None:
    if not model_dir.is_dir():
        return ["model directory does not exist"]
    missing = [name for name in REQUIRED_MODEL_FILES if not (model_dir / name).is_file()]
    missing.extend(name for name in REQUIRED_MODEL_DIRS if not (model_dir / name).is_dir())
    missing.extend(name for name in REQUIRED_AUX_MODEL_FILES if not (model_dir / name).is_file())
    missing.extend(name for name in REQUIRED_AUX_MODEL_DIRS if not (model_dir / name).is_dir())
    return missing


def _health_payload(
    *,
    ok: bool,
    code: str | None,
    message: str,
    model_dir: Path,
    repo_dir: Path | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "ok": ok,
        "installed": ok,
        "runtimeReady": ok,
        "providerId": PROVIDER_ID,
        "code": code,
        "message": message,
        "modelDir": str(model_dir),
        "repoDir": str(repo_dir) if repo_dir else None,
        "checkedAt": _now(),
        "details": dict(details or {}),
    }
    return payload


def _probe_runtime(model_dir: Path, repo_dir: Path | None, *, allow_cpu_fallback: bool) -> tuple[int, dict[str, Any]]:
    missing = _missing_model_resources(model_dir)
    if missing:
        return 2, _health_payload(
            ok=False,
            code="INDEX_TTS2_MODELS_MISSING",
            message="IndexTTS2 model resources are incomplete.",
            model_dir=model_dir,
            repo_dir=repo_dir,
            details={"missing": missing},
        )

    if repo_dir and str(repo_dir) not in sys.path:
        sys.path.insert(0, str(repo_dir))

    try:
        import torch
        import torchaudio  # noqa: F401
        import indextts  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return 3, _health_payload(
            ok=False,
            code="INDEX_TTS2_RUNTIME_IMPORT_FAILED",
            message=f"IndexTTS2 runtime import failed: {exc}",
            model_dir=model_dir,
            repo_dir=repo_dir,
        )

    device = "cpu"
    cuda_available = bool(torch.cuda.is_available())
    if cuda_available:
        device = "cuda:0"
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        device = "mps"

    if device == "cpu" and not allow_cpu_fallback:
        return 4, _health_payload(
            ok=False,
            code="INDEX_TTS2_CPU_FALLBACK_REQUIRES_APPROVAL",
            message=(
                "IndexTTS2 would run on CPU in the active environment. CPU fallback is blocked unless explicitly approved."
            ),
            model_dir=model_dir,
            repo_dir=repo_dir,
            details={"device": device, "cudaAvailable": cuda_available},
        )

    payload = _health_payload(
        ok=True,
        code=None,
        message="IndexTTS2 runtime is ready.",
        model_dir=model_dir,
        repo_dir=repo_dir,
        details={
            "device": device,
            "cudaAvailable": cuda_available,
            "torchVersion": getattr(torch, "__version__", None),
            "torchaudioVersion": getattr(sys.modules.get("torchaudio"), "__version__", None),
        },
    )
    payload["installed"] = True
    payload["runtimeReady"] = True
    payload["device"] = device
    payload["cudaAvailable"] = cuda_available
    payload["torchVersion"] = getattr(torch, "__version__", None)
    return 0, payload


def _adapter_process(args: argparse.Namespace) -> int:
    model_dir = Path(args.model_dir).expanduser().resolve()
    repo_dir = Path(args.repo_dir).expanduser().resolve() if args.repo_dir else None
    code, payload = _probe_runtime(model_dir, repo_dir, allow_cpu_fallback=args.allow_cpu_fallback)
    if args.health_json:
        _write_json(Path(args.health_json), payload)
    if code != 0:
        print(json.dumps(payload, ensure_ascii=False), flush=True)
        return code
    print(json.dumps({"providerId": PROVIDER_ID, "status": "running", "checkedAt": _now()}, ensure_ascii=False), flush=True)
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        return 0


def _run_health(args: argparse.Namespace) -> int:
    model_dir = Path(args.model_dir).expanduser().resolve()
    repo_dir = Path(args.repo_dir).expanduser().resolve() if args.repo_dir else None
    code, payload = _probe_runtime(model_dir, repo_dir, allow_cpu_fallback=args.allow_cpu_fallback)
    _write_json(Path(args.health_json), payload)
    if not payload.get("ok"):
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return code


def _run_job(args: argparse.Namespace) -> int:
    job_path = Path(args.job_json).expanduser().resolve()
    job = _read_json(job_path)
    if not job:
        error = {
            "ok": False,
            "status": "failed",
            "error": {"code": "INDEX_TTS2_JOB_JSON_MISSING", "message": f"Job file not found: {job_path}"},
            "finishedAt": _now(),
        }
        _write_json(job_path, error)
        print(json.dumps(error, ensure_ascii=False), file=sys.stderr)
        return 2

    runtime = dict(job.get("runtime") or {})
    request = dict(job.get("request") or {})
    output = dict(job.get("output") or {})
    model_dir = Path(runtime.get("modelDir") or "").expanduser().resolve()
    repo_dir = Path(runtime.get("repoDir") or "").expanduser().resolve() if runtime.get("repoDir") else None
    output_path = Path(output.get("path") or request.get("outputPath") or "").expanduser().resolve()

    code, health = _probe_runtime(
        model_dir,
        repo_dir,
        allow_cpu_fallback=bool(request.get("allowCpuFallback")),
    )
    if code != 0:
        job.update(
            {
                "ok": False,
                "status": "failed",
                "startedAt": _now(),
                "finishedAt": _now(),
                "error": {"code": health.get("code"), "message": health.get("message"), "details": health.get("details")},
                "health": health,
            }
        )
        _write_json(job_path, job)
        print(json.dumps(job["error"], ensure_ascii=False), file=sys.stderr)
        return code

    if repo_dir and str(repo_dir) not in sys.path:
        sys.path.insert(0, str(repo_dir))

    try:
        from indextts.infer_v2 import IndexTTS2
    except Exception as exc:  # noqa: BLE001
        job.update(
            {
                "ok": False,
                "status": "failed",
                "startedAt": _now(),
                "finishedAt": _now(),
                "error": {
                    "code": "INDEX_TTS2_RUNTIME_IMPORT_FAILED",
                    "message": f"Unable to import IndexTTS2: {exc}",
                },
            }
        )
        _write_json(job_path, job)
        print(json.dumps(job["error"], ensure_ascii=False), file=sys.stderr)
        return 3

    voice_path = Path(request.get("referenceAudioPath") or "").expanduser().resolve()
    emotion_path = request.get("emotionAudioPath")
    if not voice_path.is_file():
        job.update(
            {
                "ok": False,
                "status": "failed",
                "startedAt": _now(),
                "finishedAt": _now(),
                "error": {
                    "code": "INDEX_TTS2_REFERENCE_MISSING",
                    "message": f"Reference audio does not exist: {voice_path}",
                },
            }
        )
        _write_json(job_path, job)
        print(json.dumps(job["error"], ensure_ascii=False), file=sys.stderr)
        return 2

    if emotion_path:
        emotion_ref = Path(str(emotion_path)).expanduser().resolve()
        if not emotion_ref.is_file():
            job.update(
                {
                    "ok": False,
                    "status": "failed",
                    "startedAt": _now(),
                    "finishedAt": _now(),
                    "error": {
                        "code": "INDEX_TTS2_EMOTION_REFERENCE_MISSING",
                        "message": f"Emotion reference audio does not exist: {emotion_ref}",
                    },
                }
            )
            _write_json(job_path, job)
            print(json.dumps(job["error"], ensure_ascii=False), file=sys.stderr)
            return 2

    output_path.parent.mkdir(parents=True, exist_ok=True)
    job["status"] = "running"
    job["startedAt"] = _now()
    job["health"] = health
    _write_json(job_path, job)

    infer_kwargs = {
        "spk_audio_prompt": str(voice_path),
        "text": str(request.get("text") or ""),
        "output_path": str(output_path),
        "verbose": False,
    }
    if emotion_path:
        infer_kwargs["emo_audio_prompt"] = str(Path(str(emotion_path)).expanduser().resolve())
    emotion_text = str(request.get("emotionText") or "").strip()
    if emotion_text:
        infer_kwargs["use_emo_text"] = True
        infer_kwargs["emo_text"] = emotion_text
    if request.get("emotionVector"):
        infer_kwargs["emo_vector"] = list(request["emotionVector"])

    try:
        tts = IndexTTS2(
            cfg_path=str(model_dir / "config.yaml"),
            model_dir=str(model_dir),
            use_fp16=bool(request.get("useFp16", True)) and health.get("device") != "cpu",
            device=str(request.get("device") or health.get("device") or "cpu"),
            use_cuda_kernel=None,
            use_deepspeed=False,
            use_accel=False,
            use_torch_compile=False,
        )
        tts.infer(**infer_kwargs)
    except Exception as exc:  # noqa: BLE001
        job.update(
            {
                "ok": False,
                "status": "failed",
                "finishedAt": _now(),
                "error": {"code": "INDEX_TTS2_INFERENCE_FAILED", "message": str(exc)},
            }
        )
        _write_json(job_path, job)
        print(json.dumps(job["error"], ensure_ascii=False), file=sys.stderr)
        return 4

    if not output_path.is_file():
        job.update(
            {
                "ok": False,
                "status": "failed",
                "finishedAt": _now(),
                "error": {
                    "code": "INDEX_TTS2_OUTPUT_MISSING",
                    "message": "IndexTTS2 reported success but did not create an output wav.",
                },
            }
        )
        _write_json(job_path, job)
        print(json.dumps(job["error"], ensure_ascii=False), file=sys.stderr)
        return 4

    job.update(
        {
            "ok": True,
            "status": "completed",
            "finishedAt": _now(),
            "output": {
                "path": str(output_path),
                "format": "wav",
                "bytes": output_path.stat().st_size,
            },
            "device": health.get("device"),
            "error": None,
        }
    )
    _write_json(job_path, job)
    print(json.dumps({"ok": True, "output": str(output_path)}, ensure_ascii=False))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-json")
    parser.add_argument("--health-json")
    parser.add_argument("--model-dir")
    parser.add_argument("--repo-dir")
    parser.add_argument("--allow-cpu-fallback", action="store_true")
    parser.add_argument("--adapter-process", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.adapter_process:
        if not args.health_json or not args.model_dir:
            parser.error("--adapter-process requires --health-json and --model-dir")
        return _adapter_process(args)
    if args.job_json:
        return _run_job(args)
    if args.health_json:
        if not args.model_dir:
            parser.error("--health-json requires --model-dir")
        return _run_health(args)
    parser.error("provide --job-json or --health-json")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
