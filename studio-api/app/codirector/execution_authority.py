"""Project execution authority - direct execution for routine reversible actions.

Mission Parts 30, 35-36: when the creator has set execution authority to
"direct" for a project, routine reversible mutations explicitly requested
in the chat turn are auto-approved through the EXISTING proposal machinery
(preview, version pin, apply, receipt) - the user instruction in the turn
is the authorization. Destructive / high-cost / identity-sensitive tools
are never auto-approved; they always surface the proposal card.

Frozen contract #3 (creator authority) is preserved: no silent canon, no
silent approve of unrequested actions, costly generation still requires
explicit approval, and every execution is audited (proposal + receipt +
tool invocation). Additive amendment recorded in
docs/release-gate/codirector-production-orchestrator/02-ARCHITECTURE_DESIGN.md.
"""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

AUTHORITY_PROPOSALS = "proposals"
AUTHORITY_DIRECT = "direct"
ALL_AUTHORITIES = (AUTHORITY_PROPOSALS, AUTHORITY_DIRECT)

# Routine reversible mutation tools that may auto-execute under direct
# authority when created inside a chat turn. NEVER add: deletes, replaces
# of approved assets, generation triggers, voice/lipsync, cloud-paid ops,
# bible/canon mutations, vision corrections.
ROUTINE_TOOLS: frozenset[str] = frozenset({
    "timeline.propose_add_image_clip",
    "timeline.propose_add_prompt_segment",
    "timeline.propose_add_batch",
    "timeline.propose_add_camera",
    "timeline.propose_update_camera",
    "timeline.update_settings",
    "timeline.set_playhead",
    "spatial.create_camera",
    "spatial.update_camera",
    "spatial.place_character",
    "spatial.place_prop",
    "spatial.move_placement",
    "editor.place_asset",
    "image_pipeline.select_candidate",
    "production_plan.create_draft",
    "timeline.build_shot",
})

_SETTINGS_KEY = "codirector"


def _settings_dict(project: object) -> dict:
    raw = getattr(project, "settings_json", "") or ""
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw) if raw else {}
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def get_execution_authority(db: Session, project_id: str) -> str:
    """Read the project execution authority (default: proposals)."""
    from ..db import Project

    project = db.get(Project, project_id)
    if project is None:
        return AUTHORITY_PROPOSALS
    settings = _settings_dict(project)
    value = ((settings.get(_SETTINGS_KEY) or {}).get("executionAuthority") or AUTHORITY_PROPOSALS)
    return value if value in ALL_AUTHORITIES else AUTHORITY_PROPOSALS


def set_execution_authority(db: Session, project_id: str, value: str) -> str:
    """Persist the project execution authority. Returns the stored value."""
    from ..db import Project

    if value not in ALL_AUTHORITIES:
        raise ValueError("executionAuthority must be one of: " + ", ".join(ALL_AUTHORITIES))
    project = db.get(Project, project_id)
    if project is None:
        raise LookupError("project not found: " + project_id)
    settings = _settings_dict(project)
    section = dict(settings.get(_SETTINGS_KEY) or {})
    section["executionAuthority"] = value
    settings[_SETTINGS_KEY] = section
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    db.commit()
    return value


def should_auto_approve(
    db: Session,
    project_id: str,
    tool_id: str,
    request_id: Optional[str],
) -> bool:
    """Whether a tool proposal should auto-execute.

    Requires ALL of: direct authority, tool on the routine allowlist, and
    creation inside a chat turn (request_id present).
    """
    if not request_id:
        return False
    if tool_id not in ROUTINE_TOOLS:
        return False
    return get_execution_authority(db, project_id) == AUTHORITY_DIRECT