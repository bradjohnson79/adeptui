"""Prop Creator Advanced service â€” primary generate/approve + angle Qwen Edit.

Standard endpoints stay in service.py untouched for generate/approve PRS path.
Advanced uses primary_prompt as sole design authority (no silent CD rewrite).
Angles fan out from primary_approved_asset_id via Qwen Image Edit 2509.
"""

from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..db import Job
from ..spatial_map.ers_contracts import PropEntity
from ..spatial_map.ers_persistence import load_prop_entity_by_id, save_prop_entity
from . import advanced_multiview as mv
from .generation import build_prop_candidate_plans, persist_generator_selection
from .prompt import STYLE_LABELS, NEGATIVE_PROMPT
from .readiness import (
    OPTIONAL_VIEWS,
    approved_primary_asset_id,
    identity_ready,
    valid_primary_candidate_asset_id,
)
from .service import (
    PropCreatorError,
    _enqueue_plans,
    _set_asset_approval,
    _sync_candidates,
    get_prop,
    require_owned_prop,
)
from .view_upload import (
    SOURCE_GENERATED,
    SOURCE_UPLOADED,
    stamp_prop_view_asset,
    write_prop_image_asset,
)

logger = logging.getLogger(__name__)

# Same-process cancel observation for async Advanced PRS jobs (DB reload alone can race saves).
_SHEET_CANCEL_IDS: set[str] = set()
_SHEET_CANCEL_LOCK = threading.Lock()


def _sheet_cancel_mark(prop_id: str) -> None:
    with _SHEET_CANCEL_LOCK:
        _SHEET_CANCEL_IDS.add(prop_id)


def _sheet_cancel_clear(prop_id: str) -> None:
    with _SHEET_CANCEL_LOCK:
        _SHEET_CANCEL_IDS.discard(prop_id)


def _sheet_cancel_marked(prop_id: str) -> bool:
    with _SHEET_CANCEL_LOCK:
        return prop_id in _SHEET_CANCEL_IDS



def _compile_primary_prompt(prop: PropEntity) -> dict[str, Any]:
    """Creator primary_prompt is authoritative. Never rewrite from CD side-channels."""
    name = (prop.display_label or prop.tag or "prop").strip()
    primary = (prop.primary_prompt or "").strip()
    if not primary:
        raise PropCreatorError("Primary design prompt is required for Advanced Prop generation.")
    style_key = (prop.visual_style or "").strip()
    style_label = STYLE_LABELS.get(style_key, style_key.replace("_", " ").strip())
    identity_view = (
        "Single complete prop identity image, the full prop centered and clearly visible, "
        "minimal occlusion, neutral simple presentation, production-reference quality. "
        "No character holding the prop, no environment scene, no four-view sheet, "
        "no collage, no extra props, no unreadable text unless lettering is part of the prop."
    )
    facts = [f"Prop: {name}.", primary.rstrip(".") + "."]
    if style_label:
        facts.append(f"Image style: {style_label}.")
    if prop.advanced_type:
        facts.append(f"Prop class: {prop.advanced_type}.")
    facts.append(identity_view)
    return {
        "prompt": " ".join(facts),
        "negative_prompt": NEGATIVE_PROMPT,
        "name": name,
        "description": primary,
        "visual_style": style_key,
        "style_label": style_label,
        "authority": "primary_prompt",
    }


def apply_advanced_fields(
    prop: PropEntity,
    *,
    mode: str | None = None,
    advanced_type: str | None = None,
    primary_prompt: str | None = None,
    hero_optional: bool | None = None,
) -> PropEntity:
    if mode is not None:
        m = (mode or "standard").strip().lower()
        if m not in {"standard", "advanced"}:
            raise PropCreatorError("mode must be 'standard' or 'advanced'.")
        prop.mode = m  # type: ignore[assignment]
    if advanced_type is not None:
        at = (advanced_type or "").strip().lower() or None
        if at is not None and at not in {"spacecraft", "vehicle", "aircraft", "mech", "other"}:
            raise PropCreatorError(
                "advanced_type must be spacecraft, vehicle, aircraft, mech, or other."
            )
        prop.advanced_type = at  # type: ignore[assignment]
    if primary_prompt is not None:
        # Authority: store exactly what creator sent â€” no silent rewrite.
        prop.primary_prompt = primary_prompt
    if hero_optional is not None:
        prop.hero_optional = bool(hero_optional)
    if prop.mode == "advanced":
        prop.angles = mv.ensure_angles_map(
            {k: v for k, v in (prop.angles or {}).items()},
            hero_optional=prop.hero_optional,
        )
    return prop



