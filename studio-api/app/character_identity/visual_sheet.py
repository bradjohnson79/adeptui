"""Generated Character Image Profile — real Image Product / character-sheet pack.

Canonical identity (korri.v1 / approved sheet) remains authority.
Generated views prove Character Creator can produce visual coverage via certified Qwen-Image-2512.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..db import Asset, Job, Project
from ..image_prompting.qwen_2512 import compile_character_image_prompt
from . import service
from .roles import REQUIRED_COVERAGE_ROLES
from .schemas import ReferenceAttach, TraitUpsert
from .visual_gates import (
    list_gates,
    owner_select_concept,
    propose_visual_directions,
    set_gate_status,
)

PACK_TRAIT_KEY = "visual_sheet_pack"

DEFAULT_NEGATIVE_PROMPT = (
    "blonde hair, aqua eyes, blue eyes, metallic clothing, sci-fi armor, "
    "collage, grid, watermark, child, sexualized, anadriya, low quality"
)

# Hard full-body casting composition rule (Amendment 2).
# Character Creator casting candidates are full-body character views by default.
# This supplements (never rewrites) the user's Character Profile.
FULL_BODY_CASTING_COMPOSITION: dict[str, Any] = {
    "shot_type": "full body casting reference",
    "framing": "head to feet, full character visible in frame",
    "camera_angle": "eye level, slight 3/4",
    "lens": "50mm, minimal perspective distortion",
    "environment": "simple unobtrusive studio background",
    "lighting": "soft studio light",
    "pose": "standing, natural relaxed pose, readable hands and feet",
    "expression": "neutral natural presence",
    "focus": "full-body composition, character occupies most of frame without cropping",
    "full_body": True,
}

# Explicit rejections appended to negative constraints so the model cannot drift
# back to portrait/headshot framing even if a close-up reference is attached.
FULL_BODY_CASTING_NEGATIVE_RULES: list[str] = [
    "No close-up",
    "No headshot",
    "No bust portrait",
    "No waist-up framing",
    "Do not crop head, arms, hands, legs, or feet",
]

# Machine-readable composition intent persisted into prompt_metadata → creative_context
# → Job lineage so Co-Director, retakes, and MAGI can determine framing without
# parsing prompt text. Regeneration inherits this via the same endpoint.
COMPOSITION_INTENT_FULL_BODY_CASTING = "full_body_casting"

QWEN_VISUAL_SHEET_STYLE = {
    "medium": "photoreal cinematic character reference",
    "finish": "clean production-ready render",
    "palette": "grounded natural color separation with identity-safe materials",
    "lighting": "soft studio lighting with readable facial clarity",
}

# --- Character Candidate Diversity + Reference Fidelity (Amendment 3) ---
#
# Authority order when a Character Reference / Reference Sheet is attached:
#   REFERENCE IMAGE  >  Character Profile  >  project visual style  >  model formatting
#
# The written Profile may clarify personality/expression/pose and add details NOT
# visible in the reference; it must NOT override visible reference features. When
# no reference is attached, the Character Profile remains the primary visual
# authority (legacy behavior).
#
# Multi-generator routing: candidate diversity comes from different Certified
# generators / seeds / interpretation — NEVER from changing the character's
# identity. We draw from the Certified READY registry only (no Draft/Deferred
# workflows), use each distinct generator once before reusing, and never
# fabricate distinctness.
REFERENCE_REPRODUCTION_DIRECTIVE = (
    "Reproduce the attached character reference as faithfully as possible. "
    "Preserve the same face, hairstyle, eye color, ears, skin tone, body proportions, "
    "wardrobe, accessories, tattoos/circuitry, and silhouette. "
    "Do not redesign or reinterpret the character. "
    "Only vary pose, expression, and background subtly. "
    "Full-body casting view, head to feet visible."
)

# Reference-fidelity strength for zimage.ref_edit (img2img latent path). At 0.68
# denoise the model retains ~32% of the reference latent for identity lock while
# keeping enough freedom to compose a clean full-body casting image (rather than
# re-rendering a multi-view sheet layout). Lower values reproduce the sheet too
# closely; higher values drop reference conditioning.
REFERENCE_FIDELITY_DENOISE = 0.68

# Certified txt2img families available for no-reference candidate routing, in
# preference order. Each is used once before any reuse. Sourced from the
# Certified READY registry (zimage.txt2img, qwen2512.txt2img).
NO_REFERENCE_TXT2IMG_FAMILIES = ("qwen2512", "zimage")

# Reference-capable Certified workflow for reference-locked candidates. This is
# the only Certified workflow that consumes reference pixels today; until more
# reference-capable workflows are Certified, all reference-locked candidates use
# it and we record referenceFidelityMode="limited" honestly.
REFERENCE_LOCKED_WORKFLOW_KEY = "zimage.ref_edit"
REFERENCE_LOCKED_FAMILY = "zimage"
REFERENCE_FIDELITY_MODE_LIMITED = "limited"
REFERENCE_FIDELITY_MODE_FULL = "zimage_ref_edit"


def _resolve_style_profile(visual_style: str | None) -> dict[str, Any]:
    """Resolve a creator-facing visual_style to a style_profile dict.

    Accepts either a registry key (e.g. "anime", "live_action") or a display
    name (e.g. "Live Action", "Anime"). Falls back to the default
    QWEN_VISUAL_SHEET_STYLE when blank/unresolved so existing characters keep
    working. For unrecognised custom style text (e.g. "1990s hand-drawn
    anime"), wrap it as a medium hint over the default profile rather than
    discarding the user's intent.
    """
    if not visual_style:
        return dict(QWEN_VISUAL_SHEET_STYLE)
    key = visual_style.strip()
    if not key:
        return dict(QWEN_VISUAL_SHEET_STYLE)
    try:
        from ..style_intelligence.registry import STYLE_REGISTRY, REQUIRED_STYLE_KEYS

        if key in STYLE_REGISTRY:
            return STYLE_REGISTRY[key].to_dict()
        lowered = key.lower()
        for k in REQUIRED_STYLE_KEYS:
            profile = STYLE_REGISTRY[k]
            if profile.displayName.lower() == lowered:
                return profile.to_dict()
    except Exception:
        pass
    # Custom free-text style: honour the creator's wording as the medium,
    # layered over the default identity-safe cinematic baseline.
    merged = dict(QWEN_VISUAL_SHEET_STYLE)
    merged["medium"] = f"{key} character reference"
    return merged

ROLE_TO_SHEET_VIEW = {
    "full_body_front": "front",
    "full_body_side_left": "side_left",
    "full_body_back": "back",
    "closeup_front": "front_closeup",
    "closeup_side_left": "side_closeup",
    "closeup_back": "back_closeup",
}

GATE_ROLE_GROUPS: dict[str, tuple[str, ...]] = {
    "hero_identity": ("hero_identity",),
    "turnaround": ("full_body_front", "full_body_side_left", "full_body_back"),
    "facial": ("closeup_front", "closeup_side_left", "closeup_back"),
    "detail": (
        "skin_closeup",
        "hair_front",
        "hair_side",
        "hair_back",
        "wardrobe_reference",
        "accessory_reference",
    ),
    "performance": ("expression_sheet", "pose_sheet"),
}

KORRI_LOCK = (
    "LOCKED IDENTITY: Korri, 18, Human/Sun Sprite Elf Hybrid, black twin ponytails, purple eyes, "
    "pale skin, pointed Sun Sprite Elf ears, wooden earrings, circuit/light tattoos, "
    "handmade black cloth wardrobe, petite slim athletic ~5'1\". "
    "FORBIDDEN: blonde hair, aqua/blue eyes, metallic futuristic wardrobe, Anadriya face, "
    "missing pointed ears, missing circuit markings."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default
def _compiler_payload(profile: dict[str, Any]) -> dict[str, Any]:
    payload = dict(profile)
    wardrobe = payload.get("active_wardrobe") or payload.get("wardrobe") or {}
    if isinstance(wardrobe, dict) and wardrobe:
        payload["wardrobe"] = wardrobe
    canon_version = payload.get("canon_version") or payload.get("canonVersion") or ""
    if canon_version:
        payload["canonVersion"] = canon_version
    return payload


def _sheet_request_for_role(role: str) -> dict[str, Any]:
    view = ROLE_TO_SHEET_VIEW.get(role)
    if not view:
        return {}
    return {"enabled": True, "views": [view]}


def _compile_visual_prompt(
    profile: dict[str, Any],
    *,
    prompt_goal: str,
    composition: dict[str, Any],
    references: list[dict[str, Any]],
    role: str,
    extra_negative_constraints: list[str] | None = None,
    style_profile: dict[str, Any] | None = None,
    reference_locked: bool = False,
) -> Any:
    return compile_character_image_prompt(
        _compiler_payload(profile),
        prompt_goal=prompt_goal,
        composition=composition,
        style_profile=style_profile or QWEN_VISUAL_SHEET_STYLE,
        references=references,
        sheet_request=_sheet_request_for_role(role),
        extra_negative_constraints=extra_negative_constraints or [],
        reference_locked=reference_locked,
    )


def _resolve_reference_asset_id(references: list[dict[str, Any]]) -> str | None:
    """Return the first attached character-reference asset id, if any.

    A Character Reference Sheet or single reference image attached to the
    character (role ``reference_image`` or canonical ``hero_identity``) is the
    visual identity authority for reference-locked candidate generation.
    """
    for item in references or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("reference_role") or "").strip()
        if role in ("reference_image", "hero_identity"):
            aid = item.get("asset_id") or item.get("assetId")
            if aid:
                return str(aid)
    return None


def _candidate_seed(character_id: str, index: int) -> int:
    """Deterministic-but-distinct seed per candidate for diversity within a model."""
    import hashlib

    digest = hashlib.sha1(f"{character_id}:hero_identity:{index}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % (2**31)


def _candidate_family_executable(family: str) -> bool:
    """True when the family's txt2img workflow is Certified (production-executable)."""
    try:
        from ..image_runtime.certified_registry import get_workflow

        wf = get_workflow(f"{family}.txt2img")
        return bool(wf and wf.status == "Certified")
    except Exception:
        return False


def _no_reference_families_for_style(visual_style: str | None) -> list[str]:
    """Distinct Certified txt2img families for no-reference candidates.

    Anime/realistic-anime styles prefer Illustrious XL first (when Certified),
    then fall back to the default Qwen-2512 / Z-Image order. Non-anime styles
    keep the default order. Only Certified-executable families are returned so
    production paths never route to a non-executable engine.
    """
    style_preferred = ""
    try:
        from ..style_intelligence.registry import preferred_family_for_style

        style_preferred = (preferred_family_for_style(visual_style) or "").strip().lower()
    except Exception:
        style_preferred = ""

    ordered: list[str] = []
    if style_preferred and _candidate_family_executable(style_preferred):
        ordered.append(style_preferred)
    for fam in NO_REFERENCE_TXT2IMG_FAMILIES:
        if fam not in ordered and _candidate_family_executable(fam):
            ordered.append(fam)
    if not ordered:
        # No Certified family resolved — keep the declarative order and let the
        # resolver/compile layer apply its Certified fallback honestly.
        ordered = [style_preferred] + [f for f in NO_REFERENCE_TXT2IMG_FAMILIES if f != style_preferred]
    return ordered


def _build_candidate_routing_plan(
    *,
    candidate_count: int,
    reference_asset_id: str | None,
    visual_style: str | None = None,
) -> list[dict[str, Any]]:
    """Per-candidate routing plan drawn from the Certified READY registry.

    Reference-locked: all candidates route to the Certified reference-capable
    workflow (``zimage.ref_edit``) so the reference pixels participate in
    conditioning. Only one distinct reference-capable Certified model exists
    today, so ``referenceFidelityMode`` is recorded as ``limited`` honestly.
    Illustrious (text-only) is intentionally excluded from reference-locked
    candidates — never silently downgrade reference-conditioned generation to
    text-only.

    No-reference: each distinct Certified txt2img family is used once before any
    reuse; remaining slots reuse a family with a different seed. Anime/realistic-
    anime styles prefer Illustrious XL first. We never fabricate distinctness.
    """
    plan: list[dict[str, Any]] = []
    if reference_asset_id:
        for _i in range(candidate_count):
            plan.append(
                {
                    "modelFamilyPreference": REFERENCE_LOCKED_FAMILY,
                    "workflowKey": REFERENCE_LOCKED_WORKFLOW_KEY,
                    "referenceAssetId": reference_asset_id,
                    "referenceLocked": True,
                    "referenceFidelityMode": REFERENCE_FIDELITY_MODE_LIMITED,
                    "source_asset_id": reference_asset_id,
                    "denoise": REFERENCE_FIDELITY_DENOISE,
                }
            )
        return plan
    distinct = _no_reference_families_for_style(visual_style)
    for i in range(candidate_count):
        fam = distinct[i % len(distinct)]
        plan.append(
            {
                "modelFamilyPreference": fam,
                "workflowKey": f"{fam}.txt2img",
                "referenceAssetId": None,
                "referenceLocked": False,
                "referenceFidelityMode": None,
                "source_asset_id": None,
                "denoise": None,
            }
        )
    return plan


def _workflow_lineage(workflow_key: str) -> dict[str, Any]:
    """Resolve a workflow key to its registry lineage (generator/provider/model)."""
    try:
        from ..image_runtime.certified_registry import get_workflow

        wf = get_workflow(workflow_key)
        if wf:
            caps = dict(wf.capabilities or {})
            return {
                "workflowKey": wf.workflow_key,
                "generator": wf.engine,
                "provider": wf.provider or wf.provider_kind,
                "model": wf.model_family,
                "modelVariant": wf.model_variant,
                "supportsReferences": bool(caps.get("supportsReferences", False)),
            }
    except Exception:
        pass
    return {
        "workflowKey": workflow_key,
        "generator": None,
        "provider": None,
        "model": None,
        "supportsReferences": False,
    }


def _low_reference_fidelity(*, reference_locked: bool, lineage: dict[str, Any]) -> bool:
    """Provenance-based candidate quality gate (Amendment 3, §9).

    Flag a candidate as low reference fidelity when the creator attached a
    reference (expecting visual identity lock) but the resolved workflow
    cannot consume reference pixels — i.e. reference conditioning fell back to
    prompt-text-only. A full pixel-level visual comparison is deferred to a
    later vision-tooling pass; this provenance gate is the honest floor.
    """
    if not reference_locked:
        return False
    return not bool(lineage.get("supportsReferences"))


def _save_pack(db: Session, project_id: str, character_id: str, pack: dict[str, Any]) -> dict[str, Any]:
    pack["updatedAt"] = _now()
    service.upsert_trait(
        db,
        project_id,
        character_id,
        TraitUpsert(
            category="visual_sheet",
            key=PACK_TRAIT_KEY,
            value=_dumps(pack),
            provenance="PROPOSED_BY_CHARACTER_CREATOR",
        ),
    )
    return pack


def heal_pack_references(db: Session, project_id: str, character_id: str) -> int:
    """Ensure visual-sheet roleAssets are attached as Character Profile references.

    Idempotent. Heals packs that completed jobs but left category tabs empty when
    attach was skipped or the UI never refreshed after advance.
    """
    from .models import CharacterReferenceAssetRow

    pack = _load_pack_raw(db, character_id)
    role_assets = pack.get("roleAssets") if isinstance(pack.get("roleAssets"), dict) else {}
    if not role_assets:
        return 0
    existing_rows = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == character_id)
        .all()
    )
    before = {(r.reference_role, r.asset_id) for r in existing_rows}
    attached = 0
    for role, aid in role_assets.items():
        if not role or not aid:
            continue
        if (str(role), str(aid)) in before:
            continue
        try:
            _attach_role(db, project_id, character_id, str(aid), str(role))
            attached += 1
            before.add((str(role), str(aid)))
        except Exception:
            # Role unknown / locked profile — skip; do not fail pack reads
            continue
    return attached


