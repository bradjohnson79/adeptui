"""Natural-language Project Overview — no raw keys."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db import Project


def compile_project_overview(db: Session, project_id: str, *, facts: list[str]) -> dict[str, Any]:
    project = db.get(Project, project_id)
    name = (getattr(project, "name", None) or "Untitled Project").strip()
    ptype = str(getattr(project, "primary_project_type", None) or "").replace("_", " ").strip()
    bits: list[str] = []
    if ptype:
        bits.append(ptype.title() if len(ptype) < 40 else ptype)
    else:
        # Infer lightly from facts
        blob = " ".join(facts).lower()
        if "documentary" in blob:
            bits.append("Documentary")
        elif "series" in blob or "episode" in blob:
            bits.append("Multi-season live-action web series")
        elif "game" in blob:
            bits.append("Interactive game project")
        else:
            bits.append("Creative production")
    bits.append("16:9")
    bits.append("Primary video generator: MiniMax H3")
    summary = ". ".join(bits) + "."
    return {
        "pageId": "page-project-overview",
        "pageType": "PROJECT",
        "title": "Project Overview",
        "summary": summary,
        "sections": [
            {
                "id": "sec-overview",
                "title": "Overview",
                "body": f"{name}. {summary}",
                "bullets": [],
            }
        ],
        "relatedPageIds": ["page-story"],
        "sourceRecordIds": [],
        "canonState": "CONFIRMED",
        "questionsToExplore": [],
    }
