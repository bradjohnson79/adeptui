"""Closed-registry handlers for Co-Director Multi-Shot Image Planning.

Provides the operational bridge between Co-Director natural-language intent
and the authoritative Multi-Shot backend in `app.image_pipeline.multi_shot`.
All handlers are read-before-write, project-scoped, and return structured evidence
sufficient for Co-Director to verify state rather than trust a text response.
"""

from __future__ import annotations

import json
from typing import Any

from ....db import Scene
from ....image_pipeline.multi_shot import service as multi_shot_service
from ....image_pipeline.multi_shot.contracts import (
    MultiShotCreate,
    MultiShotPlanCreate,
    MultiShotReference,
    MultiShotSendToTimelineRequest,
)
from ....image_pipeline.multi_shot.models import MultiShotPlanRow, MultiShotRow
from ..definitions import ToolContext, ToolPreview


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project_id(ctx: ToolContext) -> str:
    return str(ctx.project_id or "").strip()


def _text(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    return str(value).strip() if value is not None else ""


def _require(args: dict[str, Any], key: str) -> str:
    value = _text(args, key)
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _plan(ctx: ToolContext, args: dict[str, Any]) -> MultiShotPlanRow:
    plan_id = _require(args, "planId")
    plan = multi_shot_service.get_plan_row(ctx.db, _project_id(ctx), plan_id)
    if plan is None:
        raise ValueError("Multi-Shot plan not found")
    return plan


def _shot(ctx: ToolContext, plan: MultiShotPlanRow, args: dict[str, Any]) -> MultiShotRow:
    shot_id = _require(args, "shotId")
    shot = multi_shot_service.get_shot_row(ctx.db, plan, shot_id)
    if shot is None:
        raise ValueError("Shot not found")
    return shot


def _plan_payload(db, plan: MultiShotPlanRow) -> dict[str, Any]:
    shots = []
    for shot in multi_shot_service.list_shot_rows(db, plan):
        candidates = multi_shot_service.list_candidate_rows(db, shot)
        shots.append(multi_shot_service.shot_out(shot, candidates))
    return multi_shot_service.plan_out(plan, shots=shots, shot_count=len(shots))


def _first_scene_id(db, project_id: str) -> str | None:
    scene = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.created_at).first()
    return str(scene.id) if scene else None


def _scene_id(ctx: ToolContext, args: dict[str, Any]) -> str:
    explicit = _text(args, "sceneId")
    if explicit:
        return explicit
    if ctx.scene_id:
        return ctx.scene_id
    found = _first_scene_id(ctx.db, _project_id(ctx))
    if not found:
        raise ValueError("sceneId is required and no scene exists in the project")
    return found


