"""Capability handler: character.generate_visual_sheet

Deterministic CRS / visual-sheet production. Calls the existing Character
Creator propose path with extras OFF and provider AUTO (chooser among
available CRS providers). Does not invent workflow keys or Comfy graphs.
Does not owner-approve.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_CRS_NAME_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_-]*)'s\s+(?:crs|character reference sheet|visual sheet)\b",
    re.I,
)
_CRS_FOR_RE = re.compile(
    r"\b(?:crs|character reference sheet|visual sheet)\b.*\bfor\s+([A-Za-z][A-Za-z0-9_-]*)\b",
    re.I,
)

AUTO_CRS_SOURCES = {
    "local": [{"family": "auto", "enabled": True, "batchCount": 1}],
    "api": None,
    "stage2Enabled": False,
}


def _extract_character_name(prompt: str, fallback: str = "") -> str:
    text = prompt or ""
    match = _CRS_NAME_RE.search(text) or _CRS_FOR_RE.search(text)
    if match:
        return match.group(1).strip()
    return (fallback or "").strip()


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    prompt: str = "",
    character_name: str = "",
    character_id: str = "",
    visual_style: str = "",
    **_: Any,
) -> dict[str, Any]:
    """Enqueue one CRS via propose_visual_sheet defaults: extras OFF, provider AUTO."""

    from ....character_identity import service as identity_service
    from ....character_identity.visual_sheet import (
        _load_pack_raw,
        advance_visual_sheet_pack,
        resolve_character_creator_generator_sources,
        start_visual_sheet_generation,
    )
    from ...execution.crs_lineage import extract_crs_job_id

    resolved_id = (character_id or "").strip()
    name = _extract_character_name(prompt, character_name)
    if not resolved_id and name:
        row = identity_service.resolve_character_by_name(db, project_id, name)
        if row is not None:
            resolved_id = row.id
            name = row.name or name
    if not resolved_id:
        return {
            "ok": False,
            "error": "CHARACTER_REQUIRED",
            "message": "Name the character whose Character Reference Sheet to generate.",
            "child_jobs": [],
        }

    profile = identity_service.get_profile(db, project_id, resolved_id)
    bio = (profile.description or "").strip()
    visual_desc = (getattr(profile, "visual_description", "") or "").strip()
    if len(f"{bio} {visual_desc}".strip()) < 20:
        return {
            "ok": False,
            "error": "MISSING_DESCRIPTION",
            "characterId": resolved_id,
            "message": (
                "Before I create a Character Reference Sheet, I need a basic description "
                "of this character."
            ),
            "child_jobs": [],
        }

    pack = start_visual_sheet_generation(
        db,
        project_id,
        resolved_id,
        include_details=False,
        include_performance=False,
        hero_asset_id=None,
        candidate_count=1,
        visual_style=visual_style or getattr(profile, "visual_style", "") or "",
        generator_sources=resolve_character_creator_generator_sources(
            pack=_load_pack_raw(db, resolved_id),
        ),
    )
    pack = advance_visual_sheet_pack(db, project_id, resolved_id)
    job_id = extract_crs_job_id(pack) or ""
    child_jobs = []
    if job_id:
        child_jobs.append(
            {
                "job_id": job_id,
                "label": "Character Reference Sheet",
                "status": "queued",
                "child_index": 0,
                "asset_id": None,
                "metadata": {
                    "provider": "AUTO",
                    "includeDetails": False,
                    "includePerformance": False,
                },
            }
        )
    return {
        "ok": True,
        "characterId": resolved_id,
        "pack": pack,
        "child_jobs": child_jobs,
        "surface_type": "character_visual_sheet",
    }
