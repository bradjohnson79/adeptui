"""Spawn the isolated perception worker. Never upload video."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .contracts import (
    CameraObservation,
    CharacterObservation,
    SceneObservation,
    VideoPerceptionObservation,
)
from .paths import INTERNVIDEO3_MARKERS, VIDEOCHAT3_MARKERS, internvideo3_dir, model_present, videochat3_dir

DEFAULT_QUESTION = (
    "Describe what actually happens in this video clip. "
    "Name visible characters, walking or other body action, unfinished actions, "
    "head/body turns, gaze, camera movement, framing, and lighting. "
    "If an action is only partly complete, say so. "
    "Do not invent facts you cannot see. "
    "End with a short JSON object containing keys unfinishedActions, completedActions, confidence."
)


def perception_mode() -> str:
    return (os.environ.get("ADEPT_TEMPORAL_PERCEPTION_MODE") or "live").strip().lower()


def run_perception(
    video_path: str,
    *,
    question: str = DEFAULT_QUESTION,
    model_id: str = "videochat3-4b",
    timeout_sec: float = 180.0,
) -> VideoPerceptionObservation:
    mode = perception_mode()
    markers = VIDEOCHAT3_MARKERS if "videochat3" in model_id else INTERNVIDEO3_MARKERS
    model_path = str(videochat3_dir() if "videochat3" in model_id else internvideo3_dir())
    if mode not in ("stub", "1", "true", "yes", "fail", "error"):
        if not model_present(Path(model_path), markers):
            raise RuntimeError("VIDEOCHAT3_NOT_INSTALLED" if "videochat3" in model_id else "INTERNVIDEO3_NOT_INSTALLED")

    out = Path(video_path).with_suffix(".perception.json")
    worker = Path(__file__).with_name("worker.py")
    cmd = [
        sys.executable,
        str(worker),
        "--video",
        str(video_path),
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
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    if not out.is_file():
        raise RuntimeError((proc.stderr or proc.stdout or "perception worker produced no output")[:500])
    data = json.loads(out.read_text(encoding="utf-8"))
    if not data.get("ok"):
        raise RuntimeError(str(data.get("error") or "perception failed"))
    return _observation_from_payload(data)


def _observation_from_payload(data: dict[str, Any]) -> VideoPerceptionObservation:
    chars = []
    for item in data.get("characters") or []:
        if isinstance(item, dict):
            chars.append(CharacterObservation.model_validate(item))
    cam = data.get("camera") if isinstance(data.get("camera"), dict) else {}
    scene = data.get("scene") if isinstance(data.get("scene"), dict) else {}
    raw = str(data.get("rawText") or "")
    unfinished = [str(x) for x in (data.get("unfinishedActions") or []) if str(x).strip()]
    completed = [str(x) for x in (data.get("completedActions") or []) if str(x).strip()]
    if not unfinished:
        parsed = _parse_json_tail(raw)
        unfinished = [str(x) for x in (parsed.get("unfinishedActions") or []) if str(x).strip()]
        if not completed:
            completed = [str(x) for x in (parsed.get("completedActions") or []) if str(x).strip()]
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