def _load_pack_raw(db: Session, character_id: str) -> dict[str, Any]:
    from .models import CharacterTraitRow

    row = (
        db.query(CharacterTraitRow)
        .filter(
            CharacterTraitRow.character_profile_id == character_id,
            CharacterTraitRow.key == PACK_TRAIT_KEY,
        )
        .order_by(CharacterTraitRow.id.desc())
        .first()
    )
    if not row:
        return {}
    return _loads(row.value, {})


def get_visual_sheet_pack(db: Session, project_id: str, character_id: str) -> dict[str, Any]:
    service.get_profile(db, project_id, character_id)
    data = _load_pack_raw(db, character_id)
    if not data:
        return {"characterId": character_id, "status": "NOT_STARTED", "jobs": {}, "roleAssets": {}}
    # Keep Character Sheet / Close-Ups / etc. tabs populated from pack assets
    healed = heal_pack_references(db, project_id, character_id)
    if healed:
        data = _load_pack_raw(db, character_id) or data
        data["referencesHealed"] = healed
    data["characterId"] = character_id
    return data


def start_visual_sheet_generation(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    include_details: bool = True,
    include_performance: bool = True,
    hero_asset_id: Optional[str] = None,
    candidate_count: int = 1,
    visual_style: Optional[str] = None,
) -> dict[str, Any]:
    """Enqueue real certified image jobs for a Generated Character Image Profile.

    Does not self-approve gates. Owner must approve after assets attach.

    When ``candidate_count`` > 1 and no ``hero_asset_id`` is supplied, N hero
    candidate jobs are enqueued (casting options) and exposed on the pack as
    ``candidates``. ``candidate_count`` defaults to 1, preserving the legacy
    single-hero flow.

    ``visual_style`` (optional) resolves a per-character style profile
    (Live Action / Anime / 3D / ...) that overrides the default
    QWEN_VISUAL_SHEET_STYLE for all compiled prompts in this pack.
    """
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found")
    profile_out = service.get_profile(db, project_id, character_id)
    profile = profile_out.model_dump()
    name = profile.get("name") or "Character"
    char_slug = (profile.get("slug") or name).replace(" ", "_").lower()

    # Resolve the per-character visual style into a style profile once.
    resolved_style_key = visual_style or profile.get("visual_style") or ""
    style_profile = _resolve_style_profile(resolved_style_key)

    # Ensure concept directions exist
    gates = list_gates(db, project_id, character_id)
    concept = (gates.get("gates") or {}).get("concept") or {}
    if concept.get("status") in (None, "NOT_STARTED") or not concept.get("directions"):
        propose_visual_directions(db, project_id, character_id)

    from ..storyboard_jobs import enqueue_imagegen_job

    candidate_count = max(1, int(candidate_count or 1))
    jobs: dict[str, Any] = {}
    role_assets: dict[str, str] = {}
    candidates: list[dict[str, Any]] = []

    # Optional: use existing uploaded canonical sheet as hero baseline (authority), still generate pack from it
    if hero_asset_id:
        asset = db.get(Asset, hero_asset_id)
        if not asset or asset.project_id != project_id or asset.kind != "image":
            raise ValueError("hero_asset_id must be an image asset in this project")
        role_assets["hero_identity"] = hero_asset_id
        # Attach baseline as identity reference (canonical authority) if missing.
        # Accept either the new hero_identity role or legacy hero_portrait rows
        # (covered by the read-time alias in roles.py).
        existing = service.list_references(db, project_id, character_id)
        if not any(r.get("reference_role") in ("hero_identity", "hero_portrait") for r in existing):
            service.attach_reference(
                db,
                project_id,
                character_id,
                ReferenceAttach(
                    asset_id=hero_asset_id,
                    reference_role="hero_identity",
                    source_type="upload",
                    canonical=True,
                    notes="Canonical identity authority sheet (user-approved baseline)",
                ),
            )
    else:
        # Enqueue hero candidate(s): N full-body casting variations when
        # candidate_count > 1, otherwise a single full-body casting image.
        # jobs["hero"] stays a single dict (first candidate) so existing
        # advance/coverage consumers keep working; the full set is mirrored in
        # jobs["hero_candidates"] and pack["candidates"].
        #
        # Hard rule: Character Creator casting candidates are FULL-BODY by
        # default (Amendment 2). The composition block below is authoritative;
        # a close-up reference image will NOT force close-up framing because
        # the composition block is explicit. The user's Character Profile
        # (visual_description) is preserved as authoritative subject identity —
        # the full-body instruction supplements, never rewrites.
        #
        # Amendment 3 — Candidate Diversity + Reference Fidelity:
        # * When a Character Reference / Reference Sheet is attached, the
        #   reference image is the primary visual authority and its PIXELS
        #   participate in conditioning (routed to zimage.ref_edit, the only
        #   Certified reference-capable workflow). The Character Profile
        #   becomes supplemental and must not override visible reference
        #   features.
        # * Candidate variety comes from different Certified generators / seeds
        #   / interpretation — never from changing the character's identity.
        # * Each distinct Certified generator is used once before reuse; we
        #   never fabricate distinctness.
        references = service.list_references(db, project_id, character_id)
        reference_asset_id = _resolve_reference_asset_id(references)
        routing_plan = _build_candidate_routing_plan(
            candidate_count=candidate_count,
            reference_asset_id=reference_asset_id,
            visual_style=resolved_style_key,
        )
        reference_locked = bool(reference_asset_id)
        hero_candidate_jobs: list[dict[str, Any]] = []
        for _i in range(candidate_count):
            composition = dict(FULL_BODY_CASTING_COMPOSITION)
            composition["candidate_index"] = _i
            route = routing_plan[_i]
            hero_prompt = _compile_visual_prompt(
                profile,
                prompt_goal="a cinematic full-body character casting reference",
                composition=composition,
                references=references,
                role="hero_identity",
                extra_negative_constraints=FULL_BODY_CASTING_NEGATIVE_RULES,
                style_profile=style_profile,
                reference_locked=reference_locked,
            )
            seed = _candidate_seed(character_id, _i)
            hero_job = _enqueue_txt2img(
                db,
                project_id,
                character_id=character_id,
                prompt=hero_prompt.prompt,
                negative_prompt=hero_prompt.negative_prompt,
                tag=f"{char_slug}_hero_identity" + (f"_c{_i + 1}" if candidate_count > 1 else ""),
                role="hero_identity",
                model_family_preference=route["modelFamilyPreference"],
                source_asset_id=route.get("source_asset_id"),
                denoise=route.get("denoise"),
                seed=seed,
                prompt_metadata={
                    "promptFamily": hero_prompt.prompt_family,
                    "promptModel": hero_prompt.model_key,
                    "promptValidationOk": hero_prompt.validation.get("ok"),
                    "sheetMode": hero_prompt.metadata.get("sheetMode"),
                    "candidateIndex": _i,
                    "candidateCount": candidate_count,
                    # Amendment 2b: machine-readable composition intent for
                    # lineage/retakes/MAGI. Regeneration inherits this via the
                    # same endpoint. Do not rely on prompt-text parsing.
                    "compositionIntent": COMPOSITION_INTENT_FULL_BODY_CASTING,
                    "fullBody": True,
                    # Amendment 3: per-candidate routing + reference fidelity.
                    "workflowKey": route["workflowKey"],
                    "modelFamily": route["modelFamilyPreference"],
                    "referenceLocked": reference_locked,
                    "referenceAssetId": reference_asset_id,
                    "referenceFidelityMode": route.get("referenceFidelityMode"),
                    "seed": seed,
                },
            )
            lineage = _workflow_lineage(route["workflowKey"])
            low_fidelity = _low_reference_fidelity(reference_locked=reference_locked, lineage=lineage)
            label = "Hero" if candidate_count == 1 else f"Candidate {_i + 1}"
            entry = {
                "jobId": hero_job.id,
                "role": "hero_identity",
                "status": hero_job.status,
                "candidateIndex": _i,
                "label": label,
                "assetId": None,
                "generator": lineage.get("generator"),
                "provider": lineage.get("provider"),
                "model": lineage.get("model"),
                "modelVariant": lineage.get("modelVariant"),
                "workflowKey": route["workflowKey"],
                "seed": seed,
                "referenceAssetIds": [reference_asset_id] if reference_asset_id else [],
                "compositionIntent": COMPOSITION_INTENT_FULL_BODY_CASTING,
                "referenceFidelityMode": route.get("referenceFidelityMode"),
                "referenceLocked": reference_locked,
                "lowReferenceFidelity": low_fidelity,
            }
            hero_candidate_jobs.append(entry)
            candidates.append({
                "assetId": None,
                "jobId": hero_job.id,
                "url": None,
                "label": label,
                "status": hero_job.status,
                "candidateIndex": _i,
                "generator": lineage.get("generator"),
                "provider": lineage.get("provider"),
                "model": lineage.get("model"),
                "modelVariant": lineage.get("modelVariant"),
                "workflowKey": route["workflowKey"],
                "seed": seed,
                "referenceAssetIds": [reference_asset_id] if reference_asset_id else [],
                "compositionIntent": COMPOSITION_INTENT_FULL_BODY_CASTING,
                "referenceFidelityMode": route.get("referenceFidelityMode"),
                "referenceLocked": reference_locked,
                "lowReferenceFidelity": low_fidelity,
            })
        jobs["hero"] = hero_candidate_jobs[0]
        if candidate_count > 1:
            jobs["hero_candidates"] = hero_candidate_jobs

    pack = {
        "schema_version": 2,
        "status": "GENERATING",
        "characterId": character_id,
        "projectId": project_id,
        "engine": "multi_model",
        "workflows": ["character_sheet", "sequential_identity_prompts", "multi_model_routing"],
        "identityLock": KORRI_LOCK if char_slug == "korri" else "",
        "referenceEditReplaced": True,
        "referenceLocked": bool(reference_asset_id) if not hero_asset_id else False,
        "jobs": jobs,
        "roleAssets": role_assets,
        "candidates": candidates,
        "candidateCount": candidate_count,
        "includeDetails": include_details,
        "includePerformance": include_performance,
        "characterName": name,
        "characterSlug": char_slug,
        "createdAt": _now(),
        "phase": "hero" if "hero" in jobs else "sheet_ready",
        "mock": False,
    }
    return _save_pack(db, project_id, character_id, pack)


