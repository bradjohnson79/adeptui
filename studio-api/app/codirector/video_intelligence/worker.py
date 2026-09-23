"""Isolated VideoChat3 / InternVideo3 / Qwen2.5-Omni worker. Observation JSON only.

Usage:
  python worker.py --video path.mp4 --question "..." --out path.json

Qwen2.5-Omni (--model-id qwen2-5-omni-7b) ingests video AND audio
(use_audio_in_video=True in preprocess + processor + generate) and returns
text-only output (return_audio=False). VideoChat3/InternVideo3 stay on the
AutoModelForCausalLM + trust_remote_code path.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=True), flush=True)


def _configure_stdio() -> None:
    """Windows cp1252 consoles raise on model/library emoji (e.g. U+1F6A8)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


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
        "contactEvents": [
            {
                "startTime": 0.4,
                "endTime": 0.55,
                "characterLabel": "subject-a",
                "foot": "left",
                "surface": "floor",
                "intensity": 0.4,
                "timingSource": "visible_contact",
                "confidence": 0.6,
            }
        ],
        "cueOpportunities": [
            {
                "startTime": 0.4,
                "endTime": 0.6,
                "kind": "footstep",
                "label": "footstep on floor",
                "suggestedQuery": "footstep on hard floor",
                "presentInAudio": False,
                "characterLabel": "subject-a",
                "confidence": 0.6,
            }
        ],
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


def _parse_json_span(raw: str) -> dict:
    """Outermost-brace JSON extraction for nested structured output (Qwen-Omni).

    _parse_json_tail uses rfind("{") which breaks on pretty-printed NESTED
    objects (it lands on an inner brace). Try the outermost span first, then
    fall back to the legacy flat-tail behavior.
    """
    text = (raw or "").strip()
    for start in (text.find("{"), text.rfind("{")):
        end = text.rfind("}")
        if start < 0 or end <= start:
            continue
        try:
            data = json.loads(text[start : end + 1])
        except Exception:
            continue
        if isinstance(data, dict):
            return data
    return {}


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


def _mm_evidence_item(item: object) -> dict:
    """Shape/dtype evidence for one ingested multimodal item (C1 proof)."""
    shape = getattr(item, "shape", None)
    if shape is not None:
        try:
            return {"shape": [int(d) for d in shape], "dtype": str(getattr(item, "dtype", ""))}
        except Exception:
            pass
    try:
        return {"len": len(item)}  # type: ignore[arg-type]
    except Exception:
        return {"type": type(item).__name__}


def _live_infer_qwen_omni(video: str, question: str, model_path: str, model_id: str) -> dict:
    """One question. Prefer ``_live_infer_qwen_omni_many`` when several questions share a load."""
    return _live_infer_qwen_omni_many(video, [question], model_path, model_id)[0]


def _live_infer_qwen_omni_many(
    video: str,
    questions: list[str],
    model_path: str,
    model_id: str,
    *,
    frames: list[str] | None = None,
    max_new_tokens: int = 1024,
) -> list[dict]:
    """Load Qwen2.5-Omni once and answer every question before the process exits."""
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CPU_ONLY_TORCH")
    from transformers import Qwen2_5OmniForConditionalGeneration, Qwen2_5OmniProcessor

    try:
        from qwen_omni_utils import process_mm_info
    except Exception as exc:
        raise RuntimeError(f"QWEN_OMNI_UTILS_MISSING:{exc}") from exc

    t0 = time.time()
    _emit({"phase": "load", "modelPath": model_path, "modelId": model_id, "questions": len(questions)})
    t_load = time.time()
    model = Qwen2_5OmniForConditionalGeneration.from_pretrained(
        model_path,
        torch_dtype="auto",
        device_map="auto",
        attn_implementation="sdpa",
    )
    if hasattr(model, "disable_talker"):
        model.disable_talker()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    model.eval()
    processor = Qwen2_5OmniProcessor.from_pretrained(model_path)
    load_sec = round(time.time() - t_load, 3)
    _emit({"phase": "loaded", "modelLoadSec": load_sec})
    answers: list[dict] = []
    try:
        for question in questions:
            answers.append(
                _omni_answer_loaded(
                    model,
                    processor,
                    process_mm_info,
                    video,
                    question,
                    model_id,
                    t0,
                    frames=frames,
                    max_new_tokens=max_new_tokens,
                    model_load_sec=load_sec,
                )
            )
    finally:
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    return answers


