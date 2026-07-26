"""Bridge specialist conflicts into Bible conflict_record via bible/conflicts.py."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..bible.domain_service import BibleDomainService
from ..bible.conflicts import detect_all_conflicts
from ..intelligence.schemas import SpecialistFinding


def bridge_specialist_conflicts(
    db: Session,
    project_id: str,
    findings: list[SpecialistFinding],
    *,
    scene_id: Optional[str] = None,
) -> dict[str, Any]:
    """Sync Bible conflicts and attach specialist-reported conflict notes (advise-only)."""

    try:
        bible_conflicts = BibleDomainService.sync_conflicts(db, project_id)
    except Exception:
        # Advise-only: projects without a bible still get specialist conflict notes.
        bible_conflicts = []
    specialist_conflicts: list[dict[str, Any]] = []
    for finding in findings:
        for issue in list(finding.blockingIssues or []) + list(finding.risks or []):
            text = issue if isinstance(issue, str) else str(issue)
            lowered = text.lower()
            if any(k in lowered for k in ("conflict", "contradict", "mismatch", "inconsisten")):
                specialist_conflicts.append(
                    {
                        "conflictType": "specialist_reported",
                        "severity": "warning",
                        "description": text,
                        "entityStableIds": [],
                        "sceneIds": [scene_id] if scene_id else [],
                        "specialistId": finding.specialistId,
                        "source": "m211_orchestrator",
                    }
                )
        # Heuristic: continuity specialist findings always surface as advisory conflicts when blockers exist
        if finding.specialistId == "continuity-analyst" and finding.blockingIssues:
            for issue in finding.blockingIssues:
                specialist_conflicts.append(
                    {
                        "conflictType": "continuity_specialist",
                        "severity": "warning",
                        "description": str(issue),
                        "entityStableIds": [],
                        "sceneIds": [scene_id] if scene_id else [],
                        "specialistId": finding.specialistId,
                        "source": "m211_orchestrator",
                    }
                )

    # Deduplicate by description
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for item in list(bible_conflicts) + specialist_conflicts:
        key = str(item.get("description") or item.get("conflictType") or "")
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    return {
        "projectId": project_id,
        "bibleConflicts": bible_conflicts,
        "specialistConflicts": specialist_conflicts,
        "conflicts": merged,
        "count": len(merged),
    }


def list_conflict_records(db: Session, project_id: str) -> list[dict[str, Any]]:
    try:
        return BibleDomainService.list_by_type(db, project_id, "conflict_record")
    except Exception:
        return []


def detect_from_entities(entities: list[Any]) -> list[dict[str, Any]]:
    return detect_all_conflicts(entities)