def _job_params(job: Job) -> dict[str, Any]:
    return _loads(job.params_json, {})


def advance_visual_sheet_pack(db: Session, project_id: str, character_id: str) -> dict[str, Any]:
    """Poll jobs, attach completed assets to roles, enqueue next phase (sheet → details → performance)."""
    pack = get_visual_sheet_pack(db, project_id, character_id)
    if pack.get("status") in ("NOT_STARTED",):
        raise ValueError("No visual sheet pack started")
    if pack.get("status") == "READY_FOR_OWNER":
        return pack

    jobs = dict(pack.get("jobs") or {})
    role_assets = dict(pack.get("roleAssets") or {})
    char_slug = pack.get("characterSlug") or "character"
    profile = service.get_profile(db, project_id, character_id).model_dump()
    style_profile = _resolve_style_profile(profile.get("visual_style") or "")

    # Resolve hero job
    hero_meta = jobs.get("hero")
    if hero_meta and hero_meta.get("jobId"):
        job = db.get(Job, hero_meta["jobId"])
        if job:
            hero_meta["status"] = job.status
            if job.status == "done":
                params = _job_params(job)
                aid = params.get("output_asset_id")
                if aid:
                    role_assets["hero_identity"] = aid
                    _attach_role(db, project_id, character_id, aid, "hero_identity")
                    hero_meta["assetId"] = aid
            elif job.status == "failed":
                pack["status"] = "FAILED"
                pack["error"] = job.message or "hero generation failed"
                pack["jobs"] = jobs
                pack["roleAssets"] = role_assets
                return _save_pack(db, project_id, character_id, pack)
        jobs["hero"] = hero_meta

    # Poll sibling hero candidates (only present when candidate_count > 1)
    hero_candidates = jobs.get("hero_candidates")
    if isinstance(hero_candidates, list):
        for item in hero_candidates:
            job = db.get(Job, item.get("jobId"))
            if not job:
                continue
            item["status"] = job.status
            if job.status == "done":
                aid = _job_params(job).get("output_asset_id")
                if aid:
                    item["assetId"] = aid
        # Preserve per-candidate lineage (generator/provider/model/workflowKey/
        # seed/referenceAssetIds/compositionIntent/referenceFidelityMode) recorded
        # at enqueue time — only update the live status/assetId fields above.
        pack["candidates"] = [
            {
                "assetId": item.get("assetId"),
                "jobId": item.get("jobId"),
                "url": None,
                "label": item.get("label") or "Candidate",
                "status": item.get("status"),
                "candidateIndex": item.get("candidateIndex"),
                "generator": item.get("generator"),
                "provider": item.get("provider"),
                "model": item.get("model"),
                "modelVariant": item.get("modelVariant"),
                "workflowKey": item.get("workflowKey"),
                "seed": item.get("seed"),
                "referenceAssetIds": item.get("referenceAssetIds") or [],
                "compositionIntent": item.get("compositionIntent"),
                "referenceFidelityMode": item.get("referenceFidelityMode"),
                "referenceLocked": bool(item.get("referenceLocked")),
                "lowReferenceFidelity": bool(item.get("lowReferenceFidelity")),
            }
            for item in hero_candidates
        ]

    hero_id = role_assets.get("hero_identity") or role_assets.get("hero_portrait")
    if not hero_id:
        pack["jobs"] = jobs
        pack["roleAssets"] = role_assets
        pack["phase"] = "awaiting_hero"
        pack["status"] = "GENERATING"
        return _save_pack(db, project_id, character_id, pack)

    # Coverage pack: sequential Qwen-Image-2512 txt2img per role with compiled identity prompts.
    coverage_specs = _coverage_role_specs()
    if "coverage" not in jobs:
        cov_jobs = []
        references = service.list_references(db, project_id, character_id)
        for role, prompt_goal, composition in coverage_specs:
            if role in role_assets:
                continue
            package = _compile_visual_prompt(
                profile,
                prompt_goal=prompt_goal,
                composition=composition,
                references=references,
                role=role,
                style_profile=style_profile,
            )
            j = _enqueue_txt2img(
                db,
                project_id,
                character_id=character_id,
                prompt=package.prompt,
                negative_prompt=package.negative_prompt,
                tag=f"{char_slug}_{role}",
                role=role,
                prompt_metadata={
                    "promptFamily": package.prompt_family,
                    "promptModel": package.model_key,
                    "promptValidationOk": package.validation.get("ok"),
                    "sheetMode": package.metadata.get("sheetMode"),
                },
            )
            cov_jobs.append({"jobId": j.id, "role": role, "status": j.status})
        jobs["coverage"] = cov_jobs
        pack["phase"] = "turnaround_facial"
        pack["workflows"] = list(
            dict.fromkeys([*(pack.get("workflows") or []), "qwen2512.txt2img", "coverage_pack"])
        )

    if isinstance(jobs.get("coverage"), list):
        for item in jobs["coverage"]:
            job = db.get(Job, item["jobId"])
            if not job:
                continue
            item["status"] = job.status
            if job.status == "done":
                aid = _job_params(job).get("output_asset_id")
                role = item.get("role")
                if aid and role:
                    role_assets[role] = aid
                    _attach_role(db, project_id, character_id, aid, role)
                    item["assetId"] = aid
            elif job.status == "failed":
                # Resilient Generation: retry once per role before platform NO-GO
                retries = int(item.get("retries") or 0)
                role = item.get("role") or ""
                if retries < 1 and role:
                    spec = next((entry for entry in coverage_specs if entry[0] == role), None)
                    if spec:
                        _, prompt_goal, composition = spec
                        package = _compile_visual_prompt(
                            profile,
                            prompt_goal=prompt_goal,
                            composition=composition,
                            references=service.list_references(db, project_id, character_id),
                            role=role,
                            style_profile=style_profile,
                        )
                        j = _enqueue_txt2img(
                            db,
                            project_id,
                            character_id=character_id,
                            prompt=package.prompt,
                            negative_prompt=package.negative_prompt,
                            tag=f"{char_slug}_{role}_retry",
                            role=role,
                            prompt_metadata={
                                "promptFamily": package.prompt_family,
                                "promptModel": package.model_key,
                                "promptValidationOk": package.validation.get("ok"),
                                "sheetMode": package.metadata.get("sheetMode"),
                            },
                        )
                        item["jobId"] = j.id
                        item["status"] = j.status
                        item["retries"] = retries + 1
                        item["priorError"] = job.message or "failed"
                        continue
                pack["status"] = "FAILED"
                pack["error"] = (
                    f"coverage {item.get('role')}: correction workflow exhausted — "
                    f"{job.message or 'failed'} (platform/job failure after retry)"
                )
                pack["jobs"] = jobs
                pack["roleAssets"] = role_assets
                return _save_pack(db, project_id, character_id, pack)

    sheet_done = bool(jobs.get("coverage")) and all(
        i.get("status") == "done" for i in (jobs.get("coverage") or [])
    )
    if sheet_done and pack.get("includeDetails") and "details" not in jobs:
        detail_jobs = []
        references = service.list_references(db, project_id, character_id)
        for role, prompt_goal, composition in _detail_role_specs():
            if role in role_assets:
                continue
            package = _compile_visual_prompt(
                profile,
                prompt_goal=prompt_goal,
                composition=composition,
                references=references,
                role=role,
                style_profile=style_profile,
            )
            j = _enqueue_txt2img(
                db,
                project_id,
                character_id=character_id,
                prompt=package.prompt,
                negative_prompt=package.negative_prompt,
                tag=f"{char_slug}_{role}",
                role=role,
                prompt_metadata={
                    "promptFamily": package.prompt_family,
                    "promptModel": package.model_key,
                    "promptValidationOk": package.validation.get("ok"),
                    "sheetMode": package.metadata.get("sheetMode"),
                },
            )
            detail_jobs.append({"jobId": j.id, "role": role, "status": j.status})
        jobs["details"] = detail_jobs
        pack["phase"] = "details"
        pack["workflows"] = list(
            dict.fromkeys([*(pack.get("workflows") or []), "qwen2512.txt2img", "detail_pack"])
        )

    if isinstance(jobs.get("details"), list):
        for item in jobs["details"]:
            job = db.get(Job, item["jobId"])
            if not job:
                continue
            item["status"] = job.status
            if job.status == "done":
                aid = _job_params(job).get("output_asset_id")
                role = item.get("role")
                if aid and role:
                    role_assets[role] = aid
                    _attach_role(db, project_id, character_id, aid, role)
                    item["assetId"] = aid

    details_done = True
    if pack.get("includeDetails"):
        details = jobs.get("details")
        if details is None:
            details_done = False
        else:
            details_done = all(i.get("status") == "done" for i in details) and not any(
                i.get("status") == "failed" for i in details
            )
            if any(i.get("status") == "failed" for i in details):
                pack["status"] = "FAILED"
                pack["error"] = "one or more detail jobs failed"
                pack["jobs"] = jobs
                pack["roleAssets"] = role_assets
                return _save_pack(db, project_id, character_id, pack)

    if sheet_done and details_done and pack.get("includePerformance") and "performance" not in jobs:
        perf_jobs = []
        references = service.list_references(db, project_id, character_id)
        for role, prompt_goal, composition in _performance_role_specs():
            package = _compile_visual_prompt(
                profile,
                prompt_goal=prompt_goal,
                composition=composition,
                references=references,
                role=role,
                extra_negative_constraints=["collage", "grid"] if role == "expression_sheet" else None,
                style_profile=style_profile,
            )
            j = _enqueue_txt2img(
                db,
                project_id,
                character_id=character_id,
                prompt=package.prompt,
                negative_prompt=package.negative_prompt,
                tag=f"{char_slug}_{role}",
                role=role,
                prompt_metadata={
                    "promptFamily": package.prompt_family,
                    "promptModel": package.model_key,
                    "promptValidationOk": package.validation.get("ok"),
                    "sheetMode": package.metadata.get("sheetMode"),
                },
            )
            perf_jobs.append({"jobId": j.id, "role": role, "status": j.status})
        jobs["performance"] = perf_jobs
        pack["phase"] = "performance"
        pack["workflows"] = list(
            dict.fromkeys([*(pack.get("workflows") or []), "qwen2512.txt2img", "performance_pack"])
        )

    if isinstance(jobs.get("performance"), list):
        for item in jobs["performance"]:
            job = db.get(Job, item["jobId"])
            if not job:
                continue
            item["status"] = job.status
            if job.status == "done":
                aid = _job_params(job).get("output_asset_id")
                role = item.get("role")
                if aid and role:
                    role_assets[role] = aid
                    _attach_role(db, project_id, character_id, aid, role)
                    item["assetId"] = aid

    perf_done = True
    if pack.get("includePerformance"):
        perf = jobs.get("performance")
        if perf is None:
            perf_done = False
        else:
            perf_done = all(i.get("status") == "done" for i in perf)

    # Propose gates with asset ids (awaiting owner — never self-approve)
    if sheet_done and details_done and perf_done:
        _propose_gates_with_assets(db, project_id, character_id, role_assets)
        pack["status"] = "READY_FOR_OWNER"
        pack["phase"] = "awaiting_owner_approval"
        missing = [r for r in REQUIRED_COVERAGE_ROLES if r not in role_assets]
        pack["requiredCoverageMissing"] = missing
        pack["requiredCoverageComplete"] = len(missing) == 0

    pack["jobs"] = jobs
    pack["roleAssets"] = role_assets
    if pack.get("status") != "READY_FOR_OWNER" and pack.get("status") != "FAILED":
        pack["status"] = "GENERATING"
    return _save_pack(db, project_id, character_id, pack)


