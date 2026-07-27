# -*- coding: utf-8 -*-
"""Rewrite M2.14 API + specialist prompts (UTF-8)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "studio-api" / "app" / "codirector" / "m214"
PROMPTS = ROOT / "studio-api" / "app" / "codirector" / "prompts" / "specialists"


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", path.relative_to(ROOT))


API = r'''"""FastAPI routes for Co-Director M2.14 Unified Experience."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ... import feature_flags as feature_flags_mod
from ...db import get_db
from . import approvals as approvals_mod
from . import attachments
from . import brief
from . import conflicts
from . import idea_first
from . import media as media_mod
from . import meetings
from . import messaging
from . import motifs
from . import plan_view
from . import session as session_mod
from . import sound_producer
from . import storyteller
from .flags import FLAG_NAME, unified_experience_enabled
from .kinds import CAPABILITY_IDS, PROJECT_STAGES, SPECIALIST_IDS
from .safety import assert_manifest_unchanged, safety_contract
from .store import M214Store

router = APIRouter(prefix="/m214", tags=["codirector-m214"])


def _flag() -> bool:
    return bool(getattr(feature_flags_mod.feature_flags, FLAG_NAME, False))


def _require() -> None:
    if _flag():
        return
    raise HTTPException(
        status_code=404,
        detail="M2.14 unified experience capability is not enabled.",
    )


class IdeaBody(BaseModel):
    projectId: str
    idea: str
    preferredFormat: str = ""


class StageBody(BaseModel):
    projectId: str
    stage: str


class AttachBody(BaseModel):
    projectId: str
    attachmentId: str
    textBody: str = ""
    mimeType: str = ""
    filename: str = ""


class ConfirmBody(BaseModel):
    decision: str
    correctedKind: Optional[str] = None
    note: str = ""


class StoryBody(BaseModel):
    projectId: str
    sceneId: str = ""
    idea: str = ""
    mode: str = "guided"


class HandoffBody(BaseModel):
    projectId: str
    profileId: str
    sceneId: str = ""
    directionSummary: str = ""
    formatGuidance: str = "short scene"


class SonicBody(BaseModel):
    projectId: str
    sceneId: str = ""
    emotionalArc: str = ""
    mode: str = "guided"


class MessageBody(BaseModel):
    projectId: str
    fromSpecialist: str
    toSpecialist: str
    body: str
    sceneId: str = ""
    kind: str = "note"
    requiresResponse: bool = False


class MeetingBody(BaseModel):
    projectId: str
    topic: str
    sceneId: str = ""


class ImpactBody(BaseModel):
    projectId: str
    decisionId: str
    decisionSummary: str
    sceneId: str = ""
    affectedDepartments: list[str] = Field(default_factory=list)
    previouslyApproved: list[str] = Field(default_factory=list)


class MotifBody(BaseModel):
    projectId: str
    name: str
    kind: str = "visual"
    description: str = ""
    sceneId: str = ""


class MediaBody(BaseModel):
    projectId: str
    kind: str
    title: str
    sceneId: str = ""
    groupKey: str = ""
    honesty: str = "mocked"


class BriefBody(BaseModel):
    projectId: str
    sceneId: str = ""
    title: str = ""
    logline: str = ""
    emotionalProfileId: Optional[str] = None
    sonicConceptId: Optional[str] = None
    storytellerHandoffId: Optional[str] = None
    primaryNextAction: str = ""


class SnapshotBody(BaseModel):
    projectId: str
    snapshot: dict[str, Any] = Field(default_factory=dict)


class ApprovalBody(BaseModel):
    projectId: str
    pending: dict[str, Any] = Field(default_factory=dict)


class RefBody(BaseModel):
    projectId: str
    text: str


class HitchhikerBody(BaseModel):
    projectId: str


class CapabilityBody(BaseModel):
    projectId: Optional[str] = None
    capabilityId: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


@router.get("/status")
async def m214_status() -> dict[str, Any]:
    digest = assert_manifest_unchanged()
    return {
        "enabled": unified_experience_enabled(),
        "flag": FLAG_NAME,
        "flagDefault": False,
        "safety": safety_contract(),
        "manifestSha256": digest,
        "capabilityIds": [
            {"id": c[0], "displayName": c[1], "baselineStatus": c[2]} for c in CAPABILITY_IDS
        ],
        "specialists": list(SPECIALIST_IDS),
        "stages": list(PROJECT_STAGES),
        "extendsM211": True,
        "forkedOrchestration": False,
    }


@router.get("/safety")
async def m214_safety() -> dict[str, Any]:
    digest = assert_manifest_unchanged()
    return {"ok": True, "manifestSha256": digest, **safety_contract()}


