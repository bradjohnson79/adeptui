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
    "slightly closer and drier, same event identity",
    "mid-distance with a little more space, same event",
    "slightly heavier body and longer decay, same event",
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


def _variation_hint(kind: str, index: int, event_type: str | None = None) -> str:
    if kind != "music":
        try:
            from .sound_prompt_compiler import variation_clause

            return variation_clause(str(event_type or ("ambience" if kind == "ambience" else "generic")), index)
        except Exception:
            pass
    pool = _MUSIC_VARIATIONS if kind == "music" else _AMBIENCE_VARIATIONS if kind == "ambience" else _SFX_VARIATIONS
    return pool[index % len(pool)]


def _project_label(project_id: str) -> str:
    try:
        from ..db import Project, SessionLocal

        db = SessionLocal()
        try:
            row = db.get(Project, project_id)
            return str(getattr(row, "name", "") or "")
        finally:
            db.close()
    except Exception:
        return ""


def _runtime_badge(kind: str, resolution: dict[str, Any] | None, *, proven_device: str | None = None) -> str:
    runtime = "ACE-Step" if kind == "music" else "MMAudio"
    rec = (resolution or {}).get("recommendation") or {}
    device = str(proven_device or rec.get("device") or "")
    cuda = bool(rec.get("cuda"))
    proven = device.lower().startswith("cuda") or (cuda and proven_device is None)
    if proven:
        return f"{runtime} · GPU"
    return runtime


def _progress_label(
    kind: str,
    *,
    stage: str,
    current: int,
    total: int,
    completed: int,
    badge: str,
) -> str:
    noun = "track" if kind == "music" else "bed" if kind == "ambience" else "take"
    if stage == "preparing":
        return "Preparing Sound Engine"
    if stage == "loading":
        return f"Loading Sound Engine — {badge}"
    if stage == "ready":
        return f"Sound Engine ready — {badge}"
    if stage == "generating":
        return f"Generating {noun} {current} of {total} — {badge}"
    if stage == "saving":
        return f"Saving {noun} {current} of {total} — {badge}"
    if stage == "complete":
        return f"Complete - {completed} of {total}"
    if stage == "cancelled":
        return "Cancelled — remaining takes stopped"
    return f"Generating {noun} {current} of {total} — {badge}"


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
        "libraryCount": len(library),
        "mock": False,
    }


def _library_key_for_kind(kind: str) -> str:
    key = str(kind or "").strip().lower()
    if key == "music":
        return "audio.music"
    if key == "ambience":
        return "audio.ambience"
    return "audio.sfx"


def _batch_kind(batch: dict[str, Any], candidate: dict[str, Any] | None = None) -> str:
    raw = (
        (batch or {}).get("method")
        or (batch or {}).get("kind")
        or (candidate or {}).get("summary")
        or (candidate or {}).get("category")
        or "sfx"
    )
    kind = str(raw).strip().lower()
    if kind in ("music", "sfx", "ambience"):
        return kind
    return "sfx"