def owner_approve_visual_sheet_gates(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    approved_by: str = "owner",
    select_direction_id: str = "wild_sun_sprite",
) -> dict[str, Any]:
    """Owner-only: approve concept + image gates that have real assetIds from the pack."""
    if not approved_by:
        raise ValueError("approved_by required — Character Creator cannot self-approve")
    pack = get_visual_sheet_pack(db, project_id, character_id)
    role_assets = dict(pack.get("roleAssets") or {})
    if not role_assets:
        raise ValueError("No generated role assets to approve")

    gates = list_gates(db, project_id, character_id)
    concept = (gates.get("gates") or {}).get("concept") or {}
    if concept.get("status") != "OWNER_APPROVED":
        dirs = concept.get("directions") or []
        if not dirs:
            propose_visual_directions(db, project_id, character_id)
            gates = list_gates(db, project_id, character_id)
            concept = (gates.get("gates") or {}).get("concept") or {}
            dirs = concept.get("directions") or []
        did = select_direction_id
        ids = {d.get("id") for d in dirs}
        if did not in ids and dirs:
            did = dirs[0]["id"]
        owner_select_concept(
            db,
            project_id,
            character_id,
            direction_id=did,
            approved_by=approved_by,
            notes="Owner approved concept for Generated Character Image Profile",
        )

    approved = {}
    for gate, roles in GATE_ROLE_GROUPS.items():
        aids = [role_assets[r] for r in roles if r in role_assets]
        if not aids:
            continue
        approved[gate] = set_gate_status(
            db,
            project_id,
            character_id,
            gate,
            status="OWNER_APPROVED",
            asset_ids=aids,
            approved_by=approved_by,
            notes=f"Owner approved generated visual pack assets for {gate}",
        )

    pack["status"] = "OWNER_APPROVED"
    pack["ownerApprovedBy"] = approved_by
    pack["ownerApprovedAt"] = _now()
    _save_pack(db, project_id, character_id, pack)
    return {
        "ok": True,
        "characterId": character_id,
        "approvedGates": list(approved.keys()),
        "roleAssets": role_assets,
        "gates": list_gates(db, project_id, character_id),
    }


