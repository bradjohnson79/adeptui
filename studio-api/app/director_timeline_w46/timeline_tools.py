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
        director_timeline = bundle["directorTimeline"]
        return {
            "ok": True,
            "findings": orchestrator.run_preflight(master, director_timeline=director_timeline),
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

    if tool_id == "timeline.propose_generate_scene":
        return orchestrator.generate_scene(
            db, project_id, scene_id, scope=args.get("scope") or "full", batch_ids=args.get("batchBlockIds")
        )
    if tool_id == "timeline.propose_add_batch":
        return service.add_batch(
            db,
            project_id,
            scene_id,
            label=args.get("label"),
            planned_duration=float(args.get("plannedDuration") or 5.0),
            generator_id=args.get("generatorId"),
        )
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
    if tool_id == "timeline.propose_repair_range":
        return orchestrator.add_repair_range(
            db,
            project_id,
            scene_id,
            args["batchBlockId"],
            {
                "start": args.get("start", 0),
                "length": args.get("length", 1),
                "label": args.get("label") or "Co-Director repair",
                "inPaintStrategy": args.get("inPaintStrategy") or "range_replacement",
            },
            policy=args.get("policy"),
        )
    if tool_id == "timeline.propose_cancel":
        return orchestrator.cancel_scene(
            db,
            project_id,
            scene_id,
            CancelRequest(
                action=args.get("action") or "stop_remaining_scene_jobs",
                batchBlockIds=list(args.get("batchBlockIds") or []),
            ),
        ).model_dump()
    if tool_id == "timeline.propose_retake":
        batch_id = args["batchBlockId"]
        # Directed retake = new generation job + new snapshot (does not mutate old snapshots)
        return orchestrator.submit_batch_generation(db, project_id, scene_id, batch_id)

    return {"ok": False, "error": "UNKNOWN_TOOL", "toolId": tool_id, "mock": False}
