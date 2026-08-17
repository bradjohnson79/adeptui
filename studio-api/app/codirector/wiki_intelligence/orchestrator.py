"""Wiki Intelligence Orchestrator — reconcile specialist findings into structured Wiki updates."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ..conversation.knowledge import apply_wiki_candidates
from ..conversation.project_cache import invalidate_cache_sections
from ..conversation.schemas import WikiCandidate
from ..conversation.snapshot import load_snapshot, save_snapshot
from .assignment import assign_specialists_for_domains
from .classification import (
    classify_entity_type,
    detect_domains_from_entries,
    is_user_preference_not_canon,
    target_section_for_entity,
)
from .contracts import WikiIntelligenceDecision, WikiSpecialistFinding
from .finding_adapter import adapt_specialist_finding, heuristic_department_finding
from .reorganize import _legacy_section_for_professional

logger = logging.getLogger("adept.codirector.wiki_orchestrator")


class WikiIntelligenceOrchestrator:
    """Routes material through relevant specialists and applies validated decisions."""

    def __init__(self, db: Session, project_id: str) -> None:
        self.db = db
        self.project_id = project_id

    def process_seed_texts(
        self,
        seeds: list[dict[str, Any]],
        *,
        use_specialists: bool = True,
    ) -> dict[str, Any]:
        """seeds: [{id, text, section?}] from regex extraction or conversation."""
        if not seeds:
            return {"ok": True, "decisions": [], "applied": 0}

        entries = [{"text": s.get("text"), "section": s.get("section")} for s in seeds]
        domains = detect_domains_from_entries(entries)
        assignment = assign_specialists_for_domains(
            project_id=self.project_id,
            domains=domains,
            source_id=f"turn-{uuid4().hex[:8]}",
            max_specialists=3,  # Phase 7 (CDX-086): hard max three specialists
        )

        findings: list[WikiSpecialistFinding] = []
        for seed in seeds:
            text = str(seed.get("text") or "")
            sid = str(seed.get("id") or uuid4().hex[:10])
            if is_user_preference_not_canon(text):
                continue
            if use_specialists:
                for specialist_id in assignment.requiredSpecialists[:3] or assignment.selectedSpecialists[:3]:
                    findings.append(
                        heuristic_department_finding(
                            specialist_id=specialist_id,
                            source_id=sid,
                            text=text,
                            problem_type="enrichment",
                        )
                    )
            else:
                findings.append(
                    adapt_specialist_finding(
                        specialist_id="orchestrator",
                        source_id=sid,
                        finding={"summary": text, "confidence": 0.5},
                        seed_text=text,
                    )
                )

        decisions = self._reconcile(findings, seeds)
        applied = self._apply_decisions(decisions)
        try:
            invalidate_cache_sections(self.db, self.project_id, sections=["wiki", "knowledge"])
        except Exception:
            pass
        return {
            "ok": True,
            "assignment": assignment.model_dump(mode="json"),
            "decisions": [d.model_dump(mode="json") for d in decisions],
            "applied": applied,
            "findings": len(findings),
        }

    def _reconcile(
        self,
        findings: list[WikiSpecialistFinding],
        seeds: list[dict[str, Any]],
    ) -> list[WikiIntelligenceDecision]:
        by_source: dict[str, list[WikiSpecialistFinding]] = {}
        for f in findings:
            by_source.setdefault(f.sourceId, []).append(f)

        decisions: list[WikiIntelligenceDecision] = []
        seed_by_id = {str(s.get("id")): s for s in seeds}
        for source_id, group in by_source.items():
            seed = seed_by_id.get(source_id) or {}
            text = str(seed.get("text") or (group[0].facts[0].statement if group[0].facts else ""))
            if is_user_preference_not_canon(text):
                decisions.append(
                    WikiIntelligenceDecision(
                        sourceId=source_id,
                        detectedEntityType="preference",
                        targetSection="references",
                        canonState="EXPLORATORY",
                        action="REJECT",
                        specialistIds=[g.specialistId for g in group],
                        text=text,
                    )
                )
                continue
            et = classify_entity_type(text)
            section = target_section_for_entity(et)
            action = "CREATE"
            if any(g.recommendedAction == "MERGE" for g in group):
                action = "MERGE"
            elif any(g.recommendedAction == "RECLASSIFY" for g in group):
                action = "RECLASSIFY"
            elif any(g.recommendedAction == "FLAG_CONFLICT" for g in group):
                action = "REVIEW"
            conf = max((g.confidence for g in group), default=0.5)
            canon = "INFERRED"
            if conf >= 0.8 and action == "CREATE":
                canon = "PROPOSED"
            decisions.append(
                WikiIntelligenceDecision(
                    sourceId=source_id,
                    detectedEntityType=et,
                    targetSection=section,
                    canonState=canon,  # type: ignore[arg-type]
                    confidence=conf,
                    productionUses=list({u for g in group for u in g.productionUses}),
                    action=action,  # type: ignore[arg-type]
                    specialistIds=[g.specialistId for g in group],
                    text=text[:400],
                )
            )
        return decisions

    def _apply_decisions(self, decisions: list[WikiIntelligenceDecision]) -> int:
        # Phase CK — auto-Wiki extraction disabled. Conversation mining for
        # canonical wiki entities is replaced by the Knowledge Card flow.
        # The orchestrator may remain for conversational understanding helpers,
        # but must not persist confirmed/proposed wiki candidates.
        logger.info("_apply_decisions skipped — Phase CK: auto-Wiki extraction disabled")
        return 0


def process_wiki_intelligence_turn(
    db: Session,
    project_id: str,
    seeds: list[dict[str, Any]],
    *,
    use_specialists: bool = True,
) -> dict[str, Any]:
    return WikiIntelligenceOrchestrator(db, project_id).process_seed_texts(
        seeds, use_specialists=use_specialists
    )