def _propose_gates_with_assets(
    db: Session, project_id: str, character_id: str, role_assets: dict[str, str]
) -> None:
    for gate, roles in GATE_ROLE_GROUPS.items():
        aids = [role_assets[r] for r in roles if r in role_assets]
        if not aids:
            continue
        set_gate_status(
            db,
            project_id,
            character_id,
            gate,
            status="AWAITING_OWNER",
            asset_ids=aids,
            notes="Generated Character Image Profile ready for owner review",
        )


def _attach_role(db: Session, project_id: str, character_id: str, asset_id: str, role: str) -> None:
    from .models import CharacterReferenceAssetRow

    # Query directly — do not call service.list_references (that heals and can recurse).
    dup = (
        db.query(CharacterReferenceAssetRow)
        .filter(
            CharacterReferenceAssetRow.character_profile_id == character_id,
            CharacterReferenceAssetRow.reference_role == role,
            CharacterReferenceAssetRow.asset_id == asset_id,
        )
        .first()
    )
    if dup:
        return
    service.attach_reference(
        db,
        project_id,
        character_id,
        ReferenceAttach(
            asset_id=asset_id,
            reference_role=role,
            source_type="generation",
            canonical=False,
            notes=f"Generated Character Image Profile · {role}",
        ),
    )


