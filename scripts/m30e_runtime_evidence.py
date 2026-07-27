#!/usr/bin/env python3
"""Collect M3.0e Model Intelligence runtime evidence (no fabricated proofs)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

OUT = ROOT / "artifacts" / "m30e-mil"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    from app.codirector.model_intelligence.compiler import compile_intent, normalize_audio_from_text
    from app.codirector.model_intelligence.evaluator import evaluate_result
    from app.codirector.model_intelligence.loader import validate_all
    from app.codirector.model_intelligence.preflight import run_preflight
    from app.codirector.model_intelligence.revision import propose_revision
    from app.codirector.model_intelligence.schemas import (
        AudioChannelPolicy,
        AudioIntent,
        NormalizedGenerationIntent,
    )
    from app.codirector.model_intelligence.selector import recommend

    evidence: dict = {
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "packValidation": validate_all(),
        "proofs": {},
    }

    # Recommendation comparison
    intent_video = NormalizedGenerationIntent(
        userPrompt="Cinematic I2V. No background music.",
        mode="image_to_video",
        mediaType="video",
        hasSourceImage=True,
        audioIntent=normalize_audio_from_text("No background music"),
    )
    rec = recommend(intent_video)
    evidence["proofs"]["recommendation"] = rec.model_dump(mode="json")

    # LTX no-music compile (path only — generation may be experimental)
    ltx = compile_intent(intent_video, model_id="ltx_2_3")
    evidence["proofs"]["ltx_no_music_compile"] = ltx.model_dump(mode="json")

    # fal Seedance music prohibited compile
    fal = compile_intent(intent_video, model_id="fal_seedance")
    evidence["proofs"]["fal_seedance_no_music_compile"] = fal.model_dump(mode="json")

    # Z-Image still compile
    still = compile_intent(
        NormalizedGenerationIntent(
            userPrompt="Portrait still, soft window light",
            mode="text_to_image",
            mediaType="image",
        ),
        model_id="z_image",
    )
    evidence["proofs"]["z_image_compile"] = still.model_dump(mode="json")

    # Unsupported preflight
    blocked = run_preflight(
        NormalizedGenerationIntent(
            userPrompt="still",
            mode="text_to_image",
            mediaType="image",
            forceModelId="seedream",
        ),
        model_id="seedream",
    )
    evidence["proofs"]["unsupported_preflight"] = blocked.model_dump(mode="json")

    # Evaluation + revision (artifact = this script as stand-in file existence)
    evaluation = evaluate_result(
        intent=intent_video,
        model_id="fal_seedance",
        artifact_path=str(Path(__file__).resolve()),
        generation_status="done",
        parameters={"generate_audio": False},
        audio_probe={"checked": False},
    )
    revision = propose_revision(intent=intent_video, evaluation=evaluation)
    evidence["proofs"]["evaluation"] = evaluation.model_dump(mode="json")
    evidence["proofs"]["revision"] = revision.model_dump(mode="json")

    # Reuse prior fal motion proof if present — do not invent music-suppression live run
    fal_proof = ROOT / "artifacts" / "m30c-fal" / "unified_queue_proof.json"
    if fal_proof.is_file():
        prior = json.loads(fal_proof.read_text(encoding="utf-8"))
        evidence["proofs"]["fal_motion_reused"] = {
            "path": str(fal_proof),
            "outcome": prior.get("outcome"),
            "jobId": (prior.get("queueSubmit") or {}).get("jobId"),
            "musicSuppressionLive": "NOT_RUN_IN_M30E",
            "note": "Prior motion SUCCESS reused; generate_audio=false live generate not repeated to avoid spend",
        }
    else:
        evidence["proofs"]["fal_motion_reused"] = {"status": "ABSENT"}

    evidence["finishedAt"] = datetime.now(timezone.utc).isoformat()
    evidence["status"] = "PARTIAL_RUNTIME"
    # Certification completeness requires live gen when available; compile proofs are complete.
    (OUT / "runtime_evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(OUT / "runtime_evidence.json"), "status": evidence["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