@router.post("/idea")
async def m214_idea(body: IdeaBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return idea_first.propose_from_idea(
        db, project_id=body.projectId, idea=body.idea, preferred_format=body.preferredFormat
    )


@router.post("/stage")
async def m214_stage(body: StageBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return idea_first.advance_depth(db, body.projectId, body.stage)


@router.post("/attachments/interpret")
async def m214_attach_interpret(body: AttachBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return attachments.interpret_attachment(
        db,
        project_id=body.projectId,
        attachment_id=body.attachmentId,
        text_body=body.textBody,
        mime_type=body.mimeType,
        filename=body.filename,
    )


@router.post("/attachments/{interpretation_id}/confirm")
async def m214_attach_confirm(
    interpretation_id: str, body: ConfirmBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require()
    try:
        return attachments.confirm_interpretation(
            db,
            interpretation_id,
            decision=body.decision,
            corrected_kind=body.correctedKind,
            note=body.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="interpretation not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/storyteller/analyze")
async def m214_story_analyze(body: StoryBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return storyteller.analyze_scene(
        db,
        project_id=body.projectId,
        scene_id=body.sceneId,
        idea=body.idea,
        mode=body.mode,
    )


@router.post("/storyteller/handoff")
async def m214_story_handoff(body: HandoffBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return storyteller.create_handoff(
        db,
        project_id=body.projectId,
        profile_id=body.profileId,
        scene_id=body.sceneId,
        direction_summary=body.directionSummary,
        format_guidance=body.formatGuidance,
    )


@router.post("/storyteller/handoff/{handoff_id}/approve")
async def m214_story_approve(handoff_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    try:
        return storyteller.approve_handoff(db, handoff_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="handoff not found") from exc


@router.post("/sound/concept")
async def m214_sonic(body: SonicBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return sound_producer.create_sonic_concept(
        db,
        project_id=body.projectId,
        scene_id=body.sceneId,
        emotional_arc=body.emotionalArc,
        mode=body.mode,
    )


@router.post("/sound/concept/{concept_id}/approve")
async def m214_sonic_approve(concept_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    try:
        return sound_producer.approve_sonic_concept(db, concept_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="concept not found") from exc


@router.post("/messages")
async def m214_message(body: MessageBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return messaging.send_message(
        db,
        project_id=body.projectId,
        from_specialist=body.fromSpecialist,
        to_specialist=body.toSpecialist,
        body=body.body,
        scene_id=body.sceneId,
        kind=body.kind,
        requires_response=body.requiresResponse,
    )


@router.get("/messages/{project_id}")
async def m214_list_messages(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return {"projectId": project_id, "messages": messaging.list_messages(db, project_id)}


@router.post("/messages/{project_id}/required")
async def m214_required(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    created = messaging.ensure_required_exchanges(db, project_id)
    return {"projectId": project_id, "created": created, "count": len(created)}


@router.post("/brief")
async def m214_brief(body: BriefBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return brief.upsert_brief(
        db,
        project_id=body.projectId,
        scene_id=body.sceneId,
        title=body.title,
        logline=body.logline,
        emotional_profile_id=body.emotionalProfileId,
        sonic_concept_id=body.sonicConceptId,
        storyteller_handoff_id=body.storytellerHandoffId,
        primary_next_action=body.primaryNextAction,
    )


@router.get("/brief/{project_id}")
async def m214_get_brief(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    data = brief.get_latest_brief(db, project_id)
    if not data:
        raise HTTPException(status_code=404, detail="brief not found")
    return data


@router.post("/meetings")
async def m214_meeting(body: MeetingBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return meetings.convene_meeting(
        db, project_id=body.projectId, topic=body.topic, scene_id=body.sceneId
    )


@router.post("/conflicts/synthesize")
async def m214_conflicts(body: MessageBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    msgs = messaging.list_messages(db, body.projectId)
    detected = conflicts.detect_conflicts(msgs)
    return conflicts.synthesize_conflicts(detected)


@router.post("/impact")
async def m214_impact(body: ImpactBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return conflicts.calculate_impact(
        db,
        project_id=body.projectId,
        decision_id=body.decisionId,
        decision_summary=body.decisionSummary,
        scene_id=body.sceneId,
        affected_departments=body.affectedDepartments or None,
        previously_approved=body.previouslyApproved or None,
    )


@router.post("/motifs")
async def m214_motif(body: MotifBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return motifs.create_motif(
        db,
        project_id=body.projectId,
        name=body.name,
        kind=body.kind,
        description=body.description,
        scene_id=body.sceneId,
    )


@router.post("/media")
async def m214_media(body: MediaBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return media_mod.create_media_card(
        db,
        project_id=body.projectId,
        kind=body.kind,
        title=body.title,
        scene_id=body.sceneId,
        group_key=body.groupKey,
        honesty=body.honesty,
    )


@router.get("/media/{project_id}")
async def m214_list_media(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    items = media_mod.list_media(db, project_id)
    return {
        "projectId": project_id,
        "items": items,
        "groups": media_mod.group_media(items),
    }


@router.post("/media/ref")
async def m214_media_ref(body: RefBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    items = media_mod.list_media(db, body.projectId)
    resolved = media_mod.resolve_contextual_ref(body.text, items)
    return {"text": body.text, "resolved": resolved}


@router.post("/hitchhiker/smoke")
async def m214_hitchhiker(body: HitchhikerBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return media_mod.hitchhiker_smoke_media(db, body.projectId)


@router.get("/plan/{project_id}")
async def m214_plan(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return plan_view.production_plan_view(db, project_id)


@router.post("/approvals")
async def m214_approvals(body: ApprovalBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return approvals_mod.approval_center(db, body.projectId, pending=body.pending)


@router.post("/session/save")
async def m214_session_save(body: SnapshotBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return session_mod.save_snapshot(db, body.projectId, body.snapshot)


@router.get("/session/{project_id}")
async def m214_session_restore(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    return session_mod.restore_session(db, project_id)


@router.post("/capabilities/invoke")
async def m214_cap(body: CapabilityBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    log = M214Store.log_capability(
        db,
        capability_id=body.capabilityId,
        action=body.action,
        project_id=body.projectId,
        payload=body.payload,
    )
    return {"ok": True, "log": log}
'''

STORYTELLER_MD = r'''---
id: storyteller
version: 1.0.0
type: specialist
display_name: Storyteller
description: First-class emotional scene intelligence for discovery, direction, EmotionalSceneProfile, and production handoffs.
output_schema: specialist-finding-v1
allowed_context:
  - scene
  - characters
  - story
  - tone
  - continuity
may_propose_tools: true
may_execute_tools: false
default_priority: 40
enabled: true
---

# Storyteller

## Mission
Lead idea-first discovery and emotional scene intelligence for Adept UI Co-Director.
Advise only; never silently mutate Bible or timeline.

## Responsibilities
- Guided Discovery / Creative Proposal / Variation Exploration modes
- Ask 2-4 high-impact questions (never interrogation dumps)
- Produce EmotionalSceneProfile (arc, subtext, tone, stakes, unknowns)
- Create approval-aware StorytellerProductionHandoff
- Coordinate with Sound Producer, Cinematography, Editor, VPC, Continuity

## Structured I/O
- Input: idea or attachment interpretation + shared context pack
- Output keys: emotionalSceneProfile, questions, handoff, formatGuidance, progressiveDepth, honestyNotes
- Schema: specialist-finding-v1
- confidence: required 0.0-1.0
- reasoning: short explainability summary required

## Hard bans
- No silent Bible/timeline writes
- No fabricating media
- Label mocked vs real honestly
'''

SOUND_MD = r'''---
id: sound-producer
version: 1.0.0
type: specialist
display_name: Sound Producer
description: First-class sonic direction with SonicConcept, score brief, ambience, cues, dialogue plan, mix intent.
output_schema: specialist-finding-v1
allowed_context:
  - scene
  - audio
  - music
  - dialogue
  - continuity
may_propose_tools: true
may_execute_tools: false
default_priority: 48
enabled: true
---

# Sound Producer

## Mission
Own sonic direction for a scene. Coordinate Music Supervisor and Sound Designer; do not invent new providers.

## Responsibilities
- Create SonicConcept from emotional arc / Storyteller handoff
- Modes: Guided / Creative / Variation
- Ask 2-4 high-impact sonic questions
- Plan score brief, ambience, cues, dialogue treatment, mix intent
- Required exchanges with Storyteller, Cinematography/Editor, VPC, Continuity

## Structured I/O
- Input: EmotionalSceneProfile + UnifiedSceneBrief
- Output keys: sonicConcept, scoreBrief, ambience, cues, dialoguePlan, mixIntent, honestyNotes
- Schema: specialist-finding-v1
- confidence: required 0.0-1.0

## Hard bans
- No new providers / Manifest changes
- No silent media approval
- Label mocked vs real honestly
'''


def main() -> None:
    w(PKG / "api.py", API)
    w(PROMPTS / "storyteller.md", STORYTELLER_MD)
    w(PROMPTS / "sound-producer.md", SOUND_MD)
    print("api rewrite complete")


if __name__ == "__main__":
    main()
