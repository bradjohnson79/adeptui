#!/usr/bin/env python3
"""M3.0i: exactly one Studio-queue Seedance music-off job (authorized live gate).

Requires ADEPT_M30I_FAL_LIVE=1 and FAL_KEY/FAL_API_KEY.
Zero automatic retries. Persist Studio job ID + fal request ID. Recover by ID.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "m30i" / "live-fal-music-off"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "studio-api"))

API = os.environ.get("ADEPT_API_BASE", "http://127.0.0.1:8765").rstrip("/")
# Mild cinematic prompt — prior "suspense" wording tripped fal content_policy (422).
# Changing this does NOT auto-resubmit; a human must set ADEPT_M30I_FAL_FORCE=1.
PROMPT = (
    "Quiet empty hallway at dusk, soft window light, dust in the air, "
    "no people, no dialogue, room ambience only, no background music, "
    "locked camera, cinematic still atmosphere."
)
ESTIMATED_MAX_USD = 1.50
ALLOWED = {
    "NO_AUDIO_STREAM",
    "AUDIO_STREAM_WITH_NO_DETECTED_MUSIC",
    "AUDIO_STREAM_WITH_AMBIENCE_ONLY",
}
PROOF = OUT / "live_proof.json"
SUBMITTED_MARKER = OUT / "submitted.lock.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, payload: Any) -> None:
    path = OUT / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_media(path: Path | None) -> dict[str, Any]:
    if not path or not path.is_file():
        return {"classification": "ARTIFACT_UNAVAILABLE", "streams": []}
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
            timeout=60,
            check=False,
        )
        data = json.loads(proc.stdout or "{}")
        streams = data.get("streams") or []
        audio = [s for s in streams if s.get("codec_type") == "audio"]
        video = [s for s in streams if s.get("codec_type") == "video"]
        _write("media_streams.json", {"streams": streams, "path": str(path)})
        if not audio:
            return {
                "classification": "NO_AUDIO_STREAM",
                "streams": streams,
                "videoStreams": len(video),
                "method": "ffprobe_no_audio_stream",
            }
        # Presence of audio without automated music detector → require human confirmation.
        # Default honest class when human notes ambience-only:
        return {
            "classification": "INCONCLUSIVE",
            "streams": streams,
            "audioStreams": len(audio),
            "method": "ffprobe_audio_present_music_detector_not_automated",
            "note": "Human playback must distinguish ambience vs music before GREEN upgrade",
        }
    except FileNotFoundError:
        return {"classification": "INCONCLUSIVE", "reason": "ffprobe_unavailable"}
    except Exception as exc:  # noqa: BLE001
        return {"classification": "INCONCLUSIVE", "reason": str(exc)}


def compile_mil() -> dict[str, Any]:
    from app.codirector.language_intelligence.audio_phrases import (
        normalize_audio_from_multilingual_text,
    )
    from app.codirector.model_intelligence.compiler import compile_intent
    from app.codirector.model_intelligence.preflight import run_preflight
    from app.codirector.model_intelligence.schemas import NormalizedGenerationIntent

    audio = normalize_audio_from_multilingual_text(PROMPT)
    intent = NormalizedGenerationIntent(
        userPrompt=PROMPT,
        mode="text_to_video",
        mediaType="video",
        forceModelId="fal_seedance",
        projectContext={"sourceLanguage": "en", "promptLanguagePolicy": "english"},
        audioIntent=audio,
    )
    compiled = compile_intent(intent, model_id="fal_seedance")
    preflight = run_preflight(intent, model_id="fal_seedance")
    normalized = {
        "originalUserRequest": PROMPT,
        "audioIntent": audio.model_dump() if hasattr(audio, "model_dump") else dict(audio),
        "music": getattr(audio, "music", None),
    }
    model_selection = {
        "selectedModel": compiled.modelId,
        "knowledgePackVersion": compiled.knowledgePackVersion,
    }
    compiled_job = {
        "compiledPrompt": compiled.compiledPrompt,
        "parameters": compiled.parameters,
        "generate_audio": compiled.parameters.get("generate_audio"),
        "sourceLanguage": compiled.sourceLanguage,
        "promptLanguage": compiled.promptLanguage,
    }
    preflight_doc = {
        "status": preflight.status.value if hasattr(preflight.status, "value") else str(preflight.status),
        "issues": getattr(preflight, "issues", None),
    }
    _write("request.json", {"prompt": PROMPT, "engine": "fal_seedance"})
    _write("normalized_intent.json", normalized)
    _write("model_selection.json", model_selection)
    _write(
        "knowledge_pack.json",
        {"modelId": compiled.modelId, "version": compiled.knowledgePackVersion},
    )
    _write("compiled_job.json", compiled_job)
    _write("preflight.json", preflight_doc)
    return {
        "normalized": normalized,
        "compiled": compiled_job,
        "preflight": preflight_doc,
        "ok": compiled.parameters.get("generate_audio") is False,
    }


def main() -> int:
    live = os.environ.get("ADEPT_M30I_FAL_LIVE") == "1"
    has_key = bool(os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY"))
    # Also accept .env without exporting
    if not has_key:
        env_path = ROOT / ".env"
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip().startswith(("FAL_KEY=", "FAL_API_KEY=")):
                    has_key = True
                    break

    proof: dict[str, Any] = {
        "startedAt": _now(),
        "milestone": "M3.0i",
        "liveEnabled": live,
        "falKeyPresent": has_key,
        "estimatedMaxSpendUsd": ESTIMATED_MAX_USD,
        "maxSubmissions": 1,
        "maxAutomaticRetries": 0,
        "providerSubmissionCount": 0,
    }

    mil = compile_mil()
    proof["compileOk"] = mil["ok"]
    if not mil["ok"]:
        proof["status"] = "FAILED_COMPILE"
        proof["audioInspection"] = {"classification": "INCONCLUSIVE"}
        _write("live_proof.json", proof)
        print(json.dumps({"status": proof["status"]}, indent=2))
        return 2

    if not live or not has_key:
        proof["status"] = "BLOCKED_NO_LIVE_GENERATE"
        proof["audioInspection"] = {"classification": "INCONCLUSIVE", "reason": "flag_or_key_missing"}
        proof["finishedAt"] = _now()
        _write("live_proof.json", proof)
        print(json.dumps({"status": proof["status"]}, indent=2))
        return 0

    if SUBMITTED_MARKER.is_file() and os.environ.get("ADEPT_M30I_FAL_FORCE") != "1":
        prior = json.loads(SUBMITTED_MARKER.read_text(encoding="utf-8"))
        proof["status"] = "REFUSED_PRIOR_SUBMIT"
        proof["prior"] = prior
        proof["note"] = "A paid submit already recorded; refusing duplicate (set ADEPT_M30I_FAL_FORCE=1 only for explicit human rerun)"
        _write("live_proof.json", proof)
        print(json.dumps({"status": proof["status"]}, indent=2))
        return 3

    import httpx

    print(f"[m30i-fal] estimated max spend <= ${ESTIMATED_MAX_USD:.2f}; submitting ONE Studio txt2vid job", flush=True)

    with httpx.Client(base_url=API, timeout=30.0) as client:
        health = client.get("/api/health")
        if health.status_code >= 400:
            proof["status"] = "PROVIDER_FAILED"
            proof["error"] = f"API health {health.status_code}"
            _write("live_proof.json", proof)
            return 2

        proj = client.post("/api/projects", json={"name": f"M30I Music-Off {datetime.now().strftime('%H%M%S')}"})
        proj.raise_for_status()
        project_id = proj.json()["id"]
        proof["projectId"] = project_id

        body = {
            "prompt": mil["compiled"]["compiledPrompt"] or PROMPT,
            "engine": "fal_seedance",
            "durationSec": 4,
            "generate_audio": False,
            "modelIntelligence": {
                "compiledPrompt": mil["compiled"]["compiledPrompt"],
                "generate_audio": False,
                "parameters": mil["compiled"]["parameters"],
            },
            "m30i": True,
            "musicProhibited": True,
        }
        # ONE submit — no retry loop
        submit = client.post(f"/api/projects/{project_id}/txt2vid", json=body)
        if submit.status_code >= 400:
            proof["status"] = "PROVIDER_FAILED"
            proof["submit"] = {"status": submit.status_code, "body": submit.text[:500]}
            _write("live_proof.json", proof)
            return 2

        job = submit.json()
        studio_job_id = job.get("id")
        proof["providerSubmissionCount"] = 1
        proof["studioJobId"] = studio_job_id
        SUBMITTED_MARKER.write_text(
            json.dumps({"studioJobId": studio_job_id, "submittedAt": _now()}, indent=2),
            encoding="utf-8",
        )
        _write("queue_job.json", {"submitResponse": job, "params": body})

        # Poll existing job only — never resubmit
        fal_request_id = None
        artifact_path = None
        final_status = None
        deadline = time.time() + 900
        while time.time() < deadline:
            jr = client.get(f"/api/jobs/{studio_job_id}")
            if jr.status_code >= 400:
                break
            data = jr.json()
            final_status = data.get("status")
            hist = data.get("history_json") or data.get("history")
            if isinstance(hist, str):
                try:
                    hist = json.loads(hist)
                except Exception:  # noqa: BLE001
                    hist = {}
            if isinstance(hist, dict):
                fal_request_id = hist.get("falRequestId") or fal_request_id
            msg = data.get("message") or ""
            if data.get("result_path") or data.get("resultPath"):
                artifact_path = data.get("result_path") or data.get("resultPath")
            if final_status in ("done", "succeeded", "success", "failed", "error", "blocked"):
                _write("provider_result.json", data)
                break
            time.sleep(5)
        else:
            # Timeout: recover by ID, do not resubmit
            jr = client.get(f"/api/jobs/{studio_job_id}")
            data = jr.json() if jr.status_code < 400 else {}
            _write("provider_result.json", {"timeout": True, "job": data})
            proof["status"] = "PROVIDER_SUCCESS_ARTIFACT_RETRIEVAL_FAILED" if data else "PROVIDER_FAILED"
            proof["studioJobId"] = studio_job_id
            proof["falRequestId"] = fal_request_id
            proof["audioInspection"] = {"classification": "INCONCLUSIVE", "reason": "timeout"}
            proof["finishedAt"] = _now()
            _write("live_proof.json", proof)
            print(json.dumps({"status": proof["status"], "studioJobId": studio_job_id}, indent=2))
            return 1

        proof["falRequestId"] = fal_request_id
        proof["jobStatus"] = final_status

        if final_status not in ("done", "succeeded", "success"):
            proof["status"] = "PROVIDER_FAILED"
            proof["audioInspection"] = {"classification": "PROVIDER_FAILED"}
            _write(
                "cost_record.json",
                {"estimatedMaxUsd": ESTIMATED_MAX_USD, "actualUsd": None, "submissions": 1},
            )
            proof["finishedAt"] = _now()
            _write("live_proof.json", proof)
            print(json.dumps({"status": proof["status"]}, indent=2))
            return 1

        # Locate artifact
        media_file = None
        if artifact_path:
            p = Path(artifact_path)
            if p.is_file():
                media_file = p
        if media_file is None:
            # search common export under data
            candidates = list((ROOT / "studio-api").glob(f"**/*{studio_job_id[:8]}*"))
            for c in candidates:
                if c.suffix.lower() in {".mp4", ".webm", ".mov"}:
                    media_file = c
                    break

        meta = {
            "studioJobId": studio_job_id,
            "falRequestId": fal_request_id,
            "path": str(media_file) if media_file else None,
            "sha256": _sha256(media_file) if media_file and media_file.is_file() else None,
            "sizeBytes": media_file.stat().st_size if media_file and media_file.is_file() else None,
        }
        _write("artifact_metadata.json", meta)

        audio = classify_media(media_file)
        # Human playback: document requirement; if no audio stream, GREEN without music risk
        playback = {
            "tester": "Cursor agent on Brad machine",
            "date": _now(),
            "result": "NOT_RUN" if audio.get("classification") == "INCONCLUSIVE" and audio.get("audioStreams") else (
                "NO_AUDIO_CONFIRMED" if audio.get("classification") == "NO_AUDIO_STREAM" else "PENDING_HUMAN"
            ),
            "notes": (
                "ffprobe found no audio stream — music cannot be present."
                if audio.get("classification") == "NO_AUDIO_STREAM"
                else "Audio stream present; music vs ambience requires human ear confirmation before GREEN."
            ),
        }
        _write("human_playback_check.md", "# Human playback\n\n" + json.dumps(playback, indent=2))
        _write("audio_analysis.json", audio)

        if audio.get("classification") == "NO_AUDIO_STREAM":
            # Upgrade to GREEN with documented method
            pass
        elif audio.get("classification") in ALLOWED:
            pass
        else:
            # Keep INCONCLUSIVE — do not invent ambience-only without hearing
            audio["classification"] = audio.get("classification") or "INCONCLUSIVE"

        _write(
            "cost_record.json",
            {
                "estimatedMaxUsd": ESTIMATED_MAX_USD,
                "actualUsd": None,
                "submissions": 1,
                "studioJobId": studio_job_id,
                "falRequestId": fal_request_id,
            },
        )

        classification = audio.get("classification")
        proof["audioInspection"] = audio
        proof["humanPlayback"] = playback
        proof["artifact"] = meta
        if classification in ALLOWED:
            proof["status"] = "GREEN"
            proof["closesM30gMiLive"] = True
            proof["closesM30hS3"] = True
        else:
            proof["status"] = classification if classification else "INCONCLUSIVE"
            proof["closesM30gMiLive"] = False
            proof["closesM30hS3"] = False
        proof["finishedAt"] = _now()
        _write("live_proof.json", proof)
        print(
            json.dumps(
                {
                    "status": proof["status"],
                    "classification": classification,
                    "studioJobId": studio_job_id,
                    "falRequestId": fal_request_id,
                },
                indent=2,
            )
        )
        return 0 if classification in ALLOWED else 1


if __name__ == "__main__":
    raise SystemExit(main())
