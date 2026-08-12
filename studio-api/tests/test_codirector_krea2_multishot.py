"""Krea 2 Phase F — Co-Director operations for Multi-Shot Image Planning.

Exercises the closed Co-Director tool registry path for the new multi-shot tools:
- create plan + shots
- add shots to existing plan
- ERS recommendation
- send approved shots to Timeline

All tests run on a disposable DB; no GPU generation.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.db import Project, Scene, SessionLocal, init_db
from app.codirector.tools.definitions import ToolContext
from app.image_pipeline.multi_shot import service as multi_shot_service
from app.image_pipeline.multi_shot.contracts import (
    MultiShotCandidateCreate,
    MultiShotPlanCreate,
    MultiShotCreate,
)


@pytest.fixture()
def db() -> Session:
    init_db()
    session = SessionLocal()
    yield session
    session.close()


def _new_project_scene(db: Session) -> tuple[str, str]:
    project_id = f"k2cd-{uuid.uuid4().hex[:10]}"
    scene_id = f"k2cd-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=project_id, name="K2 CD Multi-Shot Test"))
    db.merge(Scene(id=scene_id, project_id=project_id, name="Scene", prompt="A test scene"))
    db.commit()
    return project_id, scene_id


def _ctx(db: Session, project_id: str, scene_id: str | None = None) -> ToolContext:
    return ToolContext(db=db, project_id=project_id, scene_id=scene_id)


def _apply(tool_id: str, raw_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    definition = registry.get(tool_id)
    sanitized = sanitize_arguments(definition, raw_args)
    handler = registry.mutation_handler(tool_id).apply
    return handler(ctx, sanitized)


def _preview(tool_id: str, raw_args: dict[str, Any], ctx: ToolContext) -> Any:
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    definition = registry.get(tool_id)
    sanitized = sanitize_arguments(definition, raw_args)
    return registry.mutation_handler(tool_id).preview(ctx, sanitized)


async def _read(tool_id: str, raw_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    from app.codirector.tools import registry
    from app.codirector.tools.sanitize import sanitize_arguments

    definition = registry.get(tool_id)
    sanitized = sanitize_arguments(definition, raw_args)
    handler = registry.read_handler(tool_id)
    return await handler(ctx, sanitized)


def _create_plan(db: Session, project_id: str, scene_id: str) -> Any:
    plan = multi_shot_service.create_plan(
        db, project_id, scene_id,
        MultiShotPlanCreate(name="CD Plan", provider_id="krea2", model_id="krea2-turbo-local"),
    )
    return plan


def _add_candidate_and_approve(db: Session, plan: Any, shot: Any) -> None:
    candidate = multi_shot_service.add_candidate(
        db, plan, shot,
        MultiShotCandidateCreate(provider="krea2", model="krea2-turbo-local", asset_id=f"asset-{uuid.uuid4().hex[:8]}")
    )
    multi_shot_service.approve_candidate(db, shot, candidate)


def test_codirector_tool_create_plan_with_shots(db: Session) -> None:
    project_id, scene_id = _new_project_scene(db)
    ctx = _ctx(db, project_id, scene_id)

    preview = _preview(
        "multi_shot.create_plan",
        {
            "name": "Five Shot Sequence",
            "providerId": "krea2",
            "modelId": "krea2-turbo-local",
            "sharedVisualContext": "Overcast corridor",
            "sharedReferences": [{"role": "environment", "assetId": "ers-asset-1"}],
            "shots": [
                {"title": "Barnes enters", "prompt": "Barnes enters", "videoPrompt": "walks in"},
                {"title": "Barnes sees Kyung", "prompt": "Barnes sees Kyung", "videoPrompt": "glances"},
            ],
        },
        ctx,
    )
    assert "Five Shot Sequence" in preview.summary

    result = _apply(
        "multi_shot.create_plan",
        {
            "name": "Five Shot Sequence",
            "providerId": "krea2",
            "modelId": "krea2-turbo-local",
            "sharedVisualContext": "Overcast corridor",
            "sharedReferences": [{"role": "environment", "assetId": "ers-asset-1"}],
            "shots": [
                {"title": "Barnes enters", "prompt": "Barnes enters", "videoPrompt": "walks in"},
                {"title": "Barnes sees Kyung", "prompt": "Barnes sees Kyung", "videoPrompt": "glances"},
            ],
        },
        ctx,
    )
    assert result["ok"] is True
    assert result["projectId"] == project_id
    assert result["sceneId"] == scene_id
    plan = result["plan"]
    assert plan["name"] == "Five Shot Sequence"
    assert plan["providerId"] == "krea2"
    assert plan["modelId"] == "krea2-turbo-local"
    assert len(plan["shots"]) == 2
    assert plan["shots"][0]["title"] == "Barnes enters"
    assert plan["shots"][0]["videoPrompt"] == "walks in"
    assert plan["sharedEnvironmentReferences"][0]["assetId"] == "ers-asset-1"


def test_codirector_tool_add_shots_to_plan(db: Session) -> None:
    project_id, scene_id = _new_project_scene(db)
    plan = _create_plan(db, project_id, scene_id)
    ctx = _ctx(db, project_id, scene_id)

    result = _apply(
        "multi_shot.add_shots",
        {
            "planId": plan.id,
            "shots": [
                {"title": "New shot 1", "prompt": "One", "videoPrompt": "Hold"},
                {"title": "New shot 2", "prompt": "Two", "videoPrompt": "Pan"},
            ],
        },
        ctx,
    )
    assert result["ok"] is True
    assert result["planId"] == plan.id
    assert len(result["createdShots"]) == 2

    plan_reload = multi_shot_service.get_plan_row(db, project_id, plan.id)
    assert plan_reload is not None
    assert len(multi_shot_service.list_shot_rows(db, plan_reload)) == 2


@pytest.mark.anyio
async def test_codirector_tool_ers_recommendation(db: Session) -> None:
    project_id, scene_id = _new_project_scene(db)
    ctx = _ctx(db, project_id, scene_id)

    result = await _read("multi_shot.ers_recommendation", {"sceneId": scene_id}, ctx)
    assert result["ersAvailable"] is False
    assert result["recommended"] is True


def test_codirector_tool_send_to_timeline(db: Session) -> None:
    project_id, scene_id = _new_project_scene(db)
    plan = _create_plan(db, project_id, scene_id)
    shot_a = multi_shot_service.add_shot(db, plan, MultiShotCreate(title="A", videoPrompt="walks"))
    shot_b = multi_shot_service.add_shot(db, plan, MultiShotCreate(title="B", videoPrompt="holds"))
    _add_candidate_and_approve(db, plan, shot_a)
    _add_candidate_and_approve(db, plan, shot_b)
    ctx = _ctx(db, project_id, scene_id)

    result = _apply(
        "multi_shot.send_to_timeline",
        {"planId": plan.id, "generatorId": "ltx-local", "defaultDuration": 4.0},
        ctx,
    )
    assert result["ok"] is True
    assert result["count"] == 2
    assert len(result["created"]) == 2
    for item in result["created"]:
        assert item["batchBlockId"]
        assert item["approvedAssetId"]

    # Verify lineage persisted on shots.
    for shot in multi_shot_service.list_shot_rows(db, plan):
        assert shot.status == "sent_to_timeline"
        assert shot.timeline_batch_block_id

    # Verify Timeline batches exist.
    from app.director_timeline_w46 import service as timeline_service
    payload = timeline_service.load_timeline_bundle(db, project_id, scene_id)
    assert payload["ok"] is True
    master = payload["master"].model_dump()
    batch_ids = {b["id"] for b in master["batchBlocks"]}
    assert all(item["batchBlockId"] in batch_ids for item in result["created"])
