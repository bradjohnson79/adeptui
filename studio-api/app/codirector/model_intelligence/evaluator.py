"""Post-generation model-aware evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .schemas import AudioChannelPolicy, EvaluationResult, NormalizedGenerationIntent


def evaluate_result(
    *,
    intent: NormalizedGenerationIntent,
    model_id: str,
    artifact_path: Optional[str] = None,
    generation_status: str = "",
    parameters: Optional[dict[str, Any]] = None,
    audio_probe: Optional[dict[str, Any]] = None,
) -> EvaluationResult:
    findings: list[str] = []
    codes: list[str] = []
    band: str = "PASS"

    if generation_status in ("failed", "cancelled", "interrupted"):
        return EvaluationResult(
            band="REJECT",
            findings=[f"Generation status={generation_status}"],
            modelId=model_id,
            failureCodes=["generation_failed"],
        )

    if not artifact_path:
        return EvaluationResult(
            band="REJECT",
            findings=["No artifact path — file existence required for approval"],
            modelId=model_id,
            failureCodes=["missing_artifact"],
        )

    path = Path(artifact_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return EvaluationResult(
            band="REJECT",
            findings=["Artifact missing or empty"],
            modelId=model_id,
            failureCodes=["invalid_artifact"],
        )

    findings.append(f"Artifact present ({path.stat().st_size} bytes)")

    params = parameters or {}
    music_prohibited = intent.audioIntent.music == AudioChannelPolicy.PROHIBITED
    if music_prohibited:
        if params.get("generate_audio") is True:
            band = "REVIEW_REQUIRED"
            codes.append("music_param_not_suppressed")
            findings.append("Music prohibited but generate_audio remained true")
        probe = audio_probe or {}
        if probe.get("probableMusic"):
            band = "REJECT" if band != "REJECT" else band
            if band != "REJECT":
                band = "REJECT"
            codes.append("unwanted_music_detected")
            findings.append("Audio probe indicates probable background music")
        elif probe.get("checked") is False:
            if band == "PASS":
                band = "PASS_WITH_WARNINGS"
            findings.append("Music prohibition requested; live audio probe not available")
            codes.append("music_probe_unavailable")

    if intent.durationSec is not None and params.get("durationSec") is not None:
        if abs(float(params["durationSec"]) - float(intent.durationSec)) > 0.51:
            if band == "PASS":
                band = "PASS_WITH_WARNINGS"
            findings.append("Duration differs from requested (may be model clamp)")

    return EvaluationResult(
        band=band,  # type: ignore[arg-type]
        findings=findings,
        modelId=model_id,
        failureCodes=codes,
    )
