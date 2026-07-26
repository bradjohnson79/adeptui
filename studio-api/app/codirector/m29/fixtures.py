"""Deterministic fixtures for M2.9 CI / Playwright acceptance.

Never claims production_ready. Used only when ADEPT_M29_FIXTURE_MODE is on.
"""

from __future__ import annotations

import uuid
from typing import Any


def fixture_asset_id(prefix: str = "m29") -> str:
    return f"{prefix}-asset-{uuid.uuid4().hex[:12]}"


def fixture_image_result(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return {
        "assetId": payload.get("assetId") or fixture_asset_id("img"),
        "operation": payload.get("operation") or "generate",
        "provider": "m29_fixture",
        "fixture": True,
        "status": "generated",
        "prompt": payload.get("prompt") or "Fixture image",
        "width": int(payload.get("width") or 1280),
        "height": int(payload.get("height") or 720),
        "seed": payload.get("seed"),
        "mockAdapter": False,
    }


def fixture_frame_result(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    count = int(payload.get("count") or 1)
    frames = []
    for i in range(count):
        frames.append(
            {
                "frameId": f"frame-{uuid.uuid4().hex[:10]}",
                "assetId": fixture_asset_id("frm"),
                "frameType": payload.get("frameType") or "production_frame",
                "order": i,
                "shotId": payload.get("shotId"),
            }
        )
    return {
        "frames": frames,
        "provider": "m29_fixture",
        "fixture": True,
        "status": "generated",
    }


def fixture_video_result(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return {
        "assetId": payload.get("assetId") or fixture_asset_id("vid"),
        "mode": payload.get("mode") or "text_to_video",
        "provider": "m29_fixture",
        "fixture": True,
        "status": "generated",
        "durationSec": float(payload.get("durationSec") or 4.0),
        "fps": int(payload.get("fps") or 24),
        "prompt": payload.get("prompt") or "Fixture video",
    }


def fixture_audio_result(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return {
        "assetId": payload.get("assetId") or fixture_asset_id("aud"),
        "kind": payload.get("kind") or "dialogue",
        "provider": "m29_fixture",
        "fixture": True,
        "status": "generated",
        "durationSec": float(payload.get("durationSec") or 2.0),
        "prompt": payload.get("prompt") or "Fixture audio",
    }


def fixture_lipsync_result(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return {
        "assetId": payload.get("assetId") or fixture_asset_id("lips"),
        "mouthTrackId": f"mouth-{uuid.uuid4().hex[:10]}",
        "provider": "m29_fixture",
        "fixture": True,
        "status": "generated",
        "rectangles": payload.get("rectangles")
        or [{"t": 0.0, "x": 0.4, "y": 0.55, "w": 0.2, "h": 0.12}],
    }


def fixture_mouth_track_result(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return {
        "mouthTrackId": f"mouth-{uuid.uuid4().hex[:10]}",
        "provider": "m29_fixture",
        "fixture": True,
        "status": "generated",
        "keyframes": payload.get("keyframes")
        or [
            {"t": 0.0, "x": 0.4, "y": 0.55, "w": 0.2, "h": 0.12},
            {"t": 1.0, "x": 0.41, "y": 0.56, "w": 0.2, "h": 0.11},
        ],
    }


def fixture_render_result(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return {
        "manifestId": payload.get("manifestId") or f"rend-{uuid.uuid4().hex[:10]}",
        "assetId": payload.get("assetId") or fixture_asset_id("rend"),
        "kind": payload.get("kind") or "timeline_render",
        "provider": "m29_fixture",
        "fixture": True,
        "status": "generated",
    }


def fixture_edit_result(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return {
        "editId": f"edit-{uuid.uuid4().hex[:10]}",
        "provider": "m29_fixture",
        "fixture": True,
        "status": "proposed",
        "ops": payload.get("ops") or [{"op": "trim", "clipId": "clip-1", "in": 0, "out": 2}],
        "requiresApproval": True,
    }


def fixture_control_plan(request_text: str) -> dict[str, Any]:
    """Decompose a structured multi-step request into job stubs (deterministic)."""
    lower = (request_text or "").lower()
    steps: list[dict[str, Any]] = []
    if any(k in lower for k in ("image", "still", "frame", "reference")):
        steps.append({"jobType": "image_generate", "capability": "image.generate", "payload": {"prompt": request_text}})
    if "frame" in lower or "keyframe" in lower:
        steps.append({"jobType": "frame_generate", "capability": "frame.generate", "payload": {"prompt": request_text}})
    if any(k in lower for k in ("video", "txt2vid", "motion")):
        steps.append({"jobType": "video_generate", "capability": "video.generate", "payload": {"prompt": request_text, "mode": "text_to_video"}})
    if any(k in lower for k in ("lip", "mouth", "dialogue")):
        steps.append({"jobType": "lipsync_generate", "capability": "lipsync.generate", "payload": {"prompt": request_text}})
    if any(k in lower for k in ("audio", "sfx", "music", "sound")):
        kind = "sfx" if "sfx" in lower or "sound" in lower else ("music" if "music" in lower else "dialogue")
        steps.append({"jobType": "audio_generate", "capability": f"audio.{kind}.generate", "payload": {"prompt": request_text, "kind": kind}})
    if any(k in lower for k in ("render", "export", "timeline")):
        steps.append({"jobType": "timeline_render", "capability": "timeline.render", "payload": {}})
    if not steps:
        steps.append({"jobType": "image_generate", "capability": "image.generate", "payload": {"prompt": request_text or "Fixture control"}})
    return {
        "planId": f"plan-{uuid.uuid4().hex[:10]}",
        "steps": steps,
        "fixture": True,
        "requiresApproval": True,
        "status": "proposed",
    }
