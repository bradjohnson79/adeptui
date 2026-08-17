"""Problem-driven specialist assignment — never run every specialist."""

from __future__ import annotations

from uuid import uuid4

from .contracts import DOMAIN_SPECIALIST_MAP, WikiOrganizationProblem, WikiSpecialistAssignment
from .intelligence_roster import available_specialist_ids


def assign_specialists_for_domains(
    *,
    project_id: str,
    domains: list[str],
    problems: list[WikiOrganizationProblem] | None = None,
    source_id: str | None = None,
    # Phase 7 (CDX-086): HARD ceiling of THREE specialists everywhere. The
    # value is clamped below so no caller can exceed the mandate; the final
    # slice is a second, defensive guarantee.
    max_specialists: int = 3,
) -> WikiSpecialistAssignment:
    max_specialists = min(max(1, int(max_specialists)), 3)  # CDX-086 hard max
    available = available_specialist_ids()
    required: list[str] = []
    optional: list[str] = []
    reasons: dict[str, str] = {}

    problem_domains = {p.domain for p in (problems or [])}
    active_domains = sorted(set(domains) | problem_domains)

    for domain in active_domains:
        for sid in DOMAIN_SPECIALIST_MAP.get(domain, []):
            if sid not in available:
                continue
            if sid in required or sid in optional:
                continue
            # Prefer specialists tied to detected problems as required
            if domain in problem_domains and len(required) < max_specialists:
                required.append(sid)
                reasons[sid] = f"Required for detected problems in {domain}"
            elif len(required) + len(optional) < max_specialists:
                optional.append(sid)
                reasons[sid] = f"Optional coverage for {domain}"

    # Continuity always recommended when characters/timeline/wardrobe/props present
    if any(d in active_domains for d in ("characters", "timeline", "wardrobe", "props", "canon")):
        for sid in ("script-supervisor", "continuity-analyst"):
            if sid in available and sid not in required and sid not in optional:
                if len(required) < max_specialists:
                    required.append(sid)
                    reasons[sid] = "Continuity / script supervision"
                elif len(optional) < 2:
                    optional.append(sid)
                    reasons[sid] = "Continuity / script supervision"

    selected = (required + optional)[:max_specialists]
    return WikiSpecialistAssignment(
        sourceId=source_id or f"assign-{uuid4().hex[:10]}",
        projectId=project_id,
        detectedDomains=active_domains,
        selectedSpecialists=selected,
        requiredSpecialists=required[:max_specialists],
        optionalSpecialists=[s for s in optional if s in selected],
        reasonForSelection=reasons,
        executionMode="BACKGROUND",
        contextBudgetTokens=2500,
        latencyBudgetMs=8000,
    )
