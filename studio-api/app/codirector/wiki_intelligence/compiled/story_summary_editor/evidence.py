"""Build curated StorySummarySource evidence from project intelligence.

Pulls confirmed/approved knowledge entries, installment summaries, character
roles, timeline events, and world rules. Classifies each entry as fact vs
creator-interpretation vs specialist-interpretation by provenance. Loads the
previous approved summary from the compiled Wiki cache.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ....conversation.snapshot import load_snapshot
from .contracts import PreviousApprovedSummary, StorySummarySource
from .theme_normalizer import normalize_themes

_FACT_STATES = {"confirmed", "approved"}
_FACT_PROVENANCE = {"script_analyze", "USER_EXPLICIT_WIKI_WRITE", "user_explicit_wiki_write"}
_SPECIALIST_PROVENANCE_PREFIX = "specialist"
# Explicit creator writes are the highest authority below locked canon.
_CREATOR_EXPLICIT = "user_explicit_wiki_write"


def _is_creator_explicit(provenance: str | None) -> bool:
    return bool(provenance) and _CREATOR_EXPLICIT in provenance.lower()


def _is_fact(state: str, provenance: str | None) -> bool:
    if state in _FACT_STATES:
        return True
    if provenance in _FACT_PROVENANCE:
        return True
    return False


def _is_specialist(provenance: str | None) -> bool:
    if not provenance:
        return False
    p = provenance.lower()
    return p.startswith(_SPECIALIST_PROVENANCE_PREFIX) or "-" in provenance


def _classify(
    text: str, state: str, provenance: str | None
) -> tuple[str | None, str | None, str | None]:
    """Return (fact, creator_interpretation, specialist_interpretation) slots.

    CREATOR_CORRECTION_PRIORITY: an explicit creator write is always a fact and
    never a specialist interpretation, even if its provenance string contains a
    dash (e.g. `explicit_wiki_write:USER_EXPLICIT_WIKI_WRITE`).
    """
    if _is_creator_explicit(provenance):
        return text, None, None
    if _is_specialist(provenance):
        return None, None, text
    if _is_fact(state, provenance):
        return text, None, None
    # Default: treat as creator-stated interpretation (cautious phrasing).
    return None, text, None


def _format_profile(primary_type: str | None, snapshot_format: str | None) -> str:
    blob = f"{primary_type or ''} {snapshot_format or ''}".lower()
    if "document" in blob:
        return "documentary"
    if "music" in blob:
        return "music_video"
    if "commercial" in blob or "ad" in blob:
        return "commercial"
    if "game" in blob:
        return "game"
    return "narrative_visual"


def build_story_summary_source(
    db: Session, project_id: str, *, include_previous: bool = True
) -> StorySummarySource:
    snapshot = load_snapshot(db, project_id)

    confirmed_facts: list[str] = []
    creator_interp: list[str] = []
    specialist_interp: list[str] = []
    timeline_events: list[str] = []
    world_rules: list[str] = []
    theme_candidates: list[str] = []
    source_ids: list[str] = []

    for entry in getattr(snapshot, "knowledgeEntries", None) or []:
        state = str(getattr(entry, "state", "proposed") or "proposed")
        if state in {"rejected", "superseded"}:
            continue
        text = str(getattr(entry, "text", "") or "").strip()
        if len(text) < 3:
            continue
        section = str(getattr(entry, "section", "") or "")
        provenance = getattr(entry, "provenance", None)
        fact, cinterp, sinterp = _classify(text, state, provenance)
        if fact:
            if section == "storyAndEpisodes":
                timeline_events.append(text)
            elif section == "worldAndSetting":
                world_rules.append(text)
            else:
                confirmed_facts.append(fact)
        if cinterp:
            creator_interp.append(cinterp)
        if sinterp:
            specialist_interp.append(sinterp)
        if "theme" in text.lower() or "memory" in text.lower():
            theme_candidates.append(text)
        source_ids.append(str(getattr(entry, "id", "") or ""))

    # Approved script summaries from creative-operating bundle + lifecycle.
    approved_script_summaries: list[str] = []
    try:
        from ....creative_operating.persistence import load_bundle

        bundle = load_bundle(db, project_id)
        for inst in getattr(bundle, "installments", None) or []:
            summary = (inst.get("summary") or inst.get("overview") or "") if isinstance(inst, dict) else ""
            if summary:
                approved_script_summaries.append(str(summary).strip())
    except Exception:  # noqa: BLE001
        pass

    life = getattr(snapshot, "productionLifecycle", None) or {}
    for inst in life.get("installments") or []:
        summary = (inst.get("summary") or inst.get("overview") or "") if isinstance(inst, dict) else ""
        if summary and summary not in approved_script_summaries:
            approved_script_summaries.append(str(summary).strip())

    # Character roles from compiled character pages (if cached).
    character_roles: list[str] = []
    compiled = getattr(snapshot, "compiledWiki", None) or {}
    for page in compiled.get("pages") or []:
        if page.get("pageType") != "CHARACTER":
            continue
        title = page.get("title") or ""
        if title:
            character_roles.append(title)

    # Fallback to snapshot keyCharacters when no compiled pages yet.
    if not character_roles:
        character_roles = list(getattr(snapshot, "keyCharacters", None) or [])

    themes = normalize_themes(theme_candidates)

    # CREATOR_CORRECTION_SURVIVES_RECOMPILE: inject learned-correction rules as
    # highest-authority confirmed facts, and drop specialist interpretations that
    # conflict with an explicit creator correction so a corrected mistake does
    # not return on recompile.
    try:
        from ...correction import memory as correction_memory

        learned_rules = correction_memory.active_rules(db, project_id)
        for rule in learned_rules:
            if rule and rule not in confirmed_facts:
                confirmed_facts.insert(0, rule)
        overrides = correction_memory.entity_type_overrides(db, project_id)
        if overrides:
            # Remove specialist interpretations that still treat an overridden
            # entity as its old (incorrect) type.
            overridden = [name for name in overrides]
            specialist_interp = [
                s
                for s in specialist_interp
                if not any(name in s.lower() for name in overridden)
            ]
    except Exception:  # noqa: BLE001
        pass

    previous = None
    if include_previous:
        prev_summary = compiled.get("storySummary") or {}
        if prev_summary and isinstance(prev_summary, dict):
            previous = PreviousApprovedSummary(
                logline=prev_summary.get("logline") or "",
                shortSummary=prev_summary.get("shortSummary") or "",
                longSummary=prev_summary.get("longSummary") or "",
            )

    primary_type = None
    try:
        from app.db import Project

        proj = db.get(Project, project_id)
        primary_type = getattr(proj, "primary_project_type", None) if proj else None
    except Exception:  # noqa: BLE001
        primary_type = None

    return StorySummarySource(
        projectId=project_id,
        confirmedFacts=confirmed_facts[:40],
        approvedScriptSummaries=approved_script_summaries[:12],
        creatorStatedInterpretations=creator_interp[:20],
        specialistInterpretations=specialist_interp[:20],
        confirmedCharacterRoles=character_roles[:20],
        confirmedTimelineEvents=timeline_events[:20],
        confirmedWorldRules=world_rules[:20],
        inferredThemes=themes[:8],
        unresolvedQuestions=list(getattr(snapshot, "openQuestions", None) or [])[:8],
        sourceIds=source_ids[:40],
        formatProfile=_format_profile(primary_type, getattr(snapshot, "format", None)),
        previousApprovedSummary=previous,
    )


def evidence_hash(source: StorySummarySource) -> str:
    """Stable content hash for skip-no-op-recompile decisions."""
    import hashlib

    blob = "|".join(
        source.confirmedFacts
        + source.approvedScriptSummaries
        + source.confirmedCharacterRoles
        + source.creatorStatedInterpretations
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


__all__ = ["build_story_summary_source", "evidence_hash"]
