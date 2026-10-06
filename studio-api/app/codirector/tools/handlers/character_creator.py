"""Co-Director Character Creator specialist tools (M3.3 Phase 2)."""

from __future__ import annotations

import json
from typing import Any

from ....character_identity import service as ci
from ....character_identity.roles import ADDITIONAL_ROLES, REQUIRED_COVERAGE_ROLES, ROLE_GUIDANCE
from ....character_identity.schemas import CharacterProfileCreate, CharacterProfileUpdate, TraitUpsert
from .... import feature_flags as feature_flags_mod
from ..definitions import ToolContext, ToolPreview

PROVENANCE = "PROPOSED_BY_CHARACTER_CREATOR"

# Protected Hitchhiker certification IDs — character creator tools must never mutate these.
HITCHHIKER_PROJECT = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
HITCHHIKER_SCENE_IDS = frozenset(
    {
        "6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f",
        "e277e621-189d-471e-b435-f01620f03d0d",
    }
)


def _require(ctx: ToolContext) -> None:
    if not feature_flags_mod.feature_flags.character_identity_v1:
        raise ValueError("Character Identity is disabled (STUDIO_FEATURE_CHARACTER_IDENTITY_V1).")
    if not ctx.project_id:
        raise ValueError("projectId is required")
    if ctx.project_id == HITCHHIKER_PROJECT:
        raise ValueError("Hitchhiker certification project is protected from Character Creator mutations.")


def _require_character(ctx: ToolContext, args: dict[str, Any]) -> str:
    _require(ctx)
    character_id = str(args.get("characterId") or "").strip()
    if character_id:
        return character_id
    name = str(args.get("characterName") or args.get("name") or "").strip()
    if name:
        row = ci.resolve_character_by_name(ctx.db, ctx.project_id, name)
        if row is not None:
            return row.id
        raise ValueError(
            "I couldn't find that character in the current project or global character list."
        )
    raise ValueError("Tell me the character's name.")


def _profile_or_raise(ctx: ToolContext, character_id: str):
    return ci.get_profile(ctx.db, ctx.project_id, character_id)


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


