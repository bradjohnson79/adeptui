"""Scene Creator → Timeline handoff helper.

Single canonical path for sending a ``SceneGenerationBatch``'s result assets to
the W46 Timeline. Both the manual REST endpoint (``scene_creator.router``) and
the Co-Director deterministic command ("send those to timeline") converge here
(amendment #54 — manual + agent parity), then call the certified
``magi.timeline_handoff.export_to_timeline``.

Amendment #51 (SCENE SHOT TIMELINE METADATA): each clip carries shot order
(index), raw shot prompt, resolved character IDs, resolved prop IDs, ERS id,
source scene, and asset id. The frozen W46 ``BatchClip`` carries no arbitrary
metadata dict, so:
- ``label`` and ``role`` (when applicable) are passed as native BatchClip fields.
- The remaining scene-shot provenance is recorded via the W46 export ledger
  (``sequence.json.exportLedger``) inside ``export_to_timeline``.

Law #7 (no mock completion): real assets only — failed/empty slots are skipped.
Law #14 (project isolation): ``project_id`` is threaded through every call.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..magi.timeline_handoff import export_to_timeline
from ..spatial_map.ers_contracts import SceneGenerationBatch
from ..spatial_map.ers_persistence import load_scene_batch

logger = logging.getLogger(__name__)


def send_scene_batch_to_timeline(
    db: Session,
    project_id: str,
    batch_id: str,
    *,
    scene_id: str,
    label: Optional[str] = None,
    batch_block_id: Optional[str] = None,
) -> dict[str, Any]:
    """Send a Scene Creator batch's result assets to the W46 Timeline.

    Loads the persisted ``SceneGenerationBatch``, builds ordered clip dicts
    (one per completed shot) with scene-shot provenance, and delegates to
    ``magi.timeline_handoff.export_to_timeline`` — the certified MAGI→Timeline
    handoff. Failed/empty shot slots are skipped (no mock placement).

    Args:
        db: Database session.
        project_id: Owning project.
        batch_id: The ``SceneGenerationBatch.id`` to send.
        scene_id: Target W46 scene (required by the certified handoff).
        label: Optional batch label; defaults to a scene-shot-friendly name.
        batch_block_id: Optional existing W46 ``BatchBlock`` id to append to.
            When omitted, ``export_to_timeline`` creates a fresh batch.

    Returns:
        The ``export_to_timeline`` result dict (``{ok, batchBlockId, clips, ...}``
        on success; ``{ok: False, error, ...}`` on failure).
    """
    if not (scene_id or "").strip():
        return {
            "ok": False,
            "error": "SCENE_ID_REQUIRED",
            "message": "Send to Timeline needs a Scene. Create or select one first.",
        }

    batch = load_scene_batch(db, project_id, batch_id)
    if batch is None:
        return {
            "ok": False,
            "error": "SCENE_BATCH_NOT_FOUND",
            "message": f"Scene batch '{batch_id}' not found in project '{project_id}'.",
        }

    clips = build_scene_shot_clips(batch)
    if not clips:
        return {
            "ok": False,
            "error": "NO_COMPLETED_SHOTS",
            "message": "Batch has no completed result assets to send to Timeline.",
        }

    result = export_to_timeline(
        db,
        project_id,
        scene_id,
        clips,
        label=label or f"Scene Creator batch {batch_id[:8]}",
        batch_block_id=batch_block_id,
    )

    if result.get("ok"):
        result["batch_id"] = batch_id
        result["ers_package_id"] = batch.ers_package_id
        result["clips_sent"] = len(clips)
    return result


def send_approved_shot_to_timeline(
    db: Session,
    project_id: str,
    shot: Any,
    candidate: Any,
    *,
    batch_block_id: Optional[str] = None,
) -> dict[str, Any]:
    """Send one approved Scene Creator take to Timeline. Unapproved candidates are ineligible."""
    scene_id = str(getattr(shot, "scene_id", "") or "").strip()
    if not scene_id:
        return {
            "ok": False,
            "error": "SCENE_ID_REQUIRED",
            "message": "This shot is not bound to a Scene.",
        }
    asset_id = str(getattr(candidate, "asset_id", "") or "").strip()
    if not asset_id:
        return {
            "ok": False,
            "error": "NO_APPROVED_TAKE",
            "message": "Approve a take before sending to Timeline.",
        }
    cine = getattr(getattr(shot, "camera", None), "cinematic", None)
    framing = getattr(cine, "framing", "") or "scene"
    name = f"{getattr(candidate, 'take_label', 'Take') or 'Take'} — {framing}"
    clips = [
        {
            "clipId": f"scene_shot_{shot.id}_{candidate.id}",
            "assetId": asset_id,
            "name": name,
            "shot_index": 0,
            "shot_prompt": getattr(shot, "intent", "") or getattr(shot, "prompt", ""),
            "character_ids": list(getattr(shot, "character_ids", None) or []),
            "prop_ids": list(getattr(shot, "prop_entity_ids", None) or []),
            "ers_package_id": getattr(shot, "ers_package_id", "") or "",
            "sheet_id": getattr(shot, "sheet_id", "") or "",
            "source_scene": scene_id,
            "approved_take": True,
            "role": "start",
        }
    ]
    result = export_to_timeline(
        db,
        project_id,
        scene_id,
        clips,
        label=name,
        batch_block_id=batch_block_id,
    )
    if result.get("ok"):
        result["shot_id"] = shot.id
        result["candidate_id"] = candidate.id
        result["sheet_id"] = getattr(shot, "sheet_id", "")
        result["clips_sent"] = 1
    return result


def build_scene_shot_clips(batch: SceneGenerationBatch) -> list[dict[str, Any]]:
    """Build the ordered clip dicts for a Scene Creator batch.

    Each clip carries the scene-shot provenance that fits the frozen W46
    ``BatchClip`` shape: ``clipId``, ``assetId``, ``name`` (label), and the
    shot index baked into the label so it survives the W46 placement. Shot
    order, raw prompt, character IDs, prop IDs, ERS id, and source scene
    are recorded as ledger provenance inside ``export_to_timeline`` (the
    frozen ``BatchClip`` has no metadata dict).

    Failed regens (ids starting with ``failed_``) and empty slots are
    skipped — never placed as mock clips (Law #7).
    """
    clips: list[dict[str, Any]] = []
    shots = list(batch.shot_requests or [])
    for index, asset_id in enumerate(batch.result_asset_ids or []):
        if not asset_id or str(asset_id).startswith("failed_"):
            continue
        shot = shots[index] if index < len(shots) else None
        shot_index = (shot.index if shot else index) + 1
        framing = (shot.framing if shot else "") or "scene"
        # `name` becomes the BatchClip.label (within W46 field length norms).
        # The shot index is embedded so the creator can see shot order on the
        # timeline even after W46 flattening.
        name = f"Shot {shot_index} — {framing}"
        # role conveys shot position within the batch (start/middle/end/guide)
        # using the same vocabulary the W46 BatchClip.role field accepts.
        role = _shot_role(index, len(batch.result_asset_ids or []))
        clips.append(
            {
                "clipId": f"scene_shot_{batch.id}_{index}",
                "assetId": asset_id,
                "name": name,
                # Extra provenance fields are NOT consumed by the frozen W46
                # BatchClip (it has no metadata dict); they're recorded by the
                # export ledger. Kept here so callers + Co-Director can read
                # the intent of each clip without re-loading the batch.
                "shot_index": index,
                "shot_prompt": (shot.raw_text if shot else ""),
                "character_ids": list(shot.characters) if shot else [],
                "prop_ids": list(shot.prop_entities) if shot else [],
                "ers_package_id": batch.ers_package_id,
                "source_scene": batch.project_id,
                "role": role,
            }
        )
    return clips


def _shot_role(index: int, total: int) -> str:
    """Map a shot's position to a W46 BatchClip.role-friendly label."""
    if total <= 0:
        return "guide"
    if index == 0:
        return "start"
    if index == total - 1:
        return "end"
    return "middle"
