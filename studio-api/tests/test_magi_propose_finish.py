"""magi.propose_finish — published master plan, honest NOT_SUPPORTED."""

from __future__ import annotations

from app.codirector.tools.definitions import ToolContext, TOOL_IDS
from app.codirector.tools.handlers import magi
from app.codirector.tools.registry import mutation_handler
from app.db import SessionLocal, init_db


def test_propose_finish_registered():
    assert "magi.propose_finish" in TOOL_IDS
    handler = mutation_handler("magi.propose_finish")
    assert handler.preview is not None
    assert handler.apply is not None


def test_propose_finish_preview_no_music_2k_and_not_supported():
    init_db()
    db = SessionLocal()
    args = {
        "assetId": "a85c2632-dd04-4450-be5d-214aa191e209",
        "intent": "Professionally finish this scene. No music. Keep original audio untouched. Upscale to 2K.",
    }
    try:
        ctx = ToolContext(db=db, project_id="unused-project", scene_id=None)
        preview = magi.preview_propose_finish(ctx, args)
        plan = magi._finish_plan(ctx, args)
    finally:
        db.close()
    text = " ".join(preview.lines)
    assert "2K" in text
    assert "2560x1440" not in text
    assert "music=None" in text
    assert "keepOriginalAudio=True" in text
    assert "NOT_SUPPORTED" in text
    assert plan["audio"]["generateMusic"] is False
    assert plan["audio"]["music"] is None
    assert plan["upscale"]["target"] == "2K"
    assert plan["notSupported"]


def test_propose_finish_refuses_required_unsupported():
    init_db()
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id="unused-project", scene_id=None)
        result = magi.apply_propose_finish(
            ctx,
            {
                "assetId": "a85c2632-dd04-4450-be5d-214aa191e209",
                "requireUnsupported": True,
                "intent": "Add EQ and 5.1 surround",
            },
        )
    finally:
        db.close()
    assert result["ok"] is False
    assert result["error"] == "NOT_SUPPORTED"
    assert result["magiActionReceipt"]["status"] == "refused"


def test_propose_finish_apply_unpublished_scene_refuses():
    init_db()
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, project_id="00000000-0000-0000-0000-000000000000", scene_id="missing-scene")
        result = magi.apply_propose_finish(ctx, {"sceneId": "missing-scene"})
    finally:
        db.close()
    assert result["ok"] is False
    assert result["error"] == "PUBLISHED_MASTER_REQUIRED"