def _enqueue_advanced_primary_ref_edit(
    db: Session,
    project_id: str,
    prop: PropEntity,
    compiled: dict[str, Any],
    *,
    candidate_count: int = 1,
) -> list:
    """Primary looks from locked reference via Qwen Image Edit 2509 only.

    Matches angle authority (forceWorkflowKey=qwen_edit_2509.edit). Never routes
    through qwen2512.ref_edit / zimage.ref_edit silent substitutes.
    """
    from ..spatial_map.ers_contracts import PropCandidate
    from ..storyboard_jobs import enqueue_imagegen_job
    from ..workflows.qwen_image_edit_2509 import (
        QWEN_EDIT_2509_CHARACTER_ANGLE_SIZE,
        QWEN_EDIT_2509_DEFAULT_CFG,
        QWEN_EDIT_2509_DEFAULT_STEPS,
    )

    mv.assert_can_generate()
    ref_id = str(prop.reference_asset_id or "").strip()
    if not ref_id:
        raise PropCreatorError("Locked reference asset is required for Advanced primary edit.")
    count = max(1, min(int(candidate_count or 1), 4))
    size = QWEN_EDIT_2509_CHARACTER_ANGLE_SIZE
    candidates: list[PropCandidate] = []
    for index in range(count):
        seed = uuid.uuid4().int % 2_147_483_647
        body: dict[str, Any] = {
            "prompt": compiled["prompt"],
            "negative_prompt": compiled["negative_prompt"] or mv.PROP_ANGLE_NEGATIVE,
            "width": size,
            "height": size,
            "modelFamilyPreference": mv.QWEN_EDIT_FAMILY,
            "lockModelFamily": True,
            "seed": seed,
            "steps": QWEN_EDIT_2509_DEFAULT_STEPS,
            "cfg": QWEN_EDIT_2509_DEFAULT_CFG,
            "denoise": 0.55,
            "source_asset_id": ref_id,
            "tag": f"prop_{prop.tag or prop.id[:8]}_primary_c{index + 1}",
            "purpose": "project_prop",
            "source": "local",
            "providerPreference": "local",
            "forceWorkflowKey": mv.QWEN_EDIT_WORKFLOW_KEY,
            "allow_force_workflow_key": True,
            "allowDraft": True,
            "allow_draft": True,
            "creativeContext": {
                "objective": "project_prop_primary_ref_edit",
                "propId": prop.id,
                "workflowKey": mv.QWEN_EDIT_WORKFLOW_KEY,
                "modelFamily": mv.QWEN_EDIT_FAMILY,
                "runtime": mv.ENGINE_QWEN_EDIT_2509,
                "engine": mv.ENGINE_QWEN_EDIT_2509,
                "referenceAssetId": ref_id,
                "referenceLocked": True,
                "referenceKind": "PROP_LOCKED_REFERENCE",
                "referenceFidelityMode": "qwen_edit_2509_ref_edit",
                "taskType": "PROP_ADVANCED_PRIMARY",
                "authority": "primary_prompt",
                "candidateIndex": index,
                "seed": seed,
            },
        }
        job_id = f"failed_prop_cand_{index}"
        status = "failed"
        error = ""
        try:
            job = enqueue_imagegen_job(db, project_id, body)
            job_id = job.id
            status = "queued"
            error = ""
        except Exception as exc:
            logger.exception("Advanced primary Qwen Edit enqueue failed for %s", prop.id)
            error = str(exc) or "Primary Qwen Edit failed to start."
        candidates.append(
            PropCandidate(
                prop_id=prop.id,
                index=index,
                job_id=job_id,
                status=status,  # type: ignore[arg-type]
                source="local",
                family=mv.QWEN_EDIT_FAMILY,
                model=mv.ENGINE_QWEN_EDIT_2509,
                conditioning="reference_conditioned",
                seed=seed,
                error=error,
                progress=0.0 if status == "queued" else None,
                job_stage="queued" if status == "queued" else None,
                job_message="Queued..." if status == "queued" else error or None,
            )
        )
    return candidates


def generate_primary(
    db: Session,
    project_id: str,
    prop_id: str,
    *,
    local_enabled: bool = True,
    api_enabled: bool = False,
    local_family: str = "",
    api_model: str = "",
    candidate_count: int = 4,
    generator_sources: dict[str, Any] | None = None,
) -> PropEntity:
    prop = require_owned_prop(db, project_id, prop_id)
    if prop.mode != "advanced":
        raise PropCreatorError("Switch prop mode to advanced before primary generate.", 409)
    compiled = _compile_primary_prompt(prop)
    has_reference = bool((prop.reference_asset_id or "").strip())
    persisted = persist_generator_selection(
        local_enabled=local_enabled,
        api_enabled=api_enabled,
        local_family=local_family,
        api_model=api_model,
        generator_sources=generator_sources,
    )
    from ..spatial_map.ers_contracts import GeneratorSourceSelection

    prop.generator = GeneratorSourceSelection.model_validate(persisted)
    # Locked reference: force Qwen Edit 2509 (same as angles). Never qwen2512 edit /
    # silent zimage.ref_edit â€” that path refuses and left Venture primary stuck.
    if has_reference:
        # Local Qwen Edit 2509 only (assert inside enqueue). No API/zimage silent substitute.
        prop.candidates = _enqueue_advanced_primary_ref_edit(
            db,
            project_id,
            prop,
            compiled,
            candidate_count=candidate_count,
        )
    else:
        plans = build_prop_candidate_plans(
            local_enabled=local_enabled,
            api_enabled=api_enabled,
            local_family=local_family,
            api_model=api_model,
            has_reference=False,
            candidate_count=candidate_count,
            generator_sources=generator_sources,
        )
        prop.candidates = _enqueue_plans(db, project_id, prop, compiled, plans)
    prop.primary_phase = "generating"
    save_prop_entity(db, project_id, prop)
    return prop


