#!/usr/bin/env python3
"""Live Prompt Intelligence V2 evidence runner (image + video + audio/voice).

Produces artifacts under artifacts/m42/prompt-intelligence-v2/ and a summary JSON.
Mocks cannot replace live evidence — this script records honest health probes and
controlled live/dry outputs per domain.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "studio-api"))

from app.codirector.prompt_intelligence.benchmark_eval import evaluate_category
from app.codirector.prompt_intelligence.benchmark_runner import start_suite_run, suite_status
from app.codirector.prompt_intelligence.benchmark_suites import resolve_live_video_provider
from app.codirector.prompt_intelligence.recommendation import resolve_strategy_recommendation


def _wait(suite_run_id: str, timeout_s: float = 120.0) -> dict:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        last = suite_status(suite_run_id)
        status = (last.get("suiteRun") or {}).get("status")
        if status in ("completed", "failed", "cancelled"):
            return last
        time.sleep(0.25)
    return last


def main() -> int:
    out_dir = ROOT / "artifacts" / "m42" / "prompt-intelligence-v2"
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "domains": {},
        "videoProbe": resolve_live_video_provider(),
        "liveRequired": True,
        "notes": [],
    }

    # Image — dry harness with controlled PNG (Comfy live optional)
    img = start_suite_run("image-core", provider_id="comfyui", samples_per_strategy=1, dry_run=False)
    img_st = _wait(img.suiteRunId)
    report["domains"]["image"] = {
        "suiteRunId": img.suiteRunId,
        "status": img_st,
        "live": False,
        "note": "Controlled PNG fixture via runner; Comfy enqueue available via ops when healthy.",
    }
    evaluate_category(
        provider_id="comfyui",
        model_revision="default",
        domain="image",
        category="portrait",
        suite_run_id=img.suiteRunId,
    )

    # Video — prefer healthy provider; Hunyuan may be pending
    video_probe = report["videoProbe"]
    video_provider = video_probe.get("selected") or "ltx-local"
    vid = start_suite_run("video-core", provider_id=video_provider, samples_per_strategy=1, dry_run=False)
    vid_st = _wait(vid.suiteRunId)
    report["domains"]["video"] = {
        "suiteRunId": vid.suiteRunId,
        "providerId": video_provider,
        "status": vid_st,
        "probe": video_probe,
        "live": bool(video_probe.get("healthy")),
        "hunyuanPending": any(
            p.get("providerId", "").startswith("hunyuan") and p.get("status") == "pending"
            for p in (video_probe.get("probes") or [])
        ),
    }
    evaluate_category(
        provider_id=video_provider,
        model_revision="default",
        domain="video",
        category="camera_movement",
        suite_run_id=vid.suiteRunId,
    )

    # Audio
    aud = start_suite_run("audio-core", provider_id="audio-studio", samples_per_strategy=1, dry_run=False)
    aud_st = _wait(aud.suiteRunId)
    report["domains"]["audio"] = {
        "suiteRunId": aud.suiteRunId,
        "status": aud_st,
        "live": False,
        "note": "Controlled WAV fixture; Audio Studio live path when ACE-Step healthy.",
    }
    evaluate_category(
        provider_id="audio-studio",
        model_revision="default",
        domain="audio",
        category="emotional_music_cue",
        suite_run_id=aud.suiteRunId,
    )

    # Voice
    voice = start_suite_run("voice-core", provider_id="qwen3-tts", samples_per_strategy=1, dry_run=True)
    voice_st = _wait(voice.suiteRunId)
    report["domains"]["voice"] = {
        "suiteRunId": voice.suiteRunId,
        "status": voice_st,
        "live": False,
        "note": "Dry-run matrix; live TTS when qwen3-tts/kokoro healthy.",
    }

    report["recommendationSample"] = resolve_strategy_recommendation(
        domain="image",
        category="portrait",
        provider_id="comfyui",
        strategy_mode="recommend",
    ).model_dump(mode="json")
    report["finishedAt"] = datetime.now(timezone.utc).isoformat()
    report["verdictHint"] = (
        "GO if suite/run infra + evidence + blind review + promote/rollback + no silent auto-apply; "
        "Hunyuan pending does not block."
    )

    path = out_dir / "live-evidence-summary.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(path), "videoProvider": video_provider}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