def preprocess_omni_media(process_mm_info, conversation: list) -> tuple[bool, object, object, object]:
    """Visual review still runs when the take has no audio track.

    Native audio stays in the take. This does not invent, extract, or replace it.
    A clip that has audio keeps use_audio_in_video=True.
    """
    try:
        audios, images, videos = process_mm_info(conversation, use_audio_in_video=True)
        return True, audios, images, videos
    except Exception as exc:
        if "audio" not in str(exc).lower():
            raise
        audios, images, videos = process_mm_info(conversation, use_audio_in_video=False)
        return False, audios, images, videos


def _omni_answer_loaded(
    model,
    processor,
    process_mm_info,
    video: str,
    question: str,
    model_id: str,
    t0: float,
    *,
    frames: list[str] | None = None,
    max_new_tokens: int = 1024,
    model_load_sec: float | None = None,
) -> dict:
    """One question against an already-resident Omni model. Does not unload it."""
    import torch

    stills = [str(path) for path in (frames or []) if str(path).strip()]
    if stills:
        content: list[dict] = [{"type": "image", "image": path} for path in stills]
        content.append({"type": "text", "text": question})
        conversation = [{"role": "user", "content": content}]
    else:
        conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "video", "video": video},
                    {"type": "text", "text": question},
                ],
            }
        ]
    text = processor.apply_chat_template(conversation, tokenize=False, add_generation_prompt=True)
    t_pre = time.time()
    if stills:
        audios, images, videos = process_mm_info(conversation, use_audio_in_video=False)
        use_audio = False
    else:
        use_audio, audios, images, videos = preprocess_omni_media(process_mm_info, conversation)
    preprocess_sec = round(time.time() - t_pre, 3)
    ingestion_evidence = {
        "useAudioInVideo": use_audio,
        "audios": [_mm_evidence_item(a) for a in audios] if audios else [],
        "images": [_mm_evidence_item(i) for i in images] if images else [],
        "videos": [_mm_evidence_item(v) for v in videos] if videos else [],
        "audioStreamCount": len(audios) if audios else 0,
        "videoStreamCount": len(videos) if videos else 0,
    }
    _emit({"phase": "preprocess", "ingestion": ingestion_evidence})
    inputs = processor(
        text=text,
        audio=audios,
        images=images,
        videos=videos,
        return_tensors="pt",
        padding=True,
        use_audio_in_video=use_audio,
    )
    inputs = inputs.to(model.device)
    vram_during = _vram_used_gb()
    _emit(
        {
            "phase": "infer",
            "vramUsedGb": vram_during,
            "device": str(torch.cuda.get_device_name(0)),
            "audioStreamCount": ingestion_evidence["audioStreamCount"],
        }
    )
    t_gen = time.time()
    text_ids = model.generate(
        **inputs,
        use_audio_in_video=use_audio,
        return_audio=False,
        thinker_max_new_tokens=max(32, int(max_new_tokens)),
    )
    generate_sec = round(time.time() - t_gen, 3)
    generated = [o[len(i) :] for i, o in zip(inputs.input_ids, text_ids)]
    raw = processor.batch_decode(generated, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
    parsed = _parse_json_span(raw)

    def _as_str_list(value):
        skip = {"[]", "{}", "none", "n/a", "null"}
        if isinstance(value, str):
            text = value.strip()
            return [] if (not text or text.lower() in skip) else [text]
        if isinstance(value, list):
            out = []
            for item in value:
                text = str(item).strip()
                if text and text.lower() not in skip:
                    out.append(text)
            return out
        return []

    def _as_state(value):
        if isinstance(value, list):
            return "; ".join(_as_str_list(value))
        text = str(value or "").strip()
        return "" if text.lower() in {"[]", "{}", "none", "n/a", "null"} else text

    def _as_dict_list(value):
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

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
        "summary": str(parsed.get("summary") or ""),
        "visualEvents": _as_dict_list(parsed.get("visualEvents")),
        "audioEvents": _as_dict_list(parsed.get("audioEvents")),
        "speechSegments": _as_dict_list(parsed.get("speechSegments")),
        "motionEvents": _as_dict_list(parsed.get("motionEvents")),
        # Timeline Media Intelligence fields (media-intelligence-v1). Forwarded
        # verbatim from the model's JSON — dropping them here would silently
        # empty the packet's contact/cue/music surfaces.
        "characterActions": _as_dict_list(parsed.get("characterActions")),
        "contactEvents": _as_dict_list(parsed.get("contactEvents")),
        "environmentEvents": _as_dict_list(parsed.get("environmentEvents")),
        "sceneChanges": _as_dict_list(parsed.get("sceneChanges")),
        "cameraMotion": _as_dict_list(parsed.get("cameraMotion")),
        "cueOpportunities": _as_dict_list(parsed.get("cueOpportunities")),
        "musicOpportunities": _as_dict_list(parsed.get("musicOpportunities")),
        "characters": parsed.get("characters") if isinstance(parsed.get("characters"), list) else [],
        "camera": parsed.get("camera") if isinstance(parsed.get("camera"), dict) else {},
        "scene": parsed.get("scene") if isinstance(parsed.get("scene"), dict) else {},
        "unfinishedActions": _as_str_list(parsed.get("unfinishedActions")),
        "completedActions": _as_str_list(parsed.get("completedActions")),
        "continuityFlags": _as_str_list(parsed.get("continuityFlags")),
        "equipmentFlags": _as_str_list(parsed.get("equipmentFlags")),
        "cameraMoves": _as_str_list(parsed.get("cameraMoves")) or _as_str_list(parsed.get("cameraMotion")),
        "actionCompleted": _as_str_list(parsed.get("actionCompleted")),
        "actionInProgress": _as_str_list(parsed.get("actionInProgress")),
        "mustContinue": _as_str_list(parsed.get("mustContinue")),
        "mustNotRepeat": _as_str_list(parsed.get("mustNotRepeat")),
        "subjectState": _as_state(parsed.get("subjectState")),
        "propState": _as_state(parsed.get("propState")),
        "environmentState": _as_state(parsed.get("environmentState")),
        "cameraState": _as_state(parsed.get("cameraState")),
        "motionDirection": _as_state(parsed.get("motionDirection")),
        "confidence": confidence,
        "ingestion": ingestion_evidence,
        "reviewInput": {
            "kind": "frames" if stills else "video",
            "frameCount": len(stills),
            "audio": bool(use_audio),
        },
        "timings": {
            "modelLoadSec": model_load_sec,
            "preprocessSec": preprocess_sec,
            "generateSec": generate_sec,
        },
        "loadToInferSec": round(time.time() - t0, 3),
        "device": str(torch.cuda.get_device_name(0)),
        "vramUsedGb": vram_during,
        "vramDuringGb": vram_during,
        "attnImplementation": "sdpa",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="")
    ap.add_argument("--frames", nargs="*", default=[])
    ap.add_argument("--question", default="")
    ap.add_argument("--question-b", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--model-path", default="")
    ap.add_argument("--model-id", default="videochat3-4b")
    ap.add_argument("--mode", default="")
    ap.add_argument("--max-new-tokens", type=int, default=1024)
    ap.add_argument("--health", action="store_true")
    args = ap.parse_args()
    if args.health:
        payload = _health_payload()
        _emit(payload)
        return 0 if payload.get("ok") else 2
    frames = [str(path) for path in (args.frames or []) if str(path).strip()]
    if (not args.video and not frames) or not args.question or not args.out:
        _emit({"ok": False, "error": "WORKER_ARGS_REQUIRED"})
        return 2
    mode = (args.mode or os.environ.get("ADEPT_TEMPORAL_PERCEPTION_MODE") or "live").strip().lower()
    out = Path(args.out)
    try:
        if mode in ("fail", "error"):
            raise RuntimeError("PERCEPTION_FORCED_FAILURE")
        questions = [args.question]
        if (args.question_b or "").strip():
            questions.append(args.question_b)
        if mode in ("stub", "1", "true", "yes"):
            allow = (os.environ.get("ADEPT_ALLOW_PERCEPTION_STUB") or "").strip().lower() in (
                "1",
                "true",
                "yes",
            ) or bool((os.environ.get("PYTEST_CURRENT_TEST") or "").strip())
            if not allow:
                raise RuntimeError("STUB_FORBIDDEN")
            answers = [_stub_observation(args.video, q, args.model_id) for q in questions]
        else:
            if not args.model_path or not Path(args.model_path).exists():
                raise RuntimeError("MODEL_PATH_MISSING")
            if "qwen2-5-omni" in args.model_id:
                answers = _live_infer_qwen_omni_many(
                    args.video,
                    questions,
                    args.model_path,
                    args.model_id,
                    frames=frames or None,
                    max_new_tokens=int(args.max_new_tokens or 1024),
                )
            else:
                answers = [_live_infer(args.video, args.question, args.model_path, args.model_id)]
        payload = answers[0] if len(answers) == 1 else {
            "ok": all(bool(item.get("ok")) for item in answers),
            "answers": answers,
            "modelId": args.model_id,
            "mode": mode,
        }
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
    _configure_stdio()
    sys.exit(main())