async def inspect_readiness(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    cov = profile.coverage.model_dump() if profile.coverage else ci.coverage(ctx.db, ctx.project_id, character_id).model_dump()
    sheet_gate: dict[str, Any] = {}
    try:
        from ....character_identity.cc_v2 import get_status

        sheet_gate = dict((get_status(ctx.db, ctx.project_id, character_id).get("sheetGate") or {}))
    except Exception:
        sheet_gate = {}
    sheet_ready = bool(sheet_gate.get("ready"))
    sheet_next = str(sheet_gate.get("nextAction") or "").strip()
    return {
        "ok": True,
        "characterId": character_id,
        "readiness": cov,
        "sheetGate": sheet_gate,
        "sheetReady": sheet_ready,
        "nextAction": sheet_next or cov.get("next_action") or "",
        "criticalBlockers": list(sheet_gate.get("missing") or []),
    }


async def build_reference_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    cov = profile.coverage
    missing = list(cov.missing_roles) if cov else list(REQUIRED_COVERAGE_ROLES)
    steps = [
        {
            "role": role,
            "guidance": ROLE_GUIDANCE.get(role, f"Generate or attach {role} reference"),
            "provenance": PROVENANCE,
        }
        for role in missing
    ]
    optional = [r for r in ADDITIONAL_ROLES if r in ("expression_sheet", "pose_sheet", "hero_identity")]
    return {
        "ok": True,
        "characterId": character_id,
        "planType": "reference",
        "requiredSteps": steps,
        "optionalRoles": optional,
        "sheetStart": (
            "The front reference can be created from this profile. "
            "Missing side and back views do not block that start."
        ),
        "korriNote": "Korri cert: visuals from written brief + image gen only; no external character sheets.",
    }


async def build_expression_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    name = (profile.name or "").lower()
    if "korri" in name or str(args.get("characterKey") or "").lower() == "korri":
        expressions = [
            "neutral_alertness",
            "mischievous_smile",
            "amused_smirk",
            "suppressed_laughter",
            "open_laughter",
            "skeptical_side_eye",
            "irritated_disbelief",
            "sudden_offense",
            "defiant_anger",
            "impulsive_excitement",
            "focused_curiosity",
            "hidden_emotional_hurt",
            "genuine_affection",
            "vulnerable_seriousness",
            "startled_realization",
            "quiet_reflection",
        ]
        next_action = "Generate Korri-specific expression_sheet from personality (not a generic 8-pack)"
    else:
        expressions = ["neutral", "joy", "sadness", "anger", "fear", "surprise", "determination"]
        next_action = "Generate expression_sheet reference covering core emotional range"
    return {
        "ok": True,
        "characterId": character_id,
        "planType": "expression",
        "targetRole": "expression_sheet",
        "expressions": expressions,
        "provenance": PROVENANCE,
        "nextAction": next_action,
    }


async def build_pose_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    name = (profile.name or "").lower()
    if "korri" in name or str(args.get("characterKey") or "").lower() == "korri":
        poses = [
            "relaxed_asymmetrical_stance",
            "weight_shifted_one_leg",
            "leaning_into_personal_space",
            "amused_arms_folded",
            "animated_storytelling",
            "blunt_pointing",
            "crouched_curiosity",
            "informal_seated",
            "sudden_turn_distraction",
            "false_innocence",
            "defensive_ready",
            "sudden_serious_stillness",
            "affectionate_shoulder_contact",
            "impatient_pacing",
            "mocking_ceremonial_imitation",
            "energetic_walking",
        ]
        next_action = "Generate Korri pose_sheet derived from personality (not generic template only)"
    else:
        perf = profile.performance or {}
        poses = ["standing_neutral", "walking", "seated", "gesture_emphasis"]
        if perf.get("posture"):
            poses.append("signature_posture")
        next_action = "Generate pose_sheet with canonical posture and gait references"
    return {
        "ok": True,
        "characterId": character_id,
        "planType": "pose",
        "targetRole": "pose_sheet",
        "poses": poses,
        "provenance": PROVENANCE,
        "nextAction": next_action,
    }


async def build_voice_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    voices = ci.list_voice_profiles(ctx.db, ctx.project_id, character_id)
    clone_without_consent = any(v.get("source_mode") == "CLONE" and not v.get("consent_record_id") for v in voices)
    mode = str(args.get("preferredMode") or "DESIGN").upper()
    plan = {
        "ok": True,
        "characterId": character_id,
        "planType": "voice",
        "recommendedMode": mode if mode != "CLONE" or not clone_without_consent else "DESIGN",
        "existingProfiles": len(voices),
        "provenance": PROVENANCE,
        "consentRequired": mode == "CLONE",
        "warnings": [],
        "nextAction": "Design voice profile from character brief",
    }
    if clone_without_consent:
        plan["warnings"].append("Clone mode blocked until synthetic-use consent is recorded.")
        plan["nextAction"] = "Record voice consent before cloning"
    return plan


async def build_wardrobe_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    wardrobes = ci.list_wardrobes(ctx.db, ctx.project_id, character_id)
    look_name = str(args.get("lookName") or "Canonical look").strip()
    return {
        "ok": True,
        "characterId": character_id,
        "planType": "wardrobe",
        "lookName": look_name,
        "existingLooks": len(wardrobes),
        "elements": ["materials", "colors", "footwear", "accessories", "hair_state", "makeup_state"],
        "targetRole": "wardrobe_reference",
        "provenance": PROVENANCE,
        "nextAction": "Define canonical wardrobe and attach wardrobe_reference" if not wardrobes else "Review existing wardrobe looks",
    }


async def build_continuity_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    continuity = profile.continuity or {}
    locked = list(continuity.get("locked_features") or [])
    return {
        "ok": True,
        "characterId": character_id,
        "planType": "continuity",
        "lockedFeatures": locked,
        "forbidInvention": list(continuity.get("forbid_invention") or []),
        "forbidRemoval": list(continuity.get("forbid_removal") or []),
        "provenance": PROVENANCE,
        "nextAction": "Document locked features and continuity restrictions" if not locked else "Review continuity rules with Continuity Supervisor",
    }


# ---------------------------------------------------------------------------
# Mutating tools (propose / apply)
# ---------------------------------------------------------------------------


def _reuse_character(ctx: ToolContext, name: str) -> dict[str, Any] | None:
    from ....creator_scope.contract import ENTITY_CHARACTER
    from ....creator_scope.service import reuse_existing_profile

    reused = reuse_existing_profile(
        ctx.db, entity_type=ENTITY_CHARACTER, project_id=ctx.project_id, name=name
    )
    if reused is None:
        return None
    profile = ci.get_profile(ctx.db, ctx.project_id, reused["entityId"])
    reused["profile"] = profile.model_dump()
    reused["created"] = False
    return reused


def preview_create_from_brief(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _require(ctx)
    name = str(args.get("name") or "").strip() or "Untitled character"
    brief = str(args.get("brief") or "").strip()
    reused = _reuse_character(ctx, name)
    if reused:
        return ToolPreview(
            summary=f"{name} already exists. I'll use the existing Character profile.",
            lines=[
                "Does not create a second Character.",
                f"Existing id: {reused['existingId']}",
                "Global" if reused.get("isGlobal") else "Local to this project",
            ],
            resourceKind="project",
            resourceId=ctx.project_id,
        )
    return ToolPreview(
        summary=f"Create draft Character Profile “{name}” from brief.",
        lines=[
            "Creates a DRAFT Character Profile (not approved).",
            f"Brief length: {len(brief)} characters.",
            "Traits tagged PROPOSED_BY_CHARACTER_CREATOR.",
            "Does not generate images or voice.",
            "Does not mutate locked Hitchhiker certification scenes.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_create_from_brief(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _require(ctx)
    name = str(args.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    reused = _reuse_character(ctx, name)
    if reused:
        if args.get("requireNew"):
            raise ValueError(
                f"A character named {name} already exists. I did not modify that character."
            )
        return reused
    brief = str(args.get("brief") or "").strip()
    role = str(args.get("role") or "").strip()
    out = ci.create_profile(
        ctx.db,
        ctx.project_id,
        CharacterProfileCreate(
            name=name,
            role=role,
            description=brief or str(args.get("description") or ""),
        ),
    )
    if brief:
        ci.upsert_trait(
            ctx.db,
            ctx.project_id,
            out.id,
            TraitUpsert(
                category="brief",
                key="source_brief",
                value=brief,
                provenance=PROVENANCE,
            ),
        )
    traits = ci.list_traits(ctx.db, ctx.project_id, out.id)
    return {
        "ok": True,
        "created": "character_profile",
        "profile": out.model_dump(),
        "provenance": PROVENANCE,
        "traits": traits,
    }


def preview_propose_traits(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    character_id = _require_character(ctx, args)
    traits = args.get("traits") or []
    count = len(traits) if isinstance(traits, list) else 0
    profile = _profile_or_raise(ctx, character_id)
    return ToolPreview(
        summary=f"Propose {count} trait(s) for “{profile.name}”.",
        lines=[
            "Traits tagged PROPOSED_BY_CHARACTER_CREATOR (not approved).",
            "Does not auto-approve the Character Profile.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_propose_traits(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    traits = args.get("traits") or []
    if not isinstance(traits, list) or not traits:
        raise ValueError("traits array is required")
    provenance = str(args.get("provenance") or PROVENANCE)
    created = []
    for item in traits:
        if not isinstance(item, dict):
            continue
        created.append(
            ci.upsert_trait(
                ctx.db,
                ctx.project_id,
                character_id,
                TraitUpsert(
                    category=str(item.get("category") or "general"),
                    key=str(item.get("key") or ""),
                    value=str(item.get("value") or ""),
                    importance=item.get("importance") or "canonical",  # type: ignore[arg-type]
                    provenance=str(item.get("provenance") or provenance),
                ),
            )
        )
    return {"ok": True, "characterId": character_id, "proposed": created, "count": len(created)}


def preview_propose_relationships(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    character_id = _require_character(ctx, args)
    rels = args.get("relationships") or []
    count = len(rels) if isinstance(rels, list) else 0
    profile = _profile_or_raise(ctx, character_id)
    return ToolPreview(
        summary=f"Propose {count} relationship(s) for “{profile.name}”.",
        lines=[
            "Relationships stored as traits (category=relationships).",
            "Provenance: PROPOSED_BY_CHARACTER_CREATOR — not approved canon.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_propose_relationships(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    rels = args.get("relationships") or []
    if not isinstance(rels, list) or not rels:
        raise ValueError("relationships array is required")
    from ....character_identity.schemas import CharacterProfileUpdate, RelationshipEdge

    edges = []
    for item in rels:
        if not isinstance(item, dict):
            continue
        target = str(item.get("targetCharacter") or item.get("target") or "").strip()
        if not target:
            continue
        edges.append(
            RelationshipEdge(
                targetCharacter=target,
                relationship=str(item.get("relationship") or item.get("relationshipType") or item.get("type") or "related"),
                tone=str(item.get("tone") or ""),
                trust=str(item.get("trust") or ""),
                conflict=str(item.get("conflict") or ""),
                physicalAggression=str(item.get("physicalAggression") or ""),
                comfortDistance=str(item.get("comfortDistance") or ""),
                typicalGreeting=str(item.get("typicalGreeting") or item.get("notes") or ""),
                communicationStyle=str(item.get("communicationStyle") or ""),
                humorStyle=str(item.get("humorStyle") or ""),
                typicalConflictResolution=str(item.get("typicalConflictResolution") or ""),
                emotionalOpenness=str(item.get("emotionalOpenness") or ""),
                protectiveness=str(item.get("protectiveness") or ""),
                authorityBalance=str(item.get("authorityBalance") or ""),
            )
        )
    # Merge with existing graph
    profile = _profile_or_raise(ctx, character_id)
    existing = list(profile.relationships or [])
    by_target = {str(e.get("targetCharacter") or "").lower(): e for e in existing if isinstance(e, dict)}
    for edge in edges:
        by_target[edge.targetCharacter.lower()] = edge.model_dump()
    merged = list(by_target.values())
    updated = ci.update_profile(
        ctx.db,
        ctx.project_id,
        character_id,
        CharacterProfileUpdate(relationships=[RelationshipEdge(**e) for e in merged]),
    )
    return {
        "ok": True,
        "characterId": character_id,
        "relationships": updated.relationships,
        "count": len(updated.relationships or []),
        "persisted": True,
        "_evidence": {"source": "character_identity.relationships"},
    }


async def get_motion_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    return {
        "ok": True,
        "characterId": character_id,
        "motion": profile.motion or {},
        "_evidence": {"source": "character_identity.motion"},
    }


async def get_performance_bible(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    return {
        "ok": True,
        "characterId": character_id,
        "performance": profile.performance or {},
        "performanceBible": profile.performance or {},
        "note": "Actor performance — complements Motion Profile; prefer over inventing delivery traits.",
        "_evidence": {"source": "character_identity.performance"},
    }


async def get_prompt_package(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    pkg = profile.prompt_package or {}
    if not pkg:
        from ....character_identity.prompt_package import generate_prompt_package

        pkg = generate_prompt_package(profile.model_dump(), character_version_id=profile.active_version_id or "")
    return {
        "ok": True,
        "characterId": character_id,
        "promptPackage": pkg,
        "grounded": True,
        "doNotInvent": True,
        "_evidence": {"source": "character_identity.prompt_package"},
    }


async def get_relationship_graph(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    return {
        "ok": True,
        "characterId": character_id,
        "relationships": profile.relationships or [],
        "_evidence": {"source": "character_identity.relationships"},
    }


async def get_visual_sheet_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.visual_sheet import get_visual_sheet_pack

    pack = get_visual_sheet_pack(ctx.db, ctx.project_id, character_id)
    return {
        "ok": True,
        "characterId": character_id,
        "visualSheet": pack,
        "grounded": True,
        "_evidence": {"source": "character_identity.visual_sheet_pack"},
    }



def _crs_generator_sources(args: dict | None = None, pack: dict | None = None) -> dict:
    """Match the Character Creator Generate button. Unset AUTO uses Qwen Image 2512."""
    from ....character_identity.visual_sheet import resolve_character_creator_generator_sources

    sources = resolve_character_creator_generator_sources(args=args, pack=pack)
    local = sources.get("local") if isinstance(sources.get("local"), list) else []
    family = ""
    if local and isinstance(local[0], dict):
        family = str(local[0].get("family") or "").strip().lower()
    if family in {"", "auto"} and not sources.get("api"):
        return {
            "local": [{"family": "qwen2512", "enabled": True, "batchCount": 1}],
            "api": None,
            "stage2Enabled": False,
        }
    return sources


def preview_propose_visual_sheet(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    explicit_count = args.get("candidateCount")
    if explicit_count is not None:
        try:
            count = max(1, int(explicit_count))
        except (TypeError, ValueError):
            count = 1
    elif bool(args.get("candidates")) or bool(args.get("options")):
        count = 4
    else:
        count = 1
    return ToolPreview(
        summary=f"Create the front reference for “{profile.name}”.",
        lines=[
            "One front view. Extras stay off.",
            "Uses an existing front image when one is already approved.",
            "Requires a usable description (>= 20 chars) — asks for one honestly if missing.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_propose_visual_sheet(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.visual_sheet import (
        _load_pack_raw,
        advance_visual_sheet_pack,
        start_visual_sheet_generation,
    )

    # Resolve candidate count: explicit candidateCount wins; otherwise when the
    # request implies "candidates"/"options" without a number, default to 4;
    # otherwise 1 (legacy single-hero visual sheet flow).
    explicit_count = args.get("candidateCount")
    if explicit_count is not None:
        try:
            candidate_count = max(1, int(explicit_count))
        except (TypeError, ValueError):
            candidate_count = 1
    elif bool(args.get("candidates")) or bool(args.get("options")):
        candidate_count = 4
    else:
        candidate_count = 1

    # Check for a usable description before generating visual candidates.
    # Honest guard — do not fabricate visuals from an empty brief. The bio
    # (description) and the visual_description (appearance) both count.
    profile = _profile_or_raise(ctx, character_id)
    bio = (profile.description or "").strip()
    visual_desc = (getattr(profile, "visual_description", "") or "").strip()
    combined = f"{bio} {visual_desc}".strip()
    if len(combined) < 20:
        return {
            "status": "missing_description",
            "message": (
                "Before I create visual candidates, I need a basic description of this character — "
                "age range, appearance, wardrobe, personality, or just the overall feeling you're after."
            ),
            "characterId": character_id,
            "characterName": profile.name,
            "requestedCount": candidate_count,
        }

    hero = str(args.get("heroAssetId") or args.get("hero_asset_id") or "").strip() or None
    if not hero:
        hero = ci.resolve_approved_reference(ctx.db, character_id, "hero_identity") or None
    try:
        pack = start_visual_sheet_generation(
            ctx.db,
            ctx.project_id,
            character_id,
            include_details=False,
            include_performance=False,
            hero_asset_id=hero,
            candidate_count=1,
            visual_style=getattr(profile, "visual_style", "") or "",
            generator_sources=_crs_generator_sources(args, pack=_load_pack_raw(ctx.db, character_id)),
            required_views=["front_full"],
            layout="single_view",
            task_type="CRS_GENERATION",
        )
    except Exception as exc:
        if hero:
            raise
        raise ValueError("The starting image was not created.") from exc
    # Advance once in case hero was provided (sheet can enqueue immediately)
    pack = advance_visual_sheet_pack(ctx.db, ctx.project_id, character_id)
    return {
        "ok": True,
        "characterId": character_id,
        "pack": pack,
        "requestedCount": candidate_count,
        "candidates": pack.get("candidates") or [],
        "persisted": True,
        "mock": False,
        "_evidence": {"source": "character_identity.visual_sheet"},
    }


def preview_advance_visual_sheet(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    character_id = _require_character(ctx, args)
    return ToolPreview(
        summary="Advance Generated Character Image Profile (poll jobs → attach → next phase).",
        lines=[
            f"Character: {character_id}",
            "Attaches completed assets to reference roles.",
            "Does not approve gates.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_advance_visual_sheet(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.visual_sheet import advance_visual_sheet_pack

    pack = advance_visual_sheet_pack(ctx.db, ctx.project_id, character_id)
    return {
        "ok": True,
        "characterId": character_id,
        "pack": pack,
        "persisted": True,
        "_evidence": {"source": "character_identity.visual_sheet"},
    }


def preview_create_from_script(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    _require(ctx)
    name = str(args.get("name") or "").strip() or "Untitled character"
    script_ref = str(args.get("scriptRef") or args.get("sceneId") or "").strip()
    return ToolPreview(
        summary=f"Create draft Character Profile “{name}” from script context.",
        lines=[
            "Creates a DRAFT Character Profile from script/scene excerpt (not approved).",
            f"Script reference: {script_ref or '(inline excerpt)'}",
            "Traits tagged PROPOSED_BY_CHARACTER_CREATOR.",
            "Does not generate images or voice.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_create_from_script(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _require(ctx)
    name = str(args.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    excerpt = str(args.get("scriptExcerpt") or args.get("excerpt") or "").strip()
    if not excerpt:
        raise ValueError("scriptExcerpt is required")
    script_ref = str(args.get("scriptRef") or args.get("sceneId") or "").strip()
    role = str(args.get("role") or "").strip()
    description = excerpt
    if script_ref:
        description = f"[Script ref: {script_ref}]\n{excerpt}"
    reused = _reuse_character(ctx, name)
    if reused:
        return reused
    out = ci.create_profile(
        ctx.db,
        ctx.project_id,
        CharacterProfileCreate(name=name, role=role, description=description),
    )
    ci.upsert_trait(
        ctx.db,
        ctx.project_id,
        out.id,
        TraitUpsert(
            category="brief",
            key="source_script",
            value=description,
            provenance=PROVENANCE,
        ),
    )
    return {
        "ok": True,
        "created": "character_profile",
        "profile": out.model_dump(),
        "provenance": PROVENANCE,
        "source": "script",
        "scriptRef": script_ref or None,
    }


async def audit_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    cov = ci.coverage(ctx.db, ctx.project_id, character_id).model_dump()
    traits = ci.list_traits(ctx.db, ctx.project_id, character_id)
    voices = ci.list_voice_profiles(ctx.db, ctx.project_id, character_id)
    refs = ci.list_references(ctx.db, ctx.project_id, character_id)
    gate_traits = [
        json.loads(t["value"])
        for t in traits
        if t.get("category") == "visual_gates" and t.get("value")
    ]
    return {
        "ok": True,
        "characterId": character_id,
        "name": profile.name,
        "status": profile.status,
        "approvalStatus": profile.approval_status,
        "coverage": cov,
        "traitCount": len(traits),
        "referenceCount": len(refs),
        "voiceProfileCount": len(voices),
        "visualGateCount": len(gate_traits),
        "provenanceSummary": {
            "traitsProposed": sum(1 for t in traits if t.get("provenance") == PROVENANCE),
            "traitsUserConfirmed": sum(1 for t in traits if t.get("provenance") == "USER_CONFIRMED"),
        },
        "criticalBlockers": cov.get("critical_blockers") or [],
        "nextAction": cov.get("next_action") or "",
    }


def preview_submit_for_review(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    return ToolPreview(
        summary=f"Submit “{profile.name}” for user review.",
        lines=[
            "Sets approval_status=review.",
            "Does NOT approve or lock the Character Profile.",
            "User must explicitly approve before generation canon applies.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_submit_for_review(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = ci.get_profile(ctx.db, ctx.project_id, character_id)
    if profile.status in ("LOCKED", "ARCHIVED"):
        raise ValueError("Cannot submit a locked or archived Character Profile.")
    result = ci.submit_for_review(ctx.db, ctx.project_id, character_id)
    assert result["approvalStatus"] != "approved"
    assert result["status"] != "APPROVED"
    return result


def preview_delete_profile(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    from ....creator_scope.contract import ENTITY_CHARACTER
    from ....creator_scope.service import delete_preview_payload
    preview = delete_preview_payload(
        ctx.db,
        entity_type=ENTITY_CHARACTER,
        entity_id=character_id,
        name=profile.name,
        is_global=profile.is_global,
        owning_project_id=profile.project_id,
    )
    scope_label = "Global" if preview["isGlobal"] else "Local"
    lines = [
        f"This is a {scope_label} Character profile.",
        f"Referenced by {preview['usageCount']} scene(s) across {preview['projectCount']} project(s).",
        "Library images and voice assets are kept — only the canonical profile is removed.",
        "This action cannot be undone.",
    ]
    if preview["isGlobal"]:
        lines.insert(1, "Deleting it will remove the canonical profile from every project using it.")
    return ToolPreview(
        summary=f'Delete Character profile "{profile.name}".',
        lines=lines,
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_delete_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    from ....character_identity.service import delete_profile
    confirm = bool(args.get("confirmCrossProject") or args.get("confirm_cross_project"))
    result = delete_profile(ctx.db, ctx.project_id, character_id, confirm_cross_project=confirm)
    return {"ok": True, "deleted": result.get("deleted"), "name": result.get("name"), "characterId": character_id}


# ---------------------------------------------------------------------------
# Voice Creator workspace tools (Phase 4.3 corrective)
# ---------------------------------------------------------------------------


def _default_voice_message(character_name: str, active: dict[str, Any] | None, *, has_approved: bool) -> str:
    name = (character_name or "").strip() or "This character"
    if has_approved:
        profile_name = str((active or {}).get("name") or "").strip()
        version = (active or {}).get("version_number")
        suffix = f" (v{version})" if version not in (None, "", 0) else ""
        if profile_name:
            return f"{name}'s current default voice is {profile_name}{suffix}."
        return f"{name} has an approved default voice{suffix}."
    return f"{name} has no Character Voice currently approved."


async def get_voice_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.voice_creator import get_voice_workspace

    ws = get_voice_workspace(ctx.db, ctx.project_id, character_id)
    active = ws.get("activeVoice") or {}
    has_approved = bool(ws.get("activeVoiceProfileId") and str(active.get("approval_status") or "").lower() == "approved")
    return {
        "ok": True,
        "characterId": character_id,
        "characterName": ws.get("characterName"),
        "activeVoiceProfileId": ws.get("activeVoiceProfileId") if has_approved else None,
        "approvalStatus": active.get("approval_status") if has_approved else None,
        "sourceMode": active.get("source_mode") if has_approved else None,
        "provider": active.get("provider") if has_approved else None,
        "hasApprovedVoice": has_approved,
        "versionNumber": active.get("version_number") if has_approved else None,
        "message": _default_voice_message(str(ws.get("characterName") or ""), active if isinstance(active, dict) else None, has_approved=has_approved),
        "offer": None if has_approved else "Open Voice Creator",
        "providers": ws.get("providers"),
        "methods": ws.get("methods"),
        "performanceAttached": ws.get("performanceAttached"),
        "emotionAttached": ws.get("emotionAttached"),
        "mock": False,
        "grounded": True,
        "_evidence": {"source": "character_identity.voice_creator"},
    }


async def get_voice_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.voice_creator import get_voice_workspace

    ws = get_voice_workspace(ctx.db, ctx.project_id, character_id)
    return {
        "ok": True,
        "characterId": character_id,
        "activeVoice": ws.get("activeVoice"),
        "designBrief": ws.get("designBrief"),
        "compiledDesignPrompt": ws.get("compiledDesignPrompt"),
        "doNotInvent": True,
        "mock": False,
        "_evidence": {"source": "character_identity.voice_creator"},
    }


async def get_voice_candidates(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.voice_creator import list_candidates

    voice_id = str(args.get("voiceId") or args.get("voiceProfileId") or "").strip()
    if not voice_id:
        profile = _profile_or_raise(ctx, character_id)
        voice_id = profile.active_voice_profile_id or ""
    if not voice_id:
        return {"ok": True, "candidates": [], "note": "No voice profile yet.", "mock": False}
    out = list_candidates(ctx.db, ctx.project_id, character_id, voice_id)
    ready = [c for c in (out.get("candidates") or []) if c.get("status") == "ready"]
    return {
        "ok": True,
        "characterId": character_id,
        "voiceProfileId": voice_id,
        "candidates": out.get("candidates") or [],
        "readyCount": len(ready),
        "mock": False,
        "_evidence": {"source": "character_identity.voice_creator.candidates"},
    }


async def compare_voice_candidates(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.voice_creator import list_candidates

    voice_id = str(args.get("voiceId") or "").strip()
    a = str(args.get("candidateA") or args.get("candidateIdA") or "").strip()
    b = str(args.get("candidateB") or args.get("candidateIdB") or "").strip()
    if not voice_id or not a or not b:
        raise ValueError("voiceId, candidateA, and candidateB are required")
    out = list_candidates(ctx.db, ctx.project_id, character_id, voice_id)
    meta = {c["id"]: c for c in (out.get("candidates") or [])}
    ca, cb = meta.get(a), meta.get(b)
    if not ca or not cb:
        raise ValueError("One or both candidates not found")
    return {
        "ok": True,
        "candidateA": ca,
        "candidateB": cb,
        "dimensions": [
            "identity_fit",
            "age_fit",
            "clarity",
            "energy",
            "sarcasm",
            "emotional_range",
            "consistency",
            "pronunciation",
            "artifacting",
            "performance_suitability",
        ],
        "note": "Human review is authoritative; Co-Director does not auto-approve.",
        "mock": False,
        "_evidence": {"source": "character_identity.voice_creator.compare"},
    }


async def get_pronunciation_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    voices = ci.list_voice_profiles(ctx.db, ctx.project_id, character_id)
    voice_id = str(args.get("voiceId") or "").strip()
    row = next((v for v in voices if v["id"] == voice_id), None) if voice_id else None
    if not row and voices:
        row = next((v for v in reversed(voices) if v.get("approval_status") == "approved"), voices[-1])
    entries = (row or {}).get("pronunciations") or []
    return {
        "ok": True,
        "characterId": character_id,
        "voiceProfileId": (row or {}).get("id"),
        "pronunciations": entries,
        "complete": len(entries) > 0,
        "mock": False,
        "_evidence": {"source": "character_identity.voice_creator.pronunciations"},
    }


async def get_reaction_coverage(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.voice_creator import KORRI_REACTIONS

    voices = ci.list_voice_profiles(ctx.db, ctx.project_id, character_id)
    row = voices[-1] if voices else None
    reactions = (row or {}).get("reactions") or []
    ready_ids = {r.get("id") for r in reactions if r.get("status") == "ready"}
    missing = [r["id"] for r in KORRI_REACTIONS if r["id"] not in ready_ids]
    return {
        "ok": True,
        "characterId": character_id,
        "reactions": reactions,
        "missing": missing,
        "mock": False,
        "_evidence": {"source": "character_identity.voice_creator.reactions"},
    }


async def open_voice_creator(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.voice_creator import get_voice_workspace

    method = str(args.get("method") or args.get("preferredMethod") or "").strip().lower()
    if method not in {"create", "clone", "existing"}:
        method = ""
    ws = get_voice_workspace(ctx.db, ctx.project_id, character_id)
    active = ws.get("activeVoice") or {}
    has_approved = bool(ws.get("activeVoiceProfileId") and str(active.get("approval_status") or "").lower() == "approved")
    return {
        "ok": True,
        "characterId": character_id,
        "characterName": ws.get("characterName"),
        "method": method or None,
        "contentTab": "voice_creator",
        "uiAction": "open_voice_creator",
        "hasApprovedVoice": has_approved,
        "activeVoiceProfileId": ws.get("activeVoiceProfileId") if has_approved else None,
        "message": _default_voice_message(str(ws.get("characterName") or ""), active if isinstance(active, dict) else None, has_approved=has_approved),
        "offer": None if has_approved else "Open Voice Creator",
        "mock": False,
        "_evidence": {"source": "character_identity.voice_creator.ui"},
    }


def preview_voice_design(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    return ToolPreview(
        summary=f"Preview Qwen Voice Design request for “{profile.name}”.",
        lines=[
            "Compiles structured design brief + Performance Bible / Emotion attachment flags.",
            "Does not generate audio.",
            "Does not invent warm mid baritone defaults for Korri.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def _brief_from_args(args: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(args.get("designBrief"), dict):
        return args["designBrief"]
    raw = args.get("designBriefJson")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def apply_preview_voice_design(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.voice_creator import preview_voice_design as _preview

    out = _preview(ctx.db, ctx.project_id, character_id, brief=_brief_from_args(args))
    return {**out, "persisted": False, "_evidence": {"source": "character_identity.voice_creator.preview"}}


def preview_generate_voice_candidates(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    count = int(args.get("candidateCount") or 4)
    return ToolPreview(
        summary=f"Generate {count} Qwen voice candidates for “{profile.name}”.",
        lines=[
            "Uses certified Qwen Voice Design adapter + asset registration.",
            "Creates draft Voice Profile with real candidate WAVs (not mock).",
            "Does NOT approve — owner must approve after audition.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_generate_voice_candidates(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.voice_creator import generate_voice_candidates

    out = generate_voice_candidates(
        ctx.db,
        ctx.project_id,
        character_id,
        brief=_brief_from_args(args),
        candidate_count=int(args.get("candidateCount") or 4),
        test_line=str(args.get("testLine") or "") or None,
        name=str(args.get("name") or "") or None,
    )
    return {
        "ok": True,
        "voice": out,
        "candidateCount": len(out.get("candidates") or []),
        "persisted": True,
        "approved": False,
        "mock": False,
        "_evidence": {"source": "character_identity.voice_creator.generate"},
    }


def preview_refine_voice_candidate(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Refine voice candidate (creates child — does not overwrite parent).",
        lines=[
            f"Parent candidate: {args.get('candidateId')}",
            f"Refinement: {args.get('refinement') or args.get('notes') or '(default)'}",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_refine_voice_candidate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.voice_creator import refine_candidate

    voice_id = str(args.get("voiceId") or "").strip()
    candidate_id = str(args.get("candidateId") or "").strip()
    refinement = str(args.get("refinement") or args.get("notes") or "Refine slightly").strip()
    if not voice_id or not candidate_id:
        raise ValueError("voiceId and candidateId are required")
    out = refine_candidate(
        ctx.db, ctx.project_id, character_id, voice_id, candidate_id, refinement=refinement
    )
    return {**out, "persisted": True, "approved": False, "_evidence": {"source": "character_identity.voice_creator.refine"}}


def preview_approve_voice_candidate(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Approve a voice sample as this character's current default voice.",
        lines=[
            "Sets the selected Voice Profile as the character's current approved voice.",
            "Previous approved voices stay in version history. Profile audio is not overwritten.",
            "Refreshes Prompt Package voice fields.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_approve_voice_candidate(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.voice_creator import approve_voice_candidate

    voice_id = str(args.get("voiceId") or "").strip()
    if not voice_id:
        raise ValueError("voiceId is required")
    out = approve_voice_candidate(
        ctx.db,
        ctx.project_id,
        character_id,
        voice_id,
        candidate_id=str(args.get("candidateId") or "") or None,
        approved_by=str(args.get("approvedBy") or "owner"),
    )
    if not out.get("ok"):
        raise ValueError("Voice approval did not persist")
    return {**out, "persisted": True, "approved": True, "_evidence": {"source": "character_identity.voice_creator.approve"}}


def preview_generate_reactions(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Generate character reaction coverage via approved/draft voice dialogue path.",
        lines=["Registers real audio assets per reaction; reports missing on failure."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_generate_reactions(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.voice_creator import generate_reactions

    voice_id = str(args.get("voiceId") or "").strip()
    if not voice_id:
        raise ValueError("voiceId is required")
    out = generate_reactions(ctx.db, ctx.project_id, character_id, voice_id)
    return {**out, "persisted": True, "_evidence": {"source": "character_identity.voice_creator.reactions"}}


def preview_test_pronunciation(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary=f"Test pronunciation for “{args.get('word') or '?'}”.",
        lines=["Generates real dialogue audio; does not invent success."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_test_pronunciation(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.voice_creator import test_pronunciation

    voice_id = str(args.get("voiceId") or "").strip()
    word = str(args.get("word") or "").strip()
    if not voice_id or not word:
        raise ValueError("voiceId and word are required")
    out = test_pronunciation(
        ctx.db,
        ctx.project_id,
        character_id,
        voice_id,
        word=word,
        phonetic=str(args.get("phonetic") or ""),
    )
    return {**out, "persisted": True, "_evidence": {"source": "character_identity.voice_creator.pronunciation_test"}}


def preview_validate_clone_source(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Validate clone reference audio (duration, format, speech coverage).",
        lines=["Honest validation — no fabricated pass."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_validate_clone_source(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _require_character(ctx, args)
    from ....character_identity.voice import validate_voice_reference

    path = str(args.get("path") or args.get("referencePath") or "").strip()
    transcript = str(args.get("transcript") or "").strip()
    if not path:
        raise ValueError("path is required")
    out = validate_voice_reference(path, transcript=transcript)
    return {**out, "mock": False, "_evidence": {"source": "character_identity.voice.validate_reference"}}


def preview_generate_voice_clone(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Generate Qwen Voice Clone candidate (consent required).",
        lines=["Blocked without valid consent + reference validation.", "Does not approve."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_generate_voice_clone(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.schemas import VoiceConsentCreate
    from ....character_identity.voice_creator import clone_with_workspace

    consent_raw: dict[str, Any] = {}
    if isinstance(args.get("consent"), dict):
        consent_raw = args["consent"]
    elif isinstance(args.get("consentJson"), str) and args.get("consentJson"):
        try:
            parsed = json.loads(str(args["consentJson"]))
            if isinstance(parsed, dict):
                consent_raw = parsed
        except Exception:
            consent_raw = {}
    body = type(
        "Body",
        (),
        {
            "name": str(args.get("name") or "Cloned voice"),
            "reference_path": str(args.get("referencePath") or args.get("path") or ""),
            "transcript": str(args.get("transcript") or ""),
            "test_line": str(args.get("testLine") or "Hello."),
            "consent": VoiceConsentCreate(**consent_raw)
            if consent_raw
            else VoiceConsentCreate(consent_confirmed=False, synthetic_generation_allowed=False),
        },
    )()
    out = clone_with_workspace(ctx.db, ctx.project_id, character_id, body)
    return {
        "ok": True,
        "voice": out,
        "persisted": True,
        "approved": False,
        "mock": False,
        "_evidence": {"source": "character_identity.voice_creator.clone"},
    }


_ANGLE_NAMES = ("side", "three_quarter", "back")


def _normalize_angle(raw: Any) -> str:
    text = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "side": "side",
        "profile": "side",
        "three_quarter": "three_quarter",
        "threequarter": "three_quarter",
        "3_4": "three_quarter",
        "3/4": "three_quarter",
        "back": "back",
        "rear": "back",
    }
    angle = aliases.get(text)
    if angle not in _ANGLE_NAMES:
        raise ValueError("angle must be side, three_quarter, or back.")
    return angle


async def get_angles(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    from ....character_identity.cc_v2 import get_status

    state = get_status(ctx.db, ctx.project_id, character_id)
    mv = (state.get("multiView") or {}).get("angles") or {}
    front = ((state.get("views") or {}).get("front") or {})
    angles = {}
    for name in _ANGLE_NAMES:
        slot = mv.get(name) or {}
        angles[name] = {
            "assetId": slot.get("assetId"),
            "approved": bool(slot.get("approved")),
            "source": slot.get("source"),
            "status": slot.get("status"),
        }
    sheet_gate = dict(state.get("sheetGate") or {})
    return {
        "ok": True,
        "characterId": character_id,
        "characterName": state.get("name"),
        "front": {
            "assetId": front.get("assetId"),
            "approved": bool(front.get("approved")),
            "source": front.get("source"),
            "status": front.get("status"),
        },
        "angles": angles,
        "sheetGate": sheet_gate,
        "sheetReady": bool(sheet_gate.get("ready")),
        "nextAction": sheet_gate.get("nextAction") or "",
        "sameStore": True,
        "mock": False,
    }


def preview_adopt_angle(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    character_id = _require_character(ctx, args)
    angle = _normalize_angle(args.get("angle"))
    profile = _profile_or_raise(ctx, character_id)
    return ToolPreview(
        summary=f"Use this picture as {profile.name}'s {angle.replace('_', ' ')} view.",
        lines=[
            "Saves it to the Library and binds it to this character.",
            "Does not approve the angle. The creator still clicks Approve.",
            "Does not create a new character.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_adopt_angle(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    angle = _normalize_angle(args.get("angle"))
    asset_id = str(args.get("assetId") or args.get("imageAssetId") or "").strip()
    if not asset_id:
        raise ValueError("assetId is required")
    from ....character_identity.cc_v3_multiview import adopt_angle_from_asset

    state = adopt_angle_from_asset(
        ctx.db,
        ctx.project_id,
        character_id,
        angle,
        asset_id,
        source_type="uploaded",
    )
    slot = ((state.get("multiView") or {}).get("angles") or {}).get(angle) or {}
    return {
        "ok": True,
        "characterId": character_id,
        "angle": angle,
        "assetId": slot.get("assetId"),
        "approved": bool(slot.get("approved")),
        "source": slot.get("source"),
        "status": slot.get("status"),
    }


def preview_approve_angle(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    character_id = _require_character(ctx, args)
    angle = _normalize_angle(args.get("angle"))
    profile = _profile_or_raise(ctx, character_id)
    return ToolPreview(
        summary=f"Approve {profile.name}'s {angle.replace('_', ' ')} view.",
        lines=["Makes this angle the approved character view.", "Works the same for uploaded and generated pictures."],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_approve_angle(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    angle = _normalize_angle(args.get("angle"))
    from ....character_identity.cc_v3_multiview import set_angle_approval

    state = set_angle_approval(ctx.db, ctx.project_id, character_id, angle, approved=True)
    slot = ((state.get("multiView") or {}).get("angles") or {}).get(angle) or {}
    sheet_gate = dict(state.get("sheetGate") or {})
    return {
        "ok": True,
        "characterId": character_id,
        "angle": angle,
        "assetId": slot.get("assetId"),
        "approved": bool(slot.get("approved")),
        "source": slot.get("source"),
        "sheetGate": sheet_gate,
        "sheetReady": bool(sheet_gate.get("ready")),
        "nextAction": sheet_gate.get("nextAction") or "",
    }


def preview_generate_angles(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    character_id = _require_character(ctx, args)
    profile = _profile_or_raise(ctx, character_id)
    return ToolPreview(
        summary=f"Generate missing Character Angles for {profile.name}.",
        lines=[
            "Uses Qwen Image Edit from the approved Front.",
            "Skips uploaded and already approved angles.",
            "Does not replace the current character.",
        ],
        resourceKind="project",
        resourceId=ctx.project_id,
    )


def apply_generate_angles(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    character_id = _require_character(ctx, args)
    angle = str(args.get("angle") or "").strip()
    from ....character_identity.cc_v3_multiview import generate_multiview, regenerate_angle

    if angle:
        state = regenerate_angle(ctx.db, ctx.project_id, character_id, _normalize_angle(angle))
    else:
        state = generate_multiview(ctx.db, ctx.project_id, character_id)
    return {
        "ok": True,
        "characterId": character_id,
        "multiView": state.get("multiView"),
    }
