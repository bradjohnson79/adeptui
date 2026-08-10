"""Profiles, Setup Wizard, Learning, Motion tags, Preview SSE — Adept UI addendum routes."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..db import Asset, Job, Project, Scene, get_db
from ..learning import (
    LearningState,
    continuity_suggestions,
    dumps_learning,
    parse_learning,
)
from ..preview_bus import preview_bus
from ..profiles import ProfileIn, ProfileItem, ProfileOut, normalize_motion_tag
from ..setup import (
    browse_setup_path,
    diagnose_component,
    execute_recommended_action,
    get_operation,
    get_prepare_plan,
    get_setup_status,
    refresh_component_source,
    respond_to_checkpoint,
    start_choose_install_location,
    start_link_existing_pack,
    start_prepare,
)
from ..setup.orchestrator import dismiss_update
from ..setup.paths import suggested_install_path
from ..setup_wizard import approve_install, detect_environment, load_setup_state, save_setup_state

router = APIRouter()


# ---------- Setup Wizard routes ----------


@router.get("/setup/detect")
def setup_detect():
    return detect_environment()


@router.get("/setup/state")
def setup_state():
    return load_setup_state()


@router.get("/setup/status")
def setup_status():
    return get_setup_status()


@router.post("/setup/prepare/plan")
def setup_prepare_plan():
    return get_prepare_plan()


@router.post("/setup/prepare")
def setup_prepare():
    try:
        return start_prepare()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/setup/operations/{operation_id}")
def setup_operation(operation_id: str):
    try:
        return get_operation(operation_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/setup/operations/{operation_id}/checkpoint")
def setup_operation_checkpoint(operation_id: str, body: dict):
    try:
        return respond_to_checkpoint(operation_id, body or {})
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/setup/browse-path")
def setup_browse_path(body: dict | None = None):
    payload = body or {}
    try:
        return browse_setup_path(
            mode=str(payload.get("mode") or "directory"),
            start_dir=payload.get("start_dir"),
            title=payload.get("title"),
            component_id=payload.get("component_id"),
            forced_path=payload.get("forced_path"),
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Unable to open the system file browser: {exc}") from exc


@router.get("/setup/components/{component_id}/suggested-path")
def setup_component_suggested_path(component_id: str):
    try:
        from ..setup.paths import path_selector_mode

        return {
            "component_id": component_id,
            "suggested_path": suggested_install_path(component_id),
            "path_selector": path_selector_mode(component_id),
        }
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/setup/components/{component_id}/diagnostics")
def setup_component_diagnostics(component_id: str):
    try:
        return diagnose_component(component_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/setup/components/{component_id}/recommended-action")
def setup_component_recommended_action(component_id: str):
    try:
        return execute_recommended_action(component_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/setup/components/{component_id}/refresh-source")
def setup_component_refresh_source(component_id: str):
    try:
        return refresh_component_source(component_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/setup/components/{component_id}/link-existing")
def setup_component_link_existing(component_id: str):
    try:
        return start_link_existing_pack(component_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/setup/components/{component_id}/choose-install-location")
def setup_component_choose_install_location(component_id: str):
    try:
        return start_choose_install_location(component_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/setup/download-sources")
def setup_download_sources():
    from ..setup.download_sources import detect_download_sources

    return detect_download_sources(force=True)


@router.post("/setup/download-sources/{provider}/detect")
def setup_download_sources_detect(provider: str):
    from ..setup.download_sources import detect_download_sources

    result = detect_download_sources(force=True)
    key = "github" if provider == "github" else "huggingface" if provider in ("huggingface", "hf") else None
    if not key:
        raise HTTPException(400, f"Unknown provider: {provider}")
    return {"provider": key, **result.get(key, {}), "package_managers": result.get("package_managers")}


@router.post("/setup/download-sources/{provider}/verify")
def setup_download_sources_verify(provider: str):
    return setup_download_sources_detect(provider)


@router.post("/setup/download-sources/{provider}/sign-in")
def setup_download_sources_sign_in(provider: str, body: dict | None = None):
    from ..setup.download_sources import start_cli_sign_in

    payload = body or {}
    try:
        return start_cli_sign_in(provider, launch=bool(payload.get("launch")))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/setup/download-sources/{provider}/install")
def setup_download_sources_install(provider: str, body: dict | None = None):
    from ..setup.download_sources import install_cli

    payload = body or {}
    try:
        return install_cli(
            provider,
            confirm=bool(payload.get("confirm")),
            method=payload.get("method"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/setup/sources/verify")
def setup_sources_verify(body: dict):
    from ..setup.download_sources import verify_source_url
    from ..setup.download_sources.security import SourceSecurityError

    try:
        return verify_source_url(
            url=str(body.get("url") or ""),
            component_id=body.get("component_id") or body.get("componentId"),
            revision=body.get("revision"),
            asset_name=body.get("asset_name") or body.get("assetName"),
            selected_files=body.get("selected_files") or body.get("selectedFiles"),
        )
    except SourceSecurityError as exc:
        raise HTTPException(400, exc.message) from exc


@router.post("/setup/sources/list-files")
def setup_sources_list_files(body: dict):
    from ..setup.download_sources import list_source_files
    from ..setup.download_sources.security import SourceSecurityError

    try:
        return list_source_files(str(body.get("url") or ""), revision=body.get("revision"))
    except SourceSecurityError as exc:
        raise HTTPException(400, exc.message) from exc


@router.post("/setup/components/{component_id}/source-override")
def setup_component_source_override(component_id: str, body: dict):
    from ..setup.download_sources import verify_source_url
    from ..setup.download_sources.service import apply_verified_override
    from ..setup.pack_manifests import clear_manifest_cache

    verification = body.get("verification")
    if not verification:
        verification = verify_source_url(
            url=str(body.get("url") or body.get("sourceUrl") or ""),
            component_id=component_id,
            revision=body.get("revision"),
            asset_name=body.get("asset_name") or body.get("assetName"),
            selected_files=body.get("selected_files") or body.get("selectedFiles"),
        )
    try:
        saved = apply_verified_override(component_id, verification)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    clear_manifest_cache()
    return {"ok": True, "override": saved, "verification": verification}


@router.delete("/setup/components/{component_id}/source-override")
def setup_component_clear_source_override(component_id: str):
    from ..setup.pack_manifests import clear_manifest_cache

    try:
        from ..source_manager.service import remove_component_source

        result = remove_component_source(component_id)
    except Exception:
        from ..setup.download_sources import remove_source_override
        from ..setup.pack_manifests import set_source_override

        remove_source_override(component_id)
        set_source_override(component_id, None)
        result = {"removedOverride": True}
    clear_manifest_cache()
    return {"ok": True, "component_id": component_id, "cleared": True, **result}


@router.post("/setup/components/{component_id}/update/later")
def setup_component_update_later(component_id: str):
    try:
        return dismiss_update(component_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/setup/components/{component_id}/action")
def setup_component_action(
    component_id: str,
    action: str = Form(...),
    path: str = Form(""),
    approved: bool = Form(False),
):
    if not approved:
        raise HTTPException(400, "Installation/management requires explicit approval (approved=true).")
    try:
        return approve_install(component_id, action=action, path=path or None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/setup/model-locations")
def setup_model_locations(body: dict):
    from ..setup.paths import ensure_path_exists, path_selector_mode

    state = load_setup_state()
    locs = state.setdefault("model_locations", {})
    for k, v in (body or {}).items():
        key = str(k)
        raw = str(v).strip()
        if not raw:
            locs.pop(key, None)
            continue
        path = Path(raw).expanduser()
        try:
            mode = path_selector_mode(key)
        except KeyError:
            mode = "directory" if not path.suffix else "file"
        if mode == "directory":
            path = ensure_path_exists(path, mode=mode)
        elif not path.exists():
            ensure_path_exists(path, mode=mode)
        locs[key] = str(path)
    return save_setup_state(state)


# ---------- Profiles ----------


@router.get("/profiles")
def list_profiles(kind: str | None = None, db: Session = Depends(get_db)):
    q = db.query(ProfileItem)
    if kind:
        q = q.filter(ProfileItem.kind == kind)
    rows = q.order_by(ProfileItem.updated_at.desc()).all()
    return [ProfileOut.from_row(r) for r in rows]


@router.post("/profiles/{kind}")
def create_profile(kind: str, body: ProfileIn, db: Session = Depends(get_db)):
    tag = body.tag
    if kind == "motion":
        tag = normalize_motion_tag(body.tag, body.name)
    row = ProfileItem(
        id=str(uuid.uuid4()),
        kind=kind,
        name=body.name or kind,
        tag=tag,
        category=body.category,
        description=body.description,
        data_json=json.dumps(body.data or {}),
        media_path=body.media_path or "",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ProfileOut.from_row(row)


@router.patch("/profiles/item/{item_id}")
def update_profile(item_id: str, body: ProfileIn, db: Session = Depends(get_db)):
    row = db.get(ProfileItem, item_id)
    if not row:
        raise HTTPException(404, "Profile not found")
    row.name = body.name or row.name
    if row.kind == "motion":
        row.tag = normalize_motion_tag(body.tag or row.tag, body.name or row.name)
    else:
        row.tag = body.tag
    row.category = body.category
    row.description = body.description
    row.data_json = json.dumps(body.data or {})
    if body.media_path:
        row.media_path = body.media_path
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return ProfileOut.from_row(row)


@router.delete("/profiles/item/{item_id}")
def delete_profile(item_id: str, db: Session = Depends(get_db)):
    row = db.get(ProfileItem, item_id)
    if not row:
        raise HTTPException(404, "Profile not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/profiles/{kind}/upload")
async def upload_profile_media(
    kind: str,
    file: UploadFile = File(...),
    name: str = Form(""),
    tag: str = Form(""),
    category: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    dest_dir = settings.data_dir / "profiles" / kind
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "bin").suffix or ".bin"
    dest = dest_dir / f"{uuid.uuid4().hex}{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    auto_tag = normalize_motion_tag(tag, name or Path(file.filename or "motion").stem) if kind == "motion" else tag
    row = ProfileItem(
        id=str(uuid.uuid4()),
        kind=kind,
        name=name or Path(file.filename or "asset").stem,
        tag=auto_tag,
        category=category,
        description=description,
        data_json="{}",
        media_path=str(dest),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ProfileOut.from_row(row)


@router.get("/profiles/motions/tags")
def list_motion_tags(db: Session = Depends(get_db)):
    rows = db.query(ProfileItem).filter(ProfileItem.kind == "motion").all()
    return [{"id": r.id, "tag": r.tag, "name": r.name, "media_path": r.media_path} for r in rows]


@router.post("/profiles/motions/validate-tags")
def validate_motion_tags(body: dict, db: Session = Depends(get_db)):
    text = str(body.get("text") or "")
    found = re.findall(r"#([A-Za-z0-9_-]+)", text)
    known = {r.tag.lstrip("#").lower(): r for r in db.query(ProfileItem).filter(ProfileItem.kind == "motion").all()}
    undefined = []
    resolved = []
    for t in found:
        key = t.lower()
        row = known.get(key)
        if not row:
            # also try with #
            row = known.get(("#" + t).lower())
        if row:
            resolved.append({"tag": f"#{t}", "id": row.id, "name": row.name, "media_path": row.media_path})
        else:
            undefined.append(f"#{t}")
    return {"resolved": resolved, "undefined": undefined, "warnings": [f"Undefined motion tag {u}" for u in undefined]}


# ---------- Learning ----------


@router.get("/projects/{project_id}/learning")
def get_learning(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    state = parse_learning(
        getattr(project, "learning_json", "") or "",
        getattr(project, "learning_enabled_json", "") or "",
    )
    return state.model_dump()


@router.put("/projects/{project_id}/learning")
def put_learning(project_id: str, body: dict, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    state = LearningState.model_validate(body)
    lj, ej = dumps_learning(state)
    project.learning_json = lj
    project.learning_enabled_json = ej
    project.updated_at = datetime.utcnow()
    db.commit()
    return state.model_dump()


@router.post("/projects/{project_id}/learning/reset")
def reset_learning(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    state = LearningState()
    lj, ej = dumps_learning(state)
    project.learning_json = lj
    project.learning_enabled_json = ej
    db.commit()
    return state.model_dump()


@router.get("/projects/{project_id}/learning/export")
def export_learning(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    state = parse_learning(project.learning_json, project.learning_enabled_json)
    return {"project_id": project_id, "learning": state.model_dump()}


@router.post("/projects/{project_id}/learning/import")
def import_learning(project_id: str, body: dict, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    payload = body.get("learning") or body
    state = LearningState.model_validate(payload)
    lj, ej = dumps_learning(state)
    project.learning_json = lj
    project.learning_enabled_json = ej
    db.commit()
    return state.model_dump()


@router.get("/projects/{project_id}/continuity-suggestions")
def get_continuity_suggestions(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    state = parse_learning(project.learning_json, project.learning_enabled_json)
    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.index).all()
    return {"suggestions": continuity_suggestions(scenes, state.dismissed_continuity)}


@router.post("/projects/{project_id}/continuity-suggestions/{suggestion_id}/dismiss")
def dismiss_continuity(project_id: str, suggestion_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    state = parse_learning(project.learning_json, project.learning_enabled_json)
    if suggestion_id not in state.dismissed_continuity:
        state.dismissed_continuity.append(suggestion_id)
    lj, ej = dumps_learning(state)
    project.learning_json = lj
    project.learning_enabled_json = ej
    db.commit()
    return {"ok": True}


# ---------- Live preview ----------


@router.get("/jobs/{job_id}/preview")
def get_job_preview(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    latest = preview_bus.latest_for_job(job_id)
    caps = preview_bus.capabilities_for("ltx")
    preview = None
    if latest:
        from dataclasses import asdict

        preview = asdict(latest)
    elif getattr(job, "preview_json", None):
        try:
            preview = json.loads(job.preview_json)
        except Exception:
            preview = None
    return {
        "job_id": job_id,
        "stage": getattr(job, "stage", "") or "",
        "status": job.status,
        "progress": job.progress,
        "preview": preview,
        "capabilities": caps,
    }


@router.get("/projects/{project_id}/preview/stream")
async def preview_stream(project_id: str):
    q = preview_bus.subscribe()

    async def gen():
        try:
            yield f"data: {json.dumps({'event': 'subscribed', 'project_id': project_id})}\n\n"
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield f"data: {json.dumps(item, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'event': 'ping'})}\n\n"
        finally:
            preview_bus.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/jobs/{job_id}/preview/save-frame")
def save_preview_frame(
    job_id: str,
    project_id: str = Form(...),
    tag: str = Form("preview_frame"),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    latest = preview_bus.latest_for_job(job_id)
    local = None
    if latest and latest.localPath:
        local = Path(latest.localPath)
    if not local or not local.exists():
        raise HTTPException(404, "No preview frame available to save")
    dest_dir = settings.data_dir / "projects" / project_id / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{tag}_{uuid.uuid4().hex[:8]}{local.suffix or '.png'}"
    shutil.copy2(local, dest)
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tag=tag,
        kind="image",
        filename=dest.name,
        path=str(dest),
        comfy_name="",
    )
    db.add(asset)
    db.commit()
    return {"ok": True, "asset_id": asset.id, "path": str(dest)}


# ---------- Project dashboard / duplicate / archive ----------


@router.get("/projects/{project_id}/dashboard")
def project_dashboard(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    assets = db.query(Asset).filter(Asset.project_id == project_id).all()
    jobs = db.query(Job).filter(Job.project_id == project_id).order_by(Job.created_at.desc()).limit(20).all()
    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.index).all()
    images = sum(1 for a in assets if a.kind == "image")
    videos = sum(1 for a in assets if a.kind == "video")
    audio = sum(1 for a in assets if a.kind == "audio")
    done_jobs = sum(1 for j in jobs if j.status == "done")
    failed = sum(1 for j in jobs if j.status == "failed")
    untagged = sum(1 for a in assets if not (a.tag or "").strip())
    health = []
    if failed:
        health.append({"level": "warn", "text": f"{failed} recent job(s) failed"})
    if untagged:
        health.append({"level": "info", "text": f"{untagged} uncategorized asset(s)"})
    if not assets:
        health.append({"level": "info", "text": "No library assets yet — try ImageGen or upload"})
    if not any(s.output_path for s in scenes):
        health.append({"level": "info", "text": "No scene renders yet"})
    learning = parse_learning(project.learning_json, project.learning_enabled_json)
    suggestions = continuity_suggestions(scenes, learning.dismissed_continuity)
    from .. import project_service as _project_service

    cover = _project_service.pick_cover_asset(assets)
    activity = []
    for j in jobs[:8]:
        when = j.created_at.isoformat() if j.created_at else None
        activity.append(
            {
                "id": f"job-{j.id}",
                "kind": "job",
                "when": when,
                "text": f"{j.kind} · {j.status}" + (f" — {j.message[:60]}" if j.message else ""),
            }
        )
    for a in sorted(assets, key=lambda x: x.created_at or datetime.min, reverse=True)[:6]:
        activity.append(
            {
                "id": f"asset-{a.id}",
                "kind": "asset",
                "when": a.created_at.isoformat() if a.created_at else None,
                "text": f"Added {a.kind}: {a.tag or a.filename}",
            }
        )
    activity.sort(key=lambda x: x.get("when") or "", reverse=True)

    return {
        "project_id": project_id,
        "cover_asset_id": cover.id if cover else None,
        "cover_kind": _project_service.cover_media_kind(cover),
        "counts": {
            "scenes": len(scenes),
            "assets": len(assets),
            "images": images,
            "videos": videos,
            "audio": audio,
            "jobs_recent_done": done_jobs,
            "jobs_recent_failed": failed,
            "queued": sum(1 for j in jobs if j.status in ("queued", "running", "pending")),
        },
        "recent_assets": [
            {
                "id": a.id,
                "tag": a.tag,
                "kind": a.kind,
                "filename": a.filename,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in sorted(assets, key=lambda x: x.created_at or datetime.min, reverse=True)[:12]
        ],
        "recent_jobs": [
            {
                "id": j.id,
                "kind": j.kind,
                "status": j.status,
                "message": j.message,
                "progress": j.progress,
                "output_path": j.output_path,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs[:10]
        ],
        "activity": activity[:12],
        "health": health,
        "suggestions": suggestions[:8],
        "progress": {
            "scenes_with_output": sum(1 for s in scenes if s.output_path),
            "scenes_total": len(scenes),
            "pct": int(100 * sum(1 for s in scenes if s.output_path) / max(1, len(scenes))),
        },
        "last_scene_name": scenes[-1].name if scenes else None,
    }


@router.post("/projects/{project_id}/duplicate")
def duplicate_project(
    project_id: str,
    request: Request,
    body: dict | None = None,
    db: Session = Depends(get_db),
):
    src = db.get(Project, project_id)
    if not src:
        raise HTTPException(404, "Project not found")
    body = body or {}
    try:
        from ..project_security import service as project_security

        if project_security.is_protected(db, project_id):
            token = ""
            if request is not None:
                token = project_security.extract_unlock_token_for_project(request, project_id)
            if not project_security.is_unlocked(db, project_id, token):
                auth_pw = str(body.get("authorizePassword") or "")
                if not auth_pw:
                    raise HTTPException(
                        403,
                        detail={
                            "code": "PROJECT_LOCKED",
                            "message": "This project is password protected. Unlock it before accessing production data.",
                        },
                    )
                # Verify password without creating a long-lived grant for the source
                row = project_security.get_or_create_security(db, project_id)
                params = {}
                try:
                    params = json.loads(row.password_params_json or "{}")
                except Exception:
                    params = {}
                from ..project_security.hashing import verify_password

                if not verify_password(
                    auth_pw,
                    password_hash=row.password_hash or "",
                    algorithm=row.password_algorithm or "",
                    params=params,
                ):
                    raise HTTPException(
                        401,
                        detail={"code": "UNLOCK_FAILED", "message": "The password is incorrect."},
                    )
    except HTTPException:
        raise
    except Exception:
        pass
    new_id = str(uuid.uuid4())
    clone = Project(
        id=new_id,
        name=f"{src.name} (Copy)",
        engine_default=src.engine_default,
        global_prompt=src.global_prompt,
        negative_prompt=src.negative_prompt,
        width=src.width,
        height=src.height,
        fps=src.fps,
        seed=src.seed,
        preset=src.preset,
        vram_gb=src.vram_gb,
        spatial_map_json=src.spatial_map_json,
        render_safety_json=getattr(src, "render_safety_json", "") or "",
        learning_json=getattr(src, "learning_json", "") or "",
        learning_enabled_json=getattr(src, "learning_enabled_json", "") or "",
        preview_settings_json=getattr(src, "preview_settings_json", "") or "",
        description=getattr(src, "description", "") or "",
        company=getattr(src, "company", "") or "",
        director_name=getattr(src, "director_name", "") or "",
        version=getattr(src, "version", "1.0") or "1.0",
        tags_json=getattr(src, "tags_json", "[]") or "[]",
        defaults_json=getattr(src, "defaults_json", "") or "",
        settings_json=getattr(src, "settings_json", "") or "",
    )
    db.add(clone)
    for s in db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.index).all():
        db.add(
            Scene(
                id=str(uuid.uuid4()),
                project_id=new_id,
                index=s.index,
                name=s.name,
                engine=s.engine,
                prompt=s.prompt,
                duration_sec=s.duration_sec,
                camera_note=s.camera_note,
                seed=s.seed,
                aspect_ratio=getattr(s, "aspect_ratio", "16:9") or "16:9",
                width=getattr(s, "width", 0) or 0,
                height=getattr(s, "height", 0) or 0,
                fps_mode=getattr(s, "fps_mode", "auto") or "auto",
                fps=getattr(s, "fps", 0) or 0,
                continuity_json=getattr(s, "continuity_json", "") or "",
                director_json=getattr(s, "director_json", "") or "",
            )
        )
    try:
        from ..project_security import service as project_security

        mode = str(body.get("protectionMode") or "none")
        if mode == "same_password":
            # Require re-entry so we mint a fresh salted hash (never copy hash bytes).
            pw = str(body.get("password") or body.get("authorizePassword") or "")
            project_security.apply_duplicate_protection(
                db,
                source_project_id=project_id,
                new_project_id=new_id,
                mode="new_password",
                password=pw,
                confirm_password=pw,
            )
        elif mode == "new_password":
            project_security.apply_duplicate_protection(
                db,
                source_project_id=project_id,
                new_project_id=new_id,
                mode="new_password",
                password=str(body.get("password") or ""),
                confirm_password=str(body.get("confirmPassword") or body.get("password") or ""),
            )
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        pass
    db.commit()
    return {"ok": True, "id": new_id, "name": clone.name}


@router.post("/projects/{project_id}/archive")
def archive_project(project_id: str, archived: bool = True, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.archived = 1 if archived else 0
    project.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "archived": project.archived}


@router.post("/projects/{project_id}/txt2vid")
async def enqueue_txt2vid(project_id: str, body: dict, db: Session = Depends(get_db)):
    from ..queue_worker import job_queue

    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=None,
        kind="txt2vid",
        status="queued",
        message="Queued Txt2Vid",
        params_json=json.dumps(body or {}),
    )
    db.add(job)
    db.commit()
    await job_queue.enqueue(job.id)
    db.refresh(job)
    return {
        "id": job.id,
        "project_id": job.project_id,
        "kind": job.kind,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "params_json": job.params_json,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@router.post("/projects/{project_id}/imagegen")
async def enqueue_imagegen(project_id: str, body: dict, db: Session = Depends(get_db)):
    """Legacy path — migrated to Image Product compiler (M42 W3)."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    from ..image_product.service import generate_images

    payload = dict(body or {})
    payload.setdefault("modelFamilyPreference", payload.get("model") or "zimage")
    if payload.get("edit") or payload.get("source_asset_id"):
        payload["operation"] = "image.edit"
        payload.setdefault("sourceAssetId", payload.get("source_asset_id"))
    result = generate_images(db, project_id=project_id, body=payload)
    job_id = result.get("jobId")
    job = db.get(Job, job_id) if job_id else None
    if not job:
        return {
            "id": job_id,
            "project_id": project_id,
            "kind": "imagegen",
            "status": "queued",
            "progress": 0.0,
            "message": "Queued via Image Product",
            "params_json": json.dumps(payload),
            "recommendation": result.get("recommendation"),
            "imageRuntime": result.get("imageRuntime"),
        }
    return {
        "id": job.id,
        "project_id": job.project_id,
        "kind": job.kind,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "stage": getattr(job, "stage", None),
        "params_json": job.params_json,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "recommendation": result.get("recommendation"),
        "imageRuntime": result.get("imageRuntime"),
    }