def _enqueue_character_sheet(
    db: Session,
    project_id: str,
    *,
    source_asset_id: str,
    character_name: str,
    extra_prompt: str,
) -> Job:
    payload = {
        "source_asset_id": source_asset_id,
        "character_name": character_name,
        "seed": -1,
        "width": 1024,
        "height": 1024,
        "extra_prompt": extra_prompt,
    }
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=None,
        kind="character_sheet",
        status="queued",
        progress=0.0,
        stage="Queued",
        message=json.dumps(payload),
        params_json=json.dumps(payload),
    )
    db.add(job)
    db.commit()
    try:
        from ..codirector.executive.imagegen_adapter import schedule_job_queue_enqueue

        schedule_job_queue_enqueue(job.id)
    except Exception:
        pass
    db.refresh(job)
    return job


def _enqueue_txt2img(
    db: Session,
    project_id: str,
    *,
    character_id: str,
    prompt: str,
    negative_prompt: str,
    tag: str,
    role: str,
    prompt_metadata: dict[str, Any] | None = None,
    model_family_preference: str = "qwen2512",
    source_asset_id: str | None = None,
    denoise: float | None = None,
    seed: int | None = None,
) -> Job:
    from ..storyboard_jobs import enqueue_imagegen_job

    creative_context = {
        "objective": "character_sheet",
        "characterId": character_id,
        "role": role,
        "workflowKey": (prompt_metadata or {}).get("workflowKey") or f"{model_family_preference}.txt2img",
        "sequentialMethod": "method_b",
    }
    if prompt_metadata:
        creative_context.update(prompt_metadata)

    body: dict[str, Any] = {
        "prompt": prompt,
        "negative_prompt": negative_prompt or DEFAULT_NEGATIVE_PROMPT,
        "width": 1024,
        "height": 1024,
        "tag": tag,
        "modelFamilyPreference": model_family_preference,
        "purpose": "character_sheet",
        "presetId": "builtin-character-sheet",
        "creativeContext": creative_context,
    }
    # Reference-locked candidates route to a reference-capable edit workflow
    # (zimage.ref_edit) by supplying the reference asset as the source image so
    # its PIXELS participate in conditioning — not merely a filename in the prompt.
    if source_asset_id:
        body["source_asset_id"] = source_asset_id
    if denoise is not None:
        body["denoise"] = denoise
    if seed is not None:
        body["seed"] = seed
    return enqueue_imagegen_job(db, project_id, body)