def approve_primary(
    db: Session,
    project_id: str,
    prop_id: str,
    *,
    candidate_id: str = "",
    asset_id: str = "",
) -> PropEntity:
    """Primary Approve gate before any angle fan-out. Does not compose final multi-angle PRS yet."""
    prop = require_owned_prop(db, project_id, prop_id)
    if prop.mode != "advanced":
        raise PropCreatorError("Switch prop mode to advanced before primary approve.", 409)
    aid = (asset_id or "").strip()
    if candidate_id:
        candidate = next((c for c in prop.candidates if c.id == candidate_id), None)
        if candidate is None:
            raise PropCreatorError("Candidate not found.")
        if not (candidate.asset_id or "").strip():
            raise PropCreatorError("That look is not ready yet.")
        aid = candidate.asset_id
    if not aid:
        aid = valid_primary_candidate_asset_id(prop)
    if not aid:
        raise PropCreatorError("Provide candidate_id or asset_id to approve primary.")
    prev = prop.primary_approved_asset_id
    if prev and prev != aid:
        _set_asset_approval(db, project_id, prev, approved=False)
    prop.primary_approved_asset_id = aid
    prop.primary_phase = "approved"
    # Bind visual identity early so %Prop can resolve; multi-angle PRS compose is later.
    prop.approved_asset_id = aid
    prop.library_asset_id = aid
    _set_asset_approval(db, project_id, aid, approved=True)
    # Keep uploaded views on the same Prop. Reset generated angles seeded from
    # a previous primary so they cannot silently keep the old identity.
    kept: dict[str, Any] = {}
    for key, slot in mv.ensure_angles_map(prop.angles, hero_optional=prop.hero_optional).items():
        src = str(getattr(slot, "source", "") or "").strip().lower()
        if src == SOURCE_UPLOADED and (slot.asset_id or "").strip():
            if prev and prev != aid:
                slot.approved = False
                slot.status = "complete"
                slot.error = ""
            kept[key] = slot
    prop.angles = mv.ensure_angles_map(kept, hero_optional=prop.hero_optional)
    save_prop_entity(db, project_id, prop)
    return prop


def _require_primary_gate(prop: PropEntity) -> str:
    if prop.mode != "advanced":
        raise PropCreatorError("Advanced mode required for angle generation.", 409)
    if prop.primary_phase != "approved" or not (prop.primary_approved_asset_id or "").strip():
        raise PropCreatorError(
            "Approve the primary design still before generating angles.",
            409,
        )
    return str(prop.primary_approved_asset_id).strip()


def _enqueue_prop_angle_job(
    db: Session,
    project_id: str,
    prop: PropEntity,
    angle: str,
    *,
    primary_asset_id: str,
    angle_session: dict | None = None,
):
    from ..storyboard_jobs import enqueue_imagegen_job
    from ..workflows.qwen_image_edit_2509 import (
        QWEN_EDIT_2509_CHARACTER_ANGLE_SIZE,
        QWEN_EDIT_2509_DEFAULT_CFG,
        QWEN_EDIT_2509_DEFAULT_STEPS,
    )

    mv.assert_can_generate()
    name = (prop.display_label or prop.tag or "prop").strip()
    brief = (prop.primary_prompt or "").strip()[:400]
    seed = uuid.uuid4().int % 2_147_483_647
    size = QWEN_EDIT_2509_CHARACTER_ANGLE_SIZE
    prompt = mv.angle_prompt(angle, prop_name=name, identity_brief=brief)
    body: dict[str, Any] = {
        "prompt": prompt,
        "negative_prompt": mv.PROP_ANGLE_NEGATIVE,
        "width": size,
        "height": size,
        "modelFamilyPreference": mv.QWEN_EDIT_FAMILY,
        "lockModelFamily": True,
        "seed": seed,
        "steps": QWEN_EDIT_2509_DEFAULT_STEPS,
        "cfg": QWEN_EDIT_2509_DEFAULT_CFG,
        "denoise": 0.72,
        "source_asset_id": primary_asset_id,
        "tag": f"prop_{prop.tag or prop.id[:8]}_{angle}",
        "purpose": "project_prop_angle",
        "source": "local",
        "providerPreference": "local",
        "forceWorkflowKey": mv.QWEN_EDIT_WORKFLOW_KEY,
        "allow_force_workflow_key": True,
        # qwen_edit_2509.edit is Draft in certified-registry â€” Character angles set allow_draft.
        "allowDraft": True,
        "allow_draft": True,
        "creativeContext": {
            "objective": "project_prop_angle",
            "propId": prop.id,
            "angle": angle,
            "cameraRole": mv.CAMERA_ROLES.get(angle, angle.upper()),
            "workflowKey": mv.QWEN_EDIT_WORKFLOW_KEY,
            "modelFamily": mv.QWEN_EDIT_FAMILY,
            "runtime": mv.ENGINE_QWEN_EDIT_2509,
            "engine": mv.ENGINE_QWEN_EDIT_2509,
            "referenceAssetId": primary_asset_id,
            "sourcePrimaryAssetId": primary_asset_id,
            "referenceKind": "PROP_PRIMARY_IDENTITY",
            "taskType": "PROP_ADVANCED_ANGLE",
            "authority": "primary_prompt",
            "seed": seed,
            # Phase 5: sequential session — only view prompt/camera changes across angles.
            "angleSessionId": (angle_session or {}).get("sessionId"),
            "angleSessionSeq": (angle_session or {}).get("sessionSeq"),
            "maxInFlight": (angle_session or {}).get("maxInFlight", 1),
            "onlyPromptChangesBetweenAngles": True,
        },
    }
    job = enqueue_imagegen_job(db, project_id, body)
    return job, seed


