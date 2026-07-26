"""Propose / approve / apply wrappers around m29 place_cue + DirectorTimeline.

Never silently mutates timeline state — apply requires an explicit approved plan.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..m29.audio.service import AudioService
from .scene_audio import AudioPlan, validate_audio_plan


def propose_timeline_ops(plan: AudioPlan) -> dict[str, Any]:
    """Return a proposal payload; does not write to DB."""
    validation = validate_audio_plan(plan)
    ops = []
    for i, p in enumerate(plan.placements):
        if not p.assetId:
            continue
        op_id = "place-" + str(i) + "-" + uuid.uuid4().hex[:8]
        ops.append(
            {
                "opId": op_id,
                "action": "place_cue",
                "kind": p.kind,
                "assetId": p.assetId,
                "startSec": p.startSec,
                "durationSec": p.durationSec,
                "volume": p.volume,
                "ducking": p.ducking,
                "sceneId": plan.sceneId,
            }
        )
    return {
        "status": "proposed",
        "projectId": plan.projectId,
        "sceneId": plan.sceneId,
        "ops": ops,
        "validation": validation,
        "approved": False,
        "applied": False,
    }


def approve_timeline_ops(proposal: dict[str, Any], *, approve: bool = True) -> dict[str, Any]:
    """Mark a proposal approved/rejected. No DB mutation."""
    out = dict(proposal)
    validation = out.get("validation") or {}
    if approve and not validation.get("ok"):
        out["approved"] = False
        out["status"] = "rejected_invalid"
        out["error"] = "cannot approve invalid plan"
        return out
    out["approved"] = bool(approve)
    out["status"] = "approved" if approve else "rejected"
    return out


def apply_timeline_ops(db: Session, proposal: dict[str, Any]) -> dict[str, Any]:
    """Apply approved place_cue ops. Refuses if not approved."""
    if not proposal.get("approved"):
        raise PermissionError(
            "timeline ops not approved; refusing silent mutation of DirectorTimeline"
        )
    validation = proposal.get("validation") or {}
    if not validation.get("ok"):
        raise ValueError("timeline ops validation failed; refusing apply")

    results: list[dict[str, Any]] = []
    project_id = str(proposal.get("projectId") or "")
    for op in proposal.get("ops") or []:
        if op.get("action") != "place_cue":
            continue
        placed = AudioService.place_cue(
            db,
            project_id=project_id,
            kind=str(op.get("kind") or "sfx"),
            asset_id=str(op["assetId"]),
            start_sec=float(op.get("startSec") or 0.0),
            duration_sec=float(op.get("durationSec") or 2.0),
            scene_id=op.get("sceneId") or proposal.get("sceneId"),
            volume=float(op.get("volume") or 1.0),
            ducking=bool(op.get("ducking") or False),
        )
        results.append({"opId": op.get("opId"), "result": placed})
    out = dict(proposal)
    out["applied"] = True
    out["status"] = "applied"
    out["results"] = results
    return out
