"""Generate Character Prompt Package from approved profile — derived products, not identities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _join(parts: list[str]) -> str:
    return ", ".join(p for p in parts if p and str(p).strip())


def _rel_line(r: dict[str, Any]) -> str:
    target = r.get("targetCharacter") or "?"
    base = f"{target}: {r.get('relationship')} ({r.get('tone')})"
    dyn = _join(
        [
            r.get("communicationStyle") or "",
            r.get("humorStyle") or "",
            r.get("typicalConflictResolution") or "",
            r.get("protectiveness") or "",
            r.get("authorityBalance") or "",
        ]
    )
    return f"{base}; dynamics=[{dyn}]" if dyn else base


def generate_prompt_package(profile: dict[str, Any], *, character_version_id: str = "") -> dict[str, Any]:
    """Build immutable prompt products from approved CharacterProfile fields only — no invention."""
    name = profile.get("name") or "Character"
    role = profile.get("role") or ""
    hair = profile.get("hair") or {}
    skin = profile.get("skin") or {}
    motion = profile.get("motion") or {}
    emotion = profile.get("emotion") or {}
    performance = profile.get("performance") or {}
    personality = profile.get("personality") or {}
    wardrobe = profile.get("active_wardrobe") or profile.get("wardrobe") or {}
    relationships = profile.get("relationships") or []
    continuity = profile.get("continuity") or {}

    appearance = _join(
        [
            f"{hair.get('primary_color', '')} hair".strip(),
            hair.get("canonical_style") or "",
            f"{skin.get('skin_tone', '')} skin".strip(),
            profile.get("body_type") or "",
            profile.get("height_description") or "",
            "pointed elf ears"
            if "elf" in (profile.get("species_or_type") or "").lower()
            or "ear" in str(continuity.get("locked_features") or []).lower()
            else "",
            skin.get("tattoos") or "",
        ]
    )
    locked = continuity.get("locked_features") or []
    if locked:
        appearance = _join([appearance, "; locked: " + ", ".join(locked)])

    wardrobe_txt = _join(
        [
            wardrobe.get("description") or wardrobe.get("name") or "",
            wardrobe.get("colors") or "",
            wardrobe.get("footwear") or "",
            wardrobe.get("accessories") or "",
        ]
    )
    motion_txt = _join(
        [
            motion.get("defaultStandingPosture") or "",
            motion.get("walkingStyle") or "",
            motion.get("idleTendencies") or "",
            motion.get("handGestures") or "",
            motion.get("headMovement") or "",
            motion.get("energyLevel") or "",
        ]
    )
    emotion_txt = _join(
        [
            emotion.get("baseline") or "",
            emotion.get("sarcasmBehavior") or "",
            personality.get("humor") or "",
            personality.get("core_personality") or "",
        ]
    )
    performance_txt = _join(
        [
            performance.get("speakingCadence") or performance.get("speaking_rhythm") or "",
            performance.get("humorStyle") or "",
            performance.get("reactionTiming") or "",
            performance.get("eyeBehaviorWhileListening") or "",
            performance.get("silenceBehavior") or "",
            performance.get("emotionalEscalationStyle") or "",
        ]
    )
    mannerisms = performance.get("signatureMannerisms") or []
    if isinstance(mannerisms, list) and mannerisms:
        performance_txt = _join([performance_txt, "mannerisms: " + "; ".join(str(m) for m in mannerisms)])

    rel_summary = "; ".join(
        _rel_line(r) for r in relationships if isinstance(r, dict) and r.get("targetCharacter")
    )

    image_prompt = (
        f"{name}, {role}. Appearance: {appearance}. Wardrobe: {wardrobe_txt}. "
        f"Expression/posture: {motion.get('defaultStandingPosture') or 'natural'}. "
        "Photoreal cinematic character portrait, consistent identity."
    )
    video_prompt = (
        f"{name} in motion. {motion_txt}. Performance: {performance_txt}. "
        f"Emotional delivery: {emotion_txt}. Wardrobe: {wardrobe_txt}. Maintain identity: {appearance}."
    )
    storyboard_prompt = (
        f"Storyboard panels featuring {name} ({role}). Key identity: {appearance}. "
        f"Motion: {motion_txt}. Performance: {performance_txt}. Relationships: {rel_summary or 'n/a'}."
    )
    director_prompt = (
        f"Director 2.0 brief for {name}: personality={personality.get('core_personality') or emotion_txt}; "
        f"motion={motion_txt}; performance={performance_txt}; wardrobe={wardrobe_txt}; "
        f"relationships={rel_summary or 'n/a'}; do not invent traits outside locked features."
    )
    scenecraft_prompt = (
        f"SceneCraft blocking for {name}: energy={motion.get('energyLevel')}; "
        f"personalSpace={motion.get('personalSpace')}; signaturePoses={motion.get('signaturePoses')}; "
        f"idle={motion.get('idleTendencies')}; performanceCadence={performance.get('speakingCadence')}."
    )
    active_voice = profile.get("active_voice") or {}
    voice_prompt = (
        f"Voice for {name}: "
        f"design={active_voice.get('voice_design_prompt') or ''}; "
        f"age={active_voice.get('perceived_age') or ''}; "
        f"pitch={active_voice.get('pitch_description') or ''}; "
        f"pace={active_voice.get('pace_description') or performance.get('speakingCadence') or ''}; "
        f"tone={active_voice.get('tone_description') or ''}; "
        f"energy={active_voice.get('energy') or ''}; "
        f"humor={performance.get('humorStyle') or personality.get('humor') or ''}; "
        f"pauses={performance.get('thinkingPauses') or ''}; "
        f"interrupts={performance.get('interruptTendencies') or ''}; "
        f"silence={performance.get('silenceBehavior') or ''}; "
        f"baseline={emotion.get('baseline')}; sarcasm={emotion.get('sarcasmBehavior')}; "
        f"anger={emotion.get('angerBehavior')}; vulnerability={emotion.get('vulnerabilityBehavior')}; "
        f"provider={active_voice.get('provider') or ''}; mode={active_voice.get('source_mode') or ''}."
    )
    pronunciation_summary = active_voice.get("pronunciation_notes") or "; ".join(
        f"{p.get('word')}={p.get('phonetic')}"
        for p in (active_voice.get("pronunciations") or [])
        if isinstance(p, dict) and p.get("word")
    )
    reaction_summary = ", ".join(
        r.get("label") or r.get("id") or ""
        for r in (active_voice.get("reactions") or [])
        if isinstance(r, dict) and r.get("status") == "ready"
    )
    motion_prompt = (
        f"Motion profile for {name}: stand={motion.get('defaultStandingPosture')}; "
        f"walk={motion.get('walkingStyle')}; run={motion.get('runningStyle')}; "
        f"idle={motion.get('idleTendencies')}; hands={motion.get('handGestures')}; "
        f"head={motion.get('headMovement')}; eyeContact={motion.get('eyeContactBehavior')}; "
        f"combat={motion.get('combatStance')}; sit={motion.get('sittingPosture')}."
    )
    performance_prompt = (
        f"Performance Bible for {name}: cadence={performance.get('speakingCadence')}; "
        f"interrupts={performance.get('interruptTendencies')}; pauses={performance.get('thinkingPauses')}; "
        f"smile={performance.get('smileFrequency')}; listenEyes={performance.get('eyeBehaviorWhileListening')}; "
        f"facialTension={performance.get('defaultFacialTension')}; "
        f"escalation={performance.get('emotionalEscalationStyle')}; humor={performance.get('humorStyle')}; "
        f"reactionTiming={performance.get('reactionTiming')}; silence={performance.get('silenceBehavior')}; "
        f"improvBounds={performance.get('improvisationBoundaries')}; "
        f"mannerisms={mannerisms}."
    )
    reference_summary = (
        f"{name} | {role} | appearance=[{appearance}] | wardrobe=[{wardrobe_txt}] | "
        f"motion=[{motion_txt}] | performance=[{performance_txt}] | emotion=[{emotion_txt}] | "
        f"relationships=[{rel_summary}] | forbidInvention={continuity.get('forbid_invention')}"
    )

    return {
        "schema_version": 1,
        "character_version_id": character_version_id or profile.get("active_version_id") or "",
        "generated_at": _now(),
        "canon_version": profile.get("canon_version") or "",
        "imagePrompt": image_prompt,
        "videoPrompt": video_prompt,
        "storyboardPrompt": storyboard_prompt,
        "director20Prompt": director_prompt,
        "sceneCraftPrompt": scenecraft_prompt,
        "voicePrompt": voice_prompt,
        "motionPrompt": motion_prompt,
        "performancePrompt": performance_prompt,
        "pronunciationSummary": pronunciation_summary,
        "reactionSummary": reaction_summary,
        "providerTranslationHints": (
            f"mode={active_voice.get('source_mode')}; model={active_voice.get('model_id')}; "
            f"use approved voiceProfileId={active_voice.get('id') or ''} — do not invent voice traits."
        ),
        "referenceSummary": reference_summary,
    }