def generate_angle(
    db: Session,
    project_id: str,
    prop_id: str,
    angle: str,
    *,
    regenerate: bool = False,
) -> PropEntity:
    angle = (angle or "").strip().lower()
    if angle not in mv.PROP_ANGLE_KEYS:
        raise PropCreatorError(f"Unknown prop angle: {angle}")
    prop = require_owned_prop(db, project_id, prop_id)
    primary_id = _require_primary_gate(prop)
    prop.angles = mv.ensure_angles_map(prop.angles, hero_optional=prop.hero_optional)
    slot = prop.angles[angle]
    if slot.approved and not regenerate:
        raise PropCreatorError(
            f"{angle} is already approved. Use regenerate to replace it.",
            409,
        )
    # Phase 5: bind sequential angle session before enqueue (maxInFlight=1).
    from ..image_runtime.prop_angle_session import begin_angle, ensure_session, get_session

    sess_meta = ensure_session(prop.id, primary_id)
    sess_snap = {
        "sessionId": sess_meta.session_id,
        "sessionSeq": sess_meta.seq + 1,  # provisional; begin_angle bumps after job id
        "maxInFlight": 1,
    }
    # Soft single-flight at enqueue: reject if another angle already in-flight for this prop.
    if sess_meta.inflight_job_id:
        raise PropCreatorError(
            f"Prop Advanced angle session busy ({sess_meta.inflight_angle}). "
            f"Sequential maxInFlight=1 — wait or cancel before starting another angle.",
            409,
        )
    try:
        job, seed = _enqueue_prop_angle_job(
            db,
            project_id,
            prop,
            angle,
            primary_asset_id=primary_id,
            angle_session=sess_snap,
        )
        sess_snap = begin_angle(
            prop_id=prop.id,
            primary_asset_id=primary_id,
            angle=angle,
            job_id=job.id,
        )
        # Refresh creativeContext on params if present (best-effort stamp).
        try:
            import json as _json
            params = _json.loads(job.params_json or "{}")
            ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
            ctx["angleSessionId"] = sess_snap.get("sessionId")
            ctx["angleSessionSeq"] = sess_snap.get("sessionSeq")
            ctx["maxInFlight"] = sess_snap.get("maxInFlight", 1)
            params["creativeContext"] = ctx
            job.params_json = _json.dumps(params)
            db.add(job)
            db.commit()
        except Exception:
            logger.debug("angle session params stamp skipped", exc_info=True)
    except PropCreatorError:
        raise
    except Exception as exc:
        # Re-raise FastAPI HTTPException from assert_can_generate unchanged.
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            raise
        logger.exception("Prop angle enqueue failed for %s/%s", prop_id, angle)
        raise PropCreatorError(str(exc) or "Angle generation failed to start.") from exc

    slot.status = "generating" if getattr(job, "comfy_prompt_id", None) else "queued"
    slot.job_id = job.id
    slot.seed = seed
    slot.asset_id = None
    slot.approved = False
    slot.error = ""
    slot.source_primary_asset_id = primary_id
    slot.engine = mv.PRODUCTION_ENGINE
    slot.workflow_key = mv.QWEN_EDIT_WORKFLOW_KEY
    slot.progress = None
    slot.source = SOURCE_GENERATED
    prop.angles[angle] = slot
    save_prop_entity(db, project_id, prop)
    return prop


def approve_angle(
    db: Session,
    project_id: str,
    prop_id: str,
    angle: str,
    *,
    approved: bool = True,
) -> PropEntity:
    angle = (angle or "").strip().lower()
    if angle not in mv.PROP_ANGLE_KEYS:
        raise PropCreatorError(f"Unknown prop angle: {angle}")
    prop = require_owned_prop(db, project_id, prop_id)
    if prop.mode != "advanced":
        raise PropCreatorError("Advanced mode required for angle approval.", 409)
    # Additional views approve independently. Primary is required for identity,
    # not for locking an optional uploaded/generated card.
    prop.angles = mv.ensure_angles_map(prop.angles, hero_optional=prop.hero_optional)
    hydrate_angles(db, project_id, prop)
    slot = prop.angles[angle]
    if approved:
        # Root cause fix: approve any angle that has a real asset (not only status==complete).
        # Hydrate races could leave status as generating/queued briefly while asset_id is set.
        if not (slot.asset_id or "").strip():
            raise PropCreatorError(f"{angle} image is not ready to approve.", 409)
        slot.approved = True
        slot.status = "approved"
        slot.error = ""
        _set_asset_approval(db, project_id, slot.asset_id, approved=True)
    else:
        slot.approved = False
        if slot.asset_id:
            _set_asset_approval(db, project_id, slot.asset_id, approved=False)
        slot.asset_id = None
        slot.status = "idle"
        slot.job_id = None
        slot.error = ""
        slot.source = None
    prop.angles[angle] = slot
    save_prop_entity(db, project_id, prop)
    return prop


