"""Capability handler: ers.generate

Enqueues ONE Image Core job (purpose=environment_reference_sheet) for an
Environment Reference Sheet from a Spatial Map. The completed Library asset
is persisted onto the sheet (ers_composite_asset_id) so list_sheets /
resolve_ers_for_sheet can report has_reference.

Amendment #1 (ATLAS ORDER): ERS sits AFTER Spatial Map and BEFORE Scene
Creator. Workflow: Character Creator → Atlas Shot / Master Environment →
Spatial Map → ERS → Scene Creator → Timeline.

Amendment #2 (ERS COMPOSITION): AI generates the Master/N/E/S/W views.
Adept UI programmatically composites the final ERS sheet from those
actual assets + structured data via
``environment_reference_sheet.exports.render_png`` (REUSED — not duplicated).

Amendment #3 (SPATIAL AUTHORITY): the handler SNAPSHOT-COPIES placements
from the spatial map into the ERS package at generation time. It NEVER
writes back to the spatial map.

Amendment #4 (ORIENTATION): northLockDirection = "north" means the top edge
of the Atlas Shot. N/E/S/W are scene-relative.

Law #18: the one Image Core job goes through image-product
(``resolve_image_capability`` -> ``enqueue_imagegen_job`` / generate_images)
- no silent provider/model substitution. Creator-selected model =
requested = resolved = executed = provenance.
Law #7: this handler submits REAL jobs (no mock completion).
Async persist: handle stamps the sheet with the job id. When that imagegen
job completes, queue_worker._imagegen_commit_asset calls
persist_ers_composite_asset and sets sheet.ers_composite_asset_id.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DIRECTIONS: tuple[str, ...] = ("north", "east", "south", "west")
_ERS_PURPOSE = "environment_reference_sheet"
# Live Qwen qwen2512.txt2img probe 2026-08-16: native 2560x1440 decoded cleanly
# (Comfy success, ~86s warm, peak ~30GB / 32GB, no OOM). Product uses native 2K.
_ERS_2K_16_9 = (2560, 1440)

def ers_2k_pixels(aspect: str = "16:9") -> tuple[int, int]:
    """2K-class ERS pixels. 16:9 is the probed native size; other aspects use compile 2K."""
    key = (aspect or "16:9").strip() or "16:9"
    if key == "16:9":
        return _ERS_2K_16_9
    from ....image_product.compile import _ASPECT, _RES_SCALE

    w, h = _ASPECT.get(key, (1920, 1080))
    scale = float(_RES_SCALE.get("2K", 1.25))
    return max(64, int(w * scale / 8) * 8), max(64, int(h * scale / 8) * 8)

def image_core_prompt(plan: Any, fallback: str = "") -> str:
    """Image Core intent/prompt contract.

    ImageGenerationPlan has request / shotIntent / creativeDirection.
    Never read a top-level ``prompt`` attribute on the plan object.
    Prefer shotIntent.prompt, then request.prompt, then fallback.
    """
    shot = getattr(plan, "shotIntent", None)
    if shot is not None:
        text = getattr(shot, "prompt", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
    request = getattr(plan, "request", None)
    if request is not None:
        text = getattr(request, "prompt", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
    return (fallback or "").strip()

def _creator_model_body(
    *,
    hosted_model_id: str = "",
    model: str = "",
    model_family_preference: str = "",
    source: str = "",
    kie_image_model_id: str = "",
    fal_image_model_id: str = "",
    provider_kind: str = "",
    force_workflow_key: str = "",
    lock_model_family: bool = False,
) -> dict[str, Any]:
    """Pass through the creator-selected model. Never invent a default local workflow."""
    out: dict[str, Any] = {}
    if hosted_model_id:
        out["hostedModelId"] = hosted_model_id
    if model:
        out["model"] = model
    if model_family_preference:
        out["modelFamilyPreference"] = model_family_preference
    kind = (source or provider_kind or "").strip().lower()
    if kind:
        out["source"] = kind
        out["providerKind"] = kind
    if kie_image_model_id:
        out["kieImageModelId"] = kie_image_model_id
    if fal_image_model_id:
        out["falImageModelId"] = fal_image_model_id
    if force_workflow_key:
        out["forceWorkflowKey"] = force_workflow_key
        out["allow_force_workflow_key"] = True
        out["lockModelFamily"] = True
    if lock_model_family:
        out["lockModelFamily"] = True
    if out.get("hostedModelId") or out.get("kieImageModelId") or out.get("falImageModelId"):
        out["lockModelFamily"] = True
        out.setdefault("source", "api")
    return out

def build_ers_image_body(
    *,
    prompt: str,
    direction: str,
    execution_id: str,
    sheet_id: str,
    spatial_map_id: str,
    visual_style: str = "",
    north_lock: str = "north",
    operation: str = "image.generate",
    source_asset_id: str | None = None,
    selected: dict[str, Any] | None = None,
    aspect_ratio: str = "16:9",
) -> dict[str, Any]:
    """Image-product body. Creator-selected model is requested=resolved=executed."""
    selected = dict(selected or {})
    aspect = (aspect_ratio or "16:9").strip() or "16:9"
    w, h = ers_2k_pixels(aspect)
    body: dict[str, Any] = {
        "prompt": prompt,
        "negative_prompt": "",
        "width": w,
        "height": h,
        "tag": f"codirector_ers_{execution_id[:8]}_{direction}",
        "purpose": _ERS_PURPOSE,
        "operation": operation,
        "aspectRatio": aspect,
        "batchCount": 1,
        "creativeContext": {
            "objective": _ERS_PURPOSE,
            "executionId": execution_id,
            "direction": direction,
            "environmentReferenceSheetId": sheet_id,
            "spatialMapId": spatial_map_id,
            "northLockDirection": north_lock,
            "visualStyle": visual_style or "",
            "orientationNote": (
                "Scene-relative direction. North = top edge of the Atlas Shot."
            ),
        },
    }
    body.update(selected)
    # ERS is image-to-image (binding law): a source environment image may ride
    # source_asset_id / referenceImage and be consumed by the ref workflow.
    # Operation stays image.generate (reference conditioning, not an edit).
    body["operation"] = "image.generate"
    if source_asset_id:
        body["sourceAssetId"] = source_asset_id
        body["source_asset_id"] = source_asset_id
        body["referenceImage"] = source_asset_id
        body["reference_image"] = source_asset_id
    body.pop("edit", None)
    return body

def _spatial_map_reference_id(plan: Any, spatial_document: Any) -> str:
    raw = (
        getattr(plan, "reference_image", None)
        or getattr(plan, "referenceImage", None)
        or getattr(spatial_document, "backgroundAssetId", None)
    )
    return str(raw).strip() if raw else ""

def _gpt_i2i_official_id() -> str:
    """Canonical Kie Market id for GPT Image 2 image-to-image."""
    return "gpt-image-2-image-to-image"


def _gpt_t2i_official_id() -> str:
    """Canonical Kie Market id for GPT Image 2 text-to-image (prompt-only ERS)."""
    return "gpt-image-2-text-to-image"

def _pin_resolved_capability(body: dict[str, Any]) -> dict[str, Any]:
    """Resolve through image-product. Refuse instead of silently substituting."""
    from ....image_product.resolve import resolve_image_capability

    cap = resolve_image_capability(body)
    if not cap.get("canExecute"):
        reason = str(
            cap.get("reason")
            or "This model cannot run this Environment Reference Sheet request."
        )
        raise RuntimeError(reason)
    ctx = body.setdefault("creativeContext", {})
    if not isinstance(ctx, dict):
        ctx = {}
        body["creativeContext"] = ctx
    provider = str(cap.get("provider") or "")
    adapter = str(cap.get("adapter") or "")
    official = str(cap.get("officialModelId") or "")
    workflow_key = str(cap.get("workflowKey") or "")
    hosted = str(cap.get("hostedModelId") or "")
    ctx["resolvedProvider"] = provider
    ctx["resolvedAdapter"] = adapter
    ctx["resolvedOfficialModelId"] = official
    ctx["resolvedWorkflowKey"] = workflow_key
    if workflow_key:
        ctx["workflowKey"] = workflow_key
    if hosted:
        body["hostedModelId"] = hosted
    if provider == "kie" and official:
        body["kieImageModelId"] = official
        body.pop("falImageModelId", None)
    elif provider == "fal" and official:
        body["falImageModelId"] = official
        body.pop("kieImageModelId", None)
    elif provider == "wavespeed" and official:
        body["wavespeedImageModelId"] = official
        body["provider"] = "wavespeed"
        body.pop("kieImageModelId", None)
        body.pop("falImageModelId", None)
    elif provider == "local" and official and not body.get("modelFamilyPreference"):
        body["modelFamilyPreference"] = official
    return body

def _reuse_existing_ers_job(db: Session | None, project_id: str, tag: str) -> Any | None:
    """Duplicate-submit idempotency: reuse an in-flight job with the same tag."""
    if db is None or not tag:
        return None
    try:
        from ....db import Job
    except Exception:
        return None
    try:
        rows = (
            db.query(Job)
            .filter(Job.project_id == project_id, Job.kind.in_(("imagegen", "imagegen_edit")))
            .order_by(Job.created_at.desc())
            .limit(40)
            .all()
        )
    except Exception:
        return None
    terminal = {"failed", "cancelled", "canceled", "error"}
    for job in rows:
        status = str(getattr(job, "status", "") or "").strip().lower()
        if status in terminal:
            continue
        raw = getattr(job, "params_json", "") or ""
        try:
            params = json.loads(raw) if raw else {}
        except Exception:
            params = {}
        job_tag = str(params.get("tag") or "")
        if job_tag == tag:
            return job
    return None

def _enqueue_ers_image_product(db, project_id, body, scene_id=None):
    """Single image-product enqueue for ERS. Creator model already pinned."""
    from ....storyboard_jobs import enqueue_imagegen_job

    job = enqueue_imagegen_job(db, project_id, body, scene_id=scene_id)
    return {"jobId": job.id, "jobs": [{"jobId": job.id}]}

def persist_ers_composite_asset(
    db: Any = None,
    project_id: str = "",
    *,
    sheet_id: str = "",
    asset_id: str = "",
    package_id: str = "",
    sheet: Any = None,
    package: Any = None,
) -> dict[str, Any]:
    """Bind the completed Image Core Library asset onto the ERS sheet.

    Worker path: queue_worker._imagegen_commit_asset calls this with
    positional (db, project_id) when purpose=environment_reference_sheet.
    Sets sheet.ers_composite_asset_id and package.ers_composite_asset_id
    so list_sheets / resolve_ers_for_sheet has_reference is true.
    """
    from ....environment_reference_sheet.store import load_sheet, save_sheet
    from ....spatial_map.ers_persistence import (
        list_ers_packages,
        load_ers_package,
        save_ers_package,
    )

    asset_id = str(asset_id or "").strip()
    sheet_id = str(sheet_id or "").strip()
    package_id = str(package_id or "").strip()
    project_id = str(project_id or "").strip()

    current_package = package
    if current_package is None and package_id:
        try:
            current_package = load_ers_package(db, project_id, package_id)
        except Exception:
            current_package = None
    if current_package is None and sheet_id:
        try:
            packages = [
                p
                for p in list_ers_packages(db, project_id)
                if str((p.metadata or {}).get("sheet_id") or "") == sheet_id
                and not str(p.id).startswith("runtime-")
            ]
            if packages:
                current_package = sorted(
                    packages,
                    key=lambda p: p.updated_at or p.created_at or "",
                    reverse=True,
                )[0]
        except Exception:
            current_package = None
    if current_package is not None:
        current_package.ers_composite_asset_id = asset_id
        meta = dict(current_package.metadata or {})
        if sheet_id:
            meta["sheet_id"] = sheet_id
        meta["ers_composite_asset_id"] = asset_id
        current_package.metadata = meta
        save_ers_package(
            db, project_id, current_package, provenance="ers_composite_persist"
        )

    current_sheet = sheet
    if current_sheet is None and sheet_id:
        current_sheet = load_sheet(project_id, sheet_id)
    if current_sheet is not None:
        try:
            from ....environment_reference_sheet.versioning import sheet_is_frozen_for_inplace_persist
            if sheet_is_frozen_for_inplace_persist(current_sheet):
                return {
                    "ok": False,
                    "skipped": True,
                    "reason": "approved_or_canonical_sheet_frozen",
                    "sheetId": str(getattr(current_sheet, "sheetId", "") or sheet_id),
                    "assetId": asset_id,
                    "hint": "Create a new ERS version via POST .../versions instead of in-place persist.",
                }
        except Exception:
            pass
        current_sheet.ers_composite_asset_id = asset_id
        composition = getattr(current_sheet, "composition", None)
        if composition is not None:
            ids = dict(getattr(composition, "renderedAssetIds", None) or {})
            ids["composite"] = asset_id
            ids.setdefault("png", asset_id)
            composition.renderedAssetIds = ids
        save_sheet(current_sheet)

    return {
        "sheet_id": sheet_id,
        "asset_id": asset_id,
        "ers_composite_asset_id": asset_id,
        "package_id": getattr(current_package, "id", None),
        "has_reference": bool(asset_id),
    }

def _stamp_ers_job_on_sheet(sheet: Any, *, job_id: str, package_id: str) -> None:
    """Record the queued Image Core job so persist can fill the composite later."""
    provenance = getattr(sheet, "provenance", None)
    if provenance is None:
        return
    details = dict(getattr(provenance, "details", None) or {})
    details["ers_image_job_id"] = job_id
    details["ers_package_id"] = package_id
    provenance.details = details
    provenance.note = (
        "One Image Core job queued (purpose=environment_reference_sheet). "
        "queue_worker._imagegen_commit_asset calls persist_ers_composite_asset "
        "on complete and sets ers_composite_asset_id so has_reference is true."
    )

_GENERIC_SHEET_DESCRIPTION = "Programmatically composed environment reference sheet."

def _load_asset_prompt_meta(db: Session | None, asset_id: str) -> dict[str, Any]:
    """Best-effort prompt_meta for an asset (atlas Scene Intent recovery)."""
    if db is None or not asset_id:
        return {}
    try:
        from ....db import Asset

        asset = db.get(Asset, str(asset_id))
        raw = str(getattr(asset, "prompt_meta_json", "") or "") if asset is not None else ""
        if raw:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    return {}

def _placement_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    dump = getattr(item, "model_dump", None)
    if callable(dump):
        try:
            return dump()
        except Exception:
            pass
    out: dict[str, Any] = {}
    for key in (
        "characterId",
        "propId",
        "label",
        "tag",
        "visible",
        "slotIndex",
        "placementMode",
        "attachedCharacterId",
        "attachedCharacterSlot",
        "relationship",
        "attachmentPoint",
        "gridColumn",
        "gridRow",
        "miniPrompt",
        "pose",
        "id",
    ):
        if hasattr(item, key):
            out[key] = getattr(item, key)
    return out

def _character_identity_text(db: Session | None, project_id: str, character_id: str) -> dict[str, Any]:
    """Approved identity as text + asset id stamp. Never pixel refs on ERS T2I."""
    result: dict[str, Any] = {
        "characterId": character_id,
        "name": "",
        "facts": [],
        "approvedAssetId": None,
    }
    if db is None or not character_id:
        return result
    try:
        from ....character_identity.models import CharacterProfileRow, CharacterWardrobeRow
        from ....character_identity.service import resolve_approved_reference

        row = db.get(CharacterProfileRow, character_id)
        same_project = row is not None and str(row.project_id) == str(project_id)
        global_visible = row is not None and bool(getattr(row, "is_global", False))
        if row is None or not (same_project or global_visible):
            return result
        result["name"] = str(row.name or "").strip()
        facts: list[str] = []
        for label, value in (
            ("species", row.species_or_type),
            ("appearance", row.visual_description),
            ("height", row.height_description),
            ("build", row.body_type),
            ("age", row.apparent_age),
        ):
            text_value = str(value or "").strip()
            if text_value and text_value.lower() not in {"human", ""}:
                facts.append(f"{label}: {text_value}")
            elif text_value and label == "species":
                facts.append(f"{label}: {text_value}")
        wardrobe_id = str(getattr(row, "active_wardrobe_id", "") or "").strip()
        if wardrobe_id:
            wardrobe = db.get(CharacterWardrobeRow, wardrobe_id)
            if wardrobe is not None:
                wardrobe_bits = [
                    str(getattr(wardrobe, key, "") or "").strip()
                    for key in ("name", "description", "materials", "colors")
                ]
                wardrobe_text = ", ".join(bit for bit in wardrobe_bits if bit)
                if wardrobe_text:
                    facts.append(f"wardrobe: {wardrobe_text}")
        result["facts"] = facts
        result["approvedAssetId"] = resolve_approved_reference(db, character_id, "hero_identity")
    except Exception:
        logger.debug("ERS character identity text unavailable for %s", character_id, exc_info=True)
    return result

def _prop_identity_text(db: Session | None, project_id: str, prop_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "propId": prop_id,
        "name": "",
        "facts": [],
        "approvedAssetId": None,
    }
    if db is None or not prop_id:
        return result
    try:
        from ....spatial_map.ers_persistence import (
            load_prop_entity_anywhere,
            load_prop_entity_by_id,
        )

        entity = load_prop_entity_by_id(db, project_id, prop_id)
        if entity is None:
            entity = load_prop_entity_anywhere(db, prop_id)
        if entity is None:
            return result
        same_project = str(getattr(entity, "project_id", "") or "") == str(project_id)
        global_visible = bool(getattr(entity, "is_global", False) or getattr(entity, "isGlobal", False))
        if not same_project and not global_visible:
            return result
        result["name"] = str(entity.display_label or entity.tag or "").strip()
        facts: list[str] = []
        for label, value in (
            ("description", entity.description),
            ("style", entity.visual_style),
            ("notes", entity.notes),
        ):
            text_value = str(value or "").strip()
            if text_value:
                facts.append(f"{label}: {text_value}")
        result["facts"] = facts
        result["approvedAssetId"] = str(entity.approved_asset_id or "").strip() or None
    except Exception:
        logger.debug("ERS prop identity text unavailable for %s", prop_id, exc_info=True)
    return result

def _resolve_ers_grounding(
    db: Session | None,
    project_id: str,
    spatial_document: Any,
) -> dict[str, Any]:
    """Load the ERS grounding lineage in priority order (master prompt §7/§14).

    Scene Intent JSON > original environment reference image > Atlas/Spatial
    Map > structured spatial state. Snapshot-only — never re-infer here.
    """
    from ....spatial_map.scene_intent import (
        coerce_scene_intent,
        environment_intent_summary,
        lineage_fingerprint,
        scene_intent_from_atlas_meta,
    )

    atlas_id = str(getattr(spatial_document, "backgroundAssetId", None) or "").strip()
    intent = coerce_scene_intent(getattr(spatial_document, "sceneIntent", None))
    atlas_meta: dict[str, Any] = {}
    if intent is None and atlas_id:
        # Fallback: recover the Scene Intent snapshotted onto the atlas asset.
        atlas_meta = _load_asset_prompt_meta(db, atlas_id)
        intent = scene_intent_from_atlas_meta(atlas_meta)

    original_ref_id = str(
        getattr(spatial_document, "originalEnvironmentReferenceAssetId", None) or ""
    ).strip()
    if not original_ref_id and intent is not None and intent.sourceReferenceAssetIds:
        original_ref_id = str(intent.sourceReferenceAssetIds[0]).strip()
    if not original_ref_id and atlas_meta:
        refs = atlas_meta.get("originalEnvironmentReferenceAssetIds")
        if isinstance(refs, list) and refs:
            original_ref_id = str(refs[0]).strip()
    # The atlas IS the source environment when the creator uploaded it directly.
    if not original_ref_id and intent is not None:
        original_ref_id = atlas_id

    visible_characters = [
        _placement_dict(c)
        for c in (getattr(spatial_document, "characters", None) or [])
        if _placement_dict(c).get("visible", True)
    ]
    visible_props = [
        _placement_dict(p)
        for p in (getattr(spatial_document, "props", None) or [])
        if _placement_dict(p).get("visible", True)
    ]
    from ....spatial_map.ers_projection import compile_structured_blocking, compile_structured_cameras

    blocking = compile_structured_blocking([*visible_characters, *visible_props])
    camera_compile = compile_structured_cameras(getattr(spatial_document, "cameras", None) or [])
    contextual_subjects: list[str] = []
    character_ids: list[str] = []
    prop_ids: list[str] = []
    approved_character_asset_ids: list[str] = []
    approved_prop_asset_ids: list[str] = []
    char_names: list[str] = []
    prop_names: list[str] = []

    for placement in visible_characters:
        cid = str(placement.get("characterId") or "").strip()
        label = (
            str(placement.get("label") or "").strip()
            or str(placement.get("tag") or "").lstrip("@").strip()
        )
        identity = _character_identity_text(db, project_id, cid) if cid else {
            "characterId": cid,
            "name": label,
            "facts": [],
            "approvedAssetId": None,
        }
        name = identity.get("name") or label or cid
        if cid:
            character_ids.append(cid)
        if name:
            char_names.append(name)
        approved = str(identity.get("approvedAssetId") or "").strip()
        if approved:
            approved_character_asset_ids.append(approved)
        slot = placement.get("slotIndex")
        slot_note = f", slot {int(slot) + 1}" if isinstance(slot, int) and slot >= 0 else ""
        fact_text = "; ".join(str(f) for f in (identity.get("facts") or []) if f)
        line = f"Character {name}{slot_note}"
        if fact_text:
            line += f" — {fact_text}"
        mini = str(placement.get("miniPrompt") or "").strip()
        if mini:
            line += f". Blocking: {mini}"
        contextual_subjects.append(line)

    for placement in visible_props:
        pid = str(placement.get("propId") or placement.get("prop_id") or "").strip()
        label = (
            str(placement.get("label") or "").strip()
            or str(placement.get("tag") or "").lstrip("#").strip()
        )
        identity = _prop_identity_text(db, project_id, pid) if pid else {
            "propId": pid,
            "name": label,
            "facts": [],
            "approvedAssetId": None,
        }
        name = identity.get("name") or label or pid
        if pid:
            prop_ids.append(pid)
        if name:
            prop_names.append(name)
        approved = str(identity.get("approvedAssetId") or "").strip()
        if approved:
            approved_prop_asset_ids.append(approved)
        fact_text = "; ".join(str(f) for f in (identity.get("facts") or []) if f)
        line = f"Prop {name}"
        if fact_text:
            line += f" — {fact_text}"
        contextual_subjects.append(line)

    if blocking.get("conceptual_prose"):
        contextual_subjects.append(str(blocking["conceptual_prose"]))
    for block_line in blocking.get("lines") or []:
        text_line = str(block_line or "").strip()
        if text_line and text_line not in contextual_subjects:
            contextual_subjects.append(text_line)

    fingerprint = lineage_fingerprint(
        intent,
        background_asset_id=atlas_id,
        original_reference_asset_id=original_ref_id,
    )
    return {
        "intent": intent,
        "intent_summary": environment_intent_summary(intent),
        "atlas_asset_id": atlas_id,
        "original_environment_reference_asset_id": original_ref_id,
        "characters": [n for n in char_names if n],
        "props": [n for n in prop_names if n],
        "cameras": list(camera_compile.get("cameras") or []),
        "camera_lines": list(camera_compile.get("lines") or []),
        "camera_labels": list(camera_compile.get("labels") or []),
        "contextual_subjects": contextual_subjects,
        "character_ids": list(dict.fromkeys(character_ids)),
        "prop_ids": list(dict.fromkeys(prop_ids)),
        "approved_character_asset_ids": list(dict.fromkeys(approved_character_asset_ids)),
        "approved_prop_asset_ids": list(dict.fromkeys(approved_prop_asset_ids)),
        "fingerprint": fingerprint,
        "character_placements": visible_characters,
        "prop_placements": visible_props,
        "blocking": blocking,
    }

def _merge_creator_plan_subjects(
    grounding: dict[str, Any],
    db: Session | None,
    project_id: str,
    characters: list | None,
    props: list | None,
) -> dict[str, Any]:
    """Fold Environment Creator plan rows into the existing ERS grounding.

    Spatial Map placements stay first. Plan rows fill the gap when the map is
    absent (Adept UI v1.1). Identity stays text — approved asset ids are stamped,
    not sent as pixel input on prompt-only GPT.
    """
    out = dict(grounding or {})
    character_ids = list(out.get("character_ids") or [])
    prop_ids = list(out.get("prop_ids") or [])
    char_names = list(out.get("characters") or [])
    prop_names = list(out.get("props") or [])
    subjects = list(out.get("contextual_subjects") or [])
    approved_characters = list(out.get("approved_character_asset_ids") or [])
    approved_props = list(out.get("approved_prop_asset_ids") or [])

    for raw in characters or []:
        if not isinstance(raw, dict):
            continue
        cid = str(raw.get("characterId") or raw.get("character_id") or "").strip()
        if not cid or cid in character_ids:
            continue
        identity = _character_identity_text(db, project_id, cid)
        name = str(identity.get("name") or raw.get("name") or "").strip()
        character_ids.append(cid)
        if name and name not in char_names:
            char_names.append(name)
        approved = str(identity.get("approvedAssetId") or "").strip()
        if approved and approved not in approved_characters:
            approved_characters.append(approved)
        fact_text = "; ".join(str(f) for f in (identity.get("facts") or []) if f)
        line = f"Character {name or cid}"
        if fact_text:
            line += f" — {fact_text}"
        if line not in subjects:
            subjects.append(line)

    for raw in props or []:
        if not isinstance(raw, dict):
            continue
        pid = str(raw.get("propId") or raw.get("prop_id") or "").strip()
        if not pid or pid in prop_ids:
            continue
        identity = _prop_identity_text(db, project_id, pid)
        name = str(identity.get("name") or raw.get("name") or "").strip()
        prop_ids.append(pid)
        if name and name not in prop_names:
            prop_names.append(name)
        approved = str(identity.get("approvedAssetId") or "").strip()
        if approved and approved not in approved_props:
            approved_props.append(approved)
        fact_text = "; ".join(str(f) for f in (identity.get("facts") or []) if f)
        line = f"Prop {name or pid}"
        if fact_text:
            line += f" — {fact_text}"
        assignment = str(raw.get("assignment") or "").strip()
        if assignment == "used_by":
            owner = str(raw.get("characterId") or raw.get("character_id") or "").strip()
            if owner:
                line += f". Used by {owner}"
        if line not in subjects:
            subjects.append(line)

    out["character_ids"] = character_ids
    out["prop_ids"] = prop_ids
    out["characters"] = char_names
    out["props"] = prop_names
    out["contextual_subjects"] = subjects
    out["approved_character_asset_ids"] = approved_characters
    out["approved_prop_asset_ids"] = approved_props
    return out

def _public_asset_url(asset_id: str, project_id: str | None = None) -> str:
    """Public URL a hosted provider (Kie/fal) can fetch for pixel grounding."""
    from ....project_security.asset_file import canonical_project_asset_file_url

    asset_id = str(asset_id or "").strip()
    if not asset_id:
        return ""
    pid = str(project_id or "").strip()
    if not pid:
        try:
            from ....db import Asset, SessionLocal

            db = SessionLocal()
            try:
                asset = db.get(Asset, asset_id)
                pid = str(getattr(asset, "project_id", "") or "")
            finally:
                db.close()
        except Exception:
            pid = ""
    if not pid:
        return ""
    try:
        from ....config import settings

        base = str(getattr(settings, "public_api_base_url", "") or "").rstrip("/")
    except Exception:
        base = ""
    if not base:
        return ""
    rel = canonical_project_asset_file_url(pid, asset_id)
    return f"{base}{rel}" if rel else ""

def _ers_sheet_prompt(
    sheet: Any,
    spatial_document: Any,
    grounding: dict[str, Any] | None = None,
    visual_canon: Any = None,
    continuity_invariants: list[str] | None = None,
    continuity_packet: Any = None,
) -> str:
    from ....codirector.knowledgebase.ers_compiler import (
        compile_environment_reference_sheet_prompt,
    )

    grounding = grounding or {}
    intent = grounding.get("intent")
    spatial: dict[str, Any] = {}
    if spatial_document is not None:
        for key in (
            "id",
            "masterEnvironmentPrompt",
            "backgroundAssetId",
            "northLockDirection",
        ):
            val = getattr(spatial_document, key, None)
            if val not in (None, ""):
                spatial[key] = val
        if getattr(sheet, "spatialMap", None) is not None:
            lock = getattr(sheet.spatialMap, "northLockDirection", None)
            if lock:
                spatial.setdefault("northLockDirection", lock)
            mid = getattr(sheet.spatialMap, "mapId", None)
            if mid:
                spatial.setdefault("mapId", mid)
    sheet_description = str(getattr(sheet, "description", "") or "")
    if sheet_description == _GENERIC_SHEET_DESCRIPTION and intent is not None:
        sheet_description = str(intent.summary or "")
    compiled = compile_environment_reference_sheet_prompt(
        environment_name=str(getattr(sheet, "name", "") or ""),
        environment_description=sheet_description,
        creator_prompt=str(
            getattr(spatial_document, "masterEnvironmentPrompt", "") or ""
        )
        or (str(intent.sourcePromptSummary) if intent is not None else ""),
        spatial_map=spatial,
        environment_intent=intent.model_dump() if intent is not None else None,
        characters=list(grounding.get("characters") or []),
        props=list(grounding.get("props") or []),
        cameras=list(grounding.get("cameras") or []),
        camera_facts=list(grounding.get("camera_lines") or []),
        contextual_subjects=list(grounding.get("contextual_subjects") or []),
        atlas_note=str(spatial.get("backgroundAssetId") or grounding.get("atlas_asset_id") or ""),
        visual_canon=(visual_canon.model_dump() if visual_canon is not None else None),
        continuity_invariants=continuity_invariants,
        continuity_packet=continuity_packet,
    )
    seed = str(compiled.get("prompt") or "").strip()
    core_plan = type(
        "ImageCoreIntent",
        (),
        {
            "shotIntent": type("ShotIntent", (), {"prompt": seed})(),
            "request": type("Request", (), {"prompt": seed})(),
        },
    )()
    return image_core_prompt(core_plan, fallback=seed)

def _is_qwen2512_selection(creator_model: dict[str, Any]) -> bool:
    """True when the creator selected (or defaults to) the Qwen-Image-2512 family."""
    blob = " ".join(
        str(creator_model.get(k) or "")
        for k in ("model", "modelFamilyPreference", "forceWorkflowKey")
    ).lower()
    return "qwen2512" in blob or "qwen_image_2512" in blob

def _ers_i2i_workflow_key() -> str:
    """The certified Qwen image-to-image workflow for ERS, or '' when unavailable.

    ERS requires a generator with genuine image input + text instruction
    (binding law). A Draft/absent qwen2512.ref yields '' so the handler blocks
    honestly instead of falling back to text-to-image.
    """
    try:
        from ....image_runtime.certified_registry import get_workflow

        wf = get_workflow("qwen2512.ref")
    except Exception:
        return ""
    if wf is None or str(getattr(wf, "status", "") or "") != "Certified":
        return ""
    return "qwen2512.ref"

def _looks_like_fal_endpoint(model_id: str, dock_id: str = "") -> bool:
    """True when this id is a fal still endpoint, not a Kie Market id."""
    pin = str(model_id or "").strip()
    dock = str(dock_id or "").strip()
    blob = f"{pin} {dock}".lower()
    if dock.lower().endswith("-fal"):
        return True
    if pin.startswith(("fal-ai/", "openai/", "krea/")) or "fal-ai/" in blob:
        if "text-to-image" in pin or "image-to-image" in pin:
            return False
        return True
    try:
        from ....fal_catalog import FAL_IMAGE_ENDPOINT_BY_DOCK, fal_image_model_id_for_dock
    except Exception:
        return False
    if pin and pin in set(FAL_IMAGE_ENDPOINT_BY_DOCK.values()):
        return True
    mapped = fal_image_model_id_for_dock(dock) or fal_image_model_id_for_dock(pin)
    return bool(mapped)


def _fal_still_endpoint(model_id: str, dock_id: str = "") -> str:
    """Return a fal endpoint. A Kie Market id is never treated as a fal model."""
    pin = str(model_id or "").strip()
    dock = str(dock_id or "").strip()
    if pin and not pin.lower().endswith("-fal"):
        lowered = pin.lower()
        if "text-to-image" not in lowered and "image-to-image" not in lowered:
            if pin.startswith(("fal-ai/", "openai/", "krea/")):
                return pin
            try:
                from ....fal_catalog import FAL_IMAGE_ENDPOINT_BY_DOCK

                if pin in set(FAL_IMAGE_ENDPOINT_BY_DOCK.values()):
                    return pin
            except Exception:
                pass
    try:
        from ....fal_catalog import fal_image_model_id_for_dock
    except Exception:
        return ""
    return str(fal_image_model_id_for_dock(dock) or fal_image_model_id_for_dock(pin) or "").strip()


def _preflight_hosted_ers_start(
    *,
    requested_provider: str = "",
    requestedProvider: str = "",
    provider: str = "",
    provider_kind: str = "",
    providerKind: str = "",
    hosted_model_id: str = "",
    hostedModelId: str = "",
    model: str = "",
    fal_image_model_id: str = "",
    falImageModelId: str = "",
    kie_image_model_id: str = "",
    kieImageModelId: str = "",
    wavespeedImageModelId: str = "",
    wavespeed_image_model_id: str = "",
) -> None:
    """Fail closed before any ERS sheet write when the hosted route cannot start."""
    from ....image_product.compile import explicit_hosted_provider

    requested = explicit_hosted_provider(
        {
            "requested_provider": requested_provider or requestedProvider,
            "provider": provider,
            "providerKind": provider_kind or providerKind,
        }
    )
    dock = str(hosted_model_id or hostedModelId or model or "").strip()
    fal_pin = str(fal_image_model_id or falImageModelId or "").strip()
    kie_pin = str(kie_image_model_id or kieImageModelId or "").strip()
    wavespeed_pin = str(wavespeedImageModelId or wavespeed_image_model_id or "").strip()
    if not requested and _looks_like_fal_endpoint(fal_pin, dock):
        requested = "fal"
    elif not requested and wavespeed_pin and not fal_pin:
        requested = "wavespeed"
    if requested == "fal":
        endpoint = _fal_still_endpoint(fal_pin, dock)
        if not endpoint:
            raise RuntimeError("fal.ai could not start this environment generation.")
    elif requested == "wavespeed":
        if not (wavespeed_pin or dock):
            raise RuntimeError("wavespeed.ai could not start this environment generation.")
    elif requested == "kie":
        # Legacy GPT Image 2 on kie is resolved later; only hard-fail empty hosted pins.
        gpt_blob = " ".join([dock, kie_pin, str(model or "")]).lower()
        legacy_gpt = "gpt-image-2" in gpt_blob and "2.5" not in gpt_blob
        if not legacy_gpt and not (kie_pin or dock):
            raise RuntimeError("kie.ai could not start this environment generation.")


def _is_explicit_gpt_image_2(creator_model: dict[str, Any]) -> bool:
    """True only when the creator explicitly selected GPT Image 2 (Kie)."""
    blob = " ".join(
        str(creator_model.get(k) or "")
        for k in ("hostedModelId", "kieImageModelId", "model", "modelFamilyPreference")
    ).lower()
    return "gpt-image-2" in blob or "gpt_image_2" in blob

def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    spatial_map_id: str = "",
    sheet_id: str = "",
    sheetId: str = "",
    scene_id: str = "",
    visual_style: str = "",
    name: str = "",
    description: str = "",
    hosted_model_id: str = "",
    hostedModelId: str = "",
    model: str = "",
    model_family_preference: str = "",
    modelFamilyPreference: str = "",
    source: str = "",
    kie_image_model_id: str = "",
    kieImageModelId: str = "",
    fal_image_model_id: str = "",
    falImageModelId: str = "",
    provider_kind: str = "",
    providerKind: str = "",
    provider: str = "",
    forceWorkflowKey: str = "",
    lockModelFamily: bool = False,
    visual_canon_corrections: dict[str, Any] | None = None,
    panel_task: str = "",
    panelTask: str = "",
    source_asset_id: str = "",
    sourceAssetId: str = "",
    reference_asset_id: str = "",
    referenceAssetId: str = "",
    reference_image: str = "",
    referenceImage: str = "",
    authoritative_source_asset_id: str = "",
    authoritativeSourceAssetId: str = "",
    forceFull: bool = False,
    force_full: bool = False,
    ers_force_full: bool = False,
    ers_pipeline: str = "",
    generationMode: str = "",
    templateId: str = "",
    collageTemplate: str = "",
    environmentPrompt: str = "",
    prompt: str = "",
    storyTheme: str = "",
    aspectRatio: str = "",
    aspect_ratio: str = "",
    characters: list | None = None,
    props: list | None = None,
    isGlobal: bool = False,
    is_global: bool = False,
    requested_provider: str = "",
    requestedProvider: str = "",
    wavespeedImageModelId: str = "",
    wavespeed_image_model_id: str = "",
) -> dict[str, Any]:
    """Enqueue ONE Image Core job (purpose=environment_reference_sheet) and persist the asset.

    ``visual_canon_corrections`` are creator-authored overrides of the
    Co-Director Vision canon - they outrank inferred vision output.
    """
    from ....environment_reference_sheet.orchestrator import (
        attach_spatial_map,
        compose_sheet_metadata,
        create_sheet,
    )
    from ....environment_reference_sheet.store import list_sheets, save_sheet
    from ....spatial_map.ers_contracts import EnvironmentReferencePackage
    from ....spatial_map.ers_persistence import save_ers_package
    from ....spatial_map.ers_projection import project_document_placements
    from ....spatial_map.service import get_document

    map_id = str(spatial_map_id or "").strip()
    wanted_sheet_id = str(sheet_id or sheetId or "").strip()
    existing_sheets = list_sheets(project_id)
    sheet = None
    if wanted_sheet_id:
        sheet = next(
            (s for s in existing_sheets if str(getattr(s, "sheetId", "") or "") == wanted_sheet_id),
            None,
        )
    if sheet is None and map_id:
        sheet = next(
            (
                s
                for s in existing_sheets
                if s.spatialMap and s.spatialMap.mapId == map_id
            ),
            None,
        )

    # Spatial Map is optional enrichment (shelved in Adept UI v1.1). ERS remains
    # the environment authority and can proceed without a map document.
    spatial_document = None
    if map_id:
        spatial_document = get_document(db, project_id, map_id)
    grounding = _merge_creator_plan_subjects(
        _resolve_ers_grounding(db, project_id, spatial_document),
        db,
        project_id,
        characters=characters,
        props=props,
    )
    scene_intent = grounding.get("intent")

    if sheet is None:
        sheet_name = (
            (name or "").strip()
            or (str(scene_intent.sceneTitle).strip() if scene_intent is not None else "")
            or "Environment Reference Sheet"
        )
        sheet_description = (
            (description or "").strip()
            or (environmentPrompt or "").strip()
            or (prompt or "").strip()
            or (str(scene_intent.summary).strip() if scene_intent is not None else "")
            or _GENERIC_SHEET_DESCRIPTION
        )
        from ....creator_scope.contract import CreatorScopeError, normalize_is_global
        from ....environment_reference_sheet.store import (
            check_environment_tag_collision,
            find_reusable_environment_draft,
            sync_environment_scope,
        )

        # ENVIRONMENT_DRAFT_ERS_SEPARATION: never mint a new ERS row when the
        # hosted provider cannot start. Validate before create_sheet.
        _preflight_hosted_ers_start(
            requested_provider=requested_provider,
            requestedProvider=requestedProvider,
            provider=provider,
            provider_kind=provider_kind,
            providerKind=providerKind,
            hosted_model_id=hosted_model_id,
            hostedModelId=hostedModelId,
            model=model,
            fal_image_model_id=fal_image_model_id,
            falImageModelId=falImageModelId,
            kie_image_model_id=kie_image_model_id,
            kieImageModelId=kieImageModelId,
            wavespeedImageModelId=wavespeedImageModelId,
            wavespeed_image_model_id=wavespeed_image_model_id,
        )
        next_global = normalize_is_global(isGlobal if isGlobal else is_global)
        reusable = find_reusable_environment_draft(
            existing_sheets,
            project_id=project_id,
            name=sheet_name,
        )
        if reusable is not None:
            sheet = reusable
            if sheet_description.strip():
                sheet.description = sheet_description
                profile = getattr(sheet, "profile", None)
                if profile is not None:
                    profile.description = sheet_description
        else:
            try:
                check_environment_tag_collision(
                    db,
                    project_id=project_id,
                    name=sheet_name,
                    making_global=next_global,
                )
            except CreatorScopeError as exc:
                raise RuntimeError(exc.message) from exc
            except ValueError as exc:
                raise RuntimeError(str(exc)) from exc
            sheet = create_sheet(
                project_id=project_id,
                name=sheet_name,
                description=sheet_description,
                scene_id=scene_id or None,
                is_global=next_global,
            )

    # Populate the EnvironmentProfile from the Scene Intent when the profile
    # still carries generic defaults (never stomp curated fields).
    if scene_intent is not None:
        profile = getattr(sheet, "profile", None)
        if profile is not None:
            if str(getattr(profile, "environmentType", "") or "") in {"", "environment"}:
                profile.environmentType = scene_intent.locationType or "environment"
            if not str(getattr(profile, "storyPurpose", "") or "").strip() or str(
                getattr(profile, "storyPurpose", "")
            ) == "Environment reference sheet":
                profile.storyPurpose = scene_intent.productionIntent or profile.storyPurpose

    if map_id and spatial_document is not None:
        sheet = attach_spatial_map(db, sheet, spatial_map_id=map_id)
    sheet = compose_sheet_metadata(sheet)
    creator_model = _creator_model_body(
        hosted_model_id=hosted_model_id or hostedModelId,
        model=model,
        model_family_preference=model_family_preference or modelFamilyPreference,
        source=source or provider or provider_kind or providerKind,
        kie_image_model_id=kie_image_model_id or kieImageModelId,
        fal_image_model_id=fal_image_model_id or falImageModelId,
        provider_kind=provider_kind or providerKind,
        force_workflow_key=forceWorkflowKey,
        lock_model_family=bool(lockModelFamily),
    )

    reference_id = _spatial_map_reference_id(None, spatial_document) if spatial_document is not None else ""
    context_source = str(
        authoritative_source_asset_id
        or authoritativeSourceAssetId
        or source_asset_id
        or sourceAssetId
        or reference_asset_id
        or referenceAssetId
        or reference_image
        or referenceImage
        or ""
    ).strip()
    grounding_ids = [
        gid
        for gid in (
            grounding.get("original_environment_reference_asset_id"),
            grounding.get("atlas_asset_id"),
            context_source,
        )
        if gid
    ]
    grounding_ids = list(dict.fromkeys(grounding_ids))
    source_pixels = grounding_ids[0] if grounding_ids else ""
    if context_source and not grounding.get("original_environment_reference_asset_id") and not grounding.get("atlas_asset_id"):
        grounding = {
            **grounding,
            "original_environment_reference_asset_id": context_source,
            "atlas_asset_id": context_source,
        }
    planning_prompt = str(
        environmentPrompt or prompt or name or description or ""
    ).strip()
    # Creator-selected Qwen uses the existing local workflows.
    # An explicit Environment Creator provider is strict. Unset still uses
    # GPT Image 2 on kie for the older Spatial Map caller.
    from ....image_product.compile import explicit_hosted_provider

    requested = explicit_hosted_provider(
        {
            "requested_provider": requested_provider or requestedProvider,
            "provider": provider,
            "providerKind": provider_kind or providerKind,
        }
    )
    wavespeed_model = str(
        wavespeedImageModelId
        or wavespeed_image_model_id
        or creator_model.get("wavespeedImageModelId")
        or ""
    ).strip()
    fal_pin = str(creator_model.get("falImageModelId") or "").strip()
    kie_pin = str(creator_model.get("kieImageModelId") or "").strip()
    dock_id = str(creator_model.get("hostedModelId") or creator_model.get("model") or "").strip()
    if not requested and _looks_like_fal_endpoint(fal_pin, dock_id):
        requested = "fal"
    elif not requested and wavespeed_model and not fal_pin:
        requested = "wavespeed"
    # GPT Image 2 on kie keeps the certified Market image-to-image / text-to-image ids.
    # A fal or wavespeed model id must not flip that decision, and fal's own
    # GPT Image 2 endpoint must not enter the Kie path.
    gpt_parts = [dock_id, str(creator_model.get("model") or "")]
    if requested in {"", "kie"}:
        gpt_parts.append(kie_pin)
    gpt_blob = " ".join(gpt_parts).lower()
    selected_is_gpt = requested != "fal" and "gpt-image-2" in gpt_blob and "2.5" not in gpt_blob
    legacy_gpt_kie = selected_is_gpt and requested in {"", "kie"}
    hosted_selected = requested in {"fal", "wavespeed"} or (requested == "kie" and not legacy_gpt_kie)
    qwen_selected = _is_qwen2512_selection(creator_model)
    gpt_selected = _is_explicit_gpt_image_2(creator_model) and not hosted_selected
    unspecified = not qwen_selected and not gpt_selected and not any(
        str(creator_model.get(k) or "").strip()
        for k in ("model", "modelFamilyPreference", "hostedModelId", "kieImageModelId", "falImageModelId")
    )
    qwen_i2i = False
    qwen_t2i = False
    gpt_i2i = False
    gpt_t2i = False
    if not source_pixels and not planning_prompt:
        raise RuntimeError(
            "ERS requires an authoritative environment image or an environment prompt. "
            "Provide a source/reference environment asset, or describe the environment in text. "
            "Spatial Map is optional."
        )
    if qwen_selected and source_pixels:
        qwen_i2i = True
        creator_model = {
            **creator_model,
            "model": "qwen2512",
            "modelFamilyPreference": "qwen2512",
            "source": "local",
            "providerKind": "local",
            "forceWorkflowKey": "qwen2512.ref",
            "lockModelFamily": True,
        }
    elif qwen_selected and planning_prompt:
        qwen_t2i = True
        creator_model = {
            **creator_model,
            "model": "qwen2512",
            "modelFamilyPreference": "qwen2512",
            "source": "local",
            "providerKind": "local",
            "forceWorkflowKey": "qwen2512.txt2img",
            "lockModelFamily": True,
        }
    elif hosted_selected:
        official_fal = str(creator_model.get("falImageModelId") or "").strip()
        official_kie = str(creator_model.get("kieImageModelId") or "").strip()
        official_wavespeed = wavespeed_model
        dock = str(creator_model.get("hostedModelId") or creator_model.get("model") or "").strip()
        creator_model = {
            **creator_model,
            "hostedModelId": dock,
            "source": "api",
            "providerKind": requested,
            "provider": requested,
        }
        if requested == "fal":
            endpoint = _fal_still_endpoint(official_fal, dock)
            if not endpoint:
                raise RuntimeError("fal.ai could not start this environment generation.")
            creator_model["falImageModelId"] = endpoint
            creator_model["requested_provider"] = "fal"
            creator_model.pop("kieImageModelId", None)
            creator_model.pop("wavespeedImageModelId", None)
        elif requested == "wavespeed":
            if not (official_wavespeed or dock):
                raise RuntimeError("wavespeed.ai could not start this environment generation.")
            creator_model["wavespeedImageModelId"] = official_wavespeed or dock
            creator_model["requested_provider"] = "wavespeed"
            creator_model.pop("kieImageModelId", None)
            creator_model.pop("falImageModelId", None)
        else:
            if not (official_kie or dock):
                raise RuntimeError("kie.ai could not start this environment generation.")
            creator_model["kieImageModelId"] = official_kie or dock
            creator_model["requested_provider"] = "kie"
            creator_model.pop("falImageModelId", None)
            creator_model.pop("wavespeedImageModelId", None)
    elif gpt_selected or unspecified:
        creator_model = {
            **creator_model,
            "hostedModelId": "gpt-image-2-kie",
            "source": "api",
            "providerKind": "api",
        }
        if source_pixels:
            # Source present → keep GPT I2I path (existing).
            gpt_i2i = True
            creator_model["kieImageModelId"] = _gpt_i2i_official_id()
            try:
                from ....hosted_providers.adapters.kie_adapter import kie_image_supports_i2i

                gpt_i2i_ok = kie_image_supports_i2i("gpt-image-2-kie")
            except Exception:
                gpt_i2i_ok = False
            if not gpt_i2i_ok:
                raise RuntimeError(
                    "GPT Image 2 — Requires Setup. Environment Reference Sheets use "
                    "GPT Image 2 image-to-image when a source image is attached."
                )
        else:
            # No source_pixels but environmentPrompt (or name/description/prompt) → GPT T2I.
            gpt_t2i = True
            creator_model["kieImageModelId"] = _gpt_t2i_official_id()
    if not qwen_i2i and not qwen_t2i and not gpt_i2i and not gpt_t2i and not hosted_selected:
        raise RuntimeError(
            "Environment Reference Sheets use GPT Image 2 API only. "
            "This generator is not authorized for ERS. Configure GPT Image 2 image-to-image "
            "(or provide an environment prompt for text-to-image)."
        )
    # Environment Visual Canon (Co-Director Vision) + creator corrections.
    from ...vision.visual_canon import (
        canon_is_stale,
        load_visual_canon,
        merge_visual_canon,
    )

    canon = None
    if db is not None and map_id:
        canon = load_visual_canon(db, project_id, map_id)
        if canon is not None and canon_is_stale(canon, grounding.get("fingerprint") or ""):
            canon = None  # stale canon is not authoritative; regenerate via CD Vision
    creator_corrections = visual_canon_corrections if isinstance(visual_canon_corrections, dict) else None
    canon = merge_visual_canon(canon, creator_corrections)
    from types import SimpleNamespace
    from ...knowledgebase.multimodal_continuity import ContinuityCompileError, compile_packet
    from ...knowledgebase.multimodal_continuity.provenance import stamp_continuity_packet

    requested_panel = str(panel_task or panelTask or "whole_sheet").strip() or "whole_sheet"
    provider_name = "qwen" if (qwen_i2i or qwen_t2i) else ("gpt-image-2" if (gpt_i2i or gpt_t2i) else "")
    scene_title = ""
    location_type = ""
    if scene_intent is not None:
        scene_title = str(scene_intent.sceneTitle or "")
        location_type = str(scene_intent.locationType or "")
    continuity_packet = None
    try:
        continuity_packet = compile_packet(
            scene_title=scene_title or str(getattr(sheet, "name", "") or ""),
            location_type=location_type,
            original_asset_id=str(grounding.get("original_environment_reference_asset_id") or ""),
            atlas_asset_id=str(grounding.get("atlas_asset_id") or ""),
            lineage_fingerprint=str(grounding.get("fingerprint") or ""),
            canon=canon,
            characters=list(grounding.get("character_placements") or []),
            props=list(grounding.get("prop_placements") or []),
            blocking=grounding.get("blocking"),
            panel_task=requested_panel,
            extra_invariants=(
                creator_corrections.get("hardInvariants")
                if creator_corrections and isinstance(creator_corrections.get("hardInvariants"), list)
                else None
            ),
            provider=provider_name,
        )
    except ContinuityCompileError as exc:
        # Map-less prompt-only ERS: continuity is enrichment, not a hard gate.
        # This includes an explicit fal / kie / wavespeed selection, not only the legacy Kie GPT path.
        if (gpt_t2i or qwen_t2i or hosted_selected) and not map_id and planning_prompt:
            logger.info("ERS prompt-only skipped continuity compile: %s", exc)
            continuity_packet = None
        else:
            raise RuntimeError(str(exc)) from exc

    seed_prompt = _ers_sheet_prompt(
        sheet,
        spatial_document,
        grounding,
        visual_canon=canon,
        continuity_invariants=creator_corrections.get("hardInvariants")
        if creator_corrections and isinstance(creator_corrections.get("hardInvariants"), list)
        else None,
        continuity_packet=continuity_packet,
    )
    if planning_prompt:
        # Prompt-only / Express planning: prefer creator environmentPrompt.
        seed_prompt = planning_prompt if not seed_prompt else f"{planning_prompt}\n\n{seed_prompt}"
    prompt_text = image_core_prompt(
        SimpleNamespace(
            shotIntent=SimpleNamespace(prompt=seed_prompt),
            request=SimpleNamespace(prompt=str(getattr(sheet, "description", None) or planning_prompt or "")),
        ),
        fallback=seed_prompt or planning_prompt,
    )
    resolved_aspect = str(aspectRatio or aspect_ratio or "16:9").strip() or "16:9"
    body = build_ers_image_body(
        prompt=prompt_text,
        direction="sheet",
        execution_id=execution_id,
        sheet_id=sheet.sheetId,
        spatial_map_id=spatial_map_id,
        visual_style=visual_style,
        north_lock=(
            sheet.spatialMap.northLockDirection if sheet.spatialMap else "north"
        ),
        selected=creator_model,
        source_asset_id=source_pixels or None,
        aspect_ratio=resolved_aspect,
    )
    body["creativeContext"]["operationIntent"] = (
        "image_to_image_reference" if qwen_i2i else "image.generate"
    )
    body["creativeContext"]["authoritativeSourceAssetId"] = source_pixels
    # Prefer full_sheet / full_sheet_api / ers.original.v1 / forceFull for Env Creator regenerate.
    pipeline = str(ers_pipeline or "full_sheet").strip() or "full_sheet"
    gen_mode = str(generationMode or "full_sheet_api").strip() or "full_sheet_api"
    template = str(templateId or collageTemplate or "ers.original.v1").strip() or "ers.original.v1"
    body["creativeContext"]["forceFull"] = True
    body["creativeContext"]["force_full"] = True
    body["creativeContext"]["ers_force_full"] = True
    body["creativeContext"]["ers_pipeline"] = pipeline
    body["creativeContext"]["generationMode"] = gen_mode
    body["creativeContext"]["templateId"] = template
    body["creativeContext"]["collageTemplate"] = template
    body["forceFull"] = True
    body["ers_pipeline"] = pipeline
    body["generationMode"] = gen_mode
    if qwen_i2i:
        body["forceWorkflowKey"] = _ers_i2i_workflow_key()
        body["allow_force_workflow_key"] = True
        body["lockModelFamily"] = True
        body["creativeContext"]["referenceGrounding"] = {
            "mode": "pixel",
            "assetIds": grounding_ids,
            "workflow": _ers_i2i_workflow_key(),
            "authoritativeSourceAssetId": source_pixels,
        }
    elif qwen_t2i:
        body["forceWorkflowKey"] = "qwen2512.txt2img"
        body["allow_force_workflow_key"] = True
        body["lockModelFamily"] = True
        body["model"] = "qwen2512"
        body["modelFamilyPreference"] = "qwen2512"
        body.pop("sourceAssetId", None)
        body.pop("source_asset_id", None)
        body.pop("referenceImage", None)
        body.pop("reference_image", None)
        body.pop("input_urls", None)
        body["creativeContext"]["operationIntent"] = "image.generate"
        body["creativeContext"]["referenceGrounding"] = {
            "mode": "text",
            "workflow": "qwen2512.txt2img",
        }
    elif hosted_selected:
        body["hostedModelId"] = str(creator_model.get("hostedModelId") or "")
        body["providerKind"] = requested
        body["provider"] = requested
        body["requested_provider"] = requested
        body["source"] = "api"
        body["lockModelFamily"] = True
        body.pop("forceWorkflowKey", None)
        if requested == "fal":
            body["falImageModelId"] = str(creator_model.get("falImageModelId") or "")
            body.pop("kieImageModelId", None)
            body.pop("wavespeedImageModelId", None)
        elif requested == "wavespeed":
            body["wavespeedImageModelId"] = str(creator_model.get("wavespeedImageModelId") or "")
            body.pop("kieImageModelId", None)
            body.pop("falImageModelId", None)
        else:
            body["kieImageModelId"] = str(creator_model.get("kieImageModelId") or "")
            body.pop("falImageModelId", None)
            body.pop("wavespeedImageModelId", None)
        if not source_pixels:
            body.pop("sourceAssetId", None)
            body.pop("source_asset_id", None)
            body.pop("referenceImage", None)
            body.pop("reference_image", None)
            body.pop("input_urls", None)
    elif gpt_i2i:
        body["hostedModelId"] = "gpt-image-2-kie"
        body["kieImageModelId"] = _gpt_i2i_official_id()
        body["lockModelFamily"] = True
        body.pop("forceWorkflowKey", None)
    elif gpt_t2i:
        body["hostedModelId"] = "gpt-image-2-kie"
        body["kieImageModelId"] = _gpt_t2i_official_id()
        body["lockModelFamily"] = True
        body.pop("forceWorkflowKey", None)
        body.pop("sourceAssetId", None)
        body.pop("source_asset_id", None)
        body.pop("referenceImage", None)
        body.pop("reference_image", None)
        body.pop("input_urls", None)

    # Lineage into creativeContext: durable on job params for the worker commit
    # hook (edges + prompt_meta) regardless of which generator executes.
    ctx = body["creativeContext"]
    if scene_intent is not None:
        ctx["sceneIntent"] = scene_intent.model_dump()
        ctx["sceneIntentVersion"] = scene_intent.version
    if grounding.get("atlas_asset_id"):
        ctx["atlasAssetId"] = grounding["atlas_asset_id"]
    grounding_ids = [
        gid
        for gid in (
            grounding.get("original_environment_reference_asset_id"),
            grounding.get("atlas_asset_id"),
        )
        if gid
    ]
    grounding_ids = list(dict.fromkeys(grounding_ids))
    if grounding_ids:
        ctx["groundingAssetIds"] = grounding_ids
    ctx["authoritativeSourceAssetId"] = source_pixels
    if planning_prompt:
        ctx["environmentPrompt"] = planning_prompt
    if storyTheme:
        ctx["storyTheme"] = str(storyTheme).strip()
    if resolved_aspect:
        ctx["aspectRatio"] = resolved_aspect
    if isinstance(characters, list) and characters:
        ctx["characters"] = characters
    if isinstance(props, list) and props:
        ctx["props"] = props
    ctx["groundingFingerprint"] = grounding.get("fingerprint") or ""
    ctx["characterIds"] = list(grounding.get("character_ids") or [])
    ctx["propIds"] = list(grounding.get("prop_ids") or [])
    ctx["approvedCharacterAssetIds"] = list(grounding.get("approved_character_asset_ids") or [])
    ctx["approvedPropAssetIds"] = list(grounding.get("approved_prop_asset_ids") or [])
    ctx["contextualSubjects"] = list(grounding.get("contextual_subjects") or [])
    ctx["cameras"] = list(grounding.get("cameras") or [])
    ctx["cameraLines"] = list(grounding.get("camera_lines") or [])
    ctx["gridScale"] = int(getattr(spatial_document, "gridScale", 0) or 0)
    if canon is not None:
        ctx["visualCanon"] = {
            "version": canon.version,
            "availability": canon.availability,
            "fingerprint": canon.fingerprint,
            "sourceAssetId": canon.sourceAssetId,
            "provenance": canon.provenance,
            "unavailableReason": canon.unavailableReason,
        }
    if continuity_packet is not None:
        stamp_continuity_packet(body, continuity_packet)

    # GPT Image 2 I2I: pixels must reach Kie as input_urls (CDX-035).
    # Prompt-only ERS uses hosted T2I (gpt-image-2-text-to-image) — no input_urls.
    if gpt_i2i:
        urls = [u for u in (_public_asset_url(source_pixels),) if u]
        if not urls:
            urls = [u for u in (_public_asset_url(gid) for gid in grounding_ids) if u]
        if not urls:
            raise RuntimeError(
                "GPT Image 2 cannot run this Environment Reference Sheet without a "
                "public URL for the source environment image when a source is attached."
            )
        body["input_urls"] = urls
        ctx["operationIntent"] = "image.generate"
        ctx["referenceGrounding"] = {
            "mode": "pixel",
            "assetIds": [source_pixels],
            "authoritativeSourceAssetId": source_pixels,
            "urlCount": len(urls),
            "workflow": _gpt_i2i_official_id(),
        }
        body["kieImageModelId"] = _gpt_i2i_official_id()
        if "not pixel image-to-image" in str(body.get("prompt") or ""):
            body["prompt"] = str(body.get("prompt") or "").replace(
                " Atlas shot informs this environment as text only "
                f"(asset {reference_id}); not pixel image-to-image.",
                "",
            ).strip()
    elif qwen_t2i:
        body.pop("input_urls", None)
        body["forceWorkflowKey"] = "qwen2512.txt2img"
        body["lockModelFamily"] = True
        ctx["operationIntent"] = "image.generate"
        ctx["referenceGrounding"] = {"mode": "text", "workflow": "qwen2512.txt2img"}
    elif gpt_t2i:
        body.pop("input_urls", None)
        ctx["operationIntent"] = "image.generate"
        ctx["referenceGrounding"] = {
            "mode": "text",
            "workflow": _gpt_t2i_official_id(),
        }
        body["kieImageModelId"] = _gpt_t2i_official_id()
    try:
        from ....image_product.compile import compile_image_request

        compiled = compile_image_request(project_id, body)
        intent = compiled.get("imageIntent") or {}
        core_prompt = str(intent.get("prompt") or "").strip()
        if core_prompt:
            body["prompt"] = core_prompt
    except Exception as exc:
        logger.info("ERS Image Core compile used seed prompt: %s", exc)
    body = _pin_resolved_capability(body)
    if qwen_t2i:
        body["forceWorkflowKey"] = "qwen2512.txt2img"
        body["allow_force_workflow_key"] = True
        body["lockModelFamily"] = True
        body["model"] = "qwen2512"
        body["modelFamilyPreference"] = "qwen2512"
        ctx = body.setdefault("creativeContext", {})
        if isinstance(ctx, dict):
            ctx["resolvedWorkflowKey"] = "qwen2512.txt2img"
            ctx["workflowKey"] = "qwen2512.txt2img"
    if gpt_i2i:
        official = str(
            body.get("kieImageModelId")
            or (body.get("creativeContext") or {}).get("resolvedOfficialModelId")
            or ""
        )
        if "text-to-image" in official:
            raise RuntimeError(
                "GPT Image 2 resolved to text-to-image for ERS with a source image. "
                "Source-backed Environment Reference Sheets require gpt-image-2-image-to-image."
            )
        body["kieImageModelId"] = _gpt_i2i_official_id()
    elif gpt_t2i:
        body["kieImageModelId"] = _gpt_t2i_official_id()
        official = str(
            (body.get("creativeContext") or {}).get("resolvedOfficialModelId") or ""
        )
        # Prefer T2I Market id for prompt-only; do not invent new persist schema.
        if official and "image-to-image" in official and "text-to-image" not in official:
            body["kieImageModelId"] = _gpt_t2i_official_id()
    if requested == "fal":
        endpoint = _fal_still_endpoint(
            str(body.get("falImageModelId") or ""),
            str(body.get("hostedModelId") or ""),
        )
        if not endpoint:
            raise RuntimeError("fal.ai could not start this environment generation.")
        body["falImageModelId"] = endpoint
        body["provider"] = "fal"
        body["providerKind"] = "fal"
        body["requested_provider"] = "fal"
        body.pop("kieImageModelId", None)
        body.pop("wavespeedImageModelId", None)
    elif requested == "wavespeed":
        if not str(body.get("wavespeedImageModelId") or "").strip():
            raise RuntimeError("wavespeed.ai could not start this environment generation.")
        body["provider"] = "wavespeed"
        body["providerKind"] = "wavespeed"
        body["requested_provider"] = "wavespeed"
        body.pop("kieImageModelId", None)
        body.pop("falImageModelId", None)
    elif requested == "kie" and not (gpt_i2i or gpt_t2i):
        body["provider"] = "kie"
        body["requested_provider"] = "kie"
        body.pop("falImageModelId", None)
        body.pop("wavespeedImageModelId", None)

    dispatch_provider = requested or ("kie" if (gpt_i2i or gpt_t2i) else "")
    dispatch_model = str(
        body.get("falImageModelId")
        or body.get("wavespeedImageModelId")
        or body.get("kieImageModelId")
        or body.get("hostedModelId")
        or ""
    )
    logger.info(
        "Environment Creator provider=%s model=%s",
        dispatch_provider or "unspecified",
        dispatch_model,
    )

    package = EnvironmentReferencePackage(
        project_id=project_id,
        scene_layout_id=map_id or "",
        atlas_asset_id=getattr(spatial_document, "backgroundAssetId", None),
        placements=project_document_placements(spatial_document),
        style_context={"visual_style": visual_style or ""},
        orientation="atlas-north-up",
        directional_assets={d: None for d in _DIRECTIONS},
        metadata={
            "execution_id": execution_id,
            "sheet_id": sheet.sheetId,
            "grounding_asset_ids": grounding_ids,
            "authoritative_source_asset_id": source_pixels,
            "scene_intent_version": scene_intent.version if scene_intent is not None else None,
            "grounding_fingerprint": grounding.get("fingerprint") or "",
            "character_ids": list(grounding.get("character_ids") or []),
            "prop_ids": list(grounding.get("prop_ids") or []),
            "approved_character_asset_ids": list(grounding.get("approved_character_asset_ids") or []),
            "approved_prop_asset_ids": list(grounding.get("approved_prop_asset_ids") or []),
            "visual_canon": (
                {
                    "version": canon.version,
                    "availability": canon.availability,
                    "fingerprint": canon.fingerprint,
                    "sourceAssetId": canon.sourceAssetId,
                    "provenance": canon.provenance,
                }
                if canon is not None
                else None
            ),
        },
    )
    body.setdefault("creativeContext", {})
    body["creativeContext"]["ersPackageId"] = package.id
    body["creativeContext"]["environmentReferenceSheetId"] = sheet.sheetId

    existing = _reuse_existing_ers_job(db, project_id, str(body.get("tag") or ""))
    if existing is not None:
        job_id = getattr(existing, "id", None) or str(existing)
    else:
        queued = _enqueue_ers_image_product(
            db, project_id, body, scene_id=scene_id or None
        )
        if isinstance(queued, dict):
            job_id = queued.get("jobId") or (queued.get("jobs") or [{}])[0].get("jobId")
        else:
            job_id = getattr(queued, "id", None)
    job_id = str(job_id or "")

    package.metadata = {
        **dict(package.metadata or {}),
        "ers_image_job_id": job_id,
        "directional_job_ids": [job_id],
    }
    _stamp_ers_job_on_sheet(sheet, job_id=job_id, package_id=package.id)
    # Source-lineage provenance on the sheet (frozen contract: details dict).
    provenance = getattr(sheet, "provenance", None)
    if provenance is not None:
        details = dict(getattr(provenance, "details", None) or {})
        if scene_intent is not None:
            details["sceneIntent"] = scene_intent.model_dump()
            details["sceneIntentVersion"] = scene_intent.version
        if grounding_ids:
            details["groundingAssetIds"] = grounding_ids
        if grounding.get("original_environment_reference_asset_id"):
            details["originalEnvironmentReferenceAssetId"] = grounding[
                "original_environment_reference_asset_id"
            ]
        details["groundingFingerprint"] = grounding.get("fingerprint") or ""
        if canon is not None:
            details["visualCanon"] = {
                "version": canon.version,
                "availability": canon.availability,
                "fingerprint": canon.fingerprint,
                "sourceAssetId": canon.sourceAssetId,
                "provenance": canon.provenance,
            }
        provenance.details = details
    save_ers_package(db, project_id, package)
    from ....creator_scope.contract import normalize_is_global
    from ....environment_reference_sheet.store import sync_environment_scope

    if isGlobal or is_global:
        sheet.isGlobal = normalize_is_global(isGlobal if isGlobal else is_global)
    save_sheet(sheet)
    try:
        sync_environment_scope(db, sheet)
    except Exception:
        pass

    try:
        from ....production_events import ACTOR_CODIRECTOR, record_production_event

        record_production_event(
            db,
            project_id=project_id,
            scene_id=scene_id or None,
            event_type="ers.generation_started",
            actor=ACTOR_CODIRECTOR,
            actor_detail="capability:ers.generate",
            subject_kind="sheet",
            subject_id=str(getattr(sheet, "sheetId", "") or ""),
            summary=f"ERS generation started (job {job_id[:8]})",
            payload={"jobId": job_id, "sheetId": str(getattr(sheet, "sheetId", "") or ""), "packageId": package.id},

        )
    except Exception:  # noqa: BLE001 - event recording never breaks the operation
        pass

    return {
        "job_ids": [job_id],
        "child_jobs": [
            {
                "job_id": job_id,
                "label": "Environment Reference Sheet",
                "status": "queued",
                "child_index": 0,
                "metadata": {
                    "purpose": _ERS_PURPOSE,
                    "operation": body.get("operation"),
                    "operationIntent": body.get("creativeContext", {}).get(
                        "operationIntent"
                    ),
                    "resolvedProvider": body.get("creativeContext", {}).get(
                        "resolvedProvider"
                    ),
                    "resolvedWorkflowKey": body.get("creativeContext", {}).get(
                        "resolvedWorkflowKey"
                    ),
                    "ers_package_id": package.id,
                    "sheet_id": sheet.sheetId,
                    "spatial_map_id": map_id or None,
                },
            }
        ],
        "surface_type": "ers_generation",
        "ers_package_id": package.id,
        "sheet_id": sheet.sheetId,
        "spatial_map_id": map_id or None,
        "purpose": _ERS_PURPOSE,
    }
