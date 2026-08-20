"""Spawn the isolated perception worker. Never upload video."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .clip_extract import cleanup_extracted_clip, extract_review_clip
from .contracts import (
    CameraObservation,
    CharacterObservation,
    SceneObservation,
    VideoPerceptionObservation,
)
from .paths import (
    INTERNVIDEO3_MARKERS,
    VIDEOCHAT3_MARKERS,
    internvideo3_dir,
    model_present,
    videochat3_dir,
    worker_python,
)

DEFAULT_QUESTION = (
    "Describe what actually happens in this video clip. "
    "Name visible characters, walking or other body action, unfinished actions, "
    "head/body turns, gaze, camera movement, framing, and lighting. "
    "If an action is only partly complete, say so. "
    "Do not invent facts you cannot see. "
    "End with a short JSON object containing keys unfinishedActions, completedActions, confidence."
)

_STUB_MODES = ("stub", "1", "true", "yes")
_FORCE_FAIL_MODES = ("fail", "error")


def stub_allowed() -> bool:
    if (os.environ.get("ADEPT_ALLOW_PERCEPTION_STUB") or "").strip().lower() in ("1", "true", "yes"):
        return True
    return bool((os.environ.get("PYTEST_CURRENT_TEST") or "").strip())


def perception_mode() -> str:
    return (os.environ.get("ADEPT_TEMPORAL_PERCEPTION_MODE") or "live").strip().lower()


def normalize_perception_reason(exc: Exception | str) -> str:
    text = str(exc)
    if "STUB_FORBIDDEN" in text:
        return "STUB_FORBIDDEN"
    if "PERCEPTION_FORCED_FAILURE" in text:
        return "PERCEPTION_FORCED_FAILURE"
    if any(
        token in text
        for token in (
            "MODEL_NOT_INSTALLED",
            "VIDEOCHAT3_NOT_INSTALLED",
            "INTERNVIDEO3_NOT_INSTALLED",
            "MODEL_PATH_MISSING",
        )
    ):
        return "MODEL_NOT_INSTALLED"
    return text[:80]


def run_perception(
    video_path: str,
    *,
    question: str = DEFAULT_QUESTION,
    model_id: str = "videochat3-4b",
    timeout_sec: float = 180.0,
) -> VideoPerceptionObservation:
    mode = perception_mode()
    if mode in _STUB_MODES and not stub_allowed():
        raise RuntimeError("STUB_FORBIDDEN")
    markers = VIDEOCHAT3_MARKERS if "videochat3" in model_id else INTERNVIDEO3_MARKERS
    model_path = str(videochat3_dir() if "videochat3" in model_id else internvideo3_dir())
    if mode not in (*_STUB_MODES, *_FORCE_FAIL_MODES):
        if not model_present(Path(model_path), markers):
            raise RuntimeError("MODEL_NOT_INSTALLED")

    source_path = video_path
    review_path = video_path
    created_review: str | None = None
    try:
        review = Path(video_path).with_name(Path(video_path).stem + ".review512.mp4")
        try:
            review_path = extract_review_clip(video_path, str(review), duration_sec=3.0, width=512, fps=2)
            if review_path != source_path:
                created_review = review_path
        except Exception:
            review_path = source_path
        out = Path(review_path).with_suffix(".perception.json")
        worker = Path(__file__).with_name("worker.py")
        cmd = [
            str(worker_python()),
            str(worker),
            "--video",
            str(review_path),
            "--question",
            question,
            "--out",
            str(out),
            "--model-path",
            model_path,
            "--model-id",
            model_id,
            "--mode",
            mode,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("PERCEPTION_TIMEOUT") from exc
        if not out.is_file():
            raise RuntimeError((proc.stderr or proc.stdout or "perception worker produced no output")[:500])
        data = json.loads(out.read_text(encoding="utf-8"))
        if not data.get("ok"):
            detail = normalize_perception_reason(str(data.get("error") or "perception failed"))
            if detail in ("STUB_FORBIDDEN", "MODEL_NOT_INSTALLED"):
                raise RuntimeError(detail)
            tb = str(data.get("traceback") or "")[-800:]
            raise RuntimeError(f"{detail}\n{tb}".strip())
        return _observation_from_payload(data)
    finally:
        cleanup_extracted_clip(created_review, source_path=source_path)


def _observation_from_payload(data: dict[str, Any]) -> VideoPerceptionObservation:
    chars = []
    for item in data.get("characters") or []:
        if isinstance(item, dict):
            chars.append(CharacterObservation.model_validate(item))
    cam = data.get("camera") if isinstance(data.get("camera"), dict) else {}
    scene = data.get("scene") if isinstance(data.get("scene"), dict) else {}
    raw = str(data.get("rawText") or "")
    unfinished = _as_str_list(data.get("unfinishedActions"))
    completed = _as_str_list(data.get("completedActions"))
    if not unfinished:
        parsed = _parse_json_tail(raw)
        unfinished = _as_str_list(parsed.get("unfinishedActions"))
        if not completed:
            completed = _as_str_list(parsed.get("completedActions"))
        if data.get("confidence") is None and parsed.get("confidence") is not None:
            data["confidence"] = parsed.get("confidence")
    if not unfinished:
        unfinished = _extract_listed(raw, "unfinished")
    return VideoPerceptionObservation(
        modelId=str(data.get("modelId") or ""),
        rawText=raw,
        characters=chars,
        camera=CameraObservation.model_validate(cam) if cam else CameraObservation(),
        scene=SceneObservation.model_validate(scene) if scene else SceneObservation(),
        unfinishedActions=unfinished,
        completedActions=completed,
        confidence=data.get("confidence"),
        parseOk=bool(data.get("parseOk")),
    )


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _parse_json_tail(raw: str) -> dict[str, Any]:
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


def _extract_listed(raw: str, needle: str) -> list[str]:
    lines = []
    for line in (raw or "").splitlines():
        if needle in line.lower() and ":" in line:
            rest = line.split(":", 1)[1].strip()
            if rest:
                lines.append(rest)
    return lines