def adopt_angle_from_asset(
    db: Session,
    project_id: str,
    prop_id: str,
    angle: str,
    asset_id: str,
    *,
    source_type: str = SOURCE_UPLOADED,
) -> PropEntity:
    """Library / uploaded picture becomes an Advanced angle candidate. Not auto-approved."""
    from ..creator_scope.service import resolve_readable_asset
    from ..db import Asset as AssetRow

    angle = (angle or "").strip().lower()
    if angle not in mv.PROP_ANGLE_KEYS:
        raise PropCreatorError(f"Unknown prop angle: {angle}")
    prop = require_owned_prop(db, project_id, prop_id)
    if prop.mode != "advanced":
        raise PropCreatorError("Switch prop mode to advanced before uploading views.", 409)
    aid = (asset_id or "").strip()
    asset = db.get(AssetRow, aid) if aid else None
    if asset is None:
        asset = resolve_readable_asset(db, project_id, aid)
    if asset is None:
        raise PropCreatorError("That picture is not in this project's Library.", 404)
    source = SOURCE_UPLOADED if str(source_type or "").strip().lower() in {"upload", "uploaded", SOURCE_UPLOADED} else SOURCE_UPLOADED
    stamp_prop_view_asset(
        db,
        asset,
        project_id=str(asset.project_id or project_id),
        prop_id=prop.id,
        prop_name=prop.display_label or prop.tag or "Prop",
        view=angle,
        source=source,
    )
    prop.angles = mv.ensure_angles_map(prop.angles, hero_optional=prop.hero_optional)
    slot = prop.angles[angle]
    slot.status = "complete"
    slot.asset_id = asset.id
    slot.approved = False
    slot.job_id = None
    slot.error = ""
    slot.source = source
    slot.progress = None
    prop.angles[angle] = slot
    if prop.advanced_sheet_status == "complete":
        prop.advanced_sheet_status = "idle"
        prop.advanced_sheet_asset_id = None
        prop.advanced_sheet_error = ""
    save_prop_entity(db, project_id, prop)
    return prop


def upload_angle_from_bytes(
    db: Session,
    project_id: str,
    prop_id: str,
    angle: str,
    *,
    data: bytes,
    filename: str = "",
    content_type: str = "",
) -> PropEntity:
    angle = (angle or "").strip().lower()
    if angle not in mv.PROP_ANGLE_KEYS:
        raise PropCreatorError(f"Unknown prop angle: {angle}")
    prop = require_owned_prop(db, project_id, prop_id)
    if prop.mode != "advanced":
        raise PropCreatorError("Switch prop mode to advanced before uploading views.", 409)
    asset = write_prop_image_asset(
        db,
        project_id=project_id,
        prop_id=prop.id,
        prop_name=prop.display_label or prop.tag or "Prop",
        view=angle,
        data=data,
        filename=filename,
        content_type=content_type,
        source=SOURCE_UPLOADED,
    )
    return adopt_angle_from_asset(
        db,
        project_id,
        prop_id,
        angle,
        asset.id,
        source_type=SOURCE_UPLOADED,
    )


def adopt_primary_from_asset(
    db: Session,
    project_id: str,
    prop_id: str,
    asset_id: str,
    *,
    source_type: str = SOURCE_UPLOADED,
) -> PropEntity:
    from ..creator_scope.service import resolve_readable_asset
    from ..db import Asset as AssetRow
    from ..spatial_map.ers_contracts import PropCandidate

    prop = require_owned_prop(db, project_id, prop_id)
    if prop.mode != "advanced":
        raise PropCreatorError("Switch prop mode to advanced before uploading primary.", 409)
    aid = (asset_id or "").strip()
    asset = db.get(AssetRow, aid) if aid else None
    if asset is None:
        asset = resolve_readable_asset(db, project_id, aid)
    if asset is None:
        raise PropCreatorError("That picture is not in this project's Library.", 404)
    source = SOURCE_UPLOADED if str(source_type or "").strip().lower() in {"upload", "uploaded", SOURCE_UPLOADED} else SOURCE_UPLOADED
    stamp_prop_view_asset(
        db,
        asset,
        project_id=str(asset.project_id or project_id),
        prop_id=prop.id,
        prop_name=prop.display_label or prop.tag or "Prop",
        view="primary",
        source=source,
    )
    next_index = len(prop.candidates or [])
    candidate = PropCandidate(
        id=str(uuid.uuid4()),
        prop_id=prop.id,
        index=next_index,
        job_id="",
        asset_id=asset.id,
        status="complete",
        source="local",
        origin=source,
        family="upload",
        model="uploaded",
        provenance_label="Uploaded",
        take_label=f"Uploaded primary {next_index + 1}",
        conditioning="description_guided",
    )
    prop.candidates = list(prop.candidates or []) + [candidate]
    if prop.primary_phase != "approved":
        prop.primary_phase = "review"
    save_prop_entity(db, project_id, prop)
    return prop


