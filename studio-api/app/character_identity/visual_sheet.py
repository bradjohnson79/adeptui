"""Generated Character Image Profile — real Image Product / character-sheet pack.

Canonical identity (korri.v1 / approved sheet) remains authority.
Generated views prove Character Creator can produce visual coverage via certified Qwen-Image-2512.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..db import Asset, Job, Project
from ..image_prompting.flux import compile_flux_crs_single_view
from ..image_prompting.qwen_2512 import compile_character_image_prompt
from . import service
from .roles import REQUIRED_COVERAGE_ROLES
from .schemas import ReferenceAttach, TraitUpsert

logger = logging.getLogger(__name__)
from .visual_gates import (
    list_gates,
    propose_visual_directions,
    set_gate_status,
)
from .four_view_sheet import (
    FOUR_VIEW_SHEET_REQUEST,
    REQUIRED_VIEWS,
    apply_layout_assessment_to_candidate,
    assess_four_view_layout,
    attach_four_view_sheet_intent,
    candidate_layout_noncompliant,
    four_view_sheet_intent,
    public_job_error,
    strengthen_four_view_prompt,
)
from .character_sheet_compose import (
    LAW_VIEW_DISPLAY_LABELS,
    compose_labeled_character_sheet,
)
from .crs_law_view_gates import gate_candidate_law_views
from .crs_view_generation import (
    CRS_VIEW_DEFAULT_VIEW,
    CRS_VIEW_GENERATION_TASK,
    CRS_VIEW_ROLE,
    extract_crs_view_requested_family,
    is_crs_view_generation_task,
    normalize_crs_view_type,
    resolve_crs_view_generation_workflow,
    valid_identity_reference_crop,
)
from .crs_schema import (
    CharacterIdentityPacket,
    FOUR_VIEW_REQUIRED_VIEWS,
    LAW_REQUIRED_VIEWS,
    dump_identity_packet,
)
from .crs_service import build_conditioning_packet
from .crs_single_figure import required_views_are_default_four

PACK_TRAIT_KEY = "visual_sheet_pack"


class VisualSheetSourceUnavailableError(ValueError):
    """The pack's selected generator source cannot serve the requested phase.

    Raised instead of silently falling back to the default local model (e.g. a
    Cloud-only selection with no API model, or a persisted source selection that
    is no longer executable). Subclasses ValueError so the API layer maps it to
    a creator-facing 400 like the other visual-sheet errors.
    """


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

# Close-up tile is a structural identity portrait, not a cropped full-body frame.
CLOSEUP_FRONT_COMPOSITION: dict[str, Any] = {
    "shot_type": "head-and-shoulders identity portrait",
    "framing": "head and shoulders, full hair silhouette in frame",
    "camera_angle": "eye level, camera at face height",
    "lens": "85mm portrait, no fisheye, no wide-angle",
    "environment": "simple unobtrusive studio background",
    "lighting": "soft studio portrait light",
    "pose": "front-facing, upright, neutral posture, not leaning into camera",
    "expression": "neutral natural presence",
    "focus": "face, eyes, ears, identity-critical features, full hair silhouette",
    "full_body": False,
}

CLOSEUP_FRONT_NEGATIVE_RULES: list[str] = [
    "No full body",
    "No full-length figure",
    "No wide shot",
    "No fisheye",
    "No wide-angle lens",
    "No giant-head perspective",
    "No leaning into camera",
    "No hands dominating the frame",
    "No cropped skull",
    "Do not crop the hair silhouette",
    "No extra figures",
    "No split frames",
]

# CRS law views: one figure, one camera. Tokens must appear in the compiled
# prompt or negatives so Qwen cannot draw a multi-figure collage.
LAW_VIEW_SINGLE_FIGURE_RULES: list[str] = [
    "one person only",
    "one figure",
    "no other people",
    "no grid",
    "no collage",
    "no turnaround sheet",
    "no multiple poses in one image",
]
LAW_VIEW_SINGLE_FIGURE_DIRECTIVE = (
    "one person only, one figure, no other people, no grid, no collage, "
    "no turnaround sheet, no multiple poses in one image"
)

VIEW_ROLE_CANONICAL: dict[str, str] = {
    "hero_identity": "front_full",
    "full_body_three_quarter_front": "three_quarter_full",
    "full_body_side_left": "side_full",
    "full_body_back": "back_full",
    "closeup_front": "face_closeup",
}

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

# Certified txt2img families available for no-reference / Profile Guided
# candidate routing, in preference order. Each is used once before any reuse.
NO_REFERENCE_TXT2IMG_FAMILIES = ("qwen2512", "zimage", "illustrious")

# CRS AUTO (CRS_GENERATION / CRS_SINGLE_VIEW / law_views / crs_view).
# CRS_VIEW_GENERATION is a separate explicit single-view task (not a five-view pack).
# FLUX is the primary advertised canvas. Qwen is the only fallback.
# Never silent-sub to zimage / illustrious / Krea. Never default qwen2512.ref.
CRS_AUTO_PRIMARY_FAMILY = "flux"
CRS_AUTO_FALLBACK_FAMILY = "qwen2512"
CRS_AUTO_FLUX_TXT2IMG_KEY = "flux.txt2img"
CRS_AUTO_FLUX_IMG2IMG_KEY = "flux.img2img"

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
# When a Character Reference is attached:
# * Reference-capable families (e.g. Z-Image) run REFERENCE_CONDITIONED Stage 1
#   with pixels (zimage.ref_edit).
# * Txt2img-only families (Illustrious / Qwen) run PROFILE_GUIDED Stage 1 with
#   no pixels. They are never silently redirected to Z-Image.
# Stage 2 is optional: a real img2img/edit/refinement workflow (e.g. flux.img2img)
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
# Default Generate: Front, Side, Back, Head/Neck Close-Up (no 3/4).
# Isolated Advanced / legacy five-view law stays in FIVE_VIEW_LAW_ROLES.
CANDIDATE_SHEET_VIEW_ROLES: tuple[str, ...] = (
    "hero_identity",
    "full_body_side_left",
    "full_body_back",
    "closeup_front",
)
FIVE_VIEW_LAW_ROLES: tuple[str, ...] = (
    "hero_identity",
    "full_body_three_quarter_front",
    "full_body_side_left",
    "full_body_back",
    "closeup_front",
)

# View-only instructions appended to one shared Character Profile base prompt.
# Identity facts stay unchanged between views.
PROFILE_GUIDED_VIEW_INSTRUCTIONS: dict[str, str] = {
    "hero_identity": (
        "FRONT: one camera only, this view only, front-facing, full-body neutral stance"
    ),
    "full_body_three_quarter_front": (
        "THREE-QUARTER: one camera only, this view only, 3/4 view, full-body "
        "neutral stance, camera about 45 degrees"
    ),
    "full_body_side_left": (
        "SIDE: one camera only, this view only, strict side-profile, full-body "
        "neutral stance"
    ),
    "full_body_back": (
        "BACK: one camera only, this view only, back-facing, full-body neutral stance"
    ),
    "closeup_front": (
        "CLOSE-UP: one camera only, this view only, one single front-facing "
        "head-and-shoulders identity portrait, eye-level, full hair silhouette, "
        "ears readable, no hands, no fisheye"
    ),
}

# 2x2 grid layout (row-major): front, side / back, front-close-up.
# CRS 2K is a native square four-view: 1280 tiles compose to 2560×2560.
# This is not ERS 2560×1440 (environment plate) and not an upscale.
CHARACTER_SHEET_GRID_COLS = 2
CHARACTER_SHEET_GRID_ROWS = 2
CHARACTER_SHEET_TILE_SIZE = 1280
CRS_2K_COMPOSE = 2560
CRS_VIEW_LONG_EDGE = 2048

COMPOSITION_INTENT_CHARACTER_SHEET = "character_sheet_composed"

# Conditioning modes persisted on each candidate for truthful provenance.
# REFERENCE_CONDITIONED: generator can consume reference pixels (source_asset_id set).
# PROFILE_GUIDED: txt2img-only family (Illustrious / Qwen) — profile prompt, no pixels.
CONDITIONING_PROFILE_GUIDED = "PROFILE_GUIDED"
CONDITIONING_REFERENCE_CONDITIONED = "REFERENCE_CONDITIONED"

# Certified families that are text-only (cannot consume reference pixels).
# Illustrious stays PROFILE_GUIDED. Qwen Image 2512 Character Sheets are also
# PROFILE_GUIDED (qwen2512.txt2img). qwen2512.ref is ERS I2I (environment-ref)
# and must never consume a Character Sheet / CRS reference as identity pixels.
TEXT_ONLY_FAMILIES: frozenset[str] = frozenset({"illustrious"})
QWEN_FAMILIES: frozenset[str] = frozenset({"qwen2512", "qwen", "qwen-image-2512", "qwen_image_2512"})
QWEN_EDIT_2509_FAMILY = "qwen_edit_2509"
QWEN_EDIT_2509_WORKFLOW_KEY = "qwen_edit_2509.edit"
QWEN_EDIT_2509_CRS_KEY = "qwen_edit_2509.crs_single_view"
QWEN_REF_WORKFLOW_KEY = "qwen2512.ref"
QWEN_EDIT_2509_NOT_READY = (
    "Qwen Image Edit 2509 is installed but could not start. "
    "Choose another generator or retry after runtime repair."
)
QWEN_EDIT_2509_NEEDS_CROP = (
    "Qwen Image Edit 2509 needs a single-character identity image. "
    "A full Character Reference Sheet cannot be used as the edit canvas."
)
_HONORED_CRS_LOCAL_FAMILIES: dict[str, str] = {
    "qwen2512": "qwen2512",
    "qwen": "qwen2512",
    "flux": "flux",
    "qwen_edit_2509": QWEN_EDIT_2509_FAMILY,
    "qwen-edit-2509": QWEN_EDIT_2509_FAMILY,
    "qwen-image-edit-2509": QWEN_EDIT_2509_FAMILY,
    "qwen_image_edit_2509": QWEN_EDIT_2509_FAMILY,
    "krea2": "krea2",
    "krea": "krea2",
    "illustrious": "illustrious",
    "sensenova": "sensenova",
    "sensenova_u15": "sensenova",
    "sensenova-u15": "sensenova",
    "sensenova-u15-local": "sensenova",
    "sensenova_u1": "sensenova",
}

# Local Krea 2 inference target. RAW is reachable only via an explicit raw id.
KREA_LOCAL_TXT2IMG_KEY = "krea2.turbo_txt2img"
KREA_HOSTED_MODEL_LABELS: dict[str, str] = {
    "krea2-turbo-fal": "Krea 2 Turbo",
    "krea2-medium-fal": "Krea 2 Medium",
    "krea2-large-fal": "Krea 2 Large",
    "krea2-turbo-local": "Krea 2 Turbo",
    "krea2-raw-local": "Krea 2 RAW",
}


def crs_2k_pixels() -> tuple[int, int]:
    """Native CRS 2K composed square (four-view single output).

    Tile is 1280×1280 (same 2K square class as Atlas ``_atlas_pixels("1:1")``).
    The product path enqueues one four-panel job at 2560×2560 — not an upscale,
    and not ERS 2560×1440.
    """
    return CRS_2K_COMPOSE, CRS_2K_COMPOSE


def crs_2k_tile_size() -> int:
    return CHARACTER_SHEET_TILE_SIZE


def crs_2k_view_pixels() -> tuple[int, int]:
    """Per-view CRS pixels. Long edge is native 2K (>=2048), never a 1024 tile."""
    return CRS_VIEW_LONG_EDGE, CRS_VIEW_LONG_EDGE


def _qwen_ref_workflow_ready() -> bool:
    try:
        from ..image_runtime.certified_registry import get_workflow

        wf = get_workflow(QWEN_REF_WORKFLOW_KEY)
        return bool(
            wf
            and wf.status == "Certified"
            and bool((wf.capabilities or {}).get("supportsReferences", False))
        )
    except Exception:
        return False


def _is_qwen_family(family: str) -> bool:
    return (family or "").strip().lower() in QWEN_FAMILIES


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
    "full_body_three_quarter_front": "three_quarter",
    "full_body_three_quarter": "three_quarter",
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
    """CRS law views are one camera each. Do not request a four-panel sheet."""
    return {}


def _is_flux_family(family: str | None) -> bool:
    return str(family or "").strip().lower() in {"flux", "flux-schnell", "flux-dev", "flux-kontext"}


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
    sheet_request: dict[str, Any] | None = None,
    model_family: str | None = None,
) -> Any:
    v_instruction = PROFILE_GUIDED_VIEW_INSTRUCTIONS.get(role, "")
    goal = prompt_goal.strip()
    # Four-view single-output (hosted API) must not append a single-camera instruction.
    four_view = bool(sheet_request and sheet_request.get("layout") == "four_view")
    if v_instruction and not four_view:
        goal = f"{goal}. {v_instruction}"
        if LAW_VIEW_SINGLE_FIGURE_DIRECTIVE not in goal:
            goal = f"{goal}. {LAW_VIEW_SINGLE_FIGURE_DIRECTIVE}"
    if _is_flux_family(model_family) and not four_view:
        return compile_flux_crs_single_view(
            _compiler_payload(profile),
            prompt_goal=goal,
            view_instruction=v_instruction,
            extra_negative_constraints=extra_negative_constraints or [],
            full_body=role != "closeup_front",
            role=role,
            view=VIEW_ROLE_CANONICAL.get(role, ""),
        )
    return compile_character_image_prompt(
        _compiler_payload(profile),
        prompt_goal=goal,
        composition=composition,
        style_profile=style_profile or QWEN_VISUAL_SHEET_STYLE,
        references=references,
        sheet_request=sheet_request if sheet_request is not None else _sheet_request_for_role(role),
        extra_negative_constraints=extra_negative_constraints or [],
        reference_locked=reference_locked,
    )


def _reference_item_asset_id(item: dict[str, Any]) -> str | None:
    aid = str(item.get("asset_id") or item.get("assetId") or "").strip()
    return aid or None


def _iter_reference_candidate_ids(references: list[dict[str, Any]]) -> list[str]:
    """Character Reference ids in product priority, newest within each tier.

    Generated ``hero_identity`` rows from prior sheets must not override the
    creator-attached Character Reference (role ``reference_image``). Stale
    generated rows can also point at deleted files.
    """
    refs = [item for item in (references or []) if isinstance(item, dict)]

    def _newest(items: list[dict[str, Any]]) -> list[str]:
        ranked = [item for item in items if _reference_item_asset_id(item)]
        ranked.sort(
            key=lambda item: str(item.get("created_at") or item.get("createdAt") or ""),
            reverse=True,
        )
        seen: list[str] = []
        for item in ranked:
            aid = _reference_item_asset_id(item)
            if aid and aid not in seen:
                seen.append(aid)
        return seen

    image_refs = [
        item for item in refs if str(item.get("reference_role") or "").strip() == "reference_image"
    ]
    heroes = [
        item for item in refs if str(item.get("reference_role") or "").strip() == "hero_identity"
    ]
    canonical = [item for item in heroes if item.get("canonical")]
    ordered: list[str] = []
    for aid in _newest(image_refs) + _newest(canonical) + _newest(heroes):
        if aid not in ordered:
            ordered.append(aid)
    return ordered


def _asset_image_path(db: Session, project_id: str, asset_id: str) -> str | None:
    asset = db.get(Asset, asset_id)
    if not asset or asset.project_id != project_id or str(asset.kind or "") != "image":
        return None
    path = Path(str(asset.path or ""))
    if not path.is_file():
        return None
    return str(path)


def _asset_image_readable(db: Session, project_id: str, asset_id: str) -> bool:
    return _asset_image_path(db, project_id, asset_id) is not None


def _resolve_reference_asset_id(references: list[dict[str, Any]]) -> str | None:
    """Return the attached Character Reference asset id, if any.

    Priority: creator-attached ``reference_image``, then canonical
    ``hero_identity``, then other ``hero_identity``. Newest wins within a tier.
    """
    ids = _iter_reference_candidate_ids(references)
    return ids[0] if ids else None


def _resolve_readable_reference_asset_id(
    db: Session, project_id: str, references: list[dict[str, Any]]
) -> str | None:
    """Like ``_resolve_reference_asset_id``, skipping missing/unreadable files."""
    for asset_id in _iter_reference_candidate_ids(references):
        if _asset_image_readable(db, project_id, asset_id):
            return asset_id
    return None


_SHEET_LAYOUTS = frozenset({"law_views", "four_view", "character_sheet", "collage", "contact_sheet"})
_SHEET_REF_ROLES = frozenset({"character_sheet", "hero_identity", "hero_portrait", "composed_sheet"})


def _resolve_isolated_identity_crop(
    db: Session,
    project_id: str,
    character_id: str,
    references: list[dict[str, Any]],
    *,
    extract_from_sheet: bool,
) -> str | None:
    """Return a proven one-figure crop id. Never a composed CRS sheet."""
    def _readable(aid: str) -> bool:
        return _asset_image_readable(db, project_id, aid)

    def _image_path(aid: str) -> str | None:
        return _asset_image_path(db, project_id, aid)

    crop = valid_identity_reference_crop(
        references, readable=_readable, image_path=_image_path
    )
    if crop:
        return crop
    if not extract_from_sheet:
        return None
    sheet_id = ""
    for item in references or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("reference_role") or item.get("referenceRole") or item.get("role") or "").strip().lower()
        layout = str(item.get("layout") or "").strip().lower()
        aid = str(item.get("asset_id") or item.get("assetId") or "").strip()
        if not aid or not _readable(aid):
            continue
        if layout in _SHEET_LAYOUTS or role in _SHEET_REF_ROLES:
            sheet_id = aid
            break
    if not sheet_id:
        return None
    try:
        from .crs_identity_views import persist_derived_identity_views

        persist_derived_identity_views(
            db, project_id, character_id, sheet_asset_id=sheet_id
        )
    except Exception:
        logger.exception("CRS identity crop extract failed for sheet %s", sheet_id)
        return None
    refreshed = service.list_references(db, project_id, character_id)
    return valid_identity_reference_crop(
        refreshed, readable=_readable, image_path=_image_path
    )


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


def _crs_workflow_certified(workflow_key: str) -> bool:
    """True when the exact Certified workflow is advertised. No invented keys."""
    key = (workflow_key or "").strip()
    if not key:
        return False
    try:
        from ..image_runtime.certified_registry import get_workflow

        wf = get_workflow(key)
        return bool(wf and wf.status == "Certified")
    except Exception:
        return False


def _resolve_crs_auto_family(*, has_identity_crop: bool = False) -> str:
    """AUTO chooser for CRS law-view singles.

    Prefer FLUX when flux.txt2img is Certified, or flux.img2img when a real
    identity crop is attached. Else Qwen. Never Krea, never a random Certified
    family, never qwen2512.ref as the default canvas.
    """
    if has_identity_crop and _crs_workflow_certified(CRS_AUTO_FLUX_IMG2IMG_KEY):
        return CRS_AUTO_PRIMARY_FAMILY
    if _crs_workflow_certified(CRS_AUTO_FLUX_TXT2IMG_KEY) or _candidate_family_executable(
        CRS_AUTO_PRIMARY_FAMILY
    ):
        return CRS_AUTO_PRIMARY_FAMILY
    return CRS_AUTO_FALLBACK_FAMILY


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

    qwen2512.ref is ERS I2I (environment-ref), not a Character Sheet consumer.
    Qwen CRS stays PROFILE_GUIDED. Illustrious stays text-only.
    """
    fam = (family or "").strip().lower()
    if fam in {QWEN_EDIT_2509_FAMILY, "qwen-edit-2509", "qwen-image-edit-2509"}:
        return True
    if fam in {"sensenova", "sensenova_u15", "sensenova-u15", "sensenova-u15-local"}:
        return True
    if fam in TEXT_ONLY_FAMILIES or _is_qwen_family(fam):
        return False
    try:
        from ..image_runtime.certified_registry import list_workflows

        families = [fam]
        for key in families:
            for wf in list_workflows(model_family=key):
                if wf.status != "Certified":
                    continue
                wf_key = str(getattr(wf, "workflow_key", "") or "")
                variant = str(getattr(wf, "model_variant", "") or "").strip().lower()
                if wf_key in {QWEN_REF_WORKFLOW_KEY, "sensenova.ers"} or variant == "environment-ref":
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


