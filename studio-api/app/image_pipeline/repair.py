"""Repair planning for image candidate iteration."""

from __future__ import annotations

from .contracts import ImageCandidateEvaluation, ImageRepairInstruction


def least_destructive_repair_ladder(evaluation: ImageCandidateEvaluation) -> list[ImageRepairInstruction]:
    if evaluation.overallStatus in {"pass", "not-evaluated"}:
        return [
            ImageRepairInstruction(
                action="hold",
                reason="No repair is justified yet.",
                keepWhatWorks=["Preserve the current composition and identity cues."],
            )
        ]

    instructions: list[ImageRepairInstruction] = [
        ImageRepairInstruction(
            action="prompt-tune",
            reason="Start with a prompt adjustment before changing composition or model route.",
            keepWhatWorks=["Keep the current framing and successful character continuity."],
            avoidChanges=["Do not swap models unless the quality issue truly requires it."],
        )
    ]
    if evaluation.defects:
        instructions.append(
            ImageRepairInstruction(
                action="targeted-repair",
                reason=f"Address the highest-risk issue first: {evaluation.defects[0].description}",
                keepWhatWorks=["Retain any working lighting, pose, and emotional read."],
            )
        )
    instructions.append(
        ImageRepairInstruction(
            action="restage",
            reason="Only restage the shot if the lighter repairs still miss the story beat.",
            keepWhatWorks=["Preserve the original storytelling intent."],
        )
    )
    return instructions


def reject_regression(
    parent: ImageCandidateEvaluation,
    child: ImageCandidateEvaluation,
) -> dict[str, object]:
    parent_fail_codes = {finding.code for finding in parent.findings if finding.status == "fail"}
    child_fail_codes = {finding.code for finding in child.findings if finding.status == "fail"}
    new_failures = sorted(child_fail_codes - parent_fail_codes)
    regressed = len(new_failures) > 0 or (
        parent.overallStatus == "warning" and child.overallStatus == "fail"
    )
    reason = (
        f"Reject the child candidate because it introduced new failures: {', '.join(new_failures)}."
        if regressed
        else "No regression was detected."
    )
    return {"rejected": regressed, "reason": reason, "newFailureCodes": new_failures}

