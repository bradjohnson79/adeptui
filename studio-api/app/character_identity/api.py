"""HTTP API for Character Identity (M3.3)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import Project, get_db
from .. import feature_flags as feature_flags_mod
from . import service
from .schemas import (
    CharacterProfileCreate,
    CharacterProfileUpdate,
    DialogueGenerateRequest,
    PropCreate,
    ReferenceAttach,
    TraitUpsert,
    VoiceConsentCreate,
    VoiceProfileCreate,
    WardrobeCreate,
)
from .voice import provider_readiness, validate_voice_reference

router = APIRouter(tags=["character-identity"])


def _require_flag() -> None:
    # Read via module attribute — lifespan/e2e may replace the singleton object.
    if not feature_flags_mod.feature_flags.character_identity_v1:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "FEATURE_DISABLED",
                "message": "Character Identity (M3.3) is disabled. Set STUDIO_FEATURE_CHARACTER_IDENTITY_V1=1.",
            },
        )


def _project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Project not found."})
    return project


@router.get("/projects/{project_id}/characters")
def list_characters(project_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return {"items": [p.model_dump() for p in service.list_profiles(db, project_id)]}


@router.post("/projects/{project_id}/characters")
def create_character(project_id: str, body: CharacterProfileCreate, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return service.create_profile(db, project_id, body).model_dump()


@router.get("/projects/{project_id}/characters/{character_id}")
def get_character(project_id: str, character_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return service.get_profile(db, project_id, character_id).model_dump()


@router.patch("/projects/{project_id}/characters/{character_id}")
def patch_character(
    project_id: str, character_id: str, body: CharacterProfileUpdate, db: Session = Depends(get_db)
):
    _require_flag()
    _project(db, project_id)
    return service.update_profile(db, project_id, character_id, body).model_dump()


@router.get("/projects/{project_id}/characters/{character_id}/versions")
def versions(project_id: str, character_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return {"items": service.list_versions(db, project_id, character_id)}


@router.post("/projects/{project_id}/characters/{character_id}/versions/{version_id}/approve")
def approve_version(project_id: str, character_id: str, version_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return service.approve_version(db, project_id, character_id, version_id)


@router.post("/projects/{project_id}/characters/{character_id}/versions/{version_id}/lock")
def lock_version(project_id: str, character_id: str, version_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return service.lock_version(db, project_id, character_id, version_id)


@router.get("/projects/{project_id}/characters/{character_id}/references")
def references(project_id: str, character_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return {"items": service.list_references(db, project_id, character_id)}


@router.post("/projects/{project_id}/characters/{character_id}/references")
def attach_reference(project_id: str, character_id: str, body: ReferenceAttach, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return service.attach_reference(db, project_id, character_id, body)


class ApproveCandidateBody(BaseModel):
    assetId: str
    referenceRole: str = "hero_portrait"
    sourceType: str = "generation"
    notes: str = "Approved casting candidate"


@router.post("/projects/{project_id}/characters/{character_id}/approve-candidate")
def approve_candidate(
    project_id: str, character_id: str, body: ApproveCandidateBody, db: Session = Depends(get_db)
):
    """Mark a generated candidate as the canonical approved casting image."""
    _require_flag()
    _project(db, project_id)
    return service.approve_character_candidate(
        db,
        project_id,
        character_id,
        asset_id=body.assetId,
        reference_role=body.referenceRole,
        source_type=body.sourceType,
        notes=body.notes,
    )


@router.get("/projects/{project_id}/characters/{character_id}/coverage")
def coverage(project_id: str, character_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return service.coverage(db, project_id, character_id).model_dump()


@router.get("/projects/{project_id}/characters/{character_id}/wardrobes")
def wardrobes(project_id: str, character_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return {"items": service.list_wardrobes(db, project_id, character_id)}


@router.post("/projects/{project_id}/characters/{character_id}/wardrobes")
def create_wardrobe(project_id: str, character_id: str, body: WardrobeCreate, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return service.create_wardrobe(db, project_id, character_id, body)


@router.get("/projects/{project_id}/characters/{character_id}/props")
def props(project_id: str, character_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return {"items": service.list_props(db, project_id, character_id)}


@router.post("/projects/{project_id}/characters/{character_id}/props")
def create_prop(project_id: str, character_id: str, body: PropCreate, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return service.create_prop(db, project_id, character_id, body)


@router.post("/projects/{project_id}/characters/{character_id}/traits")
def upsert_trait(project_id: str, character_id: str, body: TraitUpsert, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return service.upsert_trait(db, project_id, character_id, body)


@router.get("/projects/{project_id}/characters/{character_id}/voice-profiles")
def voice_profiles(project_id: str, character_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return {"items": service.list_voice_profiles(db, project_id, character_id)}


@router.post("/projects/{project_id}/characters/{character_id}/voice-profiles")
def create_voice(project_id: str, character_id: str, body: VoiceProfileCreate, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return service.create_voice_profile(db, project_id, character_id, body)


@router.post("/projects/{project_id}/characters/{character_id}/voice-profiles/{voice_id}/consent")
def voice_consent(
    project_id: str,
    character_id: str,
    voice_id: str,
    body: VoiceConsentCreate,
    db: Session = Depends(get_db),
):
    _require_flag()
    _project(db, project_id)
    return service.record_consent(db, project_id, character_id, voice_id, body)


@router.post("/projects/{project_id}/characters/{character_id}/voice-profiles/{voice_id}/approve")
def approve_voice(project_id: str, character_id: str, voice_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    return service.approve_voice_profile(db, project_id, character_id, voice_id)


class ValidateReferenceBody(BaseModel):
    path: str
    transcript: str = ""


@router.post("/projects/{project_id}/characters/{character_id}/voice-profiles/validate-reference")
def validate_reference(
    project_id: str, character_id: str, body: ValidateReferenceBody, db: Session = Depends(get_db)
):
    _require_flag()
    _project(db, project_id)
    service.get_profile(db, project_id, character_id)
    return validate_voice_reference(body.path, transcript=body.transcript)


@router.get("/projects/{project_id}/characters/{character_id}/prompt-hints")
def prompt_hints(
    project_id: str,
    character_id: str,
    shotKind: str = "closeup_front",
    db: Session = Depends(get_db),
):
    _require_flag()
    _project(db, project_id)
    return service.prompt_hints(db, project_id, character_id, shot_kind=shotKind)


@router.get("/character-voice/providers")
def character_voice_providers():
    _require_flag()
    return provider_readiness()


class DesignVoiceBody(BaseModel):
    name: str = "Designed voice"
    voice_design_prompt: str
    test_line: str = "Hello, this is a character voice preview."
    candidate_count: int = Field(default=3, ge=1, le=6)
    language: str = "en"


@router.post("/projects/{project_id}/characters/{character_id}/voice-profiles/design")
def design_voice(project_id: str, character_id: str, body: DesignVoiceBody, db: Session = Depends(get_db)):
    """Queue voice-design candidates via Qwen when installed; honest error otherwise."""
    _require_flag()
    _project(db, project_id)
    from .voice_runtime import run_voice_design

    return run_voice_design(db, project_id, character_id, body)


# --- Voice Creator workspace ---


@router.get("/projects/{project_id}/characters/{character_id}/voice")
def get_voice_workspace(project_id: str, character_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import get_voice_workspace as _ws

    return _ws(db, project_id, character_id)


class VoiceDesignPreviewBody(BaseModel):
    designBrief: Optional[dict[str, Any]] = None


@router.post("/projects/{project_id}/characters/{character_id}/voice/design/preview")
def voice_design_preview(project_id: str, character_id: str, body: VoiceDesignPreviewBody, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import preview_voice_design

    return preview_voice_design(db, project_id, character_id, brief=body.designBrief)


class VoiceDesignGenerateBody(BaseModel):
    designBrief: Optional[dict[str, Any]] = None
    candidateCount: int = Field(default=3, ge=1, le=6)
    testLine: Optional[str] = None
    name: Optional[str] = None
    masterPrompt: Optional[str] = None
    promptDocument: Optional[dict[str, Any]] = None
    method: str = "design"
    parentCandidateId: Optional[str] = None
    appendToVoiceId: Optional[str] = None


@router.post("/projects/{project_id}/characters/{character_id}/voice/design/generate")
def voice_design_generate(project_id: str, character_id: str, body: VoiceDesignGenerateBody, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import generate_voice_candidates

    return generate_voice_candidates(
        db,
        project_id,
        character_id,
        brief=body.designBrief,
        candidate_count=body.candidateCount,
        test_line=body.testLine,
        name=body.name,
        master_prompt=body.masterPrompt,
        prompt_document=body.promptDocument,
        method=body.method,
        parent_candidate_id=body.parentCandidateId,
        append_to_voice_id=body.appendToVoiceId,
    )


class VoiceStudioDraftBody(BaseModel):
    phase: Optional[str] = None
    method: Optional[str] = None
    testingVoiceProfileId: Optional[str] = None
    testingCandidateId: Optional[str] = None
    selectedVoiceProfileId: Optional[str] = None
    selectedCandidateId: Optional[str] = None
    dialogue: Optional[str] = None
    mood: Optional[str] = None
    delivery: Optional[dict[str, Any]] = None
    selectedTakeId: Optional[str] = None
    planId: Optional[str] = None
    masterPrompt: Optional[str] = None
    designBrief: Optional[dict[str, Any]] = None
    promptDocument: Optional[dict[str, Any]] = None
    sampleLineId: Optional[str] = None
    customSampleLine: Optional[str] = None
    performancePrompt: Optional[str] = None
    latestBatchId: Optional[str] = None
    uploadKind: Optional[str] = None
    uploadAssetId: Optional[str] = None


@router.put("/projects/{project_id}/characters/{character_id}/voice/studio-draft")
def voice_studio_draft_put(project_id: str, character_id: str, body: VoiceStudioDraftBody, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import save_voice_studio_draft

    return save_voice_studio_draft(db, project_id, character_id, body.model_dump(exclude_none=True))


class VoiceSelectTestingBody(BaseModel):
    voiceId: str
    candidateId: str


@router.post("/projects/{project_id}/characters/{character_id}/voice/select-testing")
def voice_select_testing(project_id: str, character_id: str, body: VoiceSelectTestingBody, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import select_testing_candidate

    return select_testing_candidate(
        db, project_id, character_id, voice_id=body.voiceId, candidate_id=body.candidateId
    )


class VoiceRetryCandidateBody(BaseModel):
    voiceId: str
    testLine: Optional[str] = None


@router.post("/projects/{project_id}/characters/{character_id}/voice/candidates/{candidate_id}/retry")
def voice_retry_candidate(
    project_id: str,
    character_id: str,
    candidate_id: str,
    body: VoiceRetryCandidateBody,
    db: Session = Depends(get_db),
):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import retry_failed_candidate

    return retry_failed_candidate(
        db, project_id, character_id, body.voiceId, candidate_id, test_line=body.testLine
    )


class VoiceUploadRegisterBody(BaseModel):
    assetId: str
    uploadKind: str
    name: Optional[str] = None
    consentConfirmed: bool = False


@router.post("/projects/{project_id}/characters/{character_id}/voice/upload/register")
def voice_upload_register(project_id: str, character_id: str, body: VoiceUploadRegisterBody, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import register_upload_voice

    return register_upload_voice(
        db,
        project_id,
        character_id,
        asset_id=body.assetId,
        upload_kind=body.uploadKind,
        name=body.name,
        consent_confirmed=body.consentConfirmed,
    )


@router.get("/projects/{project_id}/characters/{character_id}/voice/candidates")
def voice_candidates(project_id: str, character_id: str, voiceId: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import list_candidates

    return list_candidates(db, project_id, character_id, voiceId)


class CandidateActionBody(BaseModel):
    notes: str = ""
    refinement: str = ""


@router.post("/projects/{project_id}/characters/{character_id}/voice/candidates/{candidate_id}/{action}")
def voice_candidate_action(
    project_id: str,
    character_id: str,
    candidate_id: str,
    action: str,
    voiceId: str,
    body: CandidateActionBody | None = None,
    db: Session = Depends(get_db),
):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import approve_voice_candidate, refine_candidate, update_candidate_status

    notes = (body.notes if body else "") or ""
    if action == "refine":
        refinement = (body.refinement if body else "") or notes or "Refine slightly"
        return refine_candidate(db, project_id, character_id, voiceId, candidate_id, refinement=refinement)
    if action == "approve":
        return approve_voice_candidate(
            db, project_id, character_id, voiceId, candidate_id=candidate_id, approved_by="owner"
        )
    status_map = {"shortlist": "shortlisted", "reject": "rejected"}
    if action not in status_map:
        raise HTTPException(400, detail={"code": "INVALID_ACTION", "message": f"Unknown action {action}"})
    return update_candidate_status(
        db,
        project_id,
        character_id,
        voiceId,
        candidate_id,
        status=status_map[action],
        notes=notes,
    )


class VoiceApproveBody(BaseModel):
    candidateId: Optional[str] = None
    approvedBy: str = "owner"
    voiceId: str


@router.post("/projects/{project_id}/characters/{character_id}/voice/approve")
def voice_approve(project_id: str, character_id: str, body: VoiceApproveBody, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import approve_voice_candidate

    return approve_voice_candidate(
        db,
        project_id,
        character_id,
        body.voiceId,
        candidate_id=body.candidateId,
        approved_by=body.approvedBy,
    )


class AuditionBody(BaseModel):
    voiceId: str
    text: str
    category: str = ""


@router.post("/projects/{project_id}/characters/{character_id}/voice/audition")
def voice_audition(project_id: str, character_id: str, body: AuditionBody, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import audition_line

    return audition_line(db, project_id, character_id, body.voiceId, text=body.text, category=body.category)


class PronunciationBody(BaseModel):
    voiceId: str
    entries: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/projects/{project_id}/characters/{character_id}/voice/pronunciations")
def voice_pronunciations(project_id: str, character_id: str, body: PronunciationBody, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import upsert_pronunciations

    return upsert_pronunciations(db, project_id, character_id, body.voiceId, body.entries)


class PronunciationTestBody(BaseModel):
    voiceId: str
    word: str
    phonetic: str = ""


@router.post("/projects/{project_id}/characters/{character_id}/voice/pronunciations/test")
def voice_pronunciation_test(
    project_id: str, character_id: str, body: PronunciationTestBody, db: Session = Depends(get_db)
):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import test_pronunciation

    return test_pronunciation(db, project_id, character_id, body.voiceId, word=body.word, phonetic=body.phonetic)


class ReactionsBody(BaseModel):
    voiceId: str


@router.post("/projects/{project_id}/characters/{character_id}/voice/reactions/generate")
def voice_reactions_generate(project_id: str, character_id: str, body: ReactionsBody, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import generate_reactions

    return generate_reactions(db, project_id, character_id, body.voiceId)


@router.get("/projects/{project_id}/characters/{character_id}/voice/versions")
def voice_versions(project_id: str, character_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    voices = service.list_voice_profiles(db, project_id, character_id)
    return {
        "items": [
            {
                "id": v["id"],
                "name": v["name"],
                "version_number": v["version_number"],
                "source_mode": v["source_mode"],
                "approval_status": v["approval_status"],
                "provider": v["provider"],
                "approved_at": v.get("approved_at"),
                "approved_preview_asset_id": v.get("approved_preview_asset_id"),
            }
            for v in voices
        ],
        "mock": False,
    }


@router.get("/projects/{project_id}/characters/{character_id}/voice/provenance")
def voice_provenance(project_id: str, character_id: str, voiceId: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import list_candidates

    row = service.get_voice_or_none(db, project_id, character_id, voiceId)
    if not row:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Voice Profile not found."})
    v = service.voice_to_dict(row)
    cands = list_candidates(db, project_id, character_id, voiceId)
    return {
        "voiceProfileId": voiceId,
        "provider": v.get("provider"),
        "modelId": v.get("model_id"),
        "method": v.get("source_mode"),
        "consentRecordId": v.get("consent_record_id"),
        "designBrief": (v.get("lineage") or {}).get("designBrief"),
        "compiledPrompt": (v.get("lineage") or {}).get("compiledPrompt"),
        "candidates": cands.get("candidates"),
        "pronunciations": v.get("pronunciations"),
        "reactions": v.get("reactions"),
        "approvedAt": v.get("approved_at"),
        "approvalStatus": v.get("approval_status"),
        "mock": False,
    }


class CloneVoiceBody(BaseModel):
    name: str = "Cloned voice"
    reference_path: str
    transcript: str
    test_line: str
    consent: VoiceConsentCreate


@router.post("/projects/{project_id}/characters/{character_id}/voice-profiles/clone")
def clone_voice(project_id: str, character_id: str, body: CloneVoiceBody, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import clone_with_workspace

    return clone_with_workspace(db, project_id, character_id, body)


@router.post("/projects/{project_id}/characters/{character_id}/voice/clone/generate")
def voice_clone_generate(project_id: str, character_id: str, body: CloneVoiceBody, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .voice_creator import clone_with_workspace

    return clone_with_workspace(db, project_id, character_id, body)


@router.post("/projects/{project_id}/characters/{character_id}/voice-profiles/{voice_id}/generate-dialogue")
def generate_dialogue(
    project_id: str,
    character_id: str,
    voice_id: str,
    body: DialogueGenerateRequest,
    db: Session = Depends(get_db),
):
    _require_flag()
    _project(db, project_id)
    from .voice_runtime import run_generate_dialogue

    return run_generate_dialogue(db, project_id, character_id, voice_id, body)


class ProposeDirectionsBody(BaseModel):
    directions: Optional[list[dict[str, Any]]] = None


class SelectConceptBody(BaseModel):
    directionId: str
    approvedBy: str = "owner"
    notes: str = ""


class GateStatusBody(BaseModel):
    status: str
    assetIds: list[str] = Field(default_factory=list)
    approvedBy: Optional[str] = None
    notes: str = ""


class PromoteCanonicalBody(BaseModel):
    versionId: str


@router.get("/projects/{project_id}/characters/{character_id}/visual-gates")
def get_visual_gates(project_id: str, character_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .visual_gates import list_gates

    return list_gates(db, project_id, character_id)


@router.post("/projects/{project_id}/characters/{character_id}/visual-gates/concept/propose")
def propose_concept_directions(
    project_id: str, character_id: str, body: ProposeDirectionsBody, db: Session = Depends(get_db)
):
    _require_flag()
    _project(db, project_id)
    from .visual_gates import propose_visual_directions

    return propose_visual_directions(db, project_id, character_id, body.directions)


@router.post("/projects/{project_id}/characters/{character_id}/visual-gates/concept/select")
def select_concept_direction(
    project_id: str, character_id: str, body: SelectConceptBody, db: Session = Depends(get_db)
):
    _require_flag()
    _project(db, project_id)
    from .visual_gates import owner_select_concept

    try:
        return owner_select_concept(
            db,
            project_id,
            character_id,
            direction_id=body.directionId,
            approved_by=body.approvedBy,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "INVALID_CONCEPT", "message": str(exc)}) from exc


@router.post("/projects/{project_id}/characters/{character_id}/visual-gates/{gate}")
def update_visual_gate(
    project_id: str,
    character_id: str,
    gate: str,
    body: GateStatusBody,
    db: Session = Depends(get_db),
):
    _require_flag()
    _project(db, project_id)
    from .visual_gates import set_gate_status

    try:
        return set_gate_status(
            db,
            project_id,
            character_id,
            gate,
            status=body.status,
            asset_ids=body.assetIds,
            approved_by=body.approvedBy,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "INVALID_GATE", "message": str(exc)}) from exc


@router.post("/projects/{project_id}/characters/{character_id}/visual-gates/promote-canonical")
def promote_visual_canonical(
    project_id: str, character_id: str, body: PromoteCanonicalBody, db: Session = Depends(get_db)
):
    _require_flag()
    _project(db, project_id)
    from .visual_gates import promote_to_canonical

    try:
        return promote_to_canonical(db, project_id, character_id, body.versionId)
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "GATES_INCOMPLETE", "message": str(exc)}) from exc


class PromoteIdentityBody(BaseModel):
    approvedBy: str = "owner"


@router.post("/projects/{project_id}/characters/seed-korri")
def seed_korri(project_id: str, db: Session = Depends(get_db)):
    """Create/refresh Korri from locked korri.v1 canon pack."""
    _require_flag()
    _project(db, project_id)
    return service.seed_korri_from_canon(db, project_id).model_dump()


@router.post("/projects/{project_id}/characters/{character_id}/promote")
def promote_character_identity(
    project_id: str, character_id: str, body: PromoteIdentityBody, db: Session = Depends(get_db)
):
    """Certified promotion → VisualIdentity + Bible + relationships + Prompt Package."""
    _require_flag()
    _project(db, project_id)
    from .promotion import promote_canonical

    return promote_canonical(db, project_id, character_id, approved_by=body.approvedBy)


@router.get("/projects/{project_id}/characters/{character_id}/prompt-package")
def get_prompt_package(project_id: str, character_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    profile = service.get_profile(db, project_id, character_id)
    pkg = profile.prompt_package or {}
    if not pkg:
        from .prompt_package import generate_prompt_package

        pkg = generate_prompt_package(profile.model_dump(), character_version_id=profile.active_version_id or "")
    return {"characterId": character_id, "promptPackage": pkg}


@router.get("/projects/{project_id}/characters/canon/korri")
def get_korri_canon(project_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .canon import korri_v1

    return korri_v1()


class VisualSheetStartBody(BaseModel):
    includeDetails: bool = True
    includePerformance: bool = True
    heroAssetId: Optional[str] = None
    candidateCount: Optional[int] = None
    visualStyle: Optional[str] = None


class VisualSheetApproveBody(BaseModel):
    approvedBy: str = "owner"
    selectDirectionId: str = "wild_sun_sprite"


@router.post("/projects/{project_id}/characters/{character_id}/visual-sheet/generate")
def start_visual_sheet(project_id: str, character_id: str, body: VisualSheetStartBody, db: Session = Depends(get_db)):
    """Enqueue Generated Character Image Profile via certified Z-Image / character-sheet."""
    _require_flag()
    _project(db, project_id)
    from .visual_sheet import start_visual_sheet_generation

    try:
        pack = start_visual_sheet_generation(
            db,
            project_id,
            character_id,
            include_details=body.includeDetails,
            include_performance=body.includePerformance,
            hero_asset_id=body.heroAssetId,
            candidate_count=body.candidateCount if body.candidateCount is not None else 1,
            visual_style=body.visualStyle,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "VISUAL_SHEET_ERROR", "message": str(exc)}) from exc
    return {"ok": True, "pack": pack}


@router.post("/projects/{project_id}/characters/{character_id}/visual-sheet/advance")
def advance_visual_sheet(project_id: str, character_id: str, db: Session = Depends(get_db)):
    """Poll jobs, attach role-mapped assets, enqueue next sheet phase."""
    _require_flag()
    _project(db, project_id)
    from .visual_sheet import advance_visual_sheet_pack

    try:
        pack = advance_visual_sheet_pack(db, project_id, character_id)
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "VISUAL_SHEET_ERROR", "message": str(exc)}) from exc
    return {"ok": True, "pack": pack}


@router.get("/projects/{project_id}/characters/{character_id}/visual-sheet")
def get_visual_sheet(project_id: str, character_id: str, db: Session = Depends(get_db)):
    _require_flag()
    _project(db, project_id)
    from .visual_sheet import get_visual_sheet_pack

    return get_visual_sheet_pack(db, project_id, character_id)


@router.post("/projects/{project_id}/characters/{character_id}/visual-sheet/owner-approve")
def owner_approve_visual_sheet(
    project_id: str, character_id: str, body: VisualSheetApproveBody, db: Session = Depends(get_db)
):
    """Owner-only approval of gates that have real generated assetIds."""
    _require_flag()
    _project(db, project_id)
    from .visual_sheet import owner_approve_visual_sheet_gates

    try:
        return owner_approve_visual_sheet_gates(
            db,
            project_id,
            character_id,
            approved_by=body.approvedBy,
            select_direction_id=body.selectDirectionId,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "VISUAL_SHEET_ERROR", "message": str(exc)}) from exc
