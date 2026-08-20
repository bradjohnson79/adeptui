"""MAGI Editor API — readiness, gate, overlays, deterministic composition render."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .composition.service import enqueue_overlay_compose
from .errors import magi_canonical_code, magi_error, magi_taxonomy
from .overlays import store as overlay_store
from .overlays.fonts import load_font_registry
from .overlays.validate import validate_composition
from .production_gate import evaluate_magi_wave4b_gate, evaluate_wave5_may_begin
from .readiness import readiness_payload
from .sequence.store import get_sequence, save_sequence
from .sequence.validation import parse_sequence, validate_asset_ownership
from .timeline_handoff import export_to_timeline, import_timeline_asset
from ..timeline_product.production_gate import evaluate_timeline_wave4c_gate

router = APIRouter(prefix="/api/magi", tags=["magi-editor"])


@router.get("/readiness")
def get_readiness() -> dict[str, Any]:
    return readiness_payload()


@router.get("/gate/wave4b")
def get_wave4b_gate() -> dict[str, Any]:
    gate = evaluate_magi_wave4b_gate()
    return {
        **gate,
        "ok": bool(gate.get("wave4bGo")),
        "passed": bool(gate.get("wave4bGo")),
    }


@router.get("/gate/wave5-may-begin")
def get_wave5_may_begin() -> dict[str, Any]:
    return evaluate_wave5_may_begin()


@router.get("/gate/wave4c")
def get_wave4c_gate() -> dict[str, Any]:
    gate = evaluate_timeline_wave4c_gate()
    return {
        **gate,
        "ok": bool(gate.get("wave4cGo")),
        "passed": bool(gate.get("wave4cGo")),
    }


@router.post("/deferred/{surface_id}/execute")
def refuse_deferred_execute(surface_id: str) -> dict[str, Any]:
    """Honest refuse — never fake multimodal / timeline execution."""
    from .readiness import deferred_surfaces, magi_actions_catalog

    surfaces = {s["id"]: s for s in deferred_surfaces()}
    actions = {a["id"]: a for a in magi_actions_catalog()}
    item = surfaces.get(surface_id) or actions.get(surface_id)
    if not item:
        return {
            "ok": False,
            "executed": False,
            "status": "Blocked",
            "surfaceId": surface_id,
            "code": "UNSUPPORTED_OPERATION",
            "message": f"Unknown MAGI surface '{surface_id}' — not executable.",
        }
    status = item.get("status") or "Blocked"
    return {
        "ok": False,
        "executed": False,
        "status": status,
        "surfaceId": surface_id,
        "name": item.get("name") or item.get("label"),
        "code": "UNSUPPORTED_OPERATION",
        "message": item.get("reason")
        or f"{item.get('name') or item.get('label')} is {status} — not production-ready. No fake execution.",
        "disclosure": "Use certified image MAGI Actions via ImageEditIntent path only.",
    }


@router.get("/fonts")
def get_fonts() -> dict[str, Any]:
    return load_font_registry()


@router.get("/projects/{project_id}/overlays")
def list_overlays(project_id: str) -> dict[str, Any]:
    return {"items": overlay_store.list_compositions(project_id)}


@router.get("/projects/{project_id}/overlays/{composition_id}")
def get_overlay(project_id: str, composition_id: str) -> dict[str, Any]:
    comp = overlay_store.get_composition(project_id, composition_id)
    if not comp:
        raise magi_error(
            "OVERLAY_NOT_FOUND",
            "Composition not found.",
            status_code=404,
            fields={"compositionId": composition_id, "projectId": project_id},
        )
    return comp


@router.get("/projects/{project_id}/overlays/by-asset/{asset_id}")
def get_overlay_for_asset(project_id: str, asset_id: str) -> dict[str, Any]:
    return overlay_store.get_or_create_for_asset(project_id, source_asset_id=asset_id)


@router.put("/projects/{project_id}/overlays/{composition_id}")
def put_overlay(project_id: str, composition_id: str, body: dict[str, Any]) -> dict[str, Any]:
    body = dict(body or {})
    body["compositionId"] = composition_id
    body["projectId"] = project_id
    try:
        return overlay_store.save_composition(project_id, body)
    except ValueError as exc:
        raise magi_error(
            "OVERLAY_INVALID",
            "Overlay composition failed validation.",
            fields={"detail": str(exc), "errors": [str(exc)]},
        ) from exc


@router.post("/projects/{project_id}/overlays")
def create_overlay(project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    body = dict(body or {})
    body["projectId"] = project_id
    try:
        return overlay_store.save_composition(project_id, body)
    except ValueError as exc:
        raise magi_error(
            "OVERLAY_INVALID",
            "Overlay composition failed validation.",
            fields={"detail": str(exc), "errors": [str(exc)]},
        ) from exc


@router.post("/projects/{project_id}/overlays/validate")
def validate_overlay(project_id: str, body: dict[str, Any]) -> dict[str, Any]:
    body = dict(body or {})
    body["projectId"] = project_id
    return validate_composition(body, project_id=project_id)


@router.post("/projects/{project_id}/overlays/render")
def render_overlay(project_id: str, body: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    result = enqueue_overlay_compose(
        db,
        project_id,
        composition_id=body.get("compositionId"),
        composition=body.get("composition"),
    )
    if not result.get("ok"):
        raise magi_error(
            "RENDER_FAILED",
            "MAGI overlay render failed.",
            fields={"result": result},
        )
    return result


@router.get("/projects/{project_id}/sequence")
def get_project_sequence(project_id: str) -> dict[str, Any]:
    return {"sequence": get_sequence(project_id)}


@router.put("/projects/{project_id}/sequence")
def put_project_sequence(
    project_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    payload = dict(body or {})
    sequence = payload.get("sequence") if isinstance(payload.get("sequence"), dict) else payload
    # m1 A3: optional optimistic-concurrency check. When the client supplies the
    # revision it last observed, a newer server revision is a CONFLICT and the
    # payload is refused (never last-writer-wins silently). Omitting it keeps the
    # legacy last-writer-wins behavior for older clients.
    expected = payload.get("expectedRevision")
    if expected is not None:
        try:
            expected_revision = int(expected)
        except (TypeError, ValueError):
            raise magi_error(
                "INVALID_REVISION",
                "expectedRevision must be a positive integer.",
                status_code=422,
                fields={"expectedRevision": expected},
            )
        current = get_sequence(project_id)
        if current.get("revision") != expected_revision:
            raise magi_error(
                "REVISION_CONFLICT",
                "MAGI sequence changed on the server since it was loaded.",
                status_code=409,
                fields={
                    "currentRevision": current.get("revision"),
                    "expectedRevision": expected_revision,
                },
            )
    try:
        # Strict schema validation first (m1): reject malformed documents.
        validated = parse_sequence({**sequence, "projectId": project_id})
        # Asset ownership (m2/m1 A4): every clip.assetId must be a real asset in
        # this project, reported with structured codes.
        violations = validate_asset_ownership(db, project_id, validated)
        if violations["ASSET_NOT_FOUND"]:
            raise magi_error(
                "ASSET_NOT_FOUND",
                "Sequence references assets that do not exist.",
                status_code=400,
                fields={"assetIds": violations["ASSET_NOT_FOUND"]},
            )
        if violations["ASSET_PROJECT_MISMATCH"]:
            raise magi_error(
                "ASSET_PROJECT_MISMATCH",
                "Sequence references assets owned by another project.",
                status_code=400,
                fields={"assetIds": violations["ASSET_PROJECT_MISMATCH"]},
            )
        if violations["INVALID_CLIP_ASSET"]:
            raise magi_error(
                "INVALID_CLIP_ASSET",
                "Sequence contains clips without an asset reference.",
                status_code=422,
                fields={"clipIds": violations["INVALID_CLIP_ASSET"]},
            )
        try:
            saved = save_sequence(project_id, validated.model_dump())
        except Exception as exc:
            raise magi_error(
                "PERSISTENCE_FAILED",
                "MAGI sequence could not be persisted.",
                status_code=500,
                fields={"detail": str(exc)},
            ) from exc
    except ValueError as exc:
        raise magi_error(
            "INVALID_SEQUENCE",
            "MAGI sequence failed validation.",
            fields={"detail": str(exc), "errors": [str(exc)]},
        ) from exc
    return {"sequence": saved}


@router.post("/projects/{project_id}/timeline/import")
def import_timeline_asset_endpoint(
    project_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Import a project asset as a MAGI clip preserving W46 lineage (m5)."""
    result = import_timeline_asset(db, project_id, body)
    if not result.get("ok"):
        code = magi_canonical_code(str(result.get("error") or "IMPORT_FAILED"))
        raise magi_error(
            code,
            result.get("message") or "MAGI timeline import failed.",
            status_code=magi_taxonomy(code).get("status_code", 400),
            fields={"error": result.get("error")},
        )
    return result


