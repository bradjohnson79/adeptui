"""Generated Character Image Profile — real Image Product / character-sheet pack.

Canonical identity (korri.v1 / approved sheet) remains authority.
Generated views prove Character Creator can produce visual coverage via certified Qwen-Image-2512.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
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

# --- Stage 2 Identity-Lock + Style Refinement Pipeline ---
#
# When a Character Reference is attached, Stage 1 runs a reference-capable
# identity engine (e.g. zimage.ref_edit) to lock the character identity. Stage 2
# is optional: it uses a real img2img/edit/refinement workflow (e.g. flux.img2img)
# to improve visual style / finish while preserving identity. Stage 2 receives
# the Stage 1 output as its source image, never the original reference.
# Truthfulness Law: if no real compatible Stage 2 workflow exists, Stage 2 is
# not offered and the Stage 1 result is used directly.
STAGE2_DEFAULT_DENOISE = 0.35
STAGE2_IDENTITY_PRESERVATION_PROMPT = (
    "Preserve the exact character identity, face, hair, eye color, ears, skin, "
    "body proportions, wardrobe, accessories, markings, and silhouette. "
    "Only refine visual style, finish, lighting, and texture. Do not redesign."
)
STAGE2_STYLE_ONLY_NEGATIVE = (
    "different face, different hair, different eyes, different species, "
    "different body proportions, different wardrobe, different silhouette, "
    "redesign, reinterpret"
)

# --- Phase 5 — Character Creator Simplification: composed 4-view sheet ---
#
# Each casting candidate produces ONE canonical composed Character Sheet asset.
# The 4 required views (front full body, side full body, back full body, front
# close-up) are generated per candidate, validated for identity consistency,
# then composed into a 2x2 grid (PIL) and ingested as a single Library asset.
# The 4 source view assets are retained as lineage; the creator-facing
# candidate ``assetId`` is the composed sheet (Amendment 4 / Phase 5).
CANDIDATE_SHEET_VIEW_ROLES: tuple[str, ...] = (
    "hero_identity",
    "full_body_side_left",
    "full_body_back",
    "closeup_front",
)

# 2x2 grid layout (row-major): front, side / back, front-close-up.
CHARACTER_SHEET_GRID_COLS = 2
CHARACTER_SHEET_GRID_ROWS = 2
CHARACTER_SHEET_TILE_SIZE = 1024

COMPOSITION_INTENT_CHARACTER_SHEET = "character_sheet_composed"

# Certified families that are text-only (cannot consume reference pixels). A
# reference-locked candidate must NEVER route to one of these — enforced in
# ``_build_candidate_routing_plan`` as the reference-first hierarchy guard so
# an attached reference never silently downgrades to a text-only family.
TEXT_ONLY_FAMILIES: frozenset[str] = frozenset({"illustrious"})


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


def _family_supports_references(family: str) -> bool:
    """True when the family has a Certified workflow that can consume reference pixels.

    Consults the Certified registry's ``supportsReferences`` capability. Used
    by the reference-first routing guard so a reference-locked candidate is
    never routed to a text-only family (e.g. Illustrious) that would silently
    drop reference conditioning.
    """
    try:
        from ..image_runtime.certified_registry import list_workflows

        for wf in list_workflows(model_family=family):
            if wf.status != "Certified":
                continue
            if bool((wf.capabilities or {}).get("supportsReferences", False)):
                return True
    except Exception:
        return False
    return False


def _family_supports_stage2(family: str) -> bool:
    """True when the family has a Certified real img2img/edit workflow.

    A real Stage 2 workflow must accept a source image and perform a genuine
    image-to-image/edit pass (not a text-only generation that claims to refine).
    """
    if not family:
        return False
    try:
        from ..image_runtime.certified_registry import get_workflow

        # Candidate Stage 2 keys in priority order. Only certify the exact keys
        # that are real and tested for this family.
        candidates = [f"{family}.img2img", f"{family}.edit"]
        for key in candidates:
            wf = get_workflow(key)
            if wf and wf.status == "Certified" and (wf.capabilities or {}).get("supportsEditing"):
                return True
    except Exception:
        return False
    return False


def _stage2_workflow_key(family: str) -> str | None:
    """Return the Certified Stage 2 workflow key for a family, or None."""
    if not family:
        return None
    try:
        from ..image_runtime.certified_registry import get_workflow

        candidates = [f"{family}.img2img", f"{family}.edit"]
        for key in candidates:
            wf = get_workflow(key)
            if wf and wf.status == "Certified" and (wf.capabilities or {}).get("supportsEditing"):
                return key
    except Exception:
        return None
    return None


def _build_candidate_routing_plan(
    *,
    candidate_count: int,
    reference_asset_id: str | None,
    visual_style: str | None = None,
    generator_sources: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Per-candidate routing plan drawn from the Certified READY registry.

    Reference-first hierarchy (Amendment 3 + Phase 5): when a reference image is
    attached it is the visual authority — Stage 1 routes to a Certified
    reference-capable workflow (``zimage.ref_edit``) so reference PIXELS
    participate in conditioning. An optional Stage 2 style engine may then refine
    the Stage 1 output via a real img2img/edit workflow. Stage 2 receives the
    Stage 1 output, never the original reference.

    A reference-locked candidate NEVER routes to a text-only family (e.g.
    Illustrious) for Stage 1 — enforced explicitly below. Stage 2 is only enabled
    when a real certified editing workflow exists for the selected family.

    No-reference: each distinct Certified txt2img family is used once before any
    reuse; remaining slots reuse a family with a different seed. Anime/realistic-
    anime styles prefer Illustrious XL first. We never fabricate distinctness.
    """
    # User Control Law: when the caller explicitly passes generator_sources with
    # BOTH pools disabled, refuse to enqueue any jobs (zero-job guarantee) rather
    # than silently falling back. Omitted (None) preserves legacy default routing.
    if generator_sources is not None:
        _local = generator_sources.get("local")
        _api = generator_sources.get("api")
        if not _local and not _api:
            raise ValueError(
                "No image generator enabled. Enable a Local or Cloud generator to create character sheets."
            )
    plan: list[dict[str, Any]] = []
    # Explicit Local Generator selection (User Control Law + user authority):
    # when the creator picked a specific local family (not Auto Select), honor it
    # for no-reference candidates instead of style routing. ""/"auto" → style routing.
    chosen_local = ""
    chosen_stage2_family = ""
    stage2_enabled = False
    if generator_sources is not None:
        _loc = generator_sources.get("local")
        if isinstance(_loc, dict):
            chosen_local = str(_loc.get("family") or "").strip().lower()
            chosen_stage2_family = str(_loc.get("stage2Family") or "").strip().lower()
            stage2_enabled = bool(_loc.get("stage2Enabled"))
    if chosen_local in {"", "auto"}:
        chosen_local = ""
    if chosen_stage2_family in {"", "auto"}:
        chosen_stage2_family = ""

    # Resolve Stage 2 config (if requested and real).
    stage2: dict[str, Any] | None = None
    if stage2_enabled and chosen_stage2_family:
        stage2_key = _stage2_workflow_key(chosen_stage2_family)
        if stage2_key:
            stage2 = {
                "modelFamilyPreference": chosen_stage2_family,
                "workflowKey": stage2_key,
                "referenceAssetId": None,
                "referenceLocked": False,
                "referenceFidelityMode": None,
                "source_asset_id": None,  # set to Stage 1 output at runtime
                "denoise": STAGE2_DEFAULT_DENOISE,
            }

    if reference_asset_id:
        # Reference-first guard: the resolved family must be reference-capable
        # and must NOT be a text-only family. zimage.ref_edit is the only
        # Certified reference-capable workflow today; this guard keeps the
        # hierarchy honest as more families become Certified.
        if REFERENCE_LOCKED_FAMILY in TEXT_ONLY_FAMILIES or not _family_supports_references(
            REFERENCE_LOCKED_FAMILY
        ):
            raise RuntimeError(
                "Reference-locked candidate routing requires a Certified "
                "reference-capable workflow; zimage.ref_edit is not reference-capable "
                "or is text-only. Refusing to silently downgrade reference conditioning."
            )
        # Reference-locked: only reference-capable families are eligible. If the
        # creator explicitly chose a text-only family for a reference-locked
        # generation, refuse rather than silently downgrade reference conditioning.
        if chosen_local and (
            chosen_local in TEXT_ONLY_FAMILIES or not _family_supports_references(chosen_local)
        ):
            raise ValueError(
                f"{chosen_local} requires text-to-image generation and cannot use the attached Character Reference."
            )
        for _i in range(candidate_count):
            plan.append(
                {
                    "stage1": {
                        "modelFamilyPreference": REFERENCE_LOCKED_FAMILY,
                        "workflowKey": REFERENCE_LOCKED_WORKFLOW_KEY,
                        "referenceAssetId": reference_asset_id,
                        "referenceLocked": True,
                        "referenceFidelityMode": REFERENCE_FIDELITY_MODE_LIMITED,
                        "source_asset_id": reference_asset_id,
                        "denoise": REFERENCE_FIDELITY_DENOISE,
                    },
                    "stage2": stage2,
                    "stage2Enabled": bool(stage2),
                }
            )
        return plan
    if chosen_local and _candidate_family_executable(chosen_local):
        # Honor the explicit Certified local family for every candidate (different seeds).
        for _i in range(candidate_count):
            plan.append(
                {
                    "stage1": {
                        "modelFamilyPreference": chosen_local,
                        "workflowKey": f"{chosen_local}.txt2img",
                        "referenceAssetId": None,
                        "referenceLocked": False,
                        "referenceFidelityMode": None,
                        "source_asset_id": None,
                        "denoise": None,
                    },
                    "stage2": stage2,
                    "stage2Enabled": bool(stage2),
                }
            )
        return plan
    distinct = _no_reference_families_for_style(visual_style)
    for i in range(candidate_count):
        fam = distinct[i % len(distinct)]
        plan.append(
            {
                "stage1": {
                    "modelFamilyPreference": fam,
                    "workflowKey": f"{fam}.txt2img",
                    "referenceAssetId": None,
                    "referenceLocked": False,
                    "referenceFidelityMode": None,
                    "source_asset_id": None,
                    "denoise": None,
                },
                "stage2": stage2,
                "stage2Enabled": bool(stage2),
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


def _candidate_sheet_lineage(candidate: dict[str, Any], view_jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a dual-stage lineage record for the composed Character Sheet.

    Records the Stage 1 identity engine (required) and the Stage 2 style engine
    (if enabled) per final view, including the source asset chain.
    """
    stage1_lineage = _workflow_lineage(str(candidate.get("workflowKey") or ""))
    stage2_lineage = _workflow_lineage(str(candidate.get("stage2WorkflowKey") or ""))
    view_lineages: list[dict[str, Any]] = []
    for vj in view_jobs:
        vlineage: dict[str, Any] = {
            "role": vj.get("role"),
            "viewIndex": vj.get("viewIndex"),
            "stage1": {
                "workflowKey": vj.get("workflowKey"),
                "modelFamily": vj.get("modelFamily"),
                "assetId": vj.get("assetId"),
                "seed": vj.get("seed"),
            },
        }
        if vj.get("stage2Enabled"):
            vlineage["stage2"] = {
                "workflowKey": vj.get("stage2WorkflowKey") or stage2_lineage.get("workflowKey"),
                "modelFamily": vj.get("stage2ModelFamily") or stage2_lineage.get("modelFamily"),
                "assetId": vj.get("stage2AssetId"),
                "jobId": vj.get("stage2JobId"),
                "sourceAssetId": vj.get("assetId"),
                "seed": vj.get("seed"),
            }
        view_lineages.append(vlineage)
    return {
        "stage1": stage1_lineage,
        "stage2": stage2_lineage if candidate.get("stage2Enabled") else None,
        "stage2Enabled": bool(candidate.get("stage2Enabled")),
        "stage2Failed": bool(candidate.get("stage2Failed")),
        "referenceLocked": bool(candidate.get("referenceLocked")),
        "referenceFidelityMode": candidate.get("referenceFidelityMode"),
        "referenceAssetIds": list(candidate.get("referenceAssetIds") or []),
        "views": view_lineages,
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


# --- Phase 5: composed 4-view Character Sheet helpers ---


def _candidate_view_specs() -> list[tuple[str, str, dict[str, Any], list[str] | None]]:
    """The 4 required views per casting candidate, in 2x2 grid order.

    Order is row-major: front, side, back, front-close-up. The front view
    reuses the full-body casting composition (Amendment 2) so the canonical
    "full body casting" / "no close-up" framing is preserved on the primary
    tile; the remaining views use production turnaround/close-up compositions
    drawn from the coverage pack so all 4 tiles share identity-safe framing.
    """
    coverage = {role: (goal, comp) for role, goal, comp in _coverage_role_specs()}
    side = coverage["full_body_side_left"]
    back = coverage["full_body_back"]
    closeup = coverage["closeup_front"]
    return [
        (
            "hero_identity",
            "a cinematic full-body character casting reference",
            dict(FULL_BODY_CASTING_COMPOSITION),
            list(FULL_BODY_CASTING_NEGATIVE_RULES),
        ),
        ("full_body_side_left", side[0], dict(side[1]), None),
        ("full_body_back", back[0], dict(back[1]), None),
        ("closeup_front", closeup[0], dict(closeup[1]), None),
    ]


def _validate_candidate_view_consistency(view_entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Structural identity-consistency check across a candidate's 4 view jobs.

    For two-stage candidates, this validates the final (Stage 2 when enabled,
    otherwise Stage 1) view assets. All 4 final views must be complete and share
    the same seed and routing/identity params. This is NOT a fake ML visual
    validator — a pixel-level identity comparison is deferred to a later vision
    tooling pass. Returns ``{ok, reasons, assetIds}``.
    """
    reasons: list[str] = []
    if len(view_entries) != len(CANDIDATE_SHEET_VIEW_ROLES):
        reasons.append(
            f"expected {len(CANDIDATE_SHEET_VIEW_ROLES)} views, got {len(view_entries)}"
        )
        return {"ok": False, "reasons": reasons}
    asset_ids: list[str] = []
    seeds: set[Any] = set()
    families: set[str] = set()
    workflow_keys: set[str] = set()
    ref_locks: set[bool] = set()
    for entry in view_entries:
        stage2_enabled = bool(entry.get("stage2Enabled"))
        stage2_done = stage2_enabled and entry.get("stage2Status") == "done"
        if stage2_done:
            aid = entry.get("stage2AssetId")
            family = entry.get("stage2ModelFamily") or entry.get("modelFamily")
            workflow_key = entry.get("stage2WorkflowKey") or entry.get("workflowKey")
            ref_locked = False
        else:
            if entry.get("status") != "done":
                reasons.append(f"view {entry.get('role')} not done (status={entry.get('status')})")
            aid = entry.get("assetId")
            family = entry.get("modelFamily")
            workflow_key = entry.get("workflowKey")
            ref_locked = bool(entry.get("referenceLocked"))
        if not aid:
            reasons.append(f"view {entry.get('role')} missing output assetId")
        else:
            asset_ids.append(str(aid))
        if "seed" in entry and entry["seed"] is not None:
            seeds.add(entry["seed"])
        if family:
            families.add(str(family))
        if workflow_key:
            workflow_keys.add(str(workflow_key))
        ref_locks.add(ref_locked)
    if len(seeds) > 1:
        reasons.append(f"inconsistent seeds across views: {sorted(seeds)}")
    if len(families) > 1:
        reasons.append(f"inconsistent model families across views: {sorted(families)}")
    if len(workflow_keys) > 1:
        reasons.append(f"inconsistent workflow keys across views: {sorted(workflow_keys)}")
    if len(ref_locks) > 1:
        reasons.append(f"inconsistent reference-lock state across views: {sorted(ref_locks)}")
    if len(asset_ids) != len(set(asset_ids)):
        reasons.append("duplicate output asset ids across views")
    return {"ok": not reasons, "reasons": reasons, "assetIds": asset_ids}


def _compose_character_sheet_grid(
    view_paths: list[str], out_path: str
) -> str:
    """Compose 4 view images into a 2x2 Character Sheet grid (PIL).

    Each tile is resized to ``CHARACTER_SHEET_TILE_SIZE`` (preserving aspect,
    padded onto a square canvas) then pasted into the grid. No rendered text is
    added — the sheet is a clean image grid. Returns the composed file path.
    """
    from PIL import Image

    if len(view_paths) != CHARACTER_SHEET_GRID_COLS * CHARACTER_SHEET_GRID_ROWS:
        raise ValueError(
            f"character sheet grid requires "
            f"{CHARACTER_SHEET_GRID_COLS * CHARACTER_SHEET_GRID_ROWS} view images, "
            f"got {len(view_paths)}"
        )
    tile = CHARACTER_SHEET_TILE_SIZE
    grid = Image.new("RGB", (tile * CHARACTER_SHEET_GRID_COLS, tile * CHARACTER_SHEET_GRID_ROWS), (24, 24, 24))
    for idx, src in enumerate(view_paths):
        im = Image.open(src).convert("RGB")
        # Resize preserving aspect ratio, then center on a square canvas.
        im.thumbnail((tile, tile))
        canvas = Image.new("RGB", (tile, tile), (24, 24, 24))
        x = (tile - im.width) // 2
        y = (tile - im.height) // 2
        canvas.paste(im, (x, y))
        col = idx % CHARACTER_SHEET_GRID_COLS
        row = idx // CHARACTER_SHEET_GRID_COLS
        grid.paste(canvas, (col * tile, row * tile))
    out = str(out_path)
    grid.save(out, format="PNG")
    return out


def _composed_sheet_output_path(project_id: str, character_id: str, candidate_index: int) -> Path:
    """Resolve the on-disk path for a candidate's composed Character Sheet."""
    from pathlib import Path

    from ..config import settings

    dest_dir = Path(settings.data_dir) / "projects" / project_id / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir / f"character_sheet_{character_id[:8]}_c{candidate_index + 1}_{uuid.uuid4().hex[:8]}.png"


def _ingest_composed_sheet_asset(
    db: Session,
    project_id: str,
    *,
    character_id: str,
    candidate_index: int,
    composed_path: str,
    source_asset_ids: list[str],
    lineage: dict[str, Any],
    stage1_source_asset_ids: list[str] | None = None,
) -> Asset:
    """Register the composed Character Sheet as a Library asset.

    The 4 source view asset ids are recorded in ``prompt_meta_json`` lineage so
    they remain queryable for provenance/continuity without being duplicated.
    For two-stage candidates, ``stage1_source_asset_ids`` records the identity-
    locked Stage 1 outputs when the composed sheet uses Stage 2 outputs.
    """
    import os

    meta = {
        "objective": "character_sheet_composed",
        "characterId": character_id,
        "candidateIndex": candidate_index,
        "compositionIntent": COMPOSITION_INTENT_CHARACTER_SHEET,
        "sourceAssetIds": list(source_asset_ids),
        "stage1SourceAssetIds": list(stage1_source_asset_ids or []),
        "grid": {
            "cols": CHARACTER_SHEET_GRID_COLS,
            "rows": CHARACTER_SHEET_GRID_ROWS,
            "tileSize": CHARACTER_SHEET_TILE_SIZE,
        },
        "lineage": lineage,
        "createdAt": _now(),
    }
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tag="character_sheet",
        kind="image",
        filename=os.path.basename(composed_path),
        path=str(composed_path),
        comfy_name="",
        scope="project",
        labels_json=_dumps(["character_sheet", "composed", f"candidate_{candidate_index + 1}"]),
        prompt_meta_json=_dumps(meta),
        production_approval="none",
    )
    db.add(asset)
    db.flush()
    # Record provenance edges to the 4 source views (best-effort). Use a
    # savepoint so a failure here (e.g. missing graph table in a minimal test
    # DB) never rolls back the composed sheet asset itself.
    try:
        from ..asset_graph import add_edge

        nested = db.begin_nested()
        for src_id in source_asset_ids:
            if db.get(Asset, src_id):
                add_edge(db, src_id, asset.id, "composed_from", {"op": "character_sheet_compose"})
        nested.commit()
    except Exception:
        pass
    return asset


def _poll_candidate_views(db: Session, candidate: dict[str, Any]) -> tuple[bool, bool, list[str]]:
    """Poll a candidate's 4 view jobs (Stage 1 + optional Stage 2).

    Returns ``(all_done, any_failed, final_view_asset_ids)``.
    ``all_done`` is True when every view reached a final successful asset:
    Stage 1 asset if Stage 2 is disabled, or Stage 2 asset if enabled.
    ``any_failed`` is True when any view job reached a terminal non-success
    state (failed/error/missing). This lets the caller surface a truthful
    candidate failure instead of leaving it stuck in "generating" forever.
    """
    view_jobs = candidate.get("viewJobs") or []
    if not view_jobs:
        return False, False, []
    asset_ids: list[str] = []
    all_done = True
    any_failed = False
    for vj in view_jobs:
        # Stage 1 poll
        job = db.get(Job, vj.get("jobId"))
        if not job:
            vj["status"] = "missing"
            all_done = False
            any_failed = True
            continue
        vj["status"] = job.status
        if job.status == "done":
            stage1_aid = _job_params(job).get("output_asset_id")
            if stage1_aid:
                vj["assetId"] = stage1_aid
            else:
                all_done = False
                continue
        elif job.status in ("failed", "error", "cancelled"):
            vj["status"] = job.status
            all_done = False
            any_failed = True
            continue
        else:
            all_done = False
            continue

        # Stage 2 poll (if enabled and enqueued)
        stage2_enabled = bool(vj.get("stage2Enabled"))
        stage2_job_id = vj.get("stage2JobId")
        if stage2_enabled and stage2_job_id:
            stage2_job = db.get(Job, stage2_job_id)
            if not stage2_job:
                vj["stage2Status"] = "missing"
                all_done = False
                any_failed = True
                continue
            vj["stage2Status"] = stage2_job.status
            if stage2_job.status == "done":
                stage2_aid = _job_params(stage2_job).get("output_asset_id")
                if stage2_aid:
                    vj["stage2AssetId"] = stage2_aid
                    asset_ids.append(str(stage2_aid))
                else:
                    all_done = False
                    continue
            elif stage2_job.status in ("failed", "error", "cancelled"):
                vj["stage2Status"] = stage2_job.status
                all_done = False
                any_failed = True
                continue
            else:
                all_done = False
                continue
        elif stage2_enabled and not stage2_job_id:
            # Stage 2 is enabled but not yet enqueued — not done yet.
            all_done = False
            continue
        else:
            # Stage 2 disabled: use Stage 1 asset as the final view.
            if vj.get("assetId"):
                asset_ids.append(str(vj["assetId"]))
    return all_done, any_failed, asset_ids


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
    generator_sources: Optional[dict[str, Any]] = None,
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
    reference_asset_id: str | None = None
    reference_locked = False
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
            generator_sources=generator_sources,
        )
        reference_locked = bool(reference_asset_id)
        hero_candidate_jobs: list[dict[str, Any]] = []
        view_specs = _candidate_view_specs()
        for _i in range(candidate_count):
            route = routing_plan[_i]
            stage1_route = route["stage1"]
            stage2_route = route.get("stage2")
            seed = _candidate_seed(character_id, _i)
            # Phase 5: enqueue the 4 required views for this candidate. The
            # front view reuses role="hero_identity" (legacy + e2e compat) and
            # the full-body casting composition; the other three views use
            # their turnaround/close-up coverage compositions. All 4 views
            # share the same seed + routing so identity is structurally
            # consistent across the sheet.
            #
            # Two-stage pipeline: Stage 1 locks identity (reference-capable or
            # txt2img). Stage 2 is an optional real img2img/edit refinement that
            # runs on the Stage 1 output after it completes.
            view_jobs: list[dict[str, Any]] = []
            for vidx, (vrole, vgoal, vcomposition, vneg) in enumerate(view_specs):
                composition = dict(vcomposition)
                composition["candidate_index"] = _i
                vprompt = _compile_visual_prompt(
                    profile,
                    prompt_goal=vgoal,
                    composition=composition,
                    references=references,
                    role=vrole,
                    extra_negative_constraints=vneg if vneg is not None else FULL_BODY_CASTING_NEGATIVE_RULES,
                    style_profile=style_profile,
                    reference_locked=reference_locked,
                )
                vtag = f"{char_slug}_{vrole}" + (f"_c{_i + 1}" if candidate_count > 1 else "")
                vjob = _enqueue_txt2img(
                    db,
                    project_id,
                    character_id=character_id,
                    prompt=vprompt.prompt,
                    negative_prompt=vprompt.negative_prompt,
                    tag=vtag,
                    role=vrole,
                    model_family_preference=stage1_route["modelFamilyPreference"],
                    source_asset_id=stage1_route.get("source_asset_id"),
                    denoise=stage1_route.get("denoise"),
                    seed=seed,
                    force_workflow_key=stage1_route.get("workflowKey"),
                    prompt_metadata={
                        "promptFamily": vprompt.prompt_family,
                        "promptModel": vprompt.model_key,
                        "promptValidationOk": vprompt.validation.get("ok"),
                        "sheetMode": vprompt.metadata.get("sheetMode"),
                        "candidateIndex": _i,
                        "candidateCount": candidate_count,
                        "viewIndex": vidx,
                        "viewRole": vrole,
                        "compositionIntent": COMPOSITION_INTENT_CHARACTER_SHEET
                        if vrole != "hero_identity"
                        else COMPOSITION_INTENT_FULL_BODY_CASTING,
                        "fullBody": vrole != "closeup_front",
                        "workflowKey": stage1_route["workflowKey"],
                        "modelFamily": stage1_route["modelFamilyPreference"],
                        "referenceLocked": reference_locked,
                        "referenceAssetId": reference_asset_id,
                        "referenceFidelityMode": stage1_route.get("referenceFidelityMode"),
                        "seed": seed,
                        "stage": 1,
                    },
                )
                stage2_prompt = (
                    f"{STAGE2_IDENTITY_PRESERVATION_PROMPT} {vprompt.prompt}"
                    if stage2_route
                    else None
                )
                stage2_negative = (
                    f"{STAGE2_STYLE_ONLY_NEGATIVE}, {vprompt.negative_prompt}"
                    if stage2_route
                    else None
                )
                view_jobs.append(
                    {
                        "jobId": vjob.id,
                        "role": vrole,
                        "viewIndex": vidx,
                        "status": vjob.status,
                        "assetId": None,
                        "seed": seed,
                        "modelFamily": stage1_route["modelFamilyPreference"],
                        "workflowKey": stage1_route["workflowKey"],
                        "referenceLocked": reference_locked,
                        # Stage 2 fields (populated when Stage 1 completes).
                        "stage2Enabled": bool(stage2_route),
                        "stage2Route": stage2_route,
                        "stage2JobId": None,
                        "stage2AssetId": None,
                        "stage2Status": None,
                        "stage2Prompt": stage2_prompt,
                        "stage2Negative": stage2_negative,
                        "stage2PromptMetadata": {
                            "promptFamily": vprompt.prompt_family,
                            "promptModel": vprompt.model_key,
                            "promptValidationOk": vprompt.validation.get("ok"),
                            "sheetMode": vprompt.metadata.get("sheetMode"),
                            "candidateIndex": _i,
                            "candidateCount": candidate_count,
                            "viewIndex": vidx,
                            "viewRole": vrole,
                            "compositionIntent": COMPOSITION_INTENT_CHARACTER_SHEET
                            if vrole != "hero_identity"
                            else COMPOSITION_INTENT_FULL_BODY_CASTING,
                            "fullBody": vrole != "closeup_front",
                            "workflowKey": stage2_route["workflowKey"] if stage2_route else None,
                            "modelFamily": stage2_route["modelFamilyPreference"] if stage2_route else None,
                            "referenceLocked": False,
                            "referenceAssetId": None,
                            "referenceFidelityMode": None,
                            "seed": seed,
                            "stage": 2,
                        } if stage2_route else None,
                    }
                )
            # jobs["hero"] points at the front view job (legacy + e2e compat).
            hero_job = view_jobs[0]
            stage1_lineage = _workflow_lineage(stage1_route["workflowKey"])
            stage2_lineage = _workflow_lineage(stage2_route["workflowKey"]) if stage2_route else None
            low_fidelity = _low_reference_fidelity(
                reference_locked=reference_locked, lineage=stage1_lineage
            )
            label = "Hero" if candidate_count == 1 else f"Candidate {_i + 1}"
            entry = {
                "jobId": hero_job["jobId"],
                "role": "hero_identity",
                "status": hero_job["status"],
                "candidateIndex": _i,
                "label": label,
                "assetId": None,
                "generator": stage1_lineage.get("generator"),
                "provider": stage1_lineage.get("provider"),
                "model": stage1_lineage.get("model"),
                "modelVariant": stage1_lineage.get("modelVariant"),
                "workflowKey": stage1_route["workflowKey"],
                "seed": seed,
                "referenceAssetIds": [reference_asset_id] if reference_asset_id else [],
                "compositionIntent": COMPOSITION_INTENT_FULL_BODY_CASTING,
                "referenceFidelityMode": stage1_route.get("referenceFidelityMode"),
                "referenceLocked": reference_locked,
                "lowReferenceFidelity": low_fidelity,
                "stage2Enabled": bool(stage2_route),
                "stage2Generator": stage2_lineage.get("generator") if stage2_lineage else None,
                "stage2Provider": stage2_lineage.get("provider") if stage2_lineage else None,
                "stage2Model": stage2_lineage.get("model") if stage2_lineage else None,
                "stage2ModelVariant": stage2_lineage.get("modelVariant") if stage2_lineage else None,
                "stage2WorkflowKey": stage2_route["workflowKey"] if stage2_route else None,
                # Phase 5: the 4 view jobs that compose into the canonical sheet.
                "viewJobs": view_jobs,
                "sheetAssetId": None,
                "sourceAssetIds": [],
                "stage2SourceAssetIds": [],
            }
            hero_candidate_jobs.append(entry)
            candidates.append({
                "assetId": None,
                "jobId": hero_job["jobId"],
                "url": None,
                "label": label,
                "status": hero_job["status"],
                "candidateIndex": _i,
                "generator": stage1_lineage.get("generator"),
                "provider": stage1_lineage.get("provider"),
                "model": stage1_lineage.get("model"),
                "modelVariant": stage1_lineage.get("modelVariant"),
                "workflowKey": stage1_route["workflowKey"],
                "seed": seed,
                "referenceAssetIds": [reference_asset_id] if reference_asset_id else [],
                "compositionIntent": COMPOSITION_INTENT_FULL_BODY_CASTING,
                "referenceFidelityMode": stage1_route.get("referenceFidelityMode"),
                "referenceLocked": reference_locked,
                "lowReferenceFidelity": low_fidelity,
                "stage2Enabled": bool(stage2_route),
                "stage2Generator": stage2_lineage.get("generator") if stage2_lineage else None,
                "stage2Provider": stage2_lineage.get("provider") if stage2_lineage else None,
                "stage2Model": stage2_lineage.get("model") if stage2_lineage else None,
                "stage2ModelVariant": stage2_lineage.get("modelVariant") if stage2_lineage else None,
                "stage2WorkflowKey": stage2_route["workflowKey"] if stage2_route else None,
                "viewJobs": view_jobs,
                "sheetAssetId": None,
                "sourceAssetIds": [],
                "stage2SourceAssetIds": [],
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
                    # Phase 5: when this candidate has 4 viewJobs, the canonical
                    # hero_identity asset is the COMPOSED sheet (set by the
                    # composition block below), not the front view alone. Skip
                    # the front-view attach here so we don't double-attach the
                    # hero_identity reference role.
                    if not hero_meta.get("viewJobs"):
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
                "sheetAssetId": item.get("sheetAssetId"),
                "sourceAssetIds": item.get("sourceAssetIds") or [],
                "viewJobs": item.get("viewJobs") or [],
            }
            for item in hero_candidates
        ]

    # Phase 5: compose each candidate's 4 views into ONE canonical Character
    # Sheet asset. The composed sheet becomes the creator-facing candidate
    # ``assetId`` and ``role_assets["hero_identity"]``; the 4 source view assets
    # are retained as lineage (``sourceAssetIds``) and their roles are marked
    # satisfied so the coverage flow does not duplicate them.
    _hero_candidates = jobs.get("hero_candidates")
    candidate_entries: list[dict[str, Any]] = []
    if isinstance(_hero_candidates, list):
        candidate_entries = list(_hero_candidates)
    elif jobs.get("hero"):
        candidate_entries = [jobs["hero"]]
    primary_sheet_set = bool(role_assets.get("hero_identity"))
    for centry in candidate_entries:
        view_jobs = centry.get("viewJobs")
        if not isinstance(view_jobs, list) or not view_jobs:
            continue
        if centry.get("sheetAssetId"):
            continue
        all_done, any_failed, final_asset_ids = _poll_candidate_views(db, centry)
        if any_failed:
            # Stage 1 failure is a hard candidate failure. Stage 2 failure is
            # recoverable: preserve Stage 1 identity-locked assets and mark the
            # candidate as stage2_failed so the UI can offer the Stage 1 sheet.
            stage1_failed = any(
                vj.get("status") in ("failed", "error", "cancelled", "missing")
                for vj in view_jobs
            )
            if stage1_failed:
                failed_views = [
                    (vj.get("role") or f"view {vj.get('viewIndex')}")
                    for vj in view_jobs
                    if vj.get("status") in ("failed", "error", "cancelled", "missing")
                ]
                centry["status"] = "failed"
                centry["error"] = "view generation failed: " + ", ".join(failed_views or ["unknown"])
                continue
            # Stage 2 failed but Stage 1 succeeded.
            centry["status"] = "stage2_failed"
            centry["stage2Failed"] = True
            centry["stage2SourceAssetIds"] = [
                str(vj.get("assetId")) for vj in view_jobs if vj.get("assetId")
            ]
            centry["error"] = (
                "Stage 2 style refinement failed. The identity-locked Stage 1 views are preserved; "
                "you can use the Stage 1 result or retry."
            )
            continue
        if not all_done:
            # Stage 1 may be complete while Stage 2 is enabled but not yet enqueued.
            stage1_all_done = all(vj.get("status") == "done" and vj.get("assetId") for vj in view_jobs)
            stage2_pending = any(
                vj.get("stage2Enabled") and not vj.get("stage2JobId")
                for vj in view_jobs
            )
            if stage1_all_done and stage2_pending:
                # Enqueue Stage 2 style refinement jobs using Stage 1 outputs as source.
                for vj in view_jobs:
                    if not vj.get("stage2Enabled") or vj.get("stage2JobId"):
                        continue
                    stage2_route = vj.get("stage2Route")
                    stage1_aid = vj.get("assetId")
                    if not stage2_route or not stage1_aid:
                        continue
                    stage2_tag = f"{char_slug}_{vj.get('role')}_stage2"
                    if int(pack.get("candidateCount") or 1) > 1:
                        stage2_tag += f"_c{int(centry.get('candidateIndex') or 0) + 1}"
                    stage2_prompt = str(vj.get("stage2Prompt") or "")
                    stage2_negative = str(vj.get("stage2Negative") or "")
                    stage2_metadata = dict(vj.get("stage2PromptMetadata") or {})
                    stage2_metadata["stage1AssetId"] = stage1_aid
                    stage2_job = _enqueue_txt2img(
                        db,
                        project_id,
                        character_id=character_id,
                        prompt=stage2_prompt,
                        negative_prompt=stage2_negative,
                        tag=stage2_tag,
                        role=str(vj.get("role") or "view"),
                        model_family_preference=stage2_route["modelFamilyPreference"],
                        source_asset_id=str(stage1_aid),
                        denoise=stage2_route.get("denoise"),
                        seed=vj.get("seed"),
                        force_workflow_key=stage2_route.get("workflowKey"),
                        prompt_metadata=stage2_metadata,
                    )
                    vj["stage2JobId"] = stage2_job.id
                    vj["stage2Status"] = stage2_job.status
                centry["status"] = "generating_stage2"
                continue
            # Surface per-view status on the candidate for the UI.
            centry["status"] = "generating"
            continue
        validation = _validate_candidate_view_consistency(view_jobs)
        if not validation.get("ok"):
            centry["status"] = "failed"
            centry["error"] = "identity consistency check failed: " + "; ".join(validation.get("reasons") or [])
            continue
        source_asset_ids = validation["assetIds"]
        # Resolve on-disk paths for the 4 source view assets (composition input).
        view_paths: list[str] = []
        for aid in source_asset_ids:
            a = db.get(Asset, aid)
            if not a or not a.path:
                centry["status"] = "failed"
                centry["error"] = f"missing source view asset path for {aid}"
                break
            view_paths.append(a.path)
        else:
            # All 4 views are done and validated — surface a truthful
            # "assembling" stage before the synchronous grid composition so the
            # UI can show Assembly progress rather than implying views are still
            # rendering.
            centry["status"] = "assembling"
            try:
                out_path = _composed_sheet_output_path(
                    project_id, character_id, int(centry.get("candidateIndex") or 0)
                )
                composed_path = _compose_character_sheet_grid(view_paths, str(out_path))
                lineage = _candidate_sheet_lineage(centry, view_jobs)
                stage1_source_asset_ids = [
                    str(vj.get("assetId")) for vj in view_jobs if vj.get("assetId")
                ]
                sheet_asset = _ingest_composed_sheet_asset(
                    db,
                    project_id,
                    character_id=character_id,
                    candidate_index=int(centry.get("candidateIndex") or 0),
                    composed_path=composed_path,
                    source_asset_ids=source_asset_ids,
                    lineage=lineage,
                    stage1_source_asset_ids=stage1_source_asset_ids,
                )
                centry["sheetAssetId"] = sheet_asset.id
                centry["assetId"] = sheet_asset.id
                centry["sourceAssetIds"] = source_asset_ids
                centry["stage1SourceAssetIds"] = stage1_source_asset_ids
                centry["status"] = "done"
                # Only the first candidate (candidateIndex 0) populates the
                # pack-level role_assets / hero_identity so multi-candidate
                # generation does not collide on shared role keys. Other
                # candidates keep their views as lineage only.
                if int(centry.get("candidateIndex") or 0) == 0:
                    for vj in view_jobs:
                        role_assets[vj.get("role")] = vj.get("assetId")
                    role_assets["hero_identity"] = sheet_asset.id
                    _attach_role(db, project_id, character_id, sheet_asset.id, "hero_identity")
                    primary_sheet_set = True
            except Exception as exc:  # pragma: no cover - defensive
                centry["status"] = "failed"
                centry["error"] = f"character sheet composition failed: {exc}"
    # Mirror candidate sheet state back into pack["candidates"].
    def _mirror_candidate(item: dict[str, Any]) -> dict[str, Any]:
        return {
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
            "stage2Enabled": bool(item.get("stage2Enabled")),
            "stage2Generator": item.get("stage2Generator"),
            "stage2Provider": item.get("stage2Provider"),
            "stage2Model": item.get("stage2Model"),
            "stage2ModelVariant": item.get("stage2ModelVariant"),
            "stage2WorkflowKey": item.get("stage2WorkflowKey"),
            "stage2Failed": bool(item.get("stage2Failed")),
            "stage2SourceAssetIds": item.get("stage2SourceAssetIds") or [],
            "sheetAssetId": item.get("sheetAssetId"),
            "sourceAssetIds": item.get("sourceAssetIds") or [],
            "viewJobs": item.get("viewJobs") or [],
            "error": item.get("error"),
        }

    if isinstance(jobs.get("hero_candidates"), list):
        pack["candidates"] = [_mirror_candidate(item) for item in jobs["hero_candidates"]]
    elif jobs.get("hero") and jobs["hero"].get("sheetAssetId"):
        pack["candidates"] = [_mirror_candidate(jobs["hero"])]

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
    force_workflow_key: str | None = None,
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
    # Stage 2 refinement also uses source_asset_id, pointing at the Stage 1 output.
    if source_asset_id:
        body["source_asset_id"] = source_asset_id
    if denoise is not None:
        body["denoise"] = denoise
    if seed is not None:
        body["seed"] = seed
    if force_workflow_key:
        body["forceWorkflowKey"] = force_workflow_key
        body["allow_force_workflow_key"] = True
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
