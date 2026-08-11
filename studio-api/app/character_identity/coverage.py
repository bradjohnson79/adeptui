"""Character Identity readiness / coverage calculation."""

from __future__ import annotations

from typing import Iterable

from .roles import REQUIRED_COVERAGE_ROLES, ROLE_GUIDANCE, SIDE_ALIASES
from .schemas import CategoryReadiness, CoverageReport, VoiceSourceMode


def _role_present(present: set[str], role: str) -> bool:
    if role in present:
        return True
    for canonical, aliases in SIDE_ALIASES.items():
        if role in aliases and any(a in present for a in aliases):
            return True
        if role == canonical and any(a in present for a in aliases):
            return True
    return False


def _category_readiness(
    *,
    missing_roles: list[str],
    has_physical_details: bool,
    has_personality: bool,
    has_performance: bool,
    has_wardrobe: bool,
    has_props: bool,
    voice_state: VoiceSourceMode,
    voice_needs_consent: bool,
    continuity_notes: bool,
    profile_status: str,
) -> tuple[list[CategoryReadiness], list[str]]:
    categories: list[CategoryReadiness] = []
    critical_blockers: list[str] = []

    visual_blockers = list(missing_roles)
    if not has_physical_details:
        visual_blockers.append("Physical details (skin/hair/body) not defined")
    visual_score = max(0.0, 1.0 - len(visual_blockers) / max(len(REQUIRED_COVERAGE_ROLES) + 1, 1))
    visual_ready = len(missing_roles) == 0 and has_physical_details
    categories.append(
        CategoryReadiness(
            category="VisualIdentity",
            score=round(visual_score, 3),
            ready=visual_ready,
            blockers=visual_blockers,
            next_action="Generate or attach required reference roles" if visual_blockers else "",
            critical=bool(missing_roles),
        )
    )
    if missing_roles:
        critical_blockers.append(f"Missing visual references: {', '.join(missing_roles[:3])}")

    personality_ready = has_personality
    categories.append(
        CategoryReadiness(
            category="Personality",
            score=1.0 if has_personality else 0.0,
            ready=personality_ready,
            blockers=[] if has_personality else ["Core personality not defined"],
            next_action="Define core personality and motivations" if not has_personality else "",
        )
    )

    performance_ready = has_performance
    categories.append(
        CategoryReadiness(
            category="Performance",
            score=1.0 if has_performance else 0.0,
            ready=performance_ready,
            blockers=[] if has_performance else ["Performance profile not defined"],
            next_action="Define posture, gait, and mannerisms" if not has_performance else "",
        )
    )

    wardrobe_ready = has_wardrobe
    categories.append(
        CategoryReadiness(
            category="Wardrobe",
            score=1.0 if has_wardrobe else 0.0,
            ready=wardrobe_ready,
            blockers=[] if has_wardrobe else ["No canonical wardrobe assigned"],
            next_action="Create canonical wardrobe look" if not has_wardrobe else "",
        )
    )

    categories.append(
        CategoryReadiness(
            category="Props",
            score=1.0 if has_props else 0.5,
            ready=has_props,
            blockers=[] if has_props else ["No signature props defined (optional)"],
            next_action="Add signature props if story-relevant" if not has_props else "",
        )
    )

    voice_blockers: list[str] = []
    if voice_state == "UNASSIGNED":
        voice_blockers.append("Voice profile not assigned")
    if voice_needs_consent:
        voice_blockers.append("Voice clone consent not confirmed")
        critical_blockers.append("Voice clone consent missing")
    voice_ready = voice_state != "UNASSIGNED" and not voice_needs_consent
    categories.append(
        CategoryReadiness(
            category="Voice",
            score=0.0 if voice_needs_consent else (1.0 if voice_state != "UNASSIGNED" else 0.0),
            ready=voice_ready,
            blockers=voice_blockers,
            next_action="Design or assign voice; obtain consent before cloning" if voice_blockers else "",
            critical=voice_needs_consent,
        )
    )

    continuity_ready = continuity_notes
    categories.append(
        CategoryReadiness(
            category="Continuity",
            score=1.0 if continuity_notes else 0.3,
            ready=continuity_ready,
            blockers=[] if continuity_notes else ["Continuity rules not documented"],
            next_action="Document locked features and continuity restrictions",
        )
    )

    prod_ready = profile_status in ("READY_FOR_GENERATION", "APPROVED", "LOCKED")
    prod_blockers = [c.next_action for c in categories if not c.ready and c.next_action]
    categories.append(
        CategoryReadiness(
            category="ProductionReadiness",
            score=1.0 if prod_ready else 0.0,
            ready=prod_ready,
            blockers=prod_blockers[:4],
            next_action=prod_blockers[0] if prod_blockers else "",
            critical=bool(critical_blockers),
        )
    )

    return categories, critical_blockers


def compute_coverage(
    *,
    present_roles: Iterable[str],
    has_physical_details: bool,
    has_personality: bool,
    has_performance: bool,
    has_wardrobe: bool,
    has_props: bool = False,
    voice_state: VoiceSourceMode,
    voice_needs_consent: bool = False,
    continuity_notes: bool = False,
    profile_status: str = "DRAFT",
) -> CoverageReport:
    present = {str(r) for r in present_roles if r}
    required = list(REQUIRED_COVERAGE_ROLES)
    missing = [r for r in required if not _role_present(present, r)]
    guidance = [ROLE_GUIDANCE[r] for r in missing if r in ROLE_GUIDANCE]

    role_score = (len(required) - len(missing)) / max(len(required), 1)
    extras = sum(
        1
        for ok in (has_physical_details, has_personality, has_performance, has_wardrobe, voice_state != "UNASSIGNED")
        if ok
    )
    raw_score = role_score * 0.7 + (extras / 5.0) * 0.3

    category_readiness, critical_blockers = _category_readiness(
        missing_roles=missing,
        has_physical_details=has_physical_details,
        has_personality=has_personality,
        has_performance=has_performance,
        has_wardrobe=has_wardrobe,
        has_props=has_props,
        voice_state=voice_state,
        voice_needs_consent=voice_needs_consent,
        continuity_notes=continuity_notes,
        profile_status=profile_status,
    )

    # Critical blockers must never produce a misleading high score.
    score = round(min(0.49, raw_score) if critical_blockers else min(1.0, raw_score), 3)

    ready = (
        len(missing) == 0
        and has_physical_details
        and has_personality
        and has_performance
        and has_wardrobe
        and voice_state != "UNASSIGNED"
        and not voice_needs_consent
        and not critical_blockers
    )

    if profile_status in ("APPROVED", "LOCKED", "ARCHIVED"):
        status = profile_status  # type: ignore[assignment]
    elif ready:
        status = "READY_FOR_GENERATION"
    elif present or has_physical_details or has_personality:
        status = "INCOMPLETE"
    else:
        status = "DRAFT"

    next_action = ""
    for cat in category_readiness:
        if not cat.ready and cat.next_action:
            next_action = cat.next_action
            break

    return CoverageReport(
        status=status,  # type: ignore[arg-type]
        score=score,
        required_roles=required,
        present_roles=sorted(present),
        missing_roles=missing,
        guidance=guidance,
        has_physical_details=has_physical_details,
        has_personality=has_personality,
        has_performance=has_performance,
        has_wardrobe=has_wardrobe,
        voice_state=voice_state,
        ready_for_generation=ready,
        category_readiness=category_readiness,
        critical_blockers=critical_blockers,
        next_action=next_action,
    )
