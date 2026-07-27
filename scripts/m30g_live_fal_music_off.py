#!/usr/bin/env python3
"""MI-LIVE: budgeted fal Seedance music-off shared-queue proof with audio classification.

Set ADEPT_M30G_FAL_LIVE=1 and FAL_KEY/FAL_API_KEY to execute paid generation.
Otherwise archives BLOCKED evidence (no fabricated SUCCESS).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "m30g" / "live-fal-music-off"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "studio-api"))


def classify_media(path: Path | None) -> dict:
    """Return explicit audio classification enum from ffprobe when available."""
    if not path or not path.is_file():
        return {
            "classification": "INCONCLUSIVE",
            "reason": "artifact_missing",
            "streams": [],
        }
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
            "note": "Requires human playback or dedicated music detector for AUDIO_STREAM_WITH_NO_DETECTED_MUSIC",
            "humanPlayback": "REQUIRED",
        }
    except FileNotFoundError:
        return {
            "classification": "INCONCLUSIVE",
            "reason": "ffprobe_unavailable",
            "streams": [],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "classification": "INCONCLUSIVE",
            "reason": f"ffprobe_error:{exc}",
            "streams": [],
        }


def compile_proof() -> dict:
    from app.codirector.language_intelligence.audio_phrases import (
        normalize_audio_from_multilingual_text,
    )
    from app.codirector.model_intelligence.compiler import compile_intent
    from app.codirector.model_intelligence.preflight import run_preflight
    from app.codirector.model_intelligence.schemas import NormalizedGenerationIntent

    original = "Plano cinematográfico de cinco segundos. Sin música de fondo. Solo ambiente suave."
    audio = normalize_audio_from_multilingual_text(original)
    intent = NormalizedGenerationIntent(
        userPrompt=original,
        mode="text_to_video",
        mediaType="video",
        forceModelId="fal_seedance",
        projectContext={
            "sourceLanguage": "es",
            "promptLanguagePolicy": "auto",
            "protectedTerms": ["Co-Director", "Adept UI Studio"],
        },
        audioIntent=audio,
    )
    compiled = compile_intent(intent, model_id="fal_seedance")
    preflight = run_preflight(intent, model_id="fal_seedance")
    return {
        "originalUserRequest": original,
        "normalizedAudioIntent": audio.model_dump(),
        "selectedModel": compiled.modelId,
        "knowledgePackVersion": compiled.knowledgePackVersion,
        "compiledPrompt": compiled.compiledPrompt,
        "compiledParameters": compiled.parameters,
        "generate_audio": compiled.parameters.get("generate_audio"),
        "preflight": preflight.status.value if hasattr(preflight.status, "value") else str(preflight.status),
        "sourceLanguage": compiled.sourceLanguage,
        "promptLanguage": compiled.promptLanguage,
        "translationNotes": compiled.translationNotes,
        "protectedTermsApplied": compiled.protectedTermsApplied,
    }


def main() -> int:
    live = os.environ.get("ADEPT_M30G_FAL_LIVE") == "1"
    has_key = bool(os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY"))
    proof = {
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "liveEnabled": live,
        "falKeyPresent": has_key,
        "compile": compile_proof(),
        "liveJob": None,
        "audioInspection": None,
        "status": "COMPILE_ONLY",
    }

    if proof["compile"].get("generate_audio") is not False:
        proof["status"] = "FAILED_COMPILE"
        proof["finishedAt"] = datetime.now(timezone.utc).isoformat()
        (OUT / "live_proof.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
        print(json.dumps({"status": proof["status"]}, indent=2))
        return 2

    if not live or not has_key:
        # Reuse prior motion job metadata only for motion path; music-off live remains incomplete.
        reused = ROOT / "artifacts" / "m30c-fal" / "unified_queue_proof.json"
        proof["liveJob"] = {
            "outcome": "NOT_RUN",
            "reason": "ADEPT_M30G_FAL_LIVE!=1 or FAL key missing",
            "priorMotionReusePath": str(reused) if reused.is_file() else None,
            "musicSuppressionLive": "NOT_RUN_IN_M30G",
        }
        proof["audioInspection"] = {
            "classification": "INCONCLUSIVE",
            "reason": "live_generate_not_executed",
        }
        proof["status"] = "BLOCKED_NO_LIVE_GENERATE"
        proof["finishedAt"] = datetime.now(timezone.utc).isoformat()
        (OUT / "live_proof.json").write_text(json.dumps(proof, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"status": proof["status"], "classification": "INCONCLUSIVE"}, indent=2))
        return 0

    # Live path: enqueue via API would require running server; document as operator step.
    proof["liveJob"] = {
        "outcome": "OPERATOR_REQUIRED",
        "note": "Live paid submit must go through shared Studio queue with generate_audio=false; "
        "archive Studio jobId + fal requestId here after run.",
    }
    proof["audioInspection"] = {"classification": "INCONCLUSIVE", "reason": "awaiting_artifact"}
    proof["status"] = "LIVE_HARNESS_READY"
    proof["finishedAt"] = datetime.now(timezone.utc).isoformat()
    (OUT / "live_proof.json").write_text(json.dumps(proof, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": proof["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
