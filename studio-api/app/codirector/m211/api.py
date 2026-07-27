"""FastAPI routes for Co-Director M2.11 Production Intelligence."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ... import feature_flags as feature_flags_mod
from ...db import get_db
from ..intelligence.specialist_registry import SpecialistRegistry
from .dag import DEFAULT_PIPELINE, specialist_graph
from .decisions import DecisionRecordStore
from .flags import FLAG_NAME, production_intelligence_enabled
from .memory import ProductionMemoryStore
from .orchestrator import SMOKE_BRIEF, ProductionIntelligenceOrchestrator
from .platform import platform_summary
from .review_loop import ReviewLoopService
from .traces import ExecutionTraceStore

router = APIRouter(prefix="/m211", tags=["codirector-m211"])


def _flag(name: str = FLAG_NAME) -> bool:
    return bool(getattr(feature_flags_mod.feature_flags, name, False))


def _require(name: str = FLAG_NAME) -> None:
    if _flag(name):
        return
    raise HTTPException(
        status_code=404,
        detail="M2.11 production intelligence capability is not enabled.",
    )


class OrchestrateBody(BaseModel):
    projectId: str
    brief: str = SMOKE_BRIEF
    sceneId: Optional[str] = None
    modelUsed: str = "gemma"


class MemoryCreateBody(BaseModel):
    projectId: str
    content: str
    category: str = "note"
    sceneId: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionApproveBody(BaseModel):
    projectId: str
    status: str = "approved"


class ReviewStartBody(BaseModel):
    projectId: str
    sceneId: Optional[str] = None


class ReviewAdvanceBody(BaseModel):
    action: str = "next"
    note: str = ""
    approval: Optional[dict[str, Any]] = None


@router.get("/status")
async def m211_status() -> dict[str, Any]:
    _require()
    return {
        "enabled": production_intelligence_enabled(),
        "flag": FLAG_NAME,
        "pipelineStages": [n.stage_id for n in DEFAULT_PIPELINE],
        "mutationPolicy": "advise-only",
        "smokeBrief": SMOKE_BRIEF,
    }


@router.get("/specialists")
async def m211_specialists() -> dict[str, Any]:
    _require()
    inventory = SpecialistRegistry().inventory()
    return {"count": len(inventory), "specialists": inventory}


@router.get("/dag")
async def m211_dag() -> dict[str, Any]:
    _require()
    return {
        "pipeline": [n.to_dict() for n in DEFAULT_PIPELINE],
        "graph": specialist_graph(),
    }


@router.get("/platform")
async def m211_platform() -> dict[str, Any]:
    _require()
    return platform_summary()


@router.post("/orchestrate")
async def m211_orchestrate(body: OrchestrateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    result = await ProductionIntelligenceOrchestrator().run(
        db,
        project_id=body.projectId,
        brief=body.brief,
        scene_id=body.sceneId,
        model_used=body.modelUsed,
    )
    return result


@router.get("/memory")
async def m211_memory_list(
    projectId: str = Query(...),
    sceneId: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require()
    items = ProductionMemoryStore.search(
        db,
        project_id=projectId,
        query="",
        scene_id=sceneId,
        category=category,
        limit=limit,
    )
    return {"projectId": projectId, "items": items, "count": len(items)}


@router.get("/memory/search")
async def m211_memory_search(
    projectId: str = Query(...),
    q: str = "",
    sceneId: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require()
    items = ProductionMemoryStore.search(
        db,
        project_id=projectId,
        query=q,
        scene_id=sceneId,
        category=category,
        limit=limit,
    )
    return {"projectId": projectId, "query": q, "items": items, "count": len(items)}


@router.post("/memory")
async def m211_memory_create(body: MemoryCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require()
    item = ProductionMemoryStore.upsert(
        db,
        project_id=body.projectId,
        content=body.content,
        category=body.category,
        scene_id=body.sceneId,
        tags=body.tags,
        metadata=body.metadata,
    )
    return item


@router.get("/decisions")
async def m211_decisions(
    projectId: str = Query(...),
    sceneId: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require()
    rows = DecisionRecordStore.list_for_project(
        db, projectId, scene_id=sceneId, limit=limit
    )
    return {"projectId": projectId, "decisions": rows, "count": len(rows)}


@router.post("/decisions/{decision_id}/approve")
async def m211_decision_approve(
    decision_id: str,
    body: DecisionApproveBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require()
    row = DecisionRecordStore.set_approval(
        db, body.projectId, decision_id, status=body.status
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return row


@router.get("/traces")
async def m211_traces(
    projectId: str = Query(...),
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require()
    rows = ExecutionTraceStore.list_for_project(db, projectId, limit=limit)
    return {"projectId": projectId, "traces": rows, "count": len(rows)}


@router.get("/traces/{trace_id}")
async def m211_trace_get(
    trace_id: str,
    projectId: str = Query(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require()
    row = ExecutionTraceStore.get(db, projectId, trace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return row


@router.get("/dashboard")
async def m211_dashboard(
    projectId: str = Query(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require()
    specialists = SpecialistRegistry().inventory()
    decisions = DecisionRecordStore.list_for_project(db, projectId, limit=100)
    pending = [d for d in decisions if d.get("approvalRequired") and d.get("approvalStatus") == "pending"]
    traces = ExecutionTraceStore.list_for_project(db, projectId, limit=20)
    loops = ReviewLoopService.list_for_project(projectId)
    active_stage = loops[0]["stage"] if loops else "idle"
    blockers = [
        d for d in decisions if (d.get("explainability") or {}).get("blockingIssues")
    ]
    return {
        "projectId": projectId,
        "specialists": {"count": len(specialists), "inventory": specialists},
        "stage": active_stage,
        "pendingApprovals": pending,
        "health": {
            "enabled": True,
            "decisionCount": len(decisions),
            "pendingApprovalCount": len(pending),
            "traceCount": len(traces),
            "blockerCount": len(blockers),
        },
        "blockers": blockers[:20],
        "timelineStatus": {
            "mode": "advise-only",
            "mutationsApplied": False,
            "note": "M2.11 does not mutate timeline; approvals are recorded only.",
        },
        "providerHealthNote": (
            "Orchestrator uses the live Co-Director provider when available and not "
            "STUDIO_E2E; otherwise returns clearly labeled limited-analysis / heuristic "
            "specialist digests (no fake deep reasoning)."
        ),
        "reasoningModel": "gemma",
        "executionHistory": traces,
        "reviewLoops": loops,
        "platform": platform_summary(),
    }


@router.post("/review/start")
async def m211_review_start(body: ReviewStartBody) -> dict[str, Any]:
    _require()
    state = ReviewLoopService.start(body.projectId, body.sceneId)
    return state.to_dict()


@router.post("/review/{loop_id}/advance")
async def m211_review_advance(loop_id: str, body: ReviewAdvanceBody) -> dict[str, Any]:
    _require()
    try:
        state = ReviewLoopService.advance(
            loop_id, action=body.action, note=body.note, approval=body.approval
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Review loop not found") from exc
    return state.to_dict()


@router.get("/review")
async def m211_review_list(projectId: str = Query(...)) -> dict[str, Any]:
    _require()
    rows = ReviewLoopService.list_for_project(projectId)
    return {"projectId": projectId, "loops": rows, "count": len(rows)}