def _coverage_role_specs() -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (
            "full_body_front",
            "a production turnaround full-body front reference",
            {
                "shot_type": "turnaround reference",
                "framing": "full body",
                "camera_angle": "eye level",
                "orientation": "front view",
                "environment": "plain gray background",
                "lighting": "soft studio light",
                "pose": "standing facing camera in a neutral production turnaround pose",
                "focus": "wardrobe silhouette and body proportions",
            },
        ),
        (
            "full_body_side_left",
            "a production turnaround full-body side reference",
            {
                "shot_type": "turnaround reference",
                "framing": "full body",
                "camera_angle": "eye level",
                "orientation": "left side profile",
                "environment": "plain gray background",
                "lighting": "soft studio light",
                "pose": "standing in a neutral side-profile turnaround pose",
                "focus": "profile silhouette and hair construction",
            },
        ),
        (
            "full_body_back",
            "a production turnaround full-body back reference",
            {
                "shot_type": "turnaround reference",
                "framing": "full body",
                "camera_angle": "eye level",
                "orientation": "back view",
                "environment": "plain gray background",
                "lighting": "soft studio light",
                "pose": "standing facing away in a neutral turnaround pose",
                "focus": "rear wardrobe silhouette and ponytail construction",
            },
        ),
        (
            "closeup_front",
            "a facial close-up front reference",
            {
                "shot_type": "close-up portrait reference",
                "framing": "face and shoulders",
                "camera_angle": "eye level",
                "orientation": "front view",
                "environment": "plain gray background",
                "lighting": "soft studio portrait light",
                "pose": "front-facing portrait with ears readable",
                "focus": "eyes, ears, markings, and earrings",
            },
        ),
        (
            "closeup_side_left",
            "a facial close-up side reference",
            {
                "shot_type": "close-up portrait reference",
                "framing": "head and shoulders",
                "camera_angle": "eye level",
                "orientation": "left side profile",
                "environment": "plain gray background",
                "lighting": "soft studio portrait light",
                "pose": "left profile portrait with steady expression",
                "focus": "ear silhouette, profile lines, and side hair construction",
            },
        ),
        (
            "closeup_back",
            "a facial close-up back reference",
            {
                "shot_type": "close-up portrait reference",
                "framing": "rear head and shoulders",
                "camera_angle": "eye level",
                "orientation": "back view",
                "environment": "plain gray background",
                "lighting": "soft studio portrait light",
                "pose": "rear close-up with neutral posture",
                "focus": "hair construction and ear silhouette from behind",
            },
        ),
    ]


