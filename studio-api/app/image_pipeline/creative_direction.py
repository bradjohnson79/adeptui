"""Deterministic creative direction packets for creator-facing planning."""

from __future__ import annotations

from .contracts import CreativeDirectionPacket, ImageShotIntent


def _scene_class(shot_intent: ImageShotIntent) -> str:
    if shot_intent.wantsReveal:
        return "reveal"
    if shot_intent.wantsSuspense:
        return "suspense"
    if shot_intent.wantsComedy:
        return "comedy"
    if shot_intent.wantsIntimacy:
        return "intimacy"
    if shot_intent.wantsAction:
        return "action"
    if shot_intent.wantsHorror:
        return "horror"
    if shot_intent.wantsEstablishing or shot_intent.shotSize == "wide":
        return "establishing"
    return "observational"


def _composition_for(shot_intent: ImageShotIntent, scene_class: str) -> str:
    if shot_intent.subjectCount >= 3:
        return "Layer the figures clearly so each character reads at a glance."
    if scene_class == "reveal":
        return "Hide the key detail until the eye naturally lands on it."
    if scene_class == "suspense":
        return "Use negative space and off-balance framing to build anticipation."
    if scene_class == "intimacy":
        return "Keep the frame close and emotionally centered on the subject."
    return "Compose for clarity first, then atmosphere."


def _lens_for(shot_intent: ImageShotIntent, scene_class: str) -> str:
    if shot_intent.shotSize == "wide":
        return "24mm"
    if shot_intent.shotSize == "close_up":
        return "85mm"
    if scene_class == "action":
        return "35mm"
    return "50mm"


def build_creative_direction(
    prompt: str,
    shot_intent: ImageShotIntent,
    style_profile_id: str | None = None,
) -> CreativeDirectionPacket:
    scene_class = _scene_class(shot_intent)
    mood_map = {
        "reveal": "anticipatory",
        "suspense": "tense",
        "comedy": "playful",
        "intimacy": "tender",
        "action": "urgent",
        "horror": "unnerving",
        "establishing": "immersive",
        "observational": "grounded",
        "other": "grounded",
    }
    lighting_map = {
        "reveal": "shape the frame so the key detail emerges with intention",
        "suspense": "low-key lighting with controlled shadow pockets",
        "comedy": "bright readable lighting that keeps expressions clear",
        "intimacy": "soft flattering light close to the subject",
        "action": "directional light with crisp highlights and motion energy",
        "horror": "uneasy contrast with darkness that feels alive",
        "establishing": "broad readable lighting that explains the space",
        "observational": "naturalistic lighting with believable source motivation",
        "other": "naturalistic lighting with believable source motivation",
    }
    color_map = {
        "reveal": "controlled palette with one accent color guiding the eye",
        "suspense": "cool restrained palette with pockets of danger",
        "comedy": "friendly balanced color contrast",
        "intimacy": "warm skin-forward palette",
        "action": "high-contrast palette with bold separation",
        "horror": "sickly or desaturated tones that heighten unease",
        "establishing": "palette that clearly identifies time, place, and tone",
        "observational": "honest grounded color",
        "other": "honest grounded color",
    }
    camera_height = "eye level"
    if scene_class in {"horror", "suspense"}:
        camera_height = "slightly low"
    elif scene_class == "intimacy":
        camera_height = "gentle eye level"

    movement = "keep the frame steady"
    if scene_class == "action":
        movement = "suggest a camera that can track or react with the movement"
    elif scene_class == "reveal":
        movement = "let the framing guide the audience toward the reveal"

    packet = CreativeDirectionPacket(
        scenePurpose=f"Create a {scene_class.replace('_', ' ')} image for {prompt.strip() or 'the requested moment'}.",
        audienceFocus=[
            "who the scene is about",
            "what emotional beat matters most",
            "what should be noticed first",
        ],
        composition=_composition_for(shot_intent, scene_class),
        lens=_lens_for(shot_intent, scene_class),
        cameraHeight=camera_height,
        mood=mood_map.get(scene_class, "grounded"),
        lighting=lighting_map.get(scene_class, lighting_map["observational"]),
        color=color_map.get(scene_class, color_map["observational"]),
        movementSuggestion=movement,
        visualPriority="Prioritize readable storytelling over decorative detail.",
        cameraStance="participatory" if scene_class in {"action", "intimacy"} else "observational",
        lightingEmotion=mood_map.get(scene_class, "grounded"),
        scenePurposeClass=scene_class,  # type: ignore[arg-type]
        symmetry="asymmetrical" if scene_class in {"suspense", "action", "horror"} else "mixed",
        visualLanguageProfileId=style_profile_id,
    )
    packet.creatorSummary = creator_summary(packet)
    return packet


def creator_summary(packet: CreativeDirectionPacket) -> str:
    return (
        f"{packet.scenePurposeClass.replace('_', ' ').title()} tone, {packet.lens} framing, "
        f"{packet.lightingEmotion} mood, and a composition that keeps the audience focused on the story beat."
    )

