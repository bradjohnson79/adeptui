"""PostProductionContextPackage assembler (CONTRACT_FREEZE.md).

Task-aware assembly from EXISTING reads only. No second MAGI store.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

DOMAIN_ALIASES = {
    "color": "color",
    "grade": "color",
    "grading": "color",
    "audio": "sound",
    "sound": "sound",
    "sfx": "sound",
    "music": "music",
    "score": "music",
    "edit": "edit",
    "editorial": "edit",
    "finish": "finish",
    "finishing": "finish",
    "render": "finish",
    "export": "export",
    "upscale": "upscale",
    "publish": "export",
    "all": "all",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_domains(raw: Any) -> set[str]:
    if raw is None or raw == "" or raw == []:
        return {"all"}
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, (list, tuple, set)):
        items = list(raw)
    else:
        items = [str(raw)]
    out: set[str] = set()
    for item in items:
        key = DOMAIN_ALIASES.get(str(item).strip().lower())
        if key:
            out.add(key)
    return out or {"all"}


def _clip_summary(clip: dict[str, Any], tracks_by_id: dict[str, Any]) -> dict[str, Any]:
    track = tracks_by_id.get(str(clip.get("trackId") or "")) or {}
    return {
        "clipId": clip.get("id"),
        "assetId": clip.get("assetId"),
        "track": track.get("label") or track.get("id") or clip.get("trackId"),
        "trackId": clip.get("trackId"),
        "in": clip.get("inPoint"),
        "out": clip.get("outPoint"),
        "duration": clip.get("durationFrames"),
        "mediaKind": track.get("kind") or clip.get("kind"),
        "name": clip.get("name"),
        "startFrame": clip.get("startFrame"),
    }


def _compact_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    deferred = payload.get("deferredSurfaces") or []
    return {
        "status": "ready" if payload.get("noFakeExecution") else "degraded",
        "phase": payload.get("phase"),
        "productName": payload.get("productName"),
        "noFakeExecution": bool(payload.get("noFakeExecution")),
        "productionSurfaceCount": len(payload.get("productionSurfaces") or []),
        "deferredSurfaceIds": [s.get("id") for s in deferred if isinstance(s, dict)],
        "honestNonExecutableCount": payload.get("honestNonExecutableCount"),
    }


def _recent_receipts(db: Session, project_id: str, limit: int = 8) -> list[dict[str, Any]]:
    from ....db import CoDirectorToolInvocation

    rows = (
        db.query(CoDirectorToolInvocation)
        .filter(CoDirectorToolInvocation.project_id == project_id)
        .filter(CoDirectorToolInvocation.tool_id.like("magi.%"))
        .order_by(CoDirectorToolInvocation.created_at.desc())
        .limit(limit)
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        receipt = None
        try:
            result = json.loads(row.result_json or "{}")
            data = result.get("data") if isinstance(result, dict) else None
            if isinstance(data, dict):
                receipt = data.get("magiActionReceipt")
        except Exception:
            receipt = None
        out.append(
            {
                "invocationId": row.id,
                "toolId": row.tool_id,
                "status": row.status,
                "proposalId": row.proposal_id,
                "createdAt": row.created_at.isoformat() if row.created_at else None,
                "magiActionReceipt": receipt,
            }
        )
    return out


def _open_jobs(db: Session, project_id: str, limit: int = 12) -> list[dict[str, Any]]:
    from ....db import Job
    from ....magi.jobs import ACTIVE

    rows = (
        db.query(Job)
        .filter(Job.project_id == project_id)
        .filter(Job.kind.like("magi_%"))
        .order_by(Job.created_at.desc())
        .limit(40)
        .all()
    )
    open_rows = [j for j in rows if j.status in ACTIVE][:limit]
    return [
        {
            "jobId": j.id,
            "kind": j.kind,
            "status": j.status,
            "stage": j.stage,
            "progress": j.progress,
            "message": j.message,
        }
        for j in open_rows
    ]


def _timeline_publish_slice(
    db: Session, project_id: str, scene_id: str | None
) -> dict[str, Any] | None:
    """ONLY via timeline master — never invent. Returns None if scene_id missing."""
    if not scene_id:
        return None
    try:
        from ....director_timeline_w46 import service as tl_service
    except Exception:
        return {
            "available": False,
            "reason": "timeline_service_unavailable",
            "note": "timelinePublish assembled only via Timeline master (timeline.get_workspace truth)",
        }

    load_fn = None
    for name in ("load_scene_bundle", "get_scene_bundle", "load_bundle"):
        load_fn = getattr(tl_service, name, None)
        if callable(load_fn):
            break
    if load_fn is None:
        # Fall back: try contracts/store style used by CD handler
        try:
            from ....director_timeline_w46.store import load_master  # type: ignore
        except Exception:
            return {
                "available": False,
                "reason": "no_timeline_loader",
                "note": "Pass sceneId and ensure Timeline master exists; or use timeline.get_workspace.",
            }
        try:
            master = load_master(db, project_id, scene_id)
        except Exception as exc:
            return {"available": False, "reason": "load_master_failed", "error": str(exc)[:240]}
        dump = master.model_dump() if hasattr(master, "model_dump") else dict(master or {})
    else:
        try:
            bundle = load_fn(db, project_id, scene_id)
        except TypeError:
            try:
                bundle = load_fn(project_id, scene_id)
            except Exception as exc:
                return {"available": False, "reason": "scene_bundle_load_failed", "error": str(exc)[:240]}
        except Exception as exc:
            return {"available": False, "reason": "scene_bundle_load_failed", "error": str(exc)[:240]}
        if not bundle:
            return {"available": False, "reason": "scene_not_found", "sceneId": scene_id}
        master = bundle.get("master") if isinstance(bundle, dict) else None
        if master is None:
            return {"available": False, "reason": "master_missing", "sceneId": scene_id}
        dump = master.model_dump() if hasattr(master, "model_dump") else dict(master)

    publish = dump.get("scenePublish")
    final_check = dump.get("sceneFinalCheck")
    return {
        "available": True,
        "sceneId": scene_id,
        "sceneFinalCheck": final_check,
        "scenePublish": {
            "upscaledAssetId": (publish or {}).get("upscaledAssetId") if isinstance(publish, dict) else None,
            "upscalePendingPublish": (publish or {}).get("upscalePendingPublish")
            if isinstance(publish, dict)
            else None,
            "publishedAssetId": (publish or {}).get("publishedAssetId") if isinstance(publish, dict) else None,
            "raw": publish if isinstance(publish, dict) else publish,
        },
        "source": "timeline.master (same truth as timeline.get_workspace)",
    }


def assemble_post_production_context(
    db: Session,
    project_id: str,
    *,
    domains: Any = None,
    scene_id: str | None = None,
    include_timeline_publish: bool = False,
    include_presets: bool = False,
    include_jobs: bool = False,
    include_receipts: bool = False,
) -> dict[str, Any]:
    """Assemble freeze-shaped PostProductionContextPackage from live MAGI stores."""
    from ....magi.color_grading import list_color_presets
    from ....magi.finishing import finishing_of
    from ....magi.readiness import readiness_payload
    from ....magi.sequence.store import get_sequence

    wanted = normalize_domains(domains)
    want_all = "all" in wanted

    seq = get_sequence(project_id)
    tracks = seq.get("tracks") or []
    tracks_by_id = {str(t.get("id")): t for t in tracks if isinstance(t, dict)}
    raw_clips = [c for c in (seq.get("clips") or []) if isinstance(c, dict)]
    clips = [_clip_summary(c, tracks_by_id) for c in raw_clips[:40]]
    clips_truncated = len(raw_clips) > 40
    finishing = finishing_of(seq)

    package: dict[str, Any] = {
        "projectId": project_id,
        "generatedAt": _utc_now(),
        "domains": sorted(wanted),
        "magiSequenceId": seq.get("id") or seq.get("sequenceId") or project_id,
        "sequenceSummary": {
            "frameRate": seq.get("frameRate"),
            "trackCount": len(tracks),
            "clipCount": len(clips),
            "durationFrames": seq.get("durationFrames"),
        },
        "playhead": seq.get("playheadFrame") or 0,
        "timecode": seq.get("playheadFrame") or 0,
        "selectedClipIds": None,
        "selectedClipIdsNote": (
            "Clip selection is ephemeral editor UI state and is not persisted; "
            "selectedClipIds is intentionally null."
        ),
        "clips": clips,
        "clipsTruncated": bool(locals().get("clips_truncated")),
        "finishing": {
            "clipGrades": dict(finishing.get("clipGrades") or {}),
            "audio": finishing.get("audio"),
            "lastRender": finishing.get("render") or finishing.get("lastRender"),
        },
        "readiness": _compact_readiness(readiness_payload()),
        "exportLedger": dict(seq.get("exportLedger") or {}),
        "notSupported": [
            "magi.trim/split/move/overlay mutate (UI-only)",
            "CD Publish / Final Check / Timeline persistScenePublish upscale",
            "Mix assist (gain/duck/loudness)",
            "Dissolve/Brighten/Stabilize/Silence as real engines (placebo — refuse)",
            "Overlay burn into final video (stub — refuse until Bot2)",
            "LUT import / interactive curves / scopes",
        ],
        "_evidence": {
            "source": "magi_post_context.assemble_post_production_context",
            "stores": [
                "magi.sequence.store.get_sequence",
                "magi.readiness.readiness_payload",
            ],
        },
    }

    if scene_id:
        package["sceneId"] = scene_id

    if include_timeline_publish or want_all or "export" in wanted:
        package["timelinePublish"] = _timeline_publish_slice(db, project_id, scene_id)
        if package["timelinePublish"] is None:
            package["timelinePublish"] = {
                "available": False,
                "reason": "sceneId_required",
                "note": "Pass sceneId to assemble timelinePublish from Timeline master only.",
            }

    if include_presets or want_all or "color" in wanted:
        presets = list_color_presets()
        package["colorPresetsSummary"] = [
            {"id": p.get("id"), "label": p.get("label")}
            for p in presets
        ]

    if include_jobs or want_all or "finish" in wanted or "upscale" in wanted:
        package["openJobs"] = _open_jobs(db, project_id)
        package["_evidence"]["stores"].append("Job(kind like magi_%)")

    if include_receipts or want_all:
        package["receipts"] = _recent_receipts(db, project_id)
        package["_evidence"]["stores"].append("CoDirectorToolInvocation(magi.*)")

    if not want_all:
        if "color" not in wanted and "finish" not in wanted:
            package["finishing"]["clipGrades"] = {}
            package.pop("colorPresetsSummary", None)
        if "sound" not in wanted and "music" not in wanted and "finish" not in wanted:
            package["finishing"]["audio"] = None

    package["audioStudioMix"] = {
        "authority": "NOT MAGI",
        "notMagiAuthority": True,
        "note": (
            "Audio Studio mix is adjacent — NOT MAGI authority. "
            "MAGI mix truth is sequence.finishing.audio only. "
            "Use audio.scene_status for Audio Studio; do not unify authorities."
        ),
    }
    # MAGI mix authority (Bot2 P0): finishing.audio only — already on package["finishing"]["audio"]
    package["magiMixAuthority"] = {
        "store": "sequence.finishing.audio",
        "notMagiAuthority": False,
        "note": "Only finishing.audio is MAGI mix truth.",
    }

    return package
