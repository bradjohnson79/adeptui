"""Provider-neutral timeline.* tool surface — inspect → propose → approve → execute.

Co-Director path: tools are registered in `codirector/tools/registry.py` and executed via
ProposalService (preview → approve → apply). This module keeps HTTP dispatch for direct API
callers; do not use the soft `approved` bool as the production Co-Director path.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from . import orchestrator, service
from .contracts import CancelRequest


MUTATION_GATE = ("inspect", "propose", "preview", "approve", "execute", "verify")
CODIRECTOR_AUTHORITY = "codirector/tools/registry.py (ProposalService approval gate)"


def tool_catalog() -> dict[str, Any]:
    return {
        "ok": True,
        "mutationGate": list(MUTATION_GATE),
        "codirectorRegistry": CODIRECTOR_AUTHORITY,
        "tools": [
            {"id": "timeline.get_workspace", "mutation": False},
            {"id": "timeline.get_playhead", "mutation": False},
            {"id": "timeline.get_settings", "mutation": False},
            {"id": "timeline.get_guidance_priority", "mutation": False},
            {"id": "timeline.inspect_batches", "mutation": False},
            {"id": "timeline.preflight", "mutation": False},
            {"id": "timeline.explain_asset_reference_name", "mutation": False},
            {"id": "timeline.set_playhead", "mutation": True},
            {"id": "timeline.update_settings", "mutation": True},
            {"id": "timeline.set_guidance_priority", "mutation": True},
            {"id": "timeline.remove_item", "mutation": True},
            {"id": "timeline.restore_removed_item", "mutation": True},
            {"id": "timeline.propose_add_batch", "mutation": True},
            {"id": "timeline.propose_add_image_clip", "mutation": True},
            {"id": "timeline.propose_add_prompt_segment", "mutation": True},
            {"id": "timeline.propose_generate_scene", "mutation": True},
            {"id": "timeline.propose_repair_range", "mutation": True},
            {"id": "timeline.propose_cancel", "mutation": True},
            {"id": "timeline.propose_retake", "mutation": True},
            {"id": "timeline.attach_optional_reference", "mutation": True},
        ],
        "note": (
            "Co-Director mutations use ProposalService (preview → human approve → apply). "
            "HTTP dispatch below is legacy/direct API only."
        ),
        "mock": False,
    }


def dispatch(
    db: Session,
    *,
    tool_id: str,
    project_id: str,
    scene_id: str,
    args: dict[str, Any] | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    args = args or {}
    if tool_id == "timeline.inspect_batches":
        return service.workspace(db, project_id, scene_id)
    if tool_id == "timeline.preflight":
        bundle = service.load_timeline_bundle(db, project_id, scene_id)
        if not bundle.get("ok"):
            return bundle
        master = bundle["master"]
        return {
            "ok": True,
            "findings": orchestrator.run_preflight(
                master,
                lipsync_tracks=bundle.get("lipsyncTracks"),
                db=db,
                project_id=project_id,
                scene_id=scene_id,
            ),
            "mock": False,
        }

    # Mutations
    if not approved:
        return {
            "ok": False,
            "error": "APPROVAL_REQUIRED",
            "mutationGate": list(MUTATION_GATE),
            "proposal": {"toolId": tool_id, "args": args},
            "message": "timeline.* mutations require approve before execute.",
            "mock": False,
        }

    if tool_id in {
        "timeline.propose_generate_scene",
        "timeline.propose_add_batch",
        "timeline.propose_repair_range",
        "timeline.propose_cancel",
        "timeline.propose_retake",
    }:
        _ = (db, project_id, scene_id, args)
        return {
            "ok": False,
            "error": "FILM_TIMELINE_REQUIRED",
            "message": "Generate Shot, Continue Shot, and Add to Timeline are the production Timeline actions.",
            "mock": False,
        }
    if tool_id == "timeline.propose_add_image_clip":
        return {
            "ok": False,
            "error": "USE_CODIRECTOR_PROPOSAL_SERVICE",
            "message": "timeline.propose_add_image_clip executes via Co-Director ProposalService only.",
            "mock": False,
        }
    if tool_id == "timeline.propose_add_prompt_segment":
        return {
            "ok": False,
            "error": "USE_CODIRECTOR_PROPOSAL_SERVICE",
            "message": "timeline.propose_add_prompt_segment executes via Co-Director ProposalService only.",
            "mock": False,
        }

    return {"ok": False, "error": "UNKNOWN_TOOL", "toolId": tool_id, "mock": False}
