"""Project Bible Steward — intake, background organization, periodic stewardship."""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from sqlalchemy.orm import Session

from .contracts import ProfessionalSpecialistResult, WhyItMatters
from .forward import why_it_matters_for_record
from .identity import learn_aliases_from_correction, resolve_identity

logger = logging.getLogger(__name__)

StewardMode = Literal["IMMEDIATE_INTAKE", "BACKGROUND_ORGANIZATION", "PERIODIC_STEWARDSHIP"]

STEWARD_ID = "project-bible-steward"


def simplify_heading(raw: str) -> str:
    """Collapse duplicate / noisy headings into professional labels."""
    text = re.sub(r"\s+", " ", (raw or "").strip())
    lower = text.lower()
    mapping = [
        (("theme", "emerging theme", "theme inferred"), "Themes"),
        (("story principle",), "Story Principles"),
        (("project overview", "overview"), "Overview"),
        (("open question", "missing information"), "Open Questions"),
        (("episode one", "episode 1", "attached episode 1", "ep 1"), "Episode 1"),
        (("series synopsis", "synopsis"), "Overview"),
    ]
    for keys, label in mapping:
        if any(k == lower or k in lower for k in keys):
            return label
    # Strip trailing status noise
    text = re.sub(r"\s*\((inferred|emerging|proposed|confirmed)\)\s*$", "", text, flags=re.I)
    return text[:80] or "Overview"


def merge_duplicate_headings(headings: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for h in headings:
        simple = simplify_heading(h)
        key = simple.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(simple)
    return out


def attach_why_it_matters(statement: str, *, format_label: str = "UNKNOWN") -> WhyItMatters:
    data = why_it_matters_for_record(statement, format_label=format_label)
    return WhyItMatters(
        storyImportance=data["storyImportance"],
        productionImportance=data["productionImportance"],
    )


def run_steward(
    db: Session,
    *,
    project_id: str,
    mode: StewardMode,
    user_message: str = "",
    seed_texts: list[str] | None = None,
    format_label: str = "UNKNOWN",
    force_periodic: bool = False,
) -> dict[str, Any]:
    """Bounded stewardship. Full scans only on PERIODIC or force_periodic."""
    from .persistence import load_bundle, save_bundle

    bundle = load_bundle(db, project_id)
    seeds = list(seed_texts or [])
    if user_message.strip():
        seeds.insert(0, user_message.strip()[:800])

    headings_in = []
    for s in seeds:
        # first clause as pseudo-heading
        first = s.split(":")[0].strip() if ":" in s else s.split(".")[0].strip()
        if first:
            headings_in.append(first[:80])
    clean_headings = merge_duplicate_headings(headings_in)

    knowledge_actions: list[str] = []
    why_records: list[dict[str, Any]] = []
    for s in seeds[:8]:
        if len(s) < 20:
            continue
        witm = attach_why_it_matters(s, format_label=format_label)
        why_records.append(
            {
                "statement": s[:200],
                "storyImportance": witm.storyImportance,
                "productionImportance": witm.productionImportance,
            }
        )
        knowledge_actions.append("CLASSIFY_AND_ROUTE")

    # Identity learning from correction language
    correction = re.search(
        r"(?:are|is)\s+one\s+(?:person|character).{0,40}(?:canonical\s+name|full\s+name)\s+(?:is\s+)?([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+){0,4})",
        user_message or "",
        flags=re.I,
    )
    surfaces = re.findall(
        r"\b((?:Special Agent|Agent|Commander|Captain|Doctor|Dr\.?|Detective)\s+[A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+)?|[A-Z][\w'’\-]+)\b",
        user_message or "",
    )
    if correction and surfaces:
        canonical = correction.group(1).strip()
        bundle.identityAliases = learn_aliases_from_correction(
            bundle.identityAliases, surfaces=surfaces, canonical_name=canonical
        )
        knowledge_actions.append("MERGE_IDENTITY")
        save_bundle(db, bundle)

    # Periodic: optionally nudge wiki maintenance (bounded)
    maintenance: dict[str, Any] | None = None
    if mode == "PERIODIC_STEWARDSHIP" or force_periodic:
        try:
            from ..wiki_intelligence.maintenance import run_wiki_maintenance

            maintenance = run_wiki_maintenance(db, project_id)
        except Exception:  # noqa: BLE001
            logger.debug("periodic steward maintenance skipped", exc_info=True)

    finding = ProfessionalSpecialistResult(
        specialistId=STEWARD_ID,
        taskId=f"{mode.lower()}:{project_id[:8]}",
        result={
            "mode": mode,
            "cleanHeadings": clean_headings[:12],
            "whyItMatters": why_records[:6],
            "actions": knowledge_actions[:12],
            "maintenance": bool(maintenance),
        },
        assumptions=[],
        unresolvedQuestions=[],
        conflicts=[],
        recommendedAction="ORGANIZE" if knowledge_actions else "NO_ACTION",
        confidence=0.7 if knowledge_actions else 0.4,
    )

    return {
        "ok": True,
        "mode": mode,
        "specialistId": STEWARD_ID,
        "creatorFacingAllowed": False,
        "finding": finding.model_dump(mode="json"),
        "cleanHeadings": clean_headings[:12],
        "whyItMatters": why_records[:6],
        "identityAliases": dict(bundle.identityAliases),
    }


def choose_steward_mode(
    *,
    candidate_count: int,
    user_need: str,
    substantial_growth: bool = False,
) -> StewardMode:
    if user_need == "CORRECTION" or candidate_count > 0:
        if substantial_growth:
            return "PERIODIC_STEWARDSHIP"
        return "IMMEDIATE_INTAKE" if candidate_count > 0 else "BACKGROUND_ORGANIZATION"
    if substantial_growth:
        return "PERIODIC_STEWARDSHIP"
    return "BACKGROUND_ORGANIZATION"
