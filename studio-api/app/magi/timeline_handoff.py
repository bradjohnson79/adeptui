"""MAGI <-> Timeline handoff (m5).

Import and export routed ONLY through the currently-certified W46 Timeline
contract: ``Scene -> BatchBlock -> batch-owned clips -> immutable batchBlockId``
(see ``docs/release-gate/magi-operational/MAGI_TIMELINE_INTEROP_AUDIT.md`` and the
Critical Timeline Handoff Law).

- Import: pull an existing project asset into a MAGI sequence clip, preserving
  optional W46 lineage (batchBlockId/generationId/takeId/sourceClipId/sceneId).
- Export: place MAGI sequence clips onto the Timeline as batch-owned clips via
  the W46 ``add_batch`` + ``add_clip_to_batch`` surface. No regeneration, no
  fabricated candidate/execution snapshots.

This module never writes ``project.settings_json["timeline"]`` — that legacy
pathway is NOT authoritative for MAGI.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..db import Asset, Scene


def _asset_kind(asset: Asset) -> str:
    if asset.kind in ("video",):
        return "video"
    if asset.kind in ("audio", "music"):
        return "audio"
    if asset.kind == "sfx":
        return "sfx"
    return "image"


def _scene(db: Session, project_id: str, scene_id: str) -> Scene | None:
    return (
        db.query(Scene)
        .filter(Scene.project_id == project_id, Scene.id == scene_id)
        .one_or_none()
    )


def import_timeline_asset(
    db: Session,
    project_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Import a project asset as a MAGI clip, preserving W46 lineage.

    Body: ``{assetId, sceneId?, batchBlockId?, generationId?, takeId?,
    sourceClipId?}``. The asset must belong to ``project_id`` (cross-project
    leakage rejected). Returns a ready-to-insert ``MagiClip`` dict whose lineage
    fields are FLAT (m5 B2) to match the frozen ``MagiClipModel``/``MagiClip``
    contracts, plus the resolved media defaults.
    """
    asset_id = str(body.get("assetId") or "").strip()
    if not asset_id:
        return {"ok": False, "error": "ASSET_ID_REQUIRED"}
    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id, Asset.project_id == project_id)
        .one_or_none()
    )
    if not asset:
        return {
            "ok": False,
            "error": "ASSET_OWNERSHIP",
            "message": f"Asset '{asset_id}' does not exist in project '{project_id}'.",
        }

    clip = {
        "assetId": asset.id,
        "name": asset.tag or asset.filename or "Imported clip",
        # m5 B2: flat lineage (schema parity with the frozen frontend/backend
        # MagiClip contracts — never a nested `lineage` object).
        "batchBlockId": body.get("batchBlockId"),
        "generationId": body.get("generationId"),
        "takeId": body.get("takeId"),
        "sourceClipId": body.get("sourceClipId"),
        "sceneId": body.get("sceneId"),
        "kind": _asset_kind(asset),
    }
    return {"ok": True, "clip": clip}