def _canonical_view_role(role: str) -> str:
    return VIEW_ROLE_CANONICAL.get(role) or ROLE_TO_SHEET_VIEW.get(role) or role


def _negative_rules_for_view(role: str, explicit: list[str] | None) -> list[str]:
    if explicit is not None:
        rules = list(explicit)
    elif role == "closeup_front":
        rules = list(CLOSEUP_FRONT_NEGATIVE_RULES)
    else:
        rules = list(FULL_BODY_CASTING_NEGATIVE_RULES)
    for rule in LAW_VIEW_SINGLE_FIGURE_RULES:
        if rule not in rules:
            rules.append(rule)
    return rules


def _clamp_batch_count(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 1
    return max(1, min(4, n))


def _is_auto_family(family: str) -> bool:
    return (family or "").strip().lower() in {"", "auto"}


def _parse_local_source_entries(local: Any) -> tuple[bool, list[dict[str, Any]]]:
    if local is None:
        return False, []
    if isinstance(local, list):
        entries: list[dict[str, Any]] = []
        for item in local:
            if not isinstance(item, dict):
                continue
            family = _normalize_local_family(
                str(item.get("family") or item.get("selected") or item.get("model") or "")
            )
            raw_family = str(
                item.get("family") or item.get("selected") or item.get("model") or ""
            ).strip().lower()
            if raw_family in {"", "auto"}:
                family = "auto"
            entries.append(
                {
                    "family": family,
                    "enabled": bool(item.get("enabled")),
                    "batchCount": _clamp_batch_count(item.get("batchCount") or 1),
                }
            )
        return True, entries
    if isinstance(local, dict):
        family = _normalize_local_family(
            str(local.get("family") or local.get("selected") or local.get("model") or "")
        )
        return True, [
            {
                "family": family or "auto",
                "enabled": True,
                "batchCount": 0,  # legacy uses candidate_count
            }
        ]
    return False, []


def _parse_api_source_entries(api: Any) -> tuple[bool, list[dict[str, Any]]]:
    if api is None:
        return False, []
    if isinstance(api, list):
        entries: list[dict[str, Any]] = []
        for item in api:
            if not isinstance(item, dict):
                continue
            provider_id = str(item.get("providerId") or "").strip().lower()
            model_id = str(item.get("modelId") or "").strip()
            model = str(item.get("model") or item.get("selected") or "").strip()
            if not model:
                model = model_id
            entries.append(
                {
                    "model": model,
                    "providerId": provider_id,
                    "modelId": model_id or model,
                    "enabled": bool(item.get("enabled")),
                    "batchCount": _clamp_batch_count(item.get("batchCount") or 1),
                }
            )
        return True, entries
    if isinstance(api, dict):
        model = str(api.get("model") or api.get("selected") or "").strip()
        provider_id = str(api.get("providerId") or "").strip().lower()
        model_id = str(api.get("modelId") or "").strip()
        return True, [
            {
                "model": model,
                "providerId": provider_id,
                "modelId": model_id or model,
                "enabled": True,
                "batchCount": 0,
            }
        ]
    return False, []


def _is_gpt_image_2_model(value: str) -> bool:
    blob = (value or "").strip().lower()
    return "gpt-image-2" in blob or "gpt_image_2" in blob


def _normalized_crs_local_family(family: str) -> str | None:
    return _HONORED_CRS_LOCAL_FAMILIES.get((family or "").strip().lower())


def _is_qwen_edit_2509_family(family: str) -> bool:
    return _normalized_crs_local_family(family) == QWEN_EDIT_2509_FAMILY


def _is_sensenova_family(family: str) -> bool:
    return _normalized_crs_local_family(family) == "sensenova"


def _chosen_crs_local_family(generator_sources: dict[str, Any] | None) -> str:
    for entry in (generator_sources or {}).get("local") or []:
        if isinstance(entry, dict) and entry.get("enabled"):
            return _normalized_crs_local_family(str(entry.get("family") or entry.get("model") or "")) or ""
    return ""


def _coerce_single_crs_sources(generator_sources: dict[str, Any] | None) -> dict[str, Any]:
    """One CRS slot. AUTO chooses among available CRS providers; not a Qwen-only type.

    Explicit GPT Image 2 is honored. Explicit Character Creator local families
    (qwen_edit_2509, qwen2512, flux, krea2, illustrious) are kept. Omitted /
    auto / unknown families stay family=auto so enqueue can select FLUX when
    advertised, else Qwen. AUTO is a chooser, not a Qwen-only type.
    """
    parsed = _parse_generator_sources(generator_sources)
    for entry in parsed.get("api_entries") or []:
        if not entry.get("enabled"):
            continue
        blob = f"{entry.get('model') or ''} {entry.get('modelId') or ''}"
        if _is_gpt_image_2_model(blob):
            return {
                "local": None,
                "api": [
                    {
                        "model": entry.get("model") or "gpt-image-2-kie",
                        "providerId": entry.get("providerId") or "kie",
                        "modelId": entry.get("modelId") or "gpt-image-2",
                        "enabled": True,
                        "batchCount": 1,
                    }
                ],
                "stage2Enabled": False,
            }
    family = "auto"
    for entry in parsed.get("local_entries") or []:
        if not entry.get("enabled"):
            continue
        fam = str(entry.get("family") or entry.get("model") or "").strip().lower()
        honored = _normalized_crs_local_family(fam)
        family = honored or "auto"
        break
    return {
        "local": [{"family": family, "enabled": True, "batchCount": 1}],
        "api": None,
        "stage2Enabled": False,
    }


def resolve_character_creator_generator_sources(
    *,
    args: dict[str, Any] | None = None,
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Character Creator generator plan: explicit args, else saved prefs, else AUTO."""
    raw = None
    if isinstance(args, dict):
        raw = args.get("generatorSources") or args.get("generator")
    if isinstance(raw, str) and "gpt-image-2" in raw.lower():
        return _coerce_single_crs_sources(
            {
                "local": None,
                "api": [
                    {
                        "model": "gpt-image-2-kie",
                        "providerId": "kie",
                        "modelId": "gpt-image-2",
                        "enabled": True,
                        "batchCount": 1,
                    }
                ],
            }
        )
    if isinstance(raw, dict):
        return _coerce_single_crs_sources(raw)
    prefs = None
    if isinstance(pack, dict):
        prefs = pack.get("generatorPreferences") or pack.get("generatorSources")
    if isinstance(prefs, dict):
        return _coerce_single_crs_sources(prefs)
    return _coerce_single_crs_sources(None)


def _parse_generator_sources(generator_sources: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize creator source toggles. Omitted sources keep legacy local-auto routing."""
    if generator_sources is None:
        return {
            "explicit": False,
            "list_shape": False,
            "local_enabled": True,
            "api_enabled": False,
            "chosen_local": "",
            "chosen_api": "",
            "stage2_enabled": False,
            "chosen_stage2_family": "",
            "local_entries": [],
            "api_entries": [],
        }
    local = generator_sources.get("local")
    api = generator_sources.get("api")
    list_shape = isinstance(local, list) or isinstance(api, list)
    local_enabled, local_entries = _parse_local_source_entries(local)
    api_enabled, api_entries = _parse_api_source_entries(api)
    stage2_enabled = bool(generator_sources.get("stage2Enabled"))
    chosen_stage2 = str(generator_sources.get("stage2Family") or "").strip().lower()
    if isinstance(local, dict):
        chosen_stage2 = str(local.get("stage2Family") or chosen_stage2).strip().lower()
        stage2_enabled = bool(local.get("stage2Enabled") or stage2_enabled)
    if chosen_stage2 in {"", "auto"}:
        chosen_stage2 = ""

    chosen_local = ""
    if not list_shape:
        for entry in local_entries:
            if entry.get("family") and entry.get("family") != "auto":
                chosen_local = str(entry["family"])
                break
    chosen_api = ""
    if not list_shape:
        for entry in api_entries:
            if entry.get("model"):
                chosen_api = str(entry["model"])
                break

    return {
        "explicit": True,
        "list_shape": list_shape,
        "local_enabled": local_enabled,
        "api_enabled": api_enabled,
        "chosen_local": chosen_local,
        "chosen_api": chosen_api,
        "stage2_enabled": stage2_enabled,
        "chosen_stage2_family": chosen_stage2,
        "local_entries": local_entries,
        "api_entries": api_entries,
    }


def _resolve_pack_phase_source(pack: dict[str, Any]) -> dict[str, Any]:
    """Resolve provider/model routing for the non-hero sheet phases.

    Coverage x6 (and details x6 / performance x2 when enabled) must honor the
    SAME Local/Cloud generator selection the hero stage honors — the pack's
    persisted generatorSources (legacy generatorPreferences). This is the
    CDX-001 repair: Cloud-only selections must never enqueue a local qwen2512
    job for any phase.

    Returns _enqueue_txt2img kwargs:

    * provider_kind — "local" or "api".
    * model_family_preference — local family ("qwen2512" default) or the
      hosted API model id.
    * hosted_model_id — the selected API model, or None for local.
    * force_workflow_key — the Certified txt2img workflow key for the
      resolved source (informational/route pinning; API enqueues ignore it).
    * selected_source — human/creator-facing source label.

    Raises VisualSheetSourceUnavailableError (a ValueError) instead of
    silently falling back to the default local model when the selected source
    cannot serve the phase — Cloud-only with no API model, or no source
    enabled at all.
    """
    sources = pack.get("generatorSources")
    if sources is None:
        sources = pack.get("generatorPreferences")
    parsed = _parse_generator_sources(sources)
    if not parsed["explicit"]:
        # Legacy packs / no generatorSources: preserve the historical
        # local qwen2512 auto routing for every non-hero phase.
        return {
            "provider_kind": "local",
            "model_family_preference": "qwen2512",
            "hosted_model_id": None,
            "force_workflow_key": "qwen2512.txt2img",
            "selected_source": "",
        }
    if not parsed["local_enabled"] and not parsed["api_enabled"]:
        raise VisualSheetSourceUnavailableError(
            "No image generator enabled. Enable a Local or Cloud generator to create character sheets."
        )
    if parsed["api_enabled"] and not parsed["local_enabled"]:
        # Cloud-only: every phase runs on the selected hosted model. Never a
        # local fallback.
        model = parsed["chosen_api"]
        if parsed["list_shape"]:
            enabled_api = [
                e
                for e in parsed["api_entries"]
                if e.get("enabled") and (e.get("model") or e.get("modelId"))
            ]
            if enabled_api:
                model = str(enabled_api[0].get("model") or enabled_api[0].get("modelId") or "")
        if not model:
            raise VisualSheetSourceUnavailableError(
                "Cloud generator is enabled but no API model is selected; "
                "cannot generate character sheet phases."
            )
        api_family = _hosted_family_for_model(model) or model
        return {
            "provider_kind": "api",
            "model_family_preference": model,
            "hosted_model_id": model,
            "force_workflow_key": _txt2img_workflow_key(api_family, model),
            "selected_source": model,
        }
    # Local enabled (optionally alongside Cloud): phases run on the selected
    # local family, preserving the default qwen2512 routing for Auto Select.
    # List-shaped sources carry per-row families (chosen_local is empty then) —
    # mirror _expand_list_slots: first enabled explicit family wins, else auto.
    chosen_local = parsed["chosen_local"]
    if parsed["list_shape"] and not chosen_local:
        explicit_local = [
            e
            for e in parsed["local_entries"]
            if e.get("enabled") and not _is_auto_family(str(e.get("family") or ""))
        ]
        if explicit_local:
            chosen_local = str(explicit_local[0].get("family") or "")
    return {
        "provider_kind": "local",
        "model_family_preference": chosen_local or "qwen2512",
        "hosted_model_id": None,
        "force_workflow_key": _txt2img_workflow_key(chosen_local or "qwen2512"),
        "selected_source": chosen_local or "",
    }



def _fal_image_model_id(hosted_model_id: str | None) -> str | None:
    """Fal still-image endpoint for a hosted dock id, or None."""
    try:
        from ..fal_catalog import fal_image_model_id_for_dock

        return fal_image_model_id_for_dock(hosted_model_id)
    except Exception:
        return None


def _hosted_family_for_model(model_id: str) -> str:
    """Map a hosted dock model id (nano-banana-kie) to an image-product family."""
    if not model_id:
        return ""
    try:
        from ..production_control.runtime_map import image_family_for_dock_model

        fam = image_family_for_dock_model(model_id)
        if fam:
            return str(fam)
    except Exception:
        pass
    mid = str(model_id).lower()
    if "nano-banana" in mid or "gpt-image" in mid or "seedream" in mid or mid.startswith("imagen"):
        return "imagen"
    if "flux" in mid:
        return "flux"
    if "krea" in mid:
        return "krea2"
    return mid.split("-")[0] if mid else ""


def _normalize_local_family(family: str) -> str:
    fam = (family or "").strip().lower()
    if fam in {"", "auto"}:
        return ""
    if fam in {"krea", "krea-2", "krea_2", "krea2-turbo", "krea2-turbo-local", "krea2-raw-local"}:
        return "krea2"
    return fam


def _txt2img_workflow_key(family: str, hosted_model_id: str | None = None) -> str:
    fam = (family or "").strip().lower()
    mid = (hosted_model_id or "").lower()
    if fam in {QWEN_EDIT_2509_FAMILY, "qwen-edit-2509", "qwen-image-edit-2509"}:
        return QWEN_EDIT_2509_WORKFLOW_KEY
    if fam in {"sensenova", "sensenova_u15", "sensenova-u15", "sensenova-u15-local"}:
        return "sensenova.crs"
    if fam == "krea2" or "krea" in mid:
        if "raw" in mid:
            return "krea2.raw_txt2img"
        return KREA_LOCAL_TXT2IMG_KEY
    return f"{fam}.txt2img" if fam else "imagen.txt2img"


def _krea_model_display(model_id: str) -> str:
    mid = (model_id or "").strip()
    if mid in KREA_HOSTED_MODEL_LABELS:
        return KREA_HOSTED_MODEL_LABELS[mid]
    low = mid.lower()
    if "krea" in low and "turbo" in low:
        return "Krea 2 Turbo"
    if "krea" in low and "medium" in low:
        return "Krea 2 Medium"
    if "krea" in low and "large" in low:
        return "Krea 2 Large"
    if "krea" in low and "raw" in low:
        return "Krea 2 RAW"
    if "krea" in low:
        return mid or "Krea 2"
    return mid


# Creator-facing local family names for candidate provenance.
# Keep these short; never show a raw family id (illustrious, qwen2512).
_PROVENANCE_FAMILY_NAMES: dict[str, str] = {
    "illustrious": "Illustrious XL",
    "qwen_edit_2509": "Qwen Image Edit 2509",
    "qwen2512": "Qwen Image 2512",
    "qwen": "Qwen Image 2512",
    "zimage": "Z-Image Turbo",
    "flux": "FLUX.1 Kontext",
    "krea2": "Local Krea 2",
    "sensenova": "SenseNova U1.5",
}


def _local_family_display(family: str | None, model: str | None) -> str:
    raw = str(family or model or "").strip()
    key = raw.lower().split(".", 1)[0]
    if key in _PROVENANCE_FAMILY_NAMES:
        return _PROVENANCE_FAMILY_NAMES[key]
    return raw or ""


def _candidate_provenance_label(
    *,
    provider_kind: str,
    provider: str | None,
    model: str | None,
    hosted_model_id: str | None,
    selected_source: str | None,
    conditioning_mode: str | None,
) -> str:
    pool = "API" if provider_kind == "api" else "LOCAL"
    blob = " ".join(
        str(x or "") for x in (provider, hosted_model_id, selected_source, model)
    ).lower()
    if provider_kind == "api" and ("krea" in blob or (provider or "").lower() == "krea"):
        name = _krea_model_display(str(hosted_model_id or selected_source or model or ""))
        core = f"{pool} — Krea / {name}"
    elif provider_kind == "api":
        name = selected_source or hosted_model_id or model or ""
        core = f"{pool} — {name}" if name else pool
    else:
        name = _local_family_display(selected_source, model)
        core = f"{pool} — {name}" if name else pool
    if conditioning_mode == CONDITIONING_REFERENCE_CONDITIONED:
        return f"{core} — Reference Conditioned"
    if conditioning_mode == CONDITIONING_PROFILE_GUIDED:
        return f"{core} — Profile Guided"
    return core


def _hosted_provider_label(model_id: str) -> str:
    mid = (model_id or "").lower()
    # Krea ids may also contain a host suffix (krea2-turbo-fal). Krea wins.
    if "krea" in mid:
        return "krea"
    if "kie" in mid:
        return "kie"
    if "fal" in mid:
        return "fal"
    if "wavespeed" in mid:
        return "wavespeed"
    return "api"


def _reference_workflow_key(family: str) -> str | None:
    """Certified workflow that consumes reference pixels for this family, if any."""
    if not family:
        return None
    if _is_qwen_family(family):
        # Never steal ERS I2I (qwen2512.ref / environment-ref) for a CRS.
        return None
    if family in {QWEN_EDIT_2509_FAMILY, "qwen-edit-2509", "qwen-image-edit-2509"}:
        return QWEN_EDIT_2509_CRS_KEY
    if family in {"sensenova", "sensenova_u15", "sensenova-u15", "sensenova-u15-local"}:
        return "sensenova.crs"
    if family == REFERENCE_LOCKED_FAMILY:
        return REFERENCE_LOCKED_WORKFLOW_KEY
    try:
        from ..image_runtime.certified_registry import get_workflow, list_workflows

        for key in (f"{family}.ref_edit", f"{family}.edit", f"{family}.img2img", f"{family}.ref"):
            wf = get_workflow(key)
            if wf and wf.status == "Certified" and bool((wf.capabilities or {}).get("supportsReferences")):
                if key == QWEN_REF_WORKFLOW_KEY:
                    continue
                return key
        for wf in list_workflows(model_family=family):
            if wf.status != "Certified":
                continue
            if str(wf.workflow_key or "") == QWEN_REF_WORKFLOW_KEY:
                continue
            if bool((wf.capabilities or {}).get("supportsReferences")):
                return wf.workflow_key
    except Exception:
        return None
    return None


def _build_stage1_route(
    *,
    family: str,
    reference_asset_id: str | None,
    provider_kind: str,
    hosted_model_id: str | None = None,
    selected_source: str = "",
) -> dict[str, Any]:
    """Build one candidate Stage 1 route. Selected family is authoritative."""
    fam = (family or "").strip().lower()
    if _is_sensenova_family(fam):
        selected = selected_source or hosted_model_id or family
        return {
            "modelFamilyPreference": "sensenova",
            "workflowKey": "sensenova.crs",
            "referenceAssetId": reference_asset_id,
            "referenceLocked": bool(reference_asset_id),
            "referenceFidelityMode": REFERENCE_FIDELITY_MODE_FULL if reference_asset_id else None,
            "source_asset_id": reference_asset_id,
            "denoise": None,
            "conditioningMode": (
                CONDITIONING_REFERENCE_CONDITIONED if reference_asset_id else CONDITIONING_PROFILE_GUIDED
            ),
            "providerKind": provider_kind,
            "hostedModelId": hosted_model_id,
            "selectedSource": selected,
        }
    if _is_qwen_edit_2509_family(fam):
        if not reference_asset_id:
            raise ValueError(QWEN_EDIT_2509_NEEDS_CROP)
        selected = selected_source or hosted_model_id or family
        return {
            "modelFamilyPreference": QWEN_EDIT_2509_FAMILY,
            "workflowKey": QWEN_EDIT_2509_CRS_KEY,
            "referenceAssetId": reference_asset_id,
            "referenceLocked": True,
            "referenceFidelityMode": REFERENCE_FIDELITY_MODE_FULL,
            "source_asset_id": reference_asset_id,
            "denoise": None,
            "conditioningMode": CONDITIONING_REFERENCE_CONDITIONED,
            "providerKind": provider_kind,
            "hostedModelId": hosted_model_id,
            "selectedSource": selected,
        }
    supports_ref = bool(fam and _family_supports_references(fam))
    ref_key = _reference_workflow_key(fam) if supports_ref else None
    selected = selected_source or hosted_model_id or family
    if reference_asset_id and supports_ref and ref_key and provider_kind != "api":
        if ref_key == QWEN_REF_WORKFLOW_KEY:
            # Fail-close the illegal ERS I2I route. Fall through to
            # qwen2512.txt2img PROFILE_GUIDED (honest: refs are not pixels).
            supports_ref = False
            ref_key = None
    if reference_asset_id and supports_ref and ref_key and provider_kind != "api":
        return {
            "modelFamilyPreference": family,
            "workflowKey": ref_key,
            "referenceAssetId": reference_asset_id,
            "referenceLocked": True,
            "referenceFidelityMode": (
                REFERENCE_FIDELITY_MODE_LIMITED if family == "zimage" else REFERENCE_FIDELITY_MODE_FULL
            ),
            "source_asset_id": reference_asset_id,
            "denoise": REFERENCE_FIDELITY_DENOISE if family == "zimage" else None,
            "conditioningMode": CONDITIONING_REFERENCE_CONDITIONED,
            "providerKind": provider_kind,
            "hostedModelId": hosted_model_id,
            "selectedSource": selected,
        }
    # Hosted API, or txt2img-only local family, or no reference: PROFILE_GUIDED
    # when a reference exists (pixels do not participate). No-reference stays unlocked.
    mode = CONDITIONING_PROFILE_GUIDED if reference_asset_id else None
    workflow = _txt2img_workflow_key(family, hosted_model_id)
    return {
        "modelFamilyPreference": family,
        "workflowKey": workflow,
        "referenceAssetId": None,
        "referenceLocked": False,
        "referenceFidelityMode": None,
        "source_asset_id": None,
        "denoise": None,
        "conditioningMode": mode,
        "providerKind": provider_kind,
        "hostedModelId": hosted_model_id,
        "selectedSource": selected,
    }


def _legacy_slots(
    *,
    parsed: dict[str, Any],
    candidate_count: int,
    visual_style: str | None,
) -> list[dict[str, Any]]:
    local_families: list[str] = []
    if (not parsed["explicit"]) or parsed["local_enabled"]:
        if parsed["chosen_local"]:
            local_families = [parsed["chosen_local"]]
        else:
            # CRS AUTO: FLUX primary, Qwen fallback. Not a style-mix of random families.
            local_families = [_resolve_crs_auto_family()]

    api_model = parsed["chosen_api"] if parsed["api_enabled"] else ""
    api_family = _hosted_family_for_model(api_model) if api_model else ""
    count = max(1, int(candidate_count or 1))
    slots: list[dict[str, Any]] = []
    if parsed["explicit"] and parsed["api_enabled"] and not parsed["local_enabled"]:
        for i in range(count):
            slots.append(
                {
                    "providerKind": "api",
                    "family": api_family or api_model,
                    "hostedModelId": api_model,
                    "selectedSource": api_model,
                    "providerId": "",
                    "modelId": api_model,
                    "batchIndex": i + 1,
                    "batchOf": count,
                    "autoSelect": False,
                }
            )
    elif parsed["explicit"] and parsed["local_enabled"] and parsed["api_enabled"] and api_model:
        for i in range(count):
            if i % 2 == 1:
                slots.append(
                    {
                        "providerKind": "api",
                        "family": api_family or api_model,
                        "hostedModelId": api_model,
                        "selectedSource": api_model,
                        "providerId": "",
                        "modelId": api_model,
                        "batchIndex": i + 1,
                        "batchOf": count,
                        "autoSelect": False,
                    }
                )
            else:
                fam = local_families[(i // 2) % len(local_families)] if local_families else "zimage"
                slots.append(
                    {
                        "providerKind": "local",
                        "family": fam,
                        "hostedModelId": None,
                        "selectedSource": fam,
                        "providerId": "",
                        "modelId": fam,
                        "batchIndex": i + 1,
                        "batchOf": count,
                        "autoSelect": False,
                    }
                )
    else:
        for i in range(count):
            fam = local_families[i % len(local_families)] if local_families else "zimage"
            slots.append(
                {
                    "providerKind": "local",
                    "family": fam,
                    "hostedModelId": None,
                    "selectedSource": fam,
                    "providerId": "",
                    "modelId": fam,
                    "batchIndex": i + 1,
                    "batchOf": count,
                    "autoSelect": not bool(parsed.get("chosen_local")),
                }
            )
    return slots


def _expand_list_slots(
    *,
    parsed: dict[str, Any],
    visual_style: str | None,
) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    if parsed["local_enabled"]:
        explicit = [
            e
            for e in parsed["local_entries"]
            if e.get("enabled") and not _is_auto_family(str(e.get("family") or ""))
        ]
        auto = [
            e
            for e in parsed["local_entries"]
            if e.get("enabled") and _is_auto_family(str(e.get("family") or ""))
        ]
        if explicit:
            for entry in explicit:
                n = _clamp_batch_count(entry.get("batchCount") or 1)
                family = str(entry.get("family") or "")
                for i in range(n):
                    slots.append(
                        {
                            "providerKind": "local",
                            "family": family,
                            "hostedModelId": None,
                            "selectedSource": family,
                            "providerId": "",
                            "modelId": family,
                            "batchIndex": i + 1,
                            "batchOf": n,
                            "autoSelect": False,
                        }
                    )
        elif auto:
            n = _clamp_batch_count(auto[0].get("batchCount") or 1)
            mix = [_resolve_crs_auto_family()]
            for i in range(n):
                fam = mix[i % len(mix)]
                slots.append(
                    {
                        "providerKind": "local",
                        "family": fam,
                        "hostedModelId": None,
                        "selectedSource": fam,
                        "providerId": "",
                        "modelId": fam,
                        "batchIndex": i + 1,
                        "batchOf": n,
                        "autoSelect": True,
                    }
                )
    if parsed["api_enabled"]:
        enabled_api = [e for e in parsed["api_entries"] if e.get("enabled") and (e.get("model") or e.get("modelId"))]
        if parsed["api_enabled"] and not enabled_api:
            raise ValueError("Cloud generator is enabled but no API model is selected.")
        for entry in enabled_api:
            n = _clamp_batch_count(entry.get("batchCount") or 1)
            model = str(entry.get("model") or entry.get("modelId") or "")
            provider_id = str(entry.get("providerId") or "")
            model_id = str(entry.get("modelId") or model)
            api_family = _hosted_family_for_model(model) if model else ""
            for i in range(n):
                slots.append(
                    {
                        "providerKind": "api",
                        "family": api_family or model,
                        "hostedModelId": model,
                        "selectedSource": model,
                        "providerId": provider_id,
                        "modelId": model_id,
                        "batchIndex": i + 1,
                        "batchOf": n,
                        "autoSelect": False,
                    }
                )
    return slots


def _build_candidate_routing_plan(
    *,
    candidate_count: int,
    reference_asset_id: str | None,
    visual_style: str | None = None,
    generator_sources: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Per-candidate routing plan honoring the selected Local / API source.

    Product laws:
    * Selected source/model is authoritative — no silent Comfy/Z-Image substitute.
    * Unchecked sources create zero jobs (master and per-row).
    * List-shaped generatorSources expand enabled batchCounts; Auto Select is
      ignored when any explicit local family is enabled.
    * AUTO CRS law views resolve FLUX (txt2img, or img2img with a real identity
      crop) when that workflow is Certified; otherwise Qwen. Never Krea, never
      a silent random-family substitute, never qwen2512.ref as the canvas.
    * Reference + reference-capable family → REFERENCE_CONDITIONED (pixels).
    * Reference + Qwen Image 2512 → PROFILE_GUIDED qwen2512.txt2img (honest:
      attached picture is not consumed as pixels). Never qwen2512.ref (ERS I2I)
      and never a silent zimage.ref_edit substitute.
    * Reference + txt2img-only (Illustrious) → PROFILE_GUIDED (no pixels).
    """
    parsed = _parse_generator_sources(generator_sources)
    if parsed["explicit"] and not parsed["local_enabled"] and not parsed["api_enabled"]:
        raise ValueError(
            "No image generator enabled. Enable a Local or Cloud generator to create character sheets."
        )
    if (
        parsed["explicit"]
        and not parsed["list_shape"]
        and parsed["api_enabled"]
        and not parsed["local_enabled"]
        and not parsed["chosen_api"]
    ):
        raise ValueError("Cloud generator is enabled but no API model is selected.")

    stage2: dict[str, Any] | None = None
    if parsed["stage2_enabled"] and parsed["chosen_stage2_family"]:
        stage2_key = _stage2_workflow_key(parsed["chosen_stage2_family"])
        if stage2_key:
            stage2 = {
                "modelFamilyPreference": parsed["chosen_stage2_family"],
                "workflowKey": stage2_key,
                "referenceAssetId": None,
                "referenceLocked": False,
                "referenceFidelityMode": None,
                "source_asset_id": None,
                "denoise": STAGE2_DEFAULT_DENOISE,
            }

    if parsed["list_shape"]:
        slots = _expand_list_slots(parsed=parsed, visual_style=visual_style)
        if not slots:
            raise ValueError(
                "No image generator enabled. Enable a Local or Cloud generator to create character sheets."
            )
    else:
        slots = _legacy_slots(parsed=parsed, candidate_count=candidate_count, visual_style=visual_style)

    plan: list[dict[str, Any]] = []
    for slot in slots:
        if slot.get("autoSelect") and str(slot.get("providerKind") or "") == "local":
            fam = _resolve_crs_auto_family(has_identity_crop=bool(reference_asset_id))
            slot["family"] = fam
            slot["selectedSource"] = fam
            slot["modelId"] = fam
        stage1 = _build_stage1_route(
            family=str(slot["family"] or ""),
            reference_asset_id=reference_asset_id,
            provider_kind=str(slot["providerKind"]),
            hosted_model_id=slot.get("hostedModelId"),
            selected_source=str(slot.get("selectedSource") or ""),
        )
        stage1["providerId"] = slot.get("providerId") or ""
        stage1["modelId"] = slot.get("modelId") or stage1.get("hostedModelId") or slot.get("family")
        use_stage2 = stage2 if slot["providerKind"] == "local" else None
        entry = {
            "stage1": stage1,
            "stage2": use_stage2,
            "stage2Enabled": bool(use_stage2),
            "batchIndex": int(slot.get("batchIndex") or 1),
            "batchOf": int(slot.get("batchOf") or 1),
            "autoSelect": bool(slot.get("autoSelect")),
            **stage1,
        }
        plan.append(entry)
    # Single canonical CRS: exactly one routing slot, never a candidate batch.
    if plan:
        first = plan[0]
        first["batchIndex"] = 1
        first["batchOf"] = 1
        return [first]
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


def _candidate_view_specs(
    required_views: list[str] | None = None,
) -> list[tuple[str, str, dict[str, Any], list[str] | None]]:
    """Default Generate views: front, side, back, head/neck close-up.

    When ``required_views`` is supplied (Character Identity Packet), those
    views drive order and membership. Accepts internal roles or canonical
    names (front_full, side_full, ...). Isolated 5-view law still maps if
    three_quarter_full is explicitly requested.
    """
    coverage = {role: (goal, comp) for role, goal, comp in _coverage_role_specs()}
    side = coverage["full_body_side_left"]
    back = coverage["full_body_back"]
    three_quarter = {
        "shot_type": "single-camera three-quarter reference",
        "framing": "full body",
        "camera_angle": "eye level",
        "orientation": "three-quarter front view",
        "environment": "plain gray background",
        "lighting": "soft studio light",
        "pose": "standing in a neutral three-quarter pose",
        "focus": "face, wardrobe silhouette, and body proportions",
        "full_body": True,
    }
    specs = [
        (
            "hero_identity",
            "a cinematic full-body front reference",
            {
                **dict(FULL_BODY_CASTING_COMPOSITION),
                "camera_angle": "eye level, front-facing",
                "orientation": "front view",
            },
            list(FULL_BODY_CASTING_NEGATIVE_RULES),
        ),
        (
            "full_body_three_quarter_front",
            "a production full-body three-quarter reference",
            three_quarter,
            list(FULL_BODY_CASTING_NEGATIVE_RULES),
        ),
        ("full_body_side_left", side[0], dict(side[1]), None),
        ("full_body_back", back[0], dict(back[1]), None),
        (
            "closeup_front",
            "a front-facing head-and-shoulders identity portrait",
            dict(CLOSEUP_FRONT_COMPOSITION),
            list(CLOSEUP_FRONT_NEGATIVE_RULES),
        ),
    ]
    default_four = [item for item in specs if item[0] in CANDIDATE_SHEET_VIEW_ROLES]
    if not required_views:
        return default_four
    by_role = {item[0]: item for item in specs}
    by_role["full_body_front"] = by_role["hero_identity"]
    by_canonical = {VIEW_ROLE_CANONICAL.get(item[0], item[0]): item for item in specs}
    by_canonical["full_body_front"] = by_role["hero_identity"]
    ordered: list[tuple[str, str, dict[str, Any], list[str] | None]] = []
    seen: set[str] = set()
    for view in required_views:
        key = str(view or "").strip()
        item = by_role.get(key) or by_canonical.get(key)
        if item and item[0] not in seen:
            seen.add(item[0])
            ordered.append(item)
    return ordered or default_four


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


def _sheet_profile_with_wardrobe(db: Session, profile: dict[str, Any] | None) -> dict[str, Any]:
    """Attach active wardrobe fields so Adept panels can draw them."""
    blob = dict(profile or {})
    if blob.get("wardrobe") or blob.get("active_wardrobe"):
        return blob
    wid = blob.get("active_wardrobe_id")
    if not wid:
        return blob
    from .models import CharacterWardrobeRow

    row = db.get(CharacterWardrobeRow, str(wid))
    if row:
        blob["wardrobe"] = {
            "name": row.name or "",
            "description": row.description or "",
            "materials": row.materials or "",
            "colors": row.colors or "",
            "footwear": getattr(row, "footwear", "") or "",
            "accessories": getattr(row, "accessories", "") or "",
        }
    return blob


def _compose_character_sheet_grid(
    view_paths: list[str],
    out_path: str,
    *,
    profile: dict[str, Any] | None = None,
    labels: list[str] | None = None,
    roles: list[str] | None = None,
    layout_out: dict[str, Any] | None = None,
) -> str:
    """Compose view images into a Character Sheet (PIL).

    Four views stay an unlabeled 2x2 (variant / legacy). Five law views are
    an Adept-drawn 3x2 production document: view labels, header, and
    notes/wardrobe/specs panels. Tiles use a non-distorting contain policy.
    """
    n = len(view_paths)
    four = CHARACTER_SHEET_GRID_COLS * CHARACTER_SHEET_GRID_ROWS
    if n == 5:
        result = compose_labeled_character_sheet(
            view_paths,
            out_path,
            profile=profile,
            labels=labels or list(LAW_VIEW_DISPLAY_LABELS),
            roles=roles,
        )
        if layout_out is not None:
            layout_out.clear()
            layout_out.update(result)
        return str(result["path"])
    if n != four:
        raise ValueError(
            f"character sheet grid requires {four} or 5 view images, got {n}"
        )
    from PIL import Image, ImageOps

    cols, rows = CHARACTER_SHEET_GRID_COLS, CHARACTER_SHEET_GRID_ROWS
    tile = CHARACTER_SHEET_TILE_SIZE
    grid = Image.new("RGB", (tile * cols, tile * rows), (24, 24, 24))
    for idx, src in enumerate(view_paths):
        im = Image.open(src).convert("RGB")
        contained = ImageOps.contain(im, (tile, tile), method=getattr(Image, "Resampling", Image).LANCZOS)
        canvas = Image.new("RGB", (tile, tile), (24, 24, 24))
        x = (tile - contained.width) // 2
        y = (tile - contained.height) // 2
        canvas.paste(contained, (x, y))
        col = idx % cols
        row = idx // cols
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
    layout: dict[str, Any] | None = None,
) -> Asset:
    """Register the composed Character Sheet as a Library asset.

    The 4 source view asset ids are recorded in ``prompt_meta_json`` lineage so
    they remain queryable for provenance/continuity without being duplicated.
    For two-stage candidates, ``stage1_source_asset_ids`` records the identity-
    locked Stage 1 outputs when the composed sheet uses Stage 2 outputs.
    """
    import os

    grid = {
        "cols": CHARACTER_SHEET_GRID_COLS,
        "rows": CHARACTER_SHEET_GRID_ROWS,
        "tileSize": CHARACTER_SHEET_TILE_SIZE,
    }
    if layout and isinstance(layout.get("grid"), dict):
        grid = dict(layout["grid"])
    meta = {
        "objective": "character_sheet_composed",
        "characterId": character_id,
        "candidateIndex": candidate_index,
        "compositionIntent": COMPOSITION_INTENT_CHARACTER_SHEET,
        "sourceAssetIds": list(source_asset_ids),
        "stage1SourceAssetIds": list(stage1_source_asset_ids or []),
        "grid": grid,
        "lineage": lineage,
        "createdAt": _now(),
        "composer": (layout or {}).get("composer") or "adept",
    }
    if layout:
        meta["layout"] = layout.get("layout") or "law_views_labeled"
        meta["labels"] = list(layout.get("labels") or [])
        meta["drawnStrings"] = list(layout.get("drawnStrings") or [])
        meta["header"] = layout.get("header") or {}
        meta["panels"] = [
            {
                "id": panel.get("id"),
                "title": panel.get("title"),
                "text": panel.get("text") or "",
                "bbox": panel.get("bbox"),
            }
            for panel in (layout.get("panels") or [])
        ]
        meta["viewCells"] = layout.get("views") or []
        if layout.get("width"):
            meta["width"] = layout.get("width")
        if layout.get("height"):
            meta["height"] = layout.get("height")
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
            vj["error"] = public_job_error(job.message) or job.status
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
                vj["error"] = public_job_error(stage2_job.message) or stage2_job.status
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
    approved_hero = ""
    try:
        approved_hero = str(service.resolve_approved_reference(db, character_id, "hero_identity") or "").strip()
    except Exception:
        approved_hero = ""
    pack_approved = str(pack.get("approvedHeroIdentity") or pack.get("approved_hero_identity") or "").strip()
    persist_hero = {aid for aid in (approved_hero, pack_approved) if aid}
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
        # Draft pack hero is not canon. Approve is the only persist / reference writer.
        if str(role) == "hero_identity" and str(aid) not in persist_hero:
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


def save_visual_sheet_preferences(
    db: Session,
    project_id: str,
    character_id: str,
    generator_sources: dict[str, Any] | None,
) -> dict[str, Any]:
    """Persist the NEXT generation plan without mutating generated candidates."""
    service.get_profile(db, project_id, character_id)
    pack = _load_pack_raw(db, character_id) or {
        "characterId": character_id,
        "projectId": project_id,
        "status": "NOT_STARTED",
        "jobs": {},
        "roleAssets": {},
        "candidates": [],
        "mock": False,
    }
    pack["generatorPreferences"] = generator_sources
    return _save_pack(db, project_id, character_id, pack)


def _hydrate_candidate_layout(db: Session, item: dict[str, Any]) -> bool:
    """Recompute layout flags from image dimensions + four_view intent."""
    if not isinstance(item, dict):
        return False
    views = item.get("viewJobs") if isinstance(item.get("viewJobs"), list) else []
    sheet_id = item.get("sheetAssetId")
    # Per-camera tiles are not the sheet. Do not assess a front tile as a 4-view.
    if views and not sheet_id:
        return False
    before = item.get("layoutNoncompliant")
    path = None
    aid = sheet_id or (None if views else item.get("assetId"))
    if aid:
        asset = db.get(Asset, str(aid))
        if asset and getattr(asset, "path", None):
            path = asset.path
    blob = item.get("layoutAssessment") or item.get("characterSheetLayout") or {}
    w = blob.get("width") if isinstance(blob, dict) else None
    h = blob.get("height") if isinstance(blob, dict) else None
    existing = blob if isinstance(blob, dict) else {}
    composed = bool(existing.get("composed")) or (
        str(item.get("layout") or "").strip().lower() in {"four_view", "four_panel_2x2"}
        and bool(sheet_id)
        and len(views) == 4
        and item.get("fourViewSingleOutput") is False
    )
    view_count = existing.get("viewCount")
    if composed:
        view_count = 4
    if path or (w and h) or composed:
        assessment = assess_four_view_layout(
            path, width=w, height=h, view_count=view_count, composed=composed
        )
        apply_layout_assessment_to_candidate(item, assessment)
    else:
        flag = candidate_layout_noncompliant(item)
        item["layoutNoncompliant"] = flag
        item["layout_noncompliant"] = flag
    return item.get("layoutNoncompliant") != before


def hydrate_visual_sheet_layout(db: Session, pack: dict[str, Any]) -> bool:
    """Walk pack candidates / hero entries and recompute layout flags."""
    if not isinstance(pack, dict):
        return False
    changed = False
    jobs = pack.get("jobs") if isinstance(pack.get("jobs"), dict) else {}
    items: list[Any] = []
    if isinstance(jobs.get("hero_candidates"), list):
        items.extend(jobs["hero_candidates"])
    if isinstance(jobs.get("hero"), dict):
        items.append(jobs["hero"])
    if isinstance(pack.get("candidates"), list):
        items.extend(pack["candidates"])
    seen: set[int] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        key = id(item)
        if key in seen:
            continue
        seen.add(key)
        if _hydrate_candidate_layout(db, item):
            changed = True
    return changed



_JOB_TERMINAL = frozenset({"done", "failed", "cancelled", "error"})
_JOB_COMPLETED = frozenset({"done"})
_JOB_FAILED = frozenset({"failed", "error"})
_JOB_CANCELLED = frozenset({"cancelled"})


def _iter_pack_job_ids(pack: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for item in list(pack.get("candidates") or []):
        if not isinstance(item, dict):
            continue
        for raw in [item.get("jobId") or item.get("job_id"), *[
            view.get("jobId") or view.get("job_id")
            for view in item.get("viewJobs") or []
            if isinstance(view, dict)
        ]]:
            jid = str(raw or "").strip()
            if jid and jid not in seen:
                seen.add(jid)
                ids.append(jid)
    return ids


def _pack_has_live_generation(db: Session, project_id: str, pack: dict[str, Any]) -> bool:
    if str(pack.get("status") or "").upper() not in {"GENERATING", "QUEUED", "RUNNING"}:
        return False
    for jid in _iter_pack_job_ids(pack):
        job = db.get(Job, jid)
        if not job or str(job.project_id) != project_id:
            continue
        if str(job.status or "").lower() in {"queued", "running", "pending", "starting"}:
            return True
    return False


def _cancel_replaced_draft_jobs(db: Session, project_id: str, prev_pack: dict[str, Any]) -> list[str]:
    """Stop in-flight draft tiles when Generate replaces the active draft."""
    cancelled: list[str] = []
    for item in list(prev_pack.get("candidates") or []):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        approval = str(item.get("approvalStatus") or item.get("approval_status") or "").strip().lower()
        if status == "approved" or approval == "approved" or item.get("approved") is True:
            continue
        job_ids = {str(item.get("jobId") or item.get("job_id") or "").strip()} - {""}
        for view in item.get("viewJobs") or []:
            if not isinstance(view, dict):
                continue
            jid = str(view.get("jobId") or view.get("job_id") or "").strip()
            if jid:
                job_ids.add(jid)
        for jid in job_ids:
            job = db.get(Job, jid)
            if not job or str(job.project_id) != project_id:
                continue
            if str(job.status or "").lower() in _JOB_TERMINAL | {"rejected"}:
                continue
            job.status = "cancelled"
            job.message = f"{job.message or ''} REPLACED_BY_REGENERATE".strip()
            cancelled.append(jid)
            try:
                from ..queue_worker import job_queue, schedule_comfy_interrupt_if_owner

                job_queue.cancel(jid)
                # cancel() only sets a cooperative flag a blocked native call
                # (SenseNova loader) never checks. Also POST /interrupt to Comfy
                # when this job owns the active prompt so the in-flight prompt
                # actually stops instead of running until host-RAM OOM.
                schedule_comfy_interrupt_if_owner(jid)
            except Exception:
                logger.exception("Could not signal queue cancel for replaced draft job %s", jid)
    return cancelled
_PACK_OWNER_STATES = frozenset({
    "READY_FOR_OWNER",
    "OWNER_APPROVED",
    "OWNER_APPROVED_WITH_PENDING",
})
_PACK_RECOMPUTE_STATES = frozenset({"GENERATING", "queued", "running", "QUEUED", "RUNNING"})


def _iter_pack_job_entries(node: Any, *, _seen: set[int] | None = None) -> list[dict[str, Any]]:
    """Collect mutable pack dicts that carry a child jobId / stage2JobId."""
    if _seen is None:
        _seen = set()
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        ident = id(node)
        if ident in _seen:
            return found
        _seen.add(ident)
        if node.get("jobId") or node.get("stage2JobId"):
            found.append(node)
        for value in node.values():
            found.extend(_iter_pack_job_entries(value, _seen=_seen))
    elif isinstance(node, list):
        for item in node:
            found.extend(_iter_pack_job_entries(item, _seen=_seen))
    return found


def _collect_pack_job_ids(pack: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for entry in _iter_pack_job_entries(pack):
        for key in ("jobId", "stage2JobId"):
            jid = str(entry.get(key) or "").strip()
            if jid and jid not in seen:
                seen.add(jid)
                ids.append(jid)
    return ids


def _optional_phase_job_ids(pack: dict[str, Any]) -> set[str]:
    """Coverage / details / performance job ids. Optional leftover after Adept compose."""
    jobs = pack.get("jobs") if isinstance(pack.get("jobs"), dict) else {}
    ids: set[str] = set()
    for phase in ("coverage", "details", "performance"):
        items = jobs.get(phase)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            jid = str(item.get("jobId") or "").strip()
            if jid:
                ids.add(jid)
    return ids


def _iter_crs_candidate_entries(pack: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    jobs = pack.get("jobs") if isinstance(pack.get("jobs"), dict) else {}
    if isinstance(jobs.get("hero_candidates"), list):
        items.extend(c for c in jobs["hero_candidates"] if isinstance(c, dict))
    if isinstance(jobs.get("hero"), dict):
        items.append(jobs["hero"])
    if isinstance(pack.get("candidates"), list):
        items.extend(c for c in pack["candidates"] if isinstance(c, dict))
    return items


def _labeled_adept_compose_done(
    pack: dict[str, Any] | None = None,
    *,
    candidate_entries: list[dict[str, Any]] | None = None,
) -> bool:
    """True after 5-view CRS_GENERATION labeled Adept compose (not four-panel)."""
    seen: set[int] = set()
    for item in list(candidate_entries or []) + (
        _iter_crs_candidate_entries(pack) if isinstance(pack, dict) else []
    ):
        ident = id(item)
        if ident in seen:
            continue
        seen.add(ident)
        sheet = str(item.get("sheetAssetId") or "").strip()
        views = item.get("viewJobs")
        if not sheet or not isinstance(views, list) or len(views) < 2:
            continue
        if item.get("fourViewSingleOutput") is True:
            continue
        return True
    return False


def _want_optional_sheet_phases(pack: dict[str, Any]) -> bool:
    return bool(pack.get("includeDetails")) or bool(pack.get("includePerformance"))


def _skip_optional_sheet_enqueue(pack: dict[str, Any]) -> bool:
    """CRS_GENERATION with both optional flags off must never plan extras.

    Not gated on compose. Approved leftover hero_identity must not unlock
    coverage / details / performance / turnaround_facial enqueue.
    """
    return not _want_optional_sheet_phases(pack)


def recompute_visual_sheet_pack_from_jobs(db: Session, pack: dict[str, Any]) -> bool:
    """Recompute pack child + parent status from Job rows.

    Jobs table is the canonical lifecycle; the pack JSON is a projection.
    Mirrors execution ``recompute_progress``:
    - all done → COMPLETED
    - any failed/error, rest terminal → FAILED
    - any cancelled, rest done/cancelled → CANCELLED
    - any running/queued → GENERATING
    Does not enqueue, attach Library assets, or rewrite approved identity / CRS.
    Returns True if the pack dict changed.
    """
    if not isinstance(pack, dict):
        return False
    job_ids = _collect_pack_job_ids(pack)
    if not job_ids:
        return False

    job_status: dict[str, str] = {}
    missing = False
    for jid in job_ids:
        job = db.get(Job, jid)
        if job is None:
            missing = True
            continue
        job_status[jid] = str(job.status or "")

    changed = False
    for entry in _iter_pack_job_entries(pack):
        jid = str(entry.get("jobId") or "").strip()
        if jid in job_status and entry.get("status") != job_status[jid]:
            entry["status"] = job_status[jid]
            changed = True
        stage2 = str(entry.get("stage2JobId") or "").strip()
        if stage2 in job_status and entry.get("stage2Status") != job_status[stage2]:
            entry["stage2Status"] = job_status[stage2]
            changed = True

    if missing or len(job_status) != len(job_ids):
        return changed

    current = str(pack.get("status") or "")
    if current in _PACK_OWNER_STATES or current not in _PACK_RECOMPUTE_STATES:
        return changed

    statuses = list(job_status.values())
    optional_ids = _optional_phase_job_ids(pack)
    required_statuses = [
        job_status[jid] for jid in job_ids if jid not in optional_ids and jid in job_status
    ]
    # Leftover coverage must not flip the parent to CANCELLED while law views
    # are still running or already done. Required view/hero jobs decide parent.
    leftover_optional = bool(optional_ids) and (
        _skip_optional_sheet_enqueue(pack) or _labeled_adept_compose_done(pack)
    )
    if leftover_optional and required_statuses:
        statuses_for_parent = required_statuses
    else:
        statuses_for_parent = statuses

    if all(s in _JOB_COMPLETED for s in statuses_for_parent):
        new_status = "COMPLETED"
    elif any(s in _JOB_FAILED for s in statuses_for_parent) and all(
        s in _JOB_TERMINAL for s in statuses_for_parent
    ):
        new_status = "FAILED"
    elif any(s in _JOB_CANCELLED for s in statuses_for_parent) and all(
        s in (_JOB_COMPLETED | _JOB_CANCELLED) for s in statuses_for_parent
    ):
        new_status = "CANCELLED"
    elif any(s in {"running", "queued"} for s in statuses_for_parent):
        new_status = "GENERATING"
    else:
        return changed

    if pack.get("status") != new_status:
        pack["status"] = new_status
        changed = True
    return changed


def cancel_visual_sheet_optional_phase_jobs(
    db: Session,
    project_id: str,
    character_id: str,
    job_ids: list[str] | set[str],
) -> dict[str, Any]:
    """Cancel leftover coverage/details/performance ids only.

    Isolates cancel to those extra job ids. Does not mark law-view / hero jobs
    cancelled and does not interrupt Comfy. Pack parent is recomputed from
    required jobs so a finished candidate stays complete.
    """
    pack = get_visual_sheet_pack(db, project_id, character_id)
    optional = _optional_phase_job_ids(pack)
    requested = {str(jid).strip() for jid in job_ids if str(jid).strip()}
    isolated = sorted(jid for jid in requested if jid in optional)
    skipped = sorted(requested - set(isolated))
    for jid in isolated:
        job = db.get(Job, jid)
        if not job:
            continue
        if str(job.status or "") in _JOB_TERMINAL:
            continue
        job.status = "cancelled"
        if hasattr(job, "stage"):
            job.stage = "cancelled"
        job.message = "Cancelled leftover optional coverage (law views untouched)"
    if isolated:
        db.commit()
    pack = get_visual_sheet_pack(db, project_id, character_id)
    return {
        "cancelledJobIds": isolated,
        "skippedJobIds": skipped,
        "pack": pack,
    }


def reconcile_generating_visual_sheet_packs(db: Session) -> int:
    """Startup hydrate: persist terminal pack status when all child jobs are terminal.

    Same class as execution ``reconcile_non_terminal_packs``. No sweeper daemon.
    Does not invent Library assets or treat pack crsRevision as approved CRS.
    """
    from .models import CharacterProfileRow, CharacterTraitRow

    rows = (
        db.query(CharacterTraitRow)
        .filter(CharacterTraitRow.key == PACK_TRAIT_KEY)
        .all()
    )
    healed = 0
    for row in rows:
        pack = _loads(row.value, {})
        if not isinstance(pack, dict):
            continue
        if str(pack.get("status") or "") not in _PACK_RECOMPUTE_STATES:
            continue
        profile = db.get(CharacterProfileRow, row.character_profile_id)
        if not profile:
            continue
        if recompute_visual_sheet_pack_from_jobs(db, pack):
            _save_pack(db, profile.project_id, profile.id, pack)
            healed += 1
    return healed


def get_visual_sheet_pack(db: Session, project_id: str, character_id: str) -> dict[str, Any]:
    service.get_profile(db, project_id, character_id)
    data = _load_pack_raw(db, character_id)
    if not data:
        return {"characterId": character_id, "status": "NOT_STARTED", "jobs": {}, "roleAssets": {}}
    healed = heal_pack_references(db, project_id, character_id)
    if healed:
        data = _load_pack_raw(db, character_id) or data
        data["referencesHealed"] = healed
    data["characterId"] = character_id
    changed = recompute_visual_sheet_pack_from_jobs(db, data)
    if hydrate_visual_sheet_layout(db, data):
        changed = True
    if changed:
        _save_pack(db, project_id, character_id, data)
    return data



def _enqueue_sensenova_crs_job(
    db: Session,
    project_id: str,
    *,
    character_id: str,
    profile: dict[str, Any],
    stage1_route: dict[str, Any],
    seed: int,
    char_slug: str,
    candidate_index: int,
    candidate_count: int,
    route: dict[str, Any],
    identity_packet: CharacterIdentityPacket | None = None,
    has_character_reference: bool = False,
) -> list[dict[str, Any]]:
    """Enqueue one native SenseNova production CRS. Never four Flux/Qwen tiles."""
    from ..image_prompting.sensenova import compile_sensenova_crs_prompt

    packet_dump = dump_identity_packet(identity_packet) if identity_packet is not None else None
    compiled = compile_sensenova_crs_prompt(
        name=str(profile.get("name") or "Character"),
        description=str(profile.get("description") or ""),
        visual_description=str(profile.get("visual_description") or profile.get("appearance") or ""),
        traits=profile.get("traits") if isinstance(profile.get("traits"), dict) else {},
        has_character_reference=has_character_reference,
        extra=str(profile.get("notes") or ""),
    )
    tag = f"{char_slug}_sensenova_crs" + (
        f"_c{candidate_index + 1}" if candidate_count > 1 else ""
    )
    vjob = _enqueue_txt2img(
        db,
        project_id,
        character_id=character_id,
        prompt=compiled["prompt"],
        negative_prompt=compiled["negative"],
        tag=tag,
        role="hero_identity",
        model_family_preference="sensenova",
        source_asset_id=stage1_route.get("source_asset_id"),
        seed=seed,
        force_workflow_key="sensenova.crs",
        provider_kind="local",
        sheet_layout="native_production_crs",
        prompt_metadata={
            "promptFamily": "sensenova_crs",
            "promptModel": "sensenova",
            "sheetMode": True,
            "candidateIndex": candidate_index,
            "candidateCount": candidate_count,
            "viewIndex": 0,
            "viewRole": "native_production_crs",
            "batchIndex": int(route.get("batchIndex") or (candidate_index + 1)),
            "batchOf": int(route.get("batchOf") or candidate_count),
            "compositionIntent": COMPOSITION_INTENT_CHARACTER_SHEET,
            "workflowKey": "sensenova.crs",
            "modelFamily": "sensenova",
            "referenceLocked": bool(stage1_route.get("referenceLocked")),
            "referenceAssetId": stage1_route.get("referenceAssetId"),
            "referenceFidelityMode": stage1_route.get("referenceFidelityMode"),
            "conditioningMode": stage1_route.get("conditioningMode"),
            "providerKind": "local",
            "autoSelect": bool(route.get("autoSelect")),
            "seed": seed,
            "stage": 1,
            "taskType": "CRS_NATIVE_SHEET",
            "fourViewSingleOutput": True,
            "layout": "native_production_crs",
            "identityPacket": packet_dump,
        },
    )
    return [
        {
            "jobId": vjob.id,
            "role": "hero_identity",
            "viewRole": "native_production_crs",
            "canonicalView": "native_production_crs",
            "viewIndex": 0,
            "status": vjob.status,
            "assetId": None,
            "seed": seed,
            "modelFamily": "sensenova",
            "workflowKey": "sensenova.crs",
            "referenceLocked": bool(stage1_route.get("referenceLocked")),
            "error": public_job_error(vjob.message)
            if vjob.status in ("failed", "error")
            else None,
            "stage2Enabled": False,
            "stage2Route": None,
            "stage2JobId": None,
            "stage2AssetId": None,
            "stage2Status": None,
            "fourViewSingleOutput": True,
            "layout": "native_production_crs",
        }
    ]


def _enqueue_law_view_jobs(
    db: Session,
    project_id: str,
    *,
    character_id: str,
    profile: dict[str, Any],
    references: list[dict[str, Any]],
    style_profile: dict[str, Any] | None,
    stage1_route: dict[str, Any],
    seed: int,
    char_slug: str,
    candidate_index: int,
    candidate_count: int,
    route: dict[str, Any],
    identity_packet: CharacterIdentityPacket | None = None,
) -> list[dict[str, Any]]:
    """Enqueue one camera per required view. Never one four-panel job.

    Default packet is Front / Side / Back / Head-Neck Close-Up.
    Views come from the Character Identity Packet when provided.
    """
    view_jobs: list[dict[str, Any]] = []
    provider_kind = str(stage1_route.get("providerKind") or "local")
    packet_views = list(identity_packet.requiredViews) if identity_packet is not None else None
    packet_dump = dump_identity_packet(identity_packet) if identity_packet is not None else None
    four_view_pack_tile = required_views_are_default_four(packet_views or FOUR_VIEW_REQUIRED_VIEWS)
    for vidx, (vrole, vgoal, vcomp, vneg) in enumerate(_candidate_view_specs(packet_views)):
        composition = {"candidate_index": candidate_index, **dict(vcomp or {})}
        vprompt = _compile_visual_prompt(
            profile,
            prompt_goal=vgoal,
            composition=composition,
            references=references,
            role=vrole,
            extra_negative_constraints=_negative_rules_for_view(vrole, vneg),
            style_profile=style_profile,
            reference_locked=bool(stage1_route.get("referenceLocked")),
            sheet_request={},
            model_family=str(stage1_route.get("modelFamilyPreference") or ""),
        )
        vtag = f"{char_slug}_{vrole}" + (
            f"_c{candidate_index + 1}" if candidate_count > 1 else ""
        )
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
            force_workflow_key=(
                None if provider_kind == "api" else stage1_route.get("workflowKey")
            ),
            provider_kind=provider_kind,
            hosted_model_id=stage1_route.get("hostedModelId"),
            sheet_layout="crs_view",
            prompt_metadata={
                "promptFamily": vprompt.prompt_family,
                "promptModel": vprompt.model_key,
                "promptValidationOk": vprompt.validation.get("ok"),
                "sheetMode": False,
                "candidateIndex": candidate_index,
                "candidateCount": candidate_count,
                "viewIndex": vidx,
                "viewRole": vrole,
                "canonicalView": VIEW_ROLE_CANONICAL.get(vrole) or vrole,
                "batchIndex": int(route.get("batchIndex") or (candidate_index + 1)),
                "batchOf": int(route.get("batchOf") or candidate_count),
                "compositionIntent": (
                    COMPOSITION_INTENT_CHARACTER_SHEET
                    if vrole != "hero_identity"
                    else COMPOSITION_INTENT_FULL_BODY_CASTING
                ),
                "fullBody": vrole != "closeup_front",
                "workflowKey": stage1_route["workflowKey"],
                "modelFamily": stage1_route["modelFamilyPreference"],
                "referenceLocked": bool(stage1_route.get("referenceLocked")),
                "referenceAssetId": stage1_route.get("referenceAssetId"),
                "referenceFidelityMode": stage1_route.get("referenceFidelityMode"),
                "conditioningMode": stage1_route.get("conditioningMode"),
                "providerKind": provider_kind,
                "autoSelect": bool(route.get("autoSelect")),
                "seed": seed,
                "stage": 1,
                "taskType": "CRS_SINGLE_VIEW",
                "fourViewSingleOutput": False,
                "fourViewPackTile": four_view_pack_tile,
                "requiredViews": list(packet_views or FOUR_VIEW_REQUIRED_VIEWS),
                "referenceMode": "identity_preservation",
                "identityPacket": packet_dump,
            },
        )
        view_jobs.append(
            {
                "jobId": vjob.id,
                "role": vrole,
                "viewRole": vrole,
                "canonicalView": VIEW_ROLE_CANONICAL.get(vrole) or vrole,
                "viewIndex": vidx,
                "status": vjob.status,
                "assetId": None,
                "seed": seed,
                "modelFamily": stage1_route["modelFamilyPreference"],
                "workflowKey": stage1_route["workflowKey"],
                "referenceLocked": bool(stage1_route.get("referenceLocked")),
                "error": public_job_error(vjob.message)
                if vjob.status in ("failed", "error")
                else None,
                "stage2Enabled": False,
                "stage2Route": None,
                "stage2JobId": None,
                "stage2AssetId": None,
                "stage2Status": None,
                "stage2Prompt": None,
                "stage2Negative": None,
                "stage2PromptMetadata": None,
                "fourViewSingleOutput": False,
            }
        )
    return view_jobs


def start_visual_sheet_generation(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    include_details: bool = False,
    include_performance: bool = False,
    hero_asset_id: Optional[str] = None,
    candidate_count: int = 1,
    visual_style: Optional[str] = None,
    generator_sources: Optional[dict[str, Any]] = None,
    generation_mode: Optional[str] = None,
    task_type: Optional[str] = None,
    view_type: Optional[str] = None,
    family: Optional[str] = None,
    generator_family: Optional[str] = None,
    required_views: Optional[list[str]] = None,
    layout: Optional[str] = None,
    four_view_single_output: Optional[bool] = None,
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
    if is_crs_view_generation_task(task_type) or is_crs_view_generation_task(generation_mode):
        return start_crs_view_generation(
            db,
            project_id,
            character_id,
            view_type=view_type,
            hero_asset_id=hero_asset_id,
            visual_style=visual_style,
            generator_sources=generator_sources,
            family=family,
            generator_family=generator_family,
        )
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

    candidate_count = 1
    generator_sources = _coerce_single_crs_sources(generator_sources)
    jobs: dict[str, Any] = {}
    role_assets: dict[str, str] = {}
    candidates: list[dict[str, Any]] = []

    prev_pack = _load_pack_raw(db, character_id) or {}
    if _pack_has_live_generation(db, project_id, prev_pack):
        return prev_pack
    _cancel_replaced_draft_jobs(db, project_id, prev_pack)
    approved_hero = service.resolve_approved_reference(db, character_id, "hero_identity")
    if approved_hero:
        role_assets["hero_identity"] = approved_hero

    # Provider-neutral identity packet BEFORE any Qwen/Krea routing or enqueue.
    compiled = build_conditioning_packet(
        db,
        project_id,
        character_id,
        task="CRS_GENERATION",
        include_details=include_details,
        identity_authority_asset_id=hero_asset_id or approved_hero,
        character_name=name,
    )
    if isinstance(compiled, CharacterIdentityPacket):
        identity_packet = compiled
    else:
        identity_packet = CharacterIdentityPacket(
            task="CRS_GENERATION",
            characterId=character_id,
            characterName=name,
            identityAuthorityAssetId=hero_asset_id or approved_hero,
        )
    requested = [str(v).strip() for v in (required_views or []) if str(v).strip()]
    if requested:
        identity_packet.requiredViews = requested
    elif str(layout or "").strip().lower() in {"four_view", "four_panel_2x2"}:
        identity_packet.requiredViews = list(FOUR_VIEW_REQUIRED_VIEWS)

    # Character Creator V2: retired four-view / collage default collapses to Front only.
    if not os.environ.get("ADEPT_ALLOW_FOUR_VIEW_CRS"):
        from .cc_v2 import collapse_retired_required_views

        collapsed = collapse_retired_required_views(list(identity_packet.requiredViews or []), layout)
        if collapsed == ["front_full"] and (
            str(layout or "").strip().lower() in {"four_view", "four_panel_2x2", "collage", "contact_sheet"}
            or set(identity_packet.requiredViews or []) == set(FOUR_VIEW_REQUIRED_VIEWS)
        ):
            identity_packet.requiredViews = ["front_full"]
            layout = "single_view"

    def _is_approved_revision(c: dict[str, Any]) -> bool:
        status = str(c.get("status") or "").strip().lower()
        approval = str(c.get("approvalStatus") or c.get("approval_status") or "").strip().lower()
        return status == "approved" or approval == "approved" or c.get("approved") is True

    def _pack_history(pack: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        current_hero = str(pack.get("approvedHeroIdentity") or "").strip()
        for c in list(pack.get("previousCandidates") or []) + list(pack.get("candidates") or []):
            if not isinstance(c, dict) or not _is_approved_revision(c):
                continue
            aid = str(c.get("sheetAssetId") or c.get("assetId") or "").strip()
            if not aid or aid in seen or aid == current_hero:
                continue
            seen.add(aid)
            items.append(c)
        return items

    previous_candidates = _pack_history(prev_pack)
    if approved_hero and approved_hero not in {
        str(item.get("sheetAssetId") or item.get("assetId") or "").strip()
        for item in previous_candidates
        if isinstance(item, dict)
    }:
        previous_candidates.append(
            {
                "sheetAssetId": approved_hero,
                "assetId": approved_hero,
                "status": "approved",
                "approvalStatus": "approved",
                "approved": True,
                "revision": prev_pack.get("crsRevision"),
            }
        )
    next_revision = int(prev_pack.get("nextCandidateRevision") or 1)
    parent_sheet_id = approved_hero

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
        # * Reference-capable family + attached reference → REFERENCE_CONDITIONED
        #   (pixels participate). Qwen Image 2512 CRS is PROFILE_GUIDED
        #   qwen2512.txt2img — never qwen2512.ref (ERS I2I).
        # * Txt2img-only family (Illustrious) + attached reference →
        #   PROFILE_GUIDED (profile + style prompt, no pixels). Never forced
        #   onto zimage.ref_edit.
        # * Candidate variety comes from different Certified generators / seeds
        #   / interpretation — never from changing the character's identity.
        # * Each distinct Certified generator is used once before reuse; we
        #   never fabricate distinctness.
        references = service.list_references(db, project_id, character_id)
        chosen_family = _chosen_crs_local_family(generator_sources)
        needs_2509_crop = _is_qwen_edit_2509_family(chosen_family)
        extract_sheet = needs_2509_crop
        if needs_2509_crop:
            reference_asset_id = _resolve_isolated_identity_crop(
                db,
                project_id,
                character_id,
                references,
                extract_from_sheet=extract_sheet,
            )
        else:
            # Any single uploaded figure is Character Reference (Flux / profile path).
            reference_asset_id = _resolve_readable_reference_asset_id(
                db, project_id, references
            )
        if needs_2509_crop:
            try:
                from ..workflows.qwen_image_edit_2509 import discover_qwen_edit_2509

                if not discover_qwen_edit_2509().get("runtimeReady"):
                    raise ValueError(QWEN_EDIT_2509_NOT_READY)
            except ValueError:
                raise
            except Exception:
                raise ValueError(QWEN_EDIT_2509_NOT_READY)
            if not reference_asset_id:
                raise ValueError(QWEN_EDIT_2509_NEEDS_CROP)
        routing_plan = _build_candidate_routing_plan(
            candidate_count=candidate_count,
            reference_asset_id=reference_asset_id,
            visual_style=resolved_style_key,
            generator_sources=generator_sources,
        )
        candidate_count = len(routing_plan)
        if candidate_count < 1:
            raise ValueError(
                "No image generator enabled. Enable a Local or Cloud generator to create character sheets."
            )
        reference_locked = bool(reference_asset_id)
        hero_candidate_jobs: list[dict[str, Any]] = []
        pack_generator_sources = generator_sources
        for _i, route in enumerate(routing_plan):
            stage1_route = route["stage1"]
            stage2_route = route.get("stage2")
            seed = _candidate_seed(character_id, _i)
            # Four views (front, side, back, close-up) per candidate x generator.
            # jobs["hero"] still points at the front view for legacy + e2e pack keys.
            #
            # Two-stage pipeline: Stage 1 locks identity (reference-capable or
            # txt2img). Stage 2 is an optional real img2img/edit refinement that
            # runs on the Stage 1 output after it completes.
            if _is_sensenova_family(str(stage1_route.get("modelFamilyPreference") or "")):
                view_jobs = _enqueue_sensenova_crs_job(
                    db,
                    project_id,
                    character_id=character_id,
                    profile=profile,
                    stage1_route=stage1_route,
                    seed=seed,
                    char_slug=char_slug,
                    candidate_index=_i,
                    candidate_count=candidate_count,
                    route=route,
                    identity_packet=identity_packet,
                    has_character_reference=bool(reference_asset_id),
                )
            else:
                view_jobs = _enqueue_law_view_jobs(
                    db,
                    project_id,
                    character_id=character_id,
                    profile=profile,
                    references=references,
                    style_profile=style_profile,
                    stage1_route=stage1_route,
                    seed=seed,
                    char_slug=char_slug,
                    candidate_index=_i,
                    candidate_count=candidate_count,
                    route=route,
                    identity_packet=identity_packet,
                )
            provider_kind = str(stage1_route.get("providerKind") or "local")
            is_api_sheet = provider_kind == "api"
            # jobs["hero"] points at the front view job (legacy + e2e compat).
            hero_job = view_jobs[0]
            if stage1_route.get("providerKind") == "api":
                hosted = str(stage1_route.get("hostedModelId") or stage1_route.get("selectedSource") or "")
                provider = _hosted_provider_label(hosted)
                model_name = _krea_model_display(hosted) if provider == "krea" else hosted
                stage1_lineage = {
                    "workflowKey": stage1_route.get("workflowKey"),
                    "generator": hosted,
                    "provider": provider,
                    "model": model_name,
                    "modelVariant": model_name,
                    "supportsReferences": stage1_route.get("conditioningMode")
                    == CONDITIONING_REFERENCE_CONDITIONED,
                    "providerKind": "api",
                    "provenance": _candidate_provenance_label(
                        provider_kind="api",
                        provider=provider,
                        model=model_name,
                        hosted_model_id=hosted,
                        selected_source=str(stage1_route.get("selectedSource") or hosted),
                        conditioning_mode=stage1_route.get("conditioningMode"),
                    ),
                }
            else:
                stage1_lineage = _workflow_lineage(stage1_route["workflowKey"])
                stage1_lineage["providerKind"] = "local"
            stage2_lineage = _workflow_lineage(stage2_route["workflowKey"]) if stage2_route else None
            low_fidelity = _low_reference_fidelity(
                reference_locked=bool(stage1_route.get("referenceLocked")), lineage=stage1_lineage
            )
            label = "Hero" if candidate_count == 1 else f"Candidate {_i + 1}"
            batch_index = int(route.get("batchIndex") or (_i + 1))
            batch_of = int(route.get("batchOf") or 1)
            native_crs = _is_sensenova_family(str(stage1_route.get("modelFamilyPreference") or ""))
            if native_crs:
                sheet_layout = "native_production_crs"
            elif str(layout or "").strip().lower() in {"single_view", "crs_view_generation", "v2_21x9"}:
                sheet_layout = "single_view"
            elif list(identity_packet.requiredViews or []) == ["front_full"]:
                sheet_layout = "single_view"
            else:
                sheet_layout = "four_view"
            provenance = _candidate_provenance_label(
                provider_kind=str(stage1_route.get("providerKind") or "local"),
                provider=stage1_lineage.get("provider"),
                model=stage1_lineage.get("model"),
                hosted_model_id=stage1_route.get("hostedModelId"),
                selected_source=str(
                    stage1_route.get("selectedSource")
                    or stage1_route.get("modelFamilyPreference")
                    or ""
                ),
                conditioning_mode=stage1_route.get("conditioningMode"),
            )
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
                "referenceLocked": bool(stage1_route.get("referenceLocked")),
                "conditioningMode": stage1_route.get("conditioningMode"),
                "providerKind": stage1_route.get("providerKind") or "local",
                "selectedSource": stage1_route.get("selectedSource"),
                "hostedModelId": stage1_route.get("hostedModelId"),
                "providerId": stage1_route.get("providerId") or "",
                "modelId": stage1_route.get("modelId") or stage1_route.get("hostedModelId") or stage1_route.get("selectedSource"),
                "batchIndex": batch_index,
                "batchOf": batch_of,
                "autoSelect": bool(route.get("autoSelect")),
                "provenance": provenance,
                "error": None,
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
                "layout": sheet_layout,
                "fourViewSingleOutput": native_crs,
                "requiredViews": list(identity_packet.requiredViews or FOUR_VIEW_REQUIRED_VIEWS),
                "referenceMode": "identity_preservation",
                "characterSheetIntent": {
                    "purpose": "character_sheet",
                    "layout": sheet_layout,
                    "requiredViews": list(identity_packet.requiredViews or FOUR_VIEW_REQUIRED_VIEWS),
                    "referenceMode": "identity_preservation",
                },
                "layoutNoncompliant": False,
                "layout_noncompliant": False,
                "layoutVerified": None,
                "layoutNote": None,
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
                "referenceLocked": bool(stage1_route.get("referenceLocked")),
                "conditioningMode": stage1_route.get("conditioningMode"),
                "providerKind": stage1_route.get("providerKind") or "local",
                "selectedSource": stage1_route.get("selectedSource"),
                "hostedModelId": stage1_route.get("hostedModelId"),
                "providerId": stage1_route.get("providerId") or "",
                "modelId": stage1_route.get("modelId") or stage1_route.get("hostedModelId") or stage1_route.get("selectedSource"),
                "batchIndex": batch_index,
                "batchOf": batch_of,
                "autoSelect": bool(route.get("autoSelect")),
                "provenance": provenance,
                "error": None,
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
                "layout": sheet_layout,
                "fourViewSingleOutput": native_crs,
                "requiredViews": list(identity_packet.requiredViews or FOUR_VIEW_REQUIRED_VIEWS),
                "referenceMode": "identity_preservation",
                "characterSheetIntent": {
                    "purpose": "character_sheet",
                    "layout": sheet_layout,
                    "requiredViews": list(identity_packet.requiredViews or FOUR_VIEW_REQUIRED_VIEWS),
                    "referenceMode": "identity_preservation",
                },
                "layoutNoncompliant": False,
                "layout_noncompliant": False,
                "layoutVerified": None,
                "layoutNote": None,
                "width": 2720 if native_crs else CRS_2K_COMPOSE,
                "height": 1536 if native_crs else CRS_2K_COMPOSE,
                "qualityTier": "2K",
                "resolutionOrigin": "native",
                "revision": next_revision,
                "parentSheetId": parent_sheet_id,
                "parent_sheet_id": parent_sheet_id,
                "referenceAssetId": reference_asset_id,
                "createdAt": _now(),
            })
        jobs["hero"] = hero_candidate_jobs[0]
        jobs["hero_candidates"] = hero_candidate_jobs

    pack = {
        "schema_version": 2,
        "status": "GENERATING",
        "characterId": character_id,
        "projectId": project_id,
        "engine": "multi_model",
        "workflows": ["character_sheet", "sequential_identity_prompts", "multi_model_routing"],
        "identityLock": "",
        "referenceEditReplaced": True,
        "referenceLocked": any(
            (c.get("conditioningMode") == CONDITIONING_REFERENCE_CONDITIONED) for c in candidates
        ),
        "generationMode": (
            (candidates[0].get("conditioningMode") if candidates else None)
            or generation_mode
        ),
        "jobs": jobs,
        "roleAssets": role_assets,
        "candidates": candidates,
        "candidateCount": candidate_count,
        "generatorSources": generator_sources,
        "generatorPreferences": generator_sources,
        "includeDetails": include_details,
        "includePerformance": include_performance,
        "characterName": name,
        "characterSlug": char_slug,
        "createdAt": _now(),
        "phase": "hero" if "hero" in jobs else "sheet_ready",
        "mock": False,
        "previousCandidates": previous_candidates,
        "nextCandidateRevision": next_revision + 1,
        "approvedHeroIdentity": approved_hero,
        "crsRevision": next_revision,
        "taskType": "CRS_GENERATION",
        "identityPacket": dump_identity_packet(identity_packet),
    }
    return _save_pack(db, project_id, character_id, pack)


def start_crs_view_generation(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    view_type: Optional[str] = None,
    hero_asset_id: Optional[str] = None,
    visual_style: Optional[str] = None,
    generator_sources: Optional[dict[str, Any]] = None,
    family: Optional[str] = None,
    generator_family: Optional[str] = None,
) -> dict[str, Any]:
    """Enqueue ONE canonical character view. No five-view pack. No Adept compose."""
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found")
    view_type = normalize_crs_view_type(view_type)
    profile_out = service.get_profile(db, project_id, character_id)
    profile = profile_out.model_dump()
    name = profile.get("name") or "Character"
    char_slug = (profile.get("slug") or name).replace(" ", "_").lower()
    resolved_style_key = visual_style or profile.get("visual_style") or ""
    style_profile = _resolve_style_profile(resolved_style_key)
    gates = list_gates(db, project_id, character_id)
    concept = (gates.get("gates") or {}).get("concept") or {}
    if concept.get("status") in (None, "NOT_STARTED") or not concept.get("directions"):
        propose_visual_directions(db, project_id, character_id)

    prev_pack = _load_pack_raw(db, character_id) or {}
    approved_hero = service.resolve_approved_reference(db, character_id, "hero_identity")
    next_revision = int(prev_pack.get("nextCandidateRevision") or 1)
    previous_candidates = []
    seen: set[str] = set()
    for c in list(prev_pack.get("previousCandidates") or []) + list(prev_pack.get("candidates") or []):
        if not isinstance(c, dict):
            continue
        aid = str(c.get("sheetAssetId") or c.get("assetId") or "").strip()
        if not aid or aid in seen:
            continue
        seen.add(aid)
        previous_candidates.append(c)

    references = service.list_references(db, project_id, character_id)
    identity_crop_id = valid_identity_reference_crop(
        references,
        readable=lambda aid: _asset_image_readable(db, project_id, aid),
        image_path=lambda aid: _asset_image_path(db, project_id, aid),
    )
    requested_family = extract_crs_view_requested_family(
        generator_sources,
        family=family,
        generator_family=generator_family,
    )
    resolved = resolve_crs_view_generation_workflow(
        has_identity_crop=bool(identity_crop_id),
        requested_family=requested_family or None,
    )
    family = str(resolved["family"])
    workflow_key = str(resolved["workflowKey"])
    explicit_family = bool(resolved.get("explicit") or requested_family)
    use_i2i = (
        (not explicit_family)
        and resolved.get("mode") == "img2img"
        and bool(identity_crop_id)
    )
    source_asset_id = identity_crop_id if use_i2i else None
    seed = _candidate_seed(character_id, 0)
    identity_packet = CharacterIdentityPacket(
        task=CRS_VIEW_GENERATION_TASK,
        characterId=character_id,
        characterName=name,
        identityAuthorityAssetId=hero_asset_id or approved_hero,
        requiredViews=[view_type],
        outputType="character_view",
    )
    packet_dump = dump_identity_packet(identity_packet)
    vprompt = _compile_visual_prompt(
        profile,
        prompt_goal="a production character reference, one person, front full-body",
        composition={"candidate_index": 0, "viewType": view_type, "sheetComposition": False},
        references=references,
        role=CRS_VIEW_ROLE,
        extra_negative_constraints=_negative_rules_for_view(CRS_VIEW_ROLE, None),
        style_profile=style_profile,
        reference_locked=bool(use_i2i),
        sheet_request={},
        model_family=family,
    )
    prompt_l = (vprompt.prompt or "").lower()
    for banned in ("contact sheet", "four-panel", "character sheet collage"):
        if banned in prompt_l and f"no {banned}" not in prompt_l:
            raise ValueError(f"CRS_VIEW_GENERATION prompt must not request {banned}")
    vjob = _enqueue_txt2img(
        db,
        project_id,
        character_id=character_id,
        prompt=vprompt.prompt,
        negative_prompt=vprompt.negative_prompt,
        tag=f"{char_slug}_{view_type}",
        role=CRS_VIEW_ROLE,
        model_family_preference=family,
        source_asset_id=source_asset_id,
        denoise=REFERENCE_FIDELITY_DENOISE if use_i2i else None,
        seed=seed,
        force_workflow_key=workflow_key,
        provider_kind="local",
        sheet_layout="crs_view_generation",
        prompt_metadata={
            "promptFamily": getattr(vprompt, "prompt_family", ""),
            "promptModel": getattr(vprompt, "model_key", ""),
            "sheetMode": False,
            "sheetComposition": False,
            "scene": False,
            "ers": False,
            "krea": False,
            "extras": False,
            "outputCount": 1,
            "characterCount": 1,
            "candidateIndex": 0,
            "candidateCount": 1,
            "viewIndex": 0,
            "viewRole": CRS_VIEW_ROLE,
            "viewType": view_type,
            "canonicalView": view_type,
            "compositionIntent": COMPOSITION_INTENT_FULL_BODY_CASTING,
            "fullBody": True,
            "workflowKey": workflow_key,
            "modelFamily": family,
            "referenceLocked": bool(use_i2i),
            "referenceAssetId": source_asset_id,
            "referenceKind": "IDENTITY_REFERENCE" if source_asset_id else None,
            "conditioningMode": (
                CONDITIONING_REFERENCE_CONDITIONED if use_i2i else CONDITIONING_PROFILE_GUIDED
            ),
            "providerKind": "local",
            "autoSelect": False if explicit_family else True,
            "seed": seed,
            "stage": 1,
            "taskType": CRS_VIEW_GENERATION_TASK,
            "fourViewSingleOutput": False,
            "requiredViews": [view_type],
            "referenceMode": "identity_preservation",
            "identityPacket": packet_dump,
        },
    )
    lineage = _workflow_lineage(workflow_key)
    view_job = {
        "jobId": vjob.id,
        "role": CRS_VIEW_ROLE,
        "viewRole": CRS_VIEW_ROLE,
        "viewType": view_type,
        "canonicalView": view_type,
        "viewIndex": 0,
        "status": vjob.status,
        "assetId": None,
        "seed": seed,
        "modelFamily": family,
        "workflowKey": workflow_key,
        "referenceLocked": bool(use_i2i),
        "error": None,
        "stage2Enabled": False,
        "fourViewSingleOutput": False,
        "sheetComposition": False,
    }
    entry = {
        "jobId": vjob.id,
        "role": CRS_VIEW_ROLE,
        "status": vjob.status,
        "candidateIndex": 0,
        "label": f"{name} {view_type}",
        "assetId": None,
        "generator": lineage.get("generator"),
        "provider": lineage.get("provider"),
        "model": lineage.get("model"),
        "modelVariant": lineage.get("modelVariant"),
        "workflowKey": workflow_key,
        "seed": seed,
        "referenceAssetIds": [source_asset_id] if source_asset_id else [],
        "compositionIntent": COMPOSITION_INTENT_FULL_BODY_CASTING,
        "referenceLocked": bool(use_i2i),
        "conditioningMode": view_job.get("referenceLocked") and CONDITIONING_REFERENCE_CONDITIONED or CONDITIONING_PROFILE_GUIDED,
        "providerKind": "local",
        "autoSelect": False if explicit_family else True,
        "error": None,
        "stage2Enabled": False,
        "viewJobs": [view_job],
        "sheetAssetId": None,
        "sourceAssetIds": [],
        "layout": "single_view",
        "viewType": view_type,
        "fourViewSingleOutput": False,
        "sheetComposition": False,
        "requiredViews": [view_type],
        "referenceMode": "identity_preservation",
        "characterSheetIntent": {
            "purpose": "character_view",
            "layout": "single_view",
            "requiredViews": [view_type],
            "sheetComposition": False,
        },
        "revision": next_revision,
        "parentSheetId": approved_hero,
        "parent_sheet_id": approved_hero,
        "autoApproved": False,
        "createdAt": _now(),
    }
    pack = {
        "schema_version": 2,
        "status": "GENERATING",
        "characterId": character_id,
        "projectId": project_id,
        "engine": "multi_model",
        "workflows": ["crs_view_generation"],
        "identityLock": "",
        "referenceLocked": bool(use_i2i),
        "generationMode": CRS_VIEW_GENERATION_TASK,
        "jobs": {"hero": entry, "hero_candidates": [entry]},
        "roleAssets": {"hero_identity": approved_hero} if approved_hero else {},
        "candidates": [
            {
                "assetId": None,
                "jobId": vjob.id,
                "url": None,
                "label": entry["label"],
                "status": vjob.status,
                "candidateIndex": 0,
                "workflowKey": workflow_key,
                "viewType": view_type,
                "layout": "single_view",
                "sheetComposition": False,
                "sheetAssetId": None,
                "revision": next_revision,
                "autoApproved": False,
            }
        ],
        "candidateCount": 1,
        "generatorSources": {
            "local": [
                {
                    "family": requested_family or "auto",
                    "enabled": True,
                    "batchCount": 1,
                }
            ],
            "api": None,
            "stage2Enabled": False,
        },
        "includeDetails": False,
        "includePerformance": False,
        "characterName": name,
        "characterSlug": char_slug,
        "createdAt": _now(),
        "phase": "hero",
        "mock": False,
        "previousCandidates": previous_candidates,
        "nextCandidateRevision": next_revision + 1,
        "approvedHeroIdentity": approved_hero,
        "crsRevision": next_revision,
        "taskType": CRS_VIEW_GENERATION_TASK,
        "viewType": view_type,
        "sheetComposition": False,
        "outputCount": 1,
        "characterCount": 1,
        "krea": False,
        "identityPacket": packet_dump,
        "autoApproved": False,
    }
    # Persist requested local family; Krea/API extras stay off for this task.
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
                    # Four-view compose: front tile is not the draft sheet.
                hero_meta.pop("error", None)
            elif job.status == "failed":
                hero_meta["status"] = "failed"
                hero_meta["error"] = public_job_error(job.message) or "hero generation failed"
            else:
                # running / queued / starting — clear any stale error from a
                # previous failed state so the UI does not show a dead error
                # while the job is actively generating again.
                hero_meta.pop("error", None)
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
                if aid and not item.get("viewJobs"):
                    item["assetId"] = aid
                item.pop("error", None)
            elif job.status in ("failed", "error", "cancelled"):
                item["status"] = "failed"
                if not item.get("error"):
                    item["error"] = public_job_error(job.message) or job.status
            else:
                # running / queued / starting — clear stale error from a prior
                # failed state so the UI does not show a dead error while the
                # job is actively generating again.
                item.pop("error", None)
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
                "error": public_job_error(item.get("error")) or item.get("error"),
                "layout": item.get("layout"),
                "fourViewSingleOutput": bool(item.get("fourViewSingleOutput")),
                "requiredViews": item.get("requiredViews") or list(FOUR_VIEW_REQUIRED_VIEWS),
                "referenceMode": item.get("referenceMode") or "identity_preservation",
                "layoutVerified": item.get("layoutVerified"),
                "layoutNote": item.get("layoutNote"),
                "layoutNoncompliant": candidate_layout_noncompliant(item),
                "layout_noncompliant": candidate_layout_noncompliant(item),
                "characterSheetIntent": item.get("characterSheetIntent"),
                "conditioningMode": item.get("conditioningMode"),
                "providerKind": item.get("providerKind") or "local",
                "selectedSource": item.get("selectedSource"),
                "hostedModelId": item.get("hostedModelId"),
                "providerId": item.get("providerId") or "",
                "modelId": item.get("modelId"),
                "batchIndex": item.get("batchIndex"),
                "batchOf": item.get("batchOf"),
                "autoSelect": bool(item.get("autoSelect")),
                "provenance": item.get("provenance"),
            }
            for item in hero_candidates
        ]

    # Persist law view jobs. When all views are done, Adept labeled compose
    # (G11) writes view labels + profile text panels onto a 2K sheet.
    # CRS_VIEW_GENERATION never composes a sheet from this task.
    if is_crs_view_generation_task(pack.get("taskType") or pack.get("generationMode")):
        pack["includeDetails"] = False
        pack["includePerformance"] = False
        pack["sheetComposition"] = False
        _hero_candidates = jobs.get("hero_candidates")
        candidate_entries = list(_hero_candidates) if isinstance(_hero_candidates, list) else ([jobs["hero"]] if jobs.get("hero") else [])
        for centry in candidate_entries:
            view_jobs = centry.get("viewJobs") or []
            all_done, any_failed, final_asset_ids = _poll_candidate_views(db, centry)
            if any_failed:
                centry["status"] = "failed"
                centry["autoApproved"] = False
                continue
            if not all_done:
                centry["status"] = "generating"
                continue
            aid = str(final_asset_ids[0]) if final_asset_ids else ""
            centry["assetId"] = aid or None
            centry["sheetAssetId"] = None
            centry["status"] = "done"
            centry["layout"] = "single_view"
            centry["sheetComposition"] = False
            centry["viewType"] = pack.get("viewType") or CRS_VIEW_DEFAULT_VIEW
            centry["autoApproved"] = False
            centry["fourViewSingleOutput"] = False
        pack["candidates"] = [
            {
                **(c if isinstance(c, dict) else {}),
                "sheetAssetId": None,
                "sheetComposition": False,
                "layout": "single_view",
                "viewType": pack.get("viewType") or CRS_VIEW_DEFAULT_VIEW,
                "autoApproved": False,
            }
            for c in candidate_entries
        ]
        pack["jobs"]["hero"] = candidate_entries[0] if candidate_entries else pack.get("jobs", {}).get("hero")
        pack["jobs"]["hero_candidates"] = candidate_entries
        done = all(str(c.get("status") or "") == "done" for c in candidate_entries) if candidate_entries else False
        failed = any(str(c.get("status") or "") == "failed" for c in candidate_entries)
        if failed:
            pack["status"] = "FAILED"
            pack["phase"] = "failed"
        elif done:
            pack["status"] = "READY_FOR_OWNER"
            pack["phase"] = "awaiting_owner"
        pack["autoApproved"] = False
        return _save_pack(db, project_id, character_id, pack)

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
        four_panel = bool(centry.get("fourViewSingleOutput")) and len(view_jobs) == 1
        all_done, any_failed, final_asset_ids = _poll_candidate_views(db, centry)
        if any_failed:
            failed_bits: list[str] = []
            for vj in view_jobs:
                if vj.get("status") not in ("failed", "error", "cancelled", "missing"):
                    continue
                role = vj.get("role") or vj.get("viewRole") or "view"
                msg = public_job_error(vj.get("error"))
                if not msg and vj.get("jobId"):
                    failed_job = db.get(Job, vj.get("jobId"))
                    if failed_job and failed_job.message:
                        msg = public_job_error(failed_job.message)
                        vj["error"] = msg
                failed_bits.append(f"{role}: {msg}" if msg else str(role))
            centry["status"] = "failed"
            centry["error"] = "; ".join(failed_bits) or "character sheet generation failed"
            continue
        if not all_done:
            centry["status"] = "generating"
            continue
        if four_panel:
            aid = str(final_asset_ids[0]) if final_asset_ids else ""
            if not aid:
                centry["status"] = "failed"
                centry["error"] = "four-view sheet job produced no asset"
                continue
            sheet_asset = db.get(Asset, aid)
            native = str(centry.get("layout") or "").strip().lower() in {
                "native_production_crs",
                "production_crs",
            } or _is_sensenova_family(str(centry.get("workflowKey") or centry.get("model") or ""))
            if native:
                from .sensenova_crs_gate import assess_native_production_crs

                assessment = assess_native_production_crs(sheet_asset.path if sheet_asset else None)
                centry["layout"] = "native_production_crs"
                centry["layoutVerified"] = bool(assessment.get("layoutVerified"))
                centry["layoutNoncompliant"] = bool(assessment.get("layoutNoncompliant"))
                centry["layout_noncompliant"] = bool(assessment.get("layoutNoncompliant"))
                centry["layoutNote"] = assessment.get("note")
            else:
                assessment = assess_four_view_layout(sheet_asset.path if sheet_asset else None)
                apply_layout_assessment_to_candidate(centry, assessment)
            if native:
                centry["characterSheetIntent"] = {
                    "purpose": "character_sheet",
                    "layout": "native_production_crs",
                    "referenceMode": "identity_preservation",
                }
            else:
                centry["characterSheetIntent"] = four_view_sheet_intent()
            centry["sheetAssetId"] = aid
            centry["assetId"] = aid
            centry["sourceAssetIds"] = [aid]
            centry["status"] = "done"
        else:
            validation = _validate_candidate_view_consistency(view_jobs)
            source_ids = list(validation.get("assetIds") or final_asset_ids or [])
            four_view_compose = str(centry.get("layout") or "").strip().lower() in {
                "four_view",
                "four_panel_2x2",
            } or len(source_ids) == 4
            # Isolated 5-view law enforces seed/family consistency. Default 4-view
            # tiles are independent Flux cameras (different seeds) and compose first.
            if not four_view_compose and not validation.get("ok"):
                centry["status"] = "failed"
                centry["error"] = "; ".join(validation.get("reasons") or []) or (
                    "CRS law-view consistency failed"
                )
                continue
            if not source_ids:
                centry["status"] = "failed"
                centry["error"] = "law view jobs produced no assets"
                continue
            layout_name = str(centry.get("layout") or "").strip().lower()
            if layout_name in {"single_view", "crs_view_generation", "v2_21x9"} or len(source_ids) < 2:
                # V2: identity views stay individual. Sheet is POST .../sheet/compose only.
                aid = str(source_ids[0])
                centry["status"] = "done"
                centry["assetId"] = aid
                centry["sheetAssetId"] = None
                continue
            view_paths: list[str] = []
            missing = False
            for aid in source_ids:
                asset = db.get(Asset, str(aid))
                if not asset or not asset.path:
                    missing = True
                    break
                view_paths.append(str(asset.path))
            if missing:
                centry["status"] = "failed"
                centry["error"] = "missing source view asset path"
                continue
            def _slot_path(vj: dict[str, Any]) -> str | None:
                aid = vj.get("stage2AssetId") if vj.get("stage2Status") == "done" else vj.get("assetId")
                if not aid:
                    return None
                asset = db.get(Asset, str(aid))
                return str(asset.path) if asset and asset.path else None

            # Default 4-view path composes first, then fail-closes on
            # assess_four_view_layout. Isolated 5-view law still uses tile gates.
            if four_view_compose:
                gate = {"accepted": True, "skipped": "four_view_compose"}
            else:
                gate = gate_candidate_law_views(view_jobs, resolve_path=_slot_path)
            if not gate.get("accepted"):
                centry["status"] = "failed"
                centry["error"] = gate.get("error") or "CRS law-view gate failed"
                centry["gateFailed"] = True
                centry["crsLawViewGate"] = {
                    "accepted": False,
                    "autoApproved": False,
                    "kreaInvoked": False,
                    "error": centry["error"],
                }
                continue
            try:
                out_path = _composed_sheet_output_path(
                    project_id, character_id, int(centry.get("candidateIndex") or 0)
                )
                sheet_layout: dict[str, Any] = {}
                composed_path = _compose_character_sheet_grid(
                    view_paths,
                    str(out_path),
                    profile=_sheet_profile_with_wardrobe(db, profile),
                    layout_out=sheet_layout,
                )
                lineage = _workflow_lineage(str(centry.get("workflowKey") or ""))
                sheet_asset = _ingest_composed_sheet_asset(
                    db,
                    project_id,
                    character_id=character_id,
                    candidate_index=int(centry.get("candidateIndex") or 0),
                    composed_path=composed_path,
                    source_asset_ids=source_ids,
                    lineage=lineage,
                    layout=sheet_layout or None,
                )
            except Exception as exc:  # noqa: BLE001
                centry["status"] = "failed"
                centry["error"] = f"character sheet composition failed: {exc}"
                continue
            centry["sheetAssetId"] = sheet_asset.id
            centry["assetId"] = sheet_asset.id
            centry["sourceAssetIds"] = source_ids
            centry["status"] = "done"
            centry["fourViewSingleOutput"] = False
            if len(view_paths) == 4:
                assessment = assess_four_view_layout(
                    composed_path, view_count=4, composed=True
                )
                apply_layout_assessment_to_candidate(centry, assessment)
                if assessment.get("layoutNoncompliant"):
                    centry["status"] = "failed"
                    centry["error"] = (
                        assessment.get("note")
                        or "Character Reference Sheet is not four views."
                    )
                    centry["sheetAssetId"] = None
                    continue
                centry["layout"] = "four_view"
            else:
                centry["layout"] = "law_views"
                centry["layoutNoncompliant"] = False
                centry["layout_noncompliant"] = False
            aid = sheet_asset.id
        if not primary_sheet_set:
            role_assets["hero_identity"] = aid
            # Draft only. Approve is the only persist / canon writer.
            primary_sheet_set = True
        continue

    # Mirror candidate sheet state back into pack["candidates"].
    def _mirror_candidate(item: dict[str, Any]) -> dict[str, Any]:
        # Recompute from pixels / stored dimensions; do not keep a stale true.
        _hydrate_candidate_layout(db, item)
        layout_noncompliant = candidate_layout_noncompliant(item)
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
            "conditioningMode": item.get("conditioningMode"),
            "providerKind": item.get("providerKind") or "local",
            "selectedSource": item.get("selectedSource"),
            "hostedModelId": item.get("hostedModelId"),
            "providerId": item.get("providerId") or "",
            "modelId": item.get("modelId"),
            "characterSheetIntent": item.get("characterSheetIntent"),
            "characterSheetLayout": item.get("characterSheetLayout"),
            "layoutNoncompliant": layout_noncompliant,
            "layout_noncompliant": layout_noncompliant,
            "batchIndex": item.get("batchIndex"),
            "batchOf": item.get("batchOf"),
            "autoSelect": bool(item.get("autoSelect")),
            "provenance": item.get("provenance")
            or _candidate_provenance_label(
                provider_kind=str(item.get("providerKind") or "local"),
                provider=item.get("provider"),
                model=item.get("model"),
                hosted_model_id=item.get("hostedModelId"),
                selected_source=str(item.get("selectedSource") or item.get("model") or ""),
                conditioning_mode=item.get("conditioningMode"),
            ),
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
            "error": public_job_error(item.get("error")) or item.get("error"),
            "layout": item.get("layout") or "law_views",
            "fourViewSingleOutput": bool(item.get("fourViewSingleOutput", False)),
            "requiredViews": item.get("requiredViews") or list(FOUR_VIEW_REQUIRED_VIEWS),
            "referenceMode": item.get("referenceMode") or "identity_preservation",
            "layoutVerified": item.get("layoutVerified"),
            "layoutNote": item.get("layoutNote"),
            "width": item.get("width"),
            "height": item.get("height"),
            "qualityTier": item.get("qualityTier") or "2K",
            "resolutionOrigin": item.get("resolutionOrigin") or "native",
            "revision": item.get("revision"),
            "parentSheetId": item.get("parentSheetId") or item.get("parent_sheet_id"),
            "parent_sheet_id": item.get("parent_sheet_id") or item.get("parentSheetId"),
            "referenceAssetId": item.get("referenceAssetId") or (item.get("referenceAssetIds") or [None])[0],
            "createdAt": item.get("createdAt") or item.get("created_at"),
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
        if candidate_entries and all(str(c.get("status") or "") == "failed" for c in candidate_entries):
            pack["status"] = "FAILED"
            pack["error"] = pack.get("error") or next(
                (c.get("error") for c in candidate_entries if c.get("error")),
                "all candidates failed",
            )
        else:
            pack["status"] = "GENERATING"
        return _save_pack(db, project_id, character_id, pack)

    # Coverage pack: sequential per-role txt2img with compiled identity prompts,
    # routed on the SAME Local/Cloud source the creator selected for the hero.
    # After labeled Adept 5-view compose, coverage/details/performance are
    # optional leftovers. includeDetails=false (and includePerformance=false)
    # must not enqueue them.
    phase_source = _resolve_pack_phase_source(pack)
    coverage_specs = _coverage_role_specs()
    skip_optional_phases = _skip_optional_sheet_enqueue(pack)
    law_views_pending = any(
        isinstance(c.get("viewJobs"), list)
        and bool(c.get("viewJobs"))
        and not str(c.get("sheetAssetId") or "").strip()
        for c in candidate_entries
    )
    if skip_optional_phases:
        pack["phase"] = pack.get("phase") or ("awaiting_hero" if law_views_pending else "sheet_ready")
    if (not skip_optional_phases) and "coverage" not in jobs:
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
                model_family_preference=phase_source["model_family_preference"],
                force_workflow_key=phase_source["force_workflow_key"],
                provider_kind=phase_source["provider_kind"],
                hosted_model_id=phase_source["hosted_model_id"],
                prompt_metadata={
                    "promptFamily": package.prompt_family,
                    "promptModel": package.model_key,
                    "promptValidationOk": package.validation.get("ok"),
                    "sheetMode": package.metadata.get("sheetMode"),
                    "workflowKey": phase_source["force_workflow_key"],
                    "providerKind": phase_source["provider_kind"],
                    "hostedModelId": phase_source["hosted_model_id"],
                    "selectedSource": phase_source["selected_source"],
                },
            )
            cov_jobs.append({"jobId": j.id, "role": role, "status": j.status})
        jobs["coverage"] = cov_jobs
        pack["phase"] = "turnaround_facial"
        pack["workflows"] = list(
            dict.fromkeys([*(pack.get("workflows") or []), phase_source["force_workflow_key"], "coverage_pack"])
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
                if skip_optional_phases:
                    continue
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
                            model_family_preference=phase_source["model_family_preference"],
                            force_workflow_key=phase_source["force_workflow_key"],
                            provider_kind=phase_source["provider_kind"],
                            hosted_model_id=phase_source["hosted_model_id"],
                            prompt_metadata={
                                "promptFamily": package.prompt_family,
                                "promptModel": package.model_key,
                                "promptValidationOk": package.validation.get("ok"),
                                "sheetMode": package.metadata.get("sheetMode"),
                                "workflowKey": phase_source["force_workflow_key"],
                                "providerKind": phase_source["provider_kind"],
                                "hostedModelId": phase_source["hosted_model_id"],
                                "selectedSource": phase_source["selected_source"],
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

    if skip_optional_phases:
        # Flags-off must not enqueue coverage, but the new law-view compose
        # still has to finish before the pack is sheet_done / READY_FOR_OWNER.
        sheet_done = (not law_views_pending) or _labeled_adept_compose_done(
            pack, candidate_entries=candidate_entries
        )
    else:
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
                model_family_preference=phase_source["model_family_preference"],
                force_workflow_key=phase_source["force_workflow_key"],
                provider_kind=phase_source["provider_kind"],
                hosted_model_id=phase_source["hosted_model_id"],
                prompt_metadata={
                    "promptFamily": package.prompt_family,
                    "promptModel": package.model_key,
                    "promptValidationOk": package.validation.get("ok"),
                    "sheetMode": package.metadata.get("sheetMode"),
                    "workflowKey": phase_source["force_workflow_key"],
                    "providerKind": phase_source["provider_kind"],
                    "hostedModelId": phase_source["hosted_model_id"],
                    "selectedSource": phase_source["selected_source"],
                },
            )
            detail_jobs.append({"jobId": j.id, "role": role, "status": j.status})
        jobs["details"] = detail_jobs
        pack["phase"] = "details"
        pack["workflows"] = list(
            dict.fromkeys([*(pack.get("workflows") or []), phase_source["force_workflow_key"], "detail_pack"])
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
                model_family_preference=phase_source["model_family_preference"],
                force_workflow_key=phase_source["force_workflow_key"],
                provider_kind=phase_source["provider_kind"],
                hosted_model_id=phase_source["hosted_model_id"],
                prompt_metadata={
                    "promptFamily": package.prompt_family,
                    "promptModel": package.model_key,
                    "promptValidationOk": package.validation.get("ok"),
                    "sheetMode": package.metadata.get("sheetMode"),
                    "workflowKey": phase_source["force_workflow_key"],
                    "providerKind": phase_source["provider_kind"],
                    "hostedModelId": phase_source["hosted_model_id"],
                    "selectedSource": phase_source["selected_source"],
                },
            )
            perf_jobs.append({"jobId": j.id, "role": role, "status": j.status})
        jobs["performance"] = perf_jobs
        pack["phase"] = "performance"
        pack["workflows"] = list(
            dict.fromkeys([*(pack.get("workflows") or []), phase_source["force_workflow_key"], "performance_pack"])
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
    """Owner-only: approve image gates that have real assetIds from the pack.

    CDX-002: the concept gate is NEVER auto-approved here. The owner must
    select a proposed direction explicitly first (owner_select_concept / the
    select-visual-concept API); otherwise this raises and the pack cannot
    reach an owner-approved state with a defaulted concept.
    CDX-003: the hero gate reads the canonical approved reference row
    (service-level) instead of stale pack roleAssets that may still point at
    the first-completed candidate.
    CDX-008: the pack is only OWNER_APPROVED when every gate group has an
    asset; otherwise OWNER_APPROVED_WITH_PENDING lists the asset-less gates.
    """
    if not approved_by:
        raise ValueError("approved_by required — Character Creator cannot self-approve")
    pack = get_visual_sheet_pack(db, project_id, character_id)
    role_assets = dict(pack.get("roleAssets") or {})
    if not role_assets:
        raise ValueError("No generated role assets to approve")

    gates = list_gates(db, project_id, character_id)
    concept = (gates.get("gates") or {}).get("concept") or {}
    if concept.get("status") != "OWNER_APPROVED":
        # CDX-002: never auto-approve the concept gate with a default direction.
        raise ValueError(
            "Concept gate requires explicit owner direction selection "  # noqa: E501
            "(selectVisualConcept / owner_select_concept) before owner-approving the visual sheet."
        )

    # CDX-003: the canonical approved reference is authoritative for the hero
    # gate; pack roleAssets may still point at the first-completed candidate.
    canonical_hero = service.resolve_approved_reference(db, character_id, "hero_identity")
    if canonical_hero:
        role_assets["hero_identity"] = canonical_hero

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

    pending_gates = [
        gate for gate, roles in GATE_ROLE_GROUPS.items() if not any(r in role_assets for r in roles)
    ]
    if pending_gates:
        # CDX-008: never report OWNER_APPROVED while any gate group has no asset.
        pack["status"] = "OWNER_APPROVED_WITH_PENDING"
        pack["pendingGates"] = pending_gates
    else:
        pack["status"] = "OWNER_APPROVED"
        pack.pop("pendingGates", None)
    pack["ownerApprovedBy"] = approved_by
    pack["ownerApprovedAt"] = _now()
    _save_pack(db, project_id, character_id, pack)
    # Approve / persist_crs is owner-facing Character Creator Approve only.
    return {
        "ok": True,
        "characterId": character_id,
        "approvedGates": list(approved.keys()),
        "roleAssets": role_assets,
        "status": pack["status"],
        "pendingGates": pack.get("pendingGates") or [],
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



def retry_visual_sheet_candidate(
    db: Session,
    project_id: str,
    character_id: str,
    candidate_index: int,
) -> dict[str, Any]:
    """Re-enqueue failed views for one candidate. Other candidates are left alone."""
    pack = get_visual_sheet_pack(db, project_id, character_id)
    jobs = dict(pack.get("jobs") or {})
    entries: list[dict[str, Any]] = []
    if isinstance(jobs.get("hero_candidates"), list):
        entries = list(jobs["hero_candidates"])
    elif jobs.get("hero"):
        entries = [jobs["hero"]]
    centry = next(
        (e for e in entries if int(e.get("candidateIndex") or 0) == int(candidate_index)),
        None,
    )
    if not centry:
        raise ValueError(f"Candidate {candidate_index} not found")
    profile = service.get_profile(db, project_id, character_id).model_dump()
    style_profile = _resolve_style_profile(profile.get("visual_style") or "")
    references = service.list_references(db, project_id, character_id)
    seed = int(centry.get("seed") or _candidate_seed(character_id, candidate_index))
    family = str(
        centry.get("selectedSource")
        or centry.get("modelFamily")
        or (str(centry.get("workflowKey") or "zimage").split(".")[0])
    )
    provider_kind = str(centry.get("providerKind") or "local")
    hosted = centry.get("hostedModelId")
    source_id = None
    denoise = None
    force_key = centry.get("workflowKey") if provider_kind != "api" else None
    if centry.get("conditioningMode") == CONDITIONING_REFERENCE_CONDITIONED:
        refs = list(centry.get("referenceAssetIds") or [])
        source_id = str(refs[0]) if refs else None
        if family == "zimage":
            denoise = REFERENCE_FIDELITY_DENOISE
    char_slug = pack.get("characterSlug") or "character"
    candidate_count = int(pack.get("candidateCount") or 1)
    view_jobs = list(centry.get("viewJobs") or [])
    pack_packet = pack.get("identityPacket") if isinstance(pack.get("identityPacket"), dict) else None
    packet_views = list((pack_packet or {}).get("requiredViews") or [])
    specs = {item[0]: item for item in _candidate_view_specs(packet_views or None)}
    for vj in view_jobs:
        terminal_fail = vj.get("status") in ("failed", "error", "cancelled", "missing")
        if not terminal_fail and vj.get("assetId"):
            continue
        vrole = str(vj.get("role") or "hero_identity")
        spec = specs.get(vrole)
        if spec:
            _role, vgoal, vcomp, vneg = spec
        else:
            vgoal = "a production character reference"
            vcomp = {}
            vneg = None
        vprompt = _compile_visual_prompt(
            profile,
            prompt_goal=vgoal,
            composition={"candidate_index": int(candidate_index), **dict(vcomp or {})},
            references=references,
            role=vrole,
            extra_negative_constraints=_negative_rules_for_view(vrole, vneg),
            style_profile=style_profile,
            reference_locked=bool(centry.get("referenceLocked")),
            sheet_request={},
            model_family=family,
        )
        vtag = f"{char_slug}_{vrole}_retry" + (
            f"_c{int(candidate_index) + 1}" if candidate_count > 1 else ""
        )
        vjob = _enqueue_txt2img(
            db,
            project_id,
            character_id=character_id,
            prompt=vprompt.prompt,
            negative_prompt=vprompt.negative_prompt,
            tag=vtag,
            role=vrole,
            model_family_preference=family,
            source_asset_id=source_id,
            denoise=denoise,
            seed=seed,
            force_workflow_key=force_key,
            provider_kind=provider_kind,
            hosted_model_id=hosted,
            sheet_layout="crs_view",
            prompt_metadata={
                "candidateIndex": int(candidate_index),
                "viewRole": vrole,
                "canonicalView": VIEW_ROLE_CANONICAL.get(vrole) or vrole,
                "batchIndex": int(centry.get("batchIndex") or 1),
                "batchOf": int(centry.get("batchOf") or 1),
                "workflowKey": force_key or vj.get("workflowKey"),
                "modelFamily": family,
                "referenceLocked": bool(centry.get("referenceLocked")),
                "conditioningMode": centry.get("conditioningMode"),
                "providerKind": provider_kind,
                "providerId": centry.get("providerId") or "",
                "modelId": centry.get("modelId") or hosted or family,
                "taskType": "CRS_SINGLE_VIEW",
                "fourViewSingleOutput": False,
                "fourViewPackTile": required_views_are_default_four(
                    packet_views or FOUR_VIEW_REQUIRED_VIEWS
                ),
                "requiredViews": list(packet_views or FOUR_VIEW_REQUIRED_VIEWS),
                "referenceMode": "identity_preservation",
                "identityPacket": pack_packet,
                "retry": True,
            },
        )
        vj["jobId"] = vjob.id
        vj["role"] = vrole
        vj["viewRole"] = vrole
        vj["status"] = vjob.status
        vj["assetId"] = None
        vj["error"] = None
        vj["fourViewSingleOutput"] = False
        continue
    centry["viewJobs"] = view_jobs
    centry["status"] = "queued"
    centry["error"] = None
    centry["sheetAssetId"] = None
    centry["assetId"] = None
    if isinstance(jobs.get("hero_candidates"), list):
        jobs["hero_candidates"] = entries
        if entries and int(entries[0].get("candidateIndex") or 0) == int(candidate_index):
            jobs["hero"] = centry
    elif jobs.get("hero"):
        jobs["hero"] = centry
    pack["jobs"] = jobs
    pack["status"] = "GENERATING"
    pack["error"] = None
    pack["phase"] = "hero"
    return _save_pack(db, project_id, character_id, pack)


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
    except Exception as exc:
        logger.warning("_enqueue_character_sheet queue enqueue failed for job %s: %s", job.id, exc)
        job.status = "failed"
        job.message = f"Queue enqueue failed: {exc}"
        db.commit()
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
    provider_kind: str = "local",
    hosted_model_id: str | None = None,
    sheet_layout: str | None = None,
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
        "model": model_family_preference,
        "modelFamilyPreference": model_family_preference,
        "lockModelFamily": True,
        "allowDraft": _is_qwen_edit_2509_family(model_family_preference)
        or _is_sensenova_family(model_family_preference),
        "allow_draft": _is_qwen_edit_2509_family(model_family_preference)
        or _is_sensenova_family(model_family_preference),
        "purpose": "character_sheet",
        "presetId": "builtin-character-sheet",
        "creativeContext": creative_context,
        "role": role,
        "viewRole": role,
    }
    if sheet_layout == "four_view":
        attach_four_view_sheet_intent(body)
        body["prompt"] = strengthen_four_view_prompt(prompt)
        body["role"] = role
        body["viewRole"] = "four_view_sheet"
        crs_w, crs_h = crs_2k_pixels()
        body["width"] = crs_w
        body["height"] = crs_h
        body["quality"] = "2K"
        body["resolutionOrigin"] = "native"
        creative_context.update(body.get("characterSheetIntent") or {})
        creative_context["layout"] = "four_view"
        creative_context["fourViewSingleOutput"] = True
        creative_context["viewRole"] = "four_view_sheet"
        creative_context["qualityTier"] = "2K"
        creative_context["resolutionOrigin"] = "native"
        body["creativeContext"] = creative_context
    elif sheet_layout in {"crs_view", "crs_view_generation"}:
        vw, vh = crs_2k_view_pixels()
        body["width"] = vw
        body["height"] = vh
        body["quality"] = "2K"
        body["resolutionOrigin"] = "native"
        task_name = (
            CRS_VIEW_GENERATION_TASK
            if sheet_layout == "crs_view_generation"
            else "CRS_SINGLE_VIEW"
        )
        body["taskType"] = task_name
        body["fourViewSingleOutput"] = False
        body["useExpandedPrompt"] = False
        body["sheetComposition"] = False
        body["outputCount"] = 1
        body["characterCount"] = 1
        body["viewRole"] = role
        identity_packet = (prompt_metadata or {}).get("identityPacket")
        if isinstance(identity_packet, dict):
            body["identityPacket"] = identity_packet
            creative_context["identityPacket"] = identity_packet
            body.pop("sceneCanvas", None)
            body.pop("environmentEditSource", None)
            creative_context.pop("sceneCanvas", None)
            creative_context.pop("environmentEditSource", None)
        creative_context["taskType"] = task_name
        creative_context["viewRole"] = role
        creative_context["sheetComposition"] = False
        creative_context["outputCount"] = 1
        creative_context["characterCount"] = 1
        creative_context["qualityTier"] = "2K"
        creative_context["resolutionOrigin"] = "native"
        creative_context["fourViewSingleOutput"] = False
        body["creativeContext"] = creative_context
    elif sheet_layout == "native_production_crs":
        body["width"] = 2720
        body["height"] = 1536
        body["quality"] = "2K"
        body["resolutionOrigin"] = "native"
        body["taskType"] = "CRS_NATIVE_SHEET"
        body["fourViewSingleOutput"] = True
        body["useExpandedPrompt"] = False
        body["sheetComposition"] = True
        body["outputCount"] = 1
        body["characterCount"] = 1
        body["layout"] = "native_production_crs"
        creative_context["taskType"] = "CRS_NATIVE_SHEET"
        creative_context["layout"] = "native_production_crs"
        creative_context["fourViewSingleOutput"] = True
        creative_context["qualityTier"] = "2K"
        creative_context["resolutionOrigin"] = "native"
        body["creativeContext"] = creative_context
    # Reference-locked candidates route to a reference-capable edit workflow
    # (zimage.ref_edit) by supplying the reference asset as the source image so
    # its PIXELS participate in conditioning — not merely a filename in the prompt.
    # Stage 2 refinement also uses source_asset_id, pointing at the Stage 1 output.
    if source_asset_id:
        body["source_asset_id"] = source_asset_id
        if sheet_layout in {"crs_view", "crs_view_generation"}:
            body["referenceKind"] = "IDENTITY_REFERENCE"
            body["references"] = [
                {"assetId": source_asset_id, "role": "IDENTITY_REFERENCE"}
            ]
            creative_context["referenceKind"] = "IDENTITY_REFERENCE"
    if denoise is not None:
        body["denoise"] = denoise
    if seed is not None:
        body["seed"] = seed
    if provider_kind == "api":
        hosted = hosted_model_id or model_family_preference
        body["source"] = "api"
        body["model"] = hosted
        body["lockModelFamily"] = True
        body["providerPreference"] = "cloud"
        body["hostedModelId"] = hosted
        body.pop("forceWorkflowKey", None)
        body.pop("allow_force_workflow_key", None)
        if not source_asset_id:
            body.pop("source_asset_id", None)
        job = enqueue_imagegen_job(db, project_id, body)
        _pin_crs_generation_job_params(db, job)
        return job

    if force_workflow_key:
        body["forceWorkflowKey"] = force_workflow_key
        body["allow_force_workflow_key"] = True
    job = enqueue_imagegen_job(db, project_id, body)
    _pin_crs_generation_job_params(db, job)
    return job


def apply_crs_single_figure_gate_to_job(db: Session, job: Job, params: dict[str, Any], image_path: str) -> None:
    """Hard-reject a CRS tile that is not one figure. May enqueue one Qwen fallback.

    Default 4-view pack tiles skip this gate: DINO false-positives were failing
    real single-person Flux cameras, and AUTO Flux then silently enqueued an
    untracked Qwen job. Isolated 5-view law still fail-closes here.
    """
    from .crs_single_figure import (
        is_crs_single_view_job,
        is_default_four_view_pack_tile,
        should_fallback_to_qwen,
        validate_crs_single_figure,
    )

    if not is_crs_single_view_job(params):
        return
    if is_default_four_view_pack_tile(params):
        params["crsSingleFigure"] = {
            "single_figure_pass": None,
            "detected_figures": None,
            "failure_code": None,
            "view_angle_pass": None,
            "note": "skipped: four_view_pack_tile",
            "skipped": "four_view_pack_tile",
        }
        job.params_json = json.dumps(params)
        db.commit()
        return
    result = validate_crs_single_figure(image_path)
    params["crsSingleFigure"] = result.to_dict()
    job.params_json = json.dumps(params)
    db.commit()
    if result.single_figure_pass is False:
        if should_fallback_to_qwen(params, result):
            enqueue_crs_qwen_fallback_for_job(db, job)
        raise RuntimeError(result.failure_code or "CRS_SINGLE_VIEW_MULTI_FIGURE")


def enqueue_crs_qwen_fallback_for_job(db: Session, job: Job) -> Job | None:
    """One Qwen CRS_SINGLE_VIEW retry after a failed AUTO FLUX one-figure gate."""
    params = _loads(job.params_json, {})
    if not isinstance(params, dict):
        return None
    ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
    character_id = str(ctx.get("characterId") or params.get("characterId") or "").strip()
    role = str(params.get("viewRole") or params.get("role") or ctx.get("viewRole") or "hero_identity")
    if not character_id:
        return None
    profile_out = service.get_profile(db, job.project_id, character_id)
    profile = profile_out.model_dump()
    name = profile.get("name") or "Character"
    char_slug = (profile.get("slug") or name).replace(" ", "_").lower()
    style_profile = _resolve_style_profile(str(profile.get("visual_style") or ""))
    references = service.list_references(db, job.project_id, character_id)
    vprompt = _compile_visual_prompt(
        profile,
        prompt_goal="a production character reference",
        composition={},
        references=references,
        role=role,
        extra_negative_constraints=_negative_rules_for_view(role, None),
        style_profile=style_profile,
        sheet_request={},
        model_family=CRS_AUTO_FALLBACK_FAMILY,
    )
    return _enqueue_txt2img(
        db,
        job.project_id,
        character_id=character_id,
        prompt=vprompt.prompt,
        negative_prompt=vprompt.negative_prompt,
        tag=f"{char_slug}_{role}_qwen_fallback",
        role=role,
        model_family_preference=CRS_AUTO_FALLBACK_FAMILY,
        force_workflow_key="qwen2512.txt2img",
        provider_kind="local",
        sheet_layout="crs_view",
        prompt_metadata={
            "promptFamily": getattr(vprompt, "prompt_family", ""),
            "promptModel": getattr(vprompt, "model_key", ""),
            "viewRole": role,
            "canonicalView": VIEW_ROLE_CANONICAL.get(role) or role,
            "workflowKey": "qwen2512.txt2img",
            "modelFamily": CRS_AUTO_FALLBACK_FAMILY,
            "taskType": "CRS_SINGLE_VIEW",
            "fourViewSingleOutput": False,
            "autoSelect": False,
            "crsSingleFigureFallback": True,
            "fallbackFromJobId": job.id,
        },
    )


def _pin_crs_generation_job_params(db: Session, job: Job) -> None:
    """Stop post-enqueue four-view pollution on CRS singles."""
    if not hasattr(job, "params_json"):
        return
    params = _loads(job.params_json, {})
    if not isinstance(params, dict):
        return
    ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
    task = str(params.get("taskType") or ctx.get("taskType") or "").strip().upper()
    layout = str(params.get("layout") or ctx.get("layout") or "").strip().lower()
    if layout in {"native_production_crs", "production_crs"} or task == "CRS_NATIVE_SHEET":
        return
    if task not in {"CRS_GENERATION", "CRS_SINGLE_VIEW", CRS_VIEW_GENERATION_TASK}:
        return
    changed = False
    if params.get("useExpandedPrompt") is not False:
        params["useExpandedPrompt"] = False
        changed = True
    if params.get("fourViewSingleOutput") is not False:
        params["fourViewSingleOutput"] = False
        changed = True
    if ctx.get("fourViewSingleOutput") is not False:
        ctx = dict(ctx)
        ctx["fourViewSingleOutput"] = False
        params["creativeContext"] = ctx
        changed = True
    if str(params.get("layout") or "") == "four_view":
        params["layout"] = "crs_view"
        changed = True
    intent = params.get("characterSheetIntent")
    if isinstance(intent, dict) and str(intent.get("layout") or "") == "four_view":
        intent = dict(intent)
        intent["layout"] = "law_views"
        params["characterSheetIntent"] = intent
        changed = True
    if not changed:
        return
    job.params_json = json.dumps(params)
    db.add(job)
    db.commit()
    db.refresh(job)


def _coverage_role_specs() -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (
            "full_body_front",
            "a production full-body front reference",
            {
                "shot_type": "single-camera front reference",
                "framing": "full body",
                "camera_angle": "eye level",
                "orientation": "front view",
                "environment": "plain gray background",
                "lighting": "soft studio light",
                "pose": "standing facing camera in a neutral stance",
                "focus": "wardrobe silhouette and body proportions",
            },
        ),
        (
            "full_body_side_left",
            "a production full-body side reference",
            {
                "shot_type": "single-camera side reference",
                "framing": "full body",
                "camera_angle": "eye level",
                "orientation": "left side profile",
                "environment": "plain gray background",
                "lighting": "soft studio light",
                "pose": "standing in a neutral side-profile stance",
                "focus": "profile silhouette and hair construction",
            },
        ),
        (
            "full_body_back",
            "a production full-body back reference",
            {
                "shot_type": "single-camera back reference",
                "framing": "full body",
                "camera_angle": "eye level",
                "orientation": "back view",
                "environment": "plain gray background",
                "lighting": "soft studio light",
                "pose": "standing facing away in a neutral stance",
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


def _candidate_key(item: dict[str, Any]) -> str:
    for key in ("id", "candidateId", "jobId", "job_id", "sheetAssetId", "assetId", "asset_id"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _candidate_asset_ids(item: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for key in ("sheetAssetId", "sheet_asset_id", "assetId", "asset_id"):
        value = str(item.get(key) or "").strip()
        if value and value not in ids:
            ids.append(value)
    for view in item.get("viewJobs") or []:
        if not isinstance(view, dict):
            continue
        for key in ("assetId", "asset_id", "sheetAssetId"):
            value = str(view.get(key) or "").strip()
            if value and value not in ids:
                ids.append(value)
    return ids


def _protected_crs_asset_ids(
    db: Session,
    project_id: str,
    character_id: str,
    pack: dict[str, Any],
) -> set[str]:
    """Assets reject must never delete: canon, persist_crs, parent sheets, uploads, shared refs."""
    protected: set[str] = set()
    for key in ("approvedHeroIdentity", "approved_hero_identity"):
        value = str(pack.get(key) or "").strip()
        if value:
            protected.add(value)
    # Pack roleAssets.hero_identity may point at the current DRAFT sheet.
    # Protect only persist / approved pointers — never the unapproved draft.
    try:
        approved = service.resolve_approved_reference(db, character_id, "hero_identity")
        if approved:
            protected.add(str(approved))
    except Exception:
        pass
    try:
        from .crs_service import get_crs_summary

        summary = get_crs_summary(db, project_id, character_id)
        if summary is not None:
            for attr in ("approved_reference_asset_id", "approvedReferenceAssetId", "sheet_asset_id"):
                value = str(getattr(summary, attr, "") or "").strip()
                if value:
                    protected.add(value)
            dumped = summary.model_dump() if hasattr(summary, "model_dump") else {}
            for key in ("approved_reference_asset_id", "approvedReferenceAssetId", "sheetAssetId"):
                value = str(dumped.get(key) or "").strip()
                if value:
                    protected.add(value)
    except Exception:
        pass
    from .models import CharacterReferenceAssetRow

    rows = (
        db.query(CharacterReferenceAssetRow)
        .filter(CharacterReferenceAssetRow.character_profile_id == character_id)
        .all()
    )
    for row in rows:
        source = str(getattr(row, "source_type", "") or "").strip().lower()
        if row.canonical or row.approval_status == "approved" or source in {"upload", "library", "user"}:
            if row.asset_id:
                protected.add(str(row.asset_id))
    for item in list(pack.get("candidates") or []) + list(pack.get("previousCandidates") or []):
        if not isinstance(item, dict):
            continue
        parent = str(item.get("parentSheetId") or item.get("parent_sheet_id") or "").strip()
        if parent:
            protected.add(parent)
    return {aid for aid in protected if aid}


def reject_visual_sheet_candidate(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    asset_id: str = "",
    candidate_id: str = "",
) -> dict[str, Any]:
    """Delete one draft candidate and candidate-owned pixels only.

    Never mutates persist_crs / crs_revision / canonical hero_identity.
    If asset delete fails, the candidate stays visible.
    """
    wanted = {str(asset_id or "").strip(), str(candidate_id or "").strip()} - {""}
    if not wanted:
        raise ValueError("assetId or candidateId is required")

    pack = _load_pack_raw(db, character_id)
    if not pack:
        return {
            "ok": True,
            "alreadyGone": True,
            "characterId": character_id,
            "rejectedAssetIds": [],
            "dismissedExecutionIds": [],
            "terminalizedJobIds": [],
            "pack": None,
            "crsRevision": None,
            "approvedHeroIdentity": None,
        }

    buckets = {
        "candidates": list(pack.get("candidates") or []),
        "previousCandidates": list(pack.get("previousCandidates") or []),
    }
    matches: list[dict[str, Any]] = []
    for items in buckets.values():
        for item in items:
            if not isinstance(item, dict):
                continue
            keys = {_candidate_key(item), *(_candidate_asset_ids(item))}
            if keys & wanted:
                matches.append(item)
    if not matches:
        return {
            "ok": True,
            "alreadyGone": True,
            "characterId": character_id,
            "rejectedAssetIds": [],
            "dismissedExecutionIds": [],
            "terminalizedJobIds": [],
            "pack": pack,
            "crsRevision": pack.get("crsRevision"),
            "approvedHeroIdentity": pack.get("approvedHeroIdentity"),
        }

    found = matches[0]
    protected = _protected_crs_asset_ids(db, project_id, character_id, pack)
    owned: list[str] = []
    seen_owned: set[str] = set()
    for item in matches:
        for aid in _candidate_asset_ids(item):
            if aid not in seen_owned:
                seen_owned.add(aid)
                owned.append(aid)
    if any(aid in protected for aid in owned):
        raise ValueError("Cannot reject an approved or canonical Character Reference Sheet.")

    from .models import CharacterReferenceAssetRow

    deletable: list[Asset] = []
    for aid in owned:
        asset = db.get(Asset, aid)
        if asset is None:
            continue
        if str(asset.project_id) != str(project_id):
            raise ValueError("Candidate asset is not owned by this project.")
        if str(getattr(asset, "scope", "") or "").lower() in {"shared", "global"}:
            raise ValueError("Cannot reject a shared or library reference.")
        labels_raw = getattr(asset, "labels_json", "") or "[]"
        try:
            labels = json.loads(labels_raw) if isinstance(labels_raw, str) else list(labels_raw or [])
        except Exception:
            labels = []
        label_blob = " ".join(str(x) for x in labels).lower()
        tag = str(getattr(asset, "tag", "") or "").lower()
        filename = str(getattr(asset, "filename", "") or "").lower()
        candidate_owned = (
            "candidate_" in label_blob
            or "character_sheet" in label_blob
            or tag in {"character_sheet", "composed", "imagegen", "imagegen_edit"}
            or "character_sheet" in filename
            or "candidate_" in filename
            or "imagegen" in filename
        )
        # Pack-listed draft candidates are owned even when Image Product tags
        # them as imagegen rather than character_sheet / candidate_*.
        if not candidate_owned and aid in owned:
            candidate_owned = True
        if not candidate_owned:
            raise ValueError("Refusing to delete an asset that is not candidate-owned.")
        deletable.append(asset)

    # Also drop non-canonical draft reference rows for these assets only.
    ref_rows = (
        db.query(CharacterReferenceAssetRow)
        .filter(
            CharacterReferenceAssetRow.character_profile_id == character_id,
            CharacterReferenceAssetRow.asset_id.in_(owned or ["__none__"]),
        )
        .all()
    )
    for row in ref_rows:
        if row.canonical or row.approval_status == "approved":
            raise ValueError("Cannot reject an approved or canonical Character Reference Sheet.")

    try:
        for row in ref_rows:
            db.delete(row)
        for asset in deletable:
            path = Path(str(asset.path or ""))
            db.delete(asset)
            if path.is_file() and (
                "character_sheet" in path.name.lower()
                or "candidate_" in path.name.lower()
                or "imagegen" in path.name.lower()
            ):
                path.unlink()
        drop = set(owned) | wanted

        def _keep(item: Any) -> bool:
            if not isinstance(item, dict):
                return True
            keys = {_candidate_key(item), *(_candidate_asset_ids(item))}
            return not (keys & drop)

        pack["candidates"] = [item for item in buckets["candidates"] if _keep(item)]
        pack["previousCandidates"] = [item for item in buckets["previousCandidates"] if _keep(item)]
        role_assets = pack.get("roleAssets") if isinstance(pack.get("roleAssets"), dict) else {}
        hero_ptr = str(role_assets.get("hero_identity") or "").strip()
        if hero_ptr in drop:
            role_assets = dict(role_assets)
            role_assets.pop("hero_identity", None)
            pack["roleAssets"] = role_assets
            if not pack.get("approvedHeroIdentity"):
                pack["phase"] = "awaiting_hero"
                if not pack.get("candidates"):
                    pack["status"] = "NOT_STARTED"
        # Never call persist_crs. Never bump crs_revision / approvedHeroIdentity.
        _save_pack(db, project_id, character_id, pack)
        db.commit()
    except Exception:
        db.rollback()
        raise

    dismissed_executions: list[str] = []
    terminalized_jobs: list[str] = []
    try:
        from ..codirector.execution.cancel import dismiss_executions_for_assets

        dismissed_executions = dismiss_executions_for_assets(db, project_id, owned)
        job_ids = {str(found.get("jobId") or found.get("job_id") or "").strip()} - {""}
        for view in found.get("viewJobs") or []:
            if isinstance(view, dict):
                jid = str(view.get("jobId") or view.get("job_id") or "").strip()
                if jid:
                    job_ids.add(jid)
        for job in db.query(Job).filter(Job.project_id == project_id).all():
            blob = " ".join(
                [
                    str(job.id or ""),
                    str(job.params_json or ""),
                    str(job.message or ""),
                    str(job.output_path or ""),
                ]
            )
            if job.id not in job_ids and not any(aid in blob for aid in owned):
                continue
            status = str(job.status or "").lower()
            if status not in {"done", "failed", "cancelled", "error", "rejected"}:
                job.status = "cancelled"
            job.message = f"{job.message or ''} REJECTED".strip()
            terminalized_jobs.append(str(job.id))
            # Marking the job cancelled in the DB does not stop the in-flight
            # Comfy prompt (a blocked native call never checks the cooperative
            # cancel flag). POST /interrupt when this job owns the active
            # prompt so reject-during-gen actually cancels the runtime job.
            try:
                from ..queue_worker import schedule_comfy_interrupt_if_owner

                schedule_comfy_interrupt_if_owner(str(job.id))
            except Exception:  # noqa: BLE001
                logger.exception("Could not schedule Comfy /interrupt for rejected job %s", job.id)
        if dismissed_executions or terminalized_jobs:
            db.commit()
    except Exception:
        logger.exception("Reject did not dismiss leftover Co-Director executions for %s", character_id)

    return {
        "ok": True,
        "characterId": character_id,
        "rejectedAssetIds": owned,
        "dismissedExecutionIds": dismissed_executions,
        "terminalizedJobIds": terminalized_jobs,
        "pack": _load_pack_raw(db, character_id),
        "crsRevision": pack.get("crsRevision"),
        "approvedHeroIdentity": pack.get("approvedHeroIdentity"),
    }
