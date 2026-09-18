"""Compile a scene prompt through a resolved three-layer generator profile.

Hot-path dispatch is by profile.prompt.dialect (and inherited pack rules).
Never branch on generator-id substrings.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional

from ..model_intelligence.compiler import compile_intent
from ..model_intelligence.schemas import (
    AppliedRule,
    CompileResult,
    ConfidenceLevel,
    NormalizedGenerationIntent,
    ProvenanceClaim,
)
from .resolver import try_resolve_profile
from .schemas import UNAVAILABLE_MESSAGE, VideoGeneratorKnowledgeProfile

_SUBJECT_TAG = re.compile(r"<subject\s+\d+>", re.IGNORECASE)


def _rule(rule_id: str, description: str) -> AppliedRule:
    return AppliedRule(
        ruleId=rule_id,
        description=description,
        provenance=ProvenanceClaim(
            sourceType=ConfidenceLevel.VERIFIED_INTERNAL,
            sourceReference=rule_id,
            confidence=0.8,
        ),
    )


def _unavailable(generator_id: Optional[str], err: Optional[str] = None) -> CompileResult:
    warnings = [UNAVAILABLE_MESSAGE]
    if err:
        warnings.append(err)
    return CompileResult(
        modelId=generator_id or "unknown",
        providerId="unknown",
        engineId=generator_id or "unknown",
        compiledPrompt="",
        negativePrompt="",
        parameters={},
        warnings=warnings,
        confidence=0.0,
        status="GENERATOR_KNOWLEDGE_UNAVAILABLE",
        limitations=[UNAVAILABLE_MESSAGE],
        audioPlanSummary=UNAVAILABLE_MESSAGE,
        originalRequest="",
    )


def _apply_h3_frame_roles(ctx: dict[str, Any]) -> None:
    """MiniMax H3 live adapter: CRS / ERS / PRS then prior-frame continuity."""
    prompt_layer = ctx["prompt_layer"]
    cap = ctx.get("capability")
    roles = list(prompt_layer.frameRoles or ["crs", "ers", "prs", "prior_frame"])
    ctx["applied"].append(
        _rule("prompt.frame_roles", "Frame roles: " + ", ".join(roles))
    )
    contract = [
        "Timeline H3 is Reference-to-Video.",
        "CRS / ERS / PRS bind through wired ref_images (LoadImage → ref_image_N).",
        "Owner dialect: lowercase <subject N> is Name. (N matches ref_image_(N-1)).",
        "Timed Prompt = Comfy Input Text; do not rely on orphan trailing <Picture N>.",
    ]
    if cap is not None:
        for note in cap.notes:
            if note and note not in ctx["warnings"]:
                ctx["warnings"].append(note)
        ctx["meta"]["imageSlots"] = dict(cap.imageSlots or {})
        ctx["meta"]["maxImagesTextToVideo"] = cap.maxImagesTextToVideo
        ctx["meta"]["maxImagesImageToVideo"] = cap.maxImagesImageToVideo
    for line in contract:
        if line not in ctx["warnings"]:
            ctx["warnings"].append(line)
        ctx["applied"].append(_rule("prompt.h3_contract", line))
    if prompt_layer.disclosure and prompt_layer.disclosure not in ctx["warnings"]:
        ctx["warnings"].append(prompt_layer.disclosure)
    if not prompt_layer.nativeThreeKeyframe:
        disclosure = prompt_layer.disclosure or (
            "MiniMax H3 does not take three timed keyframes natively. "
            "Adept plans this as two guided beats: Start to Middle, then Middle to End."
        )
        ctx["applied"].append(_rule("prompt.segmented_three_frame", disclosure))
        if disclosure not in ctx["warnings"]:
            ctx["warnings"].append(disclosure)
    ctx["meta"]["subjectTagsEmitted"] = False
    ctx["meta"]["frameRoles"] = roles


def _apply_pack_rules(ctx: dict[str, Any]) -> None:
    """Pack-backed dialects apply rules via compile_intent; nothing extra here."""
    ctx["meta"]["packDialect"] = ctx["prompt_layer"].dialect


def _apply_named_r2v(ctx: dict[str, Any]) -> None:
    dialect = str(ctx["prompt_layer"].dialect or "")
    ctx["applied"].append(_rule("prompt.r2v_named", f"Named extras only; dialect={dialect}"))
    ctx["meta"]["subjectTagsEmitted"] = False


def _apply_seedance(ctx: dict[str, Any]) -> None:
    ctx["applied"].append(
        _rule("prompt.seedance_r2v", "Seedance R2V uses @ImageN/@Video1 only when a video ref is uploaded")
    )
    ctx["meta"]["subjectTagsEmitted"] = False


# Dialect registry. Keys are profile.prompt.dialect values, never generator ids.
DIALECT_HANDLERS: dict[str, Callable[[dict[str, Any]], None]] = {
    "h3_frame_roles": _apply_h3_frame_roles,
    "pack_rules": _apply_pack_rules,
    "ltx25_single_cond": _apply_named_r2v,
    "seedance_at_tokens": _apply_seedance,
    "kling_named": _apply_named_r2v,
    "veo_named": _apply_named_r2v,
}


def _version_notes(
    profile: VideoGeneratorKnowledgeProfile, requested_id: str
) -> list[str]:
    notes: list[str] = []
    extra = profile.workflow.versionNotes.get(requested_id)
    if extra is None:
        return notes
    if extra.requiredComponents:
        notes.append(
            f"Workflow version {requested_id}: require "
            + ", ".join(extra.requiredComponents)
        )
    if extra.submitParams:
        notes.append(
            f"Workflow version {requested_id} submit params: "
            + ", ".join(extra.submitParams)
        )
    notes.extend(extra.notes)
    return notes


def _compile_profile_rules(
    profile: VideoGeneratorKnowledgeProfile,
    intent: NormalizedGenerationIntent,
    requested_id: str,
) -> CompileResult:
    prompt_layer = profile.prompt
    applied: list[AppliedRule] = []
    warnings: list[str] = []
    meta: dict[str, Any] = {
        "profileId": profile.profileId,
        "dialect": prompt_layer.dialect,
        "requestedGeneratorId": requested_id,
        "subjectTagsEmitted": False,
    }
    ctx = {
        "prompt_layer": prompt_layer,
        "capability": profile.capability,
        "applied": applied,
        "warnings": warnings,
        "meta": meta,
    }

    positive: list[str] = []
    if intent.userPrompt:
        positive.append(intent.userPrompt.strip())
    for phrase in prompt_layer.positiveAppend:
        if phrase and phrase not in (intent.userPrompt or ""):
            positive.append(str(phrase))
            applied.append(_rule("prompt.positive_append", f"Appended structural phrase: {phrase}"))
    for item in intent.mustInclude:
        if item:
            positive.append(str(item))

    negative: list[str] = []
    if intent.negativePromptHint:
        negative.append(intent.negativePromptHint)
    if prompt_layer.supportsNegativePrompt:
        for phrase in prompt_layer.negativeBase:
            negative.append(str(phrase))
            applied.append(_rule("prompt.negative_base", f"Negative base: {phrase}"))
    elif prompt_layer.negativeBase:
        warnings.append("Profile lists negativeBase but supportsNegativePrompt is false; omitted")

    handler = DIALECT_HANDLERS.get(prompt_layer.dialect)
    if handler is None:
        return _unavailable(
            requested_id,
            f"GENERATOR_KNOWLEDGE_UNAVAILABLE: unknown dialect {prompt_layer.dialect!r}",
        )
    handler(ctx)

    compiled = ". ".join(p for p in positive if p).strip()
    # Timeline H3 owner dialect: never strip ``<subject N>`` on h3_frame_roles.
    if (
        _SUBJECT_TAG.search(compiled)
        and not prompt_layer.subjectTags
        and prompt_layer.dialect != "h3_frame_roles"
    ):
        compiled = _SUBJECT_TAG.sub("", compiled).strip()
        warnings.append("Stripped undocumented subject tags (not in this profile prompt layer)")
        applied.append(_rule("prompt.no_subject_tags", "Subject tags are not part of this dialect"))
    elif _SUBJECT_TAG.search(compiled) and prompt_layer.dialect == "h3_frame_roles":
        warnings.append("Preserved owner-dialect <subject N> on h3_frame_roles knowledge compile")
        meta["subjectTagsEmitted"] = True

    version = _version_notes(profile, requested_id)
    warnings.extend(version)
    for note in version:
        applied.append(_rule("workflow.version_note", note))

    negative_joined = ", ".join(dict.fromkeys(p for p in negative if p))
    cap = profile.capability
    return CompileResult(
        modelId=profile.profileId,
        providerId="comfy.local",
        engineId=profile.workflow.engineId or profile.profileId,
        compiledPrompt=compiled,
        negativePrompt=negative_joined,
        parameters={
            "profileId": profile.profileId,
            "dialect": prompt_layer.dialect,
            "requestedGeneratorId": requested_id,
            "frameRoles": meta.get("frameRoles") or [],
            "subjectTagsEmitted": False,
            "imageSlots": meta.get("imageSlots") or {},
            "maxImagesTextToVideo": meta.get("maxImagesTextToVideo"),
            "maxImagesImageToVideo": meta.get("maxImagesImageToVideo"),
        },
        appliedRules=applied,
        warnings=warnings,
        confidence=0.7,
        knowledgePackVersion=profile.profileId,
        modelVersion=profile.profileId,
        audioPlanSummary="native" if cap.nativeAudio else "external_or_none",
        limitations=list(cap.notes),
        status="ok",
        originalRequest=intent.userPrompt or "",
        normalizedIntent={
            "dialect": prompt_layer.dialect,
            "profileId": profile.profileId,
            "requestedGeneratorId": requested_id,
            "subjectTagsEmitted": False,
        },
    )


def compile_for_generator(
    generator_id: Optional[str],
    intent: NormalizedGenerationIntent,
) -> CompileResult:
    """Compile using the selected generator .md, then the machine-readable profile."""
    from ..knowledgebase.video_generators import load_video_generator_knowledge

    requested_id = str(generator_id or "").strip()
    kb = load_video_generator_knowledge(requested_id)
    profile, err = try_resolve_profile(generator_id)
    if profile is None:
        if kb.loaded and kb.compile.dialect == "unavailable":
            result = CompileResult(
                modelId=requested_id or "unknown",
                providerId="none",
                engineId=requested_id or "unknown",
                compiledPrompt=str(intent.userPrompt or "").strip(),
                negativePrompt="",
                parameters={},
                warnings=["This generator row is not a Timeline execution path."],
                confidence=0.4,
                status="ok",
                limitations=["Not a Timeline execution path."],
                originalRequest=intent.userPrompt or "",
            )
            return _attach_video_knowledge(result, requested_id, kb)
        return _unavailable(generator_id, err)

    prompt_layer = profile.prompt
    pack_id = prompt_layer.sourcePack or prompt_layer.inheritPromptFromPack
    if kb.compile.dialect in {
        "ltx25_single_cond",
        "seedance_at_tokens",
        "kling_named",
        "veo_named",
        "unavailable",
    }:
        pack_id = None

    if pack_id:
        result = compile_intent(intent, model_id=pack_id)
        if result.status == "MODEL_KNOWLEDGE_UNAVAILABLE":
            return _unavailable(generator_id, result.warnings[0] if result.warnings else None)
        if _SUBJECT_TAG.search(result.compiledPrompt or ""):
            result.compiledPrompt = _SUBJECT_TAG.sub("", result.compiledPrompt).strip()
            result.warnings.append("Stripped subject tags; this dialect does not emit MiniMax tags")
        version = _version_notes(profile, requested_id)
        if version:
            result.warnings = list(result.warnings) + version
            result.appliedRules = list(result.appliedRules) + [
                _rule("workflow.version_note", note) for note in version
            ]
        result.normalizedIntent = {
            **(result.normalizedIntent or {}),
            "dialect": prompt_layer.dialect,
            "profileId": profile.profileId,
            "requestedGeneratorId": requested_id,
            "sourcePack": pack_id,
            "subjectTagsEmitted": False,
        }
        result.parameters = {
            **(result.parameters or {}),
            "profileId": profile.profileId,
            "dialect": prompt_layer.dialect,
            "requestedGeneratorId": requested_id,
            "subjectTagsEmitted": False,
        }
        handler = DIALECT_HANDLERS.get(prompt_layer.dialect)
        if handler is not None and prompt_layer.dialect != "pack_rules":
            ctx = {
                "prompt_layer": prompt_layer,
                "applied": result.appliedRules,
                "warnings": result.warnings,
                "meta": {},
            }
            handler(ctx)
        return _attach_video_knowledge(_apply_real_subject_slots(result, profile, intent), requested_id, kb)

    result = _compile_profile_rules(profile, intent, requested_id)
    return _attach_video_knowledge(_apply_real_subject_slots(result, profile, intent), requested_id, kb)


def _attach_video_knowledge(result: CompileResult, generator_id: str, kb=None) -> CompileResult:
    from ..knowledgebase.video_generators import load_video_generator_knowledge

    loaded = kb if kb is not None else load_video_generator_knowledge(generator_id)
    result.parameters = {
        **(result.parameters or {}),
        "knowledgeSpecPath": str(loaded.spec_path),
        "knowledgeLoaded": loaded.loaded,
        "knowledgeFile": loaded.spec_path.name if loaded.loaded else "",
        "r2vContract": loaded.compile.to_dict(),
        "r2vDialect": loaded.compile.dialect,
    }
    if loaded.loaded:
        result.appliedRules = list(result.appliedRules or []) + [
            _rule("prompt.video_knowledge_md", f"Loaded {loaded.spec_path.name} before R2V compile")
        ]
    return result


def bind_minimax_subject_tags(
    prompt: str,
    *,
    dialect: str,
    slots: list[Any],
) -> tuple[str, list[str], bool]:
    """H3 Timeline: preserve owner-dialect lowercase ``<subject N>``; no orphan Pictures.

    Timeline R2V ``compile_h3_prompt`` / ``render_h3`` is the slot-order authority and
    emits ``<subject N> is Name.`` bound to LoadImage / ref_image_(N-1). This binder
    must not strip that dialect on the H3 path, and must not append trailing orphan
    ``<Picture N>`` lists as a substitute for subject binding.
    """
    warnings: list[str] = []
    cleaned = prompt or ""
    if dialect != "h3_frame_roles":
        if _SUBJECT_TAG.search(cleaned):
            cleaned = _SUBJECT_TAG.sub("", cleaned).strip()
            warnings.append("Stripped MiniMax subject tags; this dialect does not emit them")
        return cleaned, warnings, False

    # Count wired slots for disclosure only — do not append orphan <Picture N>.
    wired_count = 0
    for item in slots or []:
        if not isinstance(item, dict):
            continue
        entity_id = str(item.get("entityId") or item.get("identityId") or "").strip()
        asset_id = str(item.get("assetId") or "").strip()
        route_slot = str(item.get("routeASlot") or item.get("slot") or "").strip()
        wired = bool(item.get("wired"))
        if entity_id and asset_id and route_slot and wired:
            wired_count += 1
    has_owner_subjects = bool(re.search(r"<subject\s+\d+>", cleaned, re.IGNORECASE))
    if has_owner_subjects:
        warnings.append(
            "Preserved owner-dialect lowercase <subject N> on Timeline H3 path "
            "(binding authority is R2V compile_h3_prompt)"
        )
        return cleaned, warnings, True
    if wired_count:
        warnings.append(
            f"{wired_count} wired H3 ref slot(s); subject tags emitted by Timeline R2V "
            "owner dialect (<subject N> is Name.), not orphan <Picture N>"
        )
        # Signal that real slots exist so callers know binding is expected downstream.
        return cleaned, warnings, True
    return cleaned, warnings, False

def _apply_real_subject_slots(
    result: CompileResult,
    profile: VideoGeneratorKnowledgeProfile,
    intent: NormalizedGenerationIntent,
) -> CompileResult:
    dialect = str(profile.prompt.dialect or "")
    compiled, extra, emitted = bind_minimax_subject_tags(
        result.compiledPrompt or "",
        dialect=dialect,
        slots=list(intent.subjects or []),
    )
    result.compiledPrompt = compiled
    if extra:
        result.warnings = list(result.warnings or []) + extra
    result.parameters = {**(result.parameters or {}), "subjectTagsEmitted": emitted}
    if isinstance(result.normalizedIntent, dict):
        result.normalizedIntent = {**result.normalizedIntent, "subjectTagsEmitted": emitted}
    if emitted:
        result.appliedRules = list(result.appliedRules or []) + [
            _rule("prompt.real_subject_slots", "Subject tags bound from wired Route A reference slots")
        ]
    return result
