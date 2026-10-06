"""Character Creator V2 — JSON-first, one view at a time, Co-Director vision.

Does not enqueue four-view / collage jobs. Reuses CharacterProfile, CRS persist,
JobQueue, and chat_vision. State lives on trait key ``cc_v2`` (same character_id).
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..db import Asset, Job, Project
from .models import CharacterProfileRow, CharacterTraitRow

V2_TRAIT_KEY = "cc_v2"
RETIRED_FOUR_VIEW_LAYOUTS = frozenset({"four_view", "four_panel_2x2", "collage", "contact_sheet"})
RETIRED_FOUR_VIEWS = frozenset({"front_full", "side_full", "back_full", "face_closeup"})


def collapse_retired_required_views(required_views: list[str] | None, layout: str | None) -> list[str] | None:
    """Retired Character Creator four-view default becomes Front only."""
    views = [str(v).strip() for v in (required_views or []) if str(v).strip()]
    if str(layout or "").strip().lower() in RETIRED_FOUR_VIEW_LAYOUTS or set(views) == RETIRED_FOUR_VIEWS:
        return ["front_full"]
    return required_views if required_views is not None else None

VIEWS = ("front", "back", "closeup")
VIEW_ROLES = {
    "front": "hero_identity",
    "back": "full_body_back",
    "closeup": "closeup_front",
}
VIEW_CANONICAL = {
    "front": "front_full",
    "back": "back_full",
    "closeup": "face_closeup",
}
USER_PROTECTED_FIELDS = frozenset(
    {"name", "description", "visual_description", "visual_style", "gender_presentation", "apparent_age", "height_description"}
)

FRONT_VISION_INSTRUCTIONS = """You are Co-Director inspecting an approved character FRONT photograph.
Return JSON only with keys: face, hair, skin, wardrobe, colors, distinctive, build_as_seen, style_as_seen, notes.
Use only facts visible in the image. Empty string if unknown.
Do not invent personality, backstory, age, height, or relationships.
No markdown."""

BOTH_VISION_INSTRUCTIONS = """You are Co-Director inspecting approved FRONT and BACK character photographs.
Return JSON only with keys: front_confirmed, rear_hair, back_of_wardrobe, rear_silhouette, colors_from_rear, distinctive_rear, notes.
Only evidenced visible facts. Empty string if unknown.
Do not invent personality or overwrite the creator's written name/description.
No markdown."""

CLOSEUP_VISION_INSTRUCTIONS = """You are Co-Director inspecting an approved character CLOSE-UP.
Return JSON only with keys: face, eyes, skin, hair_front, distinctive, notes.
Only evidenced facial/detail facts. Empty string if unknown. No personality. No markdown."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def empty_view() -> dict[str, Any]:
    return {
        "status": "idle",
        "jobId": None,
        "promptId": None,
        "assetId": None,
        "workflowKey": None,
        "generator": None,
        "error": None,
        "approved": False,
        "approvedAt": None,
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def empty_state() -> dict[str, Any]:
    from .cc_v3_multiview import empty_enrichment, empty_multiview

    return {
        "schema": "cc_v3",
        "phase": "DRAFT",
        "jsonRevision": 1,
        "productionReady": False,
        "visualLock": {"status": "none", "facts": {}, "error": None, "at": None},
        "revision2": {"status": "none", "facts": {}, "error": None, "at": None},
        "closeupMerge": {"status": "none", "facts": {}, "error": None, "at": None},
        "views": {name: empty_view() for name in VIEWS},
        "multiView": empty_multiview(),
        "multiviewEnrichment": empty_enrichment(),
        "sheet": {"status": "none", "assetId": None},
        "sheetAssetId": None,
        "activeJobView": None,
        "updatedAt": _now(),
    }


def load_state(db: Session, character_id: str) -> dict[str, Any]:
    from .cc_v3_multiview import empty_enrichment, merge_multiview

    row = (
        db.query(CharacterTraitRow)
        .filter(
            CharacterTraitRow.character_profile_id == character_id,
            CharacterTraitRow.key == V2_TRAIT_KEY,
        )
        .order_by(CharacterTraitRow.id.desc())
        .first()
    )
    if not row or not row.value:
        return empty_state()
    try:
        data = json.loads(row.value)
    except json.JSONDecodeError:
        return empty_state()
    if not isinstance(data, dict):
        return empty_state()
    base = empty_state()
    for key, value in data.items():
        if key in {"views", "multiView", "multiviewEnrichment", "sheet"}:
            continue
        base[key] = value
    views_raw = data.get("views") if isinstance(data.get("views"), dict) else {}
    views: dict[str, Any] = {}
    for name in VIEWS:
        merged = empty_view()
        slot = views_raw.get(name)
        if isinstance(slot, dict):
            merged.update(slot)
        views[name] = merged
    base["views"] = views
    base["multiView"] = merge_multiview(data.get("multiView"))
    enrich = empty_enrichment()
    raw_enrich = data.get("multiviewEnrichment")
    if isinstance(raw_enrich, dict):
        enrich.update(raw_enrich)
    base["multiviewEnrichment"] = enrich
    sheet = _as_dict(data.get("sheet"))
    base["sheet"] = {
        "status": str(sheet.get("status") or ("ready" if data.get("sheetAssetId") else "none")),
        "assetId": sheet.get("assetId") or data.get("sheetAssetId"),
        "layout": sheet.get("layout"),
        "fingerprint": sheet.get("fingerprint"),
        "progress": _as_dict(sheet.get("progress")),
    }
    if base["sheet"].get("assetId"):
        base["sheetAssetId"] = base["sheet"]["assetId"]
    base["jsonRevision"] = _safe_int(base.get("jsonRevision"), 1)
    return base


def save_state(db: Session, profile: CharacterProfileRow, state: dict[str, Any]) -> dict[str, Any]:
    state["updatedAt"] = _now()
    for row in (
        db.query(CharacterTraitRow)
        .filter(
            CharacterTraitRow.character_profile_id == profile.id,
            CharacterTraitRow.key == V2_TRAIT_KEY,
        )
        .all()
    ):
        db.delete(row)
    db.add(
        CharacterTraitRow(
            id=str(uuid.uuid4()),
            character_profile_id=profile.id,
            character_version_id=profile.active_version_id,
            category="character_creator_v2",
            key=V2_TRAIT_KEY,
            value=json.dumps(state, ensure_ascii=False),
            importance="canonical",
            canonical=True,
            provenance="PROPOSED_BY_CHARACTER_CREATOR",
        )
    )
    return state


def _profile(db: Session, project_id: str, character_id: str) -> CharacterProfileRow:
    from .service import require_owned_profile

    return require_owned_profile(db, project_id, character_id)


def _hydrate_view(db: Session, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Hydrate a view or angle slot from its job.

    Accepts ``(db, view)`` or ``(db, project_id, view, name)``.
    """
    project_id = kwargs.get("project_id")
    view = kwargs.get("view")
    name = kwargs.get("name")
    if len(args) == 1 and isinstance(args[0], dict):
        view = args[0]
    elif len(args) >= 2:
        if isinstance(args[0], str):
            project_id = args[0]
        if isinstance(args[1], dict):
            view = args[1]
        if len(args) >= 3:
            name = args[2]
    view = dict(view or {})
    job_id = str(view.get("jobId") or "").strip()
    job = db.get(Job, job_id) if job_id else None
    if job is not None:
        view["status"] = job.status
        view["promptId"] = job.comfy_prompt_id
        if job.status == "queued" and not job.comfy_prompt_id:
            view["status"] = "queued"
        if job.status == "done":
            from .visual_sheet import _job_params

            aid = _job_params(job).get("output_asset_id")
            if aid:
                view["assetId"] = aid
                if not view.get("approved"):
                    view["status"] = "ready"
        elif job.status in {"failed", "error", "cancelled"}:
            view["status"] = "failed"
            view["error"] = job.message or job.status
        elif job.status in {"running", "queued", "starting"}:
            if job.comfy_prompt_id:
                view["status"] = "generating"
            else:
                view["status"] = "queued"
    if project_id and view.get("assetId"):
        try:
            from .cc_v2_media import resolve_character_asset

            resolved = resolve_character_asset(db, str(project_id), view.get("assetId"))
            if resolved:
                view["assetId"] = resolved["assetId"]
                view["assetUrl"] = resolved["assetUrl"]
        except Exception:
            pass
    try:
        from .cc_v2_progress import map_job_progress

        view["progress"] = map_job_progress(
            job,
            view=str(name or "front"),
            has_output=bool(view.get("assetId")),
            approved=bool(view.get("approved")),
        )
    except Exception:
        pass
    return view


def _compute_phase(state: dict[str, Any]) -> str:
    views = state.get("views") if isinstance(state.get("views"), dict) else {}
    front = views.get("front") if isinstance(views.get("front"), dict) else {}
    lock = state.get("visualLock") if isinstance(state.get("visualLock"), dict) else {}
    rev2 = state.get("revision2") if isinstance(state.get("revision2"), dict) else {}
    closeup = views.get("closeup") if isinstance(views.get("closeup"), dict) else {}
    mv = state.get("multiView") if isinstance(state.get("multiView"), dict) else {}
    sheet = state.get("sheetAssetId") or (_as_dict(state.get("sheet")).get("assetId"))
    if sheet:
        return "SHEET_READY"
    if closeup.get("status") == "generating":
        return "CLOSEUP_GENERATING"
    if str(mv.get("status") or "") in {"generating", "queued", "running"}:
        return "ANGLES_GENERATING"
    if str(rev2.get("status") or "") == "failed":
        return "FAILED"
    if str(rev2.get("status") or "") == "ok":
        return "DETAILS_READY"
    if closeup.get("status") == "ready" and not closeup.get("approved"):
        return "CLOSEUP_READY"
    if front.get("approved") and str(lock.get("status") or "") == "ok":
        return "ACTIVE"
    if front.get("approved") and str(lock.get("status") or "") == "failed":
        return "FAILED"
    if front.get("approved"):
        return "VISION_FRONT"
    if front.get("status") == "generating":
        return "FRONT_GENERATING"
    if front.get("status") == "ready":
        return "FRONT_READY"
    if front.get("status") == "failed":
        return "FAILED"
    return "DRAFT"


def get_status(db: Session, project_id: str, character_id: str) -> dict[str, Any]:
    from .cc_v3_multiview import engine_payload, hydrate_multiview, merge_multiview, sheet_gate
    from .service import _require_visible_profile

    profile = _require_visible_profile(db, project_id, character_id)
    state = load_state(db, character_id)
    for name in VIEWS:
        slot = state["views"].get(name) if isinstance(state["views"].get(name), dict) else empty_view()
        state["views"][name] = _hydrate_view(db, project_id, slot, name)
    try:
        hydrate_multiview(db, project_id, state)
    except Exception:
        state["multiView"] = merge_multiview(state.get("multiView"))
    state["phase"] = _compute_phase(state)
    lock_ok = str((state.get("visualLock") or {}).get("status") or "") == "ok"
    front_ok = bool(state["views"]["front"].get("approved") and lock_ok)
    state["productionReady"] = front_ok
    state["atTag"] = f"@{profile.name}" if profile.name else ""
    state["characterId"] = character_id
    state["name"] = profile.name
    state["jsonRevision"] = _safe_int(state.get("jsonRevision"), 1)
    state["schema"] = "cc_v3"
    try:
        from .crs_service import load_persisted_crs

        persisted = load_persisted_crs(db, character_id)
        state["crsRevision"] = _safe_int(persisted.get("crs_revision"), 0)
    except Exception:
        state["crsRevision"] = 0
    state["sheetGate"] = sheet_gate(state, db=db, character_id=character_id)
    state["engine"] = engine_payload()
    if state.get("sheetAssetId"):
        sheet = _as_dict(state.get("sheet"))
        sheet["assetId"] = sheet.get("assetId") or state.get("sheetAssetId")
        sheet["status"] = sheet.get("status") or "ready"
        try:
            from .cc_v2_media import resolve_character_asset

            resolved_sheet = resolve_character_asset(db, project_id, sheet.get("assetId"))
            if resolved_sheet:
                sheet["assetUrl"] = resolved_sheet["assetUrl"]
        except Exception:
            pass
        progress = _as_dict(sheet.get("progress"))
        if not progress.get("percent") and sheet.get("assetId"):
            progress = {"percent": 100, "stage": "ready", "label": "Character Sheet Ready"}
        sheet["progress"] = progress
        state["sheet"] = sheet
    return state


def _active_job_busy(state: dict[str, Any]) -> Optional[str]:
    live = {"generating", "queued", "running", "starting"}
    mv = state.get("multiView") if isinstance(state.get("multiView"), dict) else {}
    if str(mv.get("status") or "") in live:
        return "multiview"
    angles = mv.get("angles") if isinstance(mv.get("angles"), dict) else {}
    for name, slot in angles.items():
        if not isinstance(slot, dict):
            continue
        if str(slot.get("upscaleStatus") or "") in {"upscaling", "generating"}:
            return f"upscale.{name}"
        if str(slot.get("status") or "") in live:
            return "multiview"
    views = state.get("views") if isinstance(state.get("views"), dict) else {}
    for name in ("front", "closeup"):
        slot = views.get(name) if isinstance(views.get(name), dict) else {}
        if str(slot.get("status") or "") in live:
            return name
    return None


def invalidate_after_regenerate(state: dict[str, Any], view: str) -> dict[str, Any]:
    """Remaking Front cannot keep a stale lock, angles, Rev 2, or sheet."""
    if view == "front":
        from .cc_v3_multiview import empty_enrichment, empty_multiview

        state["visualLock"] = {"status": "none", "facts": {}, "error": None, "at": None}
        state["revision2"] = {"status": "none", "facts": {}, "error": None, "at": None}
        state["closeupMerge"] = {"status": "none", "facts": {}, "error": None, "at": None}
        state["sheetAssetId"] = None
        state["sheet"] = {"status": "stale", "assetId": None}
        state["jsonRevision"] = 1
        state["productionReady"] = False
        state["multiView"] = empty_multiview()
        state["multiviewEnrichment"] = empty_enrichment()
        for stale in ("back", "closeup"):
            prior = state["views"].get(stale) if isinstance(state.get("views"), dict) else {}
            if isinstance(prior, dict) and (prior.get("approved") or prior.get("assetId")):
                state["views"][stale] = {
                    **empty_view(),
                    "status": "stale",
                    "assetId": prior.get("assetId"),
                    "error": "Front was remade. Create this view again from the new Front.",
                }
    elif view == "back":
        state["revision2"] = {"status": "none", "facts": {}, "error": None, "at": None}
        state["sheetAssetId"] = None
    return state


def generate_view(
    db: Session,
    project_id: str,
    character_id: str,
    view: str,
    *,
    family: Optional[str] = None,
    visual_style: Optional[str] = None,
) -> dict[str, Any]:
    if view == "back":
        raise _err(
            "BACK_RETIRED",
            "Use Generate Character Angles for Side, 3/4, and Back.",
            409,
        )
    if view not in VIEWS:
        raise _err("INVALID_VIEW", f"Unknown view: {view}")
    profile = _profile(db, project_id, character_id)
    if not db.get(Project, project_id):
        raise _err("NOT_FOUND", "Project not found.", 404)
    state = get_status(db, project_id, character_id)
    busy = _active_job_busy(state)
    if busy:
        if busy == view:
            return state
        raise _err("JOB_ACTIVE", f"Another view is generating ({busy}). One job at a time.", 409)

    lock_ok = str((state.get("visualLock") or {}).get("status") or "") == "ok"
    front_approved = bool(state["views"]["front"].get("approved"))
    if view == "closeup":
        if not front_approved or not lock_ok:
            raise _err(
                "FRONT_LOCK_REQUIRED",
                "Create Close-up only after Front is approved and Co-Director vision lock is ready.",
                409,
            )
        from .closeup_crop import generate_closeup_from_front

        return generate_closeup_from_front(db, project_id, character_id, profile, state)

    from . import service
    from .crs_view_generation import resolve_crs_view_generation_workflow
    from .visual_sheet import _compile_visual_prompt, _enqueue_txt2img, _negative_rules_for_view, _resolve_style_profile

    profile_dump = service.get_profile(db, project_id, character_id).model_dump()
    name = profile_dump.get("name") or "Character"
    char_slug = (profile_dump.get("slug") or name).replace(" ", "_").lower()
    style_profile = _resolve_style_profile(visual_style or profile_dump.get("visual_style") or "")
    references = service.list_references(db, project_id, character_id)
    front_asset = str(state["views"]["front"].get("assetId") or "") or None
    wants_ref = view == "closeup" and bool(front_asset)
    resolved = resolve_crs_view_generation_workflow(
        has_identity_crop=wants_ref,
        requested_family=family,
    )
    workflow_key = str(resolved["workflowKey"])
    fam = str(resolved["family"])
    lineage = None
    try:
        from .visual_sheet import _workflow_lineage

        lineage = _workflow_lineage(workflow_key)
    except Exception:
        lineage = {}
    supports_ref = bool((lineage or {}).get("supportsReferences")) or str(resolved.get("mode") or "") in {
        "img2img",
        "i2i_edit",
    }
    source_asset_id = front_asset if (wants_ref and supports_ref) else None
    if view == "closeup" and not source_asset_id:
        raise _err(
            "CLOSEUP_UNSUPPORTED",
            "This generator cannot bind Front pixels for a reference-conditioned Close-up. Choose a certified reference adapter.",
            409,
        )

    goals = {
        "front": "one person, full body, front-facing, neutral standing pose, centered, simple background, no collage, no text, no second person",
        "back": "the same person as the front reference, full body, viewed from behind, same hair clothing colors and identity, no collage, no second person",
        "closeup": "the same person as the front reference, head-and-shoulders close-up, useful face, same identity, no collage, no second person",
    }
    role = VIEW_ROLES[view]
    vprompt = _compile_visual_prompt(
        profile_dump,
        prompt_goal=goals[view],
        composition={"candidate_index": 0, "viewType": VIEW_CANONICAL[view], "sheetComposition": False},
        references=references,
        role=role,
        extra_negative_constraints=_negative_rules_for_view(role, None),
        style_profile=style_profile,
        reference_locked=bool(source_asset_id),
        sheet_request={},
        model_family=fam,
    )
    lock_facts = (state.get("visualLock") or {}).get("facts") or {}
    prompt_text = str(getattr(vprompt, "prompt", "") or "")
    negative = str(getattr(vprompt, "negative_prompt", "") or "")
    if view != "front" and isinstance(lock_facts, dict) and lock_facts:
        brief = ", ".join(f"{k}: {v}" for k, v in lock_facts.items() if str(v).strip())
        if brief:
            prompt_text = f"{prompt_text}\nIdentity lock from approved front: {brief}"

    invalidate_after_regenerate(state, view)

    job = _enqueue_txt2img(
        db,
        project_id,
        character_id=character_id,
        prompt=prompt_text,
        negative_prompt=negative,
        tag=f"{char_slug}_v2_{view}",
        role=role,
        model_family_preference=fam,
        source_asset_id=source_asset_id,
        denoise=0.35 if source_asset_id else None,
        seed=None,
        force_workflow_key=workflow_key,
        provider_kind="local",
        sheet_layout="crs_view_generation",
        prompt_metadata={
            "ccV2": True,
            "characterId": character_id,
            "view": view,
            "workflowKey": workflow_key,
            "modelFamily": fam,
            "referenceAssetId": source_asset_id,
            "referenceKind": "IDENTITY_REFERENCE" if source_asset_id else None,
            "taskType": "CRS_VIEW_GENERATION",
            "fourViewSingleOutput": False,
            "requiredViews": [VIEW_CANONICAL[view]],
            "visualLock": lock_facts if view != "front" else {},
        },
    )
    if job.status in {"running", "queued", "starting"} and not job.comfy_prompt_id and job.status == "running":
        # Bind-or-fail: never claim running without prompt id.
        job.status = "queued"
    state["views"][view] = {
        **empty_view(),
        "status": "generating" if job.comfy_prompt_id else "queued",
        "jobId": job.id,
        "promptId": job.comfy_prompt_id,
        "workflowKey": workflow_key,
        "generator": fam,
        "approved": False,
    }
    state["activeJobView"] = view
    save_state(db, profile, state)
    db.commit()
    return get_status(db, project_id, character_id)


def _asset_path(db: Session, project_id: str, asset_id: str) -> Path:
    asset = db.get(Asset, asset_id)
    if not asset or asset.project_id != project_id or not asset.path:
        raise _err("NOT_FOUND", "View asset not found.", 404)
    path = Path(asset.path)
    if not path.is_file():
        raise _err("NOT_FOUND", "View image file is missing.", 404)
    return path


def _parse_vision_json(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return {"notes": raw[:2000]}
    try:
        data = json.loads(raw[start : end + 1])
        return data if isinstance(data, dict) else {"notes": raw[:2000]}
    except json.JSONDecodeError:
        return {"notes": raw[:2000]}


async def _run_vision(paths: list[Path], instructions: str) -> dict[str, Any]:
    from ..codirector.vision.vision_review import chat_vision

    for path in paths:
        if not Path(path).is_file():
            return {"ok": False, "error": "image_unreadable", "facts": {}}
    response = await chat_vision(instructions=instructions, image_paths=paths)
    if not response.get("ok"):
        err = str(response.get("error") or response.get("reason") or "vlm_error")
        return {
            "ok": False,
            "error": err,
            "httpStatus": response.get("httpStatus"),
            "providerCode": response.get("providerCode"),
            "provider": response.get("provider"),
            "model": response.get("model"),
            "facts": {},
        }
    return {
        "ok": True,
        "error": None,
        "facts": _parse_vision_json(str(response.get("output") or "")),
        "provider": response.get("provider") or "fal",
        "model": response.get("model"),
    }


def _merge_evidenced(profile: CharacterProfileRow, facts: dict[str, Any]) -> None:
    """Fill blank visual fields only. Never overwrite user-authored text."""
    mapping = {
        "hair": ("hair_json", "canonical_style"),
        "skin": ("skin_json", "skin_tone"),
    }
    hair = facts.get("hair") or facts.get("rear_hair") or facts.get("hair_front")
    if hair and not (json.loads(profile.hair_json or "{}") or {}).get("canonical_style"):
        blob = json.loads(profile.hair_json or "{}")
        if not blob.get("canonical_style"):
            blob["canonical_style"] = str(hair)[:240]
            profile.hair_json = json.dumps(blob, ensure_ascii=False)
    skin = facts.get("skin")
    if skin:
        blob = json.loads(profile.skin_json or "{}")
        if not blob.get("skin_tone"):
            blob["skin_tone"] = str(skin)[:240]
            profile.skin_json = json.dumps(blob, ensure_ascii=False)
    _ = mapping


async def approve_view(
    db: Session,
    project_id: str,
    character_id: str,
    view: str,
    *,
    owner_confirmed: bool = True,
) -> dict[str, Any]:
    if view not in VIEWS:
        raise _err("INVALID_VIEW", f"Unknown view: {view}")
    profile = _profile(db, project_id, character_id)
    state = get_status(db, project_id, character_id)
    slot = state["views"][view]
    asset_id = str(slot.get("assetId") or "").strip()
    if not asset_id:
        raise _err("VIEW_NOT_READY", f"{view} image is not ready to approve.", 409)
    if slot.get("approved") and view == "front" and str((state.get("visualLock") or {}).get("status")) == "ok":
        return state
    if slot.get("approved") and view == "back" and str((state.get("revision2") or {}).get("status")) == "ok":
        return state

    from . import service

    role = VIEW_ROLES[view]
    if view == "front":
        service.approve_character_candidate(
            db,
            project_id,
            character_id,
            asset_id=asset_id,
            reference_role="hero_identity",
            source_type="generation",
            notes="V2 approved front",
            owner_confirmed=owner_confirmed,
        )
    else:
        existing = service.resolve_approved_reference(db, character_id, role)
        if existing != asset_id:
            from .schemas import ReferenceAttach

            service.attach_reference(
                db,
                project_id,
                character_id,
                ReferenceAttach(
                    asset_id=asset_id,
                    reference_role=role,
                    source_type="generation",
                    canonical=True,
                    approval_status="approved",
                    notes=f"V2 approved {view}",
                ),
            )

    state["views"][view]["approved"] = True
    state["views"][view]["approvedAt"] = _now()
    state["views"][view]["status"] = "approved"

    if view == "front":
        state["visualLock"] = {"status": "running", "facts": {}, "error": None, "at": _now()}
        save_state(db, profile, state)
        db.commit()
        result = await _run_vision([_asset_path(db, project_id, asset_id)], FRONT_VISION_INSTRUCTIONS)
        state = load_state(db, character_id)
        if result.get("ok"):
            state["visualLock"] = {
                "status": "ok",
                "facts": result.get("facts") or {},
                "error": None,
                "at": _now(),
                "provenance": "CANONICAL_FROM_USER_APPROVAL",
                "provider": result.get("provider") or "fal",
                "model": result.get("model"),
            }
            state["productionReady"] = True
            _merge_evidenced(profile, result.get("facts") or {})
        else:
            state["visualLock"] = {
                "status": "failed",
                "facts": {},
                "error": result.get("error") or "vision_failed",
                "httpStatus": result.get("httpStatus"),
                "providerCode": result.get("providerCode"),
                "provider": result.get("provider") or "fal",
                "model": result.get("model"),
                "at": _now(),
            }
        save_state(db, profile, state)
        db.commit()
        return get_status(db, project_id, character_id)

    if view == "back":
        front_id = str(state["views"]["front"].get("assetId") or "")
        state["revision2"] = {"status": "running", "facts": {}, "error": None, "at": _now()}
        save_state(db, profile, state)
        db.commit()
        result = await _run_vision(
            [_asset_path(db, project_id, front_id), _asset_path(db, project_id, asset_id)],
            BOTH_VISION_INSTRUCTIONS,
        )
        state = load_state(db, character_id)
        if result.get("ok"):
            facts = result.get("facts") or {}
            state["revision2"] = {
                "status": "ok",
                "facts": facts,
                "error": None,
                "at": _now(),
                "provenance": "CANONICAL_FROM_USER_APPROVAL",
            }
            state["jsonRevision"] = 2
            _merge_evidenced(profile, facts)
            from .crs_service import persist_crs_in_session
            from .prompt_package import generate_prompt_package

            persist_crs_in_session(db, profile, asset_id=front_id)
            from .crs_service import merge_persisted_crs

            merge_persisted_crs(
                db,
                profile,
                {
                    "json_revision": 2,
                    "approved_front_asset_id": front_id,
                    "approved_back_asset_id": asset_id,
                    "coverage": "multi_view",
                    "visual_lock_ok": True,
                },
            )
            pkg = generate_prompt_package(
                service.get_profile(db, project_id, character_id).model_dump(),
                character_version_id=profile.active_version_id or "",
            )
            profile.prompt_package_json = json.dumps(pkg, ensure_ascii=False)
        else:
            state["revision2"] = {
                "status": "failed",
                "facts": {},
                "error": result.get("error") or "vision_failed",
                "at": _now(),
            }
        save_state(db, profile, state)
        db.commit()
        return get_status(db, project_id, character_id)

    # closeup — same-file addendum, not revision 2
    state["closeupMerge"] = {"status": "running", "facts": {}, "error": None, "at": _now()}
    save_state(db, profile, state)
    db.commit()
    result = await _run_vision([_asset_path(db, project_id, asset_id)], CLOSEUP_VISION_INSTRUCTIONS)
    state = load_state(db, character_id)
    if result.get("ok"):
        state["closeupMerge"] = {
            "status": "ok",
            "facts": result.get("facts") or {},
            "error": None,
            "at": _now(),
        }
        _merge_evidenced(profile, result.get("facts") or {})
    else:
        state["closeupMerge"] = {
            "status": "failed",
            "facts": {},
            "error": result.get("error") or "vision_failed",
            "at": _now(),
        }
    save_state(db, profile, state)
    db.commit()
    return get_status(db, project_id, character_id)


async def retry_vision(db: Session, project_id: str, character_id: str) -> dict[str, Any]:
    state = get_status(db, project_id, character_id)
    front_id = str(state["views"]["front"].get("assetId") or "")
    if not front_id or not state["views"]["front"].get("approved"):
        raise _err("FRONT_REQUIRED", "Approve Front before retrying vision.", 409)
    profile = _profile(db, project_id, character_id)
    result = await _run_vision([_asset_path(db, project_id, front_id)], FRONT_VISION_INSTRUCTIONS)
    if result.get("ok"):
        state["visualLock"] = {
            "status": "ok",
            "facts": result.get("facts") or {},
            "error": None,
            "at": _now(),
            "provenance": "CANONICAL_FROM_USER_APPROVAL",
            "provider": result.get("provider") or "fal",
            "model": result.get("model"),
        }
        _merge_evidenced(profile, result.get("facts") or {})
    else:
        state["visualLock"] = {
            "status": "failed",
            "facts": {},
            "error": result.get("error") or "vision_failed",
            "httpStatus": result.get("httpStatus"),
            "providerCode": result.get("providerCode"),
            "provider": result.get("provider") or "fal",
            "model": result.get("model"),
            "at": _now(),
        }
    save_state(db, profile, state)
    db.commit()
    return get_status(db, project_id, character_id)


async def retry_revision_2(db: Session, project_id: str, character_id: str) -> dict[str, Any]:
    state = get_status(db, project_id, character_id)
    if not state["views"]["front"].get("approved") or not state["views"]["back"].get("approved"):
        raise _err("VIEWS_REQUIRED", "Front and Back must be approved before JSON revision 2.", 409)
    profile = _profile(db, project_id, character_id)
    front_id = str(state["views"]["front"]["assetId"])
    back_id = str(state["views"]["back"]["assetId"])
    result = await _run_vision(
        [_asset_path(db, project_id, front_id), _asset_path(db, project_id, back_id)],
        BOTH_VISION_INSTRUCTIONS,
    )
    if result.get("ok"):
        state["revision2"] = {"status": "ok", "facts": result.get("facts") or {}, "error": None, "at": _now()}
        state["jsonRevision"] = 2
        _merge_evidenced(profile, result.get("facts") or {})
        from .crs_service import persist_crs_in_session
        from .prompt_package import generate_prompt_package
        from . import service

        persist_crs_in_session(db, profile, asset_id=front_id)
        from .crs_service import merge_persisted_crs

        merge_persisted_crs(
            db,
            profile,
            {
                "json_revision": 2,
                "approved_front_asset_id": front_id,
                "approved_back_asset_id": back_id,
                "coverage": "multi_view",
                "visual_lock_ok": True,
            },
        )
        pkg = generate_prompt_package(
            service.get_profile(db, project_id, character_id).model_dump(),
            character_version_id=profile.active_version_id or "",
        )
        profile.prompt_package_json = json.dumps(pkg, ensure_ascii=False)
    else:
        state["revision2"] = {
            "status": "failed",
            "facts": {},
            "error": result.get("error") or "vision_failed",
            "at": _now(),
        }
    save_state(db, profile, state)
    db.commit()
    return get_status(db, project_id, character_id)


def adopt_front_from_asset(
    db: Session,
    project_id: str,
    character_id: str,
    asset_id: str,
    *,
    source_type: str = "library",
) -> dict[str, Any]:
    """Upload / Library picture becomes views.front. Creator still Approves Front."""
    from .cc_v2_media import resolve_character_asset

    profile = _profile(db, project_id, character_id)
    resolved = resolve_character_asset(db, project_id, asset_id)
    if not resolved:
        raise _err("ASSET_NOT_FOUND", "That picture is not in this project's Library.", 404)
    state = get_status(db, project_id, character_id)
    prior_front = str(state["views"]["front"].get("assetId") or "").strip()
    state["views"]["front"] = {
        **empty_view(),
        "status": "ready",
        "assetId": resolved["assetId"],
        "assetUrl": resolved.get("assetUrl"),
        "approved": False,
        "sourceType": source_type,
        "generator": "library" if source_type == "library" else "upload",
    }
    if prior_front and prior_front != resolved["assetId"]:
        invalidate_after_regenerate(state, "front")
        state["views"]["front"]["status"] = "ready"
        state["views"]["front"]["assetId"] = resolved["assetId"]
        state["views"]["front"]["assetUrl"] = resolved.get("assetUrl")
        state["views"]["front"]["sourceType"] = source_type
        state["views"]["front"]["generator"] = "library" if source_type == "library" else "upload"
    else:
        from .cc_v3_multiview import empty_enrichment, empty_multiview

        if not state.get("multiView"):
            state["multiView"] = empty_multiview()
        if not state.get("multiviewEnrichment"):
            state["multiviewEnrichment"] = empty_enrichment()
    save_state(db, profile, state)
    db.commit()
    return get_status(db, project_id, character_id)


_COMPOSE_LOCKS: dict[str, threading.Lock] = {}
_COMPOSE_LOCKS_GUARD = threading.Lock()


def _compose_lock(character_id: str) -> threading.Lock:
    with _COMPOSE_LOCKS_GUARD:
        lock = _COMPOSE_LOCKS.get(character_id)
        if lock is None:
            lock = threading.Lock()
            _COMPOSE_LOCKS[character_id] = lock
        return lock


def compose_fingerprint(
    *,
    front_id: str,
    side_id: str,
    three_quarter_id: str,
    back_id: str,
    closeup_id: str = "",
    json_revision: int = 1,
) -> str:
    parts = [front_id, side_id, three_quarter_id, back_id]
    if closeup_id:
        parts.append(closeup_id)
    parts.append(str(_safe_int(json_revision, 1)))
    return "|".join(parts)


def _sheet_source_path(db: Session, project_id: str, asset_id: str, label: str) -> Path:
    try:
        return _asset_path(db, project_id, asset_id)
    except HTTPException as exc:
        raise _err("SHEET_SOURCE_MISSING", f"{label} picture is missing.", 400) from exc


def _unlink_orphan(path: Path | None) -> None:
    if path is None:
        return
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass


async def compose_sheet(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    regenerate: bool = False,
) -> dict[str, Any]:
    """Local Front | Side | 3/4 | Back stitch. No Vision, fal, Kie, Comfy, or Qwen."""
    from . import service
    from .cc_v3_multiview import sheet_gate
    from .character_sheet_compose import compose_v3_character_sheet
    from .crs_service import persist_crs_in_session
    from .visual_sheet import _composed_sheet_output_path, _ingest_composed_sheet_asset

    profile = _profile(db, project_id, character_id)
    lock = _compose_lock(character_id)
    if not lock.acquire(blocking=False):
        raise _err("SHEET_COMPOSE_ACTIVE", "Character Sheet is already being created.", 409)

    dest: Path | None = None
    try:
        state = get_status(db, project_id, character_id)
        gate = sheet_gate(state, db=db, character_id=character_id)
        if not gate.get("ready"):
            missing = gate.get("missing") or []
            raise _err("SHEET_GATE", ", ".join(missing) or "Approve Front", 409)

        front_id = str(gate.get("approvedFrontAssetId") or "").strip()
        side_id = str(gate.get("approvedSideAssetId") or "").strip()
        tq_id = str(gate.get("approvedThreeQuarterAssetId") or "").strip()
        back_id = str(gate.get("approvedBackAssetId") or "").strip()
        closeup_id = (
            str(state["views"]["closeup"].get("assetId") or "").strip()
            if state["views"]["closeup"].get("approved")
            else ""
        )
        if not (front_id and side_id and tq_id and back_id):
            raise _err("SHEET_SOURCE_MISSING", "Approved Front, Side, 3/4, and Back pictures are required.", 400)

        json_revision = _safe_int(state.get("jsonRevision"), 1)
        fingerprint = compose_fingerprint(
            front_id=front_id,
            side_id=side_id,
            three_quarter_id=tq_id,
            back_id=back_id,
            closeup_id=closeup_id,
            json_revision=json_revision,
        )
        existing_sheet = _as_dict(state.get("sheet"))
        existing_id = str(state.get("sheetAssetId") or existing_sheet.get("assetId") or "").strip()
        if (
            existing_id
            and not regenerate
            and str(existing_sheet.get("fingerprint") or "") == fingerprint
        ):
            return get_status(db, project_id, character_id)

        front_path = _sheet_source_path(db, project_id, front_id, "Front")
        side_path = _sheet_source_path(db, project_id, side_id, "Side")
        tq_path = _sheet_source_path(db, project_id, tq_id, "3/4")
        back_path = _sheet_source_path(db, project_id, back_id, "Back")
        closeup_path = _sheet_source_path(db, project_id, closeup_id, "Close-up") if closeup_id else None

        dest = _composed_sheet_output_path(project_id, character_id, 0)
        dest.parent.mkdir(parents=True, exist_ok=True)
        profile_dump = service.get_profile(db, project_id, character_id).model_dump()
        facts = dict((state.get("visualLock") or {}).get("facts") or {})
        at_tag = f"@{profile.name}" if profile.name else ""
        layout = compose_v3_character_sheet(
            str(front_path),
            str(side_path),
            str(tq_path),
            str(back_path),
            str(dest),
            profile=profile_dump,
            extra_facts=facts,
            closeup_path=str(closeup_path) if closeup_path else None,
        )
        sources = [front_id, side_id, tq_id, back_id]
        if closeup_id:
            sources.append(closeup_id)
        asset = _ingest_composed_sheet_asset(
            db,
            project_id,
            character_id=character_id,
            candidate_index=0,
            composed_path=str(dest),
            source_asset_ids=sources,
            lineage={
                "ccV3": True,
                "ccV2": False,
                "layout": layout.get("layout") or "v3_21x9_express",
                "viewAssetIds": {
                    "front": front_id,
                    "side": side_id,
                    "three_quarter": tq_id,
                    "back": back_id,
                    **({"closeup": closeup_id} if closeup_id else {}),
                },
                "jsonRevision": json_revision,
                "atTag": at_tag,
                "fingerprint": fingerprint,
            },
            layout=layout,
        )
        persist_crs_in_session(db, profile, asset_id=asset.id)
        state["sheetAssetId"] = asset.id
        state["sheet"] = {
            "status": "ready",
            "assetId": asset.id,
            "layout": layout.get("layout"),
            "fingerprint": fingerprint,
            "progress": {"percent": 100, "stage": "ready", "label": "Character Sheet Ready"},
        }
        save_state(db, profile, state)
        db.commit()
        dest = None
        return get_status(db, project_id, character_id)
    except Exception:
        db.rollback()
        _unlink_orphan(dest)
        raise
    finally:
        lock.release()


def compact_character_tag(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())
