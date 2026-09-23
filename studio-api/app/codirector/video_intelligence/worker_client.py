"""Spawn the isolated perception worker. Never upload video."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .clip_extract import (
    cleanup_extracted_clip,
    extract_av_clip,
    extract_continuity_frames,
    extract_review_clip,
)
from .contracts import (
    CameraObservation,
    CharacterObservation,
    SceneObservation,
    VideoPerceptionObservation,
)
from .media_packet import QWEN_OMNI_MODEL_ID
from .paths import (
    INTERNVIDEO3_MARKERS,
    QWEN_OMNI_MARKERS,
    VIDEOCHAT3_MARKERS,
    internvideo3_dir,
    model_present,
    qwen_omni_dir,
    videochat3_dir,
    worker_python,
)

DEFAULT_QUESTION = (
    "Watch this entire clip from the first moment to the last. "
    "Describe what actually happens, including early and middle events, not only the ending. "
    "Name visible characters, how many people are in frame, walking or other body action, "
    "unfinished actions, head/body turns, gaze, camera movement, framing, distance, and lighting. "
    "Then describe the final frame in detail: who is visible, how far they are, "
    "where the light is, and the camera distance. The next shot must begin on that final frame. "
    "If an action is only partly complete, say so. "
    "Do not invent facts you cannot see. "
    "Reply in English only. Do not answer in Chinese or any other language. "
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
    if "QWEN_OMNI_UTILS_MISSING" in text:
        return "QWEN_OMNI_UTILS_MISSING"
    if any(
        token in text
        for token in (
            "MODEL_NOT_INSTALLED",
            "VIDEOCHAT3_NOT_INSTALLED",
            "INTERNVIDEO3_NOT_INSTALLED",
            "QWEN_OMNI_NOT_INSTALLED",
            "MODEL_PATH_MISSING",
        )
    ):
        return "MODEL_NOT_INSTALLED"
    return text[:80]


def _model_route(model_id: str) -> tuple[Path, tuple[str, ...], bool]:
    """Resolve (model_dir, markers, audio_retaining) for a perception model id.

    Qwen2.5-Omni is the AV route: it must receive a clip that KEEPS the audio
    track (extract_av_clip). VideoChat3/InternVideo3 keep the audio-stripped
    low-res path.
    """
    if "qwen2-5-omni" in model_id:
        return qwen_omni_dir(), QWEN_OMNI_MARKERS, True
    if "videochat3" in model_id:
        return videochat3_dir(), VIDEOCHAT3_MARKERS, False
    return internvideo3_dir(), INTERNVIDEO3_MARKERS, False


def _spawn_worker(
    video_path: str,
    *,
    question: str,
    model_id: str,
    timeout_sec: float,
    start_sec: float = 0.0,
    duration_sec: float = 3.0,
    question_b: str = "",
) -> dict[str, Any]:
    """Extract the review clip, spawn the isolated worker, return its payload."""
    mode = perception_mode()
    if mode in _STUB_MODES and not stub_allowed():
        raise RuntimeError("STUB_FORBIDDEN")
    model_dir, markers, audio_retaining = _model_route(model_id)
    model_path = str(model_dir)
    if mode not in (*_STUB_MODES, *_FORCE_FAIL_MODES):
        if not model_present(Path(model_path), markers):
            raise RuntimeError("MODEL_NOT_INSTALLED")

    source_path = video_path
    review_path = video_path
    created_review: str | None = None
    try:
        stem = Path(video_path).stem
        if audio_retaining:
            review = Path(video_path).with_name(stem + ".avreview512.mp4")
        else:
            review = Path(video_path).with_name(stem + ".review512.mp4")
        try:
            if audio_retaining:
                review_path = extract_av_clip(
                    video_path, str(review), start_sec=start_sec, duration_sec=duration_sec, width=512, fps=2
                )
            else:
                review_path = extract_review_clip(
                    video_path, str(review), start_sec=start_sec, duration_sec=duration_sec, width=512, fps=2
                )
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
        if (question_b or "").strip():
            cmd.extend(["--question-b", question_b])
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_sec,
                env=env,
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
        return data
    finally:
        cleanup_extracted_clip(created_review, source_path=source_path)


def compose_handoff_summary(item: dict[str, Any]) -> str:
    """Fold the compact Omni state into the summary the next window already reads."""
    parts: list[str] = []
    summary = str(item.get("summary") or "").strip()
    if summary:
        parts.append(summary)

    def _add(key: str, label: str) -> None:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(f"{label}: {value.strip()}")
            return
        if isinstance(value, list):
            texts = [str(entry).strip() for entry in value if str(entry).strip()]
            if texts:
                parts.append(f"{label}: " + "; ".join(texts))

    _add("actionCompleted", "Completed")
    _add("actionInProgress", "In progress")
    _add("subjectState", "Subject")
    _add("propState", "Props")
    _add("environmentState", "Place")
    _add("cameraState", "Camera")
    _add("motionDirection", "Motion")
    _add("mustContinue", "Continue")
    _add("mustNotRepeat", "Do not repeat")
    return " ".join(parts)[:500]


_EQUIPMENT_ECHO_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "or",
        "and",
        "crew",
        "boom",
        "microphone",
        "mic",
        "slate",
        "camera",
        "gear",
        "equipment",
        "visible",
        "in",
        "frame",
    }
)


def _drop_equipment_echo(flags: list[Any]) -> list[str]:
    """Ignore a flag that only repeats the review instructions.

    A real sighting names something extra, such as where the pole is.
    """
    import re

    kept: list[str] = []
    for flag in flags or []:
        text = str(flag).strip()
        words = re.findall(r"[a-z0-9]+", text.lower())
        if not words or all(word in _EQUIPMENT_ECHO_WORDS for word in words):
            continue
        kept.append(text)
    return kept


def _enrich_handoff_answer(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return item
    if isinstance(item.get("equipmentFlags"), list):
        item["equipmentFlags"] = _drop_equipment_echo(item["equipmentFlags"])
    item["summary"] = compose_handoff_summary(item)
    if item.get("ok"):
        item["availability"] = "ready"
    return item


def _spawn_frame_worker(
    video_path: str,
    *,
    question: str,
    question_b: str,
    model_id: str,
    timeout_sec: float,
    duration_sec: float,
    frame_count: int,
    frame_height: int,
    max_new_tokens: int,
    source_asset_id: str,
) -> dict[str, Any]:
    """One Omni process over sampled stills. No audio. The take file stays put."""
    mode = perception_mode()
    if mode in _STUB_MODES and not stub_allowed():
        raise RuntimeError("STUB_FORBIDDEN")
    model_dir, markers, _audio_retaining = _model_route(model_id)
    model_path = str(model_dir)
    if mode not in (*_STUB_MODES, *_FORCE_FAIL_MODES):
        if not model_present(Path(model_path), markers):
            raise RuntimeError("MODEL_NOT_INSTALLED")
    source = Path(video_path)
    if not source.is_file():
        raise RuntimeError("SOURCE_VIDEO_MISSING")
    source_size = source.stat().st_size
    temp_dir = tempfile.mkdtemp(prefix="adept-omni-review-")
    try:
        frames, times = extract_continuity_frames(
            str(source),
            temp_dir,
            duration_sec=duration_sec,
            count=frame_count,
            height=frame_height,
        )
        if source.stat().st_size != source_size:
            raise RuntimeError("SOURCE_TAKE_MODIFIED")
        out = Path(temp_dir) / "perception.json"
        worker = Path(__file__).with_name("worker.py")
        cmd = [
            str(worker_python()),
            str(worker),
            "--video",
            str(source),
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
            "--max-new-tokens",
            str(int(max_new_tokens)),
            "--frames",
            *frames,
        ]
        if (question_b or "").strip():
            cmd.extend(["--question-b", question_b])
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_sec,
                env=env,
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
        package = {
            "kind": "sampled_frames",
            "frameCount": len(frames),
            "height": int(frame_height),
            "audio": False,
            "timestamps": times,
            "sourceAssetId": str(source_asset_id or ""),
            "sourcePath": str(source.resolve()),
        }
        if isinstance(data.get("answers"), list):
            data["answers"] = [_enrich_handoff_answer(item) for item in data["answers"] if isinstance(item, dict)]
        else:
            data = _enrich_handoff_answer(data)
        data["reviewPackage"] = package
        return data
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if source.is_file() and source.stat().st_size != source_size:
            raise RuntimeError("SOURCE_TAKE_MODIFIED")


def run_av_perception_pair(
    video_path: str,
    *,
    question: str,
    question_b: str,
    model_id: str = QWEN_OMNI_MODEL_ID,
    timeout_sec: float = 360.0,
    start_sec: float = 0.0,
    duration_sec: float = 6.0,
    frame_count: int = 0,
    frame_height: int = 480,
    max_new_tokens: int = 320,
    source_asset_id: str = "",
) -> dict[str, Any]:
    """One Omni process. Frame review is the Timeline handoff path.

    frame_count 0 keeps the full-clip audio review used outside that handoff.
    """
    if int(frame_count or 0) > 0:
        return _spawn_frame_worker(
            video_path,
            question=question,
            question_b=question_b,
            model_id=model_id,
            timeout_sec=timeout_sec,
            duration_sec=duration_sec,
            frame_count=int(frame_count),
            frame_height=int(frame_height),
            max_new_tokens=int(max_new_tokens),
            source_asset_id=source_asset_id,
        )
    return _spawn_worker(
        video_path,
        question=question,
        question_b=question_b,
        model_id=model_id,
        timeout_sec=timeout_sec,
        start_sec=start_sec,
        duration_sec=duration_sec,
    )


def run_av_perception(
    video_path: str,
    *,
    question: str,
    model_id: str = QWEN_OMNI_MODEL_ID,
    timeout_sec: float = 300.0,
    start_sec: float = 0.0,
    duration_sec: float = 6.0,
) -> dict[str, Any]:
    """Qwen2.5-Omni AV perception. Returns the FULL worker payload dict
    (summary/visualEvents/audioEvents/speechSegments/motionEvents + ingestion
    evidence) for the Media Intelligence Packet. Never uploads video."""
    return _spawn_worker(
        video_path,
        question=question,
        model_id=model_id,
        timeout_sec=timeout_sec,
        start_sec=start_sec,
        duration_sec=duration_sec,
    )


def run_perception(
    video_path: str,
    *,
    question: str = DEFAULT_QUESTION,
    model_id: str = "videochat3-4b",
    timeout_sec: float = 180.0,
    start_sec: float = 0.0,
    duration_sec: float = 3.0,
) -> VideoPerceptionObservation:
    data = _spawn_worker(
        video_path,
        question=question,
        model_id=model_id,
        timeout_sec=timeout_sec,
        start_sec=start_sec,
        duration_sec=duration_sec,
    )
    return _observation_from_payload(data)


_JSON_JUNK = frozenset({"[]", "[],", "{}", "null", "none", "none."})


def _observation_from_payload(data: dict[str, Any]) -> VideoPerceptionObservation:
    chars = []
    for item in data.get("characters") or []:
        if isinstance(item, dict):
            chars.append(CharacterObservation.model_validate(item))
    cam = data.get("camera") if isinstance(data.get("camera"), dict) else {}
    scene = data.get("scene") if isinstance(data.get("scene"), dict) else {}
    raw = str(data.get("rawText") or "")
    parsed = _parse_json_tail(raw)
    unfinished = _as_str_list(data.get("unfinishedActions"))
    completed = _as_str_list(data.get("completedActions"))
    json_unfinished_present = isinstance(parsed, dict) and "unfinishedActions" in parsed
    if not unfinished and parsed:
        unfinished = _as_str_list(parsed.get("unfinishedActions"))
        if not completed:
            completed = _as_str_list(parsed.get("completedActions"))
        if data.get("confidence") is None and parsed.get("confidence") is not None:
            data["confidence"] = parsed.get("confidence")
    if not unfinished and not json_unfinished_present:
        unfinished = _extract_listed(raw, "unfinished")
    # Perception robustness: the vision model may emit a symbolic or malformed
    # confidence ("high", "0.9.", "none"). A non-numeric value must not crash
    # observation construction — that kills the whole temporal packet and
    # degrades the Batch N → N+1 handoff to `unavailable`. Coerce what we can;
    # otherwise drop the field (Optional) and keep the review usable.
    raw_confidence = data.get("confidence")
    confidence: float | None = None
    if isinstance(raw_confidence, bool):
        confidence = 1.0 if raw_confidence else 0.0
    elif isinstance(raw_confidence, (int, float)):
        confidence = float(raw_confidence)
    elif isinstance(raw_confidence, str):
        token = raw_confidence.strip().rstrip(".")
        symbolic = {"high": 0.9, "medium": 0.6, "moderate": 0.6, "low": 0.3, "none": 0.0, "unknown": None}
        lowered = token.lower()
        if lowered in symbolic:
            mapped = symbolic[lowered]
            confidence = mapped
        else:
            try:
                confidence = float(token)
            except ValueError:
                confidence = None
    return VideoPerceptionObservation(
        modelId=str(data.get("modelId") or ""),
        rawText=raw,
        characters=chars,
        camera=CameraObservation.model_validate(cam) if cam else CameraObservation(),
        scene=SceneObservation.model_validate(scene) if scene else SceneObservation(),
        unfinishedActions=unfinished,
        completedActions=completed,
        confidence=confidence,
        parseOk=bool(data.get("parseOk")),
    )


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower().rstrip(",") in _JSON_JUNK:
            return []
        return [text]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            text = str(item).strip()
            if text and text.lower().rstrip(",") not in _JSON_JUNK:
                out.append(text)
        return out
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
            if rest and rest.lower().rstrip(",") not in _JSON_JUNK:
                lines.append(rest)
    return lines