def upload_primary_from_bytes(
    db: Session,
    project_id: str,
    prop_id: str,
    *,
    data: bytes,
    filename: str = "",
    content_type: str = "",
) -> PropEntity:
    """Advanced Primary upload: Library candidate, not auto-approved."""
    prop = require_owned_prop(db, project_id, prop_id)
    if prop.mode != "advanced":
        raise PropCreatorError("Switch prop mode to advanced before uploading primary.", 409)
    asset = write_prop_image_asset(
        db,
        project_id=project_id,
        prop_id=prop.id,
        prop_name=prop.display_label or prop.tag or "Prop",
        view="primary",
        data=data,
        filename=filename,
        content_type=content_type,
        source=SOURCE_UPLOADED,
    )
    return adopt_primary_from_asset(
        db, project_id, prop_id, asset.id, source_type=SOURCE_UPLOADED
    )


def hydrate_angles(db: Session, project_id: str, prop: PropEntity) -> PropEntity:
    """Sync angle job statuses into PropEntity.angles (same honesty as candidate hydrate)."""
    if prop.mode != "advanced":
        return prop
    prop.angles = mv.ensure_angles_map(prop.angles, hero_optional=prop.hero_optional)
    changed = False
    for key, slot in prop.angles.items():
        if slot.status in {"complete", "failed", "approved", "idle"} and (
            slot.asset_id or slot.status in {"idle", "approved", "failed"}
        ):
            if slot.status == "approved" or (slot.status in {"complete", "failed"} and slot.asset_id):
                continue
            if slot.status == "idle":
                continue
            if slot.status == "failed" and not slot.job_id:
                continue
        job_id = (slot.job_id or "").strip()
        if not job_id:
            continue
        job = db.get(Job, job_id)
        if job is None or job.project_id != prop.project_id:
            slot.status = "failed"
            slot.error = slot.error or "Angle job missing."
            changed = True
            continue
        st = (job.status or "").lower()
        if st in {"complete", "done", "succeeded", "success"}:
            from .service import _job_asset_id
            from ..db import Asset as AssetRow

            aid = _job_asset_id(job)
            if aid:
                slot.asset_id = aid
                slot.status = "complete"
                slot.error = ""
                if not (slot.source or "").strip():
                    slot.source = SOURCE_GENERATED
                if isinstance(getattr(job, "progress", None), (int, float)):
                    slot.progress = float(job.progress)
                asset = db.get(AssetRow, aid)
                if asset is not None:
                    stamp_prop_view_asset(
                        db,
                        asset,
                        project_id=str(asset.project_id or prop.project_id),
                        prop_id=prop.id,
                        prop_name=prop.display_label or prop.tag or "Prop",
                        view=key,
                        source=slot.source or SOURCE_GENERATED,
                    )
                changed = True
            else:
                slot.status = "generating"
                changed = True
        elif st in {"failed", "error", "cancelled"}:
            slot.status = "failed"
            slot.error = job.message or slot.error or "Angle generation failed."
            changed = True
        elif st in {"running", "generating", "processing"}:
            if slot.status != "generating":
                slot.status = "generating"
                changed = True
            if isinstance(getattr(job, "progress", None), (int, float)):
                slot.progress = float(job.progress)
                changed = True
        else:
            if slot.status not in {"queued", "generating"}:
                slot.status = "queued"
                changed = True
        prop.angles[key] = slot
    if changed:
        save_prop_entity(db, project_id, prop)
    return prop


def sync_advanced_on_get(db: Session, project_id: str, prop: PropEntity) -> PropEntity:
    """Called from get_prop path â€” hydrate candidates + advanced angles.

    Clears stuck primary_phase=generating when every candidate is terminal
    (complete/failed) so the UI never parks on a generating/Waiting state after
    Comfy jobs are done (including failed/null-progress terminals).
    """
    _sync_candidates(db, project_id, prop)
    if prop.mode == "advanced":
        if prop.primary_phase == "generating":
            cands = list(prop.candidates or [])
            if cands:
                any_ready = any(
                    c.status == "complete" and bool((c.asset_id or "").strip()) for c in cands
                )
                all_terminal = all(c.status in {"complete", "failed"} for c in cands)
                if any_ready:
                    prop.primary_phase = "review"
                    save_prop_entity(db, project_id, prop)
                elif all_terminal:
                    # All failed / complete-without-asset â€” never leave generating forever.
                    prop.primary_phase = "draft"
                    save_prop_entity(db, project_id, prop)
        hydrate_angles(db, project_id, prop)
    return prop



