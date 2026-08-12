"""Compile ProductionIntent + CreativeContext from product surfaces."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from .schemas import (
    CreativeContext,
    Modality,
    ProductionIntent,
    ProductionOperation,
    SourceSurface,
)


_OP_MODALITY: dict[str, Modality] = {
    "image.generate": "image",
    "image.edit": "image",
    "video.generate": "video",
    "video.three_frame": "video",
    "video.shot_render": "video",
    "video.scene_render": "video",
    "video.timeline_render": "video",
    "video.batch_timeline": "video",
    "video.extend": "video",
    "video.lipsync": "video",
    "voice.generate": "audio",
    "music.generate": "audio",
    "sfx.generate": "audio",
    "subtitle.generate": "subtitle",
    "editor.place": "editorial",
    "asset.replace": "editorial",
    "asset.create_variation": "editorial",
    "job.cancel": "job",
    "job.retry": "job",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compile_creative_context(
    *,
    project_id: str,
    scene_id: Optional[str] = None,
    db: Any = None,
    objective: str = "",
    extra: Optional[dict[str, Any]] = None,
) -> CreativeContext:
    """Ground generation in Production / Vision / Continuity / Character bibles."""
    visual: dict[str, Any] = {}
    cinematography: dict[str, Any] = {}
    characters: list[dict[str, Any]] = []
    wardrobe: list[dict[str, Any]] = []
    environment: dict[str, Any] = {}
    lighting: dict[str, Any] = {}
    continuity: dict[str, Any] = {}
    refs: list[dict[str, Any]] = []
    prohibited: list[str] = []
    project_intent = objective

    if db is not None:
        try:
            from ..bible.context_retrieval import ContextRetrievalService

            if scene_id:
                pkg = ContextRetrievalService.generation_package(db, project_id, scene_id=scene_id)
            else:
                pkg = ContextRetrievalService.project_summary(db, project_id)
            if isinstance(pkg, dict):
                project_intent = str(
                    pkg.get("projectIntent") or pkg.get("summary") or pkg.get("title") or objective
                )
                visual = dict(pkg.get("visualLanguage") or pkg.get("visual") or {})
                cinematography = dict(pkg.get("cinematography") or {})
                characters = list(pkg.get("characters") or pkg.get("characterIdentity") or [])
                wardrobe = list(pkg.get("wardrobe") or [])
                environment = dict(pkg.get("environment") or pkg.get("location") or {})
                lighting = dict(pkg.get("lighting") or {})
                continuity = dict(pkg.get("continuity") or {})
                refs = list(pkg.get("approvedReferences") or pkg.get("references") or [])
                prohibited = list(pkg.get("prohibitedChanges") or [])
        except Exception:
            # Fail soft: empty structured context is honest; chat-only grounding is forbidden as sole source.
            pass
        try:
            from ..wiki_intelligence.maintenance import tool_wiki_context

            wiki_ctx = tool_wiki_context(db, project_id)
            if wiki_ctx.get("ok"):
                continuity.setdefault("wikiToolContext", wiki_ctx.get("context") or {})
                wiki_chars = (wiki_ctx.get("context") or {}).get("characters") or []
                if not characters and wiki_chars:
                    characters = [{"source": "wiki", "note": line} for line in wiki_chars[:8]]
                wiki_world = (wiki_ctx.get("context") or {}).get("worldAndSetting") or []
                if not environment and wiki_world:
                    environment = {"source": "wiki", "notes": wiki_world[:8]}
                wiki_visual = (wiki_ctx.get("context") or {}).get("visualIdentity") or []
                if not visual and wiki_visual:
                    visual = {"source": "wiki", "notes": wiki_visual[:8]}
        except Exception:
            pass

    if extra:
        visual.update(extra.get("visualLanguage") or {})
        continuity.update(extra.get("continuity") or {})
        if extra.get("approvedReferences"):
            refs = list(extra["approvedReferences"])

    payload = {
        "projectIntent": project_intent,
        "visualLanguage": visual,
        "cinematography": cinematography,
        "characterIdentity": characters,
        "wardrobe": wardrobe,
        "environment": environment,
        "lighting": lighting,
        "continuity": continuity,
        "approvedReferences": refs,
        "prohibitedChanges": prohibited,
        "outputPurpose": (extra or {}).get("outputPurpose") or "production",
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return CreativeContext(**payload, digest=digest)


def compile_intent(
    *,
    project_id: str,
    operation: ProductionOperation | str,
    source_surface: SourceSurface | str = "codirector",
    scene_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    prompt: str = "",
    objective: str = "",
    references: Optional[list[dict[str, Any]]] = None,
    source_assets: Optional[list[str]] = None,
    engine_preference: Optional[str] = None,
    workflow_preference: Optional[str] = None,
    quality_profile: str = "standard",
    duration: Optional[float] = None,
    aspect_ratio: Optional[str] = None,
    target_placement: Optional[dict[str, Any]] = None,
    tool_id: Optional[str] = None,
    handoff_id: Optional[str] = None,
    parent_intent_id: Optional[str] = None,
    plan_id: Optional[str] = None,
    plan_step_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    requested_by: str = "user",
    db: Any = None,
    include_creative_context: bool = True,
) -> ProductionIntent:
    op = str(operation)
    modality = _OP_MODALITY.get(op, "video")
    ctx = None
    if include_creative_context and modality in {"image", "video", "audio"}:
        ctx = compile_creative_context(
            project_id=project_id,
            scene_id=scene_id,
            db=db,
            objective=objective or prompt,
            extra=(metadata or {}).get("creativeExtra"),
        )
    now = _now()
    return ProductionIntent(
        projectId=project_id,
        sceneId=scene_id,
        shotId=shot_id,
        requestedBy=requested_by,
        sourceSurface=source_surface,  # type: ignore[arg-type]
        operation=op,  # type: ignore[arg-type]
        modality=modality,
        objective=objective or prompt,
        prompt=prompt,
        references=list(references or []),
        sourceAssets=list(source_assets or []),
        targetPlacement=target_placement,
        enginePreference=engine_preference,
        workflowPreference=workflow_preference,
        qualityProfile=quality_profile,
        duration=duration,
        aspectRatio=aspect_ratio,
        toolId=tool_id,
        handoffId=handoff_id,
        parentIntentId=parent_intent_id,
        planId=plan_id,
        planStepId=plan_step_id,
        metadata=dict(metadata or {}),
        creativeContext=ctx,
        executionState="draft",
        createdAt=now,
        updatedAt=now,
    )
