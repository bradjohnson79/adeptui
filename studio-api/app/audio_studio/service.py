"""Audio Studio orchestration — wraps real generation; persists batches/mix."""

from __future__ import annotations

import secrets
import zlib
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import store
from .contracts import AudioCreativeBrief
from .provider_resolver import resolve_execution

# Intentional creative offsets so a 3-pack is not three near-clones of one seed/prompt.
_MUSIC_VARIATIONS = (
    "Variation A — warmer intimate arrangement, softer percussion, closer mic feel",
    "Variation B — brighter melodic lead, clearer midrange lift, slightly higher energy",
    "Variation C — broader cinematic swell, richer low end, wider stereo bed",
)
_SFX_VARIATIONS = (
    "Variation A — closer perspective, sharper transient, drier room",
    "Variation B — mid-distance, moderate body, light natural space",
    "Variation C — farther / heavier body, more air and decay",
)
_AMBIENCE_VARIATIONS = (
    "Variation A — sparse and airy, lower density, gentle movement",
    "Variation B — balanced bed, steady mid activity, soft detail",
    "Variation C — denser atmosphere, richer texture, more motion",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _variation_hint(kind: str, index: int) -> str:
    pool = _MUSIC_VARIATIONS if kind == "music" else _AMBIENCE_VARIATIONS if kind == "ambience" else _SFX_VARIATIONS
    return pool[index % len(pool)]


def _candidate_seed(batch_id: str, candidate_id: str, index: int) -> int:
    """Distinct non-zero seed per candidate. Never reuse a fixed studio-wide default."""
    material = f"{batch_id}:{candidate_id}:{index}:{secrets.token_hex(4)}".encode("utf-8")
    seed = zlib.adler32(material) & 0x7FFFFFFF
    return seed or (index + 1) * 9973


def workspace(db: Session, project_id: str) -> dict[str, Any]:
    from ..db import Project

    if not db.get(Project, project_id):
        raise _err("NOT_FOUND", "Project not found.", 404)
    batches = store.list_batches(project_id)
    mix = store.get_mix(project_id)
    draft = store.get_draft(project_id)
    resolution = resolve_execution("music")
    library = _library_audio(db, project_id)
    return {
        "projectId": project_id,
        "tabs": ["music", "sfx", "ambience", "library"],
        "batches": batches,
        "mix": mix,
        "draft": draft,
        "providers": resolution,
        "library": library,
        "mock": False,
    }


def _library_audio(db: Session, project_id: str) -> list[dict[str, Any]]:
    try:
        from ..project_library import service as lib

        items = lib.list_items(db, project_id) if hasattr(lib, "list_items") else []
        if isinstance(items, dict):
            items = items.get("items") or []
        return [
            i
            for i in items
            if str(i.get("kind") or i.get("assetKind") or "").lower() == "audio"
            or str(i.get("libraryKey") or "").startswith("audio.")
        ]
    except Exception:
        from ..db import Asset

        rows = db.query(Asset).filter(Asset.project_id == project_id, Asset.kind == "audio").limit(200).all()
        return [
            {
                "id": r.id,
                "name": r.name or r.tag or r.id,
                "kind": "audio",
                "path": r.path,
                "tag": r.tag,
            }
            for r in rows
        ]


def _item_label(kind: str, index: int) -> str:
    prefix = "Track" if kind == "music" else "Sound" if kind == "sfx" else "Bed"
    return f"{prefix} {index}"


def _batch_progress(kind: str, candidates: list[dict[str, Any]], *, status: str) -> dict[str, Any]:
    total = max(1, len(candidates))
    completed = sum(1 for c in candidates if c.get("status") in ("ready", "failed", "selected", "approved"))
    generating_idx = next((i for i, c in enumerate(candidates) if c.get("status") == "generating"), None)
    current = (generating_idx + 1) if generating_idx is not None else min(completed + 1, total)
    if status == "complete":
        current = total
    percent = int(round(100.0 * completed / total)) if status == "complete" or completed else (
        int(round(100.0 * max(0, completed) / total))
    )
    if status == "running" and completed == 0:
        percent = 0
    return {
        "status": status,
        "completed": completed,
        "total": total,
        "percent": max(0, min(100, percent)),
        "current": current,
        "label": (
            f"Complete — {completed} of {total}"
            if status == "complete"
            else f"Generating {_item_label(kind, current).lower()} ({completed} of {total} done)"
        ),
    }


def _prepare_generation(
    project_id: str,
    *,
    kind: str,
    brief: dict[str, Any] | None,
    candidate_count: int,
    preferred_provider: str | None,
    allow_provider_switch: bool,
    allow_cpu_fallback: bool = False,
) -> tuple[AudioCreativeBrief, dict[str, Any], str, float, int, str]:
    if kind not in ("music", "sfx", "ambience"):
        raise _err("INVALID_KIND", f"Unknown kind: {kind}")
    brief_obj = AudioCreativeBrief(project_id=project_id, **(brief or {}))
    if not brief_obj.prompt.strip():
        raise _err("PROMPT_REQUIRED", "A creative prompt is required.")
    if kind == "ambience":
        if brief is None or brief.get("loop_required") is None:
            brief_obj.loop_required = True

    allow_cpu = bool(allow_cpu_fallback or (brief or {}).get("allow_cpu_fallback") or (brief or {}).get("allowCpuFallback"))
    # Production Dock preferences → resolver (no silent CPU; provenance-aware).
    try:
        from ..production_control.resolve import resolve_modality
        from ..production_control.store import get_user_preferences

        dock_user = get_user_preferences()
        if dock_user.cpuFallbackPolicy == "disabled":
            allow_cpu = False
        elif dock_user.cpuFallbackPolicy == "lightweight_only" and kind == "music":
            allow_cpu = False
        dock_sel = resolve_modality(project_id, "audio")
        if dock_sel.activeModelId in ("ace-step-local", "mmaudio-local") and not dock_sel.executable:
            raise _err(
                "NO_EXECUTABLE_ROUTE",
                dock_sel.blockedReason or "No executable audio route from Production Dock.",
                409,
            )
    except HTTPException:
        raise
    except Exception:
        pass
    resolution = resolve_execution(
        "music" if kind == "music" else "sfx",
        preferred_provider=preferred_provider,
        allow_switch=allow_provider_switch,
        allow_cpu_fallback=allow_cpu,
    )
    rec = resolution.get("recommendation") or {}
    mode = str(rec.get("mode") or "")
    if mode == "blocked_cpu":
        raise _err(
            "GPU_REQUIRED",
            str(
                rec.get("reason")
                or (
                    "GPU acceleration was requested, but the active worker is using "
                    "CPU-only PyTorch. Generation has been stopped to prevent an "
                    "unexpected CPU execution path."
                )
            ),
            409,
        )
    if mode == "unavailable":
        raise _err(
            "RUNTIME_UNAVAILABLE",
            str(rec.get("reason") or "No ready Audio Studio runtime for this kind."),
            409,
        )
    gen_kind = "music" if kind == "music" else ("ambience" if kind == "ambience" else "sfx")
    if kind == "sfx" and brief_obj.category:
        cat = str(brief_obj.category).lower()
        if cat in ("foley", "reaction", "ambience", "room_tone", "transition"):
            gen_kind = cat if cat != "room_tone" else "sfx"
    duration = float(brief_obj.duration_seconds or (12.0 if kind == "music" else (12.0 if kind == "ambience" else 4.0)))
    # Keep candidate batches snappy; long scores can be refined after approve.
    if kind == "music":
        duration = max(4.0, min(duration, 20.0))
    elif kind == "ambience":
        duration = max(4.0, min(duration, 20.0))
    else:
        duration = max(1.0, min(duration, 12.0))
    wanted = max(1, min(int(candidate_count), 6))

    prompt = brief_obj.prompt
    pi = (brief or {}).get("promptIntelligence") if isinstance(brief, dict) else None
    if (brief or {}).get("runPromptIntelligence") and prompt and not (isinstance(pi, dict) and pi.get("finalProviderPrompt")):
        try:
            from ..codirector.prompt_intelligence.models import ModulesEnabled, PromptIntelligenceRequest
            from ..codirector.prompt_intelligence.pipeline import enhance as pi_enhance

            domain = "music" if kind == "music" else ("sfx" if kind == "sfx" else "audio")
            result = pi_enhance(
                PromptIntelligenceRequest(
                    creatorPrompt=prompt,
                    domain=domain,  # type: ignore[arg-type]
                    providerId="audio-studio",
                    modulesEnabled=ModulesEnabled(
                        productionRefinement=True,
                        cinematicRefinement=False,
                        motionRefinement=False,
                        audioRefinement=True,
                        characterContinuity=False,
                        providerOptimization=True,
                        languageModules=["en"],
                    ),
                )
            )
            pi = result.record.model_dump(mode="json")
        except Exception:
            pi = None
    if isinstance(pi, dict) and pi.get("finalProviderPrompt"):
        prompt = str(pi["finalProviderPrompt"])
        # Attach for batch persistence without mutating pydantic brief schema unexpectedly
        if isinstance(brief, dict):
            brief["promptIntelligence"] = pi
    if brief_obj.mood:
        prompt = f"{prompt}. Mood: {', '.join(brief_obj.mood)}"
    if brief_obj.genre:
        prompt = f"{prompt}. Genre: {brief_obj.genre}"
    if kind == "ambience":
        prompt = f"Ambience bed (loopable): {prompt}"
    if kind == "sfx" and brief_obj.category:
        prompt = f"{brief_obj.category}: {prompt}"
    return brief_obj, resolution, gen_kind, duration, wanted, prompt


def begin_generate_batch(
    project_id: str,
    *,
    kind: str,
    brief: dict[str, Any] | None = None,
    candidate_count: int = 3,
    preferred_provider: str | None = None,
    allow_provider_switch: bool = False,
    allow_cpu_fallback: bool = False,
) -> dict[str, Any]:
    """Create a queued batch shell so the UI can poll real per-candidate progress."""
    brief_obj, resolution, gen_kind, duration, wanted, prompt = _prepare_generation(
        project_id,
        kind=kind,
        brief=brief,
        candidate_count=candidate_count,
        preferred_provider=preferred_provider,
        allow_provider_switch=allow_provider_switch,
        allow_cpu_fallback=allow_cpu_fallback,
    )
    rec = resolution["recommendation"]
    batch_id = store.new_id()
    candidates = []
    for i in range(wanted):
        cand_id = store.new_id()
        seed = _candidate_seed(batch_id, cand_id, i)
        hint = _variation_hint(kind, i)
        candidates.append(
            {
                "id": cand_id,
                "batch_id": batch_id,
                "name": _item_label(kind, i + 1),
                "asset_id": None,
                "status": "queued",
                "summary": brief_obj.mood[0] if brief_obj.mood else kind,
                "variation_index": i + 1,
                "variation_hint": hint,
                "seed": seed,
                "provider": rec.get("provider") or "local",
                "runtime": rec.get("runtime") or ("ACE-Step" if kind == "music" else "MMAudio"),
                "error": None,
                "stems_supported": False,
            }
        )
    batch = {
        "id": batch_id,
        "project_id": project_id,
        "method": kind,
        "brief_snapshot": brief_obj.model_dump(),
        "candidate_ids": [c["id"] for c in candidates],
        "candidates": candidates,
        "created_at": _now(),
        "resolution": resolution,
        "gen_kind": gen_kind,
        "duration_sec": duration,
        "prompt": prompt,
        "status": "queued",
        "progress": _batch_progress(kind, candidates, status="running"),
        "async": True,
        "mock": False,
    }
    store.save_batch(project_id, batch)
    store.save_draft(
        project_id,
        {"latestBatchId": batch_id, "kind": kind, "brief": brief_obj.model_dump()},
    )
    return batch


def execute_generate_batch(db: Session, project_id: str, batch_id: str) -> dict[str, Any]:
    """Run queued candidates one-by-one, persisting honest progress after each."""
    from ..generation_tools.ops import run_audio_generate
    from . import process_registry as preg

    batch = store.get_batch(project_id, batch_id)
    if not batch:
        raise _err("NOT_FOUND", "Batch not found.", 404)
    kind = str(batch.get("method") or "music")
    gen_kind = str(batch.get("gen_kind") or ("music" if kind == "music" else "sfx"))
    duration = float(batch.get("duration_sec") or 8.0)
    prompt = str(batch.get("prompt") or (batch.get("brief_snapshot") or {}).get("prompt") or kind)
    candidates = list(batch.get("candidates") or [])
    preg.clear_batch_cancel(batch_id)
    batch["status"] = "running"
    batch["progress"] = _batch_progress(kind, candidates, status="running")
    store.save_batch(project_id, batch)

    for i, cand in enumerate(candidates):
        if preg.is_batch_cancel_requested(batch_id) or batch.get("status") == "cancelled":
            for remaining in candidates:
                if remaining.get("status") in ("queued", "generating"):
                    remaining["status"] = "cancelled"
                    remaining["error"] = "Cancelled at source to free GPU/RAM"
            batch["candidates"] = candidates
            batch["status"] = "cancelled"
            batch["progress"] = {
                **_batch_progress(kind, candidates, status="complete"),
                "status": "cancelled",
                "label": "Cancelled — worker terminated at source",
            }
            store.save_batch(project_id, batch)
            return batch
        if cand.get("status") not in ("queued", "generating", None, ""):
            continue
        cand["status"] = "generating"
        batch["candidates"] = candidates
        progress = _batch_progress(kind, candidates, status="running")
        runtime = "ACE-Step" if kind == "music" else "MMAudio"
        progress["label"] = (
            f"Generating {_item_label(kind, i + 1).lower()} on {runtime} "
            f"({progress['completed']} of {progress['total']} done) — GPU preferred"
        )
        batch["progress"] = progress
        store.save_batch(project_id, batch)
        try:
            seed = int(cand.get("seed") or _candidate_seed(batch_id, str(cand.get("id") or i), i))
            hint = str(cand.get("variation_hint") or _variation_hint(kind, i))
            cand["seed"] = seed
            cand["variation_index"] = int(cand.get("variation_index") or (i + 1))
            cand["variation_hint"] = hint
            varied_prompt = f"{prompt}. {hint}"
            with preg.execution_scope(
                project_id=project_id,
                batch_id=batch_id,
                candidate_id=str(cand.get("id") or ""),
                runtime_hint="ACE-Step" if kind == "music" else "MMAudio",
            ):
                out = run_audio_generate(
                    db,
                    project_id=project_id,
                    kind=gen_kind,
                    prompt=varied_prompt,
                    duration_sec=duration,
                    seed=seed,
                )
            asset_id = out.get("assetId")
            cand["asset_id"] = asset_id
            cand["status"] = "ready" if asset_id else "failed"
            cand["error"] = None if asset_id else "No asset registered"
            cand["prompt"] = varied_prompt
            cand["audio_url"] = f"/api/assets/{asset_id}/file" if asset_id else None
            cand["m29"] = out.get("m29")
            cand["sha256"] = (out.get("m29") or {}).get("sha256") or out.get("sha256")
        except Exception as exc:
            msg = str(exc)
            cancelled = "cancel" in msg.lower() or preg.is_batch_cancel_requested(batch_id)
            cand["asset_id"] = None
            cand["status"] = "cancelled" if cancelled else "failed"
            cand["error"] = msg
            if cancelled:
                for remaining in candidates[i + 1 :]:
                    if remaining.get("status") in ("queued", "generating"):
                        remaining["status"] = "cancelled"
                        remaining["error"] = "Cancelled at source to free GPU/RAM"
                batch["candidates"] = candidates
                batch["status"] = "cancelled"
                batch["progress"] = {
                    **_batch_progress(kind, candidates, status="complete"),
                    "status": "cancelled",
                    "label": "Cancelled — worker terminated at source",
                }
                store.save_batch(project_id, batch)
                return batch
        batch["candidates"] = candidates
        batch["progress"] = _batch_progress(kind, candidates, status="running")
        store.save_batch(project_id, batch)

    batch["status"] = "complete"
    batch["progress"] = _batch_progress(kind, candidates, status="complete")
    batch["completed_at"] = _now()
    ready_assets = [str(c.get("asset_id")) for c in candidates if c.get("asset_id") and c.get("status") in ("ready", "selected", "approved")]
    ready_seeds = [c.get("seed") for c in candidates if c.get("asset_id")]
    batch["uniqueness"] = {
        "readyCount": len(ready_assets),
        "uniqueAssetIds": len(set(ready_assets)),
        "uniqueSeeds": len({s for s in ready_seeds if s is not None}),
        "ok": len(ready_assets) >= 1 and len(set(ready_assets)) == len(ready_assets),
    }
    store.save_batch(project_id, batch)
    return batch


def cancel_batch(project_id: str, batch_id: str) -> dict[str, Any]:
    """Certified cancel: kill live GPU workers at source + mark batch cancelled."""
    from . import process_registry as preg

    batch = store.get_batch(project_id, batch_id)
    if not batch:
        raise _err("NOT_FOUND", "Batch not found.", 404)
    if batch.get("project_id") and batch.get("project_id") != project_id:
        raise _err("FORBIDDEN", "Batch does not belong to this project.", 403)

    source = preg.terminate_batch(batch_id)
    orphans = preg.terminate_orphan_audio_workers()
    candidates = list(batch.get("candidates") or [])
    for cand in candidates:
        if cand.get("status") in ("queued", "generating"):
            cand["status"] = "cancelled"
            cand["error"] = "Cancelled at source to free GPU/RAM"
    kind = str(batch.get("method") or "music")
    batch["candidates"] = candidates
    batch["status"] = "cancelled"
    batch["cancelled_at"] = _now()
    batch["cancel"] = {"source": source, "orphans": orphans, "certified": True}
    batch["progress"] = {
        **_batch_progress(kind, candidates, status="complete"),
        "status": "cancelled",
        "percent": int((batch.get("progress") or {}).get("percent") or 0),
        "label": "Cancelled — worker terminated at source",
    }
    store.save_batch(project_id, batch)
    return {
        "ok": True,
        "cancelled": True,
        "batchId": batch_id,
        "sourceCancel": True,
        "batch": batch,
        "source": source,
        "orphans": orphans,
        "mock": False,
    }


def cancel_project_generations(project_id: str) -> dict[str, Any]:
    """Cancel all queued/running batches for a project and kill orphan audio workers."""
    from . import process_registry as preg

    cancelled = []
    for batch in store.list_batches(project_id):
        status = str(batch.get("status") or "")
        inflight = status in ("queued", "running") or any(
            c.get("status") in ("queued", "generating") for c in (batch.get("candidates") or [])
        )
        if inflight:
            cancelled.append(cancel_batch(project_id, str(batch["id"])))
    orphans = preg.terminate_orphan_audio_workers()
    live = preg.list_live(project_id=project_id)
    for item in live:
        preg.terminate_job(str(item["jobId"]))
    return {
        "ok": True,
        "cancelledBatches": len(cancelled),
        "batches": cancelled,
        "orphans": orphans,
        "sourceCancel": True,
        "mock": False,
    }


def run_generate_batch_job(project_id: str, batch_id: str) -> None:
    """Background entrypoint — opens a fresh DB session."""
    from ..db import SessionLocal

    db = SessionLocal()
    try:
        execute_generate_batch(db, project_id, batch_id)
    except Exception as exc:
        batch = store.get_batch(project_id, batch_id)
        if batch:
            batch["status"] = "failed"
            batch["error"] = str(exc)
            batch["progress"] = {
                **(batch.get("progress") or {}),
                "status": "failed",
                "label": f"Generation failed: {exc}",
            }
            store.save_batch(project_id, batch)
    finally:
        db.close()


def get_batch(project_id: str, batch_id: str) -> dict[str, Any]:
    batch = store.get_batch(project_id, batch_id)
    if not batch:
        raise _err("NOT_FOUND", "Batch not found.", 404)
    return batch


def generate_batch(
    db: Session,
    project_id: str,
    *,
    kind: str,
    brief: dict[str, Any] | None = None,
    candidate_count: int = 3,
    preferred_provider: str | None = None,
    allow_provider_switch: bool = False,
    allow_cpu_fallback: bool = False,
) -> dict[str, Any]:
    """Synchronous generate (tests / callers that await full completion)."""
    batch = begin_generate_batch(
        project_id,
        kind=kind,
        brief=brief,
        candidate_count=candidate_count,
        preferred_provider=preferred_provider,
        allow_provider_switch=allow_provider_switch,
        allow_cpu_fallback=allow_cpu_fallback,
    )
    return execute_generate_batch(db, project_id, batch["id"])


def select_candidate(project_id: str, batch_id: str, candidate_id: str) -> dict[str, Any]:
    batch = store.get_batch(project_id, batch_id)
    if not batch:
        raise _err("NOT_FOUND", "Batch not found.", 404)
    found = None
    for c in batch.get("candidates") or []:
        if c.get("id") == candidate_id:
            if c.get("status") == "failed":
                raise _err("INVALID_STATUS", "Cannot select a failed candidate.")
            c["status"] = "selected"
            found = c
        elif c.get("status") == "selected":
            c["status"] = "ready"
    if not found:
        raise _err("NOT_FOUND", "Candidate not found.", 404)
    store.save_batch(project_id, batch)
    store.save_draft(project_id, {"selectedCandidateId": candidate_id, "selectedBatchId": batch_id})
    return {"ok": True, "approved": False, "selected": True, "candidate": found, "mock": False}


def approve_candidate(project_id: str, batch_id: str, candidate_id: str, *, approved_by: str = "owner") -> dict[str, Any]:
    batch = store.get_batch(project_id, batch_id)
    if not batch:
        raise _err("NOT_FOUND", "Batch not found.", 404)
    found = None
    for c in batch.get("candidates") or []:
        if c.get("id") == candidate_id:
            if c.get("status") == "failed" or not c.get("asset_id"):
                raise _err("INVALID_STATUS", "Candidate must be ready with a registered asset.")
            c["status"] = "approved"
            c["approved_by"] = approved_by
            c["approved_at"] = _now()
            found = c
    if not found:
        raise _err("NOT_FOUND", "Candidate not found.", 404)
    store.save_batch(project_id, batch)
    store.save_draft(
        project_id,
        {"approvedCandidateId": candidate_id, "approvedBatchId": batch_id, "approvedAt": _now()},
    )
    return {
        "ok": True,
        "approved": True,
        "decision": {
            "candidate_id": candidate_id,
            "approved": True,
            "approved_by": approved_by,
            "approved_at": _now(),
        },
        "candidate": found,
        "mock": False,
    }


def place_on_timeline(
    db: Session,
    project_id: str,
    *,
    asset_id: str,
    category: str = "music",
    start_ms: int = 0,
    loop: bool = False,
    scene_id: Optional[str] = None,
) -> dict[str, Any]:
    """Place approved audio — uses AudioService cue placement when available."""
    from ..db import Asset

    asset = db.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        raise _err("NOT_FOUND", "Audio asset not found.", 404)
    if not asset.path:
        raise _err("NOT_READY", "Asset has no file path.", 409)

    placement = None
    try:
        from ..codirector.m29.audio.service import AudioService

        if hasattr(AudioService, "place_cue"):
            placement = AudioService.place_cue(
                db,
                project_id=project_id,
                asset_id=asset_id,
                kind=category if category in ("music", "sfx", "ambience") else "music",
                scene_id=scene_id,
                start_ms=start_ms,
            )
    except Exception as exc:
        placement = {"serviceError": str(exc)}

    # Always persist mix + placement record for reload
    mix = store.get_mix(project_id)
    clip_id = store.new_id()
    clips = mix.get("clips") or {}
    clips[clip_id] = {
        "clip_id": clip_id,
        "asset_id": asset_id,
        "category": category,
        "scene_id": scene_id,
        "start_ms": start_ms,
        "gain": 1.0,
        "pan": 0.0,
        "mute": False,
        "solo": False,
        "loop": loop or category == "ambience",
        "fade_in_ms": 0.0,
        "fade_out_ms": 0.0,
        "track_route": "master",
        "approval_status": "approved",
        "created_at": _now(),
    }
    mix["clips"] = clips
    store.save_mix(project_id, mix)
    return {
        "ok": True,
        "clipId": clip_id,
        "assetId": asset_id,
        "category": category,
        "placement": placement,
        "mix": mix,
        "mock": False,
    }


def update_mix(project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    mix = store.get_mix(project_id)
    if "master" in patch and isinstance(patch["master"], dict):
        mix["master"] = {**(mix.get("master") or {}), **patch["master"]}
    if "clips" in patch and isinstance(patch["clips"], dict):
        clips = mix.get("clips") or {}
        for cid, state in patch["clips"].items():
            if isinstance(state, dict):
                clips[cid] = {**(clips.get(cid) or {"clip_id": cid}), **state}
        mix["clips"] = clips
    if "clip" in patch and isinstance(patch["clip"], dict):
        cid = patch["clip"].get("clip_id") or patch["clip"].get("clipId")
        if cid:
            clips = mix.get("clips") or {}
            clips[cid] = {**(clips.get(cid) or {}), **patch["clip"], "clip_id": cid}
            mix["clips"] = clips
    # Stem mute/expand — only when clip already carries a real MusicStemSet (never invent stems)
    if "stem" in patch and isinstance(patch["stem"], dict):
        cid = patch["stem"].get("clip_id") or patch["stem"].get("clipId")
        stem_id = patch["stem"].get("stem_id") or patch["stem"].get("stemId")
        if cid and stem_id:
            clips = mix.get("clips") or {}
            clip = clips.get(cid) or {"clip_id": cid}
            stems = clip.get("stems") or clip.get("music_stem_set") or {}
            stem_list = stems.get("stems") if isinstance(stems, dict) else None
            if isinstance(stem_list, list):
                for s in stem_list:
                    if isinstance(s, dict) and (s.get("id") == stem_id or s.get("stem_id") == stem_id):
                        if "mute" in patch["stem"]:
                            s["mute"] = bool(patch["stem"]["mute"])
                        if "hidden" in patch["stem"]:
                            s["hidden"] = bool(patch["stem"]["hidden"])
                clip["stems"] = stems
                clips[cid] = clip
                mix["clips"] = clips
            elif patch["stem"].get("expand") is not None:
                # Honest no-op when no stems exist
                clip["stemsExpanded"] = False
                clip["stemsMessage"] = "Provider did not return stems for this clip."
                clips[cid] = clip
                mix["clips"] = clips
    return store.save_mix(project_id, mix)


def retry_candidate(
    db: Session,
    project_id: str,
    batch_id: str,
    candidate_id: str,
) -> dict[str, Any]:
    batch = store.get_batch(project_id, batch_id)
    if not batch:
        raise _err("NOT_FOUND", "Batch not found.", 404)
    cand = next((c for c in batch.get("candidates") or [] if c.get("id") == candidate_id), None)
    if not cand:
        raise _err("NOT_FOUND", "Candidate not found.", 404)
    brief = batch.get("brief_snapshot") or {}
    kind = batch.get("method") or "music"
    from ..generation_tools.ops import run_audio_generate

    gen_kind = "music" if kind == "music" else ("ambience" if kind == "ambience" else "sfx")
    idx = next(
        (i for i, c in enumerate(batch.get("candidates") or []) if c.get("id") == candidate_id),
        0,
    )
    seed = _candidate_seed(batch_id, candidate_id, idx)
    hint = str(cand.get("variation_hint") or _variation_hint(str(kind), idx))
    prompt = f"{brief.get('prompt') or 'retry'}. {hint}"
    try:
        out = run_audio_generate(
            db,
            project_id=project_id,
            kind=gen_kind,
            prompt=prompt,
            duration_sec=float(brief.get("duration_seconds") or 8.0),
            seed=seed,
        )
        asset_id = out.get("assetId")
        cand["asset_id"] = asset_id
        cand["status"] = "ready" if asset_id else "failed"
        cand["error"] = None if asset_id else "No asset"
        cand["seed"] = seed
        cand["variation_hint"] = hint
        cand["prompt"] = prompt
        cand["audio_url"] = f"/api/assets/{asset_id}/file" if asset_id else None
        cand["m29"] = out.get("m29")
        cand["sha256"] = (out.get("m29") or {}).get("sha256") or out.get("sha256")
        cand["retried_at"] = _now()
    except Exception as exc:
        cand["status"] = "failed"
        cand["error"] = str(exc)
        cand["retried_at"] = _now()
    store.save_batch(project_id, batch)
    return {"ok": True, "candidate": cand, "batch": batch, "mock": False}