@router.get("/imagegen/models")
def imagegen_models():
    from ..imagegen_workflows import IMAGEGEN_MODELS

    return IMAGEGEN_MODELS


@router.get("/projects/{project_id}/library")
def project_library(
    project_id: str,
    q: str = "",
    scope: str = "project",
    folder: str = "",
    system_key: str = "",
    db: Session = Depends(get_db),
):
    from ..asset_graph import search_assets
    from ..project_library.service import enrich_library_item, get_library_response

    project = db.get(Project, project_id)
    if not project and scope != "global":
        raise HTTPException(404, "Project not found")

    if scope == "global":
        rows = search_assets(db, None, q, global_only=True)
    else:
        rows = search_assets(db, project_id, q, global_only=False)
        if scope == "project":
            rows = [a for a in rows if a.project_id == project_id]
    items = [enrich_library_item(a) for a in rows]
    return get_library_response(
        db,
        project_id,
        items,
        folder_id=folder or None,
        system_key=system_key or None,
    )


@router.post("/projects/{project_id}/library/migrate")
def project_library_migrate(project_id: str, db: Session = Depends(get_db)):
    from ..project_library.service import migrate_project_library

    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    try:
        return migrate_project_library(db, project_id)
    except ValueError as exc:
        if str(exc) == "PROJECT_NOT_FOUND":
            raise HTTPException(404, "Project not found") from exc
        raise HTTPException(400, str(exc)) from exc