@router.post("/projects/{project_id}/scenes/{scene_id}/timeline/export")
def export_timeline_endpoint(
    project_id: str,
    scene_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Place MAGI sequence clips on the W46 Timeline as batch-owned clips (m5).

    Body: ``{clips: [{clipId, assetId, name?, startFrame?, durationFrames?}],
    label?, batchBlockId?}``. Uses the certified W46 surface only — no
    regeneration, no fabricated candidate/execution snapshots.
    """
    clips = body.get("clips")
    if not isinstance(clips, list) or not clips:
        raise magi_error(
            "CLIPS_REQUIRED",
            "MAGI timeline export requires a non-empty 'clips' array.",
            fields={"clips": clips},
        )
    result = export_to_timeline(
        db,
        project_id,
        scene_id,
        clips,
        label=body.get("label"),
        batch_block_id=body.get("batchBlockId"),
    )
    if not result.get("ok"):
        code = magi_canonical_code(str(result.get("error") or "EXPORT_FAILED"))
        status = magi_taxonomy(code).get("status_code", 400)
        raise magi_error(
            code,
            result.get("message") or "MAGI timeline export failed.",
            status_code=status,
            fields={"error": result.get("error")},
        )
    return result


@router.get("/color/presets")
def list_color_grading_presets() -> dict[str, Any]:
    """List all available color grading presets."""
    from .color_grading import list_color_presets

    return {"presets": list_color_presets()}


@router.post("/projects/{project_id}/color/preview")
def preview_color_grade(
    project_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Preview a color grade on a clip (first 3 seconds)."""
    from .color_grading import preview_color_grade as _preview

    asset_id = body.get("asset_id") or body.get("assetId")
    preset_id = body.get("preset_id") or body.get("presetId")
    params = body.get("params") or {}
    if not asset_id:
        raise magi_error(
            "ASSET_REQUIRED",
            "Color grade preview requires an asset_id.",
            fields={"body": body},
        )
    return _preview(db, project_id, asset_id, preset_id, params)


@router.post("/projects/{project_id}/color/apply")
def apply_color_grade(
    project_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Apply a color grade to an asset. Creates a new graded Library asset."""
    from .color_grading import apply_color_grade_to_asset

    asset_id = body.get("asset_id") or body.get("assetId")
    preset_id = body.get("preset_id") or body.get("presetId")
    params = body.get("params") or {}
    if not asset_id:
        raise magi_error(
            "ASSET_REQUIRED",
            "Color grade apply requires an asset_id.",
            fields={"body": body},
        )
    result = apply_color_grade_to_asset(db, project_id, asset_id, preset_id, params)
    clip_id = body.get("clipId") or body.get("clip_id")
    if not clip_id:
        from .sequence.store import get_sequence

        seq = get_sequence(project_id)
        match = next((c for c in (seq.get("clips") or []) if c.get("assetId") == asset_id), None)
        clip_id = (match or {}).get("id")
    if clip_id:
        from .finishing import set_clip_grade

        set_clip_grade(project_id, str(clip_id), preset_id, params)
    return result


@router.get("/upscale/capabilities")
def upscale_capabilities() -> dict[str, Any]:
    """SUPPORTED IN CODE vs READY ON THIS MACHINE."""
    from .upscaling import capabilities

    return capabilities()


@router.post("/projects/{project_id}/upscale/preview")
def preview_upscale(
    project_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Preview upscale on a short segment."""
    from .upscaling import preview_upscale as _preview_upscale

    asset_id = body.get("asset_id") or body.get("assetId")
    engine = body.get("engine") or "ffmpeg-scale"
    model = body.get("model") or "lanczos"
    target_resolution = body.get("target_resolution") or "1920x1080"
    if not asset_id:
        raise magi_error(
            "ASSET_REQUIRED",
            "Upscale preview requires an asset_id.",
            fields={"body": body},
        )
    try:
        return _preview_upscale(db, project_id, asset_id, engine, model, target_resolution)
    except RuntimeError as exc:
        code = "GPU_UPSCALE_UNAVAILABLE" if "unavailable" in str(exc).lower() else "RENDER_FAILED"
        raise magi_error(code, str(exc), fields={"engine": engine, "model": model}) from exc


@router.post("/projects/{project_id}/upscale/apply")
def apply_upscale(
    project_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Apply upscaling to an asset. Creates a new upscaled Library asset."""
    from .upscaling import apply_upscale as _apply_upscale

    asset_id = body.get("asset_id") or body.get("assetId")
    engine = body.get("engine") or "ffmpeg-scale"
    model = body.get("model") or "lanczos"
    target_resolution = body.get("target_resolution") or "1920x1080"
    if not asset_id:
        raise magi_error(
            "ASSET_REQUIRED",
            "Upscale apply requires an asset_id.",
            fields={"body": body},
        )
    try:
        return _apply_upscale(db, project_id, asset_id, engine, model, target_resolution)
    except RuntimeError as exc:
        code = "GPU_UPSCALE_UNAVAILABLE" if "unavailable" in str(exc).lower() else "RENDER_FAILED"
        raise magi_error(code, str(exc), fields={"engine": engine, "model": model}) from exc


@router.post("/projects/{project_id}/audio/generate")
def generate_audio(
    project_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Queue MAGI Audio Studio music/SFX. Returns job ids — never optimistic ready."""
    try:
        from .audio_generate import enqueue_audio

        return enqueue_audio(db, project_id, body or {})
    except Exception as exc:
        raise magi_error(
            "AUDIO_GENERATION_FAILED",
            f"Audio generation failed: {exc}",
            fields={"kind": (body or {}).get("kind"), "prompt": (body or {}).get("prompt")},
        ) from exc


@router.post("/projects/{project_id}/renders")
def create_render(
    project_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from .final_render import enqueue_final_render

    try:
        return enqueue_final_render(db, project_id, body or {})
    except Exception as exc:
        raise magi_error(
            "RENDER_FAILED",
            f"MAGI render could not be queued: {exc}",
            fields={"body": body},
        ) from exc


@router.get("/projects/{project_id}/jobs/{job_id}")
def get_magi_job(project_id: str, job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from ..db import Job
    from ..codirector.unified_jobs import to_unified_dto

    job = db.get(Job, job_id)
    if not job or job.project_id != project_id:
        raise magi_error("JOB_NOT_FOUND", "MAGI job not found.", status_code=404, fields={"jobId": job_id})
    unified = to_unified_dto("studio", job)
    return {
        "jobId": job.id,
        "kind": job.kind,
        "status": job.status,
        "unifiedStatus": unified.get("status") or job.status,
        "stage": job.stage,
        "progress": job.progress,
        "message": job.message,
        "history": job.history_json,
    }
