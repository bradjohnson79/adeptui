#!/usr/bin/env python3
"""M3.0h Hybrid live gate for S3 Dialogue-Free music-off.

Set ADEPT_M30H_FAL_LIVE=1 and FAL_KEY/FAL_API_KEY to execute paid generation.
Otherwise archives BLOCKED evidence (forces overall M3.0h NO per Hybrid rule).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "m30h" / "dialogue-free" / "live_fal"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "studio-api"))

ALLOWED = {
    "NO_AUDIO_STREAM",
    "AUDIO_STREAM_WITH_NO_DETECTED_MUSIC",
    "AUDIO_STREAM_WITH_AMBIENCE_ONLY",
}


def classify_media(path: Path | None) -> dict:
    if not path or not path.is_file():
        return {"classification": "INCONCLUSIVE", "reason": "artifact_missing", "streams": []}
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=index,codec_type,codec_name",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        data = json.loads(proc.stdout or "{}")
        streams = data.get("streams") or []
        audio = [s for s in streams if s.get("codec_type") == "audio"]
        if not audio:
            return {
                "classification": "NO_AUDIO_STREAM",
                "reason": "ffprobe_no_audio_stream",
                "streams": streams,
                "humanPlayback": "NOT_RUN",
            }
        return {
            "classification": "INCONCLUSIVE",
            "reason": "audio_stream_present_music_detection_not_automated",
            "streams": streams,
            "humanPlayback": "REQUIRED",
        }
    except FileNotFoundError:
        return {"classification": "INCONCLUSIVE", "reason": "ffprobe_unavailable", "streams": []}
    except Exception as exc:  # noqa: BLE001
        return {"classification": "INCONCLUSIVE", "reason": f"ffprobe_error:{exc}", "streams": []}


def compile_proof() -> dict:
    from app.codirector.model_intelligence.compiler import compile_intent
    from app.codirector.model_intelligence.schemas import NormalizedGenerationIntent

    original = (
        "Create a suspense sequence with no dialogue. Ambient sound only. No music. "
        "Keep the camera locked."
    )
    intent = NormalizedGenerationIntent(
        userPrompt=original,
        mode="text_to_video",
        mediaType="video",
        forceModelId="fal_seedance",
        projectContext={"sourceLanguage": "en", "promptLanguagePolicy": "english"},
    )
    compiled = compile_intent(intent, model_id="fal_seedance")
    return {
        "originalUserRequest": original,
        "selectedModel": compiled.modelId,
        "compiledParameters": compiled.parameters,
        "generate_audio": compiled.parameters.get("generate_audio"),
        "sourceLanguage": compiled.sourceLanguage,
        "promptLanguage": compiled.promptLanguage,
    }


def main() -> int:
    live = os.environ.get("ADEPT_M30H_FAL_LIVE") == "1"
    has_key = bool(os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY"))
    proof = {
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "milestone": "M3.0h",
        "scenario": "S3 Dialogue-Free",
        "liveEnabled": live,
        "falKeyPresent": has_key,
        "compile": compile_proof(),
        "m30gDependency": (
            "M3.0g platform certification dependency: REMAINS OPEN "
            "(MI-LIVE INCONCLUSIVE / a11y NOT GREEN — M3.0h does not close these)"
        ),
    }
    if proof["compile"].get("generate_audio") is not False:
        proof["status"] = "FAILED_COMPILE"
        proof["audioInspection"] = {"classification": "INCONCLUSIVE"}
        (OUT / "live_proof.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
        return 2

    if not live or not has_key:
        proof["liveJob"] = {
            "outcome": "NOT_RUN",
            "reason": "ADEPT_M30H_FAL_LIVE!=1 or FAL key missing",
            "note": "Prior motion reuse is NOT a music-off SUCCESS substitute",
        }
        proof["audioInspection"] = {
            "classification": "INCONCLUSIVE",
            "reason": "live_generate_not_executed",
        }
        proof["status"] = "BLOCKED_NO_LIVE_GENERATE"
        proof["forcesOverallNo"] = True
        proof["finishedAt"] = datetime.now(timezone.utc).isoformat()
        (OUT / "live_proof.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
        print(json.dumps({"status": proof["status"], "classification": "INCONCLUSIVE"}, indent=2))
        return 0

    proof["liveJob"] = {
        "outcome": "OPERATOR_REQUIRED",
        "note": "Submit one Seedance job via shared Studio queue with generate_audio=false; "
        "archive jobId + fal requestId; classify audio with ffprobe/human playback.",
    }
    proof["audioInspection"] = classify_media(None)
    proof["status"] = "LIVE_HARNESS_READY"
    proof["allowedGreenClasses"] = sorted(ALLOWED)
    proof["finishedAt"] = datetime.now(timezone.utc).isoformat()
    (OUT / "live_proof.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    print(json.dumps({"status": proof["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