def _detail_role_specs() -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (
            "skin_closeup",
            "an extreme close-up skin material reference",
            {
                "shot_type": "material reference",
                "framing": "extreme close-up",
                "camera_angle": "eye level",
                "environment": "plain gray background",
                "lighting": "soft studio light",
                "focus": "skin tone, texture, and markings clarity",
            },
        ),
        (
            "hair_front",
            "a hair construction front reference",
            {
                "shot_type": "hair reference",
                "framing": "head close-up",
                "camera_angle": "eye level",
                "orientation": "front view",
                "environment": "plain gray background",
                "lighting": "soft studio light",
                "focus": "parting, ties, and front ponytail construction",
            },
        ),
        (
            "hair_side",
            "a hair construction side reference",
            {
                "shot_type": "hair reference",
                "framing": "head close-up",
                "camera_angle": "eye level",
                "orientation": "left side profile",
                "environment": "plain gray background",
                "lighting": "soft studio light",
                "focus": "side silhouette and ponytail shape",
            },
        ),
        (
            "hair_back",
            "a hair construction back reference",
            {
                "shot_type": "hair reference",
                "framing": "head close-up",
                "camera_angle": "eye level",
                "orientation": "back view",
                "environment": "plain gray background",
                "lighting": "soft studio light",
                "focus": "rear ponytail construction and tie placement",
            },
        ),
        (
            "wardrobe_reference",
            "a wardrobe material reference",
            {
                "shot_type": "wardrobe reference",
                "framing": "mid-to-full body",
                "camera_angle": "eye level",
                "environment": "plain gray background",
                "lighting": "soft studio light",
                "pose": "neutral stance that clearly presents the outfit",
                "focus": "cloth construction, wraps, sash, and sandals",
            },
        ),
        (
            "accessory_reference",
            "an accessory and markings reference",
            {
                "shot_type": "accessory close-up",
                "framing": "close-up",
                "camera_angle": "eye level",
                "environment": "plain gray background",
                "lighting": "soft studio light",
                "focus": "wooden accessories and light-circuitry markings readability",
            },
        ),
    ]


def _performance_role_specs() -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (
            "expression_sheet",
            "a single-frame expression reference with mischievous facial readability",
            {
                "shot_type": "expression reference",
                "framing": "face and shoulders",
                "camera_angle": "eye level",
                "environment": "plain gray background",
                "lighting": "soft studio portrait light",
                "pose": "steady portrait pose",
                "expression": "mischievous smirk with teasing head tilt",
                "focus": "clean facial performance with no multi-panel collage",
            },
        ),
        (
            "pose_sheet",
            "a full-body signature pose reference",
            {
                "shot_type": "pose reference",
                "framing": "full body",
                "camera_angle": "eye level",
                "environment": "plain gray background",
                "lighting": "soft studio light",
                "pose": "hands on hips with teasing head tilt and weight on one hip",
                "focus": "readable silhouette and posture language",
            },
        ),
    ]


def _resolve_sheet_roles_by_tag(db: Session, project_id: str, character_name: str) -> dict[str, str]:
    from ..workflows.image_tools import CHARACTER_SHEET_ROLE_MAP

    prefix = character_name.replace(" ", "_")
    out: dict[str, str] = {}
    assets = db.query(Asset).filter(Asset.project_id == project_id, Asset.kind == "image").all()
    for view_key, role in CHARACTER_SHEET_ROLE_MAP.items():
        suffix = {
            "front": "front",
            "side": "side",
            "back": "back",
            "front_closeup": "front_closeup",
            "side_closeup": "side_closeup",
            "back_closeup": "back_closeup",
        }.get(view_key, view_key)
        tag = f"{prefix}_{suffix}"
        hit = next((a for a in assets if a.tag == tag), None)
        if hit:
            out[role] = hit.id
    return out
