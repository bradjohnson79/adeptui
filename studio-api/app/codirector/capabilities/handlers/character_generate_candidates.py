"""Capability handler: character.generate_candidates.

Reuses Character Creator visual-sheet generation with N casting candidates.
Does not invent a second image pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    prompt: str = "",
    character_name: str = "",
    character_id: str = "",
    visual_style: str = "",
    count: int = 4,
    **_: Any,
) -> dict[str, Any]:
    from .character_generate_visual_sheet import _extract_character_name
    from ....character_identity import service as identity_service
    from ....character_identity.visual_sheet import (
        _load_pack_raw,
        advance_visual_sheet_pack,
        resolve_character_creator_generator_sources,
        start_visual_sheet_generation,
    )

    resolved_id = (character_id or "").strip()
    name = _extract_character_name(prompt, character_name)
    if not resolved_id and name:
        row = identity_service.resolve_character_by_name(db, project_id, name)
        if row is not None:
            resolved_id = row.id
            name = row.name or name
    if not resolved_id:
        return {
            "error": "Name the character whose casting pictures to generate.",
            "child_jobs": [],
        }

    wanted = max(2, min(int(count or 4), 6))
    pack = start_visual_sheet_generation(
        db,
        project_id,
        resolved_id,
        include_details=False,
        include_performance=False,
        hero_asset_id=None,
        candidate_count=wanted,
        visual_style=visual_style or "",
        generator_sources=resolve_character_creator_generator_sources(
            pack=_load_pack_raw(db, resolved_id),
        ),
    )
    pack = advance_visual_sheet_pack(db, project_id, resolved_id)
    candidates = list((pack or {}).get("candidates") or [])
    child_jobs = []
    for index, row in enumerate(candidates):
        job_id = str((row or {}).get("jobId") or (row or {}).get("job_id") or "").strip()
        if not job_id:
            continue
        child_jobs.append(
            {
                "job_id": job_id,
                "label": f"Candidate {index + 1}",
                "status": "queued",
                "child_index": index,
                "metadata": {"character_id": resolved_id, "character_name": name},
            }
        )
    if not child_jobs:
        return {
            "error": "Character Creator did not queue casting pictures.",
            "child_jobs": [],
            "pack": pack,
        }
    return {
        "ok": True,
        "characterId": resolved_id,
        "child_jobs": child_jobs,
        "surface_type": "casting_candidates",
    }
