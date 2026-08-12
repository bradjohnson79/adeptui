"""Multi-Shot Image Planning service layer.

Owns persistence semantics for plans, shots, and candidates so the HTTP router
(and later the Co-Director / Timeline surfaces) share one source of truth.
All lookups are project-scoped: a plan/shot/candidate id from another project is
treated as missing (404), never leaked.

Approval invariant: at most one approved candidate per shot. Approving a new
candidate demotes the previously approved one to ``pending``; rejecting the
approved candidate clears the shot's approval fields. Rejected candidates stay
in history — they are never deleted by approve/reject flows.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from .contracts import (
    MultiShotCandidateCreate,
    MultiShotPlanCreate,
    MultiShotPlanUpdate,
    MultiShotCreate,
    MultiShotUpdate,
)
from .models import MultiShotCandidateRow, MultiShotPlanRow, MultiShotRow


def ensure_tables() -> None:
    from ...db import Base, engine

    Base.metadata.create_all(
        bind=engine,
        tables=[
            MultiShotPlanRow.__table__,
            MultiShotRow.__table__,
            MultiShotCandidateRow.__table__,
        ],
    )


def _now() -> datetime:
    return datetime.utcnow()


def _loads(raw: str | None, default: Any) -> Any:
    try:
        return json.loads(raw or "") if raw else default
    except Exception:
        return default


def _dumps(value: Any, default: str) -> str:
    if value is None:
        return default
    try:
        return json.dumps(value)
    except Exception:
        return default


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


# ---------------------------------------------------------------------------
# Serializers (camelCase wire format)
# ---------------------------------------------------------------------------


def candidate_out(row: MultiShotCandidateRow) -> dict[str, Any]:
    return {
        "candidateId": row.id,
        "shotId": row.shot_id,
        "planId": row.plan_id,
        "projectId": row.project_id,
        "generationId": row.generation_id,
        "provider": row.provider,
        "model": row.model,
        "seed": row.seed,
        "prompt": row.prompt,
        "references": _loads(row.references_json, []),
        "loras": _loads(row.loras_json, []),
        "settings": _loads(row.settings_json, {}),
        "assetId": row.asset_id,
        "status": row.status,
        "createdAt": _iso(row.created_at),
    }


def shot_out(row: MultiShotRow, candidates: Optional[list[MultiShotCandidateRow]] = None) -> dict[str, Any]:
    payload = {
        "shotId": row.id,
        "planId": row.plan_id,
        "projectId": row.project_id,
        "sceneId": row.scene_id,
        "order": row.order_index,
        "title": row.title,
        "prompt": row.prompt,
        "imagePrompt": row.image_prompt,
        "videoPrompt": row.video_prompt,
        "durationHint": row.duration_hint,
        "framing": row.framing,
        "cameraAngle": row.camera_angle,
        "subjectIds": _loads(row.subject_ids_json, []),
        "referenceIds": _loads(row.reference_ids_json, []),
        "seedStrategy": row.seed_strategy,
        "status": row.status,
        "approvedAssetId": row.approved_asset_id,
        "approvedCandidateId": row.approved_candidate_id,
        "timelineBatchBlockId": row.timeline_batch_block_id,
        "createdAt": _iso(row.created_at),
        "updatedAt": _iso(row.updated_at),
    }
    if candidates is not None:
        payload["candidates"] = [candidate_out(item) for item in candidates]
    return payload


def _group_shared_references(references: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for ref in references:
        role = str(ref.get("role") or "style")
        grouped.setdefault(role, []).append(ref)
    return grouped


def plan_out(
    row: MultiShotPlanRow,
    shots: Optional[list[dict[str, Any]]] = None,
    shot_count: Optional[int] = None,
) -> dict[str, Any]:
    references = _loads(row.shared_references_json, [])
    grouped = _group_shared_references(references)
    payload: dict[str, Any] = {
        "planId": row.id,
        "projectId": row.project_id,
        "sceneId": row.scene_id,
        "name": row.name,
        "providerId": row.provider_id,
        "modelId": row.model_id,
        "sharedVisualContext": row.shared_visual_context,
        "sharedReferences": references,
        # Role-grouped convenience views over the single polymorphic list.
        "sharedStyleReferences": grouped.get("style", []),
        "sharedCharacterReferences": grouped.get("character", []),
        "sharedEnvironmentReferences": grouped.get("environment", []),
        "sharedMoodboardReferences": grouped.get("moodboard", []),
        "aspectRatio": row.aspect_ratio,
        "resolutionLabel": row.resolution_label,
        "status": row.status,
        "createdAt": _iso(row.created_at),
        "updatedAt": _iso(row.updated_at),
    }
    if shots is not None:
        payload["shots"] = shots
    if shot_count is not None:
        payload["shotCount"] = shot_count
    return payload


# ---------------------------------------------------------------------------
# Lookups (always project-scoped)
# ---------------------------------------------------------------------------


def get_plan_row(db: Session, project_id: str, plan_id: str) -> Optional[MultiShotPlanRow]:
    row = db.get(MultiShotPlanRow, plan_id)
    if row is None or row.project_id != project_id:
        return None
    return row


def get_shot_row(db: Session, plan: MultiShotPlanRow, shot_id: str) -> Optional[MultiShotRow]:
    row = db.get(MultiShotRow, shot_id)
    if row is None or row.plan_id != plan.id or row.project_id != plan.project_id:
        return None
    return row


def list_shot_rows(db: Session, plan: MultiShotPlanRow) -> list[MultiShotRow]:
    return (
        db.query(MultiShotRow)
        .filter(MultiShotRow.plan_id == plan.id, MultiShotRow.project_id == plan.project_id)
        .order_by(MultiShotRow.order_index, MultiShotRow.created_at)
        .all()
    )


def list_candidate_rows(db: Session, shot: MultiShotRow) -> list[MultiShotCandidateRow]:
    return (
        db.query(MultiShotCandidateRow)
        .filter(MultiShotCandidateRow.shot_id == shot.id, MultiShotCandidateRow.project_id == shot.project_id)
        .order_by(MultiShotCandidateRow.created_at, MultiShotCandidateRow.id)
        .all()
    )


# ---------------------------------------------------------------------------
# Plan CRUD
# ---------------------------------------------------------------------------


def create_plan(db: Session, project_id: str, scene_id: str, body: MultiShotPlanCreate) -> MultiShotPlanRow:
    now = _now()
    row = MultiShotPlanRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=scene_id,
        name=(body.name or "").strip() or "Multi-Shot Plan",
        provider_id=body.provider_id or "",
        model_id=body.model_id or "",
        shared_visual_context=body.shared_visual_context or "",
        shared_references_json=_dumps(
            [ref.model_dump(mode="json", by_alias=True) for ref in (body.shared_references or [])],
            "[]",
        ),
        aspect_ratio=body.aspect_ratio or "",
        resolution_label=body.resolution_label or "",
        status=body.status or "draft",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_plans(db: Session, project_id: str, scene_id: str) -> list[tuple[MultiShotPlanRow, int]]:
    rows = (
        db.query(MultiShotPlanRow)
        .filter(MultiShotPlanRow.project_id == project_id, MultiShotPlanRow.scene_id == scene_id)
        .order_by(MultiShotPlanRow.created_at, MultiShotPlanRow.id)
        .all()
    )
    out: list[tuple[MultiShotPlanRow, int]] = []
    for row in rows:
        count = db.query(MultiShotRow).filter(MultiShotRow.plan_id == row.id).count()
        out.append((row, count))
    return out


def update_plan(db: Session, row: MultiShotPlanRow, body: MultiShotPlanUpdate) -> MultiShotPlanRow:
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        row.name = str(data["name"]).strip() or row.name
    if "provider_id" in data:
        row.provider_id = data["provider_id"] or ""
    if "model_id" in data:
        row.model_id = data["model_id"] or ""
    if "shared_visual_context" in data:
        row.shared_visual_context = data["shared_visual_context"] or ""
    if "shared_references" in data and body.shared_references is not None:
        row.shared_references_json = _dumps(
            [ref.model_dump(mode="json", by_alias=True) for ref in body.shared_references],
            "[]",
        )
    if "aspect_ratio" in data:
        row.aspect_ratio = data["aspect_ratio"] or ""
    if "resolution_label" in data:
        row.resolution_label = data["resolution_label"] or ""
    if "status" in data and data["status"] is not None:
        row.status = data["status"]
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def delete_plan(db: Session, row: MultiShotPlanRow) -> None:
    """Delete the plan, all of its shots, and every candidate on those shots."""

    shot_ids = [shot.id for shot in db.query(MultiShotRow).filter(MultiShotRow.plan_id == row.id).all()]
    if shot_ids:
        db.query(MultiShotCandidateRow).filter(MultiShotCandidateRow.shot_id.in_(shot_ids)).delete(
            synchronize_session=False
        )
        db.query(MultiShotRow).filter(MultiShotRow.id.in_(shot_ids)).delete(synchronize_session=False)
    db.delete(row)
    db.commit()


# ---------------------------------------------------------------------------
# Shot CRUD + ordering
# ---------------------------------------------------------------------------


def add_shot(db: Session, plan: MultiShotPlanRow, body: MultiShotCreate) -> MultiShotRow:
    current_max = (
        db.query(MultiShotRow.order_index)
        .filter(MultiShotRow.plan_id == plan.id)
        .order_by(MultiShotRow.order_index.desc())
        .first()
    )
    next_order = (current_max[0] + 1) if current_max else 0
    now = _now()
    row = MultiShotRow(
        id=str(uuid.uuid4()),
        plan_id=plan.id,
        project_id=plan.project_id,
        scene_id=plan.scene_id,
        order_index=next_order,
        title=body.title or "",
        prompt=body.prompt or "",
        image_prompt=body.image_prompt or "",
        video_prompt=body.video_prompt or "",
        duration_hint=body.duration_hint,
        framing=body.framing or "",
        camera_angle=body.camera_angle or "",
        subject_ids_json=_dumps(body.subject_ids, "[]"),
        reference_ids_json=_dumps(body.reference_ids, "[]"),
        seed_strategy=body.seed_strategy or "sequence",
        status=body.status or "pending",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    plan.updated_at = now
    db.commit()
    db.refresh(row)
    return row


def update_shot(db: Session, row: MultiShotRow, body: MultiShotUpdate) -> MultiShotRow:
    data = body.model_dump(exclude_unset=True)
    for key, column in (
        ("title", "title"),
        ("prompt", "prompt"),
        ("image_prompt", "image_prompt"),
        ("video_prompt", "video_prompt"),
        ("framing", "framing"),
        ("camera_angle", "camera_angle"),
        ("seed_strategy", "seed_strategy"),
        ("status", "status"),
    ):
        if key in data and data[key] is not None:
            setattr(row, column, data[key])
    if "duration_hint" in data:
        row.duration_hint = data["duration_hint"]
    if "subject_ids" in data and data["subject_ids"] is not None:
        row.subject_ids_json = _dumps(data["subject_ids"], "[]")
    if "reference_ids" in data and data["reference_ids"] is not None:
        row.reference_ids_json = _dumps(data["reference_ids"], "[]")
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def delete_shot(db: Session, row: MultiShotRow) -> None:
    db.query(MultiShotCandidateRow).filter(MultiShotCandidateRow.shot_id == row.id).delete(
        synchronize_session=False
    )
    db.delete(row)
    db.commit()


def reorder_shots(db: Session, plan: MultiShotPlanRow, shot_ids: list[str]) -> list[MultiShotRow]:
    """Apply a full-set reorder. Raises ValueError on any set mismatch."""

    existing = list_shot_rows(db, plan)
    existing_ids = {shot.id for shot in existing}
    requested_ids = list(shot_ids)
    if len(requested_ids) != len(set(requested_ids)):
        raise ValueError("shotIds contains duplicate entries")
    if set(requested_ids) != existing_ids:
        missing = sorted(existing_ids - set(requested_ids))
        unknown = sorted(set(requested_ids) - existing_ids)
        parts = []
        if missing:
            parts.append(f"missing shot ids: {', '.join(missing)}")
        if unknown:
            parts.append(f"unknown shot ids: {', '.join(unknown)}")
        raise ValueError("Reorder must list every shot in the plan exactly once (" + "; ".join(parts) + ")")
    position = {shot_id: index for index, shot_id in enumerate(requested_ids)}
    now = _now()
    for shot in existing:
        shot.order_index = position[shot.id]
        shot.updated_at = now
    plan.updated_at = now
    db.commit()
    return list_shot_rows(db, plan)


# ---------------------------------------------------------------------------
# Candidates + approval
# ---------------------------------------------------------------------------


def add_candidate(db: Session, plan: MultiShotPlanRow, shot: MultiShotRow, body: MultiShotCandidateCreate) -> MultiShotCandidateRow:
    row = MultiShotCandidateRow(
        id=str(uuid.uuid4()),
        shot_id=shot.id,
        plan_id=plan.id,
        project_id=plan.project_id,
        generation_id=body.generation_id,
        provider=body.provider or plan.provider_id or "",
        model=body.model or plan.model_id or "",
        seed=body.seed,
        prompt=body.prompt if body.prompt is not None else (shot.image_prompt or shot.prompt),
        references_json=_dumps(body.references, "[]"),
        loras_json=_dumps(body.loras, "[]"),
        settings_json=_dumps(body.settings, "{}"),
        asset_id=body.asset_id,
        status=body.status or "pending",
        created_at=_now(),
    )
    db.add(row)
    if shot.status == "pending":
        shot.status = "candidate_review"
    shot.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def get_candidate_row(db: Session, shot: MultiShotRow, candidate_id: str) -> Optional[MultiShotCandidateRow]:
    row = db.get(MultiShotCandidateRow, candidate_id)
    if row is None or row.shot_id != shot.id or row.project_id != shot.project_id:
        return None
    return row


def approve_candidate(db: Session, shot: MultiShotRow, candidate: MultiShotCandidateRow) -> MultiShotRow:
    # Demote any previously approved candidate — at most one approval per shot.
    for other in list_candidate_rows(db, shot):
        if other.id != candidate.id and other.status == "approved":
            other.status = "pending"
    candidate.status = "approved"
    shot.approved_candidate_id = candidate.id
    shot.approved_asset_id = candidate.asset_id
    shot.status = "approved"
    shot.updated_at = _now()
    db.commit()
    db.refresh(shot)
    return shot


def reject_candidate(db: Session, shot: MultiShotRow, candidate: MultiShotCandidateRow) -> MultiShotRow:
    candidate.status = "rejected"
    if shot.approved_candidate_id == candidate.id:
        shot.approved_candidate_id = None
        shot.approved_asset_id = None
        shot.status = "candidate_review"
    elif shot.status == "pending":
        shot.status = "candidate_review"
    shot.updated_at = _now()
    db.commit()
    db.refresh(shot)
    return shot


# ---------------------------------------------------------------------------
# Timeline handoff (W46 batch-owned contracts)
# ---------------------------------------------------------------------------


def send_to_timeline(
    db: Session,
    plan: MultiShotPlanRow,
    *,
    only_missing: bool = True,
    generator_id: str | None = None,
    default_duration: float = 5.0,
) -> dict[str, Any]:
    """Hand off every approved Multi-Shot to the W46 Timeline as a batch.

    Each approved shot becomes one immutable BatchBlock with:

    - visual clip: the shot's approved asset as the start image
    - prompt segment: the shot's video prompt (falling back to image prompt / prompt)
    - duration: shot duration hint or ``default_duration``
    - generator: ``generator_id`` or the plan's configured model / scene default

    The created ``batchBlockId`` is recorded on the shot row and the shot status
    moves to ``sent_to_timeline``. Already-linked shots may be skipped with
    ``only_missing=True`` to avoid duplicate batches.
    """

    from ...director_timeline_w46 import orchestrator as timeline_orchestrator, service as timeline_service
    from ...director_timeline_w46.contracts import BatchClip, TimelinePromptSegment

    shots = list_shot_rows(db, plan)
    created: list[dict[str, Any]] = []
    skipped: list[str] = []
    for shot in shots:
        if shot.status == "sent_to_timeline":
            skipped.append(shot.id)
            continue
        if shot.status != "approved":
            continue
        if only_missing and shot.timeline_batch_block_id:
            skipped.append(shot.id)
            continue

        duration = float(shot.duration_hint if shot.duration_hint is not None else default_duration)
        batch_result = timeline_service.add_batch(
            db,
            plan.project_id,
            plan.scene_id,
            label=shot.title or f"Shot {shot.order_index + 1}",
            planned_duration=duration,
            generator_id=generator_id or plan.model_id or None,
        )
        if not batch_result.get("ok"):
            raise RuntimeError(
                f"Failed to create Timeline batch for shot {shot.id}: {batch_result.get('error')}"
            )
        batch = batch_result["batch"]
        batch_id = batch["id"]

        clip = BatchClip(
            kind="image",
            assetId=shot.approved_asset_id,
            start=0.0,
            length=duration,
            label=shot.title or f"Shot {shot.order_index + 1}",
            role="start",
        )
        clip_result = timeline_orchestrator.add_clip_to_batch(
            db, plan.project_id, plan.scene_id, batch_id, clip.model_dump(mode="json")
        )
        if not clip_result.get("ok"):
            raise RuntimeError(
                f"Failed to add visual clip to batch {batch_id} for shot {shot.id}: "
                f"{clip_result.get('error')}"
            )

        prompt_text = (shot.video_prompt or shot.image_prompt or shot.prompt or "").strip()
        if prompt_text:
            patch = {
                "promptSegments": [
                    TimelinePromptSegment(
                        start=0.0, length=duration, text=prompt_text
                    ).model_dump(mode="json")
                ]
            }
            prompt_result = timeline_orchestrator.touch_batch_config(
                db, plan.project_id, plan.scene_id, batch_id, patch
            )
            if not prompt_result.get("ok"):
                raise RuntimeError(
                    f"Failed to set prompt on batch {batch_id} for shot {shot.id}: "
                    f"{prompt_result.get('error')}"
                )

        shot.timeline_batch_block_id = batch_id
        shot.status = "sent_to_timeline"
        shot.updated_at = _now()
        db.commit()
        db.refresh(shot)
        created.append(
            {
                "shotId": shot.id,
                "batchBlockId": batch_id,
                "approvedAssetId": shot.approved_asset_id,
                "approvedCandidateId": shot.approved_candidate_id,
                "duration": duration,
                "prompt": prompt_text,
            }
        )

    return {
        "planId": plan.id,
        "projectId": plan.project_id,
        "sceneId": plan.scene_id,
        "created": created,
        "skipped": skipped,
        "count": len(created),
    }


def ers_recommendation_for_scene(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    """Advisory: whether an Environment Reference Sheet is available for this project.

    Krea 2 Multi-Shot benefits from environmental continuity. When no ERS exists,
    the recommendation is surfaced so the creator can create one; when ERS sheets
    exist, their environment assets are already wired through the shared
    reference path (``environment`` role) by the reference-conditioning layer.
    """

    from ...environment_reference_sheet import store as ers_store

    sheets = ers_store.list_sheets(project_id)
    available = len(sheets) > 0
    sheet_ids = [sheet.sheetId for sheet in sheets]
    if available:
        reason = (
            f"{len(sheets)} Environment Reference Sheet(s) available for this project. "
            "ERS environment assets are wired as ``environment`` conditioning when shared references include them."
        )
        return {
            "ersAvailable": True,
            "sheetCount": len(sheets),
            "recommended": False,
            "reason": reason,
            "missingReason": None,
            "sheetIds": sheet_ids,
        }
    return {
        "ersAvailable": False,
        "sheetCount": 0,
        "recommended": True,
        "reason": (
            "No Environment Reference Sheet found for this project. "
            "Creating one improves location continuity across Krea 2 Multi-Shot generations."
        ),
        "missingReason": "no_ers_sheet",
        "sheetIds": [],
    }