def _references(args: dict[str, Any]) -> list[MultiShotReference]:
    raw = args.get("sharedReferences")
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = []
    if not isinstance(raw, list):
        return []
    out: list[MultiShotReference] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            MultiShotReference(
                role=str(item.get("role") or "style"),
                asset_id=item.get("assetId") or item.get("asset_id"),
                reference_id=item.get("referenceId") or item.get("reference_id"),
                character_id=item.get("characterId") or item.get("character_id"),
                label=item.get("label"),
                notes=item.get("notes"),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Read handlers
# ---------------------------------------------------------------------------


async def list_plans(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id = _scene_id(ctx, args)
    rows = multi_shot_service.list_plans(ctx.db, _project_id(ctx), scene_id)
    return {
        "projectId": _project_id(ctx),
        "sceneId": scene_id,
        "plans": [multi_shot_service.plan_out(row, shot_count=count) for row, count in rows],
        "_evidence": {"source": "image_pipeline.multi_shot.service.list_plans"},
    }


async def get_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _plan(ctx, args)
    return {
        "projectId": _project_id(ctx),
        "plan": _plan_payload(ctx.db, plan),
        "_evidence": {"source": "image_pipeline.multi_shot.service.get_plan_row"},
    }


async def ers_recommendation(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    scene_id = _scene_id(ctx, args)
    rec = multi_shot_service.ers_recommendation_for_scene(ctx.db, _project_id(ctx), scene_id)
    return {
        "projectId": _project_id(ctx),
        "sceneId": scene_id,
        **rec,
        "_evidence": {"source": "image_pipeline.multi_shot.service.ers_recommendation_for_scene"},
    }


# ---------------------------------------------------------------------------
# Mutation: create plan
# ---------------------------------------------------------------------------


def preview_create_plan(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    name = _text(args, "name") or "Multi-Shot Plan"
    return ToolPreview(
        summary=f"Create Multi-Shot plan '{name}' with {len(args.get('shots', []) or [])} shot(s).",
        lines=[
            f"Project: {_project_id(ctx)}",
            f"Scene: {_scene_id(ctx, args)}",
            f"Provider: {_text(args, 'providerId') or 'krea2-turbo-local'}",
            f"Model: {_text(args, 'modelId') or 'krea2-turbo-local'}",
            f"Shots requested: {len(args.get('shots', []) or [])}",
        ],
        resourceKind="project",
        resourceId=_project_id(ctx),
    )


def apply_create_plan(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    project_id = _project_id(ctx)
    scene_id = _scene_id(ctx, args)
    body = MultiShotPlanCreate(
        name=_text(args, "name") or "Multi-Shot Plan",
        provider_id=_text(args, "providerId") or "krea2-turbo-local",
        model_id=_text(args, "modelId") or "krea2-turbo-local",
        shared_visual_context=_text(args, "sharedVisualContext"),
        shared_references=_references(args),
        aspect_ratio=_text(args, "aspectRatio"),
        resolution_label=_text(args, "resolutionLabel"),
        status="active",
    )
    plan = multi_shot_service.create_plan(ctx.db, project_id, scene_id, body)

    shots_data = args.get("shots") or []
    if not isinstance(shots_data, list):
        shots_data = []
    created_shots: list[dict[str, Any]] = []
    for item in shots_data:
        if not isinstance(item, dict):
            continue
        shot_body = MultiShotCreate(
            title=item.get("title") or "",
            prompt=item.get("prompt") or "",
            image_prompt=item.get("imagePrompt") or item.get("image_prompt") or "",
            video_prompt=item.get("videoPrompt") or item.get("video_prompt") or "",
            duration_hint=item.get("durationHint") if item.get("durationHint") is not None else None,
            framing=item.get("framing") or "",
            camera_angle=item.get("cameraAngle") or item.get("camera_angle") or "",
        )
        shot = multi_shot_service.add_shot(ctx.db, plan, shot_body)
        created_shots.append(multi_shot_service.shot_out(shot, candidates=[]))

    # Reload plan with shots for authoritative response.
    plan = multi_shot_service.get_plan_row(ctx.db, project_id, plan.id)
    assert plan is not None
    return {
        "ok": True,
        "projectId": project_id,
        "sceneId": scene_id,
        "plan": _plan_payload(ctx.db, plan),
        "createdShots": created_shots,
        "_evidence": {"source": "image_pipeline.multi_shot.service.create_plan + add_shot"},
    }


# ---------------------------------------------------------------------------
# Mutation: add shots to existing plan
# ---------------------------------------------------------------------------


def preview_add_shots(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Add shots to an existing Multi-Shot plan.",
        lines=[
            f"Plan: {_require(args, 'planId')}",
            f"Shots to add: {len(args.get('shots', []) or [])}",
        ],
        resourceKind="project",
        resourceId=_project_id(ctx),
    )


def apply_add_shots(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _plan(ctx, args)
    shots_data = args.get("shots") or []
    if not isinstance(shots_data, list):
        raise ValueError("shots must be a list")
    created_shots: list[dict[str, Any]] = []
    for item in shots_data:
        if not isinstance(item, dict):
            continue
        shot_body = MultiShotCreate(
            title=item.get("title") or "",
            prompt=item.get("prompt") or "",
            image_prompt=item.get("imagePrompt") or item.get("image_prompt") or "",
            video_prompt=item.get("videoPrompt") or item.get("video_prompt") or "",
            duration_hint=item.get("durationHint") if item.get("durationHint") is not None else None,
            framing=item.get("framing") or "",
            camera_angle=item.get("cameraAngle") or item.get("camera_angle") or "",
        )
        shot = multi_shot_service.add_shot(ctx.db, plan, shot_body)
        created_shots.append(multi_shot_service.shot_out(shot, candidates=[]))

    return {
        "ok": True,
        "projectId": plan.project_id,
        "sceneId": plan.scene_id,
        "planId": plan.id,
        "createdShots": created_shots,
        "_evidence": {"source": "image_pipeline.multi_shot.service.add_shot"},
    }


# ---------------------------------------------------------------------------
# Mutation: send approved shots to Timeline
# ---------------------------------------------------------------------------


def preview_send_to_timeline(ctx: ToolContext, args: dict[str, Any]) -> ToolPreview:
    return ToolPreview(
        summary="Send approved Multi-Shot images into the W46 Timeline as batch blocks.",
        lines=[
            f"Plan: {_require(args, 'planId')}",
            f"Only missing shots: {args.get('onlyMissing', True)}",
            f"Generator override: {_text(args, 'generatorId') or 'plan default / scene default'}",
        ],
        resourceKind="project",
        resourceId=_project_id(ctx),
    )


def apply_send_to_timeline(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    plan = _plan(ctx, args)
    body = MultiShotSendToTimelineRequest(
        only_missing=bool(args.get("onlyMissing", True)),
        generator_id=_text(args, "generatorId") or None,
        default_duration=float(args.get("defaultDuration", 5.0)) if args.get("defaultDuration") is not None else 5.0,
    )
    result = multi_shot_service.send_to_timeline(
        ctx.db,
        plan,
        only_missing=body.only_missing,
        generator_id=body.generator_id,
        default_duration=body.default_duration,
    )
    return {
        "ok": True,
        **result,
        "_evidence": {"source": "image_pipeline.multi_shot.service.send_to_timeline"},
    }