def _resolve_prop_asset_path(db: Session, project_id: str, prop: PropEntity, asset_id: str):
    from ..db import Asset
    from .prs_compose import _asset_path

    aid = (asset_id or "").strip()
    if not aid:
        return None
    asset = db.get(Asset, aid)
    if asset is None:
        from ..creator_scope.service import resolve_readable_asset

        asset = resolve_readable_asset(db, project_id, aid)
    if asset is None or str(asset.project_id or "") not in {project_id, prop.project_id}:
        return None
    return _asset_path(asset)


def _approved_angle_paths(
    db: Session, project_id: str, prop: PropEntity
) -> list[tuple[str, Path]]:
    """Primary first, then any approved optional views in canonical order. Skip missing."""
    from pathlib import Path as _P

    paths: list[tuple[str, _P]] = []
    primary_id = approved_primary_asset_id(prop)
    if not primary_id:
        raise PropCreatorError(
            "Approve Primary before generating the Prop Reference Sheet. Additional views are optional.",
            409,
        )
    primary_path = _resolve_prop_asset_path(db, project_id, prop, primary_id)
    if primary_path is None:
        raise PropCreatorError("Approved Primary image is missing from the Library.", 409)
    paths.append(("primary", primary_path))
    for key in OPTIONAL_VIEWS:
        slot = prop.angles.get(key) if prop.angles else None
        if slot is None or not slot.approved or not (slot.asset_id or "").strip():
            continue
        path = _resolve_prop_asset_path(db, project_id, prop, str(slot.asset_id).strip())
        if path is None:
            continue
        paths.append((key, path))
    return paths


def _sheet_cancel_check(db: Session, project_id: str, prop: PropEntity) -> None:
    """Honor concurrent cancel via in-process mark + DB reload of cancel_requested/status."""
    fresh = load_prop_entity_by_id(db, project_id, prop.id)
    if fresh is None:
        raise PropCreatorError("Prop not found during Advanced Prop Reference Sheet generation.", 404)
    mem = _sheet_cancel_marked(prop.id)
    cancelled = mem or bool(fresh.advanced_sheet_cancel_requested) or (
        str(fresh.advanced_sheet_status or "").strip().lower() == "cancelled"
    )
    if cancelled:
        _sheet_cancel_clear(prop.id)
        prop.advanced_sheet_status = "cancelled"
        prop.advanced_sheet_progress = None
        prop.advanced_sheet_error = "Cancelled"
        prop.advanced_sheet_cancel_requested = False
        raise PropCreatorError("Advanced prop reference sheet cancelled.", 409)
    prop.advanced_sheet_cancel_requested = bool(fresh.advanced_sheet_cancel_requested)


def _save_sheet_progress(db: Session, project_id: str, prop: PropEntity, progress: float) -> None:
    """Persist mid-flight progress without clobbering a concurrent cancel."""
    _sheet_cancel_check(db, project_id, prop)
    fresh = load_prop_entity_by_id(db, project_id, prop.id)
    if fresh is None:
        raise PropCreatorError("Prop not found during Advanced Prop Reference Sheet generation.", 404)
    if _sheet_cancel_marked(prop.id) or bool(fresh.advanced_sheet_cancel_requested) or (
        str(fresh.advanced_sheet_status or "").strip().lower() == "cancelled"
    ):
        _sheet_cancel_clear(prop.id)
        prop.advanced_sheet_status = "cancelled"
        prop.advanced_sheet_progress = None
        prop.advanced_sheet_error = "Cancelled"
        prop.advanced_sheet_cancel_requested = False
        save_prop_entity(db, project_id, prop)
        raise PropCreatorError("Advanced prop reference sheet cancelled.", 409)
    fresh.advanced_sheet_status = "generating"
    fresh.advanced_sheet_progress = progress
    fresh.advanced_sheet_error = ""
    save_prop_entity(db, project_id, fresh)
    prop.advanced_sheet_status = "generating"
    prop.advanced_sheet_progress = progress
    # Re-check after save in case cancel won the write race.
    _sheet_cancel_check(db, project_id, prop)


def _bind_advanced_prs_authority(prop: PropEntity, sheet_asset_id: str) -> None:
    """Converge official PRS onto Advanced sheet via structured fields only."""
    aid = (sheet_asset_id or "").strip()
    if not aid:
        return
    prop.advanced_sheet_asset_id = aid
    if not str(prop.advanced_sheet_status or "").strip():
        prop.advanced_sheet_status = "complete"


