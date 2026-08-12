"""Deterministic creator-safe guidance composed from domain profiles."""

from __future__ import annotations

from app.codirector.foundation.contracts import DomainProfile


def _dedupe(values: list[str], *, limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _collect(profiles: list[DomainProfile], field_name: str, *, limit: int) -> list[str]:
    values: list[str] = []
    per_profile = [list(getattr(profile, field_name)) for profile in profiles]
    index = 0
    while len(values) < limit and any(index < len(items) for items in per_profile):
        for items in per_profile:
            if index < len(items):
                values.append(items[index])
                if len(values) >= limit:
                    break
        index += 1
    return _dedupe(values, limit=limit)


def domain_guidance(profiles: list[DomainProfile], topic: str) -> str:
    """Return plain-language guidance tailored to the requested domain blend."""

    if not profiles:
        return "Use a creator-friendly plan: clarify the story goal, gather the missing references, and pause for approval before any big change."

    ordered = sorted(profiles, key=lambda profile: profile.displayName.casefold())
    topic_key = (topic or "general").strip().lower()
    names = " + ".join(profile.displayName for profile in ordered)
    deliverables = _collect(ordered, "commonDeliverables", limit=4)
    approval_points = _collect(ordered, "approvalPoints", limit=4)
    quality_checks = _collect(ordered, "qualityChecks", limit=4)
    risks = _collect(ordered, "commonRisks", limit=3)
    workflows = _collect(ordered, "recommendedWorkflows", limit=4)
    specialists = _collect(ordered, "specialistPriorities", limit=4)

    lead = f"For this {names} project, keep the guidance simple, visual, and easy for the creator to act on."

    if any(word in topic_key for word in ("story", "script", "pacing", "narrative", "scene")):
        body = (
            f"Shape the story around these quality checks: {', '.join(quality_checks) or 'clear intent, strong continuity, and emotional clarity'}. "
            f"Let these specialists lead the review: {', '.join(specialists) or 'story, direction, and edit'}. "
            f"Watch for common risks like {', '.join(risks) or 'scope creep and uneven pacing'}."
        )
    elif any(word in topic_key for word in ("approval", "review", "signoff", "greenlight")):
        body = (
            f"Pause the creator at these approval points: {', '.join(approval_points) or 'major story, look, and final delivery choices'}. "
            f"Before each signoff, confirm: {', '.join(quality_checks) or 'clarity, continuity, and readiness'}. "
            f"Do not bury important decisions under technical language."
        )
    elif any(word in topic_key for word in ("deliverable", "export", "release", "publish", "handoff")):
        body = (
            f"Focus the team on creator-ready deliverables such as {', '.join(deliverables) or 'the script, references, and final output package'}. "
            f"Use these workflow checks before handoff: {', '.join(workflows) or 'project_readiness_audit and export_readiness_check'}. "
            f"Call out risks early: {', '.join(risks) or 'missing assets, stale plans, and consistency drift'}."
        )
    else:
        body = (
            f"Start with these creator-facing deliverables: {', '.join(deliverables) or 'a clear plan, the key references, and the next approved action'}. "
            f"Guide the work through: {', '.join(workflows) or 'project_readiness_audit, plan_validation, and generation_preflight'}. "
            f"Keep quality centered on {', '.join(quality_checks) or 'clarity, continuity, and audience impact'}."
        )

    closing = (
        f"If the team gets stuck, revisit the main risks: {', '.join(risks) or 'scope creep, missing references, and stale decisions'}, "
        "then bring the creator back to the smallest next approved step."
    )
    return " ".join((lead, body, closing))
