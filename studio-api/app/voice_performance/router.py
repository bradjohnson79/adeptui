"""Voice Performance HTTP API."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from . import m410_service, service
from .compiler import character_readiness, compile_performance
from .production_gate import evaluate_m42_voice_performance_gate
from .m410_schemas import (
    ApproveTakeBody,
    CodirectorPlanRequest,
    CompareTakesBody,
    DirectionModeBody,
    GenerateTakesBody as M410GenerateTakesBody,
    LipsyncBody,
    PerformancePlanPatchBody,
    RuntimeInstallBody,
    SceneBatchBody,
    TimelinePlacementBody,
    VoicePerformanceRecordCreate,
)
from .schemas import CreatePlanBody, GeneratePlanBody, ParseMarkupBody, PlaceOnTimelineBody

router = APIRouter(prefix="/voice-performance", tags=["voice-performance"])


@router.get("/gate/wave44")
def wave44_gate():
    g = evaluate_m42_voice_performance_gate()
    return {**g, "ok": bool(g.get("voicePerformanceGo")), "passed": bool(g.get("voicePerformanceGo"))}


@router.get("/tags")
def list_tags():
    return service.get_registry()


@router.get("/providers")
def list_providers():
    return service.get_provider_caps()


@router.post("/parse")
def parse_markup(body: ParseMarkupBody, request: Request, db: Session = Depends(get_db)):
    return compile_performance(
        db,
        project_id=body.projectId,
        character_id=body.characterId,
        source_text=body.sourceText,
        scene_id=body.sceneId,
        voice_version_id=body.voiceVersionId,
        request=request,
    )


@router.post("/validate")
def validate_markup(body: ParseMarkupBody, request: Request, db: Session = Depends(get_db)):
    return parse_markup(body, request, db)


@router.post("/plans")
def create_plan(body: CreatePlanBody, request: Request, db: Session = Depends(get_db)):
    return service.create_plan(db, body, request=request)


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str, request: Request, db: Session = Depends(get_db)):
    return service.get_plan(db, plan_id, request=request)


@router.post("/plans/{plan_id}/compile")
def compile_plan(plan_id: str, db: Session = Depends(get_db)):
    return service.submit_plan(db, plan_id)


@router.get("/plans/{plan_id}/provider-translation")
def provider_translation(plan_id: str, provider: Optional[str] = None, db: Session = Depends(get_db)):
    return service.provider_translation_for_plan(db, plan_id, provider_key=provider)


@router.post("/plans/{plan_id}/generate")
def generate_plan(
    plan_id: str,
    body: GeneratePlanBody,
    request: Request,
    db: Session = Depends(get_db),
    projectId: Optional[str] = None,
):
    return service.generate_segments(
        db,
        plan_id,
        allow_kokoro_fallback=body.allowKokoroFallback,
        allow_testing_voice=body.allowTestingVoice,
        request=request,
        project_id=projectId,
    )


@router.get("/plans/{plan_id}/segments")
def list_segments(plan_id: str, request: Request, db: Session = Depends(get_db), projectId: Optional[str] = None):
    plan = service.get_plan(db, plan_id, request=request, project_id=projectId)
    return {"planId": plan_id, "segments": [s.model_dump() for s in plan.segments], "mock": False}


@router.post("/segments/{segment_id}/retry")
def retry_segment(
    segment_id: str,
    body: GeneratePlanBody | None = None,
    db: Session = Depends(get_db),
    projectId: Optional[str] = None,
):
    return service.retry_segment(
        db,
        segment_id,
        allow_kokoro_fallback=bool(body and body.allowKokoroFallback),
        project_id=projectId,
    )


@router.post("/segments/{segment_id}/approve")
def approve_segment(segment_id: str, db: Session = Depends(get_db), projectId: Optional[str] = None):
    return service.approve_segment(db, segment_id, approved=True, project_id=projectId)


@router.post("/segments/{segment_id}/reject")
def reject_segment(segment_id: str, db: Session = Depends(get_db), projectId: Optional[str] = None):
    return service.approve_segment(db, segment_id, approved=False, project_id=projectId)


@router.post("/plans/{plan_id}/assemble")
def assemble(plan_id: str, db: Session = Depends(get_db), projectId: Optional[str] = None):
    return service.assemble_plan(db, plan_id, project_id=projectId)


@router.post("/assemblies/{assembly_id}/approve")
def approve_assembly(assembly_id: str, approvedBy: str = "owner", db: Session = Depends(get_db), projectId: Optional[str] = None):
    return service.approve_assembly(db, assembly_id, approved_by=approvedBy, project_id=projectId)


@router.post("/assemblies/{assembly_id}/place-on-timeline")
def place_timeline(assembly_id: str, body: PlaceOnTimelineBody, db: Session = Depends(get_db), projectId: Optional[str] = None):
    return service.place_on_timeline(
        db,
        assembly_id,
        timeline_id=body.timelineId,
        start_ms=body.startMs,
        project_id=projectId,
    )


@router.get("/characters/{character_id}/readiness")
def readiness(character_id: str, projectId: str, request: Request, db: Session = Depends(get_db)):
    return character_readiness(db, projectId, character_id, request=request)


@router.get("/m410/runtime/status")
def m410_runtime_status():
    return m410_service.get_runtime_status()


@router.post("/m410/runtime/install")
def m410_runtime_install(body: RuntimeInstallBody):
    return m410_service.install_runtime(
        confirm=body.confirm,
        confirm_download_models=body.confirm_download_models,
    )


@router.post("/m410/runtime/verify")
def m410_runtime_verify():
    return m410_service.verify_runtime()


@router.get("/m410/capabilities")
def m410_capabilities():
    return m410_service.get_capabilities()


@router.get("/m410/emotion-presets")
def m410_emotion_presets():
    return m410_service.get_emotion_presets()


@router.post("/m410/records")
def m410_create_record(body: VoicePerformanceRecordCreate, db: Session = Depends(get_db)):
    return m410_service.create_record(db, body)


@router.get("/m410/records/{record_id}")
def m410_get_record(record_id: str, db: Session = Depends(get_db)):
    return m410_service.get_record(db, record_id)


@router.get("/m410/projects/{project_id}/records")
def m410_list_records(project_id: str, db: Session = Depends(get_db)):
    return {"projectId": project_id, "records": [r.model_dump() for r in m410_service.list_records(db, project_id)]}


@router.post("/m410/records/{record_id}/performance-plan")
def m410_generate_performance_plan(
    record_id: str,
    body: CodirectorPlanRequest,
    db: Session = Depends(get_db),
):
    record = m410_service.get_record(db, record_id)
    plan = m410_service.build_codirector_performance_plan(record.dialogueText, body.context)
    return m410_service.apply_performance_plan(
        db,
        record_id,
        plan,
        mode="codirector",
        emotion_source="codirector",
        emotion_vector=plan.get("emotionVector") or {},
    )


@router.patch("/m410/records/{record_id}/performance-plan")
def m410_patch_performance_plan(
    record_id: str,
    body: PerformancePlanPatchBody,
    db: Session = Depends(get_db),
):
    return m410_service.apply_performance_plan(
        db,
        record_id,
        body.performancePlan,
        mode=body.mode,
        emotion_source=body.emotionSource,
        emotion_vector=body.emotionVector,
    )


@router.post("/m410/records/{record_id}/direction-mode")
def m410_set_direction_mode(record_id: str, body: DirectionModeBody, db: Session = Depends(get_db)):
    return m410_service.set_direction_mode(
        db, record_id, body.directionMode, performance_plan=body.performancePlan or None
    )


@router.post("/m410/records/{record_id}/generate-takes")
def m410_generate_takes(record_id: str, body: M410GenerateTakesBody, db: Session = Depends(get_db)):
    return m410_service.create_takes(db, record_id, body)


@router.get("/m410/records/{record_id}/takes")
def m410_list_takes(record_id: str, db: Session = Depends(get_db)):
    return m410_service.list_takes(db, record_id)


@router.post("/m410/records/{record_id}/takes/{take_id}/approve")
def m410_approve_take(
    record_id: str,
    take_id: str,
    body: ApproveTakeBody,
    db: Session = Depends(get_db),
):
    return m410_service.approve_take(db, record_id, take_id, approved_by=body.approvedBy)


@router.post("/m410/records/{record_id}/compare")
def m410_compare(record_id: str, body: CompareTakesBody, db: Session = Depends(get_db)):
    return m410_service.compare_takes(db, record_id, take_ids=body.takeIds)


@router.post("/m410/records/{record_id}/timeline")
def m410_timeline(record_id: str, body: TimelinePlacementBody, db: Session = Depends(get_db)):
    return m410_service.place_timeline_dialogue(
        db,
        record_id,
        track_id=body.trackId,
        start_ms=body.startMs,
        confirm_replace=body.confirmReplace,
    )


@router.post("/m410/records/{record_id}/lipsync")
def m410_lipsync(record_id: str, body: LipsyncBody, db: Session = Depends(get_db)):
    return m410_service.prepare_lipsync(
        db,
        record_id,
        confirm=body.confirm,
        set_scene_audio_asset=body.setSceneAudioAsset,
    )


@router.post("/m410/scene-batch")
def m410_scene_batch(body: SceneBatchBody, db: Session = Depends(get_db)):
    return m410_service.create_scene_batch(db, body)
