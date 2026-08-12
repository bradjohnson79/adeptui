"""Creative director review pass for bundled specialist findings."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import uuid4

from app.codirector.foundation.contracts import CreativeDirectorReview, SpecialistResult

_CONTRADICTION_SIGNALS: tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...] = (
    (("static", "locked"), ("handheld", "kinetic"), "Camera movement guidance conflicts."),
    (("bright", "soft"), ("dark", "shadow"), "Lighting direction points in opposite moods."),
    (("wide", "distant"), ("close", "intimate"), "Framing guidance mixes opposing proximity goals."),
    (("sparse", "minimal"), ("dense", "layered"), "Design density recommendations conflict."),
    (("silence", "quiet"), ("music-driven", "wall of sound"), "Sound strategy alternates between restraint and heavy scoring."),
)


def _collect_texts(findings: Iterable[SpecialistResult]) -> list[str]:
    texts: list[str] = []
    for finding in findings:
        texts.extend(
            [
                finding.summary,
                finding.recommendation,
                *finding.findings,
                *finding.opportunities,
                *[item.text for item in finding.recommendations],
            ]
        )
    return [" ".join(str(text).lower().split()) for text in texts if str(text or "").strip()]


def _detect_contradictions(findings: list[SpecialistResult]) -> list[str]:
    texts = _collect_texts(findings)
    contradictions: list[str] = []
    corpus = " ".join(texts)
    for left, right, note in _CONTRADICTION_SIGNALS:
        if any(token in corpus for token in left) and any(token in corpus for token in right):
            contradictions.append(note)
    return contradictions


def _profile_fit_notes(domain_profile_ids: list[str], findings: list[SpecialistResult]) -> list[str]:
    notes: list[str] = []
    profiles = [profile.lower() for profile in domain_profile_ids if profile]
    selected = {finding.specialistId for finding in findings}

    if any("audio" in profile or "podcast" in profile for profile in profiles) and "sound_director" not in selected:
        notes.append("Audio-focused profile is active, but the bundle does not include sound direction.")
    if any("animation" in profile for profile in profiles) and "performance_director" not in selected:
        notes.append("Animation profile usually benefits from explicit performance direction.")
    if any("horror" in profile or "thriller" in profile for profile in profiles) and "lighting_director" not in selected:
        notes.append("Suspense-oriented profiles usually need deliberate lighting guidance.")
    if profiles and not notes:
        notes.append("Selected specialists broadly fit the active domain profile set.")
    return notes[:3]


def _prioritized_recommendations(findings: list[SpecialistResult]) -> list[str]:
    weighted: list[tuple[int, int, str]] = []
    priority_weight = {"high": 0, "medium": 1, "low": 2}
    for finding_index, finding in enumerate(findings):
        for rec_index, recommendation in enumerate(finding.recommendations):
            text = recommendation.text.strip()
            if not text:
                continue
            weighted.append((priority_weight.get(recommendation.priority, 1), finding_index * 10 + rec_index, text))
        if not finding.recommendations and finding.recommendation.strip():
            weighted.append((1, finding_index * 10, finding.recommendation.strip()))

    ordered: list[str] = []
    seen: set[str] = set()
    for _, _, text in sorted(weighted):
        if text not in seen:
            seen.add(text)
            ordered.append(text)
    return ordered[:5]


def review_specialist_bundle(
    project_id: str,
    user_message: str,
    findings: list[SpecialistResult],
    domain_profile_ids: list[str] | None,
    vision_summary: str = "",
) -> CreativeDirectorReview:
    """Review specialist output for alignment, usefulness, and overload."""

    contradictions = _detect_contradictions(findings)
    practical: list[str] = []
    complexity: list[str] = []
    notes: list[str] = []
    keep_ids: list[str] = []
    drop_ids: list[str] = []

    message = " ".join((user_message or "").lower().split())
    vision = " ".join((vision_summary or "").lower().split())

    for finding in findings:
        if finding.status == "failed" or finding.contentDropped:
            drop_ids.append(finding.specialistId)
            notes.append(f"Dropped {finding.specialistId} because the result was incomplete.")
            continue
        if finding.blockingIssues:
            practical.append(f"{finding.specialistId} surfaced blockers: {'; '.join(finding.blockingIssues[:2])}")
        if len(finding.questions) > 1:
            complexity.append(f"{finding.specialistId} asked for too many follow-ups for a foundation pass.")
        if finding.confidence < 0.45:
            drop_ids.append(finding.specialistId)
            notes.append(f"Dropped {finding.specialistId} because confidence is too low to guide synthesis.")
            continue
        if finding.specialistId not in keep_ids:
            keep_ids.append(finding.specialistId)

    if len(keep_ids) > 4:
        complexity.append("The bundle is wide enough to risk overload; synthesis should keep only the strongest threads.")
    if any(len(finding.recommendations) > 2 for finding in findings):
        complexity.append("Several specialists are suggesting multiple directions, so prioritization is required.")
    if contradictions:
        practical.append("Contradictions should be resolved before the creator is asked to react to the bundle.")

    if vision and not any(token in " ".join(_collect_texts(findings)) for token in vision.split()[:3]):
        notes.append("Vision summary is present but only weakly echoed by the current specialist bundle.")
    if "simple" in message and len(keep_ids) > 2:
        complexity.append("The creator request sounds simple, but the bundle may be broader than necessary.")

    overload_score = len(keep_ids) + len(contradictions) + sum(len(f.blockingIssues) > 0 for f in findings)
    overload = "low"
    if overload_score >= 5:
        overload = "high"
    elif overload_score >= 3:
        overload = "medium"

    aligned = not contradictions
    if vision:
        aligned = aligned and not any("weakly echoed" in note for note in notes)

    return CreativeDirectorReview(
        reviewId=f"cdr-{uuid4().hex[:12]}",
        projectId=project_id,
        alignedWithVision=aligned,
        contradictions=contradictions,
        practicalityNotes=practical[:4],
        complexityWarnings=complexity[:4],
        profileFitNotes=_profile_fit_notes(domain_profile_ids or [], findings),
        overloadRisk=overload,
        keepSpecialistIds=keep_ids,
        dropSpecialistIds=drop_ids,
        prioritizedRecommendations=_prioritized_recommendations([f for f in findings if f.specialistId in keep_ids]),
        maxQuestions=1 if any(f.questions for f in findings) else 0,
        notes=notes[:4],
    )


__all__ = ["review_specialist_bundle"]
