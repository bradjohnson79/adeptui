"""Isolated VideoChat3 / InternVideo3 worker. Observation JSON only.

Usage:
  python worker.py --video path.mp4 --question "..." --out path.json
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


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _stub_observation(video: str, question: str, model_id: str) -> dict:
    return {
        "ok": True,
        "mode": "stub",
        "modelId": model_id,
        "parseOk": True,
        "rawText": (
            "Walking remains correct. The turn is unfinished at about 70 percent. "
            "Camera dolly remains correct. Screen geography is preserved."
        ),
        "characters": [
            {
                "label": "subject-a",
                "actionState": "walking",
                "actionCompletion": 0.7,
                "movementDirection": "forward",
                "identityCertainty": "unknown",
            }
        ],
        "camera": {
            "movementType": "dolly",
            "framing": "two-shot",
            "certainty": "unknown",
        },
        "scene": {"environmentState": "same location", "certainty": "unknown"},
        "unfinishedActions": ["complete the remaining head/body turn toward the other character"],
        "completedActions": ["walking continues"],
        "confidence": 0.72,
        "video": video,
        "question": question[:400],
    }


def _parse_json_tail(raw: str) -> dict:
    text = (raw or "").strip()
    start = text.rfind("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(text[start : end + 1])
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _vram_used_gb() -> float | None:
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        free, total = torch.cuda.mem_get_info(0)
        return round((total - free) / (1024**3), 3)
    except Exception:
        return None


def _health_payload() -> dict:
    try:
        import torch
    except Exception as exc:
        return {"ok": False, "error": f"TORCH_IMPORT_FAILED:{exc}"}
    if not torch.cuda.is_available():
        return {"ok": False, "error": "CPU_ONLY_TORCH"}
    return {
        "ok": True,
        "cuda": True,
        "device": str(torch.cuda.get_device_name(0)),
    }


def _live_infer(video: str, question: str, model_path: str, model_id: str) -> dict:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CPU_ONLY_TORCH")
    from transformers import AutoModelForCausalLM, AutoProcessor

    t0 = time.time()
    _emit({"phase": "load", "modelPath": model_path})
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
        device_map={"": 0},
        trust_remote_code=True,
        attn_implementation="sdpa",
    )
    # Vision tower defaults to flash_attention_2 in config.json. Flash-attn is
    # optional; SDPA is the documented fallback. Do not rewrite pinned weights.
    def _force_sdpa(module) -> None:
        if getattr(module, "attn_impl", None) == "flash_attention_2":
            module.attn_impl = "sdpa"

    model.apply(_force_sdpa)
    model.eval()
    processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "video", "video": video},
                {"type": "text", "text": question},
            ],
        }
    ]
    try:
        from qwen_vl_utils import process_vision_info

        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
    except Exception:
        inputs = processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt"
        )
    inputs = inputs.to(model.device)
    vram_during = _vram_used_gb()
    _emit({"phase": "infer", "vramUsedGb": vram_during, "device": str(torch.cuda.get_device_name(0))})
    output = model.generate(**inputs, max_new_tokens=512, use_cache=True)
    generated = [o[len(i) :] for i, o in zip(inputs.input_ids, output)]
    raw = processor.batch_decode(generated, skip_special_tokens=True)[0]
    parsed = _parse_json_tail(raw)
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    def _as_str_list(value):
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    unfinished = _as_str_list(parsed.get("unfinishedActions"))
    completed = _as_str_list(parsed.get("completedActions"))
    confidence = parsed.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None
    return {
        "ok": True,
        "mode": "live",
        "modelId": model_id,
        "parseOk": bool(parsed),
        "rawText": raw,
        "characters": parsed.get("characters") if isinstance(parsed.get("characters"), list) else [],
        "camera": parsed.get("camera") if isinstance(parsed.get("camera"), dict) else {},
        "scene": parsed.get("scene") if isinstance(parsed.get("scene"), dict) else {},
        "unfinishedActions": unfinished,
        "completedActions": completed,
        "confidence": confidence,
        "loadToInferSec": round(time.time() - t0, 3),
        "device": str(torch.cuda.get_device_name(0)),
        "vramUsedGb": vram_during,
        "vramDuringGb": vram_during,
        "attnImplementation": "sdpa",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="")
    ap.add_argument("--question", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--model-path", default="")
    ap.add_argument("--model-id", default="videochat3-4b")
    ap.add_argument("--mode", default="")
    ap.add_argument("--health", action="store_true")
    args = ap.parse_args()
    if args.health:
        payload = _health_payload()
        _emit(payload)
        return 0 if payload.get("ok") else 2
    if not args.video or not args.question or not args.out:
        _emit({"ok": False, "error": "WORKER_ARGS_REQUIRED"})
        return 2
    mode = (args.mode or os.environ.get("ADEPT_TEMPORAL_PERCEPTION_MODE") or "live").strip().lower()
    out = Path(args.out)
    try:
        if mode in ("fail", "error"):
            raise RuntimeError("PERCEPTION_FORCED_FAILURE")
        if mode in ("stub", "1", "true", "yes"):
            allow = (os.environ.get("ADEPT_ALLOW_PERCEPTION_STUB") or "").strip().lower() in (
                "1",
                "true",
                "yes",
            ) or bool((os.environ.get("PYTEST_CURRENT_TEST") or "").strip())
            if not allow:
                raise RuntimeError("STUB_FORBIDDEN")
            payload = _stub_observation(args.video, args.question, args.model_id)
        else:
            if not args.model_path or not Path(args.model_path).exists():
                raise RuntimeError("MODEL_PATH_MISSING")
            payload = _live_infer(args.video, args.question, args.model_path, args.model_id)
        _write(out, payload)
        _emit({"phase": "done", "out": str(out)})
        return 0
    except Exception as exc:
        import traceback

        payload = {
            "ok": False,
            "error": str(exc)[:500],
            "traceback": traceback.format_exc()[-2000:],
            "modelId": args.model_id,
            "mode": mode,
        }
        _write(out, payload)
        _emit({"phase": "failed", "error": payload["error"]})
        return 2


if __name__ == "__main__":
    sys.exit(main())
