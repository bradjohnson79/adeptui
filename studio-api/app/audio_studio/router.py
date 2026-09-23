"""Audio Studio HTTP API — M42 W45."""

from __future__ import annotations

from typing import Any, Optional

from ..magi.authority import audio_studio_mix_labels
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from . import service
from .production_gate import evaluate_m42_audio_studio_gate
from .provider_resolver import resolve_execution

router = APIRouter(prefix="/audio-studio", tags=["audio-studio"])


@router.get("/gate/w45")
def gate_w45():
    return evaluate_m42_audio_studio_gate()


@router.get("/projects/{project_id}/workspace")
def get_workspace(project_id: str, db: Session = Depends(get_db)):
    return service.workspace(db, project_id)


class GenerateBody(BaseModel):
    kind: str = "music"
    brief: Optional[dict[str, Any]] = None
    prompt: Optional[str] = None
    durationSeconds: Optional[float] = None
    mood: Optional[list[str]] = None
    genre: Optional[str] = None
    energy: Optional[str] = None
    instrumentation: Optional[list[str]] = None
    category: Optional[str] = None
    intensity: Optional[str] = None
    eventType: Optional[str] = None
    loopRequired: Optional[bool] = None
    # ORDER 14 SFX Director (additive)
    intent: Optional[dict[str, Any]] = None
    sfxIntent: Optional[dict[str, Any]] = None
    physicalEvent: Optional[str] = None
    material: Optional[str] = None
    context: Optional[str] = None
    temporal: Optional[dict[str, Any]] = None
    negatives: Optional[list[str]] = None
    distance: Optional[str] = None
    environment: Optional[str] = None
    reverb: Optional[str] = None
    perspective: Optional[str] = None
    adherence: Optional[str] = None
    candidateCount: int = Field(default=3, ge=1, le=6)
    preferredProvider: Optional[str] = None
    allowProviderSwitch: bool = False
    allowCpuFallback: bool = False
    asyncMode: bool = True


def _brief_from_body(body: GenerateBody) -> dict[str, Any]:
    brief = dict(body.brief or {})
    if body.prompt is not None:
        brief["prompt"] = body.prompt
    if body.durationSeconds is not None:
        brief["duration_seconds"] = body.durationSeconds
    if body.mood is not None:
        brief["mood"] = body.mood
    if body.genre is not None:
        brief["genre"] = body.genre
    if body.energy is not None:
        brief["energy"] = body.energy
    if body.instrumentation is not None:
        brief["instrumentation"] = body.instrumentation
    if body.category is not None:
        brief["category"] = body.category
    if body.intensity is not None:
        brief["intensity"] = body.intensity
    if body.eventType is not None:
        brief["eventType"] = body.eventType
    if body.loopRequired is not None:
        brief["loop_required"] = body.loopRequired
    # ORDER 14 structured intent
    intent = dict(body.intent or body.sfxIntent or brief.get("intent") or {})
    for key, val in (
        ("physicalEvent", body.physicalEvent),
        ("material", body.material),
        ("context", body.context),
        ("temporal", body.temporal),
        ("negatives", body.negatives),
        ("distance", body.distance),
        ("environment", body.environment),
        ("reverb", body.reverb),
        ("perspective", body.perspective),
        ("adherence", body.adherence),
    ):
        if val is not None:
            intent[key] = val
    if body.eventType and not intent.get("physicalEvent"):
        intent["physicalEvent"] = body.eventType
    if body.durationSeconds is not None:
        temporal = dict(intent.get("temporal") or {})
        temporal.setdefault("durationSec", float(body.durationSeconds))
        intent["temporal"] = temporal
    if body.prompt is not None and not intent.get("prompt"):
        intent["prompt"] = body.prompt
    if body.intensity is not None and not intent.get("intensity"):
        intent["intensity"] = body.intensity
    if intent:
        brief["intent"] = intent
        brief["sfxIntent"] = intent
        if intent.get("physicalEvent"):
            brief["eventType"] = intent["physicalEvent"]
            brief["physicalEvent"] = intent["physicalEvent"]
        for k in ("material", "context", "temporal", "negatives", "distance", "environment", "reverb", "perspective", "adherence"):
            if k in intent:
                brief[k] = intent[k]
    return brief


