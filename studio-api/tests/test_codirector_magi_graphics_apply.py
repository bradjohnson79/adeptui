"""Co-Director magi.graphics.apply tool regressions."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.codirector.tools.definitions import ToolContext
from app.codirector.tools import registry
from app.codirector.tools.sanitize import sanitize_arguments
from app.db import Project, SessionLocal, init_db


def _db() -> Session:
    init_db()
    session = SessionLocal()
    return session


def _new_project(db: Session, name: str = "MAGI Graphics Tool") -> str:
    pid = f"gfx-{uuid.uuid4().hex[:10]}"
    db.merge(Project(id=pid, name=name))
    db.commit()
    return pid


def _ctx(db: Session, project_id: str) -> ToolContext:
    return ToolContext(db=db, project_id=project_id)


def _apply(tool_id: str, raw_args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    definition = registry.get(tool_id)
    sanitized = sanitize_arguments(definition, raw_args)
    return registry.mutation_handler(tool_id).apply(ctx, sanitized)


def test_graphics_apply_preview_has_summary():
    db = _db()
    try:
        pid = _new_project(db)
        ctx = _ctx(db, pid)
        preview = registry.mutation_handler("magi.graphics.apply").preview(ctx, {"kind": "text", "text": "Hello"})
        assert "text" in preview.summary.lower()
    finally:
        db.close()


def test_graphics_apply_creates_overlay_composition():
    db = _db()
    try:
        pid = _new_project(db)
        ctx = _ctx(db, pid)
        result = _apply("magi.graphics.apply", {"kind": "text", "text": "Title"}, ctx)
        assert result["ok"] is True
        assert result["compositionId"]
        assert result["overlayCount"] == 1
    finally:
        db.close()


def test_graphics_apply_lower_third_defaults():
    db = _db()
    try:
        pid = _new_project(db)
        ctx = _ctx(db, pid)
        result = _apply("magi.graphics.apply", {"kind": "lower_third"}, ctx)
        assert result["ok"] is True
        assert result["overlayCount"] == 1
        from app.magi.overlays.store import get_composition
        comp = get_composition(pid, result["compositionId"])
        assert comp["overlays"][0]["type"] == "group"
        assert comp["overlays"][0].get("objectsTrack", 1) == 1
    finally:
        db.close()


def test_graphics_apply_routes_logo_to_objects_2():
    db = _db()
    try:
        pid = _new_project(db)
        ctx = _ctx(db, pid)
        from app.db import Asset

        asset_id = str(uuid.uuid4())
        db.add(
            Asset(
                id=asset_id,
                project_id=pid,
                tag="Adept logo",
                kind="image",
                filename="logo.png",
                path="",
            )
        )
        db.commit()
        result = _apply(
            "magi.graphics.apply",
            {"kind": "image", "assetId": asset_id, "name": "Adept logo"},
            ctx,
        )
        assert result["ok"] is True
        assert result["objectsTrack"] == 2
        from app.magi.overlays.store import get_composition

        comp = get_composition(pid, result["compositionId"])
        assert comp["overlays"][0]["objectsTrack"] == 2
    finally:
        db.close()