@router.post("/projects/{project_id}/library/repair")
def project_library_repair(project_id: str, db: Session = Depends(get_db)):
    from ..project_library.service import repair_library

    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    try:
        return repair_library(db, project_id)
    except ValueError as exc:
        if str(exc) == "PROJECT_NOT_FOUND":
            raise HTTPException(404, "Project not found") from exc
        raise HTTPException(400, str(exc)) from exc


@router.post("/projects/{project_id}/library/resolve-path")
def project_library_resolve_path(project_id: str, body: dict, db: Session = Depends(get_db)):
    from ..project_library.service import resolve_path

    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    folder_id = body.get("folderId") or body.get("folder_id") or None
    system_key = body.get("systemKey") or body.get("system_key") or None
    path = resolve_path(db, project_id, folder_id=folder_id, system_key=system_key)
    return {
        "projectId": project_id,
        "folderId": folder_id,
        "systemKey": system_key,
        "libraryPath": path,
    }


@router.post("/projects/{project_id}/library/resolve")
def project_library_resolve(project_id: str, body: dict, db: Session = Depends(get_db)):
    from ..project_library.codirector import resolve_library_location

    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    return resolve_library_location(
        db,
        project_id,
        path=body.get("path") or None,
        system_key=body.get("systemKey") or body.get("system_key") or None,
        query=body.get("query") or body.get("q") or None,
    )