def _library_audio(db: Session, project_id: str) -> list[dict[str, Any]]:
    from ..db import Asset
    from ..project_library.service import enrich_library_item, read_asset_library_meta

    rows = (
        db.query(Asset)
        .filter(Asset.project_id == project_id)
        .order_by(Asset.created_at.desc())
        .limit(400)
        .all()
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        kind = str(row.kind or "").lower()
        meta = read_asset_library_meta(row)
        folder_key = str(meta.folder_system_key or "")
        if kind not in ("audio", "voice") and not folder_key.startswith("audio"):
            continue
        item = enrich_library_item(row)
        item["libraryKey"] = folder_key or item.get("folderSystemKey")
        item["category"] = folder_key.split(".")[-1] if folder_key.startswith("audio.") else kind
        item["name"] = item.get("tag") or item.get("filename") or row.id
        items.append(item)
    return items


def _candidate_source_path(candidate: dict[str, Any], asset_path: str | None = None) -> str | None:
    from pathlib import Path

    seen: list[str] = []
    if asset_path:
        seen.append(str(asset_path))
    m29 = candidate.get("m29") or {}
    seen.append(str(m29.get("assetPath") or ""))
    provenance = m29.get("provenance") if isinstance(m29.get("provenance"), dict) else {}
    seen.append(str(provenance.get("assetPath") or ""))
    for raw in seen:
        if raw and Path(raw).is_file():
            return raw
    return None


def _path_is_sandbox(path: str | None) -> bool:
    if not path:
        return True
    normalized = str(path).replace("\\", "/").lower()
    return "m210b-sandbox" in normalized


def _ingest_approved_audio(
    db: Session,
    project_id: str,
    batch: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Copy an approved take into this project's Library as a durable Asset.id."""
    from pathlib import Path

    from ..db import Asset
    from ..generation_tools.lineage import register_derived_asset
    from ..project_library.service import assign_asset, enrich_library_item

    kind = _batch_kind(batch, candidate)
    library_key = _library_key_for_kind(kind)
    asset_id = str(candidate.get("asset_id") or "").strip()
    asset = db.get(Asset, asset_id) if asset_id else None
    if asset and asset.project_id != project_id:
        asset = None
    src = _candidate_source_path(candidate, getattr(asset, "path", None) if asset else None)
    if not src:
        raise _err(
            "NOT_READY",
            "This take has no file that can be added to this project's Library.",
            409,
        )

    needs_copy = asset is None or _path_is_sandbox(getattr(asset, "path", None)) or not Path(str(asset.path)).is_file()
    if needs_copy:
        m29 = candidate.get("m29") or {}
        asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=src,
            kind="audio",
            tag=f"{kind}_approved",
            parent_asset_id=asset.id if asset else None,
            op=f"{kind}_approve",
            model=str(m29.get("registryId") or candidate.get("runtime") or kind),
            prompt_meta={
                "approvedFromCandidate": candidate.get("id"),
                "batchId": batch.get("id"),
                "sandboxOnly": False,
                "audioStudioProductionPath": True,
                "audioRole": kind,
                "m29AssetId": m29.get("assetId"),
                "sha256": candidate.get("sha256") or m29.get("sha256"),
            },
            library_key=library_key,
        )
        candidate["asset_id"] = asset.id
        candidate["audio_url"] = f"/api/projects/{project_id}/assets/{asset.id}/file"
        candidate["sandboxOnly"] = False
    else:
        assign_asset(db, asset, system_key=library_key, classified_by="audio_studio.approve", override=True)

    asset.production_approval = "approved"
    db.add(asset)
    db.commit()
    db.refresh(asset)
    item = enrich_library_item(asset)
    item["libraryKey"] = library_key
    item["category"] = kind
    return {
        "assetId": asset.id,
        "libraryItem": item,
        "libraryKey": library_key,
        "ingested": True,
    }


def _item_label(kind: str, index: int) -> str:
    prefix = "Track" if kind == "music" else "Sound" if kind == "sfx" else "Bed"
    return f"{prefix} {index}"


def _batch_progress(kind: str, candidates: list[dict[str, Any]], *, status: str) -> dict[str, Any]:
    """Honest batch progress. Never pin at 0% for the whole first-candidate generate."""
    total = max(1, len(candidates))
    completed = sum(1 for c in candidates if c.get("status") in ("ready", "failed", "selected", "approved"))
    generating_idx = next((i for i, c in enumerate(candidates) if c.get("status") == "generating"), None)
    queued_idx = next((i for i, c in enumerate(candidates) if c.get("status") in ("queued", "pending")), None)
    current = (generating_idx + 1) if generating_idx is not None else min(completed + 1, total)
    if status == "complete":
        current = total
        percent = 100
    else:
        # completed share + partial credit for the in-flight candidate
        base = 100.0 * completed / total
        if generating_idx is not None:
            partial = 45.0 / total  # mid-candidate floor contribution
            percent = int(round(base + partial))
            percent = max(percent, int(round(12.0 + 80.0 * completed / total)))
        elif status == "running":
            # queued / loading before first audio bytes
            percent = max(8, int(round(base)))
        else:
            percent = int(round(base))
        percent = max(0, min(95 if status == "running" else 100, percent))
    return {
        "status": status,
        "completed": completed,
        "total": total,
        "percent": max(0, min(100, percent)),
        "current": current,
        "label": (
            f"Complete - {completed} of {total}"
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
) -> tuple[AudioCreativeBrief, dict[str, Any], str, float, int, str, dict[str, Any] | None]:
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
        needed = "ace-step-local" if kind == "music" else "mmaudio-local"
        if dock_sel.activeModelId == needed and not dock_sel.executable:
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
    compiler_record: dict[str, Any] | None = None
    if kind in ("sfx", "ambience"):
        from .sound_prompt_compiler import compile_sound_prompt

        event_hint = None
        if isinstance(brief, dict):
            event_hint = brief.get("eventType") or brief.get("event_type")
        intent_in = None
        if isinstance(brief, dict):
            intent_in = brief.get("intent") or brief.get("sfxIntent")
            if not isinstance(intent_in, dict):
                intent_in = None
            # Promote flat ORDER-14 fields into intent when FE/API sends them beside brief.
            flat_keys = (
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
            )
            promoted = {k: brief[k] for k in flat_keys if brief.get(k) is not None}
            if promoted:
                intent_in = {**(intent_in or {}), **promoted}
        compiled = compile_sound_prompt(
            prompt,
            kind=kind,
            duration_seconds=duration,
            intensity=brief_obj.intensity,
            event_type=str(event_hint) if event_hint else None,
            project_name=_project_label(project_id),
            project_id=project_id,
            intent=intent_in,
        )
        compiler_record = compiled.to_dict()
        prompt = compiled.compiled_prompt
        if isinstance(brief, dict):
            brief["soundCompiler"] = compiler_record
            brief["intent"] = {
                "physicalEvent": compiler_record.get("physicalEvent"),
                "material": compiler_record.get("material"),
                "context": compiler_record.get("context"),
                "temporal": compiler_record.get("temporal"),
                "negatives": compiler_record.get("negatives") or [],
                "refinementOps": compiler_record.get("refinementOps") or [],
            }
    else:
        pi = (brief or {}).get("promptIntelligence") if isinstance(brief, dict) else None
        if (brief or {}).get("runPromptIntelligence") and prompt and not (isinstance(pi, dict) and pi.get("finalProviderPrompt")):
            try:
                from ..codirector.prompt_intelligence.models import ModulesEnabled, PromptIntelligenceRequest
                from ..codirector.prompt_intelligence.pipeline import enhance as pi_enhance

                result = pi_enhance(
                    PromptIntelligenceRequest(
                        creatorPrompt=prompt,
                        domain="music",
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
            if isinstance(brief, dict):
                brief["promptIntelligence"] = pi
        if brief_obj.mood:
            prompt = f"{prompt}. Mood: {', '.join(brief_obj.mood)}"
        if brief_obj.genre:
            prompt = f"{prompt}. Genre: {brief_obj.genre}"
    return brief_obj, resolution, gen_kind, duration, wanted, prompt, compiler_record


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
    brief_obj, resolution, gen_kind, duration, wanted, prompt, compiler_record = _prepare_generation(
        project_id,
        kind=kind,
        brief=brief,
        candidate_count=candidate_count,
        preferred_provider=preferred_provider,
        allow_provider_switch=allow_provider_switch,
        allow_cpu_fallback=allow_cpu_fallback,
    )
    rec = resolution["recommendation"]
    event_type = str((compiler_record or {}).get("event_type") or "")
    batch_id = store.new_id()
    candidates = []
    for i in range(wanted):
        cand_id = store.new_id()
        seed = _candidate_seed(batch_id, cand_id, i)
        hint = _variation_hint(kind, i, event_type or None)
        cand_row = {
                "id": cand_id,
                "batch_id": batch_id,
                "name": _item_label(kind, i + 1),
                "asset_id": None,
                "status": "queued",
                "summary": brief_obj.mood[0] if brief_obj.mood else kind,
                "variation_index": i + 1,
                "variation_hint": hint,
                "seed": seed,
                "provider": ("elevenlabs" if (preferred_provider or "").strip().lower() in ("elevenlabs", "eleven_labs", "el") else (rec.get("provider") or "local")),
                "runtime": ("ElevenLabs" if (preferred_provider or "").strip().lower() in ("elevenlabs", "eleven_labs", "el") else (rec.get("runtime") or ("ACE-Step" if kind == "music" else "MMAudio"))),
                "error": None,
                "stems_supported": False,
            }
        if compiler_record:
            # ORDER 14: persist structured compiler fields for FE chips / refine.
            cand_row["physicalEvent"] = compiler_record.get("physicalEvent")
            cand_row["material"] = compiler_record.get("material")
            cand_row["context"] = compiler_record.get("context")
            cand_row["temporal"] = compiler_record.get("temporal")
            cand_row["negatives"] = compiler_record.get("negatives") or []
            cand_row["refinementOps"] = compiler_record.get("refinementOps") or []
            cand_row["compiled_prompt"] = compiler_record.get("compiled_prompt") or compiler_record.get("compiledPrompt")
            cand_row["compiledPrompt"] = compiler_record.get("compiledPrompt") or compiler_record.get("compiled_prompt")
            cand_row["negative_prompt"] = compiler_record.get("negative_prompt") or compiler_record.get("negativePrompt") or ""
            cand_row["negativePrompt"] = compiler_record.get("negativePrompt") or compiler_record.get("negative_prompt") or ""
            cand_row["cfg_strength"] = compiler_record.get("cfg_strength")
            cand_row["event_type"] = compiler_record.get("event_type")
            cand_row["sound_compiler"] = compiler_record
        candidates.append(cand_row)
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
        "raw_prompt": (compiler_record or {}).get("raw_prompt") or brief_obj.prompt,
        "compiled_prompt": prompt if compiler_record else None,
        "negative_prompt": (compiler_record or {}).get("negative_prompt") or "",
        "cfg_strength": (compiler_record or {}).get("cfg_strength"),
        "sound_compiler": compiler_record,
        "status": "queued",
        "progress": {
            **_batch_progress(kind, candidates, status="running"),
            "label": _progress_label(
                kind,
                stage="preparing",
                current=1,
                total=wanted,
                completed=0,
                badge=_runtime_badge(kind, resolution),
            ),
            "stage": "preparing",
        },
        "async": True,
        "mock": False,
        "preferred_provider": preferred_provider,
        "provider_source": (preferred_provider or "local"),
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
    negative_prompt = str(batch.get("negative_prompt") or "")
    _temporal = ((batch.get("sound_compiler") or {}).get("temporal") or {})
    try:
        event_count_batch = int(_temporal["eventCount"]) if _temporal.get("eventCount") is not None else None
    except (TypeError, ValueError):
        event_count_batch = None
    cfg_strength = batch.get("cfg_strength")
    compiler_record = batch.get("sound_compiler") or {}
    event_type = str(compiler_record.get("event_type") or "")
    resolution = batch.get("resolution") or {}
    badge = _runtime_badge(kind, resolution)
    candidates = list(batch.get("candidates") or [])
    preg.clear_batch_cancel(batch_id)
    batch["status"] = "running"
    batch["progress"] = {
        **_batch_progress(kind, candidates, status="running"),
        "label": _progress_label(kind, stage="loading", current=1, total=max(1, len(candidates)), completed=0, badge=badge),
        "stage": "loading",
    }
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
                "stage": "cancelled",
                "label": _progress_label(kind, stage="cancelled", current=i + 1, total=len(candidates) or 1, completed=0, badge=badge),
            }
            store.save_batch(project_id, batch)
            return batch
        if cand.get("status") not in ("queued", "generating", None, ""):
            continue
        cand["status"] = "generating"
        batch["candidates"] = candidates
        progress = _batch_progress(kind, candidates, status="running")
        progress["label"] = _progress_label(
            kind,
            stage="generating",
            current=i + 1,
            total=progress["total"],
            completed=progress["completed"],
            badge=badge,
        )
        progress["stage"] = "generating"
        batch["progress"] = progress
        store.save_batch(project_id, batch)
        try:
            seed = int(cand.get("seed") or _candidate_seed(batch_id, str(cand.get("id") or i), i))
            hint = str(cand.get("variation_hint") or _variation_hint(kind, i, event_type or None))
            cand["seed"] = seed
            cand["variation_index"] = int(cand.get("variation_index") or (i + 1))
            cand["variation_hint"] = hint
            varied_prompt = f"{prompt} {hint}."
            pref = str(batch.get("preferred_provider") or batch.get("provider_source") or "").strip().lower()
            if pref in ("elevenlabs", "eleven_labs", "el"):
                # ElevenLabs sound and music text has a 450 character limit.
                # The local compiler prompt is for the local engine. Send the creator line.
                raw_line = str(batch.get("raw_prompt") or "").strip()
                el_text = raw_line or prompt
                if hint and len(el_text) + len(hint) + 2 <= 450:
                    el_text = f"{el_text} {hint}."
                elif len(el_text) > 450:
                    el_text = el_text[:450].rsplit(" ", 1)[0].strip() or el_text[:450]
                from ..hosted_providers.adapters.elevenlabs_routed import generate_music_routed, generate_sfx_routed
                from ..generation_tools.lineage import register_derived_asset
                from pathlib import Path as _Path
                import tempfile as _tempfile
                if kind == "ambience":
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "code": "ELEVENLABS_VALIDATION",
                            "error": "ELEVENLABS_VALIDATION",
                            "message": "Choose Sound Effects or Music for ElevenLabs. Ambience stays on Local.",
                            "silentFallback": False,
                            "mock": False,
                        },
                    )
                if kind == "music":
                    dest = _Path(_tempfile.mkstemp(prefix="el_music_", suffix=".mp3")[1])
                    el = generate_music_routed(
                        prompt=el_text,
                        duration_seconds=float(duration) if duration else None,
                        dest=dest,
                        surface="audio-studio.music",
                    )
                    library_class = "music"
                    op_name = "music_generate_elevenlabs"
                    tag_name = "music"
                else:
                    dest = _Path(_tempfile.mkstemp(prefix="el_sfx_", suffix=".mp3")[1])
                    el = generate_sfx_routed(
                        text=el_text,
                        duration_seconds=float(duration) if duration else None,
                        loop=bool((batch.get("brief_snapshot") or {}).get("loop_required")),
                        dest=dest,
                        surface="audio-studio.sfx",
                    )
                    library_class = "sfx"
                    op_name = "sfx_generate_elevenlabs"
                    tag_name = "sfx"
                proven_el = dict(el.get("provenance") or {})
                asset = register_derived_asset(
                    db,
                    project_id=project_id,
                    source_path=el["path"],
                    kind="audio",
                    tag=tag_name,
                    parent_asset_id=None,
                    op=op_name,
                    model=str(el.get("model") or proven_el.get("providerModelId") or ""),
                    prompt_meta={
                        "prompt": el_text,
                        "localProvider": False,
                        "cloudPaid": True,
                        "audioStudioProductionPath": True,
                        "audioRole": library_class,
                        "libraryClass": library_class,
                        **proven_el,
                    },
                    library_key=f"audio.{library_class}",
                )
                out = {
                    "assetId": asset.id,
                    "m29": {
                        "provenance": {
                            "provider": "elevenlabs",
                            "model": el.get("model"),
                            "negativeUsed": False,
                            "runtime": "ElevenLabs",
                            **proven_el,
                        },
                        "sha256": None,
                    },
                    "sha256": None,
                }
                cand["provider"] = "elevenlabs"
                cand["runtime"] = "ElevenLabs"
                cand["model"] = el.get("model")
            else:
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
                        negative_prompt=negative_prompt or None,
                        cfg_strength=float(cfg_strength) if cfg_strength is not None else None,
                        event_count=event_count_batch,
                    )
            asset_id = out.get("assetId")
            proven = ((out.get("m29") or {}).get("provenance") or {})
            if proven.get("gpuProven") or str(proven.get("device") or "").startswith("cuda"):
                badge = _runtime_badge(kind, resolution, proven_device=str(proven.get("device") or "cuda"))
            if asset_id and kind in ("sfx", "ambience") and pref not in ("elevenlabs", "eleven_labs", "el"):
                from .sfx_wav_validate import validate_sfx_wav
                from ..db import Asset

                asset_row = db.get(Asset, asset_id) if hasattr(db, "get") else None
                check = validate_sfx_wav(getattr(asset_row, "path", None) or "", expected_duration_sec=duration)
                cand["wav_validation"] = check
                if not check.get("ok"):
                    cand["asset_id"] = None
                    cand["status"] = "failed"
                    cand["error"] = check.get("reason") or "Take failed objective audio checks"
                    cand["prompt"] = varied_prompt
                    cand["audio_url"] = None
                    cand["m29"] = out.get("m29")
                    batch["candidates"] = candidates
                    batch["progress"] = _batch_progress(kind, candidates, status="running")
                    store.save_batch(project_id, batch)
                    continue
            cand["asset_id"] = asset_id
            cand["status"] = "ready" if asset_id else "failed"
            cand["error"] = None if asset_id else "No asset registered"
            cand["prompt"] = varied_prompt
            cand["compiled_prompt"] = prompt
            cand["raw_prompt"] = batch.get("raw_prompt")
            cand["audio_url"] = (
                f"/api/projects/{project_id}/assets/{asset_id}/file" if asset_id else None
            )
            cand["m29"] = out.get("m29")
            cand["sha256"] = (out.get("m29") or {}).get("sha256") or out.get("sha256")
            cand["timings"] = {
                "inferenceMs": proven.get("inferenceMs"),
                "saveMs": proven.get("saveMs"),
                "totalMs": proven.get("totalMs"),
                "warmResident": proven.get("warmResident"),
                "route": proven.get("route"),
                "device": proven.get("device"),
            }
            batch["progress"] = {
                **_batch_progress(kind, candidates, status="running"),
                "label": _progress_label(
                    kind,
                    stage="saving",
                    current=i + 1,
                    total=len(candidates) or 1,
                    completed=sum(1 for c in candidates if c.get("status") in ("ready", "failed", "selected", "approved")),
                    badge=badge,
                ),
                "stage": "saving",
            }
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            cand["asset_id"] = None
            cand["status"] = "failed"
            cand["error"] = detail.get("message") or "ElevenLabs could not complete that request."
            cand["errorCode"] = detail.get("code")
            if detail.get("upstreamStatus"):
                cand["upstreamStatus"] = detail.get("upstreamStatus")
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
    serve_interrupt = {"ok": True, "interrupted": False}
    if str(batch.get("method") or "") in ("sfx", "ambience"):
        try:
            from .mmaudio_runtime import interrupt_in_flight

            serve_interrupt = interrupt_in_flight(batch_id)
        except Exception as exc:
            serve_interrupt = {"ok": False, "error": str(exc)}
    orphans = preg.terminate_orphan_audio_workers(include_serve=False)
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
        "label": "Cancelled — remaining takes stopped",
        "stage": "cancelled",
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
        "serveInterrupt": serve_interrupt,
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
    orphans = preg.terminate_orphan_audio_workers(include_serve=False)
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