@router.post("/projects/{project_id}/generate")
def generate(
    project_id: str,
    body: GenerateBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # ORDER 15: explicit ElevenLabs selection must not silently fall back to Local/MMAudio.
    if (body.preferredProvider or "").strip().lower() in ("elevenlabs", "eleven_labs", "el"):
        from ..hosted_providers.elevenlabs_gate import gate_preferred_provider
        gate_preferred_provider(body.preferredProvider, surface="audio-studio.generate", capability="elevenlabs.sfx")
    brief = _brief_from_body(body)
    if body.asyncMode:
        batch = service.begin_generate_batch(
            project_id,
            kind=body.kind,
            brief=brief,
            candidate_count=body.candidateCount,
            preferred_provider=body.preferredProvider,
            allow_provider_switch=body.allowProviderSwitch,
            allow_cpu_fallback=body.allowCpuFallback,
        )
        background_tasks.add_task(service.run_generate_batch_job, project_id, batch["id"])
        return batch
    return service.generate_batch(
        db,
        project_id,
        kind=body.kind,
        brief=brief,
        candidate_count=body.candidateCount,
        preferred_provider=body.preferredProvider,
        allow_provider_switch=body.allowProviderSwitch,
        allow_cpu_fallback=body.allowCpuFallback,
    )


@router.get("/projects/{project_id}/batches/{batch_id}")
def get_batch(project_id: str, batch_id: str):
    return service.get_batch(project_id, batch_id)


@router.post("/projects/{project_id}/batches/{batch_id}/cancel")
def cancel_batch(project_id: str, batch_id: str):
    """Certified cancel-to-source — terminates ACE-Step/MMAudio worker process trees."""
    return service.cancel_batch(project_id, batch_id)


@router.post("/projects/{project_id}/cancel-generations")
def cancel_project_generations(project_id: str):
    """Cancel all in-flight Audio Studio batches for the project (GPU/RAM safety)."""
    return service.cancel_project_generations(project_id)


@router.post("/projects/{project_id}/batches/{batch_id}/candidates/{candidate_id}/select")
def select_candidate(project_id: str, batch_id: str, candidate_id: str):
    return service.select_candidate(project_id, batch_id, candidate_id)


@router.post("/projects/{project_id}/batches/{batch_id}/candidates/{candidate_id}/approve")
def approve_candidate(project_id: str, batch_id: str, candidate_id: str, db: Session = Depends(get_db)):
    return service.approve_candidate(project_id, batch_id, candidate_id, db=db)


@router.post("/projects/{project_id}/batches/{batch_id}/candidates/{candidate_id}/retry")
def retry_candidate(project_id: str, batch_id: str, candidate_id: str, db: Session = Depends(get_db)):
    return service.retry_candidate(db, project_id, batch_id, candidate_id)


class PlaceBody(BaseModel):
    assetId: str
    category: str = "music"
    startMs: int = 0
    loop: bool = False
    sceneId: Optional[str] = None


@router.post("/projects/{project_id}/place")
def place(project_id: str, body: PlaceBody, db: Session = Depends(get_db)):
    return service.place_on_timeline(
        db,
        project_id,
        asset_id=body.assetId,
        category=body.category,
        start_ms=body.startMs,
        loop=body.loop,
        scene_id=body.sceneId,
    )


@router.get("/projects/{project_id}/mix")
def get_mix(project_id: str):
    from . import store

    return {
        "ok": True,
        "mix": store.get_mix(project_id),
        "mock": False,
        **audio_studio_mix_labels(project_id),
    }


class MixBody(BaseModel):
    master: Optional[dict[str, Any]] = None
    clips: Optional[dict[str, Any]] = None
    clip: Optional[dict[str, Any]] = None


@router.put("/projects/{project_id}/mix")
def put_mix(project_id: str, body: MixBody):
    return {
        "ok": True,
        "mix": service.update_mix(project_id, body.model_dump(exclude_none=True)),
        "mock": False,
        **audio_studio_mix_labels(project_id),
    }




class MutateIntentBody(BaseModel):
    intent: Optional[dict[str, Any]] = None
    op: str
    materialHint: Optional[str] = None
    physicalEventHint: Optional[str] = None
    deltaEventCount: Optional[int] = None
    generate: bool = False
    candidateCount: int = Field(default=3, ge=1, le=6)


class CandidateMutateIntentBody(BaseModel):
    """Preferred FE path — intent optional; loaded from candidate lineage when omitted."""
    op: str
    intent: Optional[dict[str, Any]] = None
    materialHint: Optional[str] = None
    physicalEventHint: Optional[str] = None
    deltaEventCount: Optional[int] = None
    generate: bool = True
    candidateCount: int = Field(default=3, ge=1, le=6)


def _intent_from_candidate(batch: dict[str, Any], cand: dict[str, Any]) -> dict[str, Any]:
    """Rebuild SfxDirectorIntent from persisted candidate / batch compiler fields."""
    sc = cand.get("sound_compiler") or batch.get("sound_compiler") or {}
    if not isinstance(sc, dict):
        sc = {}
    intent: dict[str, Any] = {}
    for k in (
        "physicalEvent",
        "material",
        "context",
        "temporal",
        "negatives",
        "refinementOps",
        "distance",
        "environment",
        "reverb",
        "perspective",
        "adherence",
        "intensity",
    ):
        if cand.get(k) is not None:
            intent[k] = cand.get(k)
        elif sc.get(k) is not None:
            intent[k] = sc.get(k)
    if not intent.get("physicalEvent"):
        intent["physicalEvent"] = cand.get("event_type") or sc.get("event_type") or sc.get("physicalEvent")
    if not intent.get("intensity"):
        intent["intensity"] = sc.get("intensity_key")
    brief = batch.get("brief_snapshot") or {}
    if isinstance(brief, dict):
        bi = brief.get("intent") or brief.get("sfxIntent")
        if isinstance(bi, dict):
            for k, v in bi.items():
                intent.setdefault(k, v)
    intent["prompt"] = (
        cand.get("raw_prompt")
        or sc.get("raw_prompt")
        or batch.get("raw_prompt")
        or (brief.get("prompt") if isinstance(brief, dict) else None)
        or ""
    )
    intent["raw_prompt"] = intent.get("prompt")
    return {k: v for k, v in intent.items() if v is not None}


def _apply_sfx_mutate(
    *,
    project_id: str,
    intent_in: dict[str, Any],
    op: str,
    material_hint: Optional[str],
    physical_event_hint: Optional[str],
    delta_event_count: Optional[int],
    generate: bool,
    candidate_count: int,
    background_tasks: BackgroundTasks,
    previous_intent: Optional[dict[str, Any]] = None,
    parent_candidate_id: Optional[str] = None,
) -> dict[str, Any]:
    from .sound_prompt_compiler import compile_sound_prompt, mutate_sfx_intent

    intent = dict(intent_in or {})
    op_s = str(op or "").strip()
    if material_hint:
        intent["materialHint"] = material_hint
        if op_s in {"wrong_material", "more_material"}:
            intent["material"] = material_hint
    if physical_event_hint:
        intent["physicalEventHint"] = physical_event_hint
        if op_s == "wrong_sound":
            intent["physicalEvent"] = physical_event_hint
    if delta_event_count is not None:
        intent["deltaEventCount"] = int(delta_event_count)

    patched = mutate_sfx_intent(intent, op_s)
    if not isinstance(patched, dict):
        patched = dict(intent)
        patched.setdefault("refinementOps", [])
        if isinstance(patched["refinementOps"], list):
            patched["refinementOps"] = list(patched["refinementOps"]) + [op_s]

    if parent_candidate_id:
        patched["parentCandidateId"] = parent_candidate_id

    prompt = str(patched.get("prompt") or patched.get("raw_prompt") or intent.get("prompt") or "")
    duration = None
    temporal = patched.get("temporal") if isinstance(patched.get("temporal"), dict) else {}
    if temporal.get("durationSec") is not None:
        duration = float(temporal["durationSec"])
    intensity = patched.get("intensity") or patched.get("intensity_key")
    event = patched.get("physicalEvent") or patched.get("event_type")

    compiled = compile_sound_prompt(
        prompt,
        duration_seconds=float(duration or 3.0),
        intensity=intensity if isinstance(intensity, str) else None,
        event=event if isinstance(event, str) else None,
        physicalEvent=event if isinstance(event, str) else None,
        intent=patched,
    )
    compile_payload = compiled.to_dict() if hasattr(compiled, "to_dict") else {
        "compiled_prompt": getattr(compiled, "prompt", ""),
        "negative_prompt": getattr(compiled, "negative_prompt", ""),
    }
    compiled_prompt = (
        compile_payload.get("compiledPrompt")
        or compile_payload.get("compiled_prompt")
        or ""
    )

    out: dict[str, Any] = {
        "ok": True,
        "op": op_s,
        "intent": patched,
        "patchedIntent": patched,
        "previousIntent": previous_intent if previous_intent is not None else intent,
        "compile": compile_payload,
        "compiledPrompt": compiled_prompt,
        "projectId": project_id,
    }
    if generate:
        brief = {
            "prompt": compiled_prompt or prompt,
            "duration_seconds": duration or 3.0,
            "intensity": intensity,
            "eventType": event,
            "physicalEvent": event,
            "intent": patched,
            "sfxIntent": patched,
            "sound_compiler": compile_payload,
        }
        for k in ("material", "context", "temporal", "negatives"):
            if k in patched:
                brief[k] = patched[k]
        batch = service.begin_generate_batch(
            project_id,
            kind="sfx",
            brief=brief,
            candidate_count=candidate_count,
        )
        background_tasks.add_task(service.run_generate_batch_job, project_id, batch["id"])
        out["batchId"] = batch.get("id")
        out["batch"] = batch
    return out


@router.post("/projects/{project_id}/sfx/mutate-intent")
def mutate_sfx_intent_route(
    project_id: str,
    body: MutateIntentBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """ORDER 14 fallback — refine structured SFX intent; optional re-generate."""
    if not body.intent:
        raise service._err("INVALID", "intent is required for /sfx/mutate-intent", 400)  # type: ignore[attr-defined]
    return _apply_sfx_mutate(
        project_id=project_id,
        intent_in=dict(body.intent or {}),
        op=body.op,
        material_hint=body.materialHint,
        physical_event_hint=body.physicalEventHint,
        delta_event_count=body.deltaEventCount,
        generate=bool(body.generate),
        candidate_count=body.candidateCount,
        background_tasks=background_tasks,
        previous_intent=dict(body.intent or {}),
    )


@router.post("/projects/{project_id}/batches/{batch_id}/candidates/{candidate_id}/mutate-intent")
def mutate_sfx_candidate_intent_route(
    project_id: str,
    batch_id: str,
    candidate_id: str,
    body: CandidateMutateIntentBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """ORDER 14 preferred — refine from candidate lineage; default generate=true."""
    from . import store as as_store
    batch = as_store.get_batch(project_id, batch_id)
    if not batch:
        raise service._err("NOT_FOUND", "Batch not found.", 404)
    cand = next((c for c in (batch.get("candidates") or []) if c.get("id") == candidate_id), None)
    if not cand:
        raise service._err("NOT_FOUND", "Candidate not found.", 404)

    previous = dict(body.intent) if isinstance(body.intent, dict) and body.intent else _intent_from_candidate(batch, cand)
    out = _apply_sfx_mutate(
        project_id=project_id,
        intent_in=previous,
        op=body.op,
        material_hint=body.materialHint,
        physical_event_hint=body.physicalEventHint,
        delta_event_count=body.deltaEventCount,
        generate=bool(body.generate),
        candidate_count=body.candidateCount,
        background_tasks=background_tasks,
        previous_intent=previous,
        parent_candidate_id=candidate_id,
    )
    out["batchIdSource"] = batch_id
    out["candidateId"] = candidate_id
    return out


@router.get("/projects/{project_id}/providers")
def providers(project_id: str, kind: str = "music"):
    return resolve_execution(kind if kind in ("music", "sfx", "ambience") else "music")