@router.get("/projects/{project_id}/library/codirector-context")
def project_library_codirector_context(project_id: str, limit: int = 8, db: Session = Depends(get_db)):
    from ..project_library.codirector import get_library_context

    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    return get_library_context(db, project_id, recent_limit=max(1, min(limit, 20)))


@router.post("/projects/{project_id}/library/preflight")
def project_library_preflight(project_id: str, body: dict, db: Session = Depends(get_db)):
    from ..project_library.codirector import storage_preflight

    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    task = body.get("task")
    if not task:
        raise HTTPException(400, "task is required")
    return storage_preflight(
        db,
        project_id,
        task=str(task),
        system_key=body.get("systemKey") or body.get("system_key") or None,
        path=body.get("path") or None,
        entity_type=body.get("entityType") or body.get("entity_type") or None,
        entity_name=body.get("entityName") or body.get("entity_name") or None,
        entity_id=body.get("entityId") or body.get("entity_id") or None,
        filename_hint=body.get("filenameHint") or body.get("expectedName") or None,
    )


@router.patch("/assets/{asset_id}/library")
def patch_asset_library(asset_id: str, body: dict, db: Session = Depends(get_db)):
    from ..project_library.service import assign_asset, enrich_library_item

    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")

    system_key = body.get("systemKey") or body.get("system_key")
    folder_id = body.get("folderId") or body.get("folder_id")
    entity_type = body.get("entityType") or body.get("entity_type")
    entity_name = body.get("entityName") or body.get("entity_name")
    entity_id = body.get("entityId") or body.get("entity_id")
    override = bool(body.get("override"))
    hints = body.get("hints") if isinstance(body.get("hints"), dict) else None

    meta = assign_asset(
        db,
        asset,
        system_key=system_key,
        folder_id=folder_id,
        entity_type=entity_type,
        entity_name=entity_name,
        entity_id=entity_id,
        classified_by="manual",
        override=override or bool(system_key or folder_id),
        hints=hints,
    )
    return {
        "ok": True,
        "asset": enrich_library_item(asset),
        "meta": meta.to_dict(),
    }


