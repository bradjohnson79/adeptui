"""Wave 3 gap read tools — scripts, proposals, jobs, plans, continuity, workspace, capabilities.

Handlers return typed domain dicts (plus optional `_evidence` / `_warnings` / `_pagination`
meta keys). `execute_read` wraps them into the canonical retrieval envelope.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from ....db import Asset, CoDirectorProductionPlan, Job, Project, Scene
from ....script_storyboard import ScriptDocRow, ScriptSegmentRow
from ...bible import conflicts as bible_conflicts
from ...bible.domain_service import BibleDomainService
from ...bible.proposals import ProposalService
from ...errors import PROJECT_SCOPE_VIOLATION, TOOL_TARGET_NOT_FOUND, CoDirectorError
from ...executive.store import JobStore
from ...session_context import build_session_context
from ..definitions import ToolContext
from ..read_envelope import clamp_limit

_ENTITY_TYPES = (
    "character",
    "location",
    "prop",
    "wardrobe",
    "visual_style",
    "continuity_rule",
    "continuity_state",
    "canon_record",
    "conflict_record",
    "production_decision",
)


def _project(ctx: ToolContext) -> Project:
    project = ctx.db.get(Project, ctx.project_id)
    if not project:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "Project not found.",
            details={"projectId": ctx.project_id},
            recoverable=False,
            recommended_action="none",
        )
    return project


def _page(items: list[Any], *, limit: int, cursor: Optional[str]) -> tuple[list[Any], dict[str, Any]]:
    start = 0
    if cursor:
        try:
            start = max(0, int(cursor))
        except (TypeError, ValueError):
            start = 0
    slice_ = items[start : start + limit]
    next_cursor = str(start + limit) if start + limit < len(items) else None
    return slice_, {
        "cursor": str(start) if start else None,
        "nextCursor": next_cursor,
        "total": len(items),
        "limit": limit,
        "hasMore": bool(next_cursor),
        "returnedCount": len(slice_),
        "appliedFilters": {},
    }


def _bible_entities_readonly(db: Session, project_id: str) -> list[Any]:
    """Load bible entities without calling sync_conflicts (which writes)."""
    try:
        _bible, _version, entities = BibleDomainService._current_entities(db, project_id)
        return list(entities or [])
    except Exception:
        return []


def _canonical_status(lifecycle: str | None) -> str:
    status = (lifecycle or "").lower()
    if status in {"approved", "locked", "canonical", "active"}:
        return "canonical"
    if status in {"draft", "proposed", "pending", "revision_requested"}:
        return "draft"
    if status:
        return status
    return "unknown"


# ---- project ----


async def project_get_summary(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from .... import project_service

    project = _project(ctx)
    warnings: list[dict[str, str]] = []
    available: list[str] = []
    unavailable: list[str] = []
    status = project_service.project_status(ctx.db, project)
    profile = project_service.project_profile(project)
    available.extend(["status", "profile"])

    script_count = 0
    try:
        script_count = ctx.db.query(ScriptDocRow).filter(ScriptDocRow.project_id == ctx.project_id).count()
        available.append("scripts")
    except Exception:
        unavailable.append("scripts")
        warnings.append({"code": "SCRIPTS_UNAVAILABLE", "message": "Script repository unavailable.", "section": "scripts"})

    scene_count = status.get("sceneCount")
    if scene_count is None:
        try:
            scene_count = ctx.db.query(Scene).filter(Scene.project_id == ctx.project_id).count()
            available.append("scenes")
        except Exception:
            unavailable.append("scenes")
            warnings.append({"code": "SCENES_UNAVAILABLE", "message": "Scene repository unavailable.", "section": "scenes"})
    else:
        available.append("scenes")

    character_count = 0
    try:
        from ....character_identity import service as char_svc

        profiles = char_svc.list_profiles(ctx.db, ctx.project_id)
        character_count = len(profiles or [])
        available.append("characters")
    except Exception:
        unavailable.append("characters")
        warnings.append(
            {"code": "CHARACTERS_UNAVAILABLE", "message": "Character Identity repository unavailable.", "section": "characters"}
        )

    bible_count = None
    try:
        entities = _bible_entities_readonly(ctx.db, ctx.project_id)
        bible_count = len(entities)
        available.append("production_bible")
    except Exception:
        unavailable.append("production_bible")
        warnings.append(
            {"code": "BIBLE_UNAVAILABLE", "message": "Production Bible repository unavailable.", "section": "production_bible"}
        )

    proposal_count = 0
    try:
        proposals = ProposalService.list(ctx.db, ctx.project_id, status="pending")
        proposal_count = len(proposals or [])
        available.append("proposals")
    except Exception:
        unavailable.append("proposals")
        warnings.append({"code": "PROPOSALS_UNAVAILABLE", "message": "Proposal repository unavailable.", "section": "proposals"})

    active_jobs = 0
    failed_jobs = 0
    try:
        jobs = JobStore.list_jobs(ctx.db, project_id=ctx.project_id, limit=100)
        active_jobs = sum(1 for j in jobs if getattr(j, "status", "") in {"queued", "running", "pending", "in_progress"})
        failed_jobs = sum(1 for j in jobs if getattr(j, "status", "") == "failed")
        available.append("jobs")
    except Exception:
        unavailable.append("jobs")
        warnings.append({"code": "JOBS_UNAVAILABLE", "message": "Executive job store unavailable.", "section": "jobs"})

    plan_count = 0
    try:
        plan_count = (
            ctx.db.query(CoDirectorProductionPlan).filter(CoDirectorProductionPlan.project_id == ctx.project_id).count()
        )
        available.append("plans")
    except Exception:
        unavailable.append("plans")
        warnings.append({"code": "PLANS_UNAVAILABLE", "message": "Production plan store unavailable.", "section": "plans"})

    data = {
        **status,
        "profile": profile,
        "scriptCount": script_count,
        "sceneCount": scene_count,
        "characterCount": character_count,
        "bibleEntryCount": bible_count,
        "pendingProposalCount": proposal_count,
        "activeJobCount": active_jobs if "jobs" in available else status.get("activeJobCount"),
        "failedJobCount": failed_jobs,
        "planCount": plan_count,
        "knownBlockers": [],
    }
    return {
        **data,
        "_summary": f"Project '{getattr(project, 'name', ctx.project_id)}' summary from live repositories.",
        "_evidence": [
            {
                "sourceType": "project",
                "sourceId": ctx.project_id,
                "sourceName": getattr(project, "name", None),
                "repository": "project_service",
            }
        ],
        "_warnings": warnings,
        "_availableSections": available,
        "_unavailableSections": unavailable,
    }


async def project_list_blockers(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    blockers: list[dict[str, Any]] = []
    session = build_session_context(ctx.db, project_id=ctx.project_id, active_scene_id=ctx.scene_id)
    for i, b in enumerate(session.get("unresolvedBlockers") or []):
        blockers.append(
            {
                "blocker_id": f"session-{i}-{b}",
                "category": "session",
                "severity": "warning",
                "title": str(b).replace("_", " "),
                "description": str(b),
                "source": "session_context",
                "affected_entity": ctx.project_id,
                "recommended_next_step": "Resolve the listed session blocker before production mutations.",
            }
        )
    entities = _bible_entities_readonly(ctx.db, ctx.project_id)
    for c in bible_conflicts.detect_all_conflicts(entities):
        blockers.append(
            {
                "blocker_id": f"bible-{c.get('conflictType', 'conflict')}",
                "category": "continuity",
                "severity": "warning",
                "title": str(c.get("conflictType") or "Bible continuity conflict"),
                "description": str(c.get("description") or c)[:500],
                "source": "bible.conflicts",
                "affected_entity": ctx.project_id,
                "recommended_next_step": "Review Production Bible conflicts.",
            }
        )
    return {
        "blockers": blockers,
        "_summary": f"{len(blockers)} blocker(s) from session and supported repositories.",
        "_evidence": [
            {"sourceType": "project", "sourceId": ctx.project_id, "repository": "session_context"},
        ],
    }


# ---- scripts (read-only; never get_or_create) ----


def _list_script_docs(db: Session, project_id: str) -> list[ScriptDocRow]:
    return (
        db.query(ScriptDocRow)
        .filter(ScriptDocRow.project_id == project_id)
        .order_by(ScriptDocRow.created_at.asc())
        .all()
    )


async def script_list(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    limit = clamp_limit(args.get("limit"))
    docs = _list_script_docs(ctx.db, ctx.project_id)
    items = [
        {
            "scriptId": d.id,
            "title": d.title,
            "createdAt": d.created_at.isoformat() if d.created_at else None,
            "updatedAt": d.updated_at.isoformat() if d.updated_at else None,
            "model": "script_storyboard",
        }
        for d in docs
    ]
    # M4.7 ScriptDocument list (preferred when present)
    try:
        from app.scriptwriter.store import list_documents

        for d in list_documents(ctx.db, ctx.project_id):
            items.append(
                {
                    "scriptId": d.id,
                    "title": d.title,
                    "createdAt": None,
                    "updatedAt": None,
                    "model": "scriptwriter",
                    "revision": d.revision,
                }
            )
    except Exception:
        pass
    page, pagination = _page(items, limit=limit, cursor=args.get("cursor"))
    pagination["appliedFilters"] = {k: args[k] for k in ("status", "title") if args.get(k) is not None}
    return {
        "scripts": page,
        "searchMethod": "exact field match",
        "_pagination": pagination,
        "_summary": f"{pagination['returnedCount']} script document(s).",
        "_evidence": [
            {
                "sourceType": "script",
                "sourceId": s["scriptId"],
                "sourceName": s["title"],
                "repository": s.get("model") or "script_storyboard",
            }
            for s in page
        ],
    }


async def script_get(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    script_id = str(args.get("scriptId") or "")
    # Prefer M4.7 ScriptDocument when id matches
    try:
        from app.scriptwriter.service import canonical_elements
        from app.scriptwriter.store import load_document

        sw_doc = load_document(ctx.db, script_id)
        if sw_doc and sw_doc.projectId == ctx.project_id:
            # CDX-051/052: typed HTML is the canonical content — never read
            # the stale/default elements snapshot.
            canon = canonical_elements(sw_doc)
            excerpts = [
                {"index": e.order, "type": e.type, "text": (e.text or "")[:400]}
                for e in sorted(canon, key=lambda x: x.order)[:40]
            ]
            return {
                "scriptId": sw_doc.id,
                "title": sw_doc.title,
                "segmentCount": len(canon),
                "revision": sw_doc.revision,
                "model": "scriptwriter",
                "excerpts": excerpts,
                "bodyTruncated": len(canon) > 40,
                "_summary": f"Script '{sw_doc.title}' with {len(canon)} element(s).",
                "_evidence": [
                    {
                        "sourceType": "script",
                        "sourceId": sw_doc.id,
                        "sourceName": sw_doc.title,
                        "repository": "scriptwriter",
                    }
                ],
            }
    except Exception:
        pass
    doc = ctx.db.get(ScriptDocRow, script_id)
    if not doc or doc.project_id != ctx.project_id:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "Script not found in this project.",
            details={"scriptId": script_id, "projectId": ctx.project_id},
            recoverable=False,
            recommended_action="none",
        )
    segs = (
        ctx.db.query(ScriptSegmentRow)
        .filter(ScriptSegmentRow.doc_id == doc.id, ScriptSegmentRow.project_id == ctx.project_id)
        .order_by(ScriptSegmentRow.index.asc())
        .limit(200)
        .all()
    )
    excerpts = [{"index": s.index, "type": s.segment_type, "text": (s.text or "")[:400]} for s in segs[:40]]
    return {
        "scriptId": doc.id,
        "title": doc.title,
        "segmentCount": len(segs),
        "excerpts": excerpts,
        "bodyTruncated": len(segs) > 40,
        "_summary": f"Script '{doc.title}' with {len(segs)} segment(s); body bounded.",
        "_evidence": [
            {"sourceType": "script", "sourceId": doc.id, "sourceName": doc.title, "repository": "script_storyboard"}
        ],
    }


async def script_search(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    query = str(args.get("query") or "").strip()
    limit = clamp_limit(args.get("limit"), default=25)
    if not query:
        return {"matches": [], "searchMethod": "case-insensitive text search", "_summary": "Empty query."}
    needle = query.lower()
    matches = []

    # CDX-052: script_documents_v2 is the canonical Script Writer store. When
    # a v2 document with content exists for the project, search its canonical
    # projection (typed HTML when present); the legacy script_segments
    # snapshot is searched only when no v2 content exists.
    repo = "script_storyboard"
    v2_docs: list[tuple[Any, list[dict[str, Any]]]] = []
    try:
        from app.scriptwriter.service import project_segments
        from app.scriptwriter.store import list_documents

        docs = list_documents(ctx.db, ctx.project_id) or []
        if args.get("scriptId"):
            docs = [d for d in docs if d.id == str(args["scriptId"])]
        for d in docs:
            segs = project_segments(d)
            if segs:
                v2_docs.append((d, segs))
    except Exception:
        v2_docs = []

    if v2_docs:
        repo = "scriptwriter"
        for d, segs in v2_docs:
            for s in segs:
                text = s.get("text") or ""
                if needle in text.lower():
                    idx = text.lower().index(needle)
                    start = max(0, idx - 40)
                    end = min(len(text), idx + len(query) + 40)
                    matches.append(
                        {
                            "segmentId": s.get("id"),
                            "scriptId": d.id,
                            "matchType": "case-insensitive text search",
                            "matchedField": "text",
                            "excerpt": text[start:end],
                            "sourceId": s.get("id"),
                        }
                    )
                if len(matches) >= limit:
                    break
            if len(matches) >= limit:
                break
    else:
        q = ctx.db.query(ScriptSegmentRow).filter(ScriptSegmentRow.project_id == ctx.project_id)
        if args.get("scriptId"):
            q = q.filter(ScriptSegmentRow.doc_id == str(args["scriptId"]))
        rows = q.order_by(ScriptSegmentRow.index.asc()).limit(500).all()
        for s in rows:
            text = s.text or ""
            if needle in text.lower():
                idx = text.lower().index(needle)
                start = max(0, idx - 40)
                end = min(len(text), idx + len(query) + 40)
                matches.append(
                    {
                        "segmentId": s.id,
                        "scriptId": s.doc_id,
                        "matchType": "case-insensitive text search",
                        "matchedField": "text",
                        "excerpt": text[start:end],
                        "sourceId": s.id,
                    }
                )
            if len(matches) >= limit:
                break
    return {
        "matches": matches,
        "searchMethod": "case-insensitive text search",
        "_summary": f"{len(matches)} script match(es) for '{query}'.",
        "_evidence": [
            {"sourceType": "script", "sourceId": m["scriptId"], "repository": repo} for m in matches[:10]
        ],
        "_pagination": {
            "limit": limit,
            "hasMore": False,
            "returnedCount": len(matches),
            "appliedFilters": {"query": query},
        },
    }


# ---- scene extras ----


async def scene_search(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    query = str(args.get("query") or "").strip().lower()
    limit = clamp_limit(args.get("limit"))
    scenes = ctx.db.query(Scene).filter(Scene.project_id == ctx.project_id).order_by(Scene.index.asc()).all()
    matches = []
    for s in scenes:
        blob = " ".join([s.name or "", s.summary or "", s.prompt or ""]).lower()
        if query and query not in blob:
            continue
        matches.append(
            {
                "sceneId": s.id,
                "title": s.name,
                "matchType": "case-insensitive text search",
                "matchedField": "name|summary|prompt",
            }
        )
        if len(matches) >= limit:
            break
    return {
        "matches": matches,
        "searchMethod": "case-insensitive text search",
        "_summary": f"{len(matches)} scene match(es).",
        "_evidence": [{"sourceType": "scene", "sourceId": m["sceneId"], "repository": "scene_service"} for m in matches],
    }


async def scene_list_characters(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    scene_id = str(args.get("sceneId") or ctx.scene_id or "")
    scene = ctx.db.get(Scene, scene_id)
    if not scene or scene.project_id != ctx.project_id:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "Scene not found in this project.",
            details={"sceneId": scene_id},
            recoverable=False,
            recommended_action="none",
        )
    linked: list[str] = []
    try:
        director = json.loads(scene.director_json or "{}")
        if isinstance(director, dict):
            linked = list(director.get("characterIds") or director.get("character_ids") or [])
    except Exception:
        linked = []
    textual: list[str] = []
    if not linked:
        try:
            from ....character_identity import service as char_svc

            prompt_blob = (scene.prompt or "").lower()
            for p in char_svc.list_profiles(ctx.db, ctx.project_id) or []:
                name = getattr(p, "name", None) or ""
                if name and name.lower() in prompt_blob:
                    textual.append(name)
        except Exception:
            pass
    return {
        "sceneId": scene_id,
        "canonicalCharacterIds": linked,
        "textualNameMatches": textual,
        "relationshipKind": "canonical" if linked else ("textual_match" if textual else "none"),
        "_summary": (
            f"{len(linked)} canonical character link(s)."
            if linked
            else (
                f"{len(textual)} textual name match(es); no canonical scene-character relationship stored."
                if textual
                else "No character links for this scene."
            )
        ),
        "_evidence": [{"sourceType": "scene", "sourceId": scene_id, "repository": "scene_service"}],
    }


async def scene_list_assets(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    scene_id = str(args.get("sceneId") or ctx.scene_id or "")
    scene = ctx.db.get(Scene, scene_id)
    if not scene or scene.project_id != ctx.project_id:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "Scene not found in this project.",
            details={"sceneId": scene_id},
            recoverable=False,
            recommended_action="none",
        )
    linked_ids = {
        x
        for x in (
            scene.start_asset_id,
            scene.middle_asset_id,
            scene.end_asset_id,
            scene.audio_asset_id,
            scene.lipsync_audio_asset_id,
        )
        if x
    }
    assets = []
    for asset_id in linked_ids:
        a = ctx.db.get(Asset, asset_id)
        if not a or a.project_id != ctx.project_id:
            continue
        assets.append(
            {
                "assetId": a.id,
                "name": a.filename or a.id,
                "assetType": a.kind,
                "previewUrl": None,
                "hasPreview": bool(a.path),
            }
        )
    return {
        "sceneId": scene_id,
        "assets": assets,
        "_summary": f"{len(assets)} asset(s) linked to scene.",
        "_evidence": [{"sourceType": "asset", "sourceId": x["assetId"], "repository": "assets"} for x in assets[:20]],
    }


# ---- character search / asset helpers ----


async def character_search(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    query = str(args.get("query") or "").strip().lower()
    limit = clamp_limit(args.get("limit"))
    from .... import feature_flags as feature_flags_mod
    from ....character_identity import service as char_svc

    if not feature_flags_mod.feature_flags.character_identity_v1:
        return {
            "matches": [],
            "searchMethod": "case-insensitive text search",
            "_summary": "Character Identity feature is disabled.",
            "_unavailableSections": ["characters"],
            "_warnings": [
                {
                    "code": "CHARACTERS_UNAVAILABLE",
                    "message": "Character Identity is disabled.",
                    "section": "characters",
                }
            ],
        }

    profiles = char_svc.list_profiles(ctx.db, ctx.project_id) or []
    matches = []
    for p in profiles:
        name = (getattr(p, "name", None) or "").lower()
        pid = getattr(p, "id", None)
        if query and query not in name and query not in str(pid).lower():
            continue
        matches.append(
            {
                "characterId": pid,
                "displayName": getattr(p, "name", None),
                "matchType": "case-insensitive text search",
                "matchedField": "name",
            }
        )
        if len(matches) >= limit:
            break
    return {
        "matches": matches,
        "searchMethod": "case-insensitive text search",
        "_summary": f"{len(matches)} character match(es).",
        "_evidence": [
            {"sourceType": "character", "sourceId": str(m["characterId"]), "repository": "character_identity"}
            for m in matches
        ],
    }


async def asset_list(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    limit = clamp_limit(args.get("limit"))
    query = str(args.get("query") or "").strip().lower()
    rows = ctx.db.query(Asset).filter(Asset.project_id == ctx.project_id).order_by(Asset.created_at.desc()).all()
    items = []
    for a in rows:
        blob = f"{a.filename} {a.tag} {a.kind}".lower()
        if query and query not in blob:
            continue
        items.append(
            {
                "assetId": a.id,
                "name": a.filename or a.id,
                "assetType": a.kind,
                "previewUrl": None,
                "hasPreview": bool(a.path),
                "createdAt": a.created_at.isoformat() if a.created_at else None,
            }
        )
    page, pagination = _page(items, limit=limit, cursor=args.get("cursor"))
    pagination["appliedFilters"] = {"query": query} if query else {}
    return {
        "assets": page,
        "searchMethod": "case-insensitive text search" if query else "project asset list",
        "_pagination": pagination,
        "_summary": f"{pagination['returnedCount']} asset(s).",
        "_evidence": [{"sourceType": "asset", "sourceId": x["assetId"], "repository": "assets"} for x in page],
    }


async def asset_get(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    asset_id = str(args.get("assetId") or "")
    asset = ctx.db.get(Asset, asset_id)
    if not asset:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "Asset not found in this project.",
            details={"assetId": asset_id, "projectId": ctx.project_id},
            recoverable=False,
            recommended_action="none",
        )
    if asset.project_id != ctx.project_id:
        raise CoDirectorError(
            PROJECT_SCOPE_VIOLATION,
            "Asset belongs to a different project.",
            details={"assetId": asset_id, "projectId": ctx.project_id},
            recoverable=False,
            recommended_action="none",
        )
    return {
        "assetId": asset.id,
        "name": asset.filename or asset.id,
        "assetType": asset.kind,
        "status": asset.validation_lifecycle,
        "previewUrl": None,
        "hasPreview": bool(asset.path),
        "createdAt": asset.created_at.isoformat() if asset.created_at else None,
        "_summary": f"Asset metadata for {asset.id}.",
        "_evidence": [{"sourceType": "asset", "sourceId": asset.id, "repository": "assets"}],
    }


async def asset_list_by_character(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    character_id = str(args.get("characterId") or "")
    assets = ctx.db.query(Asset).filter(Asset.project_id == ctx.project_id).all()
    linked = []
    for a in assets:
        meta = {}
        try:
            meta = json.loads(a.prompt_meta_json or "{}")
        except Exception:
            meta = {}
        labels = []
        try:
            labels = json.loads(a.labels_json or "[]")
        except Exception:
            labels = []
        hay = json.dumps({"meta": meta, "labels": labels, "tag": a.tag}, default=str)
        if character_id and character_id in hay:
            linked.append({"assetId": a.id, "name": a.filename or a.id, "previewUrl": None})
    return {
        "characterId": character_id,
        "assets": linked,
        "_summary": f"{len(linked)} asset(s) linked to character.",
        "_evidence": [{"sourceType": "asset", "sourceId": x["assetId"], "repository": "assets"} for x in linked],
    }


async def production_bible_search(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    query = str(args.get("query") or "").strip().lower()
    limit = clamp_limit(args.get("limit"))
    entities = _bible_entities_readonly(ctx.db, ctx.project_id)
    matches = []
    for e in entities:
        key = getattr(e, "entityKey", None) or getattr(e, "entity_key", None) or getattr(e, "stableId", None)
        title = getattr(e, "displayName", None) or getattr(e, "display_name", None) or key
        lifecycle = (
            getattr(e, "lifecycleStatus", None)
            or getattr(e, "lifecycle", None)
            or getattr(e, "status", None)
        )
        blob = json.dumps(
            {
                "key": key,
                "title": title,
                "type": getattr(e, "entityType", None),
                "data": getattr(e, "data", None) if hasattr(e, "data") else None,
            },
            default=str,
        ).lower()
        if query and query not in blob:
            continue
        matches.append(
            {
                "entryId": key,
                "title": title,
                "canonical_status": _canonical_status(str(lifecycle) if lifecycle else None),
                "matchType": "case-insensitive text search",
            }
        )
        if len(matches) >= limit:
            break
    return {
        "matches": matches,
        "searchMethod": "case-insensitive text search",
        "_summary": f"{len(matches)} Bible match(es).",
        "_evidence": [
            {"sourceType": "production_bible", "sourceId": str(m["entryId"]), "repository": "bible.domain"}
            for m in matches
        ],
    }


# ---- plans / proposals / jobs ----


async def production_plan_list(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    limit = clamp_limit(args.get("limit"))
    rows = (
        ctx.db.query(CoDirectorProductionPlan)
        .filter(CoDirectorProductionPlan.project_id == ctx.project_id)
        .order_by(CoDirectorProductionPlan.updated_at.desc())
        .limit(200)
        .all()
    )
    items = [
        {
            "planId": r.id,
            "title": r.title,
            "state": r.status,
            "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
            "source": "intelligence",
        }
        for r in rows
    ]
    warnings = []
    try:
        from ...m214.plan_view import production_plan_view

        view = production_plan_view(ctx.db, ctx.project_id)
        if view:
            items.append(
                {
                    "planId": f"m214:{ctx.project_id}",
                    "title": "M214 production stages",
                    "state": "scaffolded",
                    "source": "m214",
                    "honesty": "scaffolded",
                }
            )
            warnings.append(
                {
                    "code": "M214_SCAFFOLDED",
                    "message": "M214 plan view is scaffolded and must not be treated as completed step truth.",
                    "section": "plans",
                }
            )
    except Exception:
        pass
    page, pagination = _page(items, limit=limit, cursor=args.get("cursor"))
    return {
        "plans": page,
        "_pagination": pagination,
        "_warnings": warnings,
        "_summary": f"{pagination['returnedCount']} plan record(s).",
        "_evidence": [
            {"sourceType": "plan", "sourceId": p["planId"], "repository": p.get("source") or "intelligence"} for p in page
        ],
    }


async def production_plan_get(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    plan_id = str(args.get("planId") or "")
    if plan_id.startswith("m214:"):
        from ...m214.plan_view import production_plan_view

        view = production_plan_view(ctx.db, ctx.project_id)
        return {
            "plan": view,
            "source": "m214",
            "honesty": "scaffolded",
            "_warnings": [
                {
                    "code": "M214_SCAFFOLDED",
                    "message": "Scaffolded plan — steps are not inferred as complete.",
                    "section": "plans",
                }
            ],
            "_summary": "M214 scaffolded production plan view.",
            "_evidence": [{"sourceType": "plan", "sourceId": plan_id, "repository": "m214.plan_view"}],
        }
    row = ctx.db.get(CoDirectorProductionPlan, plan_id)
    if not row or row.project_id != ctx.project_id:
        raise CoDirectorError(
            TOOL_TARGET_NOT_FOUND,
            "Production plan not found in this project.",
            details={"planId": plan_id},
            recoverable=False,
            recommended_action="none",
        )
    data = json.loads(row.plan_json or "{}")
    return {
        "planId": row.id,
        "title": row.title,
        "state": row.status,
        "objective": data.get("objective") or data.get("title"),
        "steps": data.get("steps") or [],
        "dependencies": data.get("dependencies") or [],
        "blockers": data.get("blockers") or [],
        "approvals_required": data.get("approvalsRequired") or data.get("approvals_required"),
        "completed_outputs": data.get("completedOutputs") or [],
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        "source": "intelligence",
        "_summary": f"Stored plan '{row.title}' (read-only; not advanced).",
        "_evidence": [{"sourceType": "plan", "sourceId": row.id, "repository": "intelligence.store"}],
    }


async def proposal_list(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    limit = clamp_limit(args.get("limit"))
    status = args.get("state") or args.get("status")
    proposals = ProposalService.list(ctx.db, ctx.project_id, status=str(status) if status else None)
    items = [p.model_dump(mode="json") if hasattr(p, "model_dump") else dict(p) for p in (proposals or [])]
    page, pagination = _page(items, limit=limit, cursor=args.get("cursor"))
    pagination["appliedFilters"] = {"status": status} if status else {}
    return {
        "proposals": page,
        "_pagination": pagination,
        "_summary": f"{pagination['returnedCount']} proposal(s).",
        "_evidence": [
            {
                "sourceType": "proposal",
                "sourceId": str(p.get("id") or p.get("proposalId")),
                "repository": "ProposalService",
            }
            for p in page
            if p.get("id") or p.get("proposalId")
        ],
    }


async def proposal_get(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    proposal_id = str(args.get("proposalId") or "")
    p = ProposalService.get(ctx.db, ctx.project_id, proposal_id)
    data = p.model_dump(mode="json") if hasattr(p, "model_dump") else dict(p)
    return {
        **data,
        "_summary": f"Proposal '{data.get('title') or proposal_id}' (read-only).",
        "_evidence": [{"sourceType": "proposal", "sourceId": proposal_id, "repository": "ProposalService"}],
    }


async def job_list(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    limit = clamp_limit(args.get("limit"))
    source = str(args.get("source") or "executive")
    items: list[dict[str, Any]] = []
    if source in ("executive", "all"):
        jobs = JobStore.list_jobs(
            ctx.db,
            project_id=ctx.project_id,
            status=args.get("state") or args.get("status"),
            scene_id=args.get("sceneId"),
            limit=200,
        )
        for j in jobs:
            d = j.model_dump(mode="json") if hasattr(j, "model_dump") else dict(j)
            # JobOut has no progress field — never fabricate one.
            items.append(
                {
                    **d,
                    "source": "executive",
                    "progress": None,
                    "progress_available": False,
                }
            )
    if source in ("render", "all"):
        rows = ctx.db.query(Job).filter(Job.project_id == ctx.project_id).order_by(Job.created_at.desc()).limit(200).all()
        for r in rows:
            # Classic Job.progress exists but Wave 3 honesty: only expose when meaningful;
            # still label source and do not invent values beyond stored float.
            progress = float(r.progress) if r.progress is not None else None
            items.append(
                {
                    "jobId": r.id,
                    "job_type": r.kind,
                    "state": r.status,
                    "source": "render",
                    "progress": progress,
                    "progress_available": progress is not None,
                    "createdAt": r.created_at.isoformat() if r.created_at else None,
                }
            )
    page, pagination = _page(items, limit=limit, cursor=args.get("cursor"))
    return {
        "jobs": page,
        "_pagination": pagination,
        "_summary": f"{pagination['returnedCount']} job(s); progress never fabricated.",
        "_evidence": [
            {
                "sourceType": "job",
                "sourceId": str(j.get("id") or j.get("jobId")),
                "repository": j.get("source") or "executive",
            }
            for j in page
        ],
    }


async def job_get(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    job_id = str(args.get("jobId") or "")
    job = JobStore.get_job(ctx.db, job_id, project_id=ctx.project_id)
    if job:
        d = job.model_dump(mode="json") if hasattr(job, "model_dump") else dict(job)
        return {
            **d,
            "source": "executive",
            "progress": None,
            "progress_available": False,
            "_summary": f"Executive job {job_id}.",
            "_evidence": [{"sourceType": "job", "sourceId": job_id, "repository": "executive.JobStore"}],
        }
    row = ctx.db.get(Job, job_id)
    if row and row.project_id == ctx.project_id:
        return {
            "jobId": row.id,
            "state": row.status,
            "source": "render",
            "progress": float(row.progress) if row.progress is not None else None,
            "progress_available": row.progress is not None,
            "_summary": f"Render job {job_id}.",
            "_evidence": [{"sourceType": "job", "sourceId": job_id, "repository": "jobs"}],
        }
    raise CoDirectorError(
        TOOL_TARGET_NOT_FOUND,
        "Job not found in this project.",
        details={"jobId": job_id},
        recoverable=False,
        recommended_action="none",
    )


# ---- continuity ----


async def continuity_list_findings(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    limit = clamp_limit(args.get("limit"))
    findings: list[dict[str, Any]] = []
    entities = _bible_entities_readonly(ctx.db, ctx.project_id)
    for c in bible_conflicts.detect_all_conflicts(entities):
        findings.append(
            {
                "finding_id": f"bible-{c.get('conflictType', 'conflict')}-{abs(hash(c.get('description', ''))) % 10_000_000}",
                "severity": "warning",
                "category": c.get("conflictType") or "bible_conflict",
                "status": "open",
                "description": str(c.get("description") or "")[:500],
                "source": "bible.conflicts",
            }
        )
    for e in entities:
        if getattr(e, "entityType", None) == "conflict_record":
            data = getattr(e, "data", None) or {}
            if not isinstance(data, dict):
                data = {}
            findings.append(
                {
                    "finding_id": getattr(e, "entityKey", None) or getattr(e, "stableId", None),
                    "severity": "warning",
                    "category": data.get("conflictType") or "conflict_record",
                    "status": "recorded",
                    "description": str(data.get("description") or getattr(e, "displayName", "") or "")[:500],
                    "source": "bible.conflict_record",
                }
            )
    try:
        from ...vision.store import VisionStore

        sessions = VisionStore.list_sessions_for_project(ctx.db, ctx.project_id, limit=20)
        for s in sessions or []:
            sid = getattr(s, "id", None) or (s.get("id") if isinstance(s, dict) else None)
            findings.append(
                {
                    "finding_id": str(sid),
                    "severity": "info",
                    "category": "vision",
                    "status": getattr(s, "status", None) or "recorded",
                    "description": "Vision validation session available.",
                    "source": "vision.store",
                }
            )
    except Exception:
        pass
    page, pagination = _page(findings, limit=limit, cursor=args.get("cursor"))
    return {
        "findings": page,
        "_pagination": pagination,
        "_summary": f"{pagination['returnedCount']} continuity finding(s) from real stores.",
        "_evidence": [
            {
                "sourceType": "continuity",
                "sourceId": str(f["finding_id"]),
                "repository": f.get("source") or "continuity",
            }
            for f in page
        ],
        "_warnings": [
            {
                "code": "HEURISTIC_CONTINUITY_EXCLUDED",
                "message": "Learning heuristic continuity suggestions are not included as canonical findings.",
                "section": "continuity",
            }
        ],
    }


async def continuity_get_finding(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    finding_id = str(args.get("findingId") or "")
    listed = await continuity_list_findings(ctx, {"limit": 100})
    for f in listed.get("findings") or []:
        if str(f.get("finding_id")) == finding_id:
            return {
                **f,
                "_summary": f"Continuity finding {finding_id}.",
                "_evidence": [
                    {"sourceType": "continuity", "sourceId": finding_id, "repository": f.get("source") or "continuity"}
                ],
            }
    raise CoDirectorError(
        TOOL_TARGET_NOT_FOUND,
        "Continuity finding not found.",
        details={"findingId": finding_id},
        recoverable=False,
        recommended_action="none",
    )


# ---- workspace / system ----


async def workspace_get_active_context(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    data = build_session_context(
        ctx.db,
        project_id=ctx.project_id,
        active_scene_id=ctx.scene_id or args.get("sceneId"),
        active_workspace=args.get("workspace"),
        active_document_id=args.get("documentId"),
    )
    return {
        **data,
        "_summary": "Canonical session context (Wave 1 contract).",
        "_evidence": [{"sourceType": "workspace", "sourceId": ctx.project_id, "repository": "session_context"}],
    }


async def system_list_capabilities(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    _project(ctx)
    from .. import registry as tool_registry

    # Compact matrix: summarize registry counts + explicit deferred operator capabilities.
    read_count = sum(1 for d in tool_registry.all_definitions() if d.kind == "read")
    mutating_count = sum(1 for d in tool_registry.all_definitions() if d.kind == "mutating")
    caps = [
        {
            "capability_id": "registry.read_tools",
            "display_name": "Registered read tools",
            "status": "available",
            "read_available": True,
            "mutation_available": False,
            "requires_project": True,
            "requires_runtime": False,
            "provider_dependency": None,
            "reason_unavailable": None,
            "count": read_count,
        },
        {
            "capability_id": "registry.mutating_tools",
            "display_name": "Registered mutating tools (proposal-only)",
            "status": "deferred_mutation",
            "read_available": False,
            "mutation_available": False,
            "requires_project": True,
            "requires_runtime": False,
            "provider_dependency": None,
            "reason_unavailable": "Mutating tools require human-approved proposals; Wave 3 is read-only.",
            "count": mutating_count,
        },
    ]
    for deferred_id, label in (
        ("editor.place_clip", "Editor place clip"),
        ("generation.video", "Video generation"),
        ("generation.image", "Image generation"),
        ("job.retry", "Job retry"),
        ("proposal.apply", "Apply proposal"),
    ):
        caps.append(
            {
                "capability_id": deferred_id,
                "display_name": label,
                "status": "deferred",
                "read_available": False,
                "mutation_available": False,
                "requires_project": True,
                "requires_runtime": False,
                "provider_dependency": None,
                "reason_unavailable": "Deferred to later Phase 4.1 waves.",
            }
        )
    return {
        "capabilities": caps,
        "_summary": f"{len(caps)} capability rows; deferred mutations marked unavailable.",
        "_evidence": [{"sourceType": "system", "sourceId": "tool_registry", "repository": "codirector.tools.registry"}],
    }