def export_to_timeline(
    db: Session,
    project_id: str,
    scene_id: str,
    clips: list[dict[str, Any]],
    *,
    label: str | None = None,
    batch_block_id: str | None = None,
) -> dict[str, Any]:
    """Place MAGI sequence clips onto the W46 Timeline as batch-owned clips.

    ``clips``: ``[{clipId, assetId, name?, startFrame?, durationFrames?}]``.
    Every asset must belong to the project. Uses the certified W46 surface:
    ``service.add_batch`` -> ``orchestrator.add_clip_to_batch``. Never
    regenerates media and never fabricates candidate/execution snapshots.

    Existing-batch export REQUIRES an explicit ``batch_block_id`` (m5 B3); a
    missing/unknown batch is a structured ``BATCH_NOT_FOUND`` — there is no
    silent ``batches[0]`` fallback. On success, MAGI-side provenance is
    recorded in ``sequence.json.exportLedger`` (no revision bump).
    """
    scene = _scene(db, project_id, scene_id)
    if not scene:
        return {"ok": False, "error": "SCENE_NOT_FOUND"}

    from ..director_timeline_w46 import orchestrator, service

    # Genuine CLIP_NOT_FOUND trigger (m8): when the project has a saved sequence
    # that contains clips, every clipId the caller references must exist in it.
    # A stale or unknown clipId is a structured 404 CLIP_NOT_FOUND — never a
    # silent skip. A project with no saved clips (never saved, or a
    # ledger-only/empty sequence) keeps the legacy asset-placement path, where
    # clipId is recorded as W46 ``legacyClipId`` metadata only.
    from .sequence.store import get_sequence, has_saved_sequence

    if has_saved_sequence(project_id):
        sequence = get_sequence(project_id)
        saved_clips = sequence.get("clips") or []
        if saved_clips:
            known_clip_ids = {c.get("id") for c in saved_clips}
            missing_clip_ids = sorted(
                {str(c.get("clipId")) for c in clips if c.get("clipId")} - known_clip_ids
            )
            if missing_clip_ids:
                return {
                    "ok": False,
                    "error": "CLIP_NOT_FOUND",
                    "message": f"Sequence does not contain clip(s): {missing_clip_ids}",
                }

    # Validate ownership up front for all clips.
    ids = sorted({c.get("assetId") for c in clips if c.get("assetId")})
    owned: set[str] = set()
    if ids:
        rows = (
            db.query(Asset.id)
            .filter(Asset.id.in_(ids), Asset.project_id == project_id)
            .all()
        )
        owned = {r[0] for r in rows}
    missing = [aid for aid in ids if aid not in owned]
    if missing:
        return {
            "ok": False,
            "error": "ASSET_OWNERSHIP",
            "message": f"Clip references assets not in project '{project_id}': {missing}",
        }

    def _place(batch_id: str) -> list[dict[str, Any]]:
        placed = []
        for clip in clips:
            asset = db.query(Asset).filter(Asset.id == clip["assetId"]).first()
            result = orchestrator.add_clip_to_batch(
                db,
                project_id,
                scene_id,
                batch_id,
                {
                    "kind": _asset_kind(asset),
                    "assetId": clip["assetId"],
                    "label": clip.get("name") or asset.tag or asset.filename or "MAGI clip",
                    "start": float(clip.get("startFrame") or 0),
                    "length": float(
                        (clip.get("durationFrames") or 0) / 24.0 or 5.0
                    ),
                    "legacyClipId": clip.get("clipId"),
                },
            )
            placed.append(result)
        return placed

    if batch_block_id:
        # Existing-batch export requires a real batch. Probe first so a missing
        # batch yields ONE structured BATCH_NOT_FOUND (never silent fallback,
        # never a partial append loop against a phantom batch).
        from ..director_timeline_w46.store import load_master
        from ..director_timeline_w46.contracts import SceneTimelineMaster

        master_payload = load_master(db, project_id, scene_id)
        if not master_payload.get("ok"):
            return master_payload
        master = SceneTimelineMaster.model_validate(master_payload["master"])
        if not any(block.id == batch_block_id for block in master.batchBlocks):
            return {"ok": False, "error": "BATCH_NOT_FOUND", "mock": False}
        created = _place(batch_block_id)
        if not all(r.get("ok", False) for r in created):
            return {
                "ok": False,
                "error": "TIMELINE_HANDOFF_FAILED",
                "mock": False,
                "message": "One or more clips could not be placed on the batch.",
            }
        _record_ledger(
            project_id,
            batch_block_id,
            clips,
            created,
            scene_id=scene_id,
            label=label,
        )
        return {
            "ok": True,
            "batchBlockId": batch_block_id,
            "clips": created,
            "mock": False,
        }

    add = service.add_batch(
        db,
        project_id,
        scene_id,
        label=label or "MAGI export",
        planned_duration=5.0,
    )
    if not add.get("ok"):
        return {
            "ok": False,
            "error": "TIMELINE_HANDOFF_FAILED",
            "message": add.get("message") or "MAGI timeline batch could not be created.",
        }
    batch_id = (add.get("batch") or {}).get("id")
    if not batch_id:
        from ..director_timeline_w46.contracts import _nid

        batch_id = _nid("bb_")

    created = _place(batch_id)
    if not all(r.get("ok", False) for r in created):
        return {
            "ok": False,
            "error": "TIMELINE_HANDOFF_FAILED",
            "mock": False,
            "message": "One or more clips could not be placed on the new batch.",
        }
    _record_ledger(
        project_id,
        batch_id,
        clips,
        created,
        scene_id=scene_id,
        label=label or "MAGI export",
    )

    return {
        "ok": True,
        "batchBlockId": batch_id,
        "clips": created,
        "mock": False,
    }


def _record_ledger(
    project_id: str,
    batch_block_id: str,
    clips: list[dict[str, Any]],
    placed: list[dict[str, Any]],
    *,
    scene_id: str | None,
    label: str | None,
) -> None:
    """Record MAGI-side export provenance (B3) without bumping sequence revision.

    The frozen W46 ``BatchClip`` carries no metadata dict, so provenance lives
    in ``sequence.json.exportLedger`` keyed by ``batchBlockId``.
    """
    from .sequence.store import record_export_ledger

    entries = []
    for clip, result in zip(clips, placed):
        w46 = (result.get("clip") or {})
        entries.append(
            {
                "clipId": clip.get("clipId"),
                "w46ClipId": w46.get("id"),
                "assetId": clip.get("assetId"),
            }
        )
    record_export_ledger(
        project_id,
        batch_block_id,
        entries,
        scene_id=scene_id,
        label=label,
    )