@router.patch("/assets/{asset_id}/meta")
def patch_asset_meta(asset_id: str, body: dict, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    for key in ("tag", "scope", "labels_json", "prompt_meta_json", "shared_project_ids_json"):
        if key in body and body[key] is not None:
            val = body[key]
            setattr(asset, key, val if not isinstance(val, (list, dict)) else json.dumps(val))
    db.commit()
    return {"ok": True, "id": asset.id}


@router.post("/assets/{asset_id}/promote-global")
def promote_asset_global(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    asset.scope = "global"
    db.commit()
    return {"ok": True, "scope": "global"}


@router.get("/assets/{asset_id}/graph")
def asset_graph_view(asset_id: str, db: Session = Depends(get_db)):
    from ..asset_graph import AssetVersion, neighbors

    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    edges = neighbors(db, asset_id)
    versions = (
        db.query(AssetVersion)
        .filter(AssetVersion.asset_id == asset_id)
        .order_by(AssetVersion.version.desc())
        .all()
    )
    related = []
    for e in edges:
        other = db.get(Asset, e["other_id"])
        if other:
            related.append(
                {
                    "id": other.id,
                    "tag": other.tag,
                    "kind": other.kind,
                    "filename": other.filename,
                    "relation": e["relation"],
                }
            )
    return {
        "asset": {
            "id": asset.id,
            "tag": asset.tag,
            "kind": asset.kind,
            "filename": asset.filename,
            "parent_asset_id": getattr(asset, "parent_asset_id", None),
        },
        "related": related,
        "versions": [
            {
                "id": v.id,
                "version": v.version,
                "op": v.op,
                "seed": v.seed,
                "model": v.model,
                "path": v.path,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ],
    }


@router.post("/assets/edges")
def create_asset_edge(body: dict, db: Session = Depends(get_db)):
    from ..asset_graph import add_edge

    from_id = body.get("from_id")
    to_id = body.get("to_id")
    relation = body.get("relation") or "related"
    if not from_id or not to_id:
        raise HTTPException(400, "from_id and to_id required")
    row = add_edge(db, from_id, to_id, relation, body.get("meta"))
    db.commit()
    return {"ok": True, "id": row.id}


@router.get("/marketplace")
def marketplace_list(category: str | None = None, base_model: str | None = None, q: str = ""):
    from ..marketplace import list_catalog

    return list_catalog(category=category, base_model=base_model, q=q)


@router.post("/marketplace/{item_id}/install")
def marketplace_install(item_id: str, path: str = Form(""), approved: bool = Form(False)):
    from ..marketplace import approve_install

    if not approved:
        raise HTTPException(400, "Marketplace install requires explicit approval (approved=true).")
    try:
        return approve_install(item_id, path=path or "", approved=True)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/lora/stack")
def lora_stack_get(scope: str = "global"):
    from ..marketplace import get_stack

    return {"scope": scope, "stack": get_stack(scope)}


@router.put("/lora/stack")
def lora_stack_put(body: dict):
    from ..marketplace import set_stack

    scope = body.get("scope") or "global"
    stack = body.get("stack") or []
    return {"scope": scope, "stack": set_stack(scope, stack)}


@router.post("/projects/{project_id}/promote")
def promote_asset(project_id: str, body: dict, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    asset_id = body.get("asset_id")
    target = body.get("target")
    scene_id = body.get("scene_id")
    asset = db.get(Asset, asset_id) if asset_id else None
    if not asset:
        raise HTTPException(404, "Asset not found")
    applied = []
    if target == "scene_new":
        count = db.query(Scene).filter(Scene.project_id == project_id).count()
        scene = Scene(
            id=str(uuid.uuid4()),
            project_id=project_id,
            index=count,
            name=body.get("name") or f"From {asset.tag or asset.filename}",
            engine=project.engine_default,
            prompt=body.get("prompt") or "",
            duration_sec=float(body.get("duration_sec") or 5),
            start_asset_id=asset.id if asset.kind == "image" else None,
        )
        if asset.kind == "video":
            scene.output_path = asset.path
        db.add(scene)
        applied.append(f"scene:{scene.id}")
    elif target in ("scene_start", "scene_middle", "scene_end") and scene_id:
        scene = db.get(Scene, scene_id)
        if not scene or scene.project_id != project_id:
            raise HTTPException(404, "Scene not found")
        field = {
            "scene_start": "start_asset_id",
            "scene_middle": "middle_asset_id",
            "scene_end": "end_asset_id",
        }[target]
        setattr(scene, field, asset.id)
        applied.append(field)
    elif target == "tag" and body.get("tag"):
        asset.tag = body["tag"]
        applied.append("tag")
    elif target == "profile":
        from ..profiles import ProfileItem

        row = ProfileItem(
            id=str(uuid.uuid4()),
            kind=body.get("profile_kind") or "character",
            name=body.get("name") or asset.tag or asset.filename,
            tag=body.get("tag") or asset.tag or "",
            category=body.get("category") or "",
            description=body.get("description") or "",
            media_path=asset.path,
            data_json=json.dumps({"from_asset_id": asset.id}),
        )
        db.add(row)
        applied.append(f"profile:{row.id}")
    else:
        raise HTTPException(400, f"Unknown promote target: {target}")
    project.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "applied": applied}


# ---------- Spatial Scene Engine ----------


@router.get("/projects/{project_id}/scenes/{scene_id}/spatial")
def get_scene_spatial(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    scene = db.get(Scene, scene_id)
    if not project or not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    from ..spatial_scene import get_or_create_spatial, parse_spatial_doc

    row = get_or_create_spatial(db, project_id, scene_id)
    doc = parse_spatial_doc(row, project.spatial_map_json)
    return {
        "id": row.id,
        "project_id": project_id,
        "scene_id": scene_id,
        "guidance": row.guidance,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "doc": doc.model_dump(),
    }


@router.put("/projects/{project_id}/scenes/{scene_id}/spatial")
def put_scene_spatial(project_id: str, scene_id: str, body: dict, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    scene = db.get(Scene, scene_id)
    if not project or not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    from ..spatial_scene import SpatialSceneDoc, get_or_create_spatial, save_spatial_doc

    row = get_or_create_spatial(db, project_id, scene_id)
    payload = body.get("doc") if isinstance(body.get("doc"), dict) else body
    doc = SpatialSceneDoc.model_validate(payload)
    if body.get("guidance"):
        doc.guidance = body["guidance"]
    save_spatial_doc(db, row, doc)
    # keep project fallback in sync for legacy consumers
    project.spatial_map_json = doc.model_dump_json()
    project.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": row.id, "doc": doc.model_dump()}


@router.post("/projects/{project_id}/scenes/{scene_id}/spatial/prompt")
def spatial_prompt(project_id: str, scene_id: str, body: dict | None = None, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    scene = db.get(Scene, scene_id)
    if not project or not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    from ..profiles import ProfileItem
    from ..spatial_prompt_builder import assemble_prompt_layers, flatten_layers, guidance_hint
    from ..spatial_scene import get_or_create_spatial, parse_spatial_doc

    row = get_or_create_spatial(db, project_id, scene_id)
    doc = parse_spatial_doc(row, project.spatial_map_json)
    body = body or {}
    state_id = body.get("state_id") or doc.active_state_id
    blurbs = {}
    for a in doc.avatars:
        if a.profile_id:
            p = db.get(ProfileItem, a.profile_id)
            if p:
                blurbs[a.profile_id] = f"{p.name}. {p.description}".strip()
    layers = assemble_prompt_layers(doc, state_id=state_id, profile_blurbs=blurbs, style=body.get("style") or "")
    if body.get("layers"):
        for k, v in body["layers"].items():
            if hasattr(layers, k) and v is not None:
                setattr(layers, k, v)
    positive, negative = flatten_layers(layers)
    return {
        "layers": layers.model_dump(),
        "positive": positive,
        "negative": negative,
        "guidance": doc.guidance,
        "guidance_hint": guidance_hint(doc.guidance),
        "state_id": state_id,
    }


@router.post("/projects/{project_id}/scenes/{scene_id}/spatial/generate")
async def spatial_generate(project_id: str, scene_id: str, body: dict | None = None, db: Session = Depends(get_db)):
    from ..queue_worker import job_queue
    from ..spatial_prompt_builder import assemble_prompt_layers, flatten_layers, guidance_hint
    from ..spatial_scene import get_or_create_spatial, parse_spatial_doc
    from ..profiles import ProfileItem

    project = db.get(Project, project_id)
    scene = db.get(Scene, scene_id)
    if not project or not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    body = body or {}
    row = get_or_create_spatial(db, project_id, scene_id)
    doc = parse_spatial_doc(row, project.spatial_map_json)
    state_id = body.get("state_id") or doc.active_state_id
    blurbs = {}
    for a in doc.avatars:
        if a.profile_id:
            p = db.get(ProfileItem, a.profile_id)
            if p:
                blurbs[a.profile_id] = f"{p.name}. {p.description}".strip()
    layers = assemble_prompt_layers(doc, state_id=state_id, profile_blurbs=blurbs, style=body.get("style") or "")
    if body.get("layers"):
        for k, v in body["layers"].items():
            if hasattr(layers, k) and v is not None:
                setattr(layers, k, v)
    positive, negative = flatten_layers(layers)
    hint = guidance_hint(doc.guidance)
    positive = f"{positive}\n\n{hint}".strip()
    camera_id = body.get("camera_avatar_id")
    params = {
        "prompt": positive,
        "negative": negative or project.negative_prompt,
        "style": body.get("style") or "",
        "model": body.get("model") or "auto",
        "width": int(body.get("width") or project.width or 1024),
        "height": int(body.get("height") or project.height or 1024),
        "tag": "spatial_shot",
        "labels": ["spatial", "storyboard"],
        "spatial_scene_id": row.id,
        "spatial_state_id": state_id,
        "camera_avatar_id": camera_id,
        "scene_id": scene_id,
        "guidance": doc.guidance,
    }
    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        scene_id=scene_id,
        kind="imagegen",
        status="queued",
        message="Queued spatial ImageGen",
        params_json=json.dumps(params),
    )
    db.add(job)
    db.commit()
    await job_queue.enqueue(job.id)
    return {"id": job.id, "status": job.status, "params": params}


@router.post("/projects/{project_id}/scenes/{scene_id}/spatial/send-director")
def spatial_send_director(project_id: str, scene_id: str, body: dict | None = None, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    scene = db.get(Scene, scene_id)
    if not project or not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    from ..spatial_prompt_builder import assemble_prompt_layers, flatten_layers
    from ..spatial_scene import get_or_create_spatial, parse_spatial_doc, spatial_doc_summary

    body = body or {}
    row = get_or_create_spatial(db, project_id, scene_id)
    doc = parse_spatial_doc(row, project.spatial_map_json)
    state_id = body.get("state_id") or doc.active_state_id
    layers = assemble_prompt_layers(doc, state_id=state_id)
    positive, _neg = flatten_layers(layers)
    asset_id = body.get("asset_id")
    create_new = bool(body.get("create_new_scene"))
    applied = []
    target = scene
    if create_new:
        count = db.query(Scene).filter(Scene.project_id == project_id).count()
        target = Scene(
            id=str(uuid.uuid4()),
            project_id=project_id,
            index=count,
            name=body.get("name") or f"Spatial {doc.states[0].name if doc.states else 'State'}",
            engine=project.engine_default,
            prompt=positive[:4000],
            duration_sec=float(body.get("duration_sec") or 5),
            camera_note=spatial_doc_summary(doc)[:1000],
            continuity_json=scene.continuity_json or "",
        )
        db.add(target)
        applied.append(f"scene:{target.id}")
    else:
        if body.get("update_prompt", True):
            target.prompt = positive[:4000]
            applied.append("prompt")
        target.camera_note = (target.camera_note + " | " if target.camera_note else "") + spatial_doc_summary(doc)[:800]
        applied.append("camera_note")
    if asset_id:
        slot = body.get("slot") or "start"
        field = {"start": "start_asset_id", "middle": "middle_asset_id", "end": "end_asset_id"}.get(slot, "start_asset_id")
        setattr(target, field, asset_id)
        applied.append(field)
        try:
            from ..asset_graph import add_edge

            add_edge(db, asset_id, target.id, "used_in_director", {"from": "spatial", "state_id": state_id})
        except Exception:
            pass
    project.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "applied": applied, "scene_id": target.id}


@router.post("/projects/{project_id}/scenes/{scene_id}/spatial/commands")
def spatial_commands(project_id: str, scene_id: str, body: dict, db: Session = Depends(get_db)):
    """Co-Director spatial commands: return proposed mutations; apply only if approved=true."""
    project = db.get(Project, project_id)
    scene = db.get(Scene, scene_id)
    if not project or not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    from ..spatial_scene import (
        apply_avatar_mutations,
        get_or_create_spatial,
        parse_spatial_doc,
        save_spatial_doc,
    )

    row = get_or_create_spatial(db, project_id, scene_id)
    doc = parse_spatial_doc(row, project.spatial_map_json)
    text = (body.get("command") or "").strip().lower()
    mutations: list[dict] = []
    # Lightweight keyword proposals (honest heuristic, not silent apply)
    if "camera" in text and ("add" in text or "create" in text or "master" in text):
        mutations.append(
            {
                "op": "add",
                "entity_type": "camera",
                "label": "C1",
                "x": doc.width * 0.3,
                "y": doc.height * 0.7,
            }
        )
    if ("face" in text and "one another" in text) or "face each other" in text:
        chars = [a for a in doc.avatars if a.entity_type == "character"]
        if len(chars) >= 2:
            mutations.append(
                {
                    "op": "update",
                    "id": chars[0].id,
                    "patch": {"facing": {"mode": "face_avatar", "target_avatar_id": chars[1].id}},
                }
            )
            mutations.append(
                {
                    "op": "update",
                    "id": chars[1].id,
                    "patch": {"facing": {"mode": "face_avatar", "target_avatar_id": chars[0].id}},
                }
            )
    if re.search(r"place|put|add", text) and "character" not in [m.get("entity_type") for m in mutations]:
        # generic character add if a name-like token present
        m = re.search(r"(?:place|put)\s+([a-z][a-z\-']+)", text)
        if m and m.group(1) not in ("the", "a", "an", "near", "beside"):
            mutations.append(
                {
                    "op": "add",
                    "entity_type": "character",
                    "label": m.group(1).title(),
                    "x": doc.width * 0.4,
                    "y": doc.height * 0.5,
                }
            )
    if not mutations:
        mutations.append({"op": "noop", "message": "No map mutations inferred. Be more specific or edit the map manually."})

    applied = False
    if body.get("approved") and mutations and mutations[0].get("op") != "noop":
        doc = apply_avatar_mutations(doc, [m for m in mutations if m.get("op") != "noop"])
        save_spatial_doc(db, row, doc)
        applied = True
    return {
        "proposed_mutations": mutations,
        "applied": applied,
        "message": "Review mutations before apply. Set approved=true to commit.",
        "doc": doc.model_dump() if applied else None,
    }


# ---------- Script & Storyboard ----------


@router.get("/projects/{project_id}/script")
def get_script(project_id: str, db: Session = Depends(get_db)):
    from ..script_storyboard import (
        PanelOut,
        SegmentOut,
        ScriptDocRow,
        ScriptSegmentRow,
        StoryboardPanelRow,
        get_or_create_script_doc,
    )

    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    doc = get_or_create_script_doc(db, project_id)
    segs = (
        db.query(ScriptSegmentRow)
        .filter(ScriptSegmentRow.doc_id == doc.id)
        .order_by(ScriptSegmentRow.index.asc())
        .all()
    )
    panels = (
        db.query(StoryboardPanelRow)
        .filter(StoryboardPanelRow.doc_id == doc.id)
        .order_by(StoryboardPanelRow.panel_index.asc())
        .all()
    )
    return {
        "doc": {
            "id": doc.id,
            "project_id": doc.project_id,
            "title": doc.title,
            "revision": doc.revision,
            "meta": json.loads(doc.meta_json or "{}") or {},
        },
        "segments": [SegmentOut.from_row(s).model_dump() for s in segs],
        "panels": [PanelOut.from_row(p).model_dump() for p in panels],
    }


@router.post("/projects/{project_id}/script/import")
def import_script(project_id: str, body: dict, db: Session = Depends(get_db)):
    from ..script_storyboard import SegmentOut, import_plain_text

    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    text = body.get("text") or ""
    segs = import_plain_text(db, project_id, text)
    return {"ok": True, "count": len(segs), "segments": [SegmentOut.from_row(s).model_dump() for s in segs]}


@router.post("/projects/{project_id}/script/segments")
def create_segment(project_id: str, body: dict, db: Session = Depends(get_db)):
    from ..script_storyboard import ScriptSegmentRow, SegmentOut, get_or_create_script_doc

    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    doc = get_or_create_script_doc(db, project_id)
    idx = db.query(ScriptSegmentRow).filter(ScriptSegmentRow.doc_id == doc.id).count()
    row = ScriptSegmentRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        doc_id=doc.id,
        scene_id=body.get("scene_id"),
        index=idx,
        segment_number=idx + 1,
        segment_type=body.get("segment_type") or "action",
        speaker=body.get("speaker") or "",
        text=body.get("text") or "",
        action=body.get("action") or "",
        dialogue=body.get("dialogue") or "",
        emotion=body.get("emotion") or "",
        location=body.get("location") or "",
        time_of_day=body.get("time_of_day") or "",
        characters_json=json.dumps(body.get("characters") or []),
        duration_est=float(body.get("duration_est") or 3),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return SegmentOut.from_row(row).model_dump()


@router.patch("/projects/{project_id}/script/segments/{segment_id}")
def patch_segment(project_id: str, segment_id: str, body: dict, db: Session = Depends(get_db)):
    from ..script_storyboard import (
        ScriptSegmentRow,
        SegmentOut,
        mark_panels_script_changed,
        visual_change_heuristic,
    )

    row = db.get(ScriptSegmentRow, segment_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Segment not found")
    old = ScriptSegmentRow(
        id=row.id,
        project_id=row.project_id,
        doc_id=row.doc_id,
        action=row.action,
        text=row.text,
        dialogue=row.dialogue,
        location=row.location,
        segment_type=row.segment_type,
    )
    for key in (
        "segment_type",
        "speaker",
        "text",
        "action",
        "dialogue",
        "emotion",
        "location",
        "time_of_day",
        "status",
        "scene_id",
        "spatial_scene_id",
        "continuity_json",
    ):
        if key in body and body[key] is not None:
            setattr(row, key, body[key])
    if "characters" in body:
        row.characters_json = json.dumps(body["characters"] or [])
    if "duration_est" in body:
        row.duration_est = float(body["duration_est"])
    row.revision = (row.revision or 1) + 1
    row.updated_at = datetime.utcnow()
    visual = visual_change_heuristic(
        old,
        row.text or "",
        row.action or "",
        row.dialogue or "",
    )
    mark_panels_script_changed(db, row.id, visual)
    db.commit()
    db.refresh(row)
    return {"segment": SegmentOut.from_row(row).model_dump(), "visual_change": visual}


@router.post("/projects/{project_id}/storyboard/panels")
def create_panel(project_id: str, body: dict, db: Session = Depends(get_db)):
    from ..script_storyboard import PanelOut, StoryboardPanelRow, get_or_create_script_doc

    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    doc = get_or_create_script_doc(db, project_id)
    segment_id = body.get("segment_id")
    if not segment_id:
        raise HTTPException(400, "segment_id required")
    count = db.query(StoryboardPanelRow).filter(StoryboardPanelRow.segment_id == segment_id).count()
    row = StoryboardPanelRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        doc_id=doc.id,
        segment_id=segment_id,
        panel_index=count,
        label=body.get("label") or f"Panel {chr(65 + count)}",
        style=body.get("style") or "Pencil storyboard",
        shot_size=body.get("shot_size") or "",
        lens=body.get("lens") or "",
        notes=body.get("notes") or "",
        prompt=body.get("prompt") or "",
        spatial_state_id=body.get("spatial_state_id"),
        camera_avatar_id=body.get("camera_avatar_id"),
        status="missing",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return PanelOut.from_row(row).model_dump()


@router.patch("/projects/{project_id}/storyboard/panels/{panel_id}")
def patch_panel(project_id: str, panel_id: str, body: dict, db: Session = Depends(get_db)):
    from ..script_storyboard import PanelOut, StoryboardPanelRow

    row = db.get(StoryboardPanelRow, panel_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Panel not found")
    for key in (
        "label",
        "style",
        "shot_size",
        "lens",
        "notes",
        "prompt",
        "approval",
        "script_sync_status",
        "status",
        "asset_id",
        "spatial_state_id",
        "camera_avatar_id",
    ):
        if key in body and body[key] is not None:
            setattr(row, key, body[key])
    if "duration_est" in body:
        row.duration_est = float(body["duration_est"])
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return PanelOut.from_row(row).model_dump()


@router.post("/projects/{project_id}/storyboard/generate")
async def storyboard_generate(project_id: str, body: dict, db: Session = Depends(get_db)):
    from ..queue_worker import job_queue
    from ..storyboard_jobs import prepare_storyboard_generate

    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    try:
        prepared = prepare_storyboard_generate(db, project_id, body or {})
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await job_queue.enqueue(prepared["job_id"])
    return {
        "job_id": prepared["job_id"],
        "panel_id": prepared["panel_id"],
        "status": prepared["status"],
    }


@router.post("/projects/{project_id}/storyboard/send-director")
def storyboard_send_director(project_id: str, body: dict, db: Session = Depends(get_db)):
    from ..asset_graph import add_edge
    from ..script_storyboard import ScriptSegmentRow, StoryboardPanelRow

    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    panel_ids = body.get("panel_ids") or []
    approved_only = bool(body.get("approved_only"))
    q = db.query(StoryboardPanelRow).filter(StoryboardPanelRow.project_id == project_id)
    if panel_ids:
        q = q.filter(StoryboardPanelRow.id.in_(panel_ids))
    panels = q.order_by(StoryboardPanelRow.panel_index.asc()).all()
    if approved_only:
        panels = [p for p in panels if p.approval == "approved"]
    created = []
    for p in panels:
        if not p.asset_id:
            continue
        seg = db.get(ScriptSegmentRow, p.segment_id)
        count = db.query(Scene).filter(Scene.project_id == project_id).count()
        scene = Scene(
            id=str(uuid.uuid4()),
            project_id=project_id,
            index=count,
            name=p.label or (seg and f"Seg {seg.segment_number}") or "Storyboard",
            engine=project.engine_default,
            prompt=p.prompt or (seg.text if seg else ""),
            duration_sec=float(p.duration_est or (seg.duration_est if seg else 3) or 3),
            start_asset_id=p.asset_id,
            camera_note=f"storyboard:{p.id}; segment:{p.segment_id}",
        )
        db.add(scene)
        p.status = "in_director"
        try:
            add_edge(db, p.asset_id, scene.id, "used_in_director", {"panel_id": p.id, "segment_id": p.segment_id})
            if seg:
                add_edge(db, seg.id, p.id, "storyboard_of", {})
        except Exception:
            pass
        created.append(scene.id)
    project.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "created_scene_ids": created}