def approve_candidate(
    project_id: str,
    batch_id: str,
    candidate_id: str,
    *,
    approved_by: str = "owner",
    db: Session | None = None,
) -> dict[str, Any]:
    batch = store.get_batch(project_id, batch_id)
    if not batch:
        raise _err("NOT_FOUND", "Batch not found.", 404)
    found = None
    for c in batch.get("candidates") or []:
        if c.get("id") == candidate_id:
            if c.get("status") == "failed" or not (c.get("asset_id") or (c.get("m29") or {}).get("assetPath")):
                raise _err("INVALID_STATUS", "Candidate must be ready with a registered asset.")
            found = c
            break
    if not found:
        raise _err("NOT_FOUND", "Candidate not found.", 404)

    own_session = False
    session = db
    if session is None:
        from ..db import SessionLocal

        session = SessionLocal()
        own_session = True
    try:
        ingested = _ingest_approved_audio(session, project_id, batch, found)
        library = _library_audio(session, project_id)
    finally:
        if own_session:
            session.close()

    found["status"] = "approved"
    found["approved_by"] = approved_by
    found["approved_at"] = _now()
    found["library_ingested"] = True
    found["production_approved"] = True
    store.save_batch(project_id, batch)
    store.save_draft(
        project_id,
        {
            "approvedCandidateId": candidate_id,
            "approvedBatchId": batch_id,
            "approvedAssetId": ingested["assetId"],
            "approvedAt": _now(),
        },
    )
    in_library = any(str(item.get("id")) == str(ingested["assetId"]) for item in library)
    return {
        "ok": True,
        "approved": True,
        "ingested": True,
        "approvedAssetInLibrary": in_library,
        "assetId": ingested["assetId"],
        "libraryItem": ingested["libraryItem"],
        "libraryCount": len(library),
        "decision": {
            "candidate_id": candidate_id,
            "approved": True,
            "approved_by": approved_by,
            "approved_at": _now(),
            "asset_id": ingested["assetId"],
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
                start_sec=float(start_ms or 0) / 1000.0,
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
    from ..film_timeline.insertion import add_to_timeline
    from ..scene_service import list_scenes

    target_scene = scene_id
    if not target_scene:
        scenes = list_scenes(db, project_id)
        target_scene = scenes[0].id if scenes else None
    film_place = None
    if target_scene:
        lane = category if category in {"music", "sfx", "ambience", "voice"} else None
        film_place = add_to_timeline(
            db,
            project_id,
            target_scene,
            media_type=lane or "audio",
            asset_id=asset_id,
            target_track_type=lane,
            start_time=float(start_ms or 0) / 1000.0,
            label=category,
            metadata={"source": "audio-studio", "loop": loop},
        )
    return {
        "ok": True,
        "clipId": clip_id,
        "assetId": asset_id,
        "category": category,
        "placement": placement,
        "mix": mix,
        "filmTimeline": film_place,
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
    hint = str(cand.get("variation_hint") or _variation_hint(str(kind), idx, str((batch.get("sound_compiler") or {}).get("event_type") or "") or None))
    prompt = f"{batch.get('compiled_prompt') or batch.get('prompt') or brief.get('prompt') or 'retry'} {hint}."
    try:
        _temporal_r = ((batch.get("sound_compiler") or {}).get("temporal") or {})
        try:
            _ec_r = int(_temporal_r["eventCount"]) if _temporal_r.get("eventCount") is not None else None
        except (TypeError, ValueError):
            _ec_r = None
        out = run_audio_generate(
            db,
            project_id=project_id,
            kind=gen_kind,
            prompt=prompt,
            duration_sec=float(batch.get("duration_sec") or brief.get("duration_seconds") or 8.0),
            seed=seed,
            negative_prompt=str(batch.get("negative_prompt") or "") or None,
            cfg_strength=batch.get("cfg_strength"),
            event_count=_ec_r,
        )
        asset_id = out.get("assetId")
        cand["asset_id"] = asset_id
        cand["status"] = "ready" if asset_id else "failed"
        cand["error"] = None if asset_id else "No asset"
        cand["seed"] = seed
        cand["variation_hint"] = hint
        cand["prompt"] = prompt
        cand["audio_url"] = (
            f"/api/projects/{project_id}/assets/{asset_id}/file" if asset_id else None
        )
        cand["m29"] = out.get("m29")
        cand["sha256"] = (out.get("m29") or {}).get("sha256") or out.get("sha256")
        cand["retried_at"] = _now()
    except Exception as exc:
        cand["status"] = "failed"
        cand["error"] = str(exc)
        cand["retried_at"] = _now()
    store.save_batch(project_id, batch)
    return {"ok": True, "candidate": cand, "batch": batch, "mock": False}
