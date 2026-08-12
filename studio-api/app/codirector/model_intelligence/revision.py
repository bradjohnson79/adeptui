"""Targeted revision intelligence — no blind paid retries."""

from __future__ import annotations

from typing import Any, Optional

from .schemas import EvaluationResult, NormalizedGenerationIntent, RevisionPlan


def propose_revision(
    *,
    intent: NormalizedGenerationIntent,
    evaluation: EvaluationResult,
    compile_parameters: Optional[dict[str, Any]] = None,
    attempt: int = 1,
) -> RevisionPlan:
    actions: list[dict[str, Any]] = []
    codes = list(evaluation.failureCodes or [])

    if attempt >= 2:
        return RevisionPlan(
            actions=[
                {
                    "action": "stop",
                    "reason": "Paid/retry loop guard — human review required after prior attempt",
                }
            ],
            reason="prevent_uncontrolled_retry",
            preventPaidLoop=True,
            originalFailureCodes=codes,
        )

    if "unwanted_music_detected" in codes or "music_param_not_suppressed" in codes:
        actions.append(
            {
                "action": "strengthen_music_exclusion",
                "parameters": {"generate_audio": False},
                "promptDelta": "Add stronger no-score / no-music negatives",
            }
        )
        actions.append(
            {
                "action": "prefer_external_audio_pipeline",
                "reason": "Generate silent/visual motion then place imported audio",
            }
        )
        actions.append(
            {
                "action": "consider_model_switch",
                "candidates": ["fal_seedance", "ltx_2_5_distilled", "ltx_2_5_full", "ltx_2_3"],
                "reason": "Prefer engines with explicit audio off or no native soundtrack",
            }
        )

    if "missing_artifact" in codes or "invalid_artifact" in codes:
        actions.append({"action": "do_not_approve", "reason": "No real artifact"})
        actions.append({"action": "inspect_job", "reason": "Check provider error before retry"})

    if "generation_failed" in codes:
        actions.append({"action": "reduce_prompt_complexity"})
        actions.append({"action": "shorten_duration"})

    if not actions:
        actions.append(
            {
                "action": "human_review",
                "reason": "No automated revision mapped for failure codes",
            }
        )

    return RevisionPlan(
        actions=actions,
        reason="; ".join(codes) or evaluation.band,
        preventPaidLoop=True,
        originalFailureCodes=codes,
    )
