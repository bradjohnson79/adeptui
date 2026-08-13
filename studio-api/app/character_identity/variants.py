"""Phase 6 — Character Variants.

A Variant is an alternate look for a character (wardrobe/styling change)
that preserves the locked identity (face/hair/eyes/body/silhouette). The
ORIGINAL canonical Character Sheet is immutable and lives on the character's
``hero_identity`` reference; variants hang off the character's continuity
identity version via the EXISTING ``identity_variants`` table (no new table).

Variant generation is reference-locked: the ORIGINAL canonical Character
Sheet asset is the PRIMARY conditioning reference so identity stays locked
while only the requested wardrobe/look changes. Each variant generation
reuses the SAME 4-view composed-sheet pipeline as candidates
(``visual_sheet.py``): front/side/back/close-up views are enqueued
reference-locked to the canonical sheet, validated for identity consistency,
then composed into a single 2x2 Character Sheet asset whose id is stored on
the variant.

This module bridges ``character_identity`` (canonical sheet resolution) and
``continuity`` (variant persistence). It does NOT modify ``visual_sheet.py``;
it reuses that module's compose/view helpers by import.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..continuity import service as continuity_service
from ..continuity.models import IdentityVariantRow, VisualIdentityRow
from ..db import Asset
from . import service as character_service
from .models import CharacterProfileRow

VARIANT_SHEET_KEY = "__variant_sheet__"
MAX_VARIANTS_PER_CHARACTER = 12


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _j(obj: Any) -> str:
    return json.dumps(obj if obj is not None else None, ensure_ascii=False)


def _l(raw: str | None, default: Any = None) -> Any:
    if not raw:
        return default if default is not None else {}
    try:
        return json.loads(raw)
    except Exception:
        return default if default is not None else {}


def _get_variant_row(db: Session, variant_id: str) -> IdentityVariantRow:
    row = db.get(IdentityVariantRow, variant_id)
    if not row or row.archived:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Variant not found."})
    return row


def _read_sheet_state(row: IdentityVariantRow) -> dict[str, Any]:
    overrides = _l(row.trait_overrides_json, {})
    state = overrides.get(VARIANT_SHEET_KEY) if isinstance(overrides, dict) else None
    return state if isinstance(state, dict) else {}


def _write_sheet_state(db: Session, row: IdentityVariantRow, state: dict[str, Any]) -> None:
    overrides = _l(row.trait_overrides_json, {})
    if not isinstance(overrides, dict):
        overrides = {}
    overrides[VARIANT_SHEET_KEY] = state
    row.trait_overrides_json = _j(overrides)
    db.commit()


def _assert_same_project(row_project_id: str, project_id: str, *, what: str = "variant") -> None:
    if row_project_id != project_id:
        raise HTTPException(
            status_code=403,
            detail={"code": "CROSS_PROJECT", "message": f"{what} belongs to a different project."},
        )


def resolve_identity_for_character(
    db: Session, project_id: str, character_id: str
) -> tuple[str, str]:
    """Resolve (identity_id, active_version_id) for a character.

    A character maps to a continuity VisualIdentityRow via character_profile_id.
    If no identity exists yet, one is created idempotently with an approved
    first version so variants have a stable version to hang off. Mirrors the
    certified promotion path in character_identity.promotion.
    """
    prow = db.get(CharacterProfileRow, character_id)
    if not prow or prow.project_id != project_id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Character not found."})

    existing = (
        db.query(VisualIdentityRow)
        .filter(
            VisualIdentityRow.project_id == project_id,
            VisualIdentityRow.character_profile_id == character_id,
        )
        .first()
    )
    if existing:
        version_id = existing.active_version_id or existing.production_version_id
        if not version_id:
            versions = continuity_service.list_versions(db, project_id, existing.id)
            if not versions:
                created = continuity_service.create_version(
                    db, project_id, existing.id, {"label": "Version 1", "summary": "Auto-created for variants"}
                )
                version_id = created["id"]
            else:
                version_id = versions[0]["id"]
        return existing.id, version_id

    created = continuity_service.create_identity(
        db,
        project_id,
        {
            "identityType": "character",
            "canonicalName": prow.slug or prow.name,
            "displayName": prow.name,
            "description": prow.description or prow.role,
            "characterProfileId": character_id,
        },
    )
    identity_id = created["id"]
    versions = continuity_service.list_versions(db, project_id, identity_id)
    version_id = versions[0]["id"] if versions else None
    if not version_id:
        v = continuity_service.create_version(
            db, project_id, identity_id, {"label": "Version 1", "summary": "Auto-created for variants"}
        )
        version_id = v["id"]
    try:
        continuity_service.approve_version(db, project_id, version_id, approved_by="variants")
    except Exception:
        pass
    return identity_id, version_id


def get_canonical_sheet_asset_id(db: Session, project_id: str, character_id: str) -> str | None:
    """Return the asset id of the character's canonical hero_identity sheet.

    The Original canonical Character Sheet is the immutable identity authority.
    Variants are reference-locked to THIS asset so identity stays consistent.
    """
    try:
        refs = character_service.list_references(db, project_id, character_id)
    except Exception:
        return None
    for role in ("hero_identity", "hero_portrait"):
        approved = next(
            (r for r in refs if r.get("reference_role") == role and r.get("approval_status") == "approved" and r.get("asset_id")),
            None,
        )
        if approved:
            return str(approved["asset_id"])
    for role in ("hero_identity", "hero_portrait"):
        any_ref = next((r for r in refs if r.get("reference_role") == role and r.get("asset_id")), None)
        if any_ref:
            return str(any_ref["asset_id"])
    return None


def create_variant_for_character(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    name: str,
    description: str = "",
    created_by: str = "user",
) -> dict[str, Any]:
    """Create a variant for a character, enforcing the max-12 cap.

    The Original canonical sheet is NOT a variant row — it is the immutable
    hero_identity reference on the character. Only variant rows count toward
    the 12 cap.
    """
    _identity_id, version_id = resolve_identity_for_character(db, project_id, character_id)
    existing = continuity_service.list_variants(db, project_id, version_id)
    if len(existing) >= MAX_VARIANTS_PER_CHARACTER:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VARIANT_LIMIT_REACHED",
                "message": (
                    f"You can have up to {MAX_VARIANTS_PER_CHARACTER} variants per character "
                    "(plus the Original). Delete a variant to add another."
                ),
                "max": MAX_VARIANTS_PER_CHARACTER,
            },
        )
    return continuity_service.create_variant(
        db,
        project_id,
        version_id,
        {
            "variantType": "custom",
            "name": name,
            "description": description,
            "traitOverrides": {},
            "lockedTraits": [],
            "createdBy": created_by,
        },
    )


def list_variants_for_character(
    db: Session, project_id: str, character_id: str
) -> dict[str, Any]:
    """Return the Original + variants for a character in one call."""
    identity_id, version_id = resolve_identity_for_character(db, project_id, character_id)
    variants = continuity_service.list_variants(db, project_id, version_id)
    canonical_asset_id = get_canonical_sheet_asset_id(db, project_id, character_id)
    original = {
        "id": None,
        "name": "Original",
        "description": "The canonical character sheet. This look is locked and never changes.",
        "characterSheetAssetId": canonical_asset_id,
        "isOriginal": True,
        "immutable": True,
    }
    return {
        "characterId": character_id,
        "identityId": identity_id,
        "versionId": version_id,
        "original": original,
        "variants": variants,
        "maxVariants": MAX_VARIANTS_PER_CHARACTER,
        "canGenerate": bool(canonical_asset_id),
    }


def delete_variant(db: Session, project_id: str, variant_id: str) -> dict[str, Any]:
    """Delete a variant. NEVER alters the Original canonical sheet."""
    row = _get_variant_row(db, variant_id)
    _assert_same_project(row.project_id, project_id)
    db.delete(row)
    db.commit()
    return {"ok": True, "variantId": variant_id, "deleted": True}


def _resolve_reference_locked_route(canonical_asset_id: str) -> dict[str, Any]:
    """Reference-first routing plan: canonical sheet as the source image."""
    from .visual_sheet import (
        REFERENCE_FIDELITY_DENOISE,
        REFERENCE_FIDELITY_MODE_LIMITED,
        REFERENCE_LOCKED_FAMILY,
        REFERENCE_LOCKED_WORKFLOW_KEY,
        _build_candidate_routing_plan,
    )

    try:
        plan = _build_candidate_routing_plan(
            candidate_count=1,
            reference_asset_id=canonical_asset_id,
        )
        return plan[0]
    except Exception:
        # No Certified reference-capable workflow in this environment — fall
        # back to an explicit zimage.ref_edit plan so the canonical sheet
        # still participates as the source image (honest referenceFidelityMode
        # "limited"). Never silently downgrade to text-only.
        return {
            "modelFamilyPreference": REFERENCE_LOCKED_FAMILY,
            "workflowKey": REFERENCE_LOCKED_WORKFLOW_KEY,
            "referenceAssetId": canonical_asset_id,
            "referenceLocked": True,
            "referenceFidelityMode": REFERENCE_FIDELITY_MODE_LIMITED,
            "source_asset_id": canonical_asset_id,
            "denoise": REFERENCE_FIDELITY_DENOISE,
        }


def enqueue_variant_generation(
    db: Session, project_id: str, character_id: str, variant_id: str
) -> dict[str, Any]:
    """Enqueue a reference-locked 4-view generation conditioned on the canonical sheet.

    Identity lock: the canonical hero_identity sheet asset is the PRIMARY
    reference (source image) for every view job so face/hair/eyes/body/
    silhouette stay locked; only the requested wardrobe/look (the variant
    description) changes. Reuses visual_sheet.py's view specs + compose
    helpers so the variant sheet is produced via the SAME pipeline as
    candidates.
    """
    row = _get_variant_row(db, variant_id)
    _assert_same_project(row.project_id, project_id)

    canonical_asset_id = get_canonical_sheet_asset_id(db, project_id, character_id)
    if not canonical_asset_id:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "NO_CANONICAL_SHEET",
                "message": (
                    "Generate and approve the Original character sheet first — "
                    "variants are locked to that look."
                ),
            },
        )
    asset = db.get(Asset, canonical_asset_id)
    if not asset or asset.project_id != project_id or asset.kind != "image":
        raise HTTPException(
            status_code=400,
            detail={"code": "BAD_CANONICAL_SHEET", "message": "Canonical sheet asset is missing or invalid."},
        )

    from .visual_sheet import (
        COMPOSITION_INTENT_CHARACTER_SHEET,
        COMPOSITION_INTENT_FULL_BODY_CASTING,
        FULL_BODY_CASTING_NEGATIVE_RULES,
        _candidate_seed,
        _candidate_view_specs,
        _compile_visual_prompt,
        _enqueue_txt2img,
        _low_reference_fidelity,
        _resolve_style_profile,
        _workflow_lineage,
    )

    profile_out = character_service.get_profile(db, project_id, character_id)
    profile = profile_out.model_dump()
    char_slug = (profile.get("slug") or profile.get("name") or "character").replace(" ", "_").lower()
    style_profile = _resolve_style_profile(profile.get("visual_style") or "")

    route = _resolve_reference_locked_route(canonical_asset_id)
    variant_description = (row.description or "").strip()
    seed = _candidate_seed(character_id, 0)
    view_specs = _candidate_view_specs()
    references = character_service.list_references(db, project_id, character_id)

    view_jobs: list[dict[str, Any]] = []
    for vidx, (vrole, vgoal, vcomposition, vneg) in enumerate(view_specs):
        composition = dict(vcomposition)
        composition["candidate_index"] = 0
        package = _compile_visual_prompt(
            profile,
            prompt_goal=vgoal,
            composition=composition,
            references=references,
            role=vrole,
            extra_negative_constraints=vneg if vneg is not None else FULL_BODY_CASTING_NEGATIVE_RULES,
            style_profile=style_profile,
            reference_locked=True,
        )
        prompt_text = package.prompt
        if variant_description:
            prompt_text = (
                f"{prompt_text}\n\nVARIANT LOOK (preserve identity, change only this): "
                f"{variant_description}"
            )
        vtag = f"{char_slug}_variant_{variant_id[:8]}_{vrole}"
        vjob = _enqueue_txt2img(
            db,
            project_id,
            character_id=character_id,
            prompt=prompt_text,
            negative_prompt=package.negative_prompt,
            tag=vtag,
            role=vrole,
            model_family_preference=route["modelFamilyPreference"],
            source_asset_id=route.get("source_asset_id"),
            denoise=route.get("denoise"),
            seed=seed,
            prompt_metadata={
                "promptFamily": package.prompt_family,
                "promptModel": package.model_key,
                "promptValidationOk": package.validation.get("ok"),
                "sheetMode": package.metadata.get("sheetMode"),
                "candidateIndex": 0,
                "candidateCount": 1,
                "viewIndex": vidx,
                "viewRole": vrole,
                "compositionIntent": COMPOSITION_INTENT_CHARACTER_SHEET
                if vrole != "hero_identity"
                else COMPOSITION_INTENT_FULL_BODY_CASTING,
                "fullBody": vrole != "closeup_front",
                "workflowKey": route["workflowKey"],
                "modelFamily": route["modelFamilyPreference"],
                "referenceLocked": True,
                "referenceAssetId": canonical_asset_id,
                "referenceFidelityMode": route.get("referenceFidelityMode"),
                "seed": seed,
                "variantId": variant_id,
                "variantDescription": variant_description,
                "objective": "character_variant_sheet",
            },
        )
        view_jobs.append(
            {
                "jobId": vjob.id,
                "role": vrole,
                "viewIndex": vidx,
                "status": vjob.status,
                "assetId": None,
                "seed": seed,
                "modelFamily": route["modelFamilyPreference"],
                "workflowKey": route["workflowKey"],
                "referenceLocked": True,
            }
        )

    lineage = _workflow_lineage(route["workflowKey"])
    low_fidelity = _low_reference_fidelity(reference_locked=True, lineage=lineage)

    state = {
        "status": "generating",
        "canonicalSheetAssetId": canonical_asset_id,
        "referenceAssetId": canonical_asset_id,
        "referenceLocked": True,
        "description": variant_description,
        "viewJobs": view_jobs,
        "seed": seed,
        "generator": lineage.get("generator"),
        "provider": lineage.get("provider"),
        "model": lineage.get("model"),
        "modelVariant": lineage.get("modelVariant"),
        "workflowKey": route["workflowKey"],
        "referenceFidelityMode": route.get("referenceFidelityMode"),
        "lowReferenceFidelity": low_fidelity,
        "sheetAssetId": None,
        "sourceAssetIds": [],
        "createdAt": _now(),
        "updatedAt": _now(),
    }
    _write_sheet_state(db, row, state)
    return {"ok": True, "variantId": variant_id, "generation": state}


def _job_params(job) -> dict[str, Any]:
    return _l(getattr(job, "params_json", None), {})


def advance_variant_generation(
    db: Session, project_id: str, variant_id: str
) -> dict[str, Any]:
    """Poll a variant's 4 view jobs; compose a 2x2 sheet when all done.

    Reuses visual_sheet.py's poll/validate/compose/ingest helpers so the
    variant sheet is produced via the SAME pipeline as candidates.
    """
    row = _get_variant_row(db, variant_id)
    _assert_same_project(row.project_id, project_id)
    state = _read_sheet_state(row)
    if not state:
        raise HTTPException(
            status_code=400,
            detail={"code": "NOT_STARTED", "message": "Variant generation has not been started."},
        )
    if state.get("status") == "done" and state.get("sheetAssetId"):
        return {"ok": True, "variantId": variant_id, "generation": state}

    from .visual_sheet import (
        _compose_character_sheet_grid,
        _composed_sheet_output_path,
        _ingest_composed_sheet_asset,
        _poll_candidate_views,
        _validate_candidate_view_consistency,
        _workflow_lineage,
    )

    view_jobs = state.get("viewJobs") or []
    if not view_jobs:
        raise HTTPException(status_code=400, detail={"code": "NO_VIEW_JOBS", "message": "Variant has no view jobs."})

    all_done, _asset_ids = _poll_candidate_views(db, {"viewJobs": view_jobs})
    state["viewJobs"] = view_jobs
    if not all_done:
        state["status"] = "generating"
        state["updatedAt"] = _now()
        _write_sheet_state(db, row, state)
        return {"ok": True, "variantId": variant_id, "generation": state}

    validation = _validate_candidate_view_consistency(view_jobs)
    if not validation.get("ok"):
        state["status"] = "failed"
        state["error"] = "identity consistency check failed: " + "; ".join(validation.get("reasons") or [])
        state["updatedAt"] = _now()
        _write_sheet_state(db, row, state)
        return {"ok": True, "variantId": variant_id, "generation": state}

    source_asset_ids = validation["assetIds"]
    view_paths: list[str] = []
    for aid in source_asset_ids:
        a = db.get(Asset, aid)
        if not a or not a.path:
            state["status"] = "failed"
            state["error"] = f"missing source view asset path for {aid}"
            state["updatedAt"] = _now()
            _write_sheet_state(db, row, state)
            return {"ok": True, "variantId": variant_id, "generation": state}
        view_paths.append(a.path)

    try:
        out_path = _composed_sheet_output_path(row.project_id, row.identity_id, 0)
        composed_path = _compose_character_sheet_grid(view_paths, str(out_path))
        lineage = _workflow_lineage(state.get("workflowKey") or "")
        # Resolve the character profile id for sheet metadata (provenance).
        vi = db.get(VisualIdentityRow, row.identity_id)
        sheet_character_id = (vi.character_profile_id if vi else None) or row.identity_id
        sheet_asset = _ingest_composed_sheet_asset(
            db,
            row.project_id,
            character_id=sheet_character_id,
            candidate_index=0,
            composed_path=composed_path,
            source_asset_ids=source_asset_ids,
            lineage=lineage,
        )
        state["sheetAssetId"] = sheet_asset.id
        state["sourceAssetIds"] = source_asset_ids
        state["status"] = "done"
        state["updatedAt"] = _now()
    except Exception as exc:
        state["status"] = "failed"
        state["error"] = f"character sheet composition failed: {exc}"
        state["updatedAt"] = _now()

    _write_sheet_state(db, row, state)
    return {"ok": True, "variantId": variant_id, "generation": state}