def _execute_advanced_reference_sheet(db: Session, project_id: str, prop_id: str) -> None:
    """In-flight compose with DB-observed cancel + mid-flight progress saves."""
    from .prs_compose import compose_and_ingest_advanced_prs

    prop = get_prop(db, project_id, prop_id)
    try:
        _sheet_cancel_check(db, project_id, prop)
        # Cooperative yield so FE poll / cancel can observe 0.05
        time.sleep(0.25)
        _sheet_cancel_check(db, project_id, prop)

        angle_paths = _approved_angle_paths(db, project_id, prop)
        _save_sheet_progress(db, project_id, prop, 0.35)

        time.sleep(0.25)
        _sheet_cancel_check(db, project_id, prop)

        _save_sheet_progress(db, project_id, prop, 0.55)

        _sheet_cancel_check(db, project_id, prop)
        asset = compose_and_ingest_advanced_prs(db, project_id, prop, angle_paths)
        _sheet_cancel_check(db, project_id, prop)

        # Finalize only if cancel did not win; never overwrite cancelled with complete.
        fresh = load_prop_entity_by_id(db, project_id, prop.id)
        if fresh is None:
            raise PropCreatorError("Prop not found during Advanced Prop Reference Sheet generation.", 404)
        if _sheet_cancel_marked(prop.id) or bool(fresh.advanced_sheet_cancel_requested) or (
            str(fresh.advanced_sheet_status or "").strip().lower() == "cancelled"
        ):
            _sheet_cancel_clear(prop.id)
            prop.advanced_sheet_status = "cancelled"
            prop.advanced_sheet_progress = None
            prop.advanced_sheet_error = "Cancelled"
            prop.advanced_sheet_cancel_requested = False
            save_prop_entity(db, project_id, prop)
            return

        prop.advanced_sheet_asset_id = asset.id
        prop.advanced_sheet_status = "complete"
        prop.advanced_sheet_progress = 1.0
        prop.advanced_sheet_error = ""
        prop.advanced_sheet_cancel_requested = False
        _bind_advanced_prs_authority(prop, asset.id)
        save_prop_entity(db, project_id, prop)
        _sheet_cancel_clear(prop.id)
    except PropCreatorError as exc:
        if prop.advanced_sheet_status == "cancelled":
            save_prop_entity(db, project_id, prop)
            return
        msg = str(exc) or "Sheet generation failed"
        if "cancelled" in msg.lower():
            prop.advanced_sheet_status = "cancelled"
            prop.advanced_sheet_error = "Cancelled"
        elif (
            "Need all required" in msg
            or "Approve Primary" in msg
            or "Approve primary" in msg
            or "Advanced mode" in msg
            or "already generating" in msg
        ):
            prop.advanced_sheet_status = "idle"
            prop.advanced_sheet_error = msg
        else:
            prop.advanced_sheet_status = "failed"
            prop.advanced_sheet_error = msg
        prop.advanced_sheet_progress = None
        prop.advanced_sheet_cancel_requested = False
        save_prop_entity(db, project_id, prop)
        logger.warning("Advanced PRS job ended with PropCreatorError for %s: %s", prop_id, msg)
    except Exception as exc:
        prop.advanced_sheet_status = "failed"
        prop.advanced_sheet_error = str(exc) or "Sheet generation failed"
        prop.advanced_sheet_progress = None
        prop.advanced_sheet_cancel_requested = False
        save_prop_entity(db, project_id, prop)
        logger.exception("Advanced PRS job failed for %s", prop_id)


def generate_advanced_reference_sheet(
    db: Session, project_id: str, prop_id: str
) -> PropEntity:
    """Start Advanced PRS compose asynchronously; return immediately with generating status.

    Progress (0.05→0.35→0.55→1.0) is saved mid-flight for FE poll. Cancel reloads from DB.
    """
    prop = require_owned_prop(db, project_id, prop_id)
    if prop.mode != "advanced":
        raise PropCreatorError("Advanced mode required for Advanced Prop Reference Sheet.", 409)
    if not identity_ready(prop):
        raise PropCreatorError(
            "Approve Primary before generating the Prop Reference Sheet. Additional views are optional.",
            409,
        )
    if prop.advanced_sheet_status == "generating":
        raise PropCreatorError("Advanced Prop Reference Sheet is already generating.", 409)

    # Primary-only is valid. Optional views are included when already approved.
    _approved_angle_paths(db, project_id, prop)

    _sheet_cancel_clear(prop_id)
    prop.advanced_sheet_cancel_requested = False
    prop.advanced_sheet_status = "generating"
    prop.advanced_sheet_progress = 0.05
    prop.advanced_sheet_error = ""
    save_prop_entity(db, project_id, prop)

    def _runner() -> None:
        from ..db import SessionLocal

        session = SessionLocal()
        try:
            _execute_advanced_reference_sheet(session, project_id, prop_id)
        except Exception:
            logger.exception("Advanced PRS background runner crashed for %s", prop_id)
        finally:
            session.close()

    threading.Thread(
        target=_runner,
        daemon=True,
        name=f"adv-prs-{prop_id[:8]}",
    ).start()
    return prop


def cancel_advanced_reference_sheet(
    db: Session, project_id: str, prop_id: str
) -> PropEntity:
    prop = require_owned_prop(db, project_id, prop_id)
    if prop.advanced_sheet_status != "generating":
        raise PropCreatorError("No Advanced Prop Reference Sheet generation in progress.", 409)
    # In-process mark + DB flag so the async job observes cancel even if a progress save races.
    _sheet_cancel_mark(prop_id)
    prop.advanced_sheet_cancel_requested = True
    prop.advanced_sheet_status = "cancelled"
    prop.advanced_sheet_progress = None
    prop.advanced_sheet_error = "Cancelled"
    save_prop_entity(db, project_id, prop)
    return prop
