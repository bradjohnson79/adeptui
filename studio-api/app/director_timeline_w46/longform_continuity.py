"""Compile LongFormContinuityState from existing authorities. Not a second brain."""

from __future__ import annotations

from typing import Any

from ..codirector.video_intelligence.media_packet import MediaIntelligencePacket
from ..codirector.video_intelligence.contracts import TemporalContinuityPacket
from .contracts import (
    LongFormCharacterState,
    LongFormContinuityState,
    LongFormPropState,
    SceneTimelineMaster,
)


def select_h3_mode(*, multi_character: bool, has_ers: bool, identity_risk: bool) -> str:
    """I2V when last-frame is enough; R2V when recurring identity/environment matter."""

    if multi_character or has_ers or identity_risk:
        return "r2v"
    return "i2v"


def compile_longform_continuity(
    *,
    project_id: str,
    scene_id: str,
    master: SceneTimelineMaster | None,
    media_packet: MediaIntelligencePacket | None,
    temporal: TemporalContinuityPacket | None,
    next_intent: str = "",
    reference_bindings: list[dict[str, Any]] | None = None,
) -> LongFormContinuityState:
    prior = master.longFormContinuity if master and master.longFormContinuity else None
    revision = int(prior.revision) + 1 if prior else 1
    bindings = reference_bindings or []

    characters: list[LongFormCharacterState] = []
    if media_packet:
        for action in media_packet.characterActions:
            characters.append(
                LongFormCharacterState(
                    characterId=action.characterId,
                    label=action.characterLabel,
                    poseAction=action.action,
                    position=action.movementDirection or "",
                )
            )
    if temporal:
        for obs in temporal.characters:
            if any((c.characterId and c.characterId == obs.characterId) or (c.label and c.label == obs.label) for c in characters):
                continue
            characters.append(
                LongFormCharacterState(
                    characterId=obs.characterId,
                    label=obs.label,
                    appearanceState=obs.expression or "",
                    poseAction=obs.poseState or obs.actionState or "",
                    position=obs.screenPosition or "",
                )
            )
    for bind in bindings:
        kind = str(bind.get("kind") or bind.get("type") or "").lower()
        if kind in ("character", "crs") and bind.get("assetId"):
            label = str(bind.get("name") or bind.get("label") or "")
            match = next((c for c in characters if c.label.lower() == label.lower()), None)
            if match:
                match.crsAssetId = str(bind.get("assetId"))
                if bind.get("characterId"):
                    match.characterId = str(bind.get("characterId"))
            else:
                characters.append(
                    LongFormCharacterState(
                        characterId=str(bind.get("characterId") or "") or None,
                        crsAssetId=str(bind.get("assetId")),
                        label=label,
                    )
                )

    environment = {
        "ersAssetId": next((str(b.get("assetId")) for b in bindings if str(b.get("kind") or "").lower() in ("environment", "ers")), None),
        "locationState": (temporal.scene.environmentState if temporal else "") or "",
        "lightingState": (temporal.scene.lightingState if temporal else "") or "",
    }
    props = [
        LongFormPropState(
            prsAssetId=str(b.get("assetId")) if b.get("assetId") else None,
            label=str(b.get("name") or b.get("label") or ""),
        )
        for b in bindings
        if str(b.get("kind") or "").lower() in ("prop", "prs")
    ]
    camera = {}
    if temporal:
        camera = {
            "framing": temporal.camera.framing,
            "movement": temporal.camera.movementType,
            "direction": temporal.camera.movementDirection,
            "shotType": temporal.camera.shotSize,
        }
    dialogue = {}
    if media_packet and media_packet.speechSegments:
        last = media_packet.speechSegments[-1]
        dialogue = {
            "lastSpeaker": last.speaker,
            "currentSpeechState": "speaking" if (last.transcription and not last.isSilence) else "idle",
            "unfinishedLine": last.transcription if last.transcription and not last.isSilence else "",
        }
    audio = {
        "ambience": [e.ambienceType for e in (media_packet.environmentEvents if media_packet else [])],
        "activeMusic": [m.role for m in (media_packet.musicOpportunities if media_packet else [])],
    }
    story = ""
    if temporal and temporal.exitState and temporal.exitState.summary:
        # REBUILD LAW (Qwen observation-only): storyState is prompt-facing
        # state ("Continue: …" reaches persisted batch prompt segments via
        # extend_service._compile_segment_prompt). It may only come from the
        # TemporalContinuityPacket lane, which passes
        # reconcile_packet_with_authority before persistence. The raw
        # MediaIntelligencePacket.summary is unreviewed Qwen Omni prose and
        # must never be inserted directly into a generation prompt.
        story = temporal.exitState.summary

    return LongFormContinuityState(
        revision=revision,
        projectId=project_id,
        sceneId=scene_id,
        mediaIntelligencePacketId=media_packet.packetId if media_packet else None,
        temporalPacketId=temporal.packetId if temporal else None,
        characters=characters,
        environment=environment,
        props=props,
        camera=camera,
        motion={"events": [e.motionType for e in (media_packet.motionEvents if media_packet else [])]},
        dialogue=dialogue,
        audio=audio,
        endingAnchors=list((prior.endingAnchors if prior else [])),
        storyState=story,
        nextIntent=next_intent,
        scores={},
        stale=False,
    )


def mark_downstream_stale(master: SceneTimelineMaster, *, from_segment_id: str) -> SceneTimelineMaster:
    """Chapter 28 — replacing an earlier segment invalidates later continuity."""

    if master.longFormContinuity:
        master.longFormContinuity.stale = True
        master.longFormContinuity.staleFromSegmentId = from_segment_id
    found = False
    for seg in master.extendSegments:
        if seg.segmentId == from_segment_id:
            found = True
            continue
        if found:
            seg.status = "planned" if seg.status != "cancelled" else seg.status
    for batch in master.batchBlocks:
        if found:
            batch.downstreamStale = True
    return master
